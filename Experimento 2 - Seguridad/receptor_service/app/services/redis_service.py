import json
import logging
import pytz
import redis
from datetime import datetime

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("redis_service")


def get_redis_client(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url, decode_responses=True)


def store_auditoria(client: redis.Redis, checksum: str, auditoria: dict, ttl: int):
    key = f"auditoria:{checksum}"
    try:
        client.setex(key, ttl, json.dumps(auditoria))
        logger.info(f"[{get_bogota_time()}] [INFO] Auditoría almacenada en Redis con key: {key}")
    except redis.RedisError as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al guardar en Redis: {str(e)}")
        raise


def enqueue_request(client: redis.Redis, queue_name: str, payload: dict):
    try:
        client.rpush(queue_name, json.dumps(payload))
        logger.info(f"[{get_bogota_time()}] [INFO] Payload encolado en '{queue_name}'")
    except redis.RedisError as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al encolar en Redis queue '{queue_name}': {str(e)}")
        raise


def dequeue_response(client: redis.Redis, queue_name: str, timeout: int = 5):
    try:
        result = client.blpop(queue_name, timeout=timeout)
        if result:
            _, value = result
            logger.info(f"[{get_bogota_time()}] [INFO] Respuesta recibida de cola '{queue_name}'")
            return json.loads(value)
        logger.warning(f"[{get_bogota_time()}] [WARN] Timeout esperando respuesta de '{queue_name}'")
        return None
    except redis.RedisError as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al leer de Redis queue '{queue_name}': {str(e)}")
        raise