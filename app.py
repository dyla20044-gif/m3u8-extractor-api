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
# ... (Este código se queda igual) ...
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
        # Lo separamos por el salto de línea '\n'
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
# --- NUEVO PLAN B: BÚSQUEDA RÁPDA EN HTML (requests + re) ---
# (Se ejecuta si el Plan A falla, es mucho más rápido que Playwright)
# ======================================================================
def extract_with_requests_fast(target_url):
    print(f"[Plan B: Requests Fast] Intentando extracción de token en HTML para: {target_url}")
    
    # 1. Parche de seguridad para que el servidor no nos bloquee
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # 2. Descargar el contenido de la página
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status() # Lanza error si la descarga falla
        html_content = response.text
        
        # 3. Expresión Regular para buscar la URL. 
        # Busca el patrón que viste: una URL que empieza con "https://hls" y termina en ".m3u8" seguido por el token.
        # El patrón simplificado es: la ruta hls2 + cualquier cosa + .m3u8 + ? + cualquier cosa
        pattern = r"(https:\/\/hls\d?\.goodstream\.one\/[^\s]+?\.m3u8\?t=[^\s\"]+)"
        
        match = re.search(pattern, html_content)
        
        if match:
            # Devuelve el primer grupo capturado (la URL completa)
            link = match.group(1).replace("\\", "") # Limpia cualquier barra invertida que pueda aparecer en el HTML
            print(f"[Plan B: Requests Fast] ¡Éxito! Enlace capturado: {link}")
            return link
        else:
            print("[Plan B: Requests Fast] No se encontró el patrón de URL m3u8 en el HTML.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"[Plan B: Requests Fast] Falló la solicitud HTTP: {e}")
        return None


# ======================================================================
# --- PLAN C: ROBOT LENTO (PLAYWRIGHT) ---
# (Se ejecuta SOLO SI el Plan A y el NUEVO Plan B fallan)
# ======================================================================
async def extract_with_playwright_async(video_url):
    global link_url_global
    link_url_global = None
    print(f"[Plan C: Playwright] Iniciando extracción (Último recurso) para: {video_url}")
    
    # Creamos un "Evento" (bandera)
    link_found_event = asyncio.Event()

    async with async_playwright() as p:
        try:
            # ... (Mantenemos los cambios de timeout del plan 3 aquí) ...
            
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
                        print(f"[Plan C: Playwright] ¡{link_type} Detectado!: {url}")
                        link_url_global = url
                        # Levanta la "bandera"
                        event.set()
            
            page.on("request", lambda req: log_request(req, link_found_event))
            
            # 3. Navegar a la página
            print("[Plan C: Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # 4. Lógica de Clic (Robusta)
            try:
                # 1. Intentamos encontrar un iframe
                print("[Plan C: Playwright] Buscando 'iframe' (4s)...")
                video_iframe = await page.wait_for_selector('iframe', timeout=4000) # Timeout 4s
                
                print("[Plan C: Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    await iframe_content.mouse.click(x=300, y=300)
                    print("[Plan C: Playwright] Clic en iframe. Esperando enlace...")
                else:
                    print("[Plan C: Playwright] Iframe vacío, clic en body.")
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    print("[Plan C: Playwright] Clic en body. Esperando enlace...")

            except Exception as e:
                # 2. Si NO se encuentra iframe (Timeout), clic en el body
                print(f"[Plan C: Playwright] No se encontró iframe (o error: {e}).")
                print("[Plan C: Playwright] Asumiendo video en página principal. Clic en body.")
                await page.click('body', force=True, position={'x': 500, 'y': 500})
                print("[Plan C: Playwright] Clic en body. Esperando enlace...")
            
            # 5. Espera Inteligente
            try:
                print("[Plan C: Playwright] Esperando por el enlace (máx 8s)...")
                await asyncio.wait_for(link_found_event.wait(), timeout=8.0) # Timeout 8s
                print("[Plan C: Playwright] ¡Enlace capturado!")
            except asyncio.TimeoutError:
                print("[Plan C: Playwright] Timeout de 8s alcanzado. No se capturó enlace.")

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
    
    # --- LÓGICA INTELIGENTE (TRES PLANES) ---
    
    # 1. Intentar Plan A (rápido, yt-dlp)
    link = extract_with_yt_dlp(video_url)
    
    # 2. Si Plan A falló, probar el NUEVO Plan B (Ultrarrápido, Requests + Regex)
    if not link and "goodstream" in video_url: # Solo ejecuta el Plan B si es de GoStream
        print("[Cerebro] Plan A falló. Iniciando Plan B (Requests Fast)...")
        link = extract_with_requests_fast(video_url)

    # 3. Si Plan B (y A) fallaron, probar Plan C (lento, Playwright - el último recurso)
    if not link:
        print("[Cerebro] Plan A y B fallaron. Iniciando Plan C (Playwright Lento)...")
        # El código asíncrono debe envolverse en asyncio.run()
        link = asyncio.run(extract_with_playwright_async(video_url)) 
    
    # 4. Devolver el resultado
    if link and isinstance(link, str) and ("http" in link):
        # Éxito (de A, B o C)
        # NOTA: En la extracción de GoStream, la URL incluye el token, por lo que expira.
        return jsonify({"status": "success", "m3u8_url": link, "original_url": video_url}), 200
    else:
        # Todos los planes fallaron
        message = link if link and "Error" in link else "No se pudo detectar el enlace (Todos los planes fallaron)."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
