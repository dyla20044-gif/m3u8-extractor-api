import os
import json
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

# --- Función Asíncrona de Extracción con Playwright (La nueva "receta") ---
async def extract_m3u8_url_async(video_url):
    """
    Inicia un navegador headless para navegar y monitorear el tráfico de red
    en busca del enlace .m3u8.
    """
    m3u8_url = None
    
    # 1. Iniciar Playwright y el navegador Chrome
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        # 2. Configurar el monitoreo del tráfico de red
        def log_request(request):
            nonlocal m3u8_url
            url = request.url
            # Buscamos enlaces que terminen en .m3u8 o contengan hls.
            if ".m3u8" in url and "chunklist" not in url:
                if not m3u8_url:
                    m3u8_url = url
                    
        page.on("request", log_request)
        
        # 3. Navegar y esperar la carga (El navegador se encargará de ejecutar JS y cargar el video)
        try:
            # Puedes ajustar el tiempo de espera si la plataforma tarda en cargar
            await page.goto(video_url, wait_until="networkidle") 
            await asyncio.sleep(5) # Dale unos segundos extra para que el reproductor inicie la petición

        except Exception as e:
            await browser.close()
            return f"Error de navegación o tiempo de espera: {e}"
            
        await browser.close()
        return m3u8_url

# --- Adaptación de Flask (El Endpoint debe ser síncrono) ---
# Flask no es naturalmente asíncrono, por lo que usamos asyncio para ejecutar la función Playwright.
@app.route('/extract', methods=['POST'])
def handle_extract():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Falta el campo 'url' en el cuerpo de la solicitud."}), 400

    video_url = data['url']
    
    # Ejecutamos la función asíncrona de extracción
    m3u8_link = asyncio.run(extract_m3u8_url_async(video_url))

    # Devolver el resultado
    if m3u8_link and isinstance(m3u8_link, str) and ("Error" not in m3u8_link) and ("http" in m3u8_link):
        return jsonify({"status": "success", "m3u8_url": m3u8_link, "original_url": video_url}), 200
    else:
        # En caso de no encontrar nada o si hay un error
        message = m3u8_link if m3u8_link and "Error" in m3u8_link else "No se pudo detectar el enlace .m3u8 mediante simulación de navegador."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
