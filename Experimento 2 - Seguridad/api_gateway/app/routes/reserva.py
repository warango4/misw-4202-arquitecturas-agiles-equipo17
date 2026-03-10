import logging
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.middleware.auth import validate_token_and_permissions
from app.services.proxy import forward_post_json

reserva_bp = Blueprint("reserva", __name__)

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("route_reserva")


@reserva_bp.route("/reserva", methods=["POST"])
@validate_token_and_permissions("reserva")
def reserva():
    logger.info(f"[{get_bogota_time()}] [INFO] Request recibido en /reserva")

    body = request.get_json(silent=True)
    if not body:
        logger.warning(f"[{get_bogota_time()}] [WARN] Body vacío o no es JSON válido en /reserva")
        return jsonify({"error": "Body JSON requerido"}), 400

    required_fields = ["checkin", "checkout", "destino", "valor_pagado"]
    missing = [f for f in required_fields if f not in body]
    if missing:
        logger.warning(f"[{get_bogota_time()}] [WARN] Campos faltantes en /reserva: {missing}")
        return jsonify({"error": f"Campos requeridos faltantes: {missing}"}), 400

    payload = {
        "checkin": body["checkin"],
        "checkout": body["checkout"],
        "destino": body["destino"],
        "valor_pagado": body["valor_pagado"],
        "usuario": request.token_payload.get("sub")
    }

    receptor_url = current_app.config["RECEPTOR_SERVICE_URL"] + "/receptor/reserva"
    response = forward_post_json(receptor_url, payload)

    if response is None:
        logger.error(f"[{get_bogota_time()}] [ERROR] Fallo al conectar con App Receptor")
        return jsonify({"error": "Servicio receptor no disponible"}), 502

    logger.info(f"[{get_bogota_time()}] [INFO] Respuesta de App Receptor enviada al cliente")
    return jsonify(response.json()), response.status_code