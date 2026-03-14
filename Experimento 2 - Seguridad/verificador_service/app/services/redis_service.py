"""
Servicio de Redis para operaciones de cola.
Maneja la comunicación con las colas de mensajería.
"""
import json
import redis
from app.utils import get_bogota_time, setup_logger

logger = setup_logger("redis_service")


def get_redis_client(redis_url: str) -> redis.Redis:
    """Crea y retorna un cliente Redis."""
    return redis.Redis.from_url(redis_url, decode_responses=True)


def dequeue_message(client: redis.Redis, queue_name: str, timeout: int = 1):
    """
    Lee un mensaje de la cola (blocking pop).
    """
    try:
        result = client.blpop(queue_name, timeout=timeout)
        if result:
            _, value = result
            message = json.loads(value)
            logger.info(
                f"[{get_bogota_time()}] [INFO] Mensaje recibido de cola '{queue_name}'"
            )
            return message
        return None
    except redis.RedisError as e:
        logger.error(
            f"[{get_bogota_time()}] [ERROR] Error al leer de cola '{queue_name}': {str(e)}"
        )
        raise
    except json.JSONDecodeError as e:
        logger.error(
            f"[{get_bogota_time()}] [ERROR] Error al parsear mensaje de '{queue_name}': {str(e)}"
        )
        return None


def enqueue_message(client: redis.Redis, queue_name: str, message: dict):
    """
    Publica un mensaje en la cola.
    """
    try:
        client.rpush(queue_name, json.dumps(message))
        logger.info(
            f"[{get_bogota_time()}] [INFO] Mensaje publicado en cola '{queue_name}'"
        )
    except redis.RedisError as e:
        logger.error(
            f"[{get_bogota_time()}] [ERROR] Error al publicar en cola '{queue_name}': {str(e)}"
        )
        raise
