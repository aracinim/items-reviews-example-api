# ---- Base ----
FROM python:3.10-slim

# Ajustes básicos de Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Dependencias del sistema (opcional pero útil para wheels)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar caché
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código (main.py, data.json, etc.)
COPY . .

# Exponer puerto 8001
EXPOSE 8001

# Comando de arranque: uvicorn en 0.0.0.0:8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
