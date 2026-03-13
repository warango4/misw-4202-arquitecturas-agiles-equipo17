"""
Módulo de utilidades comunes para el servicio verificador.
Centraliza funciones reutilizables para evitar duplicación de código.
"""
import logging
import pytz
from datetime import datetime

# Timezone para Colombia
BOGOTA_TZ = pytz.timezone("America/Bogota")


def get_bogota_time():
    """Retorna la hora actual en zona horaria de Bogotá formateada."""
    return datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d %H:%M:%S")


def setup_logger(name):
    """
    Configura y retorna un logger con formato estándar.

    Args:
        name: Nombre del logger

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger
