import os
import json
import subprocess # ¡Usamos esto en lugar de Playwright!
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Función de Extracción con YT-DLP ---
def extract_with_yt_dlp(target_url):
    print(f"[yt-dlp] Extrayendo de: {target_url}")
    
    # El comando para llamar a yt-dlp
    command = [
        'python3', '-m', 'yt_dlp',
        '-g',                          # Obtener solo la URL
        '--no-warnings',               # No mostrar advertencias
        '--socket-timeout', '10',     # Timeout de red de 10s
        '-f', 'best[ext=mp4]/best',    # El formato que queremos
        target_url                     # La URL de vimeos
    ]
    
    try:
        # Ejecutar el comando
        # timeout=20 pone un límite de 20s a todo el proceso
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=20)
        
        # stdout es la salida (el enlace)
        extracted_link = result.stdout.strip()
        
        if extracted_link.startswith('http'):
            print(f"[yt-dlp] Enlace encontrado: {extracted_link}")
            return extracted_link
        else:
            print(f"[yt-dlp] La salida no fue un enlace: {extracted_link}")
            return f"Error: yt-dlp no devolvió un enlace válido. Salida: {extracted_link}"

    except subprocess.CalledProcessError as e:
        # El comando yt-dlp falló (ej. video no encontrado)
        print(f"[yt-dlp] Error (CalledProcessError): {e.stderr}")
        return f"Error de yt-dlp: {e.stderr.strip()}"
    except subprocess.TimeoutExpired:
        # El proceso tardó más de 20 segundos
        print("[yt-dlp] Error: Timeout (20s) superado.")
        return "Error: El proceso de yt-dlp tardó demasiado."
    except Exception as e:
        # Otro error
        print(f"[yt-dlp] Error desconocido: {e}")
        return f"Error general de subprocess: {e}"

# --- Endpoint del API (Flask) ---
@app.route('/extract', methods=['POST'])
def handle_extract():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Falta el campo 'url' en el cuerpo de la solicitud."}), 400

    video_url = data['url']
    
    # Ejecutamos la nueva función de extracción (rápida)
    m3u8_link = extract_with_yt_dlp(video_url)

    # Devolver el resultado
    if m3u8_link and "http" in m3u8_link:
        # Éxito
        return jsonify({"status": "success", "m3u8_url": m3u8_link, "original_url": video_url}), 200
    else:
        # Error (yt-dlp no encontró nada)
        return jsonify({"status": "error", "m3u8_url": None, "message": m3u8_link}), 500

# --- Inicio del Servidor ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)
