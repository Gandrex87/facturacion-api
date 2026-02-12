FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- CAMBIO AQUÍ ---
# Copiamos TODOS los archivos python (api_server.py y api_server_2.py)
COPY *.py . 

# Exponemos ambos puertos (informativo)
EXPOSE 8000 8004

# --- CAMBIO EN HEALTHCHECK ---
# Como ahora la imagen sirve para dos cosas, es mejor quitar el Healthcheck rígido del Dockerfile
# y ponerlo en el docker-compose, o hacerlo genérico. 
# Por ahora, dejemos el CMD por defecto apuntando al servicio principal (8000)
# pero lo sobrescribiremos en el compose.
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
