import os
import json
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

# Variable global para almacenar el URL m3u8 capturado por el listener
m3u8_url_global = None

# --- Función Asíncrona de Extracción con Playwright ---
async def extract_m3u8_url_async(video_url):
    global m3u8_url_global
    m3u8_url_global = None
    
    # 1. Iniciar Playwright y el navegador Chrome
    async with async_playwright() as p:
        try:
            # Lanzamos el navegador en modo headless
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # 2. Configurar el monitoreo del tráfico de red (Listener)
            def log_request(request):
                global m3u8_url_global
                url = request.url
                # Captura el URL m3u8 y excluye los segmentos de video individuales
                if ".m3u8" in url and "chunklist" not in url:
                    if not m3u8_url_global:
                        m3u8_url_global = url
                        
            page.on("request", log_request)
            
            # 3. Navegar y forzar el inicio del streaming (Lógica de Iframe y Clic)
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # Búsqueda avanzada del Iframe que contiene el reproductor de video
            # Usamos un selector amplio que busca iframes con nombres o fuentes relacionadas al video
            video_iframe = await page.wait_for_selector('iframe[name*="video"], iframe[id*="embed"], iframe[src*="stream"], iframe[src*="filemoon"]', timeout=5000)
            
            if video_iframe:
                # Entrar al contexto del Iframe
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    # Hacer clic dentro del Iframe para iniciar la reproducción
                    await iframe_content.mouse.click(x=300, y=300)
                    
                    # Esperar 8 segundos para que la solicitud m3u8 se complete
                    await asyncio.sleep(8) 
                else:
                    # Fallback si el iframe está vacío
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    await asyncio.sleep(5)
            else:
                 # Fallback si no se encuentra ningún iframe (clic simple)
                 await page.click('body', force=True, position={'x': 500, 'y': 500})
                 await asyncio.sleep(5)


        except Exception as e:
            # Captura errores generales de navegación o timeout
            return f"Error de navegación, clic o tiempo de espera: {e}"
            
        finally:
            # Asegurarse de que el navegador se cierre SIEMPRE para liberar RAM en el servidor
            if 'browser' in locals() and browser:
                await browser.close()
                
        return m3u8_url_global

# --- Endpoint del API (Flask) ---
@app.route('/extract', methods=['POST'])
def handle_extract():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Falta el campo 'url' en el cuerpo de la solicitud."}), 400

    video_url = data['url']
    
    # Ejecutamos la función asíncrona de extracción
    m3u8_link = asyncio.run(extract_m3u8_url_async(video_url))

    # Devolver el resultado
    if m3u8_link and isinstance(m3u8_link, str) and ("http" in m3u8_link):
        return jsonify({"status": "success", "m3u8_url": m3u8_link, "original_url": video_url}), 200
    else:
        # En caso de no encontrar nada o si hay un error
        message = m3u8_link if m3u8_link and "Error" in m3u8_link else "No se pudo detectar el enlace .m3u8 mediante simulación de navegador."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
