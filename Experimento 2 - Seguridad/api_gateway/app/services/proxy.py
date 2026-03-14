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


def forward_post_json_with_headers(url, payload, headers):
    """
    Forward a POST request with specific headers.
    Used for forwarding authorization and IP context to downstream services.
    """
    try:
        logger.info(f"[{get_bogota_time()}] [INFO] Reenviando request POST con headers a: {url}")
        logger.debug(f"[{get_bogota_time()}] [DEBUG] Headers enviados: X-Original-Client-IP={headers.get('X-Original-Client-IP')}")
        response = requests.post(url, json=payload, headers=headers, timeout=15)
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


def forward_post_form_with_ip(url, data, client_ip):
    """
    Forward a POST form request including the client IP.
    Used for token generation to include IP context.
    """
    try:
        logger.info(f"[{get_bogota_time()}] [INFO] Reenviando request POST form-urlencoded a: {url}")
        logger.info(f"[{get_bogota_time()}] [INFO] Incluyendo IP del cliente: {client_ip}")
        
        # Add client_ip to form data
        data_with_ip = dict(data)
        data_with_ip["client_ip"] = client_ip
        
        response = requests.post(url, data=data_with_ip, timeout=15)
        logger.info(f"[{get_bogota_time()}] [INFO] Respuesta recibida de {url} con status {response.status_code}")
        return response
    except requests.exceptions.ConnectionError:
        logger.error(f"[{get_bogota_time()}] [ERROR] No se pudo conectar con el servicio en {url}")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"[{get_bogota_time()}] [ERROR] Timeout al conectar con {url}")
        return None