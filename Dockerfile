# Usa una imagen base de Python oficial, que es ligera.
FROM python:3.11-slim-bullseye

# =========================================================
# PASO 1: INSTALAR DEPENDENCIAS DEL SISTEMA OPERATIVO
# =========================================================
# Se instalan las librerías necesarias para que Chrome (de Playwright) funcione
# en el entorno Linux de Render. La lista ha sido ajustada para evitar errores
# de paquetes descontinuados.
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgconf-2-4 \
    libgtk-3-0 \
    libxshmfence6 \
    libasound2 \
    libicu-dev \
    libwebp-dev \
    libglib2.0-0 \
    libgdk-pixbuf2.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libxkbcommon0 \
    libxcursor1 \
    libdbus-1-3 \
    libxext6 \
    libxtst6 \
    libxss1 \
    libcurl4 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# =========================================================
# PASO 2: INSTALAR DEPENDENCIAS DE PYTHON Y NAVEGADOR
# =========================================================
# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos de requisitos e instala las bibliotecas de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ¡CRUCIAL! Instalar los binarios del navegador (Chrome) usando Playwright.
# Esto funciona en Docker porque ya instalamos las librerías del sistema arriba.
RUN playwright install chromium

# =========================================================
# PASO 3: INICIAR EL SERVIDOR
# =========================================================
# Copia el resto del código (incluyendo app.py)
COPY . .

# Comando para iniciar la aplicación con Gunicorn en el puerto 10000 (el estándar de Render para Docker)
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:10000"]
