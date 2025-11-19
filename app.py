import os
import json
import asyncio
import subprocess
from flask import Flask, request, jsonify

### LIBRERÍAS DE OPTIMIZACIÓN ###
import requests  # Para solicitudes HTTP rápidas
import re        # Para expresiones regulares rápidas
### FIN LIBRERÍAS ###

from playwright.async_api import async_playwright

app = Flask(__name__)

# Variable global para almacenar el URL capturado por el listener
link_url_global = None

# ======================================================================
# --- PLAN A: DETECTIVE RÁPIDO (YT-DLP) ---
# ======================================================================
def extract_with_yt_dlp(target_url):
    print(f"[Plan A: yt-dlp] Intentando extracción rápida de: {target_url}")
    
    command = [
        'python3', '-m', 'yt_dlp',
        '-g',
        '--no-warnings',
        '--socket-timeout', '10',
        '-f', 'best[ext=mp4]/best',
        '--no-playlist',
        target_url
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=20)
        all_links = result.stdout.strip().split('\n')
        
        if all_links and all_links[0].startswith('http'):
            first_link = all_links[0]
            print(f"[Plan A: yt-dlp] ¡Éxito! {len(all_links)} enlaces encontrados. Devolviendo el primero: {first_link}")
            return first_link
        else:
            print("[Plan A: yt-dlp] yt-dlp se ejecutó pero no devolvió un enlace http.")
            return None

    except Exception as e:
        print(f"[Plan A: yt-dlp] Falló.")
        return None


# ======================================================================
# --- PLAN B: BÚSQUEDA RÁPIDA EN HTML (requests + re) - GoStream
# (¡CORREGIDO! - Ultrarrápido, funciona si el enlace está impreso en el HTML)
# ======================================================================
def extract_with_requests_gostream(target_url):
    print(f"[Plan B: Requests Fast - GoStream] Intentando extracción de token en HTML para: {target_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Nota: requests.get sigue redirects por defecto, esto manejará enlaces cortos y largos.
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        
        # PATRÓN CORREGIDO: Busca la URL tokenizada en cualquier subdominio de goodstream.one
        pattern = r"(https?:\/\/[a-zA-Z0-9-]+\.goodstream\.one\/[^\s\"']+\.m3u8\?[^\s\"']+)"
        
        match = re.search(pattern, html_content)
        
        if match:
            link = match.group(1).replace("\\", "")
            print(f"[Plan B: Requests Fast - GoStream] ¡Éxito! Enlace capturado: {link}")
            return link
        else:
            print("[Plan B: Requests Fast - GoStream] No se encontró el patrón de URL m3u8 en el HTML.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"[Plan B: Requests Fast - GoStream] Falló la solicitud HTTP: {e}")
        return None


# ======================================================================
# --- PLAN C: ROBOT LENTO (PLAYWRIGHT) ---
# (Timeouts AGRESIVAMENTE REDUCIDOS - Último recurso, para Vimeos y otros)
# ======================================================================
async def extract_with_playwright_async(video_url):
    global link_url_global
    link_url_global = None
    print(f"[Plan C: Playwright] Iniciando extracción (Último recurso) para: {video_url}")
    
    link_found_event = asyncio.Event()

    async with async_playwright() as p:
        try:
            # Aplicamos los Timeouts agresivos (2s y 4s)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # 2. Configurar el monitoreo del tráfico de red (Listener)
            def log_request(request, event):
                global link_url_global
                url = request.url
                
                if (".m3u8" in url or ".mp4" in url) and "chunklist" not in url:
                    if not link_url_global:
                        link_type = ".mp4" if ".mp4" in url else ".m3u8"
                        print(f"[Plan C: Playwright] ¡{link_type} Detectado!: {url}")
                        link_url_global = url
                        event.set()
            
            page.on("request", lambda req: log_request(req, link_found_event))
            
            # 3. Navegar a la página
            print("[Plan C: Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # 4. Lógica de Clic (Robusta)
            try:
                # 1. Intentamos encontrar un iframe
                print("[Plan C: Playwright] Buscando 'iframe' (2s)...")
                video_iframe = await page.wait_for_selector('iframe', timeout=2000) # Timeout 2s 
                
                print("[Plan C: Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    await iframe_content.mouse.click(x=300, y=300)
                    print("[Plan C: Playwright] Clic en iframe. Esperando enlace...")
                else:
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    print("[Plan C: Playwright] Clic en body. Esperando enlace...")

            except Exception as e:
                # 2. Si NO se encuentra iframe (Timeout), clic en el body
                print(f"[Plan C: Playwright] No se encontró iframe (o error: {e}).")
                print("[Plan C: Playwright] Asumiendo video en página principal. Clic en body.")
                await page.click('body', force=True, position={'x': 500, 'y': 500})
            
            # 5. Espera Inteligente
            try:
                print("[Plan C: Playwright] Esperando por el enlace (máx 4s)...")
                await asyncio.wait_for(link_found_event.wait(), timeout=4.0) # Timeout 4s 
                print("[Plan C: Playwright] ¡Enlace capturado!")
            except asyncio.TimeoutError:
                print("[Plan C: Playwright] Timeout de 4s alcanzado. No se capturó enlace.")

        except Exception as e:
            print(f"[Plan C: Playwright] Error Crítico: {e}")
            return f"Error de Playwright (Crítico): {e}"
            
        finally:
            if 'browser' in locals() and browser:
                await browser.close()
                print("[Plan C: Playwright] Navegador cerrado.")
                
        return link_url_global


# ======================================================================
# --- ENDPOINT PRINCIPAL (El Cerebro) ---
# ======================================================================
@app.route('/extract', methods=['POST'])
def handle_extract():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Falta el campo 'url' en el cuerpo de la solicitud."}), 400

    video_url = data['url']
    link = None
    used_plan = None # Variable para registrar el plan usado
    
    # --- LÓGICA INTELIGENTE (TRES PLANES DE VELOCIDAD) ---
    
    # 1. Plan A: Intentar yt-dlp (rápido, general)
    link = extract_with_yt_dlp(video_url)
    if link:
        used_plan = "A (yt-dlp)"
    
    # 2. Plan B: Si Plan A falló, probar el optimizado para GoStream (Ultrarrápido)
    if not link and "goodstream" in video_url:
        print("[Cerebro] Plan A falló. Iniciando Plan B (Requests Fast - GoStream)...")
        link = extract_with_requests_gostream(video_url)
        if link:
            used_plan = "B (Requests Fast - GoStream)"
        
    # 3. Plan C: Si Plan A y B fallaron, usar Plan C (Playwright Lento - el último recurso)
    if not link:
        print("[Cerebro] Plan A/B fallaron. Iniciando Plan C (Playwright Lento)...")
        # El código asíncrono debe envolverse en asyncio.run()
        link = asyncio.run(extract_with_playwright_async(video_url))
        if link:
             used_plan = "C (Playwright Lento)"
    
    # 4. Devolver el resultado (AÑADIMOS used_plan a la respuesta JSON)
    if link and isinstance(link, str) and ("http" in link):
        # Éxito (de A, B o C)
        return jsonify({"status": "success", 
                        "m3u8_url": link, 
                        "original_url": video_url,
                        "plan_used": used_plan # CLAVE AÑADIDA
                       }), 200
    else:
        # Todos los planes fallaron
        message = link if link and "Error" in link else "No se pudo detectar el enlace (Todos los planes fallaron)."
        return jsonify({"status": "error", "m3u8_url": None, "message": message, "plan_used": used_plan}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
