import logging
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.services.proxy import forward_post_form

token_bp = Blueprint("token", __name__)

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("route_token")


@token_bp.route("/token", methods=["POST"])
def token():
    logger.info(f"[{get_bogota_time()}] [INFO] Request recibido en /token")

    grant_type = request.form.get("grant_type")
    client_id = request.form.get("client_id")
    client_secret = request.form.get("client_secret")

    if not all([grant_type, client_id, client_secret]):
        logger.warning(f"[{get_bogota_time()}] [WARN] Parámetros faltantes en /token")
        return jsonify({"error": "Parámetros grant_type, client_id y client_secret son requeridos"}), 400

    auth_url = current_app.config["AUTH_SERVICE_URL"] + "/auth/token"
    form_data = {
        "grant_type": grant_type,
        "client_id": client_id,
        "client_secret": client_secret
    }

    response = forward_post_form(auth_url, form_data)

    if response is None:
        logger.error(f"[{get_bogota_time()}] [ERROR] Fallo al conectar con App Autorización")
        return jsonify({"error": "Servicio de autorización no disponible"}), 502

    logger.info(f"[{get_bogota_time()}] [INFO] Respuesta del servicio de autorización enviada al cliente")
    return jsonify(response.json()), response.status_code