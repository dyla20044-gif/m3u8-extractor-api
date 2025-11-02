# Usa una imagen base de Python que ya tenga las dependencias comunes
FROM python:3.11-slim

# Instalar las dependencias de Playwright que permiten el headless
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
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos de requisitos e instala las bibliotecas de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar los binarios de los navegadores de Playwright (¡Esto ahora funciona en Docker!)
RUN playwright install chromium

# Copia el resto del código de la aplicación
COPY . .

# Comando para iniciar la aplicación
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:10000"]
