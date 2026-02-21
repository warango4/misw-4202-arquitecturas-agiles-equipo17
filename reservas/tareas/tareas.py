import logging
import os
import json
from datetime import datetime
import pytz
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

from reservas.config import get_config

config = get_config()

log_dir = os.path.dirname(config.LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)


# ============================================================================

class StructuredLogger:
    def __init__(self, service_name: str, log_file: str):
        self.service_name = service_name
        self.tz = pytz.timezone(config.TIMEZONE)
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(logging.INFO)

        # Evitar duplicación de handlers
        if not self.logger.handlers:
            formatter = logging.Formatter('%(message)s')

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def _get_timestamp(self) -> str:
        return datetime.now(self.tz).isoformat()

    def _format_log(self, level: str, event: str, check_id: str = None, **kwargs) -> str:
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": level,
            "service": self.service_name,
            "event": event,
        }
        if check_id:
            log_entry["check_id"] = check_id
        log_entry.update(kwargs)
        return json.dumps(log_entry, ensure_ascii=False)

    def info(self, event: str, check_id: str = None, **kwargs):
        self.logger.info(self._format_log("INFO", event, check_id, **kwargs))

    def warning(self, event: str, check_id: str = None, **kwargs):
        self.logger.warning(self._format_log("WARNING", event, check_id, **kwargs))

    def error(self, event: str, check_id: str = None, **kwargs):
        self.logger.error(self._format_log("ERROR", event, check_id, **kwargs))


structured_logger = StructuredLogger(config.SERVICE_NAME, config.LOG_FILE)


# ============================================================================

celery_app = Celery(
    'reservas_tasks',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=config.TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30,
    worker_prefetch_multiplier=1,
    task_queues={
        config.HEALTHCHECK_REQUEST_QUEUE: {
            'exchange': config.HEALTHCHECK_REQUEST_QUEUE,
            'routing_key': config.HEALTHCHECK_REQUEST_QUEUE,
        },
        config.SOLICITUDES_QUEUE: {
            'exchange': config.SOLICITUDES_QUEUE,
            'routing_key': config.SOLICITUDES_QUEUE,
        },
    },
    task_default_queue=config.HEALTHCHECK_REQUEST_QUEUE,
)


def _error_inducido() -> bool:
    redis_key = f'reservas:{config.SERVICE_NAME}:induce_error'
    try:
        import redis as redis_lib
        r = redis_lib.from_url(config.CELERY_BROKER_URL)
        flag = r.get(redis_key)
        if flag is not None:
            return flag.decode('utf-8') == 'true'
    except Exception:
        pass
    return config.INDUCE_ERROR


# ============================================================================

@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **kw):
    structured_logger.info(
        event="TASK_START",
        task_id=task_id,
        task_name=task.name
    )


@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, state, **kw):
    structured_logger.info(
        event="TASK_END",
        task_id=task_id,
        task_name=task.name,
        state=state
    )


@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **kw):
    structured_logger.error(
        event="TASK_FAILURE",
        task_id=task_id,
        exception=str(exception)
    )

# ============================================================================

@celery_app.task(name='reservas.health_check_funcional', bind=True, max_retries=0)
def health_check_funcional(self, request_data: dict):
    tz = pytz.timezone(config.TIMEZONE)
    response_timestamp = datetime.now(tz).isoformat()

    check_id = request_data.get('check_id', 'unknown')
    original_timestamp = request_data.get('original_timestamp')
    callback_queue = request_data.get('callback_queue', config.HEALTHCHECK_RESPONSE_QUEUE)

    structured_logger.info(
        event="HEALTH_CHECK_RECEIVED",
        check_id=check_id,
        original_timestamp=original_timestamp
    )

    available = True
    error_message = None

    if _error_inducido():
        available = False
        error_message = 'Error inducido para pruebas de failover'
        structured_logger.warning(
            event="HEALTH_CHECK_ERROR_INDUCIDO",
            check_id=check_id,
            error=error_message
        )

    # Enviar respuesta al monitor por la cola de respuesta
    celery_app.send_task(
        'monitor.recibir_health_check_funcional',
        args=[{
            'check_id': check_id,
            'available': available,
            'original_timestamp': original_timestamp,
            'response_timestamp': response_timestamp,
            'service': config.SERVICE_NAME,
            'error': error_message
        }],
        queue=callback_queue
    )

    structured_logger.info(
        event="HEALTH_CHECK_RESPONSE_SENT",
        check_id=check_id,
        available=available,
        target_queue=callback_queue
    )

    return {
        'check_id': check_id,
        'available': available,
        'response_timestamp': response_timestamp
    }


# ============================================================================

@celery_app.task(name='reservas.procesar_solicitud', bind=True, max_retries=0)
def procesar_solicitud(self, request_data: dict):
    """
    Procesa una solicitud de reserva enviada por el receptor.

    El receptor envía:
        {
            'solicitud_id': str,
            'datos': dict,
            'callback_queue': str   (opcional)
        }
    """
    tz = pytz.timezone(config.TIMEZONE)
    timestamp = datetime.now(tz).isoformat()

    solicitud_id = request_data.get('solicitud_id', 'unknown')
    datos = request_data.get('datos', {})
    callback_queue = request_data.get('callback_queue', config.RESPUESTAS_QUEUE)

    structured_logger.info(
        event="SOLICITUD_RECIBIDA",
        solicitud_id=solicitud_id
    )

    try:
        if _error_inducido():
            raise ValueError('Error inducido: datos incorrectos')

        if not datos:
            raise ValueError('Datos de la solicitud están vacíos')

        resultado = {
            'solicitud_id': solicitud_id,
            'status': 'procesada',
            'service': config.SERVICE_NAME,
            'timestamp': timestamp,
            'datos_procesados': datos
        }

        structured_logger.info(
            event="SOLICITUD_PROCESADA",
            solicitud_id=solicitud_id
        )

    except Exception as e:
        resultado = {
            'solicitud_id': solicitud_id,
            'status': 'error',
            'service': config.SERVICE_NAME,
            'timestamp': timestamp,
            'error': str(e)
        }
        structured_logger.error(
            event="SOLICITUD_ERROR",
            solicitud_id=solicitud_id,
            error=str(e)
        )

    # Enviar resultado al receptor si hay cola de respuesta
    if callback_queue:
        celery_app.send_task(
            'receptor.recibir_respuesta',
            args=[resultado],
            queue=callback_queue
        )

    return resultado
