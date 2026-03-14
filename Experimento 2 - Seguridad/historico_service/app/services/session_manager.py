import redis
from datetime import datetime
from app.utils import get_bogota_time, setup_logger

logger = setup_logger("session_manager")


class SessionManager:
    """
    Manager for handling session blacklisting when MITM is detected.
    Uses Redis to store blacklisted tokens/sessions.
    """

    def __init__(self, redis_url, blacklist_ttl=3600):
        self.redis_client = redis.from_url(redis_url)
        self.blacklist_ttl = blacklist_ttl
        self.BLACKLIST_PREFIX = "session:blacklist:"
        self.USER_BLACKLIST_PREFIX = "user:blacklist:"
        self.MITM_LOG_PREFIX = "mitm:log:"

    def invalidate_session(self, jti, user, detection_info):
        """
        Invalidate a session by adding it to the blacklist.
        Also logs the MITM detection event.
        
        IMPORTANTE: Solo invalida el token específico (jti), NO toda la sesión del usuario.
        Esto permite que nuevos tokens del mis usuario puedan ser usados después de un MITM.
        
        Args:
            jti: JWT Token ID
            user: User identifier
            detection_info: Information about the MITM detection
            
        Returns:
            Boolean indicating success
        """
        try:
            # Blacklist ONLY the specific token (by jti) that detected MITM
            # This prevents other tokens of the same user from being blocked
            if jti:
                blacklist_key = f"{self.BLACKLIST_PREFIX}{jti}"
                self.redis_client.setex(
                    blacklist_key,
                    self.blacklist_ttl,
                    "invalidated_mitm"
                )
                logger.info(
                    f"[{get_bogota_time()}] [INFO] Token invalidado por MITM - JTI: {jti} para usuario: {user}"
                )
            
            # Log the MITM event for audit/metrics
            mitm_log_key = f"{self.MITM_LOG_PREFIX}{datetime.utcnow().timestamp()}"
            mitm_log_data = {
                "user": user,
                "jti": jti or "unknown",
                "token_ip": detection_info.get("token_ip", "unknown"),
                "request_ip": detection_info.get("request_ip", "unknown"),
                "timestamp": get_bogota_time(),
                "action": "session_invalidated"
            }
            self.redis_client.setex(
                mitm_log_key,
                86400,  # Keep logs for 24 hours
                str(mitm_log_data)
            )
            
            logger.critical(
                f"[{get_bogota_time()}] [AUDIT] MITM Event logged - User: {user}, "
                f"Token IP: {detection_info.get('token_ip')}, "
                f"Request IP: {detection_info.get('request_ip')}"
            )
            
            return True
            
        except redis.RedisError as e:
            logger.error(f"[{get_bogota_time()}] [ERROR] Error al invalidar sesión en Redis: {str(e)}")
            return False

    def is_session_blacklisted(self, jti, user):
        """
        Check if a session is blacklisted.
        
        Only checks the specific token (jti), NOT all user sessions.
        This allows other tokens from the same user to continue working.
        
        Returns:
            tuple (is_blacklisted, reason)
        """
        try:
            # Check ONLY the specific token blacklist
            if jti:
                token_blacklisted = self.redis_client.get(f"{self.BLACKLIST_PREFIX}{jti}")
                if token_blacklisted:
                    logger.warning(
                        f"[{get_bogota_time()}] [WARN] Token en blacklist detectado - JTI: {jti}"
                    )
                    return True, "Token invalidado por detección MITM"
            
            # NOTE: We no longer check user blacklist here, as we only invalidate specific tokens
            # This is a design decision to allow users to continue using new tokens after a MITM is detected
            
            return False, None
            
        except redis.RedisError as e:
            logger.error(f"[{get_bogota_time()}] [ERROR] Error al verificar blacklist en Redis: {str(e)}")
            # In case of Redis error, we don't block the request but log it
            return False, None

    def get_mitm_statistics(self):
        """
        Get statistics about MITM detections.
        Returns count and recent events.
        """
        try:
            pattern = f"{self.MITM_LOG_PREFIX}*"
            keys = self.redis_client.keys(pattern)
            
            events = []
            for key in keys[:10]:  # Get last 10 events
                data = self.redis_client.get(key)
                if data:
                    events.append(str(data))
            
            return {
                "total_detections": len(keys),
                "recent_events": events
            }
        except redis.RedisError as e:
            logger.error(f"[{get_bogota_time()}] [ERROR] Error al obtener estadísticas MITM: {str(e)}")
            return {"total_detections": 0, "recent_events": [], "error": str(e)}
