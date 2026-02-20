"""
Procesa health checks del monitor y solicitudes del receptor.

Ejecución:
- Flask App:    python -m reservas.app
- Celery Worker: celery -A reservas.tareas.tareas worker --loglevel=info -Q healthcheck.request,reservas.solicitudes
"""

import os
from datetime import datetime

import redis
from flask_restful import Resource, Api

from reservas import create_app
from reservas.config import get_config

config = get_config()

app = create_app('reservas.config.DefaultConfig')
app_context = app.app_context()
app_context.push()

api = Api(app)

redis_client = redis.from_url(config.CELERY_BROKER_URL)
REDIS_ERROR_FLAG_KEY = f'reservas:{config.SERVICE_NAME}:induce_error'


# ============================================================================

class VistaHealth(Resource):
    def get(self):
        redis_healthy = False
        try:
            redis_client.ping()
            redis_healthy = True
        except Exception:
            pass

        error_inducido = False
        try:
            flag = redis_client.get(REDIS_ERROR_FLAG_KEY)
            error_inducido = flag is not None and flag.decode('utf-8') == 'true'
        except Exception:
            pass

        return {
            'service': config.SERVICE_NAME,
            'available': True,
            'redis_connected': redis_healthy,
            'error_inducido': error_inducido,
            'timestamp': datetime.utcnow().isoformat()
        }, 200


class VistaInducirError(Resource):
    def post(self):
        try:
            flag = redis_client.get(REDIS_ERROR_FLAG_KEY)
            activo = flag is not None and flag.decode('utf-8') == 'true'
            nuevo_estado = not activo
            redis_client.set(REDIS_ERROR_FLAG_KEY, 'true' if nuevo_estado else 'false')
        except Exception as e:
            return {'error': f'No se pudo actualizar el flag en Redis: {str(e)}'}, 500

        return {
            'service': config.SERVICE_NAME,
            'error_inducido': nuevo_estado,
            'message': f'Error inducido {"activado" if nuevo_estado else "desactivado"}'
        }, 200


class VistaReservas(Resource):
    _reservas = [
        {'id': '1', 'cliente': 'Juan Pérez', 'fecha': '2024-03-01', 'estado': 'confirmada'},
        {'id': '2', 'cliente': 'María López', 'fecha': '2024-03-02', 'estado': 'pendiente'},
    ]

    def get(self):
        return {
            'service': config.SERVICE_NAME,
            'reservas': self._reservas,
            'timestamp': datetime.utcnow().isoformat()
        }, 200


api.add_resource(VistaHealth, '/health')
api.add_resource(VistaInducirError, '/inducir-error')
api.add_resource(VistaReservas, '/reservas')


if __name__ == '__main__':
    os.makedirs('logs', exist_ok=True)
    port = int(os.environ.get('FLASK_PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
