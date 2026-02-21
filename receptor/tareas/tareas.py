"""
Tareas Celery del Receptor
Recibe respuestas de las instancias de reservas (principal y redundancia)
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any
import redis
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from receptor.config import get_config
import pytz

# Configuración
config = get_config()

# Asegurar que el directorio de logs exista
log_dir = os.path.dirname(config.LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)


# ============================================================================
# LOGGER ESTRUCTURADO PARA OBSERVABILIDAD
# ============================================================================
class StructuredLogger:
    """Logger estructurado con trazas claras para observabilidad."""
    
    def __init__(self, service_name: str, log_file: str):
        self.service_name = service_name
        self.tz = pytz.timezone(config.TIMEZONE)
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(logging.INFO)
        
        # Evitar duplicación de handlers
        if not self.logger.handlers:
            formatter = logging.Formatter('%(message)s')
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def _get_timestamp(self) -> str:
        return datetime.now(self.tz).isoformat()
    
    def _format_log(self, level: str, event: str, **kwargs) -> str:
        """Genera log estructurado en JSON."""
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": level,
            "service": self.service_name,
            "event": event,
        }
        log_entry.update(kwargs)
        return json.dumps(log_entry, ensure_ascii=False)
    
    def info(self, event: str, **kwargs):
        self.logger.info(self._format_log("INFO", event, **kwargs))
    
    def warning(self, event: str, **kwargs):
        self.logger.warning(self._format_log("WARNING", event, **kwargs))
    
    def error(self, event: str, **kwargs):
        self.logger.error(self._format_log("ERROR", event, **kwargs))
    
    def debug(self, event: str, **kwargs):
        self.logger.debug(self._format_log("DEBUG", event, **kwargs))


# Inicializar logger estructurado
structured_logger = StructuredLogger(config.SERVICE_NAME, config.LOG_FILE)

# Cliente Redis para almacenar respuestas
redis_client = redis.Redis.from_url(config.CELERY_BROKER_URL)

# Configuración de Celery
celery_app = Celery('receptor')
celery_app.conf.update(
    broker_url=config.CELERY_BROKER_URL,
    result_backend=config.CELERY_RESULT_BACKEND,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone=config.TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_default_queue='receptor.respuestas',
    task_routes={
        'receptor.recibir_respuesta': {'queue': 'receptor.respuestas'},
    },
)


# ============================================================================
# SIGNALS PARA TRAZABILIDAD
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


@celery_app.task(name='receptor.recibir_respuesta', bind=True)
def recibir_respuesta(self, resultado: Dict[str, Any]):
    """
    Recibe respuestas de las instancias de reservas.
    Esta tarea es llamada por los workers de reservas cuando terminan de procesar.
    
    Args:
        resultado: Dict con la respuesta de la instancia de reservas
            {
                'solicitud_id': str,
                'status': str ('procesada' o 'error'),
                'service': str (nombre de la instancia que respondió),
                'timestamp': str,
                'datos_procesados': dict (opcional),
                'error': str (opcional)
            }
    """
    solicitud_id = resultado.get('solicitud_id')
    status = resultado.get('status')
    service = resultado.get('service')
    error = resultado.get('error')
    
    structured_logger.info(
        event='RESPUESTA_RECIBIDA',
        solicitud_id=solicitud_id,
        status=status,
        service=service,
        task_id=self.request.id,
        has_error=error is not None
    )
    
    try:
        # Guardar la respuesta en Redis con TTL de 1 hora
        key = f'receptor:respuesta:{solicitud_id}'
        redis_client.setex(
            key,
            3600,  # TTL: 1 hora
            json.dumps(resultado)
        )
        
        # Actualizar contador de respuestas
        counter_key = f'receptor:metricas:respuestas_{status}'
        redis_client.incr(counter_key)
        
        if status == 'procesada':
            structured_logger.info(
                event='RESPUESTA_PROCESADA',
                solicitud_id=solicitud_id,
                service=service
            )
        else:
            structured_logger.warning(
                event='RESPUESTA_CON_ERROR',
                solicitud_id=solicitud_id,
                service=service,
                error=error
            )
            
    except Exception as e:
        structured_logger.error(
            event='ERROR_GUARDANDO_RESPUESTA',
            solicitud_id=solicitud_id,
            error=str(e)
        )
        raise


@celery_app.task(name='receptor.verificar_timeout', bind=True)
def verificar_timeout(self, solicitud_id: str, timestamp_envio: str):
    """
    Verifica si una solicitud ha excedido el timeout sin recibir respuesta.
    Se programa cuando se envía una solicitud a reservas.
    
    Args:
        solicitud_id: ID único de la solicitud
        timestamp_envio: Timestamp cuando se envió la solicitud
    """
    key = f'receptor:respuesta:{solicitud_id}'
    respuesta = redis_client.get(key)
    
    if respuesta is None:
        # No se recibió respuesta, marcar como timeout
        structured_logger.error(
            event='SOLICITUD_TIMEOUT',
            solicitud_id=solicitud_id,
            timestamp_envio=timestamp_envio,
            timeout_seconds=config.SOLICITUD_TIMEOUT
        )
        
        # Guardar información del timeout
        timeout_info = {
            'solicitud_id': solicitud_id,
            'status': 'timeout',
            'error': f'No se recibió respuesta en {config.SOLICITUD_TIMEOUT} segundos',
            'timestamp_envio': timestamp_envio,
            'timestamp_timeout': datetime.now(pytz.timezone(config.TIMEZONE)).isoformat()
        }
        
        redis_client.setex(
            key,
            3600,
            json.dumps(timeout_info)
        )
        
        # Incrementar contador de timeouts
        redis_client.incr('receptor:metricas:respuestas_timeout')


def get_respuesta(solicitud_id: str) -> Dict[str, Any] | None:
    """
    Obtiene la respuesta de una solicitud desde Redis.
    
    Args:
        solicitud_id: ID de la solicitud
        
    Returns:
        Dict con la respuesta o None si no existe
    """
    key = f'receptor:respuesta:{solicitud_id}'
    respuesta_json = redis_client.get(key)
    
    if respuesta_json:
        return json.loads(respuesta_json)
    return None


def get_metricas() -> Dict[str, Any]:
    """
    Obtiene métricas acumuladas del receptor.
    
    Returns:
        Dict con las métricas
    """
    return {
        'respuestas_procesadas': int(redis_client.get('receptor:metricas:respuestas_procesada') or 0),
        'respuestas_error': int(redis_client.get('receptor:metricas:respuestas_error') or 0),
        'respuestas_timeout': int(redis_client.get('receptor:metricas:respuestas_timeout') or 0),
    }
