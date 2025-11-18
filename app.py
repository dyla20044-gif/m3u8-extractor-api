import os
import json
import asyncio
import subprocess # ¡Añadido de nuevo para yt-dlp!
from flask import Flask, request, jsonify
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
# --- PLAN B: ROBOT LENTO (PLAYWRIGHT) ---
# (Se ejecuta SOLO SI el Plan A falla)
# ======================================================================
async def extract_with_playwright_async(video_url): # <--- Este es el nombre correcto
    global link_url_global
    link_url_global = None
    print(f"[Plan B: Playwright] Iniciando extracción (Plan Rápido) para: {video_url}")
    
    # Creamos un "Evento" (bandera)
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
                
                # Busca .m3u8 O .mp4
                if (".m3u8" in url or ".mp4" in url) and "chunklist" not in url:
                    if not link_url_global:
                        link_type = ".mp4" if ".mp4" in url else ".m3u8"
                        print(f"[Plan B: Playwright] ¡{link_type} Detectado!: {url}")
                        link_url_global = url
                        # Levanta la "bandera"
                        event.set()
            
            page.on("request", lambda req: log_request(req, link_found_event))
            
            # 3. Navegar a la página
            print("[Plan B: Playwright] Navegando a la página...")
            await page.goto(video_url, wait_until="load", timeout=30000)
            
            # 4. Lógica de Clic (Robusta)
            try:
                # 1. Intentamos encontrar un iframe
                print("[Plan B: Playwright] Buscando 'iframe' (7s)...")
                video_iframe = await page.wait_for_selector('iframe', timeout=7000) 
                
                print("[Plan B: Playwright] Iframe encontrado. Entrando y haciendo clic.")
                iframe_content = await video_iframe.content_frame()
                
                if iframe_content:
                    await iframe_content.mouse.click(x=300, y=300)
                    print("[Plan B: Playwright] Clic en iframe. Esperando enlace...")
                else:
                    print("[Plan B: Playwright] Iframe vacío, clic en body.")
                    await page.click('body', force=True, position={'x': 500, 'y': 500})
                    print("[Plan B: Playwright] Clic en body. Esperando enlace...")

            except Exception as e:
                # 2. Si NO se encuentra iframe (Timeout), clic en el body
                print(f"[Plan B: Playwright] No se encontró iframe (o error: {e}).")
                print("[Plan B: Playwright] Asumiendo video en página principal. Clic en body.")
                await page.click('body', force=True, position={'x': 500, 'y': 500})
                print("[Plan B: Playwright] Clic en body. Esperando enlace...")
            
            # 5. Espera Inteligente
            try:
                print("[Plan B: Playwright] Esperando por el enlace (máx 15s)...")
                await asyncio.wait_for(link_found_event.wait(), timeout=15.0)
                print("[Plan B: Playwright] ¡Enlace capturado!")
            except asyncio.TimeoutError:
                print("[Plan B: Playwright] Timeout de 15s alcanzado. No se capturó enlace.")

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
    
    # --- LÓGICA INTELIGENTE ---
    
    # 1. Intentar Plan A (rápido, yt-dlp)
    link = extract_with_yt_dlp(video_url)
    
    # 2. Si Plan A falló (devuelve None), probar Plan B (lento, Playwright)
    if not link:
        print("[Cerebro] Plan A (yt-dlp) falló. Iniciando Plan B (Playwright)...")
        
        # --- ¡AQUÍ ESTÁ LA CORRECCIÓN! ---
        # Antes decía: extract_link_url_async
        # Ahora dice:  extract_with_playwright_async
        link = asyncio.run(extract_with_playwright_async(video_url))
    
    # 3. Devolver el resultado
    if link and isinstance(link, str) and ("http" in link):
        # Éxito (de A o B)
        return jsonify({"status": "success", "m3u8_url": link, "original_url": video_url}), 200
    else:
        # Ambos planes fallaron
        message = link if link and "Error" in link else "No se pudo detectar el enlace (Ambos planes fallaron)."
        return jsonify({"status": "error", "m3u8_url": None, "message": message}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
