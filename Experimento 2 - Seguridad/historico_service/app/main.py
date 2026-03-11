import logging
from flask import Flask
from app.config import Config
from app.routes.historico import historico_bp
from app.models.database import get_engine, get_session_factory
from app.utils import get_bogota_time, setup_logger


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s"
    )

    logger = setup_logger("historico_service")

    # Initialize database connection
    engine = get_engine(app.config["DATABASE_URL"])
    app.db_session = get_session_factory(engine)

    # Register blueprints
    app.register_blueprint(historico_bp)

    logger.info(f"[{get_bogota_time()}] [INFO] ============================================")
    logger.info(f"[{get_bogota_time()}] [INFO] Historico Service iniciado correctamente")
    logger.info(f"[{get_bogota_time()}] [INFO] MITM Detection: HABILITADO")
    logger.info(f"[{get_bogota_time()}] [INFO] Session Blacklist TTL: {app.config['SESSION_BLACKLIST_TTL']}s")
    logger.info(f"[{get_bogota_time()}] [INFO] ============================================")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5003, debug=False)
