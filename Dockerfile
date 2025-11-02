# Instalar las dependencias de Playwright que permiten el headless
# Usamos las dependencias recomendadas para Debian moderno, eliminando las obsoletas.
RUN apt-get update && apt-get install -y \
    python3-venv \
    libglib2.0-0 \
    libnss3 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgconf-2-4 \
    libatk-bridge2.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libxkbcommon0 \
    libxcursor1 \
    libasound2 \
    libx11-xcb1 \
    libdbus-1-3 \
    libxext6 \
    libxtst6 \
    libxss1 \
    libcurl4 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
