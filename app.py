import os
import json
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

# Necesitamos una variable global para almacenar el URL m3u8 que Playwright captura
m3u8_url_global = None

# --- Función Asíncrona de Extracción con Playwright ---
async def extract_m3u8_url_async(video_url):
    global m3u8_url_global
    m3u8_url_global = None
    
    # 1. Iniciar Playwright y el navegador Chrome
    async with async_playwright() as p:
        # Usamos el modo headless para que el navegador no se abra visualmente
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 2. Configurar el monitoreo del tráfico de red (Listener)
        def log_request(request):
            global m3u8_url_global
            url = request.url
            # Buscamos enlaces que terminen en .m3u8 y excluimos los segmentos individuales
            if ".m3u8" in url and "chunklist" not in url:
                if not m3u8_url_global:
                    m3u8_url_global = url
                    
        page.on("request", log_request)
        
        # 3. Navegar y forzar el inicio del streaming (con clic)
        try:
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # --- Simular Clic en el centro del reproductor para iniciar el streaming ---
            # Esperamos un selector común para el botón de play
            await page.wait_for_selector('body', timeout=10000)

            # Hacemos clic en el centro para evitar si está detrás de un iframe o un overlay
            await page.mouse.click(x=500, y=500)
            
            # Esperamos un tiempo prudente para que la solicitud .m3u8 aparezca después del clic
            await asyncio.sleep(7) 

        except Exception as e:
            await browser.close()
            # Devolvemos un error si no se pudo navegar o hacer clic
            return f"Error de navegación, clic o tiempo de espera: {e}"
            
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
    port = int(os.environ.get('PORT', 10000)) # Usar 10000 para Docker
    app.run(host='0.0.0.0', port=port)
