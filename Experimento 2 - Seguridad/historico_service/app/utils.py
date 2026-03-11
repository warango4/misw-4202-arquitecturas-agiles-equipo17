"""
Módulo de utilidades comunes para el servicio de histórico.
Centraliza funciones reutilizables para evitar duplicación de código.
"""
import logging
import pytz
from datetime import datetime
from flask import request

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


def get_client_ip():
    """
    Obtiene la IP original del cliente desde los headers.
    
    Prioridad:
    1. X-Original-Client-IP (establecido por API Gateway)
    2. X-Forwarded-For (primer IP)
    3. X-Real-IP
    4. request.remote_addr
    
    Returns:
        IP del cliente como string
    """
    if request.headers.get("X-Original-Client-IP"):
        return request.headers.get("X-Original-Client-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    return request.remote_addr


def extract_token(auth_header):
    """
    Extrae el token Bearer del header de Authorization.
    
    Args:
        auth_header: Valor del header Authorization
    
    Returns:
        Token string o None si no es válido
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ")[1]
