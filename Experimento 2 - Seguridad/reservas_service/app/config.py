import os


class Config:
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://travelhub:travelhub@db:5432/travelhub")
    
    # Queue where receptor_service publishes reservation requests
    QUEUE_RESERVAS_REQUEST = os.getenv("QUEUE_RESERVAS_REQUEST", "reservas.request")
    
    # Queue where this service publishes final response to receptor_service
    QUEUE_RESERVAS_RESPONSE = os.getenv("QUEUE_RESERVAS_RESPONSE", "reservas.response")
    
    # Queue where this service publishes validated requests for checksum validation
    QUEUE_CHECKSUM_REQUEST = os.getenv("QUEUE_CHECKSUM_REQUEST", "reservas.checksum.request")
    
    # Queue where checksum validator publishes validation results
    QUEUE_CHECKSUM_RESPONSE = os.getenv("QUEUE_CHECKSUM_RESPONSE", "reservas.checksum.response")
    
    # Timeout for waiting checksum response (seconds)
    CHECKSUM_RESPONSE_TIMEOUT = int(os.getenv("CHECKSUM_RESPONSE_TIMEOUT", "10"))
    
    # Worker poll interval (seconds)
    WORKER_POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "0.5"))
