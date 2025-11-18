# Usa una imagen de Python ligera
FROM python:3.11-slim-bullseye

# Instalar Python y PIP (ya viene, pero por si acaso)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar e instalar requisitos (Flask, gunicorn, yt-dlp)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copiar el resto de la app (app.py)
COPY . .

# Iniciar el servidor Gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:10000"]
