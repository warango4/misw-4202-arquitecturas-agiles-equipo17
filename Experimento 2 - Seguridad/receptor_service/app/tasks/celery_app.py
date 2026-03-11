from celery import Celery


def create_celery_app(broker_url: str, result_backend: str) -> Celery:
    celery = Celery(
        "receptor_service",
        broker=broker_url,
        backend=result_backend
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="America/Bogota",
        enable_utc=False
    )
    return celery