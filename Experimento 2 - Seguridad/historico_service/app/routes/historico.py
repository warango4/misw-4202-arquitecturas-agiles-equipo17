from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.services.mitm_detector import MITMDetector
from app.services.session_manager import SessionManager
from app.services.historico_service import get_user_reservations
from app.utils import get_bogota_time, get_client_ip, extract_token, setup_logger

historico_bp = Blueprint("historico", __name__)
logger = setup_logger("route_historico")


@historico_bp.route("/consulta/historico", methods=["POST"])
def consulta_historico():
    request_start = datetime.now()
    
    logger.info(f"[{get_bogota_time()}] [INFO] ========================================")
    logger.info(f"[{get_bogota_time()}] [INFO] Nueva solicitud de histórico recibida")
    
    # Extract token
    auth_header = request.headers.get("Authorization")
    token = extract_token(auth_header)
    
    if not token:
        logger.warning(f"[{get_bogota_time()}] [WARN] Token ausente o malformado")
        return jsonify({
            "error": "Token de autorización requerido",
            "mitm_detected": False
        }), 401
    
    # Get client IP
    client_ip = get_client_ip()
    logger.info(f"[{get_bogota_time()}] [INFO] IP del cliente detectada: {client_ip}")
    
    # Initialize MITM detector
    mitm_detector = MITMDetector(
        secret_key=current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"]
    )
    
    # Initialize session manager
    session_manager = SessionManager(
        redis_url=current_app.config["REDIS_URL"],
        blacklist_ttl=current_app.config["SESSION_BLACKLIST_TTL"]
    )
    
    # Validate IP context (MITM detection)
    is_valid, payload, detection_info = mitm_detector.validate_ip_context(token, client_ip)
    
    # Check if session is already blacklisted
    if payload:
        jti = payload.get("jti")
        user = payload.get("sub")
        
        is_blacklisted, blacklist_reason = session_manager.is_session_blacklisted(jti, user)
        if is_blacklisted:
            logger.warning(
                f"[{get_bogota_time()}] [WARN] Intento de acceso con sesión blacklisteada. "
                f"Usuario: {user}, Razón: {blacklist_reason}"
            )
            request_duration = (datetime.now() - request_start).total_seconds()
            logger.info(f"[{get_bogota_time()}] [METRIC] Duración de request: {request_duration:.4f}s - BLOQUEADO (blacklist)")
            return jsonify({
                "error": "Sesión invalidada",
                "reason": blacklist_reason,
                "mitm_detected": False,
                "session_invalidated": True
            }), 403
    
    # Handle MITM detection
    if not is_valid:
        if detection_info.get("mitm_detected"):
            logger.critical(
                f"[{get_bogota_time()}] [CRITICAL] *** RESPUESTA MITM *** "
                f"Denegando acceso e invalidando sesión"
            )
            
            # Invalidate session
            if payload:
                session_manager.invalidate_session(
                    jti=payload.get("jti"),
                    user=payload.get("sub"),
                    detection_info=detection_info
                )
            
            request_duration = (datetime.now() - request_start).total_seconds()
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Duración de request: {request_duration:.4f}s - "
                f"BLOQUEADO (MITM)"
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] MITM Detection - "
                f"Token IP: {detection_info.get('token_ip')} | "
                f"Request IP: {detection_info.get('request_ip')} | "
                f"User: {detection_info.get('user')}"
            )
            
            return jsonify({
                "error": "Acceso denegado: Inconsistencia de contexto de autenticación detectada",
                "detail": "La dirección IP de la solicitud no coincide con la IP de autenticación original",
                "mitm_detected": True,
                "session_invalidated": True,
                "request_ip": detection_info.get("request_ip")
            }), 403
        else:
            # Token error (expired, invalid, etc.)
            request_duration = (datetime.now() - request_start).total_seconds()
            logger.info(f"[{get_bogota_time()}] [METRIC] Duración de request: {request_duration:.4f}s - BLOQUEADO (token error)")
            return jsonify({
                "error": detection_info.get("error", "Error de autenticación"),
                "mitm_detected": False
            }), 401
    
    # Token is valid, query reservation history
    logger.info(f"[{get_bogota_time()}] [INFO] Validación de seguridad exitosa. Consultando histórico...")
    
    user = payload.get("sub")
    
    session = current_app.db_session()
    try:
        reservas, error = get_user_reservations(session, user)
        
        if error:
            logger.error(f"[{get_bogota_time()}] [ERROR] Error al consultar histórico: {error}")
            return jsonify({"error": error}), 404 if "no encontrado" in error.lower() else 500
        
        request_duration = (datetime.now() - request_start).total_seconds()
        logger.info(
            f"[{get_bogota_time()}] [METRIC] Duración de request: {request_duration:.4f}s - "
            f"EXITOSO ({len(reservas)} reservas)"
        )
        logger.info(
            f"[{get_bogota_time()}] [INFO] Histórico entregado exitosamente para usuario {user}"
        )
        logger.info(f"[{get_bogota_time()}] [INFO] ========================================")
        
        return jsonify({
            "status": "success",
            "user": user,
            "total_reservas": len(reservas),
            "reservas": reservas,
            "security_validated": True,
            "client_ip": client_ip
        }), 200
        
    except Exception as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Excepción al consultar histórico: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500
    finally:
        session.close()


@historico_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "historico_service"}), 200


@historico_bp.route("/metrics/mitm", methods=["GET"])
def mitm_metrics():
    try:
        session_manager = SessionManager(
            redis_url=current_app.config["REDIS_URL"],
            blacklist_ttl=current_app.config["SESSION_BLACKLIST_TTL"]
        )
        
        stats = session_manager.get_mitm_statistics()
        
        logger.info(f"[{get_bogota_time()}] [INFO] Métricas MITM solicitadas. Total detecciones: {stats.get('total_detections', 0)}")
        
        return jsonify({
            "status": "success",
            "mitm_detections": stats
        }), 200
        
    except Exception as e:
        logger.error(f"[{get_bogota_time()}] [ERROR] Error al obtener métricas MITM: {str(e)}")
        return jsonify({"error": str(e)}), 500
