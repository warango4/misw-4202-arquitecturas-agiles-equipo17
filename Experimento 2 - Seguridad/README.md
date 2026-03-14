# Experimento de Seguridad — Equipo 17

## Conformación de equipo

| Nombres         | Email Uniandes                | Usuario GitHub |
|-----------------|-------------------------------|----------------|
| Wendy Arango    | w.arangoc@uniandes.edu.co    | warango4       |
| Andrés Echeverry| a.echeverryb@uniandes.edu.co | afecheverryb10 |
| Juan Vega       | js.vega1@uniandes.edu.co     | jsebasvegag    |
| Julio Urian     | j.urianv@uniandes.edu.co     | jurianvilla    |

Sistema de seguridad completo con detección de ataques Man-in-the-Middle (MITM) y validación de integridad de datos mediante checksums. Implementa mecanismos de validación de contexto de autenticación basados en dirección IP del cliente y detección de manipulación de payloads en colas de mensajería.

## Inicio rápido

```bash
# 1. Levantar todos los servicios
cd "Experimento 2 - Seguridad"
docker-compose up --build

# 2. En otra terminal, activar ambiente virtual (Primera vez)
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows
source venv/bin/activate           # macOS / Linux

# 3. Instalar dependencias
pip install --upgrade pip
pip install requests pytz

# 4. Ejecutar prueba de detección MITM
python experiment_1_mitm_detection.py

# 5. Ejecutar prueba de integridad de datos
python experiment_2_data_integrity.py
```

## Componentes

| Componente            | Puerto | Descripción                                                          |
|-----------------------|--------|----------------------------------------------------------------------|
| API Gateway           | 5000   | Punto de entrada único, valida tokens y captura IP del cliente       |
| Auth Service          | 5001   | Genera tokens JWT con la IP del cliente embebida                     |
| Receptor Service      | 5002   | Recibe reservas, genera checksum y encola                            |
| Histórico Service     | 5003   | Consulta de histórico con detección MITM                             |
| Reservas Service      | 5004   | Procesa reservas y coordina validación de checksum                   |
| PostgreSQL            | 5432   | Base de datos                                                        |
| Redis                 | 6379   | Cache, colas de mensajería y sesiones blacklisteadas                |

## Pruebas

### Opción 1: Prueba automática de detección MITM

**Descripción:** Valida que el sistema detecta correctamente los ataques Man-in-the-Middle comparando la IP de autenticación con la IP de la request.

#### Comando básico (100 requests, 30% MITM):

```powershell
python experiment_1_mitm_detection.py
```

#### Ejemplos con parámetros personalizados:

```powershell
# 300 requests, 50% ataques MITM
python experiment_1_mitm_detection.py --total-requests 300 --mitm-percentage 50

# 200 requests, 20% ataques MITM
python experiment_1_mitm_detection.py --total-requests 200 --mitm-percentage 20

# Con URL custom del API Gateway
python experiment_1_mitm_detection.py --total-requests 100 --mitm-percentage 30 --api-gateway http://localhost:5000

# Con número custom de tokens independientes
python experiment_1_mitm_detection.py --total-requests 150 --mitm-percentage 40 --num-tokens 10
```

**Resultado esperado:**
- Detección correcta de solicitudes MITM
- Rechazo de solicitudes con IP inconsistente
- Invalidación de sesiones comprometidas
- Reporte de métricas de detección

### Opción 2: Prueba automática de detección de manipulación de datos

**Descripción:** Valida que el sistema detecta correctamente la alteración de payloads mediante checksums SHA256.

#### Comando básico (100 requests, 30% manipuladas):

```powershell
python experiment_2_data_integrity.py
```

#### Ejemplos con parámetros personalizados:

```powershell
# 300 requests, 50% con datos manipulados
python experiment_2_data_integrity.py --total-requests 300 --tampering-percentage 50

# 200 requests, 20% manipuladas
python experiment_2_data_integrity.py --total-requests 200 --tampering-percentage 20

# Con URL custom del API Gateway
python experiment_2_data_integrity.py --total-requests 100 --tampering-percentage 30 --api-gateway http://localhost:5000
```

**Resultado esperado:**
- Detección correcta de datos manipulados
- Rechazo de reservas con checksum inválido
- Reporte de intentos de manipulación
- Análisis detallado de integridad de datos

### Opción 3: Pruebas manuales con curl

Endpoints clave:

```bash
# Obtener token
TOKEN=$(curl -s -X POST http://localhost:5000/token \
  -d "grant_type=client_credentials" \
  -d "client_id=admin" \
  -d "client_secret=admin" | jq -r '.access_token')

# Consultar histórico (solicitud legítima)
curl -X POST http://localhost:5000/historico \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# Simular ataque MITM (solicitud desde IP diferente)
curl -X POST http://localhost:5000/historico \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Forwarded-For: 192.168.1.100" \
  -H "Content-Type: application/json" \
  -d '{}'

# Ver métricas MITM
curl http://localhost:5003/metrics/mitm

# Crear reserva
curl -X POST http://localhost:5000/reservas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"checkin":"2026-03-15","checkout":"2026-03-20","destino":"Bogotá","valor":500000}'
```

## Hipótesis de Seguridad

### Detección de MITM

> *"Si un atacante intercepta un token JWT válido y lo utiliza desde una dirección IP diferente a la que se usó durante la autenticación original, el sistema debe ser capaz de detectar esta inconsistencia y rechazar la solicitud, invalidando la sesión comprometida."*

### Validación de Integridad

> *"Si los datos de una reserva son manipulados durante su tránsito por las colas de mensajería, el sistema debe detectar la inconsistencia mediante validación de checksum y rechazar la operación."*

## Verificación del Sistema

### 1. Solicitud legítima exitosa

```bash
curl -X POST http://localhost:5000/historico \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Respuesta esperada**: Acceso otorgado con histórico de reservas.

### 2. Ataque MITM detectado

```bash
curl -X POST http://localhost:5000/historico \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Forwarded-For: 192.168.1.100" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Respuesta esperada**:
```json
{
  "error": "Acceso denegado: Inconsistencia de contexto de autenticación detectada",
  "detail": "La dirección IP de la solicitud no coincide con la IP de autenticación original",
  "mitm_detected": true,
  "session_invalidated": true,
  "token_ip": "<IP_original>",
  "request_ip": "192.168.1.100"
}
```

### 3. Validación de checksum exitosa

```bash
curl -X POST http://localhost:5000/reservas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"checkin":"2026-03-15","checkout":"2026-03-20","destino":"Bogotá","valor":500000}'
```

**Respuesta esperada**: Reserva creada exitosamente con integridad verificada.

### 4. Manipulación de datos detectada

Al ejecutar `experiment_2_data_integrity.py`, el sistema simula intentos de manipulación y valida que sean detectados.

**Respuesta esperada**: Rechazo de la reserva con error de checksum inválido.

## Colas de Mensajería

| Cola | Publicador | Consumidor | Descripción |
|------|------------|------------|-------------|
| `reservas.request` | Receptor Service | Reservas Service | Solicitudes de reserva |
| `reservas.response` | Reservas Service | Receptor Service | Resultado final |
| `reservas.checksum.request` | Reservas Service | Checksum Validator | Solicitud de validación |
| `reservas.checksum.response` | Checksum Validator | Reservas Service | Resultado de validación |

## Logs en tiempo real

## Logs en tiempo real

```bash
# Ver todos los logs
docker-compose logs -f

# Logs del API Gateway
docker logs api-gateway -f

# Logs del servicio de autenticación
docker logs auth-service -f

# Logs del servicio de histórico (MITM detection)
docker logs historico-service -f

# Logs del servicio de reservas
docker logs reservas-service -f

# Logs del servicio receptor
docker logs receptor-service -f
```

Eventos clave en logs del Histórico Service:
- `MITM DETECTADO` — Inconsistencia de IP identificada
- `Validación exitosa` — Contexto IP validado correctamente
- `Session blacklisted` — Sesión comprometida invalidada
- `SECURITY` — Eventos de seguridad

Eventos clave en logs del Reservas Service:
- `CHECKSUM INVÁLIDO` — Posible manipulación de datos
- `Validación fallida` — Campos obligatorios faltantes
- `SECURITY` — Integridad verificada correctamente
- `Timeout checksum` — Sin respuesta del validador

## Comandos útiles

### Gestión de servicios

```bash
# Levantar todo
docker-compose up --build

# Levantar en background
docker-compose up -d --build

# Reiniciar un servicio específico
docker-compose restart historico-service

# Reconstruir solo un servicio
docker-compose up -d --no-deps --build api-gateway

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
docker exec -it api-gateway /bin/bash

# Ver logs desde un punto específico
docker logs historico-service --since 5m

# Ver métricas de Redis
docker exec redis redis-cli -p 6379 INFO stats

# Limpiar cache de Redis
docker exec redis redis-cli -p 6379 FLUSHDB
```

### Monitoreo y Métricas

```bash
# Métricas MITM
curl http://localhost:5003/metrics/mitm

# Métricas del Histórico Service
curl http://localhost:5003/metrics

# Métricas del Reservas Service
curl http://localhost:5004/metrics

# Estado del API Gateway
curl http://localhost:5000/health
```

## Estructura del proyecto

```
Experimento 2 - Seguridad/
│
├── docker-compose.yml                   # Orquestación de servicios
├── README.md                            # Este archivo
├── EXPERIMENTOS.md                      # Guía de ejecución de experimentos
├── experiment_1_mitm_detection.py      # Script de prueba MITM
├── experiment_2_data_integrity.py      # Script de prueba integridad
│
├── api_gateway/                         # API Gateway (Puerto 5000)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── middleware/
│       ├── routes/
│       └── services/
│
├── auth_service/                        # Servicio de Autenticación (Puerto 5001)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── models/
│       ├── routes/
│       └── services/
│
├── receptor_service/                    # Servicio Receptor (Puerto 5002)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── routes/
│       ├── services/
│       └── tasks/
│
├── historico_service/                   # Servicio de Histórico (Puerto 5003)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── utils.py
│       ├── models/
│       ├── routes/
│       └── services/
│           ├── historico_service.py
│           ├── mitm_detector.py
│           └── session_manager.py
│
├── reservas_service/                    # Servicio de Reservas (Puerto 5004)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── utils.py
│       ├── models/
│       ├── services/
│       │   ├── redis_service.py
│       │   └── validation_service.py
│       └── workers/
│           └── reserva_worker.py
│
├── verificador_service/                 # Servicio Verificador (Checksum)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── utils.py
│       ├── services/
│       └── workers/
│
├── db_init/                             # Inicialización de BD
│   └── init.sql
│
└── logs/                                # Logs persistentes
```

## Características implementadas

### Detección de MITM

**API Gateway:**
- Captura la dirección IP del cliente en cada solicitud
- Pasa la IP a través de headers seguros
- Integración con servicio de autenticación

**Auth Service:**
- Genera tokens JWT con IP del cliente embebida
- Algoritmo HS256 para firma segura
- Almacenamiento de tokens en Redis

**Histórico Service (MITMDetector):**
- Decodificación segura de tokens JWT
- Validación de contexto de IP
- Detección automática de inconsistencias
- Generación de información de detección

**Session Manager:**
- Gestión de blacklist de sesiones en Redis
- Invalidación de tokens comprometidos
- Registro de eventos de auditoría
- Estadísticas de MITM

### Validación de Integridad de Datos

**Receptor Service:**
- Genera checksum SHA256 de payloads
- Almacena auditoría en Redis
- Publica en cola de mensajería

**Reservas Service:**
- Lectura de colas de mensajería
- Validación de campos obligatorios
- Coordinación con checksum validator
- Respuesta final basada en validación

**Verificador Service (Checksum Validator):**
- Cálculo de checksum SHA256
- Comparación con valores originales
- Detección de manipulación de datos
- Reporte de resultados

### Infraestructura

- Docker Compose para orquestación
- PostgreSQL para almacenamiento persistente
- Redis para cache, colas y sesiones
- Logs persistentes en volumen
- Configuración por variables de entorno
- Health checks HTTP en todos los servicios

## Variables de Entorno

### Configuración General

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `SECRET_KEY` | `super-secret-key` | Clave para firmar JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo de firma |
| `DATABASE_URL` | `postgresql://...` | URL de PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/0` | URL de Redis |

### Histórico Service (Detección MITM)

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `SESSION_BLACKLIST_TTL` | `3600` | TTL de blacklist en segundos |
| `MITM_CHECK_ENABLED` | `true` | Habilitar detección MITM |

### Reservas Service (Validación de Integridad)

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `QUEUE_RESERVAS_REQUEST` | `reservas.request` | Cola de entrada de reservas |
| `QUEUE_RESERVAS_RESPONSE` | `reservas.response` | Cola de respuesta final |
| `QUEUE_CHECKSUM_REQUEST` | `reservas.checksum.request` | Cola para validación checksum |
| `QUEUE_CHECKSUM_RESPONSE` | `reservas.checksum.response` | Cola de respuesta checksum |
| `CHECKSUM_RESPONSE_TIMEOUT` | `10` | Timeout espera checksum (seg) |

## Contexto académico

**Curso:** MISW-4202 Arquitecturas Ágiles
**Universidad:** Universidad de los Andes
**Ciclo:** 3
**Equipo:** 17

**Objetivo del experimento:**
Demostrar un sistema de seguridad integral que detecta y mitiga dos clases de ataques:
1. **Ataques Man-in-the-Middle (MITM):** Mediante validación de contexto de IP embebida en tokens JWT
2. **Manipulación de Datos:** Mediante validación de checksums SHA256 en colas de mensajería

**Resultados esperados:**
- Detección automática de inconsistencias de contexto de autenticación
- Rechazo y bloqueo de sesiones comprometidas
- Identificación de intentos de manipulación de datos
- Auditoría completa de eventos de seguridad

## Referencias

- [JWT Authentication Best Practices](https://datatracker.ietf.org/doc/html/rfc7519)
- [OWASP Man-in-the-Middle Attacks](https://owasp.org/www-community/attacks/Manipulator-in-the-middle_attack)
- [Data Integrity Validation](https://en.wikipedia.org/wiki/Integrity_check)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Redis Documentation](https://redis.io/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## Equipo 17

Experimento de seguridad con detección MITM y validación de integridad
Arquitecturas Ágiles — Universidad de los Andes
2026


