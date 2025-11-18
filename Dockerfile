# Usa una imagen base de Python oficial, que es ligera.
# Usa una imagen base de Python estable y compatible con las dependencias de Playwright
FROM python:3.11-slim-bullseye

# =========================================================
# PASO 1: INSTALAR DEPENDENCIAS DEL SISTEMA OPERATIVO
# Se instala un conjunto de librerías esenciales para que Chrome funcione.
# =========================================================
# Se instalan las librerías necesarias para que Chrome (de Playwright) funcione
# en el entorno Linux de Render. La lista ha sido ajustada para evitar errores de
# paquetes descontinuados.
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libasound2 \
    libicu-dev \
    libwebp-dev \
    libglib2.0-0 \
    libgdk-pixbuf2.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libxdamage1 \
    libxfixes3 \
    libxtst6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# =========================================================
# PASO 2: INSTALAR DEPENDENCIAS DE PYTHON Y EL NAVEGADOR
# =========================================================
# Establece el directorio de trabajo
WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Esto ahora funciona porque las dependencias del sistema están correctas.
RUN playwright install chromium

# =========================================================
# PASO 3: COPIAR Y EJECUTAR LA APLICACIÓN
# =========================================================
# Copia el resto del código (incluyendo app.py)
COPY . .

# Comando para iniciar la aplicación con Gunicorn en el puerto 10000 de Render
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:10000"]
