"""
Punto de entrada principal del servicio verificador.
Ejecuta el worker para verificar checksums de reservas.
"""
import logging
import threading
from flask import Flask, jsonify
from app.config import Config
from app.utils import get_bogota_time, setup_logger
from app.workers.verificador_worker import VerificadorWorker

logger = setup_logger("verificador_service")


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
            "service": "verificador_service",
            "timestamp": get_bogota_time()
        }), 200

    @app.route("/status", methods=["GET"])
    def status():
        """Status endpoint with queue info."""
        return jsonify({
            "status": "running",
            "service": "verificador_service",
            "queues": {
                "listening": Config.QUEUE_CHECKSUM_REQUEST,
                "publishing": Config.QUEUE_CHECKSUM_RESPONSE
            },
            "timestamp": get_bogota_time()
        }), 200

    return app


def run_worker():
    """Ejecuta el worker verificador en un thread separado."""
    config = Config()
    worker = VerificadorWorker(config)
    worker.start()


if __name__ == "__main__":
    logger.info(f"[{get_bogota_time()}] [INFO] ============================================")
    logger.info(f"[{get_bogota_time()}] [INFO] Verificador Service iniciando...")
    logger.info(f"[{get_bogota_time()}] [INFO] ============================================")

    # Start worker in background thread
    worker_thread = threading.Thread(target=run_worker)
    worker_thread.daemon = True
    worker_thread.start()

    # Start Flask app for health checks
    app = create_app()
    logger.info(f"[{get_bogota_time()}] [INFO] Health check disponible en puerto 5005")
    app.run(host="0.0.0.0", port=5005, debug=False, use_reloader=False)
