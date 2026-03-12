# Experimento de Seguridad — Equipo 17

## Conformación de equipo

| Nombres         | Email Uniandes                | Usuario GitHub |
|-----------------|-------------------------------|----------------|
| Wendy Arango    | w.arangoc@uniandes.edu.co    | warango4       |
| Andrés Echeverry| a.echeverryb@uniandes.edu.co | afecheverryb10 |
| Juan Vega       | js.vega1@uniandes.edu.co     | jsebasvegag    |
| Julio Urian     | j.urianv@uniandes.edu.co     | jurianvilla    |

---

## Descripción del Experimento

Este experimento valida una **hipótesis de seguridad** enfocada en la detección de ataques **Man-in-the-Middle (MITM)**. El sistema implementa un mecanismo de validación de contexto de autenticación basado en la dirección IP del cliente.

### Hipótesis de Seguridad

> *"Si un atacante intercepta un token JWT válido y lo utiliza desde una dirección IP diferente a la que se usó durante la autenticación original, el sistema debe ser capaz de detectar esta inconsistencia y rechazar la solicitud, invalidando la sesión comprometida."*

---

## Arquitectura del Experimento

### Servicios

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| API Gateway | 5000 | Punto de entrada único, valida tokens y reenvía la IP del cliente |
| Auth Service | 5001 | Genera tokens JWT con la IP del cliente embebida |
| Receptor Service | 5002 | Recibe reservas, genera checksum y encola |
| **Historico Service** | **5003** | **Consulta de histórico con detección MITM** |
| **Reservas Service** | **5004** | **Procesa reservas y coordina validación de checksum** |
| PostgreSQL | 5432 | Base de datos |
| Redis | 6379 | Cache, colas de mensajería y sesiones blacklisteadas |

### Flujo de Detección MITM

```
┌─────────┐      ┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│ Cliente │─────>│ API Gateway │─────>│ Auth Service │─────>│    Token JWT    │
│ IP: A   │      │ Captura IP  │      │ Genera JWT   │      │ client_ip: A    │
└─────────┘      └─────────────┘      └──────────────┘      │ jti: uuid       │
                                                            └─────────────────┘
                                                                    │
                                                                    ▼
┌─────────┐      ┌─────────────┐      ┌──────────────────┐   (Ataque MITM)
│Atacante │─────>│ API Gateway │─────>│ Historico Service│
│ IP: B   │      │ IP: B       │      │                  │
│Token(A) │      │ Token(A)    │      │ Valida:          │
└─────────┘      └─────────────┘      │ token_ip=A ≠ B   │
                                      │ *** MITM ***     │
                                      │ Sesión invalidada│
                                      └──────────────────┘
```

---

## Detección MITM - Servicio de Histórico

### Funcionalidad

El `historico_service` implementa:

1. **Validación de contexto IP**: Compara la IP almacenada en el token con la IP de la solicitud actual
2. **Invalidación de sesión**: Al detectar MITM, invalida el token y todas las sesiones del usuario
3. **Logging y métricas**: Registra todos los eventos de seguridad para análisis

### Logs y Trazas Relevantes

| Nivel | Tipo | Descripción |
|-------|------|-------------|
| `CRITICAL` | MITM DETECTADO | Inconsistencia de IP detectada |
| `CRITICAL` | AUDIT | Evento MITM registrado para auditoría |
| `WARN` | SECURITY | Detalle del ataque (IP original vs IP atacante) |
| `WARN` | Session blacklisted | Intento de uso de sesión invalidada |
| `INFO` | METRIC | Duración de request y resultado |
| `INFO` | Validación exitosa | Contexto IP validado correctamente |

### Métricas para Evaluación de Hipótesis

El endpoint `/metrics/mitm` proporciona:
- Total de detecciones MITM
- Eventos recientes con detalles
- Información para dashboards de seguridad

---

## Validación de Integridad - Servicio de Reservas

### Hipótesis de Seguridad (Checksum)

> *"Si los datos de una reserva son manipulados durante su tránsito por las colas de mensajería, el sistema debe detectar la inconsistencia mediante validación de checksum y rechazar la operación."*

### Flujo de Validación de Checksum

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE VALIDACIÓN DE INTEGRIDAD                        │
└─────────────────────────────────────────────────────────────────────────────┘

1. Cliente envía reserva
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Receptor Service                                                          │
│    ├── Genera checksum inicial (SHA256)                                     │
│    ├── Guarda auditoría en Redis                                            │
│    └── Publica en cola: reservas.request                                    │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. Reservas Service (NUEVO)                                                  │
│    ├── Lee de cola: reservas.request                                        │
│    ├── Valida campos obligatorios (checkin, checkout, destino, valor)       │
│    ├── Si inválido → Responde error en reservas.response                    │
│    └── Si válido → Publica en cola: reservas.checksum.request               │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. Checksum Validator (PENDIENTE)                                            │
│    ├── Lee de cola: reservas.checksum.request                               │
│    ├── Recalcula checksum del payload                                       │
│    ├── Compara con checksum original (en auditoría)                         │
│    └── Publica resultado en: reservas.checksum.response                     │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. Reservas Service                                                          │
│    ├── Lee respuesta de: reservas.checksum.response                         │
│    ├── Si checksum válido → Confirma reserva                                │
│    ├── Si checksum inválido → RECHAZA operación                             │
│    └── Publica resultado final en: reservas.response                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Colas de Mensajería

| Cola | Publicador | Consumidor | Descripción |
|------|------------|------------|-------------|
| `reservas.request` | Receptor Service | Reservas Service | Solicitudes de reserva |
| `reservas.response` | Reservas Service | Receptor Service | Resultado final |
| `reservas.checksum.request` | Reservas Service | Checksum Validator | Solicitud de validación |
| `reservas.checksum.response` | Checksum Validator | Reservas Service | Resultado de validación |

### Funcionalidad del Reservas Service

1. **Lectura de cola**: Escucha `reservas.request` para nuevas solicitudes
2. **Validación de campos**: Verifica campos obligatorios no nulos
3. **Coordinación de checksum**: Envía a validador y espera respuesta
4. **Respuesta final**: Publica resultado en `reservas.response`

### Logs y Trazas del Servicio de Reservas

| Nivel | Tipo | Descripción |
|-------|------|-------------|
| `CRITICAL` | CHECKSUM INVÁLIDO | Posible manipulación de datos detectada |
| `ERROR` | Validación fallida | Campos obligatorios faltantes o inválidos |
| `WARN` | Timeout checksum | Sin respuesta del validador |
| `INFO` | METRIC | Duración de procesamiento y resultado |
| `INFO` | SECURITY | Integridad verificada correctamente |

---

## Ejecución del Experimento

### Iniciar los servicios

```bash
cd "Experimento 2 - Seguridad"
docker-compose up --build
```

### Caso 1: Solicitud Legítima

```bash
# 1. Obtener token (IP se vincula al token)
TOKEN=$(curl -s -X POST http://localhost:5000/token \
  -d "grant_type=client_credentials" \
  -d "client_id=admin" \
  -d "client_secret=admin" | jq -r '.access_token')

# 2. Consultar histórico (misma IP)
curl -X POST http://localhost:5000/historico \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Resultado esperado**: Respuesta exitosa con el histórico de reservas.

### Caso 2: Simulación de Ataque MITM

Para simular un ataque MITM, se puede enviar una solicitud con un header `X-Forwarded-For` diferente:

```bash
# Solicitud desde IP diferente (simula atacante)
curl -X POST http://localhost:5000/historico \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Forwarded-For: 192.168.1.100" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Resultado esperado**:
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

### Verificar Métricas MITM

```bash
curl http://localhost:5003/metrics/mitm
```

---

## Estructura del Servicio de Histórico

```
historico_service/
├── __init__.py
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── config.py
    ├── main.py
    ├── utils.py
    ├── models/
    │   ├── __init__.py
    │   └── database.py
    ├── routes/
    │   ├── __init__.py
    │   └── historico.py
    └── services/
        ├── __init__.py
        ├── historico_service.py
        ├── mitm_detector.py
        └── session_manager.py
```

## Estructura del Servicio de Reservas

```
reservas_service/
├── __init__.py
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── config.py
    ├── main.py
    ├── utils.py
    ├── services/
    │   ├── __init__.py
    │   ├── redis_service.py
    │   └── validation_service.py
    └── workers/
        ├── __init__.py
        └── reserva_worker.py
```

---

## Componentes de Seguridad

### MITMDetector (`mitm_detector.py`)
- Decodifica tokens JWT
- Valida contexto de IP
- Genera información de detección

### SessionManager (`session_manager.py`)
- Gestiona blacklist de sesiones en Redis
- Invalida tokens comprometidos
- Registra eventos de auditoría
- Proporciona estadísticas de MITM

---

## Variables de Entorno

### Generales

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `SECRET_KEY` | `super-secret-key` | Clave para firmar JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo de firma |
| `DATABASE_URL` | `postgresql://...` | URL de PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/0` | URL de Redis |

### Historico Service

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `SESSION_BLACKLIST_TTL` | `3600` | TTL de blacklist (segundos) |

### Reservas Service

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `QUEUE_RESERVAS_REQUEST` | `reservas.request` | Cola de entrada de reservas |
| `QUEUE_RESERVAS_RESPONSE` | `reservas.response` | Cola de respuesta final |
| `QUEUE_CHECKSUM_REQUEST` | `reservas.checksum.request` | Cola para validación checksum |
| `QUEUE_CHECKSUM_RESPONSE` | `reservas.checksum.response` | Cola de respuesta checksum |
| `CHECKSUM_RESPONSE_TIMEOUT` | `10` | Timeout espera checksum (seg) |


