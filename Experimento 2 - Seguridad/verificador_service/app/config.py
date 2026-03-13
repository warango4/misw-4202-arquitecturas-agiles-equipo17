import os


class Config:
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # Queue where reservas_service publishes checksum validation requests
    QUEUE_CHECKSUM_REQUEST = os.getenv("QUEUE_CHECKSUM_REQUEST", "reservas.checksum.request")

    # Queue where this service publishes validation results back to reservas_service
    QUEUE_CHECKSUM_RESPONSE = os.getenv("QUEUE_CHECKSUM_RESPONSE", "reservas.checksum.response")

    # Worker poll interval (seconds)
    WORKER_POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "0.5"))
