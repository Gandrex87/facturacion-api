FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema para psycopg
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY api_server.py .

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/docs || exit 1

# Comando de inicio con logs verbosos
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
