import os
import json
import asyncio
import subprocess
from flask import Flask, request, jsonify

### CAMBIOS AQUÍ ###
import requests  # Importar la librería requests
import re        # Importar la librería de expresiones regulares
### FIN CAMBIOS ###

from playwright.async_api import async_playwright

app = Flask(__name__)

# Variable global para almacenar el URL capturado por el listener
link_url_global = None

# ======================================================================
# --- PLAN A: DETECTIVE RÁPIDO (YT-DLP) ---
# (Se ejecuta primero)
# ======================================================================
def extract_with_yt_dlp(target_url):
    print(f"[Plan A: yt-dlp] Intentando extracción rápida de: {target_url}")
    
    command = [
        'python3', '-m', 'yt_dlp',
        '-g',                          # Obtener solo la URL
        '--no-warnings',               # No mostrar advertencias
        '--socket-timeout', '10',     # Timeout de red de 10s
        '-f', 'best[ext=mp4]/best',    # El formato que queremos
        '--no-playlist',               # ¡MODIFICACIÓN! No extraer playlists, solo el video principal
        target_url                     # La URL
    ]
    
    try:
        # Ejecutar el comando
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=20)
        
        # stdout puede tener MÚLTIPLES enlaces, uno por línea
        all_links = result.stdout.strip().split('\n')
        
        # Tomamos solo el PRIMER enlace válido de la lista
        if all_links and all_links[0].startswith('http'):
            first_link = all_links[0]
            print(f"[Plan A: yt-dlp] ¡Éxito! {len(all_links)} enlaces encontrados. Devolviendo el primero: {first_link}")
            return first_link
        else:
            print("[Plan A: yt-dlp] yt-dlp se ejecutó pero no devolvió un enlace http.")
            return None # No se encontró ningún enlace válido

    except Exception as e:
        # Fallo de yt-dlp (ej. "Unsupported URL")
        print(f"[Plan A: yt-dlp] Falló (normal para sitios difíciles o playlists vacías).")
        return None # Indica que el Plan A falló


# ======================================================================
# --- PLAN B: BÚSQUEDA RÁPIDA EN HTML (requests + re) - GoStream
# (Ultrarrápido, funciona si el enlace está impreso en el HTML)
# ======================================================================
def extract_with_requests_gostream(target_url):
    print(f"[Plan B: Requests Fast - GoStream] Intentando extracción de token en HTML para: {target_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status() # Lanza error si la descarga falla
        html_content = response.text
        
        # Patrón para GoStream: hls2.goodstream.one/.../master.m3u8?t=...
        pattern = r"(https:\/\/hls\d?\.goodstream\.one\/[^\s]+?\.m3u8\?t=[^\s\"]+)"
        
        match = re.search(pattern, html_content)
        
        if match:
            # Devuelve el primer grupo capturado (la URL completa)
            link = match.group(1).replace("\\", "") # Limpia cualquier barra invertida que pueda aparecer en el HTML
            print(f"[Plan B: Requests Fast - GoStream] ¡Éxito! Enlace capturado: {link}")
            return link
        else:
            print("[Plan B: Requests Fast - GoStream] No se encontró el patrón de URL m3u8 en el HTML.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"[Plan B: Requests Fast - GoStream] Falló la solicitud HTTP: {e}")
        return None


# ======================================================================
# --- PLAN C: BÚSQUEDA RÁPIDA EN HTML (requests + re) - Vimeos
# (NUEVO - Ultrarrápido, funciona si el enlace está impreso en el HTML)
# ======================================================================
def extract_with_requests_vimeos(target_url):
    print(f"[Plan C: Requests Fast - Vimeos] Intentando extracción de token en HTML para: {target_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status() # Lanza error si la descarga falla
        html_content = response.text
        
        # Patrón para Vimeos: s1.vimeos.net/.../master.m3u8?t=...
        pattern = r"(https:\/\/s\d?\.vimeos\.net\/[^\s]+?\.m3u8\?t=[^\s\"]+)"
        
        match = re.search(pattern, html_content)
        
        if match:
            link = match.group(1).replace("\\", "")
            print(f"[Plan C: Requests Fast - Vimeos] ¡Éxito! Enlace capturado: {link}")
            return link
        else:
            print("[Plan C: Requests Fast - Vimeos] No se encontró el patrón de URL m3u8 en el HTML.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"[Plan C: Requests Fast - Vimeos] Falló la solicitud HTTP: {e}")
        return None


# ======================================================================
# --- PLAN D: ROBOT LENTO (PLAYWRIGHT) ---
# (Se ejecuta SOLO SI los Planes A, B y C fallan - Último recurso)
# ======================================================================
async def extract_with_playwright_async(video_url):
    global link_url_global
    link_url_global = None
    print(f"[Plan D: Playwright] Iniciando extracción (Último recurso) para: {video_url}")
    
    # Creamos un "Evento" (bandera)
    link_found_event = asyncio.Event()

    async with async_playwright() as p:
        try:
            # Aplicamos los Timeouts reducidos (4s y 8s)
            
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # 2. Configurar el monitoreo del tráfico de red (Listener)
            def log_request(request, event):
                global link_url_global
                url = request.url
                
                # Busca .m3u8 O .mp4
                if (".m3u8" in url or ".mp4" in url) and "chunklist" not in url:
                    if not link_url_global:
                        link_type = ".mp4" if ".mp4" in url else ".m3u8"
                        print(f"[Plan D: Playwright] ¡{link_type} Detectado!: {url}")
                        link_url_global = url
                        # Levanta la "bandera"
                        event.set()
            
            page.on("request", lambda req: log_request(req, link_found_event))
            
            # 3. Navegar a la página
            print("[Plan D: Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # 4. Lógica de Clic (Robusta)
            try:
                # 1. Intentamos encontrar un iframe
                print("[Plan D: Playwright] Buscando 'iframe' (4s)...")
                video_iframe = await page.wait_for_selector('iframe', timeout=4000) # Timeout 4s
                
                print("[Plan D: Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    await iframe_content.mouse.click(x=300, y=300)
                    print("[Plan D: Playwright] Clic en iframe. Esperando enlace...")
                else:
                    print("[Plan D: Playwright] Iframe vacío, clic en body.")
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    print("[Plan D: Playwright] Clic en body. Esperando enlace...")

            except Exception as e:
                # 2. Si NO se encuentra iframe (Timeout), clic en el body
                print(f"[Plan D: Playwright] No se encontró iframe (o error: {e}).")
                print("[Plan D: Playwright] Asumiendo video en página principal. Clic en body.")
                await page.click('body', force=True, position={'x': 500, 'y': 500})
                print("[Plan D: Playwright] Clic en body. Esperando enlace...")
            
            # 5. Espera Inteligente
            try:
                print("[Plan D: Playwright] Esperando por el enlace (máx 8s)...")
                await asyncio.wait_for(link_found_event.wait(), timeout=8.0) # Timeout 8s
                print("[Plan D: Playwright] ¡Enlace capturado!")
            except asyncio.TimeoutError:
                print("[Plan D: Playwright] Timeout de 8s alcanzado. No se capturó enlace.")

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
    
    # --- LÓGICA INTELIGENTE (CUATRO PLANES DE VELOCIDAD) ---
    
    # 1. Plan A: Intentar yt-dlp (rápido, general)
    link = extract_with_yt_dlp(video_url)
    
    # 2. Plan B: Si Plan A falló, probar el optimizado para GoStream (Ultrarrápido)
    if not link and "goodstream" in video_url:
        print("[Cerebro] Plan A falló. Iniciando Plan B (Requests Fast - GoStream)...")
        link = extract_with_requests_gostream(video_url)
        
    # 3. Plan C: Si Plan A y B fallaron, probar el optimizado para Vimeos (Ultrarrápido)
    if not link and "vimeos.net" in video_url:
        print("[Cerebro] Plan A/B fallaron. Iniciando Plan C (Requests Fast - Vimeos)...")
        link = extract_with_requests_vimeos(video_url)

    # 4. Plan D: Si todo falló, usar Plan D (Playwright Lento - el último recurso)
    if not link:
        print("[Cerebro] Plan A/B/C fallaron. Iniciando Plan D (Playwright Lento)...")
        # El código asíncrono debe envolverse en asyncio.run()
        link = asyncio.run(extract_with_playwright_async(video_url)) 
    
    # 5. Devolver el resultado
    if link and isinstance(link, str) and ("http" in link):
        # Éxito (de A, B, C o D)
        return jsonify({"status": "success", "m3u8_url": link, "original_url": video_url}), 200
    else:
        # Todos los planes fallaron
        message = link if link and "Error" in link else "No se pudo detectar el enlace (Todos los planes fallaron)."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
