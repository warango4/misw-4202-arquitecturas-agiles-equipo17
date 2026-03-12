"""
Worker principal del servicio de reservas.
Procesa solicitudes de reserva, valida campos y coordina la validación de checksum.

Flujo:
1. Lee de cola `reservas.request` (mensaje con checksum_original + payload del receptor)
2. Valida campos obligatorios
3. Si válido, publica en `reservas.checksum.request` con checksum_original
4. Espera respuesta en `reservas.checksum.response`
5. Publica resultado final en `reservas.response`
"""
import json
import time
import threading
from datetime import datetime
from app.config import Config
from app.utils import get_bogota_time, setup_logger, BOGOTA_TZ
from app.services.validation_service import validate_reservation_data
from app.services.redis_service import (
    get_redis_client,
    dequeue_message,
    enqueue_message,
    update_auditoria_estado
)

logger = setup_logger("reserva_worker")


class ReservaWorker:
    """
    Worker que procesa solicitudes de reserva.
    Implementa el flujo de validación de campos y coordinación con checksum validator.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.redis_client = get_redis_client(config.REDIS_URL)
        self.running = False
        self._pending_checksums = {}  # Mapea checksum_original -> request data
        self._lock = threading.Lock()
    
    def start(self):
        """Inicia el worker."""
        self.running = True
        logger.info(f"[{get_bogota_time()}] [INFO] ============================================")
        logger.info(f"[{get_bogota_time()}] [INFO] Reserva Worker iniciado")
        logger.info(f"[{get_bogota_time()}] [INFO] Escuchando cola: {self.config.QUEUE_RESERVAS_REQUEST}")
        logger.info(f"[{get_bogota_time()}] [INFO] Publicando a checksum: {self.config.QUEUE_CHECKSUM_REQUEST}")
        logger.info(f"[{get_bogota_time()}] [INFO] ============================================")
        
        # Start checksum response listener in separate thread
        response_thread = threading.Thread(target=self._listen_checksum_responses)
        response_thread.daemon = True
        response_thread.start()
        
        # Main loop for reservation requests
        self._process_reservations()
    
    def stop(self):
        """Detiene el worker."""
        self.running = False
        logger.info(f"[{get_bogota_time()}] [INFO] Reserva Worker detenido")
    
    def _process_reservations(self):
        """Loop principal que procesa solicitudes de reserva."""
        while self.running:
            try:
                # Read from reservation request queue
                message = dequeue_message(
                    self.redis_client,
                    self.config.QUEUE_RESERVAS_REQUEST,
                    timeout=1
                )
                
                if message:
                    self._handle_reservation_request(message)
                
            except Exception as e:
                logger.error(
                    f"[{get_bogota_time()}] [ERROR] Error en loop principal: {str(e)}"
                )
                time.sleep(1)
    
    def _handle_reservation_request(self, message: dict):
        """
        Procesa una solicitud de reserva.
        
        1. Extrae checksum_original y payload del mensaje
        2. Valida campos obligatorios
        3. Si válido, envía a checksum validator con checksum_original
        4. Si inválido, responde con error
        """
        request_start = datetime.now(BOGOTA_TZ)
        
        # Extraer checksum_original y payload del mensaje
        checksum_original = message.get("checksum_original")
        payload = message.get("payload", {})
        
        logger.info(f"[{get_bogota_time()}] [INFO] ========================================")
        logger.info(f"[{get_bogota_time()}] [INFO] Nueva solicitud de reserva recibida")
        logger.info(
            f"[{get_bogota_time()}] [INFO] Checksum original: {checksum_original[:16] if checksum_original else 'NO RECIBIDO'}..."
        )
        logger.info(
            f"[{get_bogota_time()}] [INFO] Datos: destino={payload.get('destino')}, "
            f"checkin={payload.get('checkin')}, checkout={payload.get('checkout')}"
        )
        
        # Validar que se recibió el checksum original
        if not checksum_original:
            logger.error(f"[{get_bogota_time()}] [ERROR] No se recibió checksum_original del receptor")
            self._send_error_response(
                payload,
                "Mensaje inválido: falta checksum_original",
                ["checksum_original es requerido"],
                request_start
            )
            return
        
        # Step 1: Validate required fields
        logger.info(f"[{get_bogota_time()}] [INFO] Paso 1: Validando campos obligatorios...")
        validation_result = validate_reservation_data(payload)
        
        if not validation_result.is_valid:
            # Validation failed - respond with error
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Validación de campos fallida"
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Errores de validación: {validation_result.errors}"
            )
            
            self._send_error_response(
                payload,
                "Validación de campos fallida",
                validation_result.errors,
                request_start
            )
            return
        
        logger.info(f"[{get_bogota_time()}] [INFO] Validación de campos exitosa")
        
        # Step 2: Send to checksum validator with original checksum from receptor
        logger.info(f"[{get_bogota_time()}] [INFO] Paso 2: Enviando a validación de checksum...")
        logger.info(f"[{get_bogota_time()}] [INFO] Usando checksum_original del receptor: {checksum_original[:16]}...")
        
        # Store pending request using original checksum as key
        with self._lock:
            self._pending_checksums[checksum_original] = {
                "payload": payload,
                "request_start": request_start.isoformat(),
                "timestamp": get_bogota_time()
            }
        
        # Prepare checksum validation request - send original checksum for comparison
        checksum_request = {
            "checksum_original": checksum_original,
            "payload": payload,
            "timestamp": get_bogota_time(),
            "correlation_id": checksum_original[:16]
        }
        
        try:
            enqueue_message(
                self.redis_client,
                self.config.QUEUE_CHECKSUM_REQUEST,
                checksum_request
            )
            logger.info(
                f"[{get_bogota_time()}] [INFO] Solicitud enviada a validador de checksum. "
                f"Esperando respuesta..."
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Checksum Request - "
                f"Correlation ID: {checksum_original[:16]} | Queue: {self.config.QUEUE_CHECKSUM_REQUEST}"
            )
        except Exception as e:
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Error al enviar a validador checksum: {str(e)}"
            )
            self._send_error_response(
                payload,
                "Error interno al procesar reserva",
                [str(e)],
                request_start
            )
            # Clean up pending
            with self._lock:
                self._pending_checksums.pop(checksum_original, None)
    
    def _listen_checksum_responses(self):
        """
        Thread que escucha respuestas del validador de checksum.
        """
        logger.info(
            f"[{get_bogota_time()}] [INFO] Listener de checksum response iniciado. "
            f"Cola: {self.config.QUEUE_CHECKSUM_RESPONSE}"
        )
        
        while self.running:
            try:
                response = dequeue_message(
                    self.redis_client,
                    self.config.QUEUE_CHECKSUM_RESPONSE,
                    timeout=1
                )
                
                if response:
                    self._handle_checksum_response(response)
                    
            except Exception as e:
                logger.error(
                    f"[{get_bogota_time()}] [ERROR] Error en listener checksum: {str(e)}"
                )
                time.sleep(1)
    
    def _handle_checksum_response(self, response: dict):
        """
        Procesa la respuesta del validador de checksum.
        
        Args:
            response: Diccionario con:
                - checksum_original: checksum original enviado
                - is_valid: resultado de validación
                - message: mensaje descriptivo
        """
        # Soportar ambos nombres de campo por compatibilidad
        checksum = response.get("checksum_original") or response.get("checksum")
        is_valid = response.get("is_valid", False)
        message = response.get("message", "")
        
        logger.info(f"[{get_bogota_time()}] [INFO] ----------------------------------------")
        logger.info(
            f"[{get_bogota_time()}] [INFO] Respuesta de checksum recibida. "
            f"Checksum: {checksum[:16] if checksum else 'N/A'}..."
        )
        logger.info(
            f"[{get_bogota_time()}] [INFO] Resultado: {'VÁLIDO' if is_valid else 'INVÁLIDO'}"
        )
        
        # Get pending request data
        pending_data = None
        with self._lock:
            pending_data = self._pending_checksums.pop(checksum, None)
        
        if not pending_data:
            logger.warning(
                f"[{get_bogota_time()}] [WARN] No se encontró solicitud pendiente para checksum: "
                f"{checksum[:16] if checksum else 'N/A'}..."
            )
            return
        
        payload = pending_data.get("payload", {})
        request_start_str = pending_data.get("request_start")
        request_start = datetime.fromisoformat(request_start_str) if request_start_str else datetime.now(BOGOTA_TZ)
        
        if is_valid:
            # Checksum validated - send success response
            logger.info(
                f"[{get_bogota_time()}] [INFO] Paso 3: Checksum validado exitosamente"
            )
            logger.info(
                f"[{get_bogota_time()}] [SECURITY] Integridad de datos verificada. "
                f"Checksum coincide."
            )
            
            # Update audit status
            update_auditoria_estado(self.redis_client, checksum, "VERIFICADO")
            
            self._send_success_response(payload, checksum, request_start)
        else:
            # Checksum validation failed
            logger.critical(
                f"[{get_bogota_time()}] [CRITICAL] *** CHECKSUM INVÁLIDO ***"
            )
            logger.error(
                f"[{get_bogota_time()}] [SECURITY] Posible manipulación de datos detectada. "
                f"El checksum no coincide con el original."
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Checksum Validation Failed - "
                f"Correlation ID: {checksum[:16]} | Reason: {message}"
            )
            
            # Update audit status
            update_auditoria_estado(self.redis_client, checksum, "RECHAZADO_CHECKSUM")
            
            self._send_error_response(
                payload,
                "Validación de integridad fallida",
                [message or "El checksum no coincide con el original"],
                request_start
            )
    
    def _send_success_response(self, payload: dict, checksum: str, request_start: datetime):
        """Envía respuesta exitosa al receptor_service."""
        request_duration = (datetime.now(BOGOTA_TZ) - request_start).total_seconds()
        
        response = {
            "estado": "OK",
            "mensaje": "Reserva procesada exitosamente",
            "checksum": checksum,
            "checksum_validado": True,
            "destino": payload.get("destino"),
            "checkin": payload.get("checkin"),
            "checkout": payload.get("checkout"),
            "valor_pagado": payload.get("valor_pagado"),
            "timestamp": get_bogota_time()
        }
        
        try:
            enqueue_message(
                self.redis_client,
                self.config.QUEUE_RESERVAS_RESPONSE,
                response
            )
            
            logger.info(
                f"[{get_bogota_time()}] [INFO] Respuesta exitosa enviada a receptor_service"
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Duración total de procesamiento: {request_duration:.4f}s - EXITOSO"
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Reserva Completada - "
                f"Destino: {payload.get('destino')} | Checksum: {checksum[:16]}..."
            )
            logger.info(f"[{get_bogota_time()}] [INFO] ========================================")
            
        except Exception as e:
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Error al enviar respuesta exitosa: {str(e)}"
            )
    
    def _send_error_response(self, payload: dict, error_message: str, details: list, request_start: datetime):
        """Envía respuesta de error al receptor_service."""
        request_duration = (datetime.now(BOGOTA_TZ) - request_start).total_seconds()
        
        response = {
            "estado": "ERROR",
            "mensaje": error_message,
            "detalles": details,
            "destino": payload.get("destino"),
            "timestamp": get_bogota_time()
        }
        
        try:
            enqueue_message(
                self.redis_client,
                self.config.QUEUE_RESERVAS_RESPONSE,
                response
            )
            
            logger.info(
                f"[{get_bogota_time()}] [INFO] Respuesta de error enviada a receptor_service"
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Duración total de procesamiento: {request_duration:.4f}s - ERROR"
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Reserva Rechazada - "
                f"Razón: {error_message} | Detalles: {details}"
            )
            logger.info(f"[{get_bogota_time()}] [INFO] ========================================")
            
        except Exception as e:
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Error al enviar respuesta de error: {str(e)}"
            )


def run_worker():
    """Función helper para ejecutar el worker."""
    config = Config()
    worker = ReservaWorker(config)
    
    try:
        worker.start()
    except KeyboardInterrupt:
        worker.stop()
