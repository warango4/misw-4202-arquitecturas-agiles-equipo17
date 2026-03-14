"""
Worker principal del servicio verificador.
Valida la integridad de los datos de reserva comprobando su checksum SHA256.

Flujo:
1. Lee de cola `reservas.checksum.request` (mensaje con checksum_original + payload)
2. Recalcula el SHA256 del payload recibido
3. Compara el checksum recalculado contra el checksum_original
4. Publica el resultado en `reservas.checksum.response`
"""
import time
from datetime import datetime
from app.config import Config
from app.utils import get_bogota_time, setup_logger, BOGOTA_TZ
from app.services.checksum_service import verify_checksum
from app.services.redis_service import (
    get_redis_client,
    dequeue_message,
    enqueue_message,
)

logger = setup_logger("verificador_worker")


class VerificadorWorker:
    """
    Worker que verifica la integridad de datos de reserva mediante SHA256.
    Recibe solicitudes del reservas_service y publica resultados de validación.
    """

    def __init__(self, config: Config):
        self.config = config
        self.redis_client = get_redis_client(config.REDIS_URL)
        self.running = False

    def start(self):
        """Inicia el worker."""
        self.running = True
        logger.info(f"[{get_bogota_time()}] [INFO] ============================================")
        logger.info(f"[{get_bogota_time()}] [INFO] Verificador Worker iniciado")
        logger.info(f"[{get_bogota_time()}] [INFO] Escuchando cola: {self.config.QUEUE_CHECKSUM_REQUEST}")
        logger.info(f"[{get_bogota_time()}] [INFO] Publicando a: {self.config.QUEUE_CHECKSUM_RESPONSE}")
        logger.info(f"[{get_bogota_time()}] [INFO] ============================================")

        self._process_requests()

    def stop(self):
        """Detiene el worker."""
        self.running = False
        logger.info(f"[{get_bogota_time()}] [INFO] Verificador Worker detenido")

    def _process_requests(self):
        """Loop principal que procesa solicitudes de verificación de checksum."""
        while self.running:
            try:
                message = dequeue_message(
                    self.redis_client,
                    self.config.QUEUE_CHECKSUM_REQUEST,
                    timeout=1
                )

                if message:
                    self._handle_checksum_request(message)

            except Exception as e:
                logger.error(
                    f"[{get_bogota_time()}] [ERROR] Error en loop principal: {str(e)}"
                )
                time.sleep(1)

    def _handle_checksum_request(self, message: dict):
        """
        Procesa una solicitud de verificación de checksum.

        1. Extrae checksum_original y payload del mensaje
        2. Recalcula el SHA256 del payload
        3. Compara con checksum_original
        4. Publica el resultado en la cola de respuesta

        Args:
            message: Diccionario con:
                - checksum_original: checksum calculado por receptor_service
                - payload: datos de la reserva
                - correlation_id: identificador de correlación (opcional)
                - timestamp: marca de tiempo del envío (opcional)
        """
        request_start = datetime.now(BOGOTA_TZ)

        checksum_original = message.get("checksum_original")
        payload = message.get("payload", {})
        correlation_id = message.get("correlation_id", "N/A")

        logger.info(f"[{get_bogota_time()}] [INFO] ========================================")
        logger.info(f"[{get_bogota_time()}] [INFO] Solicitud de verificación recibida")
        logger.info(
            f"[{get_bogota_time()}] [INFO] Correlation ID: {correlation_id}"
        )
        logger.info(
            f"[{get_bogota_time()}] [INFO] Checksum original: "
            f"{checksum_original[:16] if checksum_original else 'NO RECIBIDO'}..."
        )
        logger.info(
            f"[{get_bogota_time()}] [INFO] Datos: destino={payload.get('destino')}, "
            f"checkin={payload.get('checkin')}, checkout={payload.get('checkout')}"
        )

        if not checksum_original:
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Mensaje inválido: falta checksum_original"
            )
            self._publish_response(
                checksum_original="",
                is_valid=False,
                message="Mensaje inválido: falta checksum_original"
            )
            return

        if not payload:
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Mensaje inválido: falta payload"
            )
            self._publish_response(
                checksum_original=checksum_original,
                is_valid=False,
                message="Mensaje inválido: falta payload"
            )
            return

        logger.info(f"[{get_bogota_time()}] [INFO] Recalculando checksum del payload...")
        is_valid, result_message = verify_checksum(payload, checksum_original)

        request_duration = (datetime.now(BOGOTA_TZ) - request_start).total_seconds()

        if is_valid:
            logger.info(
                f"[{get_bogota_time()}] [SECURITY] Integridad de datos confirmada. "
                f"Checksum coincide."
            )
            logger.info(
                f"[{get_bogota_time()}] [METRIC] Verificación exitosa - "
                f"Correlation ID: {correlation_id} | Duración: {request_duration:.4f}s"
            )
        else:
            logger.critical(
                f"[{get_bogota_time()}] [CRITICAL] *** MANIPULACIÓN DE DATOS DETECTADA ***"
            )
            logger.error(
                f"[{get_bogota_time()}] [SECURITY] El payload fue alterado en tránsito. "
                f"Correlation ID: {correlation_id} | Duración: {request_duration:.4f}s"
            )

        self._publish_response(
            checksum_original=checksum_original,
            is_valid=is_valid,
            message=result_message
        )

        logger.info(f"[{get_bogota_time()}] [INFO] ========================================")

    def _publish_response(self, checksum_original: str, is_valid: bool, message: str):
        """
        Publica el resultado de la verificación en la cola de respuesta.

        Args:
            checksum_original: checksum original del receptor
            is_valid: resultado de la comparación
            message: mensaje descriptivo del resultado
        """
        response = {
            "checksum_original": checksum_original,
            "is_valid": is_valid,
            "message": message,
            "timestamp": get_bogota_time()
        }

        try:
            enqueue_message(
                self.redis_client,
                self.config.QUEUE_CHECKSUM_RESPONSE,
                response
            )
            logger.info(
                f"[{get_bogota_time()}] [INFO] Respuesta publicada en "
                f"'{self.config.QUEUE_CHECKSUM_RESPONSE}' — "
                f"resultado: {'VÁLIDO' if is_valid else 'INVÁLIDO'}"
            )
        except Exception as e:
            logger.error(
                f"[{get_bogota_time()}] [ERROR] Error al publicar respuesta: {str(e)}"
            )


def run_worker():
    """Función helper para ejecutar el worker."""
    config = Config()
    worker = VerificadorWorker(config)

    try:
        worker.start()
    except KeyboardInterrupt:
        worker.stop()
