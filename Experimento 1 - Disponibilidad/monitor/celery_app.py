"""Configuración de Celery para el microservicio de monitoreo."""
from celery import Celery

from monitor.config import get_config

config = get_config()


def make_celery():
    """
    Crea y configura la instancia de Celery para el servicio de monitoreo.
    """
    celery = Celery(
        'monitor_tasks',
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
        include=['monitor.tareas.tareas']
    )
    
    # Configuración de Celery
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone=config.TIMEZONE,
        enable_utc=True,
        # Configuración para tareas periódicas con Celery Beat
        beat_schedule={
            'health-check-reservas': {
                'task': 'monitor.health_check_funcional',
                'schedule': config.HEALTH_CHECK_INTERVAL,
            },
        },
        task_track_started=True,
        task_time_limit=30,
        worker_prefetch_multiplier=1,
    )
    
    return celery


celery_app = make_celery()
