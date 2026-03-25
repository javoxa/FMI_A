FROM python:3.11-slim

WORKDIR /app

# Copiar requirements del frontend
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto (necesario para acceder a backend/shared)
COPY . /app

# Establecer PYTHONPATH para que encuentre los módulos
ENV PYTHONPATH=/app

# Ejecutar el bot
CMD ["python", "frontend/bot/main.py"]
