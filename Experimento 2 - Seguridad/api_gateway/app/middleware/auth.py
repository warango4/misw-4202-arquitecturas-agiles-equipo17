import jwt
import logging
import pytz
from datetime import datetime
from functools import wraps
from flask import request, jsonify, current_app

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


def setup_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger


logger = setup_logger("auth_middleware")


def extract_token(auth_header):
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ")[1]


def validate_token_and_permissions(required_permission):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            token = extract_token(auth_header)

            if not token:
                logger.warning(f"[{get_bogota_time()}] [WARN] Token ausente o malformado en el header")
                return jsonify({"error": "Token de autorización requerido"}), 401

            try:
                payload = jwt.decode(
                    token,
                    current_app.config["SECRET_KEY"],
                    algorithms=[current_app.config["JWT_ALGORITHM"]]
                )
                logger.info(f"[{get_bogota_time()}] [INFO] Token validado para usuario: {payload.get('sub')}")
            except jwt.ExpiredSignatureError:
                logger.warning(f"[{get_bogota_time()}] [WARN] Token expirado")
                return jsonify({"error": "Token expirado"}), 401
            except jwt.InvalidTokenError as e:
                logger.error(f"[{get_bogota_time()}] [ERROR] Token inválido: {str(e)}")
                return jsonify({"error": "Token inválido"}), 401

            permissions = payload.get("permissions", [])
            if required_permission not in permissions:
                logger.warning(
                    f"[{get_bogota_time()}] [WARN] Usuario {payload.get('sub')} sin permiso '{required_permission}'"
                )
                return jsonify({"error": "No tiene permisos para acceder a este recurso"}), 403

            logger.info(
                f"[{get_bogota_time()}] [INFO] Permiso '{required_permission}' verificado para {payload.get('sub')}"
            )
            request.token_payload = payload
            return f(*args, **kwargs)
        return wrapper
    return decorator