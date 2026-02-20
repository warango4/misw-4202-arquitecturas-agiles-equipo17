"""
Módulo de tareas Celery para el servicio de monitoreo.
Implementa health check funcional por cola para verificar disponibilidad del servicio de reservas.
"""
import logging
import uuid
import os
import json
import time
from datetime import datetime
import pytz
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

# Importar configuración
from monitor.config import get_config

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
    
    def _format_log(self, level: str, event: str, check_id: str = None, **kwargs) -> str:
        """Genera log estructurado en JSON."""
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
    
    def state_change(self, check_id: str, previous_state: str, current_state: str, **kwargs):
        """Log especial para cambios de estado."""
        self.logger.warning(self._format_log(
            "STATE_CHANGE", 
            "SERVICE_STATE_CHANGED", 
            check_id,
            previous_state=previous_state,
            current_state=current_state,
            **kwargs
        ))


# Inicializar logger estructurado
structured_logger = StructuredLogger('monitor', config.LOG_FILE)

# Logger básico para compatibilidad
logger = logging.getLogger('monitor_health_check')

# Función helper para obtener timestamp con timezone
def get_timestamp():
    """Retorna el timestamp actual con la zona horaria configurada."""
    tz = pytz.timezone(config.TIMEZONE)
    return datetime.now(tz).strftime("%Y/%b/%d %H:%M:%S")

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
# HEALTH CHECK FUNCIONAL (POR COLA)
# ============================================================================

@celery_app.task(name='monitor.health_check_funcional', bind=True, max_retries=0)
def health_check_funcional(self):
    """
    Envía health check funcional al servicio de reservas por cola.
    Verifica que el worker de reservas esté funcionando.
    """
    start_time = time.time()
    timestamp = get_timestamp()
    check_id = str(uuid.uuid4())
    
    # 🔹 LOG: Inicio del health check con ID único
    structured_logger.info(
        event="HEALTH_CHECK_START",
        check_id=check_id,
        method="QUEUE",
        target_service="reservas",
        sent_at=timestamp
    )
    
    state_manager.increment_metric('total_health_checks')
    state_manager.set_metric('last_health_check_timestamp', timestamp)
    
    # Guardar check_id con TTL para control de timeout
    if state_manager.redis_client:
        try:
            # Guardar timestamp de inicio para calcular latencia
            state_manager.redis_client.setex(
                f'health_check:{check_id}', 
                config.HEALTH_CHECK_TTL, 
                json.dumps({"timestamp": timestamp, "start_time": start_time})
            )
        except Exception as e:
            structured_logger.error(event="REDIS_ERROR", check_id=check_id, error=str(e))
    
    # Enviar tarea al servicio de reservas
    try:
        celery_app.send_task(
            'reservas.health_check_funcional',
            args=[{
                'check_id': check_id,
                'original_timestamp': timestamp,
                'callback_task': 'monitor.recibir_health_check_funcional',
                'callback_queue': config.MONITOR_QUEUE,
                'source': 'monitor'
            }],
            queue=config.RESERVAS_QUEUE
        )
        
        # 🔹 LOG: Health check enviado exitosamente
        structured_logger.info(
            event="HEALTH_CHECK_SENT",
            check_id=check_id,
            target_queue=config.RESERVAS_QUEUE,
            status="SENT"
        )
    except Exception as e:
        structured_logger.error(
            event="HEALTH_CHECK_SEND_ERROR",
            check_id=check_id,
            error=str(e)
        )
        procesar_respuesta.delay(False, timestamp, f"Error enviando: {str(e)}")
    
    # Programar verificación de timeout
    verificar_timeout.apply_async(args=[check_id, timestamp], countdown=config.HEALTH_CHECK_TIMEOUT)
    
    return {'check_id': check_id, 'timestamp': timestamp}


@celery_app.task(name='monitor.recibir_health_check_funcional', bind=True)
def recibir_health_check_funcional(self, response_data: dict):
    """Recibe la respuesta del health check funcional."""
    received_at = time.time()
    timestamp = get_timestamp()
    check_id = response_data.get('check_id', 'unknown')
    is_available = response_data.get('available', False)
    original_timestamp = response_data.get('original_timestamp', 'N/A')
    response_timestamp = response_data.get('response_timestamp', 'N/A')
    service = response_data.get('service', 'unknown')
    error = response_data.get('error')
    
    # 🔹 Calcular latencia round-trip desde Redis
    latency_ms = None
    if state_manager.redis_client:
        try:
            check_data = state_manager.redis_client.get(f'health_check:{check_id}')
            if check_data:
                data = json.loads(check_data)
                start_time = data.get('start_time')
                if start_time:
                    latency_ms = (received_at - float(start_time)) * 1000
                state_manager.redis_client.delete(f'health_check:{check_id}')
            else:
                # Check expirado
                structured_logger.warning(
                    event="HEALTH_CHECK_EXPIRED",
                    check_id=check_id,
                    reason="Check ID not found in Redis (TTL expired or already processed)"
                )
                return {'status': 'expired'}
        except Exception as e:
            structured_logger.error(event="REDIS_ERROR", check_id=check_id, error=str(e))
    
    # 🔹 LOG: Respuesta recibida con métricas de tiempo
    structured_logger.info(
        event="HEALTH_CHECK_RESPONSE_RECEIVED",
        check_id=check_id,
        source_service=service,
        available=is_available,
        original_timestamp=original_timestamp,
        response_timestamp=response_timestamp,
        received_at=timestamp,
        latency_ms=round(latency_ms, 3) if latency_ms else None,
        status="SUCCESS" if is_available else "FAILED"
    )
    
    procesar_respuesta.delay(is_available, timestamp, error)
    
    return {'check_id': check_id, 'available': is_available, 'latency_ms': latency_ms}


@celery_app.task(name='monitor.verificar_timeout', bind=True)
def verificar_timeout(self, check_id: str, original_timestamp: str):
    """Verifica si el health check excedió el timeout."""
    timestamp = get_timestamp()
    
    if state_manager.redis_client:
        try:
            check_data = state_manager.redis_client.get(f'health_check:{check_id}')
            if check_data:
                state_manager.redis_client.delete(f'health_check:{check_id}')
                
                # 🔹 LOG: Timeout detectado
                structured_logger.error(
                    event="HEALTH_CHECK_TIMEOUT",
                    check_id=check_id,
                    original_timestamp=original_timestamp,
                    timeout_detected_at=timestamp,
                    timeout_seconds=config.HEALTH_CHECK_TIMEOUT,
                    status="TIMEOUT"
                )
                procesar_respuesta.delay(False, timestamp, "TIMEOUT: Sin respuesta en tiempo límite")
        except Exception as e:
            structured_logger.error(event="REDIS_ERROR", check_id=check_id, error=str(e))
    
    return {'check_id': check_id, 'status': 'timeout_verified'}


@celery_app.task(name='monitor.procesar_respuesta', bind=True)
def procesar_respuesta(self, is_available: bool, timestamp: str, error_message: str = None):
    """Procesa la respuesta y notifica cambios de estado."""
    previous_state = state_manager.get_state()
    current_state = is_available
    
    # 🔹 LOG: Procesamiento de respuesta
    structured_logger.info(
        event="PROCESS_RESPONSE",
        previous_state="AVAILABLE" if previous_state else "UNAVAILABLE",
        current_state="AVAILABLE" if current_state else "UNAVAILABLE",
        state_changed=previous_state != current_state
    )
    
    if is_available:
        state_manager.increment_metric('successful_health_checks')
        if not previous_state:
            # 🔹 LOG: Cambio de estado - Servicio RECUPERADO
            structured_logger.state_change(
                check_id=None,
                previous_state="UNAVAILABLE",
                current_state="AVAILABLE",
                event_type="SERVICE_RECOVERED",
                recovered_at=timestamp,
                message="El servicio de reservas se ha recuperado"
            )
            state_manager.set_metric('last_recovery_timestamp', timestamp)
            state_manager.set_state(True)
    else:
        state_manager.increment_metric('failed_health_checks')
        if previous_state:
            # 🔹 LOG: Cambio de estado - Servicio CAÍDO
            structured_logger.state_change(
                check_id=None,
                previous_state="AVAILABLE",
                current_state="UNAVAILABLE",
                event_type="SERVICE_DOWN",
                down_at=timestamp,
                error=error_message,
                message="El servicio de reservas no está disponible"
            )
            state_manager.set_metric('last_downtime_start', timestamp)
            state_manager.set_state(False)
    
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
