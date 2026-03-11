import jwt
from app.utils import get_bogota_time, setup_logger

logger = setup_logger("mitm_detector")


class MITMDetector:
    """
    Service to detect Man-in-the-Middle attacks by comparing
    the IP address in the token with the actual client IP.
    """

    def __init__(self, secret_key, algorithm):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def decode_token(self, token):
        """
        Decode JWT token and extract payload.
        Returns tuple (payload, error)
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            logger.info(f"[{get_bogota_time()}] [INFO] Token decodificado exitosamente para usuario: {payload.get('sub')}")
            return payload, None
        except jwt.ExpiredSignatureError:
            logger.warning(f"[{get_bogota_time()}] [WARN] Token expirado detectado")
            return None, "Token expirado"
        except jwt.InvalidTokenError as e:
            logger.error(f"[{get_bogota_time()}] [ERROR] Token inválido: {str(e)}")
            return None, f"Token inválido: {str(e)}"

    def validate_ip_context(self, token, client_ip):
        """
        Validate that the IP in the token matches the requesting client IP.
        
        Returns tuple (is_valid, payload, detection_info)
        
        detection_info contains:
        - token_ip: IP stored in token
        - request_ip: IP from current request
        - mitm_detected: Boolean indicating if MITM was detected
        - user: User identifier from token
        - jti: Token unique identifier
        """
        payload, error = self.decode_token(token)
        
        if error:
            return False, None, {
                "error": error,
                "request_ip": client_ip,
                "mitm_detected": False
            }
        
        token_ip = payload.get("client_ip")
        user = payload.get("sub")
        jti = payload.get("jti")
        
        detection_info = {
            "token_ip": token_ip,
            "request_ip": client_ip,
            "user": user,
            "jti": jti,
            "mitm_detected": False
        }
        
        # If no IP was stored in token, log warning but allow (backward compatibility)
        if not token_ip:
            logger.warning(
                f"[{get_bogota_time()}] [WARN] Token sin IP de origen para usuario {user}. "
                f"Request IP: {client_ip}"
            )
            detection_info["warning"] = "Token sin IP de origen"
            return True, payload, detection_info
        
        # Compare IPs
        if token_ip != client_ip:
            logger.critical(
                f"[{get_bogota_time()}] [CRITICAL] *** MITM DETECTADO *** "
                f"Usuario: {user} | Token IP: {token_ip} | Request IP: {client_ip} | JTI: {jti}"
            )
            logger.warning(
                f"[{get_bogota_time()}] [SECURITY] Posible ataque Man-in-the-Middle. "
                f"El token fue generado desde IP {token_ip} pero la solicitud proviene de IP {client_ip}"
            )
            detection_info["mitm_detected"] = True
            return False, payload, detection_info
        
        logger.info(
            f"[{get_bogota_time()}] [INFO] Validación de contexto IP exitosa para usuario {user}. "
            f"IP: {client_ip}"
        )
        return True, payload, detection_info
