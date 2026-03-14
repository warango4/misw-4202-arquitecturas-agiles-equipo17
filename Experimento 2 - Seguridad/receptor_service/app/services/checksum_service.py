import hashlib
import json
import logging
import pytz
from datetime import datetime

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("checksum_service")


def generate_checksum(payload: dict) -> str:
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    logger.info(f"[{get_bogota_time()}] [INFO] Checksum generado: {checksum[:16]}...")
    return checksum


def build_auditoria(payload: dict, checksum: str) -> dict:
    return {
        "fecha_registro": datetime.now(bogota_tz).isoformat(),
        "checksum": checksum,
        "payload": payload,
        "estado": "POR VERIFICAR"
    }