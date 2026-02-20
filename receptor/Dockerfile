FROM python:3.11-slim

WORKDIR /app

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del receptor
COPY . /app/receptor/

# Crear directorio de logs
RUN mkdir -p /app/logs

# Configurar PYTHONPATH
ENV PYTHONPATH=/app

# Exponer puerto Flask
EXPOSE 5000

# Solo ejecutar Flask (los workers de reservas guardan directamente en Redis)
CMD ["python", "-m", "receptor.app"]
