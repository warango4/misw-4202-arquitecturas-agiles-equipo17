ARG PYTHON_VERSION=3.11-slim
FROM python:${PYTHON_VERSION}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorio de logs
RUN mkdir -p /app/logs

# Copiar todos los archivos como módulo reservas
COPY . /app/reservas/

# Agregar /app al PYTHONPATH
ENV PYTHONPATH=/app

# Ejecutar worker Celery (ambas colas) + Flask
CMD ["sh", "-c", "celery -A reservas.tareas.tareas worker --loglevel=info -Q ${HEALTHCHECK_REQUEST_QUEUE:-healthcheck.request},${SOLICITUDES_QUEUE:-reservas.solicitudes} & python reservas/app.py"]
