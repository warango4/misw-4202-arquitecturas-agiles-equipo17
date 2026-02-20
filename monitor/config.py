"""
Configuración del microservicio de monitoreo.
"""
import os


class DefaultConfig:
    """Configuración base del monitor."""
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'monitor-secret-key')
    
    # Redis / Celery
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
    
    # Flask
    FLASK_HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.environ.get('FLASK_PORT', 5003))
    
    # Health Check
    HEALTH_CHECK_INTERVAL = float(os.environ.get('HEALTH_CHECK_INTERVAL', 5))  # 200ms
    HEALTH_CHECK_TIMEOUT = int(os.environ.get('HEALTH_CHECK_TIMEOUT', 10))  # segundos
    HEALTH_CHECK_TTL = int(os.environ.get('HEALTH_CHECK_TTL', 15))  # segundos
    
    # Colas
    MONITOR_QUEUE = os.environ.get('MONITOR_QUEUE', 'healthcheck.response')
    RESERVAS_QUEUE = os.environ.get('RESERVAS_QUEUE', 'healthcheck.request')
    
    # URLs de servicios
    RESERVAS_SERVICE_URL = os.environ.get('RESERVAS_SERVICE_URL', 'http://localhost:5001')
    NOTIFICACIONES_URL = os.environ.get('NOTIFICACIONES_URL', 'http://localhost:5002')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', '/app/logs/monitor.log')
    
    # Timezone
    TIMEZONE = os.environ.get('TIMEZONE', 'America/Bogota')


class ProductionConfig(DefaultConfig):
    """Configuración de producción."""
    DEBUG = False
    LOG_LEVEL = 'WARNING'


class TestingConfig(DefaultConfig):
    """Configuración de testing."""
    TESTING = True
    HEALTH_CHECK_INTERVAL = 1.0  # Más lento para tests


# Mapeo de configuraciones
config_by_name = {
    'development': DefaultConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DefaultConfig
}


def get_config():
    """Obtiene la configuración según el entorno."""
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, config_by_name['default'])
