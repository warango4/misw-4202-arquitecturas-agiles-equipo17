import logging
import requests
import pytz
from datetime import datetime

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("proxy_service")


def forward_post_json(url, payload, headers=None):
    try:
        logger.info(f"[{get_bogota_time()}] [INFO] Reenviando request POST a: {url}")
        response = requests.post(url, json=payload, headers=headers or {}, timeout=15)
        logger.info(f"[{get_bogota_time()}] [INFO] Respuesta recibida de {url} con status {response.status_code}")
        return response
    except requests.exceptions.ConnectionError:
        logger.error(f"[{get_bogota_time()}] [ERROR] No se pudo conectar con el servicio en {url}")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"[{get_bogota_time()}] [ERROR] Timeout al conectar con {url}")
        return None


def forward_post_form(url, data):
    try:
        logger.info(f"[{get_bogota_time()}] [INFO] Reenviando request POST form-urlencoded a: {url}")
        response = requests.post(url, data=data, timeout=15)
        logger.info(f"[{get_bogota_time()}] [INFO] Respuesta recibida de {url} con status {response.status_code}")
        return response
    except requests.exceptions.ConnectionError:
        logger.error(f"[{get_bogota_time()}] [ERROR] No se pudo conectar con el servicio en {url}")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"[{get_bogota_time()}] [ERROR] Timeout al conectar con {url}")
        return None