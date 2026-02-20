import os
from typing import Optional


class Config:
    """Configuración base para el receptor"""
    
    # Información del servicio
    SERVICE_NAME: str = os.getenv('SERVICE_NAME', 'receptor')
    TIMEZONE: str = os.getenv('TIMEZONE', 'America/Bogota')
    
    # Flask
    FLASK_HOST: str = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT: int = int(os.getenv('FLASK_PORT', '5000'))
    
    # Celery / Redis
    CELERY_BROKER_URL: str = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND: str = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # URLs de servicios
    MONITOR_URL: str = os.getenv('MONITOR_URL', 'http://localhost:5003')
    
    # Colas de solicitudes (envío a reservas)
    RESERVAS_PRINCIPAL_QUEUE: str = os.getenv('RESERVAS_PRINCIPAL_QUEUE', 'reservas.principal.solicitudes')
    RESERVAS_REDUNDANCIA_QUEUE: str = os.getenv('RESERVAS_REDUNDANCIA_QUEUE', 'reservas.redundancia.solicitudes')
    
    # Colas de respuestas (recepción desde reservas)
    RESPUESTAS_PRINCIPAL_QUEUE: str = os.getenv('RESPUESTAS_PRINCIPAL_QUEUE', 'reservas.principal.respuestas')
    RESPUESTAS_REDUNDANCIA_QUEUE: str = os.getenv('RESPUESTAS_REDUNDANCIA_QUEUE', 'reservas.redundancia.respuestas')
    
    # Timeout y reintentos (reducido porque ahora es más rápido)
    SOLICITUD_TIMEOUT: int = int(os.getenv('SOLICITUD_TIMEOUT', '5'))  # segundos
    MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))
    
    # Cache del estado del monitor (muy corto para failover rápido)
    CACHE_ESTADO_TTL: int = int(os.getenv('CACHE_ESTADO_TTL', '1'))  # segundos
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.getenv('LOG_FILE', '/app/logs/receptor.log')


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False


class TestingConfig(Config):
    """Configuración para pruebas"""
    TESTING = True


# Mapeo de entornos
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(environment: Optional[str] = None) -> Config:
    """Obtiene la configuración según el entorno"""
    if environment is None:
        environment = os.getenv('FLASK_ENV', 'default')
    return config_by_name.get(environment, DevelopmentConfig)
