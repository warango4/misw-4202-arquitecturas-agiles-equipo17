import jwt
import uuid
import logging
import pytz
from datetime import datetime, timedelta
from app.models.database import Usuario, UsuarioPermiso, Permiso

bogota_tz = pytz.timezone("America/Bogota")


def get_bogota_time():
    return datetime.now(bogota_tz).strftime("%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("auth_service")


def validate_credentials(client_id, client_secret, grant_type):
    if not client_id or not client_secret or not grant_type:
        logger.warning(f"[{get_bogota_time()}] [WARN] Credenciales con campos vacíos o nulos")
        return None, "Todos los campos son requeridos"

    if client_id.strip() == "" or client_secret.strip() == "" or grant_type.strip() == "":
        logger.warning(f"[{get_bogota_time()}] [WARN] Credenciales con valores vacíos")
        return None, "Los campos no pueden estar vacíos"

    return True, None


def get_user_with_permissions(session, client_id, client_secret):
    usuario = session.query(Usuario).filter_by(
        client_id=client_id,
        client_secret=client_secret
    ).first()

    if not usuario:
        logger.warning(f"[{get_bogota_time()}] [WARN] Usuario no encontrado: {client_id}")
        return None, "Credenciales inválidas"

    logger.info(f"[{get_bogota_time()}] [INFO] Usuario encontrado: {client_id}")
    return usuario, None


def get_user_permissions(session, usuario_id):
    permisos = (
        session.query(Permiso.nombre)
        .join(UsuarioPermiso, Permiso.id == UsuarioPermiso.permiso_id)
        .filter(UsuarioPermiso.usuario_id == usuario_id)
        .all()
    )
    return [p.nombre for p in permisos]


def generate_jwt(usuario, permissions, secret_key, algorithm, expiration_minutes, client_ip=None):
    """
    Generate JWT token with client IP for MITM detection.
    
    The token includes:
    - sub: user identifier (client_id)
    - nombre: user name
    - permissions: list of user permissions
    - exp: expiration timestamp
    - iat: issued at timestamp
    - jti: unique token identifier (for session invalidation)
    - client_ip: IP address from which the token was requested (for MITM detection)
    """
    expiration = datetime.utcnow() + timedelta(minutes=expiration_minutes)
    jti = str(uuid.uuid4())  # Unique token identifier
    
    payload = {
        "sub": usuario.client_id,
        "nombre": usuario.nombre,
        "permissions": permissions,
        "exp": expiration,
        "iat": datetime.utcnow(),
        "jti": jti,
        "client_ip": client_ip  # Store client IP for MITM detection
    }
    
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    
    logger.info(
        f"[{get_bogota_time()}] [INFO] JWT generado para usuario: {usuario.client_id} | "
        f"JTI: {jti} | IP: {client_ip}"
    )
    logger.info(
        f"[{get_bogota_time()}] [SECURITY] Token vinculado a IP de origen: {client_ip}"
    )
    
    return token