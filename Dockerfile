# Imagen del tablero para Fly.io (fly.toml) o para cualquier servidor con Docker, como uno de la Universidad.
FROM python:3.13-slim

# TZ: las fechas del tablero (línea base, registro) en hora de Colombia, no en la del servidor.
ENV TZ=America/Bogota \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Primero los paquetes, con las versiones fijas de requirements.txt: si solo cambia el código, Docker reutiliza esta parte.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Genera la línea base y entrena el modelo al construir, para que la primera visita no espere.
RUN python precalcular.py

EXPOSE 8080
CMD ["streamlit", "run", "app.py", "--server.port", "8080", "--server.address", "0.0.0.0", \
     "--server.headless", "true", "--server.fileWatcherType", "none"]
