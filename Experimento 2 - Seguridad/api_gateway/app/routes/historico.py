import logging
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.middleware.auth import validate_token_and_permissions
from app.services.proxy import forward_post_json_with_headers

historico_bp = Blueprint("historico", __name__)
bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("route_historico")


def get_client_ip():
    """
    Get the original client IP.
    Priority:
    1. X-Forwarded-For (first IP)
    2. X-Real-IP
    3. request.remote_addr
    """
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    return request.remote_addr


@historico_bp.route("/historico", methods=["POST"])
@validate_token_and_permissions("historico")
def historico():
    logger.info(f"[{get_bogota_time()}] [INFO] Request recibido en /historico")

    payload = request.get_json(silent=True)
    
    # Get original client IP
    client_ip = get_client_ip()
    logger.info(f"[{get_bogota_time()}] [INFO] IP del cliente: {client_ip}")
    
    # Prepare headers to forward to historico_service
    # Include the Authorization header and original client IP
    forward_headers = {
        "Authorization": request.headers.get("Authorization"),
        "X-Original-Client-IP": client_ip
    }
    
    historico_url = current_app.config["HISTORICO_SERVICE_URL"] + "/consulta/historico"
    response = forward_post_json_with_headers(historico_url, payload, forward_headers)

    if response is None:
        logger.error(f"[{get_bogota_time()}] [ERROR] Fallo al conectar con App ConsultaHistorico")
        return jsonify({"error": "Servicio de histórico no disponible"}), 502

    logger.info(f"[{get_bogota_time()}] [INFO] Respuesta de App ConsultaHistorico enviada al cliente")
    return jsonify(response.json()), response.status_code