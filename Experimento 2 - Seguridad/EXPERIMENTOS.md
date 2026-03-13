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

