from app.models.database import Usuario, Reserva
from app.utils import get_bogota_time, setup_logger

logger = setup_logger("historico_service")


def get_user_reservations(session, client_id):
    try:
        usuario = session.query(Usuario).filter_by(client_id=client_id).first()
        
        if not usuario:
            logger.warning(f"[{get_bogota_time()}] [WARN] Usuario no encontrado: {client_id}")
            return None, "Usuario no encontrado"
        
        reservas = (
            session.query(Reserva)
            .filter_by(usuario_id=usuario.id)
            .order_by(Reserva.fecha_registro.desc())
            .all()
        )
        
        logger.info(
            f"[{get_bogota_time()}] [INFO] Consulta de histórico exitosa para usuario {client_id}. "
            f"Total reservas: {len(reservas)}"
        )
        
        reservas_list = [
            {
                "id": r.id,
                "checkin": r.checkin,
                "checkout": r.checkout,
                "destino": r.destino,
                "valor_pagado": r.valor_pagado,
                "fecha_registro": r.fecha_registro.isoformat() if r.fecha_registro else None
            }
            for r in reservas
        ]
        
        return reservas_list, None
        
    except Exception as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al consultar histórico: {str(e)}")
        return None, f"Error interno: {str(e)}"
