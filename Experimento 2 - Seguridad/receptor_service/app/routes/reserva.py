import json
import logging
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.services.checksum_service import generate_checksum, build_auditoria
from app.services.redis_service import (
    get_redis_client,
    store_auditoria,
    enqueue_request,
    dequeue_response
)

reserva_bp = Blueprint("reserva", __name__)

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("route_receptor_reserva")


@reserva_bp.route("/receptor/reserva", methods=["POST"])
def receptor_reserva():
    logger.info(f"[{get_bogota_time()}] [INFO] Reserva recibida en App Receptor")

    payload = request.get_json(silent=True)
    if not payload:
        logger.warning(f"[{get_bogota_time()}] [WARN] Payload vacío recibido en receptor")
        return jsonify({"error": "Payload requerido"}), 400

    redis_client = get_redis_client(current_app.config["REDIS_URL"])

    checksum = generate_checksum(payload)
    auditoria = build_auditoria(payload, checksum)

    try:
        store_auditoria(redis_client, checksum, auditoria, current_app.config["REDIS_AUDITORIA_TTL"])
    except Exception as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al guardar auditoría: {str(e)}")
        return jsonify({"error": "Error interno al registrar auditoría"}), 500

    queue_request = current_app.config["QUEUE_REQUEST"]
    queue_response = current_app.config["QUEUE_RESPONSE"]

    try:
        enqueue_request(redis_client, queue_request, payload)
    except Exception as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al encolar reserva: {str(e)}")
        return jsonify({"error": "Error interno al encolar reserva"}), 500

    logger.info(f"[{get_bogota_time()}] [INFO] Esperando respuesta de GestorReservas...")
    response_data = dequeue_response(redis_client, queue_response, timeout=10)

    if response_data is None:
        logger.warning(f"[{get_bogota_time()}] [WARN] GestorReservas no respondió a tiempo")
        return jsonify({"mensaje": "Reserva encolada para procesamiento. Sin respuesta inmediata."}), 202

    if response_data.get("estado") == "ERROR":
        logger.error(f"[{get_bogota_time()}] [ERROR] GestorReservas retornó error: {response_data.get('mensaje')}")
        return jsonify({"error": response_data.get("mensaje", "Error al procesar reserva")}), 422

    logger.info(f"[{get_bogota_time()}] [INFO] Reserva procesada exitosamente por GestorReservas")
    return jsonify({"mensaje": "Reserva procesada exitosamente", "detalle": response_data}), 200