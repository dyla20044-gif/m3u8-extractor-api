import os
import json
import asyncio
import subprocess
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

# --- ¡NUEVO! El "Disfraz" que usaremos ---
# Este es un User-Agent de un navegador Chrome normal.
# Lo usaremos en AMBOS planes (A y B) y se lo daremos a tu app.
COMMON_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"

# Variable global para almacenar el URL capturado por el listener
link_url_global = None

# ======================================================================
# --- PLAN A: DETECTIVE RÁPIDO (YT-DLP) ---
# ======================================================================
def extract_with_yt_dlp(target_url):
    print(f"[Plan A: yt-dlp] Intentando extracción rápida de: {target_url}")
    
    command = [
        'python3', '-m', 'yt_dlp',
        '-g',                          # Obtener solo la URL
        '--no-warnings',               # No mostrar advertencias
        '--socket-timeout', '10',     # Timeout de red de 10s
        '-f', 'best[ext=mp4]/best',    # El formato que queremos
        '--no-playlist',               # No extraer playlists
        '--user-agent', COMMON_USER_AGENT, # ¡NUEVO! Usar el disfraz
        target_url
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=20)
        all_links = result.stdout.strip().split('\n')
        
        if all_links and all_links[0].startswith('http'):
            first_link = all_links[0]
            print(f"[Plan A: yt-dlp] ¡Éxito! Enlace encontrado: {first_link}")
            return first_link
        else:
            return None

    except Exception as e:
        print(f"[Plan A: yt-dlp] Falló.")
        return None

# ======================================================================
# --- PLAN B: ROBOT LENTO (PLAYWRIGHT) ---
# ======================================================================
async def extract_with_playwright_async(video_url):
    global link_url_global
    link_url_global = None
    print(f"[Plan B: Playwright] Iniciando extracción (Plan Rápido) para: {video_url}")
    
    link_found_event = asyncio.Event()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            
            # --- ¡NUEVO! Ponerle el disfraz al robot ---
            context = await browser.new_context(
                user_agent=COMMON_USER_AGENT
            )
            page = await context.new_page()

            # 2. Configurar el monitoreo del tráfico de red (Listener)
            def log_request(request, event):
                global link_url_global
                url = request.url
                
                if (".m3u8" in url or ".mp4" in url) and "chunklist" not in url:
                    if not link_url_global:
                        link_type = ".mp4" if ".mp4" in url else ".m3u8"
                        print(f"[Plan B: Playwright] ¡{link_type} Detectado!: {url}")
                        link_url_global = url
                        event.set()
            
            page.on("request", lambda req: log_request(req, link_found_event))
            
            # 3. Navegar
            print("[Plan B: Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # 4. Lógica de Clic
            try:
                print("[Plan B: Playwright] Buscando 'iframe' (7s)...")
                video_iframe = await page.wait_for_selector('iframe', timeout=7000) 
                print("[Plan B: Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                if iframe_content:
                    await iframe_content.mouse.click(x=300, y=300)
                    print("[Plan B: Playwright] Clic en iframe. Esperando enlace...")
                else:
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
            except Exception as e:
                print(f"[Plan B: Playwright] No se encontró iframe. Clic en body.")
                await page.click('body', force=True, position={'x': 500, 'y': 500})
            
            # 5. Espera Inteligente
            try:
                print("[Plan B: Playwright] Esperando por el enlace (máx 15s)...")
                await asyncio.wait_for(link_found_event.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                print("[Plan B: Playwright] Timeout de 15s alcanzado.")

        except Exception as e:
            print(f"[Plan B: Playwright] Error Crítico: {e}")
            return f"Error de Playwright (Crítico): {e}"
            
        finally:
            if 'browser' in locals() and browser:
                await browser.close()
                print("[Plan B: Playwright] Navegador cerrado.")
                
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
    
    # 1. Intentar Plan A (rápido, yt-dlp)
    link = extract_with_yt_dlp(video_url)
    
    # 2. Si Plan A falló, probar Plan B (lento, Playwright)
    if not link:
        print("[Cerebro] Plan A (yt-dlp) falló. Iniciando Plan B (Playwright)...")
        link = asyncio.run(extract_with_playwright_async(video_url))
    
    # 3. Devolver el resultado
    if link and isinstance(link, str) and ("http" in link):
        # ¡NUEVO! Devolvemos también el disfraz (User-Agent)
        return jsonify({
            "status": "success", 
            "m3u8_url": link, 
            "user_agent": COMMON_USER_AGENT, # <-- La nueva llave
            "original_url": video_url
        }), 200
    else:
        # Ambos planes fallaron
        message = link if link and "Error" in link else "No se pudo detectar el enlace (Ambos planes fallaron)."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
