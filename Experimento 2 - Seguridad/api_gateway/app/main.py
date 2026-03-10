import logging
import pytz
from datetime import datetime
from flask import Flask
from app.config import Config
from app.routes.reserva import reserva_bp
from app.routes.historico import historico_bp
from app.routes.token import token_bp

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s"
    )

    logger = logging.getLogger("api_gateway")

    app.register_blueprint(reserva_bp)
    app.register_blueprint(historico_bp)
    app.register_blueprint(token_bp)

    logger.info(f"[{get_bogota_time()}] [INFO] API Gateway iniciado correctamente")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)