# Experimentos de Seguridad - TravelHub

Guía completa para ejecutar los dos experimentos de seguridad del sistema de reservas TravelHub.

---

## Requisitos Previos

Antes de empezar, asegúrate de tener instalado:

- **Python 3.11+** — comprueba con `python --version`
- **Docker Desktop** — comprueba con `docker --version`
- **Git** (opcional, si clonas el repositorio)

---

## 1. Activar el Ambiente Virtual

### En Windows (PowerShell):

```powershell
# Crear el ambiente virtual (primera vez)
python -m venv venv

# Activar el ambiente
.\venv\Scripts\Activate.ps1
```

Si obtienes un error de permisos, ejecuta PowerShell como administrador o usa:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### En macOS/Linux:

```bash
# Crear el ambiente virtual (primera vez)
python3 -m venv venv

# Activar el ambiente
source venv/bin/activate
```

---

## 2. Instalar Dependencias

Con el ambiente virtual activado, instala los paquetes necesarios:

```powershell
pip install --upgrade pip
pip install requests pytz
```

Verifica la instalación:

```powershell
pip list
```

Deberías ver:
- `requests` (versión 2.31+)
- `pytz`

---

## 3. Levantar los Servicios con Docker

### Iniciar Docker Compose:

```powershell
# Posicionarse en la carpeta del experimento
cd "Experimento 2 - Seguridad"

# Levantar los contenedores
docker-compose up -d

# Verificar que los servicios estén corriendo
docker-compose ps
```

Deberías ver 6 servicios en estado `running`:
- `postgres` (puerto 5432)
- `redis` (puerto 6379)
- `api_gateway` (puerto 5000)
- `auth_service` (puerto 5001)
- `receptor_service` (puerto 5002)
- `historico_service` (puerto 5003)
- `reservas_service` (puerto 5004)
- `verificador_service` (puerto 5005)

### Esperar a que los servicios estén listos:

```powershell
# Ver logs de un servicio específico
docker-compose logs -f api_gateway

# Cuando veas "Running on http://0.0.0.0:5000", está listo
```

---

## 4. Ejecutar los Experimentos

### Experimento 1: Detección de Ataques MITM

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

#### Ayuda:

```powershell
python experiment_1_mitm_detection.py --help
```

#### Salida esperada:

```
================================================================================
EXPERIMENTO 1: DETECCIÓN DE ATAQUES MITM
================================================================================

Parámetros:
  • Total de requests: 300
  • Requests legítimas: 150
  • Ataques MITM: 150
  • Porcentaje MITM: 50%
  • URL API Gateway: http://localhost:5000
  • IP Original: 127.0.0.1
  • Tokens independientes: 5

...

EVALUACIÓN DE HIPÓTESIS
================================================================================
HIPOTESIS CONFIRMADA: El sistema detecta el 100% de ataques MITM

Resultados guardados en: experiment_1_results_20260312_201838.json
```

---

### Experimento 2: Detección de Manipulación de Datos (Data Integrity)

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

#### Ayuda:

```powershell
python experiment_2_data_integrity.py --help
```

#### Salida esperada:

```
================================================================================
EXPERIMENTO 2: DETECCIÓN DE MANIPULACIÓN DE DATOS (DATA INTEGRITY)
================================================================================

Parámetros:
  • Total de requests: 300
  • Requests legítimas: 150
  • Ataques de manipulación: 150
  • Porcentaje de manipulación: 50%
  • URL API Gateway: http://localhost:5000

...

ESTADÍSTICAS GENERALES:
  Total de requests exitosas: 300
  Total de requests fallidas: 0
  Tiempo de respuesta promedio: 0.021s

EVALUACIÓN DE HIPÓTESIS
================================================================================
HIPOTESIS CONFIRMADA: El sistema detecta el 100% de manipulaciones de datos

Resultados guardados en: experiment_2_results_20260312_201838.json
```

---

## 5. Analizar Resultados

Los resultados de cada experimento se guardan en archivos JSON con timestamp:

```
experiment_1_results_20260312_201838.json
experiment_2_results_20260312_201838.json
```

### Estructura de los resultados:

```json
{
  "legitimate_requests": [...],
  "tampering_requests": [...],  // o "mitm_requests" en experimento 1
  "statistics": {
    "total_requests": 300,
    "execution_time": 36.73,
    "requests_per_second": 8.17,
    "legitimate": {
      "total": 150,
      "successful": 150,
      "failed": 0,
      "success_rate": 100.0,
      ...
    },
    "tampering": {  // o "mitm" en experimento 1
      "total": 150,
      "correctly_detected": 150,
      "not_detected": 0,
      "detection_rate": 100.0,
      ...
    }
  }
}
```

---

## 6. Detener los Servicios

Cuando termines:

```powershell
# Detener y eliminar los contenedores
docker-compose down

# Si también quieres limpiar volúmenes (base de datos)
docker-compose down -v

# Ver logs históricos
docker-compose logs --tail=100
```

---

## 7. Solución de Problemas

### Error: "Connection refused"
**Causa:** Los servicios no están corriendo.  
**Solución:**
```powershell
docker-compose ps
```
Si no ves los servicios corriendo, usa `docker-compose up -d` nuevamente.

### Error: "ModuleNotFoundError: No module named 'requests'"
**Causa:** Las dependencias no están instaladas.  
**Solución:**
```powershell
pip install requests pytz
```

### Error: "Port 5000 already in use"
**Causa:** Otro proceso usa el puerto.  
**Solución:**
```powershell
# Liberar el puerto (o reiniciar Docker)
docker-compose down
docker-compose up -d
```

### Error: "Service postgres is not healthy"
**Causa:** La base de datos está iniciando.  
**Solución:** Espera 30 segundos y vuelve a intentar.

---

## 8. Flujo Completo de Ejecución

```powershell
# 1. Activar ambiente virtual
.\venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install requests pytz

# 3. Navegar a la carpeta del experimento
cd "Experimento 2 - Seguridad"

# 4. Levantar Docker
docker-compose up -d

# 5. Esperar a que los servicios estén listos (30-60 segundos)
docker-compose logs -f api_gateway
# (cuando veas "Running on http://0.0.0.0:5000", presiona Ctrl+C)

# 6. Ejecutar Experimento 1
python experiment_1_mitm_detection.py --total-requests 300 --mitm-percentage 50

# 7. Ejecutar Experimento 2
python experiment_2_data_integrity.py --total-requests 300 --tampering-percentage 50

# 8. Revisar resultados en los archivos JSON generados

# 9. Detener servicios
docker-compose down
```

---

## 9. Parámetros por Defecto

### Experimento 1:
- `--total-requests`: 100 (total de requests)
- `--mitm-percentage`: 30 (% MITM, rango 0-100)
- `--api-gateway`: http://localhost:5000
- `--num-tokens`: 5 (número de tokens independientes)

### Experimento 2:
- `--total-requests`: 100 (total de requests)
- `--tampering-percentage`: 30 (% manipuladas, rango 0-100)
- `--api-gateway`: http://localhost:5000

---

## 10. Más Información

- **Experimento 1 (MITM):** Detecta cambios de IP entre autenticación y uso del token
- **Experimento 2 (Data Integrity):** Detecta alteración de payloads mediante SHA256

Ambos experimentos generan reportes detallados en consola y resultados completos en JSON.

---

**Última actualización:** 12 de marzo de 2026  
**Versión:** 2.0
