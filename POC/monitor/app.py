import os
import threading
import time
from celery import Celery
from datetime import datetime
import pytz

BROKER = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
REQUEST_QUEUE = os.getenv("HEALTHCHECK_REQUEST_QUEUE", "healthcheck.request")
RESPONSE_QUEUE = os.getenv("HEALTHCHECK_RESPONSE_QUEUE", "healthcheck.response")

TZ = pytz.timezone("America/Bogota")

def get_timestamp():
    return datetime.now(TZ).strftime("%Y/%b/%d %H:%M")

celery = Celery(
    "monitor",
    broker=BROKER,
    backend=BACKEND
)

celery.conf.task_default_queue = RESPONSE_QUEUE

@celery.task(name="monitor.receive_health")
def receive_health(data):

    timestamp = data.get("timestamp")
    status = data.get("status")
    service = data.get("service", "unknown")
    print(
        f"Respuesta recibida - {timestamp} "
        f"- Status: {status} "
        f"- From: {service}"
    )

def send_health_loop():
    while True:
        timestamp = get_timestamp()
        message = {
            "timestamp": timestamp,
            "from": "monitor"
        }

        celery.send_task(
            "reservas.process_health",
            args=[message],
            queue=REQUEST_QUEUE
        )

        print(f"Healthcheck enviado - {timestamp}")
        time.sleep(10)

if __name__ == "__main__":

    sender = threading.Thread(target=send_health_loop)
    sender.start()

    celery.worker_main([
        "worker",
        "--loglevel=info",
        "-Q",
        RESPONSE_QUEUE
    ])