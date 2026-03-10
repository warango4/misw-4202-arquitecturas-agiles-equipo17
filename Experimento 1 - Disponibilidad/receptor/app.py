"""
Flask API del Receptor
Load balancer que enruta solicitudes entre instancias de reservas según disponibilidad
"""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
import redis
import requests
from flask import Flask, request, jsonify
import pytz

from receptor.config import get_config
from receptor.tareas.tareas import celery_app, get_respuesta, get_metricas, structured_logger

# Configuración
config = get_config()

# Cliente Redis para caché de estado
redis_client = redis.Redis.from_url(config.CELERY_BROKER_URL)


def get_estado_monitor() -> Dict[str, Any]:
    """
    Consulta el estado del servicio de reservas desde el monitor.
    Utiliza caché en Redis con TTL configurable.
    
    Returns:
        Dict con el estado del servicio
    """
    cache_key = 'receptor:cache:estado_monitor'
    
    # Intentar obtener desde caché
    cached_estado = redis_client.get(cache_key)
    if cached_estado:
        return json.loads(cached_estado)
    
    # Si no hay caché, consultar al monitor
    try:
        response = requests.get(
            f'{config.MONITOR_URL}/estado',
            timeout=5
        )
        response.raise_for_status()
        estado = response.json()
        
        # Guardar en caché
        redis_client.setex(
            cache_key,
            config.CACHE_ESTADO_TTL,
            json.dumps(estado)
        )
        
        return estado
        
    except Exception as e:
        structured_logger.error(
            event='ERROR_CONSULTANDO_MONITOR',
            error=str(e),
            monitor_url=config.MONITOR_URL
        )
        
        # En caso de error, asumir que el principal está disponible
        return {
            'service': 'reservas',
            'available': True,
            'status': 'AVAILABLE',
            'error': f'No se pudo consultar monitor: {str(e)}'
        }


def enrutar_solicitud(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enruta una solicitud a la instancia apropiada de reservas.
    Consulta el estado del monitor y decide qué cola usar.
    
    Args:
        datos: Datos de la solicitud del cliente
        
    Returns:
        Dict con información del enrutamiento y la solicitud
    """
    solicitud_id = str(uuid.uuid4())
    tz = pytz.timezone(config.TIMEZONE)
    timestamp = datetime.now(tz).isoformat()
    
    # Consultar estado del monitor
    estado = get_estado_monitor()
    disponible = estado.get('available', True)
    
    # Decidir cola de destino
    if disponible:
        queue_solicitudes = config.RESERVAS_PRINCIPAL_QUEUE
        queue_respuestas = config.RESPUESTAS_PRINCIPAL_QUEUE
        instancia = 'principal'
    else:
        queue_solicitudes = config.RESERVAS_REDUNDANCIA_QUEUE
        queue_respuestas = config.RESPUESTAS_REDUNDANCIA_QUEUE
        instancia = 'redundancia'
    
    structured_logger.info(
        event='ENRUTANDO_SOLICITUD',
        solicitud_id=solicitud_id,
        instancia=instancia,
        disponible=disponible,
        queue=queue_solicitudes
    )
    
    # Preparar payload para la tarea de reservas
    payload = {
        'solicitud_id': solicitud_id,
        'datos': datos
    }
    
    try:
        # Enviar tarea a la cola correspondiente
        celery_app.send_task(
            'reservas.procesar_solicitud',
            args=[payload],
            queue=queue_solicitudes
        )
        
        # Programar verificación de timeout
        celery_app.send_task(
            'receptor.verificar_timeout',
            args=[solicitud_id, timestamp],
            countdown=config.SOLICITUD_TIMEOUT
        )
        
        structured_logger.info(
            event='SOLICITUD_ENVIADA',
            solicitud_id=solicitud_id,
            instancia=instancia,
            queue=queue_solicitudes
        )
        
        # Incrementar contador
        counter_key = f'receptor:metricas:solicitudes_{instancia}'
        redis_client.incr(counter_key)
        
        return {
            'solicitud_id': solicitud_id,
            'status': 'enviada',
            'instancia': instancia,
            'timestamp': timestamp,
            'queue': queue_solicitudes
        }
        
    except Exception as e:
        structured_logger.error(
            event='ERROR_ENVIANDO_SOLICITUD',
            solicitud_id=solicitud_id,
            instancia=instancia,
            error=str(e)
        )
        raise


# Crear aplicación Flask
app = Flask(__name__)
app.config.from_object(config)


@app.route('/health', methods=['GET'])
def health():
    """
    Health check del receptor.
    Verifica conectividad con Redis.
    """
    try:
        # Verificar Redis
        redis_client.ping()
        redis_ok = True
        redis_error = None
    except Exception as e:
        redis_ok = False
        redis_error = str(e)
    
    tz = pytz.timezone(config.TIMEZONE)
    
    health_data = {
        'service': config.SERVICE_NAME,
        'status': 'healthy' if redis_ok else 'degraded',
        'timestamp': datetime.now(tz).isoformat(),
        'checks': {
            'redis': {'status': 'ok' if redis_ok else 'error', 'error': redis_error}
        }
    }
    
    status_code = 200 if redis_ok else 503
    
    return jsonify(health_data), status_code


@app.route('/solicitud', methods=['POST'])
def crear_solicitud():
    """
    Endpoint principal para recibir solicitudes de clientes.
    Enruta la solicitud a la instancia apropiada de reservas.
    
    Body (JSON):
        {
            "tipo": "crear_reserva",  # o cualquier tipo de solicitud
            "datos": {
                "cliente_id": "123",
                "fecha": "2026-02-25",
                ...
            }
        }
    
    Response:
        {
            "solicitud_id": "uuid",
            "status": "enviada",
            "instancia": "principal" | "redundancia",
            "timestamp": "...",
            "message": "Solicitud enviada a procesamiento"
        }
    """
    try:
        datos = request.get_json()
        
        if not datos:
            return jsonify({
                'error': 'Se requiere un body JSON con los datos de la solicitud'
            }), 400
        
        # Enrutar la solicitud
        resultado = enrutar_solicitud(datos)
        
        return jsonify({
            **resultado,
            'message': 'Solicitud enviada a procesamiento',
            'instrucciones': f'Use GET /solicitud/{resultado["solicitud_id"]} para consultar el resultado'
        }), 202  # 202 Accepted
        
    except Exception as e:
        structured_logger.error(event='ERROR_CREANDO_SOLICITUD', error=str(e))
        return jsonify({
            'error': 'Error procesando solicitud',
            'details': str(e)
        }), 500


@app.route('/solicitud/<solicitud_id>', methods=['GET'])
def consultar_solicitud(solicitud_id: str):
    """
    Consulta el estado y resultado de una solicitud.
    
    Response:
        - Si está procesada: devuelve la respuesta completa
        - Si está pendiente: devuelve status "pending"
        - Si hubo timeout: devuelve error de timeout
    """
    respuesta = get_respuesta(solicitud_id)
    
    if respuesta is None:
        return jsonify({
            'solicitud_id': solicitud_id,
            'status': 'pending',
            'message': 'La solicitud aún está siendo procesada'
        }), 202  # 202 Accepted - aún procesando
    
    status = respuesta.get('status')
    
    if status == 'procesada':
        return jsonify(respuesta), 200
    elif status == 'timeout':
        return jsonify(respuesta), 504  # 504 Gateway Timeout
    else:  # error
        return jsonify(respuesta), 500


@app.route('/estado-enrutamiento', methods=['GET'])
def estado_enrutamiento():
    """
    Muestra información sobre el enrutamiento actual.
    Indica a qué instancia se están enviando las solicitudes.
    """
    estado = get_estado_monitor()
    disponible = estado.get('available', True)
    
    if disponible:
        instancia_activa = 'principal'
        queue_activa = config.RESERVAS_PRINCIPAL_QUEUE
    else:
        instancia_activa = 'redundancia'
        queue_activa = config.RESERVAS_REDUNDANCIA_QUEUE
    
    # Obtener métricas de solicitudes
    solicitudes_principal = int(redis_client.get('receptor:metricas:solicitudes_principal') or 0)
    solicitudes_redundancia = int(redis_client.get('receptor:metricas:solicitudes_redundancia') or 0)
    
    tz = pytz.timezone(config.TIMEZONE)
    
    return jsonify({
        'timestamp': datetime.now(tz).isoformat(),
        'instancia_activa': instancia_activa,
        'queue_activa': queue_activa,
        'estado_monitor': estado,
        'metricas': {
            'solicitudes_enviadas_principal': solicitudes_principal,
            'solicitudes_enviadas_redundancia': solicitudes_redundancia,
            'total_solicitudes': solicitudes_principal + solicitudes_redundancia
        }
    }), 200


@app.route('/metricas', methods=['GET'])
def metricas():
    """
    Endpoint para obtener métricas completas del receptor.
    """
    metricas_tareas = get_metricas()
    
    solicitudes_principal = int(redis_client.get('receptor:metricas:solicitudes_principal') or 0)
    solicitudes_redundancia = int(redis_client.get('receptor:metricas:solicitudes_redundancia') or 0)
    
    tz = pytz.timezone(config.TIMEZONE)
    
    return jsonify({
        'service': config.SERVICE_NAME,
        'timestamp': datetime.now(tz).isoformat(),
        'solicitudes': {
            'principal': solicitudes_principal,
            'redundancia': solicitudes_redundancia,
            'total': solicitudes_principal + solicitudes_redundancia
        },
        'respuestas': metricas_tareas
    }), 200


@app.route('/estado-servicio', methods=['POST'])
def recibir_estado_servicio():
    """
    Endpoint para recibir notificaciones PUSH del monitor sobre cambios de estado.
    Esto permite al receptor reaccionar inmediatamente cuando el servicio de reservas
    cambia de estado, sin depender del polling.
    
    Body (JSON):
        {
            "event": "SERVICE_DOWN" | "SERVICE_RECOVERED",
            "service": "reservas",
            "available": true | false,
            "status": "AVAILABLE" | "UNAVAILABLE",
            "timestamp": "...",
            "error": "mensaje de error opcional"
        }
    """
    try:
        datos = request.get_json()
        
        if not datos:
            return jsonify({'error': 'Se requiere body JSON'}), 400
        
        event = datos.get('event')
        available = datos.get('available')
        status = datos.get('status')
        timestamp = datos.get('timestamp')
        error = datos.get('error')
        
        structured_logger.info(
            event='ESTADO_RECIBIDO_PUSH',
            event_type=event,
            available=available,
            status=status,
            timestamp=timestamp
        )
        
        # Actualizar caché inmediatamente con el nuevo estado
        cache_key = 'receptor:cache:estado_monitor'
        estado_actualizado = {
            'service': 'reservas',
            'available': available,
            'status': status,
            'timestamp': timestamp,
            'source': 'push_notification'
        }
        
        # Guardar en caché con TTL extendido ya que es información fresca del monitor
        redis_client.setex(
            cache_key,
            config.CACHE_ESTADO_TTL * 10,  # TTL extendido para notificaciones push
            json.dumps(estado_actualizado)
        )
        
        structured_logger.info(
            event='CACHE_ACTUALIZADO_PUSH',
            event_type=event,
            available=available,
            cache_key=cache_key
        )
        
        return jsonify({
            'message': 'Estado recibido y caché actualizado',
            'event': event,
            'available': available
        }), 200
        
    except Exception as e:
        structured_logger.error(event='ERROR_RECIBIENDO_ESTADO_PUSH', error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/limpiar-cache', methods=['POST'])
def limpiar_cache():
    """
    Endpoint para forzar la actualización del caché del estado del monitor.
    Útil para pruebas.
    """
    cache_key = 'receptor:cache:estado_monitor'
    redis_client.delete(cache_key)
    
    structured_logger.info(event='CACHE_LIMPIADO', cache_key=cache_key)
    
    return jsonify({
        'message': 'Caché del estado del monitor limpiado',
        'cache_key': cache_key
    }), 200


if __name__ == '__main__':
    structured_logger.info(
        event='RECEPTOR_INICIANDO', 
        host=config.FLASK_HOST, 
        port=config.FLASK_PORT,
        monitor_url=config.MONITOR_URL
    )
    
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.DEBUG if hasattr(config, 'DEBUG') else False
    )
