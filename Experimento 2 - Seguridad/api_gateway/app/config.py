import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:5001")
    RECEPTOR_SERVICE_URL = os.getenv("RECEPTOR_SERVICE_URL", "http://receptor_service:5002")
    HISTORICO_SERVICE_URL = os.getenv("HISTORICO_SERVICE_URL", "http://historico_service:5003")

    PERMISSION_RESERVA = "reserva"
    PERMISSION_HISTORICO = "historico"