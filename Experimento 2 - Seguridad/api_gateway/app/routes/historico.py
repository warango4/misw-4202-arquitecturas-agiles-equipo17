import logging
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.middleware.auth import validate_token_and_permissions
from app.services.proxy import forward_post_json

historico_bp = Blueprint("historico", __name__)
bogota_tz = pytz.timezone("America/Bogota")

def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger("route_historico")

@historico_bp.route("/historico", methods=["POST"])
@validate_token_and_permissions("historico")
def historico():
    logger.info(f"[{get_bogota_time()}] [INFO] Request recibido en /historico")

    payload = request.get_json(silent=True)

    historico_url = current_app.config["HISTORICO_SERVICE_URL"] + "/consulta/historico"
    response = forward_post_json(historico_url, payload)

    if response is None:
        logger.error(f"[{get_bogota_time()}] [ERROR] Fallo al conectar con App ConsultaHistorico")
        return jsonify({"error": "Servicio de histórico no disponible"}), 502

    logger.info(f"[{get_bogota_time()}] [INFO] Respuesta de App ConsultaHistorico enviada al cliente")
    return jsonify(response.json()), response.status_code