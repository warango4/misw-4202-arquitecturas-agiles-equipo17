import os


class DefaultConfig:
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'reservas-secret-key')

    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

    FLASK_HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.environ.get('FLASK_PORT', 5001))

    # Identificador de instancia (reservas-principal o reservas-redundancia)
    SERVICE_NAME = os.environ.get('SERVICE_NAME', 'reservas-principal')

    # Colas
    HEALTHCHECK_REQUEST_QUEUE = os.environ.get('HEALTHCHECK_REQUEST_QUEUE', 'healthcheck.request')
    HEALTHCHECK_RESPONSE_QUEUE = os.environ.get('HEALTHCHECK_RESPONSE_QUEUE', 'healthcheck.response')
    SOLICITUDES_QUEUE = os.environ.get('SOLICITUDES_QUEUE', 'reservas.solicitudes')
    RESPUESTAS_QUEUE = os.environ.get('RESPUESTAS_QUEUE', 'reservas.respuestas')

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', '/app/logs/reservas.log')
    TIMEZONE = os.environ.get('TIMEZONE', 'America/Bogota')

    # Error inducido al arrancar (se puede sobreescribir en tiempo de ejecución via Redis)
    INDUCE_ERROR = os.environ.get('INDUCE_ERROR', 'false').lower() == 'true'


class TestingConfig(DefaultConfig):
    """Configuración de testing."""
    TESTING = True


config_by_name = {
    'development': DefaultConfig,
    'testing': TestingConfig,
    'default': DefaultConfig
}


def get_config():
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, config_by_name['default'])
