import os
from celery import Celery
from datetime import datetime
import pytz

BROKER = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
REQUEST_QUEUE = os.getenv("HEALTHCHECK_REQUEST_QUEUE", "healthcheck.request")
RESPONSE_QUEUE = os.getenv("HEALTHCHECK_RESPONSE_QUEUE", "healthcheck.response")
SERVICE_NAME = os.getenv("SERVICE_NAME", "reservas")

TZ = pytz.timezone("America/Bogota")

def get_timestamp():
    return datetime.now(TZ).strftime("%Y/%b/%d %H:%M")

celery = Celery(
    "reservas",
    broker=BROKER,
    backend=BACKEND
)

celery.conf.task_default_queue = REQUEST_QUEUE
celery.conf.task_acks_late = True
celery.conf.worker_prefetch_multiplier = 1

@celery.task(name="reservas.process_health")
def process_health(message):
    timestamp = get_timestamp()
    print(f"Lectura de Salud Nueva - {timestamp}")
    response = {
        "status": True,
        "timestamp": timestamp,
        "service": SERVICE_NAME
    }
    celery.send_task(
        "monitor.receive_health",
        args=[response],
        queue=RESPONSE_QUEUE
    )
    return True

if __name__ == "__main__":
    celery.worker_main([
        "worker",
        "--loglevel=info",
        "-Q",
        REQUEST_QUEUE
    ])