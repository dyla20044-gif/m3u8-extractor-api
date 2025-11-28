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
# ======================================================================
def extract_with_requests_gostream(target_url):
    print(f"[Plan B: Requests Fast - GoStream] Intentando extracción de token en HTML para: {target_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        
        # Patrón para GoStream: hls2.goodstream.one/.../master.m3u8?t=...
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
# --- PLAN C: BÚSQUEDA RÁPIDA EN HTML (requests + re) - Dinisglows
# (NUEVO - Requiere DOBLE REQUEST para encontrar la URL intermedia)
# ======================================================================
def extract_with_requests_dinisglows(target_url):
    print(f"[Plan C: Requests Fast - Dinisglows] Iniciando extracción rápida para: {target_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # 1. Obtener la página principal (dinisglows.com) para encontrar la URL intermedia
        response_main = requests.get(target_url, headers=headers, timeout=10)
        response_main.raise_for_status()
        html_main = response_main.text
        
        # Patrón para la URL intermedia (ico3c.com/bkg/dynamic_id)
        intermediate_pattern = r"(https?:\/\/ico3c\.com\/bkg\/[a-zA-Z0-9]+)"
        match_intermediate = re.search(intermediate_pattern, html_main)
        
        if not match_intermediate:
            print("[Plan C: Dinisglows] No se encontró la URL intermedia en la página principal.")
            return None
            
        intermediate_url = match_intermediate.group(1)
        print(f"[Plan C: Dinisglows] URL intermedia encontrada: {intermediate_url}")
        
        # 2. Obtener el contenido de la página intermedia
        response_intermediate = requests.get(intermediate_url, headers=headers, timeout=10)
        response_intermediate.raise_for_status()
        html_intermediate = response_intermediate.text
        
        # 3. Extraer el M3U8 tokenizado de la página intermedia (patrón de la Network tab)
        # Este patrón es muy específico para el formato de dinisglows: dominio random/hls2/.../master.m3u8?t=...
        final_m3u8_pattern = r"(https?:\/\/[^\s\"']+\.com\/hls2\/[^\s\"']+\/master\.m3u8\?[^\s\"']+)"
        
        match_final = re.search(final_m3u8_pattern, html_intermediate)
        
        if match_final:
            link = match_final.group(1)
            print(f"[Plan C: Dinisglows] ¡Éxito! Enlace capturado: {link}")
            return link
        else:
            print("[Plan C: Dinisglows] No se encontró el patrón M3U8 final en la página intermedia.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"[Plan C: Dinisglows] Falló una solicitud HTTP: {e}")
        return None


# ======================================================================
# --- PLAN D: ROBOT LENTO (PLAYWRIGHT) ---
# (Timeouts AGRESIVAMENTE REDUCIDOS - Último recurso)
# ======================================================================
async def extract_with_playwright_async(video_url):
    global link_url_global
    link_url_global = None
    print(f"[Plan D: Playwright] Iniciando extracción (Último recurso) para: {video_url}")
    
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
                        print(f"[Plan D: Playwright] ¡{link_type} Detectado!: {url}")
                        link_url_global = url
                        event.set()
            
            page.on("request", lambda req: log_request(req, link_found_event))
            
            # 3. Navegar a la página
            print("[Plan D: Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # 4. Lógica de Clic (Robusta)
            try:
                # 1. Intentamos encontrar un iframe
                print("[Plan D: Playwright] Buscando 'iframe' (2s)...")
                video_iframe = await page.wait_for_selector('iframe', timeout=2000) # Timeout 2s 
                
                print("[Plan D: Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    # ✅ CAMBIO REALIZADO: Clic robusto en el body del iframe.
                    await iframe_content.click('body', force=True)
                    print("[Plan D: Playwright] Clic robusto en iframe ejecutado.")
                else:
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    print("[Plan D: Playwright] Clic en body. Esperando enlace...")

            except Exception as e:
                # 2. Si NO se encuentra iframe (Timeout), clic en el body
                print(f"[Plan D: Playwright] No se encontró iframe (o error: {e}).")
                print("[Plan D: Playwright] Asumiendo video en página principal. Clic en body.")
                await page.click('body', force=True, position={'x': 500, 'y': 500})
            
            # 5. Espera Inteligente
            try:
                print("[Plan D: Playwright] Esperando por el enlace (máx 4s)...")
                await asyncio.wait_for(link_found_event.wait(), timeout=4.0) # Timeout 4s 
                print("[Plan D: Playwright] ¡Enlace capturado!")
            except asyncio.TimeoutError:
                print("[Plan D: Playwright] Timeout de 4s alcanzado. No se capturó enlace.")

        except Exception as e:
            print(f"[Plan D: Playwright] Error Crítico: {e}")
            return f"Error de Playwright (Crítico): {e}"
            
        finally:
            if 'browser' in locals() and browser:
                await browser.close()
                print("[Plan D: Playwright] Navegador cerrado.")
                
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
    
    # --- LÓGICA INTELIGENTE (CUATRO PLANES DE VELOCIDAD) ---
    
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
            
    # 3. Plan C: Si Plan A y B fallaron, probar el optimizado para Dinisglows (Ultrarrápido)
    if not link and "dinisglows.com" in video_url:
        print("[Cerebro] Plan A/B fallaron. Iniciando Plan C (Requests Fast - Dinisglows)...")
        link = extract_with_requests_dinisglows(video_url)
        if link:
            used_plan = "C (Requests Fast - Dinisglows)"
        
    # 4. Plan D: Si todo falló, usar Plan D (Playwright Lento - el último recurso)
    if not link:
        print("[Cerebro] Plan A/B/C fallaron. Iniciando Plan D (Playwright Lento)...")
        # El código asíncrono debe envolverse en asyncio.run()
        link = asyncio.run(extract_with_playwright_async(video_url))
        if link:
             used_plan = "D (Playwright Lento)"
    
    # 5. Devolver el resultado (AÑADIMOS used_plan a la respuesta JSON)
    if link and isinstance(link, str) and ("http" in link):
        # Éxito (de A, B, C o D)
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
