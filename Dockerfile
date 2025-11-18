# Usa una imagen base de Python más completa (no 'slim')
FROM python:3.11-bullseye

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos de requisitos
COPY requirements.txt .

# Instala las bibliotecas de Python (Flask, gunicorn, playwright, yt-dlp)
RUN pip install --no-cache-dir -r requirements.txt

# --- ¡MODIFICACIÓN CLAVE! ---
# En lugar de instalar las librerías del sistema a mano,
# usamos el comando oficial de Playwright para que él
# instale TODO lo que necesita (Chrome y sus dependencias).
RUN playwright install --with-deps chromium

# Copia el resto del código (incluyendo app.py)
COPY . .

# Comando para iniciar la aplicación
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:10000"]
