FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorio de logs
RUN mkdir -p /app/logs

# Copiar todos los archivos como módulo monitor
COPY . /app/monitor/

# Agregar /app al PYTHONPATH
ENV PYTHONPATH=/app

# Script de inicio que ejecuta Flask, Worker y Beat
CMD ["sh", "-c", "celery -A monitor.tareas.tareas worker --loglevel=info & celery -A monitor.tareas.tareas beat --loglevel=info & python monitor/app.py"]

