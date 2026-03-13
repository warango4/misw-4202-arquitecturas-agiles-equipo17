"""
Servicio de base de datos para persistir reservas verificadas.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Usuario, Reserva
from app.utils import get_bogota_time, setup_logger

logger = setup_logger("db_service")


def get_session(database_url: str):
    """Crea y retorna una sesión de base de datos."""
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def save_reserva(database_url: str, client_id: str, payload: dict) -> bool:
    """
    Persiste una reserva verificada en la base de datos.

    Args:
        database_url: URL de conexión a PostgreSQL
        client_id: Identificador del usuario autenticado (sub del JWT)
        payload: Datos de la reserva con checkin, checkout, destino, valor_pagado

    Returns:
        True si se guardó correctamente, False si ocurrió un error
    """
    session = get_session(database_url)
    try:
        usuario = session.query(Usuario).filter_by(client_id=client_id).first()
        if not usuario:
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Usuario no encontrado en BD: {client_id}"
            )
            return False

        reserva = Reserva(
            usuario_id=usuario.id,
            checkin=payload.get("checkin"),
            checkout=payload.get("checkout"),
            destino=payload.get("destino"),
            valor_pagado=str(payload.get("valor_pagado"))
        )
        session.add(reserva)
        session.commit()

        logger.info(
            f"[{get_bogota_time()}] [INFO] Reserva persistida en BD — "
            f"Usuario: {client_id} | Destino: {payload.get('destino')} | "
            f"ID: {reserva.id}"
        )
        return True

    except Exception as e:
        session.rollback()
        logger.error(
            f"[{get_bogota_time()}] [ERROR] Error al persistir reserva en BD: {str(e)}"
        )
        return False
    finally:
        session.close()
