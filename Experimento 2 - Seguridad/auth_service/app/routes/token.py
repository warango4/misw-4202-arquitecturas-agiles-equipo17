import logging
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.services.auth_service import (
    validate_credentials,
    get_user_with_permissions,
    get_user_permissions,
    generate_jwt
)

token_bp = Blueprint("token", __name__)

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("route_token")


@token_bp.route("/auth/token", methods=["POST"])
def token():
    logger.info(f"[{get_bogota_time()}] [INFO] Request de autenticación recibido")

    grant_type = request.form.get("grant_type")
    client_id = request.form.get("client_id")
    client_secret = request.form.get("client_secret")

    valid, error = validate_credentials(client_id, client_secret, grant_type)
    if not valid:
        logger.warning(f"[{get_bogota_time()}] [WARN] Validación fallida: {error}")
        return jsonify({"error": error}), 400

    session = current_app.db_session()
    try:
        usuario, error = get_user_with_permissions(session, client_id, client_secret)
        if not usuario:
            return jsonify({"error": error}), 401

        permissions = get_user_permissions(session, usuario.id)
        logger.info(f"[{get_bogota_time()}] [INFO] Permisos obtenidos para {client_id}: {permissions}")

        token_value = generate_jwt(
            usuario,
            permissions,
            current_app.config["SECRET_KEY"],
            current_app.config["JWT_ALGORITHM"],
            current_app.config["JWT_EXPIRATION_MINUTES"]
        )

        return jsonify({
            "access_token": token_value,
            "token_type": "Bearer",
            "expires_in": current_app.config["JWT_EXPIRATION_MINUTES"] * 60
        }), 200

    except Exception as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al generar token: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500
    finally:
        session.close()