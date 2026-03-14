"""
Servicio de validación de campos para solicitudes de reserva.
Implementa validaciones básicas requeridas antes de enviar a checksum.
"""
from app.utils import get_bogota_time, setup_logger

logger = setup_logger("validation_service")

# Campos obligatorios para una reserva
REQUIRED_FIELDS = ["checkin", "checkout", "destino", "valor_pagado"]


class ValidationResult:
    """Resultado de validación con detalles."""
    
    def __init__(self, is_valid: bool, errors: list = None, warnings: list = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings
        }


def validate_required_fields(payload: dict) -> ValidationResult:
    """
    Valida que todos los campos obligatorios estén presentes y no sean nulos/vacíos.
    
    Args:
        payload: Diccionario con los datos de la reserva
    
    Returns:
        ValidationResult con el resultado de la validación
    """
    errors = []
    warnings = []
    
    if not payload:
        logger.error(f"[{get_bogota_time()}] [ERROR] Payload vacío recibido")
        return ValidationResult(False, ["Payload vacío o nulo"])
    
    logger.info(f"[{get_bogota_time()}] [INFO] Iniciando validación de campos obligatorios")
    
    for field in REQUIRED_FIELDS:
        if field not in payload:
            error_msg = f"Campo obligatorio '{field}' no está presente"
            errors.append(error_msg)
            logger.warning(f"[{get_bogota_time()}] [WARN] {error_msg}")
        elif payload[field] is None:
            error_msg = f"Campo obligatorio '{field}' es nulo"
            errors.append(error_msg)
            logger.warning(f"[{get_bogota_time()}] [WARN] {error_msg}")
        elif isinstance(payload[field], str) and payload[field].strip() == "":
            error_msg = f"Campo obligatorio '{field}' está vacío"
            errors.append(error_msg)
            logger.warning(f"[{get_bogota_time()}] [WARN] {error_msg}")
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info(
            f"[{get_bogota_time()}] [INFO] Validación de campos exitosa. "
            f"Campos validados: {REQUIRED_FIELDS}"
        )
    else:
        logger.error(
            f"[{get_bogota_time()}] [ERROR] Validación de campos fallida. "
            f"Errores: {len(errors)}"
        )
    
    return ValidationResult(is_valid, errors, warnings)


def validate_date_format(date_str: str, field_name: str) -> tuple:
    """
    Valida el formato de fecha (YYYY-MM-DD).
    
    Returns:
        tuple (is_valid, error_message)
    """
    if not date_str:
        return False, f"{field_name} es requerido"
    
    try:
        parts = date_str.split("-")
        if len(parts) != 3:
            return False, f"{field_name} debe tener formato YYYY-MM-DD"
        
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        
        if not (1900 <= year <= 2100):
            return False, f"{field_name}: año fuera de rango válido"
        if not (1 <= month <= 12):
            return False, f"{field_name}: mes inválido"
        if not (1 <= day <= 31):
            return False, f"{field_name}: día inválido"
        
        return True, None
    except (ValueError, AttributeError):
        return False, f"{field_name} tiene formato de fecha inválido"


def validate_reservation_data(payload: dict) -> ValidationResult:
    """
    Validación completa de datos de reserva.
    Incluye campos obligatorios y formato de fechas.
    
    Args:
        payload: Diccionario con los datos de la reserva
    
    Returns:
        ValidationResult con el resultado completo
    """
    # Primero validar campos obligatorios
    result = validate_required_fields(payload)
    
    if not result.is_valid:
        return result
    
    errors = []
    warnings = []
    
    # Validar formato de fechas
    checkin_valid, checkin_error = validate_date_format(payload.get("checkin"), "checkin")
    if not checkin_valid:
        errors.append(checkin_error)
        logger.warning(f"[{get_bogota_time()}] [WARN] {checkin_error}")
    
    checkout_valid, checkout_error = validate_date_format(payload.get("checkout"), "checkout")
    if not checkout_valid:
        errors.append(checkout_error)
        logger.warning(f"[{get_bogota_time()}] [WARN] {checkout_error}")
    
    # Validar que checkout sea posterior a checkin (warning, no error)
    if checkin_valid and checkout_valid:
        if payload.get("checkout") <= payload.get("checkin"):
            warnings.append("checkout debería ser posterior a checkin")
            logger.warning(f"[{get_bogota_time()}] [WARN] checkout no es posterior a checkin")
    
    # Validar valor_pagado sea numérico
    valor = payload.get("valor_pagado")
    if valor:
        try:
            float(str(valor).replace(",", ""))
        except ValueError:
            errors.append("valor_pagado debe ser numérico")
            logger.warning(f"[{get_bogota_time()}] [WARN] valor_pagado no es numérico: {valor}")
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info(
            f"[{get_bogota_time()}] [INFO] Validación completa exitosa para reserva. "
            f"Destino: {payload.get('destino')}"
        )
    else:
        logger.error(
            f"[{get_bogota_time()}] [ERROR] Validación completa fallida. "
            f"Errores: {errors}"
        )
    
    return ValidationResult(is_valid, errors, warnings)
