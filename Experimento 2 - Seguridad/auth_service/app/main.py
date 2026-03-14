import logging
import pytz
from datetime import datetime
from flask import Flask
from app.config import Config
from app.routes.token import token_bp
from app.models.database import get_engine, get_session_factory

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    logger = logging.getLogger("auth_service")

    engine = get_engine(app.config["DATABASE_URL"])
    app.db_session = get_session_factory(engine)

    app.register_blueprint(token_bp)

    logger.info(f"[{get_bogota_time()}] [INFO] Auth Service iniciado correctamente")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=False)