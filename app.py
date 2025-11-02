import os
import json
from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

# --- Función de Extracción con yt-dlp ---
def extract_m3u8_url(video_url):
    """Utiliza yt-dlp para obtener el mejor URL de streaming (m3u8)."""
    # Configuramos yt-dlp para no descargar, solo extraer metadatos
    ydl_opts = {
        'skip_download': True,      
        'listformats': False,       
        'format': 'best',           
        'quiet': True,              
        'force_generic_extractor': True, # Útil para sitios no reconocidos
        'noplaylist': True,
        'default_search': 'ytsearch',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extraer información del video
            info_dict = ydl.extract_info(video_url, download=False)
            
            # Buscar el URL m3u8. El mejor formato (HLS) suele estar en 'url' o en 'formats'.
            
            # 1. Intentar el URL directo (m3u8)
            best_url = info_dict.get('url')
            if best_url and '.m3u8' in best_url:
                return best_url
            
            # 2. Buscar en la lista de formatos
            for f in info_dict.get('formats', []):
                # Filtramos por HLS o m3u8
                if f.get('protocol') == 'hls' or (f.get('url') and '.m3u8' in f['url']):
                    return f['url']

            return "URL de streaming no encontrado."

    except Exception as e:
        return f"Error de yt-dlp: {str(e)}"

# --- Endpoint del API ---
@app.route('/extract', methods=['POST'])
def handle_extract():
    # Asegurarse de que el request tiene el formato correcto
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Falta el campo 'url' en el cuerpo de la solicitud."}), 400

    video_url = data['url']
    
    # Llamar a la función de extracción
    m3u8_link = extract_m3u8_url(video_url)

    # Devolver el resultado
    if "Error" in m3u8_link or "no encontrado" in m3u8_link:
        return jsonify({"status": "error", "m3u8_url": None, "message": m3u8_link}), 500
    else:
        return jsonify({"status": "success", "m3u8_url": m3u8_link, "original_url": video_url}), 200

# --- Inicio del Servidor ---
if __name__ == '__main__':
    # Usar el puerto que asigne el entorno de despliegue, o 5000 por defecto
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
