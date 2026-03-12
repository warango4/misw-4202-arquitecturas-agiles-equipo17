"""
Punto de entrada principal del servicio de reservas.
Ejecuta el worker para procesar solicitudes de reserva.
"""
import logging
import threading
from flask import Flask, jsonify
from app.config import Config
from app.utils import get_bogota_time, setup_logger
from app.workers.reserva_worker import ReservaWorker

logger = setup_logger("reservas_service")


def create_app():
    """Crea la aplicación Flask para health checks."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s"
    )
    
    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "service": "reservas_service",
            "timestamp": get_bogota_time()
        }), 200
    
    @app.route("/status", methods=["GET"])
    def status():
        """Status endpoint with queue info."""
        return jsonify({
            "status": "running",
            "service": "reservas_service",
            "queues": {
                "listening": Config.QUEUE_RESERVAS_REQUEST,
                "publishing_checksum": Config.QUEUE_CHECKSUM_REQUEST,
                "listening_checksum": Config.QUEUE_CHECKSUM_RESPONSE,
                "publishing_response": Config.QUEUE_RESERVAS_RESPONSE
            },
            "timestamp": get_bogota_time()
        }), 200
    
    return app


def run_worker():
    """Ejecuta el worker de reservas en un thread separado."""
    config = Config()
    worker = ReservaWorker(config)
    worker.start()


if __name__ == "__main__":
    logger.info(f"[{get_bogota_time()}] [INFO] ============================================")
    logger.info(f"[{get_bogota_time()}] [INFO] Reservas Service iniciando...")
    logger.info(f"[{get_bogota_time()}] [INFO] ============================================")
    
    # Start worker in background thread
    worker_thread = threading.Thread(target=run_worker)
    worker_thread.daemon = True
    worker_thread.start()
    
    # Start Flask app for health checks
    app = create_app()
    logger.info(f"[{get_bogota_time()}] [INFO] Health check disponible en puerto 5004")
    app.run(host="0.0.0.0", port=5004, debug=False, use_reloader=False)
