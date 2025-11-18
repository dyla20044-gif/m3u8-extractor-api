import os
import json
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

# Variable global para almacenar el URL capturado por el listener
link_url_global = None

# --- Función Asíncrona de Extracción con Playwright (Plan RÁPIDO) ---
async def extract_link_url_async(video_url):
    global link_url_global
    link_url_global = None
    print(f"[Playwright] Iniciando extracción (Plan RÁPIDO) para: {video_url}")
    
    # --- MODIFICACIÓN DE VELOCIDAD (1) ---
    # Creamos un "Evento" de asyncio.
    # Esto es como una bandera que podemos levantar.
    link_found_event = asyncio.Event()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # 2. Configurar el monitoreo del tráfico de red (Listener)
            def log_request(request, event):
                global link_url_global
                url = request.url
                
                # --- MODIFICACIÓN DE FILTRO (.mp4) ---
                # Ahora busca .m3u8 O .mp4
                if (".m3u8" in url or ".mp4" in url) and "chunklist" not in url:
                    if not link_url_global:
                        link_type = ".mp4" if ".mp4" in url else ".m3u8"
                        print(f"[Playwright] ¡{link_type} Detectado!: {url}")
                        link_url_global = url
                        
                        # --- MODIFICACIÓN DE VELOCIDAD (2) ---
                        # Levanta la "bandera" para avisar que ya lo tenemos
                        event.set()
            
            # Le pasamos el evento al listener usando lambda
            page.on("request", lambda req: log_request(req, link_found_event))
            
            # 3. Navegar a la página
            print("[Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000) # 30s para cargar
            
            # 4. Lógica de Clic (Sigue siendo el Plan D, robusto)
            try:
                # 1. Intentamos encontrar un iframe (selector simple) con menos tiempo
                print("[Playwright] Buscando 'iframe' (7s)...")
                video_iframe = await page.wait_for_selector('iframe', timeout=7000) 
                
                print("[Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    await iframe_content.mouse.click(x=300, y=300)
                    print("[Playwright] Clic en iframe. Esperando M3U8/MP4...")
                else:
                    # Si el iframe está vacío, clic en el body
                    print("[Playwright] Iframe vacío, clic en body.")
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    print("[Playwright] Clic en body. Esperando M3U8/MP4...")

            except Exception as e:
                # 2. Si NO se encuentra iframe (Timeout), no es un error fatal.
                print(f"[Playwright] No se encontró iframe (o error: {e}).")
                print("[Playwright] Asumiendo video en página principal. Clic en body.")
                await page.click('body', force=True, position={'x': 500, 'y': 500})
                print("[Playwright] Clic en body. Esperando M3U8/MP4...")
            
            # --- MODIFICACIÓN DE VELOCIDAD (3) ---
            # En lugar de un sleep(12), esperamos el evento.
            # Esperará HASTA 15 segundos a que se levante la bandera.
            # Si la bandera se levanta en 3 segundos, continúa al instante.
            # Si no, se rendirá a los 15 segundos (timeout).
            try:
                print("[Playwright] Esperando por el enlace (máx 15s)...")
                await asyncio.wait_for(link_found_event.wait(), timeout=15.0)
                print("[Playwright] ¡Enlace capturado! Continuando...")
            except asyncio.TimeoutError:
                print("[Playwright] Timeout de 15s alcanzado. No se capturó enlace.")
            # --- FIN DE MODIFICACIONES ---

        except Exception as e:
            # Error crítico de navegación o Playwright
            print(f"[Playwright] Error Crítico: {e}")
            return f"Error de Playwright (Crítico): {e}"
            
        finally:
            if 'browser' in locals() and browser:
                await browser.close()
                print("[Playwright] Navegador cerrado.")
                
        return link_url_global

# --- Endpoint del API (Flask) ---
@app.route('/extract', methods=['POST'])
def handle_extract():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Falta el campo 'url' en el cuerpo de la solicitud."}), 400

    video_url = data['url']
    
    # Ejecutamos la función asíncrona (Plan RÁPIDO)
    link = asyncio.run(extract_link_url_async(video_url))

    # Devolver el resultado
    if link and isinstance(link, str) and ("http" in link):
        # Cambiamos la llave a "m3u8_url" para no romper tu app de Node.js
        return jsonify({"status": "success", "m3u8_url": link, "original_url": video_url}), 200
    else:
        # En caso de no encontrar nada o si hay un error
        message = link if link and "Error" in link else "No se pudo detectar el enlace .m3u8 o .mp4 (Timeout)."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
