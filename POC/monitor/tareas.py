"""
Módulo de tareas Celery para el servicio de monitoreo.
Implementa health check funcional por cola para verificar disponibilidad del servicio de reservas.
"""
import logging
import uuid
from datetime import datetime
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

# Importar configuración
from monitor.config import get_config

config = get_config()

# Configuración del logger para métricas y trazabilidad
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('monitor_health_check')

# Crear instancia de Celery usando configuración
celery_app = Celery(
    'monitor_tasks',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

# Configuración de Celery incluyendo el beat_schedule
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=config.TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_queues={
        config.MONITOR_QUEUE: {
            'exchange': config.MONITOR_QUEUE,
            'routing_key': config.MONITOR_QUEUE,
        }
    },
    task_default_queue=config.MONITOR_QUEUE,
    beat_schedule={
        'health-check-funcional-reservas': {
            'task': 'monitor.health_check_funcional',
            'schedule': config.HEALTH_CHECK_INTERVAL,
        },
    },
)


class ServiceStateManager:
    """Gestiona el estado y métricas del servicio monitoreado usando Redis."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.redis_client = None
        try:
            import redis
            self.redis_client = redis.from_url(config.CELERY_BROKER_URL)
        except Exception as e:
            logger.error(f"[METRIC] Error conectando a Redis: {e}")
    
    def get_state(self):
        """Obtiene el estado actual del servicio de reservas."""
        if self.redis_client:
            try:
                state = self.redis_client.get('reservas_service_available')
                return state.decode('utf-8') == 'true' if state else True
            except:
                return True
        return True
    
    def set_state(self, available: bool):
        """Establece el estado del servicio de reservas."""
        if self.redis_client:
            try:
                self.redis_client.set('reservas_service_available', 'true' if available else 'false')
            except Exception as e:
                logger.error(f"[METRIC] Error guardando estado: {e}")
    
    def get_metrics(self):
        """Obtiene las métricas acumuladas."""
        if self.redis_client:
            try:
                return {
                    'total_checks': int(self.redis_client.get('total_health_checks') or 0),
                    'successful_checks': int(self.redis_client.get('successful_health_checks') or 0),
                    'failed_checks': int(self.redis_client.get('failed_health_checks') or 0),
                    'last_check_timestamp': self.redis_client.get('last_health_check_timestamp'),
                    'last_downtime_start': self.redis_client.get('last_downtime_start'),
                    'last_recovery_timestamp': self.redis_client.get('last_recovery_timestamp'),
                }
            except:
                pass
        return {}
    
    def increment_metric(self, metric_name: str, value: int = 1):
        """Incrementa una métrica."""
        if self.redis_client:
            try:
                self.redis_client.incrby(metric_name, value)
            except Exception as e:
                logger.error(f"[METRIC] Error incrementando métrica: {e}")
    
    def set_metric(self, metric_name: str, value: str):
        """Establece el valor de una métrica."""
        if self.redis_client:
            try:
                self.redis_client.set(metric_name, value)
            except Exception as e:
                logger.error(f"[METRIC] Error estableciendo métrica: {e}")


state_manager = ServiceStateManager()


# Signals para trazabilidad
@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **kw):
    logger.info(f"[METRIC] TASK_START | task_id={task_id} | task_name={task.name}")


@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, state, **kw):
    logger.info(f"[METRIC] TASK_END | task_id={task_id} | task_name={task.name} | state={state}")


@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **kw):
    logger.error(f"[METRIC] TASK_FAILURE | task_id={task_id} | exception={str(exception)}")


# ============================================================================
# HEALTH CHECK FUNCIONAL (POR COLA)
# ============================================================================

@celery_app.task(name='monitor.health_check_funcional', bind=True, max_retries=0)
def health_check_funcional(self):
    """
    Envía health check funcional al servicio de reservas por cola.
    Verifica que el worker de reservas esté funcionando.
    """
    timestamp = datetime.utcnow().isoformat()
    check_id = str(uuid.uuid4())
    
    logger.info(
        f"[METRIC] HEALTH_CHECK_START | "
        f"timestamp={timestamp} | "
        f"check_id={check_id} | "
        f"method=QUEUE"
    )
    
    state_manager.increment_metric('total_health_checks')
    state_manager.set_metric('last_health_check_timestamp', timestamp)
    
    # Guardar check_id con TTL para control de timeout
    if state_manager.redis_client:
        try:
            state_manager.redis_client.setex(f'health_check:{check_id}', config.HEALTH_CHECK_TTL, timestamp)
        except Exception as e:
            logger.error(f"[METRIC] Error guardando check_id: {e}")
    
    # Enviar tarea al servicio de reservas
    try:
        celery_app.send_task(
            'reservas.health_check_funcional',
            args=[{
                'check_id': check_id,
                'timestamp': timestamp,
                'callback_task': 'monitor.recibir_health_check_funcional',
                'callback_queue': config.MONITOR_QUEUE,
                'source': 'monitor'
            }],
            queue=config.RESERVAS_QUEUE
        )
        logger.info(f"[METRIC] HEALTH_CHECK_SENT | check_id={check_id}")
    except Exception as e:
        logger.error(f"[METRIC] HEALTH_CHECK_SEND_ERROR | check_id={check_id} | error={str(e)}")
        procesar_respuesta.delay(False, timestamp, f"Error enviando: {str(e)}")
    
    # Programar verificación de timeout
    verificar_timeout.apply_async(args=[check_id, timestamp], countdown=config.HEALTH_CHECK_TIMEOUT)
    
    return {'check_id': check_id, 'timestamp': timestamp}


@celery_app.task(name='monitor.recibir_health_check_funcional', bind=True)
def recibir_health_check_funcional(self, response_data: dict):
    """Recibe la respuesta del health check funcional."""
    timestamp = datetime.utcnow().isoformat()
    check_id = response_data.get('check_id', 'unknown')
    is_available = response_data.get('available', False)
    original_timestamp = response_data.get('original_timestamp', timestamp)
    error = response_data.get('error')
    
    # Calcular latencia
    try:
        from dateutil import parser
        latency_ms = (parser.isoparse(timestamp) - parser.isoparse(original_timestamp)).total_seconds() * 1000
    except:
        latency_ms = None
    
    # Verificar si el check aún es válido
    if state_manager.redis_client:
        try:
            if not state_manager.redis_client.get(f'health_check:{check_id}'):
                logger.warning(f"[METRIC] HEALTH_CHECK_EXPIRED | check_id={check_id}")
                return {'status': 'expired'}
            state_manager.redis_client.delete(f'health_check:{check_id}')
        except:
            pass
    
    logger.info(
        f"[METRIC] HEALTH_CHECK_RESPONSE_RECEIVED | "
        f"check_id={check_id} | "
        f"available={is_available} | "
        f"latency_ms={f'{latency_ms:.2f}' if latency_ms else 'N/A'}"
    )
    
    procesar_respuesta.delay(is_available, timestamp, error)
    
    return {'check_id': check_id, 'available': is_available, 'latency_ms': latency_ms}


@celery_app.task(name='monitor.verificar_timeout', bind=True)
def verificar_timeout(self, check_id: str, original_timestamp: str):
    """Verifica si el health check excedió el timeout."""
    timestamp = datetime.utcnow().isoformat()
    
    if state_manager.redis_client:
        try:
            if state_manager.redis_client.get(f'health_check:{check_id}'):
                state_manager.redis_client.delete(f'health_check:{check_id}')
                logger.error(f"[METRIC] HEALTH_CHECK_TIMEOUT | check_id={check_id}")
                procesar_respuesta.delay(False, timestamp, "TIMEOUT: Sin respuesta en 5 segundos")
        except:
            pass
    
    return {'check_id': check_id, 'status': 'timeout_verified'}


@celery_app.task(name='monitor.procesar_respuesta', bind=True)
def procesar_respuesta(self, is_available: bool, timestamp: str, error_message: str = None):
    """Procesa la respuesta y notifica cambios de estado."""
    previous_state = state_manager.get_state()
    
    logger.info(
        f"[METRIC] PROCESS_RESPONSE | "
        f"previous={previous_state} | "
        f"current={is_available}"
    )
    
    if is_available:
        state_manager.increment_metric('successful_health_checks')
        if not previous_state:
            # Servicio recuperado
            logger.info(f"[METRIC] SERVICE_RECOVERED | timestamp={timestamp}")
            state_manager.set_metric('last_recovery_timestamp', timestamp)
            state_manager.set_state(True)
            notificar_cambio_estado.delay('SERVICE_RECOVERED', timestamp)
    else:
        state_manager.increment_metric('failed_health_checks')
        if previous_state:
            # Servicio caído
            logger.warning(f"[METRIC] SERVICE_DOWN | timestamp={timestamp} | error={error_message}")
            state_manager.set_metric('last_downtime_start', timestamp)
            state_manager.set_state(False)
            notificar_cambio_estado.delay('SERVICE_DOWN', timestamp, error_message)
    
    return {'previous': previous_state, 'current': is_available}


@celery_app.task(name='monitor.notificar_cambio_estado', bind=True, max_retries=3)
def notificar_cambio_estado(self, event: str, timestamp: str, error_message: str = None):
    """Envía notificación a la API externa sobre cambio de estado."""
    import requests
    
    notification_url = os.environ.get('NOTIFICATION_API_URL', 'http://localhost:5002/notify')
    
    payload = {
        'event': event,
        'service': 'reservas',
        'timestamp': timestamp,
        'message': 'Servicio no disponible' if event == 'SERVICE_DOWN' else 'Servicio recuperado',
        'error': error_message,
        'severity': 'CRITICAL' if event == 'SERVICE_DOWN' else 'INFO'
    }
    
    logger.info(f"[METRIC] NOTIFICATION_SEND | event={event}")
    
    try:
        response = requests.post(notification_url, json=payload, timeout=10)
        logger.info(f"[METRIC] NOTIFICATION_SENT | event={event} | status={response.status_code}")
    except Exception as e:
        logger.error(f"[METRIC] NOTIFICATION_ERROR | event={event} | error={str(e)}")
        raise self.retry(exc=e, countdown=5)
    
    return {'event': event, 'status': 'notified'}
