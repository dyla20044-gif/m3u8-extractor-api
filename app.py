import os
import json
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

# Variable global para almacenar el URL m3u8 capturado por el listener
m3u8_url_global = None

# --- Función Asíncrona de Extracción con Playwright (Modificada) ---
async def extract_m3u8_url_async(video_url):
    global m3u8_url_global
    m3u8_url_global = None
    print(f"[Playwright] Iniciando extracción para: {video_url}")
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # 2. Configurar el monitoreo del tráfico de red
            def log_request(request):
                global m3u8_url_global
                url = request.url
                if ".m3u8" in url and "chunklist" not in url:
                    if not m3u8_url_global:
                        print(f"[Playwright] ¡M3U8 Detectado!: {url}")
                        m3u8_url_global = url
                        
            page.on("request", log_request)
            
            # 3. Navegar y forzar el inicio del streaming
            print("[Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000) # 30s para cargar
            
            # --- MODIFICACIÓN CLAVE ---
            # Aumentamos el tiempo de espera para encontrar el iframe
            print("[Playwright] Buscando el iframe del video (hasta 10s)...")
            video_iframe = await page.wait_for_selector(
                'iframe[name*="video"], iframe[id*="embed"], iframe[src*="stream"], iframe[src*="filemoon"]', 
                timeout=10000 # Aumentado de 5s a 10s
            )
            
            if video_iframe:
                print("[Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    # Hacemos clic y esperamos más tiempo
                    await iframe_content.mouse.click(x=300, y=300)
                    
                    print("[Playwright] Clic realizado. Esperando 12 segundos a que cargue el m3u8...")
                    await asyncio.sleep(12) # Aumentado de 8s a 12s
                else:
                    print("[Playwright] Fallback (iframe vacío). Clic en body.")
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    await asyncio.sleep(10) # Aumentado de 5s a 10s
            else:
                 print("[Playwright] Fallback (no se encontró iframe). Clic en body.")
                 await page.click('body', force=True, position={'x': 500, 'y': 500})
                 await asyncio.sleep(10) # Aumentado de 5s a 10s

        except Exception as e:
            print(f"[Playwright] Error: {e}")
            return f"Error de Playwright: {e}"
            
        finally:
            if 'browser' in locals() and browser:
                await browser.close()
                print("[Playwright] Navegador cerrado.")
                
        return m3u8_url_global

# --- Endpoint del API (Flask) ---
@app.route('/extract', methods=['POST'])
def handle_extract():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Falta el campo 'url' en el cuerpo de la solicitud."}), 400

    video_url = data['url']
    
    # Ejecutamos la función asíncrona
    m3u8_link = asyncio.run(extract_m3u8_url_async(video_url))

    # Devolver el resultado
    if m3u8_link and isinstance(m3u8_link, str) and ("http" in m3u8_link):
        return jsonify({"status": "success", "m3u8_url": m3u8_link, "original_url": video_url}), 200
    else:
        message = m3u8_link if m3u8_link and "Error" in m3u8_link else "No se pudo detectar el enlace .m3u8 (Playwright)."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
