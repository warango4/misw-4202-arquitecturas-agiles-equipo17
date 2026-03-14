import os


class Config:
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
    QUEUE_REQUEST = "reservas.request"
    QUEUE_RESPONSE = "reservas.response"
    REDIS_AUDITORIA_TTL = int(os.getenv("REDIS_AUDITORIA_TTL", "3600"))