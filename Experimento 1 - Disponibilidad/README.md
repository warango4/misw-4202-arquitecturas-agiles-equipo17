# Experimento de Disponibilidad — Equipo 17

## Conformación de equipo

| Nombres         | Email Uniandes                | Usuario GitHub |
|-----------------|-------------------------------|----------------|
| Wendy Arango    | w.arangoc@uniandes.edu.co    | warango4       |
| Andrés Echeverry| a.echeverryb@uniandes.edu.co | afecheverryb10 |
| Juan Vega       | js.vega1@uniandes.edu.co     | jsebasvegag    |
| Julio Urian     | j.urianv@uniandes.edu.co     | jurianvilla    |


Sistema completo de disponibilidad funcional con redundancia activo-pasiva, failover automático y balanceo de carga inteligente usando Flask, Celery y Redis.

## Inicio rápido

```bash
# 1. Levantar todos los servicios
docker-compose up --build

# 2. Esperar 30 segundos para que todo inicie

# 3. Ejecutar prueba de carga con failover
.\test-carga-failover.ps1        # Windows
python3 test-carga-failover.py   # macOS / Linux
```

## Componentes

| Componente            | Puerto | Descripción                                                  |
|-----------------------|--------|--------------------------------------------------------------|
| Receptor              | 5000   | Load balancer que enruta solicitudes según disponibilidad    |
| Reservas Principal    | 5001   | Instancia activa del servicio de reservas                    |
| Reservas Redundancia  | 5002   | Instancia pasiva (failover) del servicio de reservas         |
| Monitor               | 5003   | Monitorea disponibilidad con health checks cada 500ms        |
| Redis                 | 6380   | Broker de mensajes y almacenamiento de estado                |


### Flujo de operación

1. El cliente envía una solicitud a `POST http://localhost:5000/solicitud`
2. El receptor consulta el estado del monitor
3. El monitor reporta si el servicio principal está disponible
4. El receptor enruta la solicitud a:
   - Reservas Principal, si está disponible
   - Reservas Redundancia, si el principal ha fallado
5. La instancia seleccionada procesa la solicitud
6. El receptor recibe la respuesta y la entrega al cliente

## Pruebas

### Opción 1: Prueba de carga con failover aleatorio (recomendado)

En Windows (PowerShell):

```powershell
.\test-carga-failover.ps1
```

En macOS o Linux:

```bash
python3 test-carga-failover.py
```

Este script prueba el sistema bajo carga:
- Envía 60 solicitudes en paralelo (bloques de 10)
- Induce el error aleatoriamente durante el envío (entre solicitudes 15 y 35)
- Verifica que todas las solicitudes se procesen sin pérdida
- Muestra la distribución entre principal y redundancia
- Mide la latencia de cada solicitud (tiempo de respuesta completo)
- Presenta análisis detallado: min, max, promedio, P50 y P95 por instancia
- Identifica las 5 solicitudes más lentas
- Compara latencias entre instancias

Resultado esperado:
- 60/60 solicitudes procesadas exitosamente
- Algunas procesadas por el principal (antes del fallo)
- Otras procesadas por la redundancia (después del fallo)
- 0 solicitudes perdidas
- Latencias típicas: 1000–3000ms por solicitud

### Opción 2: Pruebas manuales con curl

Endpoints clave:

```bash
# Enviar solicitud
curl -X POST http://localhost:5000/solicitud \
  -H "Content-Type: application/json" \
  -d '{"tipo":"crear_reserva","datos":{"cliente_id":"CLI-001"}}'

# Consultar resultado
curl http://localhost:5000/solicitud/{solicitud_id}

# Ver estado de enrutamiento
curl http://localhost:5000/estado-enrutamiento

# Inducir fallo (activa o desactiva el error en la instancia principal)
curl -X POST http://localhost:5001/inducir-error

# Ver métricas
curl http://localhost:5000/metricas
```

## Verificación del failover

### 1. Estado normal (principal activo)

```bash
curl http://localhost:5000/estado-enrutamiento
```

```json
{
  "instancia_activa": "principal",
  "queue_activa": "reservas.principal.solicitudes",
  "estado_monitor": {
    "available": true,
    "status": "AVAILABLE"
  }
}
```

### 2. Inducir fallo

```bash
curl -X POST http://localhost:5001/inducir-error
```

### 3. Verificar failover (después de unos segundos)

```bash
curl http://localhost:5000/estado-enrutamiento
```

```json
{
  "instancia_activa": "redundancia",
  "queue_activa": "reservas.redundancia.solicitudes",
  "estado_monitor": {
    "available": false,
    "status": "UNAVAILABLE"
  }
}
```

### 4. Las solicitudes ahora van a redundancia

```bash
curl -X POST http://localhost:5000/solicitud \
  -H "Content-Type: application/json" \
  -d '{"tipo":"test"}'
```

```json
{
  "solicitud_id": "...",
  "instancia": "redundancia",
  "status": "enviada"
}
```

## Métricas y monitoreo

```bash
# Métricas del receptor
curl http://localhost:5000/metricas

# Estado del monitor
curl http://localhost:5003/estado

# Métricas del monitor
curl http://localhost:5003/metricas
```

## Logs en tiempo real

```bash
# Ver todos los logs
docker-compose logs -f

# Logs del receptor
docker logs receptor -f

# Logs del monitor
docker logs monitor -f

# Logs de reservas principal
docker logs reservas-principal -f

# Logs de reservas redundancia
docker logs reservas-redundancia -f
```

Eventos clave en logs del receptor:
- `ENRUTANDO_SOLICITUD` — decisión de enrutamiento
- `SOLICITUD_ENVIADA` — confirmación de envío
- `RESPUESTA_RECIBIDA` — llegada de respuesta

Eventos clave en logs del monitor:
- `SERVICE_STATE_CHANGED` — cambio de disponibilidad
- `HEALTH_CHECK_TIMEOUT` — servicio no responde
- `SERVICE_RECOVERED` — servicio se recuperó

## Comandos útiles

### Gestión de servicios

```bash
# Levantar todo
docker-compose up --build

# Levantar en background
docker-compose up -d --build

# Reiniciar solo un servicio
docker-compose restart receptor

# Reconstruir solo un servicio
docker-compose up -d --no-deps --build receptor

# Parar todo
docker-compose down

# Parar y limpiar volúmenes
docker-compose down -v
```

### Debugging

```bash
# Ver estado de contenedores
docker ps

# Entrar a un contenedor
docker exec -it receptor /bin/bash

# Ver logs desde un punto específico
docker logs receptor --since 5m

# Limpiar caché del receptor
curl -X POST http://localhost:5000/limpiar-cache

# Ver métricas de Redis
docker exec redis redis-cli -p 6379 INFO stats
```

## Estructura del proyecto

```
misw-4202-arquitecturas-agiles-equipo17/
│
├── docker-compose.yml           # Orquestación de servicios
├── README.md                    # Este archivo
├── test-carga-failover.ps1     # Script de prueba de carga (PowerShell)
├── test-carga-failover.py      # Script de prueba de carga (Python)
│
├── receptor/                    # Load Balancer (Puerto 5000)
│   ├── __init__.py
│   ├── app.py                  # Flask REST API
│   ├── config.py               # Configuración
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tareas/
│       ├── __init__.py
│       └── tareas.py           # Celery tasks
│
├── reservas/                    # Servicio de Reservas
│   ├── __init__.py
│   ├── app.py                  # Flask API (Principal: 5001, Redundancia: 5002)
│   ├── config.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tareas/
│       ├── __init__.py
│       └── tareas.py
│
├── monitor/                     # Monitor de Disponibilidad (Puerto 5003)
│   ├── __init__.py
│   ├── app.py                  # Flask API
│   ├── celery_app.py
│   ├── config.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── tareas.py
│   └── tareas/
│       ├── __init__.py
│       └── tareas.py
│
└── logs/                        # Logs persistentes
    ├── receptor.log
    ├── monitor.log
    └── reservas.log
```

## Características implementadas

### Receptor (Load Balancer)
- Enrutamiento inteligente basado en disponibilidad
- Failover automático a instancia redundante
- Recovery automático al servicio principal
- Caché del estado del monitor (TTL 1s)
- Detección y manejo de timeouts
- Métricas de solicitudes y respuestas
- API RESTful para integración con clientes

### Monitor
- Health checks funcionales cada 500ms
- Detección automática de fallos
- Detección automática de recuperación
- Timeout configurable (10 segundos por defecto)
- Métricas de disponibilidad
- Logs estructurados en JSON

### Servicio de Reservas (Activo-Pasivo)
- Dos instancias idénticas (principal y redundancia)
- Error inducido controlable en runtime (toggle via `/inducir-error`)
- Health checks funcionales
- Procesamiento de solicitudes del receptor
- Respuestas asíncronas vía Celery

### Infraestructura
- Docker Compose para orquestación
- Redis como broker de mensajes
- Logs persistentes en volumen
- Configuración por variables de entorno
- Health checks HTTP en todos los servicios

## Configuración

Todos los servicios se configuran mediante variables de entorno en [docker-compose.yml](docker-compose.yml).

Variables clave del Receptor:
- `MONITOR_URL`: URL del servicio monitor (por defecto: `http://monitor:5003`)
- `CACHE_ESTADO_TTL`: TTL del caché en segundos (por defecto: `1`)
- `SOLICITUD_TIMEOUT`: Timeout de solicitudes en segundos (por defecto: `5`)

Variables clave del Monitor:
- `HEALTH_CHECK_INTERVAL`: Intervalo entre checks en segundos (por defecto: `0.5`)
- `HEALTH_CHECK_TIMEOUT`: Timeout antes de marcar como caído (por defecto: `10`)

## Contexto académico

**Curso:** MISW-4202 Arquitecturas Ágiles
**Universidad:** Universidad de los Andes
**Ciclo:** 3
**Equipo:** 17

**Objetivo del experimento:**
Demostrar un sistema de alta disponibilidad con patrón activo-pasivo, donde el receptor (load balancer) detecta automáticamente fallos en el servicio principal y enruta solicitudes a una instancia redundante sin pérdida de requests.

## Referencias

- [Celery Documentation](https://docs.celeryproject.org/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Redis Documentation](https://redis.io/docs/)

## Equipo 17

Experimento de disponibilidad con redundancia activo-pasiva
Arquitecturas Ágiles — Universidad de los Andes
2026
