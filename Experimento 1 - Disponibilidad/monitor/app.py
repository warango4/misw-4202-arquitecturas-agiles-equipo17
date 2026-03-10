"""
Microservicio Monitor - Health Check Funcional
==============================================

Monitorea la disponibilidad funcional del servicio de reservas
mediante health checks por cola cada 200ms.

Ejecución:
- Flask App: python -m monitor.app
- Celery Worker: celery -A monitor.tareas.tareas worker --loglevel=info
- Celery Beat: celery -A monitor.tareas.tareas beat --loglevel=info
"""

from monitor import create_app
from flask_restful import Resource, Api
import os
from datetime import datetime

from monitor.tareas.tareas import (
    celery_app,
    health_check_funcional,
    state_manager
)


app = create_app('monitor.config.DefaultConfig')
app_context = app.app_context()
app_context.push()

api = Api(app)


class VistaHealthCheck(Resource):
    """Endpoint para ejecutar un health check manual."""
    
    def get(self):
        """Ejecuta un health check manual."""
        timestamp = datetime.utcnow().isoformat()
        task = health_check_funcional.delay()
        
        return {
            'message': 'Health check funcional iniciado',
            'task_id': task.id,
            'timestamp': timestamp
        }, 202


class VistaMetricas(Resource):
    """Endpoint para obtener métricas de disponibilidad."""
    
    def get(self):
        """Retorna las métricas de monitoreo acumuladas."""
        metrics = state_manager.get_metrics()
        current_state = state_manager.get_state()
        
        total_checks = metrics.get('total_checks', 0)
        successful_checks = metrics.get('successful_checks', 0)
        availability_percentage = (successful_checks / total_checks * 100) if total_checks > 0 else 100.0
        
        def decode_value(value):
            if isinstance(value, bytes):
                return value.decode('utf-8')
            return value
        
        return {
            'service': 'reservas',
            'current_status': 'AVAILABLE' if current_state else 'UNAVAILABLE',
            'metrics': {
                'total_health_checks': total_checks,
                'successful_checks': successful_checks,
                'failed_checks': metrics.get('failed_checks', 0),
                'availability_percentage': round(availability_percentage, 2),
                'last_check_timestamp': decode_value(metrics.get('last_check_timestamp')),
                'last_downtime_start': decode_value(metrics.get('last_downtime_start')),
                'last_recovery_timestamp': decode_value(metrics.get('last_recovery_timestamp'))
            },
            'timestamp': datetime.utcnow().isoformat()
        }, 200


class VistaEstado(Resource):
    """Endpoint para obtener el estado actual del servicio monitoreado."""
    
    def get(self):
        """Retorna el estado actual del servicio de reservas."""
        current_state = state_manager.get_state()
        
        return {
            'service': 'reservas',
            'available': current_state,
            'status': 'AVAILABLE' if current_state else 'UNAVAILABLE',
            'timestamp': datetime.utcnow().isoformat()
        }, 200


class VistaMonitorHealth(Resource):
    """Health check del propio microservicio de monitoreo."""
    
    def get(self):
        """Retorna el estado del servicio de monitoreo."""
        redis_healthy = False
        try:
            if state_manager.redis_client:
                state_manager.redis_client.ping()
                redis_healthy = True
        except:
            pass
        
        return {
            'service': 'monitor',
            'available': True,
            'redis_connected': redis_healthy,
            'timestamp': datetime.utcnow().isoformat()
        }, 200


api.add_resource(VistaHealthCheck, '/health-check')
api.add_resource(VistaMetricas, '/metricas')
api.add_resource(VistaEstado, '/estado')
api.add_resource(VistaMonitorHealth, '/health')


if __name__ == '__main__':
    os.makedirs('logs', exist_ok=True)
    port = int(os.environ.get('MONITOR_PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=True)
