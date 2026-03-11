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

    payload = request.get_json(silent=True)

    receptor_url = current_app.config["RECEPTOR_SERVICE_URL"] + "/receptor/reserva"
    response = forward_post_json(receptor_url, payload)

    if response is None:
        logger.error(f"[{get_bogota_time()}] [ERROR] Fallo al conectar con App Receptor")
        return jsonify({"error": "Servicio receptor no disponible"}), 502

    logger.info(f"[{get_bogota_time()}] [INFO] Respuesta de App Receptor enviada al cliente")
    return jsonify(response.json()), response.status_code