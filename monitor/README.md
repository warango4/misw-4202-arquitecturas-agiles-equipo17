# Sistema de Monitoreo de Disponibilidad Funcional

## Descripción

Sistema de monitoreo que verifica la **disponibilidad funcional** del servicio de gestión de reservas usando Celery y Redis. El monitor envía health checks por cola cada 200 milisegundos, verificando que el worker del servicio pueda procesar tareas.

## Arquitectura

```
┌─────────────────────┐                      ┌─────────────────────┐
│  Monitor            │   1. Health Check    │  Reservas           │
│  ┌───────────────┐  │      (por cola)      │  ┌───────────────┐  │
│  │ Celery Beat   │──┼──────────────────────┼─▶│ Celery Worker │  │
│  └───────────────┘  │                      │  └───────┬───────┘  │
│  ┌───────────────┐  │   2. Respuesta       │          │          │
│  │ Celery Worker │◀─┼──────────────────────┼──────────┘          │
│  └───────┬───────┘  │      (por cola)      │                     │
│          │          │                      └─────────────────────┘
│          │          │
│          │ 3. Notifica cambios de estado
│          ▼          │
│  ┌───────────────┐  │
│  │ HTTP Request  │──┼──────────────────────▶ Servicio Notificaciones
│  └───────────────┘  │
└─────────────────────┘
```

## ¿Por qué Health Check Funcional por Cola?

| Tipo | Qué verifica | Limitación |
|------|--------------|------------|
| HTTP `/health` | Solo que el API Flask responda | No verifica el worker |
| **Por Cola** | Que el **worker** pueda procesar tareas | Verifica disponibilidad real |

Al enviar por cola, verificamos que:
- Redis está funcionando
- El worker de Celery está corriendo
- El worker puede procesar tareas
- Las dependencias internas funcionan

## Componentes

### 1. Microservicio Monitor (`microservicio_monitor/`)
- Celery Beat envía health checks cada 200ms por cola
- Worker recibe respuestas y detecta cambios de estado
- Notifica por HTTP cuando el servicio cae o se recupera
- Implementa timeout de 5 segundos

**Endpoints Flask:**
- `GET /health-check` - Ejecutar health check manual
- `GET /metricas` - Métricas de disponibilidad
- `GET /estado` - Estado actual del servicio monitoreado
- `GET /health` - Health del propio monitor

### 2. Microservicio Reservas (`microservicio_reservas/`)
- Worker que recibe y responde health checks
- Soporta modo de fallo aleatorio para testing

**Endpoints Flask:**
- `GET /estado-servicio` - Ver estado y configuración
- `POST /estado-servicio` - Cambiar disponibilidad manualmente
- `GET /modo-aleatorio` - Ver configuración de fallos aleatorios
- `POST /modo-aleatorio` - Activar/desactivar fallos aleatorios

### 3. Microservicio Notificaciones (`microservicio_notificaciones/`)
- Recibe notificaciones de cambios de estado
- Almacena historial

**Endpoints:**
- `POST /notify` - Recibir notificación
- `GET /notificaciones` - Listar notificaciones
- `GET /resumen` - Resumen por tipo de evento

## Requisitos

- Python 3.8+
- Redis Server
- Celery

## Instalación

```bash
pip install Flask Flask-RESTful celery redis requests python-dateutil
```

## Ejecución

```bash
# 1. Redis
redis-server

# 2. Reservas - Flask API (control de estado)
python -m microservicio_reservas.app

# 3. Reservas - Worker (¡ESENCIAL! procesa health checks)
celery -A microservicio_reservas.tareas.tareas worker --loglevel=info -Q reservas_queue

# 4. Notificaciones - Flask API
python -m microservicio_notificaciones.app

# 5. Monitor - Flask API
python -m microservicio_monitor.app

# 6. Monitor - Worker (procesa respuestas)
celery -A microservicio_monitor.tareas.tareas worker --loglevel=info

# 7. Monitor - Beat (dispara health checks cada 200ms)
celery -A microservicio_monitor.tareas.tareas beat --loglevel=info
```

## Variables de Entorno

```bash
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
export NOTIFICATION_API_URL=http://localhost:5002/notify
export MONITOR_PORT=5003
export RESERVAS_PORT=5001
export NOTIFICACIONES_PORT=5002
```

## Métricas y Trazabilidad

### Formato de Logs
```
[METRIC] EVENT_TYPE | key1=value1 | key2=value2
```

### Eventos Registrados

| Evento | Descripción |
|--------|-------------|
| `HEALTH_CHECK_START` | Health check enviado por cola |
| `HEALTH_CHECK_SENT` | Tarea enviada a cola de reservas |
| `HEALTH_CHECK_RECEIVED` | Worker de reservas recibió el check |
| `HEALTH_CHECK_RESPONSE` | Respuesta procesada por monitor |
| `HEALTH_CHECK_TIMEOUT` | Sin respuesta en 5 segundos |
| `SERVICE_DOWN` | Servicio detectado como caído |
| `SERVICE_RECOVERED` | Servicio recuperado |
| `NOTIFICATION_SEND` | Notificación enviada |

### Análisis de Disponibilidad

```bash
# Health checks exitosos
grep "available=True" logs/monitor_health_check.log | wc -l

# Health checks fallidos
grep "available=False" logs/monitor_health_check.log | wc -l

# Eventos de caída
grep "SERVICE_DOWN" logs/monitor_health_check.log

# Recuperaciones
grep "SERVICE_RECOVERED" logs/monitor_health_check.log

# Timeouts
grep "TIMEOUT" logs/monitor_health_check.log
```

## Testing

### Activar fallos aleatorios (30% probabilidad)
```bash
curl -X POST http://localhost:5001/modo-aleatorio \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "probability": 0.3}'
```

### Desactivar fallos aleatorios
```bash
curl -X POST http://localhost:5001/modo-aleatorio \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### Forzar indisponibilidad manual
```bash
curl -X POST http://localhost:5001/estado-servicio \
  -H "Content-Type: application/json" \
  -d '{"available": false}'
```

### Restaurar disponibilidad
```bash
curl -X POST http://localhost:5001/estado-servicio \
  -H "Content-Type: application/json" \
  -d '{"available": true}'
```

### Ver métricas del monitor
```bash
curl http://localhost:5003/metricas
```

### Ver notificaciones recibidas
```bash
curl http://localhost:5002/notificaciones
```

## Estructura de Archivos

```
microservicio_monitor/
├── __init__.py
├── app.py              # Flask API
├── config.py           # Configuración
└── tareas/
    ├── __init__.py
    └── tareas.py       # Health check funcional, timeout, notificaciones

microservicio_reservas/
├── __init__.py
├── app.py              # Flask API (control de estado)
├── config.py
└── tareas/
    ├── __init__.py
    └── tareas.py       # Responde health checks, modo aleatorio

microservicio_notificaciones/
├── __init__.py
├── app.py              # Flask API
└── config.py

logs/
├── monitor_health_check.log
├── reservas_health.log
└── notificaciones.log
```

## Flujo de Health Check

1. **Beat** programa tarea `monitor.health_check_funcional` cada 200ms
2. **Monitor Worker** envía tarea `reservas.health_check_funcional` a cola `reservas_queue`
3. **Reservas Worker** procesa y responde con tarea `monitor.recibir_health_check_funcional`
4. **Monitor Worker** recibe respuesta y verifica cambio de estado
5. Si hay cambio → notifica por HTTP al servicio de notificaciones
6. Si no hay respuesta en 5s → se procesa como TIMEOUT (servicio no disponible)
