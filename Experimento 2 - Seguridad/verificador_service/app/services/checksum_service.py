"""
Servicio de verificación de checksum.
Recalcula el SHA256 del payload y lo compara contra el checksum original
enviado por el receptor_service.
"""
import hashlib
import json
from app.utils import get_bogota_time, setup_logger

logger = setup_logger("checksum_service")


def recalculate_checksum(payload: dict) -> str:
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    logger.info(f"[{get_bogota_time()}] [INFO] Checksum recalculado: {checksum[:16]}...")
    return checksum


def verify_checksum(payload: dict, checksum_original: str) -> tuple[bool, str]:
    checksum_recalculado = recalculate_checksum(payload)

    if checksum_recalculado == checksum_original:
        logger.info(
            f"[{get_bogota_time()}] [SECURITY] Checksum válido. "
            f"Original: {checksum_original[:16]}... | "
            f"Recalculado: {checksum_recalculado[:16]}..."
        )
        return True, "Checksum válido"

    logger.critical(
        f"[{get_bogota_time()}] [CRITICAL] *** CHECKSUM INVÁLIDO *** "
        f"Posible manipulación de datos detectada. "
        f"Original: {checksum_original[:16]}... | "
        f"Recalculado: {checksum_recalculado[:16]}..."
    )
    return False, (
        f"Checksum no coincide. "
        f"Original: {checksum_original[:16]}... | "
        f"Recalculado: {checksum_recalculado[:16]}..."
    )
