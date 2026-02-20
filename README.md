# Experimento de Disponibilidad — Equipo 17

Sistema completo de disponibilidad funcional con redundancia activo-pasiva, failover automático y load balancing inteligente usando Flask, Celery y Redis.

## 🚀 Quick Start

```bash
# 1. Levantar todos los servicios
docker-compose up --build

# 2. Esperar 30 segundos para que todo inicie

# 3. Ejecutar prueba automatizada
.\test-failover.ps1

# 4. O probar manualmente con Postman (ver PRUEBAS_POSTMAN.md)
```

## 📋 Componentes

| Componente | Puerto | Estado | Descripción |
|---|---|---|---|
| **Receptor** | 5000 | ✅ Completo | Load balancer que enruta solicitudes según disponibilidad |
| **Reservas Principal** | 5001 | ✅ Completo | Instancia activa del servicio de reservas |
| **Reservas Redundancia** | 5002 | ✅ Completo | Instancia pasiva (failover) del servicio de reservas |
| **Monitor** | 5003 | ✅ Completo | Monitorea disponibilidad con health checks cada 5s |
| **Redis** | 6380 | ✅ Completo | Broker de mensajes y almacenamiento de estado |

## 🏗️ Arquitectura

```
Cliente (Postman/API)
         │
         ▼
    RECEPTOR :5000
    (Load Balancer)
         │
         ├─────────────┬───────────────┐
         │             │               │
         │        Consulta estado      │
         │             │               │
         │             ▼               │
         │        MONITOR :5003        │
         │      (Health Checks)        │
         │             │               │
         │             │ checks cada 5s│
         │             │               │
         ▼             ▼               ▼
    PRINCIPAL     REDUNDANCIA       REDIS
       :5001          :5002          :6380
    (Activo)       (Pasivo)        (Broker)
```

### Flujo de Operación

1. **Cliente** envía solicitud → `POST http://localhost:5000/solicitud`
2. **Receptor** consulta el estado del monitor
3. **Monitor** reporta si el servicio principal está disponible
4. **Receptor** enruta a:
   - `Reservas Principal` si está disponible ✅
   - `Reservas Redundancia` si el principal falló ⚠️
5. **Instancia seleccionada** procesa la solicitud
6. **Receptor** recibe la respuesta y la entrega al cliente

## 🧪 Pruebas

### Opción 1: Script Automatizado Básico (Recomendado)

```powershell
.\test-failover.ps1
```

Este script ejecuta un flujo completo:
- ✅ Verifica que todos los servicios estén activos
- ✅ Envía solicitud normal (debe ir a principal)
- ✅ Induce fallo en el servicio principal
- ✅ Verifica que el receptor cambie automáticamente a redundancia
- ✅ Envía solicitud durante failover (debe ir a redundancia)
- ✅ Restaura el servicio principal
- ✅ Verifica que el receptor vuelva automáticamente a principal
- ✅ Muestra métricas finales

### Opción 2: Prueba de Carga con Failover Aleatorio

```powershell
.\test-carga-failover.ps1
```

Este script prueba el sistema bajo carga:
- 🚀 Envía **60 solicitudes en paralelo** (bloques de 10)
- ⚠️ **Induce el error aleatoriamente** durante el envío (entre solicitud 15-35)
- ✅ Verifica que **todas las solicitudes se procesen** sin pérdida
- 📊 Muestra distribución: cuántas fueron procesadas por principal vs redundancia
- ⏱️ **Mide latencias** de cada solicitud (tiempo de respuesta completo)
- 📈 **Análisis detallado**: min, max, avg, P50, P95 por instancia
- 🔍 Identifica las 5 solicitudes más lentas
- ⏲️ Compara latencias entre principal y redundancia
- ✓ **Demuestra que el sistema no pierde solicitudes** durante failover bajo carga

**Resultado esperado:**
- 60/60 solicitudes procesadas exitosamente
- Algunas procesadas por principal (antes del fallo)
- Otras procesadas por redundancia (después del fallo)
- 0 solicitudes perdidas
- Latencias típicas: 1000-3000ms por solicitud
- Diferencia de latencia entre instancias visible

### Opción 3: Pruebas Manuales con Postman

Ver guía completa en [PRUEBAS_POSTMAN.md](PRUEBAS_POSTMAN.md)

**Endpoints clave:**

```bash
# Enviar solicitud
curl -X POST http://localhost:5000/solicitud \
  -H "Content-Type: application/json" \
  -d '{"tipo":"crear_reserva","datos":{"cliente_id":"CLI-001"}}'

# Consultar resultado
curl http://localhost:5000/solicitud/{solicitud_id}

# Ver estado de enrutamiento
curl http://localhost:5000/estado-enrutamiento

# Inducir fallo
curl -X POST http://localhost:5001/inducir-error

# Ver métricas
curl http://localhost:5000/metricas
```

## 📊 Verificación del Failover

### 1. Estado Normal (Principal Activo)

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

### 2. Inducir Fallo

```bash
curl -X POST http://localhost:5001/inducir-error
```

### 3. Verificar Failover (después de 10-15 segundos)

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
  "instancia": "redundancia",  ← Cambió automáticamente
  "status": "enviada"
}
```

## 📈 Métricas y Monitoreo

```bash
# Métricas del receptor
curl http://localhost:5000/metricas

# Estado del monitor
curl http://localhost:5003/estado

# Métricas del monitor
curl http://localhost:5003/metricas
```

## 🔍 Logs en Tiempo Real

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

**Eventos clave en logs del receptor:**
- `ENRUTANDO_SOLICITUD` — decisión de enrutamiento
- `SOLICITUD_ENVIADA` — confirmación de envío
- `RESPUESTA_RECIBIDA` — llegada de respuesta

**Eventos clave en logs del monitor:**
- `SERVICE_STATE_CHANGED` — cambio de disponibilidad
- `HEALTH_CHECK_TIMEOUT` — servicio no responde
- `SERVICE_RECOVERED` — servicio se recuperó

## 🛠️ Comandos Útiles

### Gestión de Servicios

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

## 📁 Estructura del Proyecto

```
misw-4202-arquitecturas-agiles-equipo17/
│
├── docker-compose.yml           # Orquestación de servicios
├── README.md                    # Este archivo
├── PRUEBAS_POSTMAN.md          # Guía de pruebas manuales
├── test-failover.ps1           # Script de prueba automatizado
│
├── receptor/                    # ⭐ Load Balancer (Puerto 5000)
│   ├── __init__.py
│   ├── app.py                  # Flask REST API
│   ├── config.py               # Configuración
│   ├── Dockerfile
│   ├── README.md               # Documentación del receptor
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
│   ├── config.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tareas/
│       ├── __init__.py
│       └── tareas.py
│
└── logs/                        # Logs persistentes
    ├── receptor.log
    ├── monitor.log
    └── reservas.log
```

## 🎯 Características Implementadas

### ✅ Receptor (Load Balancer)
- Enrutamiento inteligente basado en disponibilidad
- Failover automático a instancia redundante
- Recovery automático al servicio principal
- Caché del estado del monitor (TTL 2s)
- Detección y manejo de timeouts
- Métricas de solicitudes y respuestas
- API RESTful para integración con clientes

### ✅ Monitor
- Health checks funcionales cada 5 segundos
- Detección automática de fallos
- Detección automática de recuperación
- Timeout configurable (10 segundos default)
- Métricas de disponibilidad
- Logs estructurados en JSON

### ✅ Servicio de Reservas (Activo-Pasivo)
- Dos instancias idénticas (principal y redundancia)
- Error inducido controlable en runtime
- Health checks funcionales
- Procesamiento de solicitudes del receptor
- Respuestas asíncronas vía Celery

### ✅ Infraestructura
- Docker Compose para orquestación
- Redis como broker de mensajes
- Logs persistentes en volumen
- Configuración por variables de entorno
- Health checks HTTP en todos los servicios

## 🔧 Configuración

Todos los servicios se configuran mediante variables de entorno en [docker-compose.yml](docker-compose.yml).

**Variables clave del Receptor:**
- `MONITOR_URL`: URL del servicio monitor (default: http://monitor:5003)
- `CACHE_ESTADO_TTL`: TTL del caché en segundos (default: 2)
- `SOLICITUD_TIMEOUT`: Timeout de solicitudes en segundos (default: 30)

**Variables clave del Monitor:**
- `HEALTH_CHECK_INTERVAL`: Intervalo entre checks en segundos (default: 5)
- `HEALTH_CHECK_TIMEOUT`: Timeout antes de marcar como caído (default: 10)

Ver documentación completa de variables en cada servicio:
- [receptor/README.md](receptor/README.md)
- [monitor/README.md](monitor/README.md) (si existe)
- [reservas/README.md](reservas/README.md) (si existe)

## 🎓 Contexto Académico

**Curso:** MISW-4202 Arquitecturas Ágiles  
**Universidad:** Universidad de los Andes  
**Ciclo:** 3  
**Equipo:** 17

**Objetivo del Experimento:**  
Demostrar un sistema de alta disponibilidad con patrón activo-pasivo, donde el receptor (load balancer) detecta automáticamente fallos en el servicio principal y enruta solicitudes a una instancia redundante sin pérdida de requests.

## 📖 Referencias

- [PRUEBAS_POSTMAN.md](PRUEBAS_POSTMAN.md) — Guía completa de pruebas manuales
- [receptor/README.md](receptor/README.md) — Documentación del receptor
- [Celery Documentation](https://docs.celeryproject.org/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Redis Documentation](https://redis.io/docs/)

## 👥 Equipo 17

Experimento de disponibilidad con redundancia activo-pasiva  
Arquitecturas Ágiles - Universidad de los Andes  
2026