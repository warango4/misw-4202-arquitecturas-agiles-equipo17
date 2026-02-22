"""
Python equivalent of test-carga-failover.ps1
Sends 200 requests in parallel blocks of 10, induces random failover,
collects per-request latency stats identical to the PowerShell script.
"""

import threading
import time
import random
import json
import statistics
import requests
from datetime import datetime

TOTAL_SOLICITUDES = 200
RECEPTOR   = "http://localhost:5000"
MONITOR    = "http://localhost:5003"
PRINCIPAL  = "http://localhost:5001"
BLOCK_SIZE = 10

print("=" * 42)
print("  PRUEBA DE CARGA CON FAILOVER ALEATORIO")
print(f"  {TOTAL_SOLICITUDES} solicitudes en paralelo")
print("=" * 42)
print()

# ── Verify services ───────────────────────────────────────────────
print("Verificando servicios...")
try:
    requests.get(f"{RECEPTOR}/health", timeout=5).raise_for_status()
    print("  Receptor activo")
except Exception as e:
    print(f"  Receptor no responde: {e}")
    exit(1)

try:
    requests.get(f"{MONITOR}/health", timeout=5).raise_for_status()
    print("  Monitor activo")
except Exception as e:
    print(f"  Monitor no responde: {e}")
    exit(1)

# ── Ensure principal is available ────────────────────────────────
print()
print("Preparando entorno...")
try:
    estado = requests.get(f"{MONITOR}/estado", timeout=5).json()
    if not estado.get("available"):
        print("  Servicio principal no disponible. Restaurando...")
        requests.post(f"{PRINCIPAL}/inducir-error", timeout=5)
        time.sleep(15)
        requests.post(f"{RECEPTOR}/limpiar-cache", timeout=5)
    print("  Servicio principal disponible")
except Exception as e:
    print(f"  No se pudo verificar estado del monitor: {e}")

# ── Test config ───────────────────────────────────────────────────
error_inducido_en = random.randint(15, 34)      # same range as PS: Minimum 15, Maximum 35
error_inducido    = threading.Event()
error_lock        = threading.Lock()

print()
print("Configuracion de la prueba:")
print(f"  Total de solicitudes: {TOTAL_SOLICITUDES}")
print(f"  Solicitudes en paralelo: {BLOCK_SIZE}")
print(f"  Error se inducira despues de: {error_inducido_en} solicitudes")
print()

metricas_iniciales = requests.get(f"{RECEPTOR}/metricas", timeout=5).json()

print("Iniciando envio de solicitudes...")
print()

# ── Per-request worker (mirrors the PS1 job ScriptBlock) ─────────
results = [None] * (TOTAL_SOLICITUDES + 1)   # 1-indexed

def worker(num):
    global error_inducido

    # Induce error exactly once at the designated request number
    with error_lock:
        should_induce = (not error_inducido.is_set()) and (num == error_inducido_en)
        if should_induce:
            error_inducido.set()

    if should_induce:
        print(f"    [Sol {num}] INDUCIENDO ERROR...")
        try:
            requests.post(f"{PRINCIPAL}/inducir-error", timeout=5)
            requests.post(f"{RECEPTOR}/limpiar-cache", timeout=5)
            time.sleep(3)
        except Exception:
            pass

    timestamp_envio = datetime.now()
    body = {
        "tipo": "crear_reserva",
        "datos": {
            "solicitud_num": num,
            "cliente_id": f"CLI-LOAD-{num}",
            "fecha": "2026-02-25",
            "servicio": "Hotel Load Test",
            "huespedes": 2,
            "timestamp": timestamp_envio.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        }
    }

    def send_and_poll():
        resp = requests.post(
            f"{RECEPTOR}/solicitud",
            json=body,
            timeout=10
        )
        resp.raise_for_status()
        ts_resp = datetime.now()
        data    = resp.json()
        sol_id  = data["solicitud_id"]
        instancia = data.get("instancia")

        # Poll for result (3 retries, 200ms initial + 300ms between)
        time.sleep(0.2)
        resultado = None
        for retry in range(3):
            try:
                r = requests.get(f"{RECEPTOR}/solicitud/{sol_id}", timeout=10)
                r.raise_for_status()
                resultado = r.json()
                if resultado.get("estado") != "pendiente":
                    break
            except Exception:
                pass
            if retry < 2:
                time.sleep(0.3)

        ts_final = datetime.now()
        return {
            "num":               num,
            "solicitud_id":      sol_id,
            "instancia":         instancia,
            "status":            "enviada",
            "timestamp_envio":   timestamp_envio,
            "timestamp_respuesta": ts_resp,
            "latencia_envio_ms": (ts_resp - timestamp_envio).total_seconds() * 1000,
            "estado_final":      resultado.get("estado") if resultado else "pendiente",
            "instancia_final":   resultado.get("instancia") if resultado else None,
            "timestamp_final":   ts_final,
            "latencia_total_ms": (ts_final - timestamp_envio).total_seconds() * 1000,
            "error":             None,
        }

    # First attempt
    try:
        results[num] = send_and_poll()
        return
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 500:
            # Retry after 3 s (mirrors PS1 500-error branch)
            time.sleep(3)
            try:
                results[num] = send_and_poll()
                return
            except Exception:
                pass
        # Fall through to error result
    except Exception:
        pass

    ts_err = datetime.now()
    results[num] = {
        "num":               num,
        "solicitud_id":      None,
        "instancia":         None,
        "status":            "error_envio",
        "timestamp_envio":   timestamp_envio,
        "timestamp_respuesta": ts_err,
        "latencia_envio_ms": (ts_err - timestamp_envio).total_seconds() * 1000,
        "estado_final":      "error_envio",
        "instancia_final":   None,
        "timestamp_final":   ts_err,
        "latencia_total_ms": (ts_err - timestamp_envio).total_seconds() * 1000,
        "error":             "send failed",
    }

# ── Send in blocks of 10 ─────────────────────────────────────────
start_time = datetime.now()

for block_start in range(1, TOTAL_SOLICITUDES + 1, BLOCK_SIZE):
    block_end = min(block_start + BLOCK_SIZE - 1, TOTAL_SOLICITUDES)
    print(f"  Enviando solicitudes {block_start}-{block_end}...")

    threads = [threading.Thread(target=worker, args=(n,))
               for n in range(block_start, block_end + 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if block_end < TOTAL_SOLICITUDES:
        time.sleep(0.5)

end_time  = datetime.now()
duration  = (end_time - start_time).total_seconds()
print()
print(f"  Todas las solicitudes enviadas en {duration:.2f} segundos")
print()

# ── Wait for pending ─────────────────────────────────────────────
print("Esperando procesamiento de solicitudes...")
print("  Las solicitudes se procesan en paralelo (concurrencia de 10 workers por instancia)...")
time.sleep(5)

print()
print("Verificando solicitudes pendientes...")

solicitudes = [r for r in results[1:] if r is not None]

for attempt in range(5):
    pending = [s for s in solicitudes if s["estado_final"] == "pendiente"]
    if not pending:
        break
    print(f"  Hay {len(pending)} solicitudes pendientes. Esperando 1 segundo mas...")
    time.sleep(1)
    for s in pending:
        try:
            r = requests.get(f"{RECEPTOR}/solicitud/{s['solicitud_id']}", timeout=10)
            res = r.json()
            ts_final = datetime.now()
            s["estado_final"]      = res.get("estado")
            s["instancia_final"]   = res.get("instancia")
            s["timestamp_final"]   = ts_final
            s["latencia_total_ms"] = (ts_final - s["timestamp_envio"]).total_seconds() * 1000
        except Exception:
            pass

print("  Consulta de resultados completada")
print()

# ── Restore principal ────────────────────────────────────────────
print()
print("Restaurando servicio principal...")
try:
    requests.post(f"{PRINCIPAL}/inducir-error", timeout=5)
    print("  Servicio restaurado")
except Exception:
    print("  No se pudo restaurar el servicio")

time.sleep(2)
metricas_finales = requests.get(f"{RECEPTOR}/metricas", timeout=5).json()

# ── Latency analysis (mirrors PS1 output exactly) ────────────────
print()
print("=" * 42)
print("  ANALISIS DE LATENCIAS")
print("=" * 42)
print()

por_principal   = [s for s in solicitudes if "principal"   in (s["instancia"] or "")]
por_redundancia = [s for s in solicitudes if "redundancia" in (s["instancia"] or "")]

print("Envio de Solicitudes:")
print(f"  Principal:   {len(por_principal)} solicitudes")
print(f"  Redundancia: {len(por_redundancia)} solicitudes")
print()

def latency_stats(group, label):
    lats = [s["latencia_total_ms"] for s in group if s.get("latencia_total_ms") is not None]
    if not lats:
        print(f"  {label}: No hay datos")
        return
    lats_sorted = sorted(lats)
    n = len(lats_sorted)
    p50 = lats_sorted[int(n * 0.50)]
    p95 = lats_sorted[int(n * 0.95)]
    print(f"  {label} ({len(group)} solicitudes):")
    print(f"    Min:  {min(lats):.2f} ms")
    print(f"    Avg:  {statistics.mean(lats):.2f} ms")
    print(f"    P50:  {p50:.2f} ms")
    print(f"    P95:  {p95:.2f} ms")
    print(f"    Max:  {max(lats):.2f} ms")
    return statistics.mean(lats)

print("Estadisticas de Latencia Total (envio + procesamiento):")
print()
avg_p = latency_stats(por_principal,   "Principal")
print()
avg_r = latency_stats(por_redundancia, "Redundancia")

if avg_p and avg_r:
    diff   = avg_r - avg_p
    pct    = (diff / avg_p) * 100
    print()
    print("  Comparacion:")
    if diff > 0:
        print(f"    Redundancia es {abs(diff):.2f} ms mas lenta")
        print(f"    Diferencia: +{abs(pct):.1f} porciento")
    else:
        print(f"    Redundancia es {abs(diff):.2f} ms mas rapida")
        print(f"    Diferencia: -{abs(pct):.1f} porciento")

top5 = sorted([s for s in solicitudes if s.get("latencia_total_ms")],
              key=lambda s: s["latencia_total_ms"], reverse=True)[:5]
if top5:
    print()
    print("  Top 5 solicitudes mas lentas:")
    for s in top5:
        print(f"    - Solicitud {s['num']:3d}: {s['latencia_total_ms']:.2f} ms ({s['instancia']})")

# ── Summary ───────────────────────────────────────────────────────
print()
print("=" * 42)
print("  RESUMEN DE RESULTADOS")
print("=" * 42)
print()

sol_principal   = [s for s in solicitudes if "principal"   in (s.get("instancia_final") or "")]
sol_redundancia = [s for s in solicitudes if "redundancia" in (s.get("instancia_final") or "")]

print("Procesamiento Final:")
print(f"  Enviadas a principal:   {len(sol_principal)}")
print(f"  Enviadas a redundancia: {len(sol_redundancia)}")
total_procesadas = len(sol_principal) + len(sol_redundancia)
print(f"  Total: {total_procesadas}")
print()

hubo_failover = len(sol_redundancia) > 0
if hubo_failover:
    print("  Failover detectado")
    if sol_principal:
        print("    - Algunas solicitudes fueron procesadas por el principal")
    print(f"    - Solicitudes redirigidas a redundancia: {len(sol_redundancia)}")
else:
    print("  No se detecto failover - todas las solicitudes fueron al principal")

print()

exitosas      = sum(1 for s in solicitudes if s["estado_final"] == "completada")
fallidas      = sum(1 for s in solicitudes if "error" in (s["estado_final"] or ""))
pendientes_f  = sum(1 for s in solicitudes if s["estado_final"] == "pendiente")
errores_envio = sum(1 for s in solicitudes if s["status"] == "error_envio")

print("Estados de Solicitudes:")
print(f"  Total registradas: {len(solicitudes)}")
print(f"  Completadas: {exitosas}")
print(f"  Fallidas:    {fallidas}")
print(f"  Pendientes:  {pendientes_f}")
if errores_envio:
    print(f"  Errores de envio: {errores_envio}")
    for s in solicitudes:
        if s["status"] == "error_envio":
            print(f"    - Solicitud {s['num']}: {s.get('error')}")
print()

sin_perdidas = (exitosas + fallidas + pendientes_f) == TOTAL_SOLICITUDES

print("Evaluacion del Sistema:")
if sin_perdidas:
    print(f"  [OK] Sin perdida de solicitudes ({TOTAL_SOLICITUDES}/{TOTAL_SOLICITUDES})")
else:
    print("  [ERROR] Perdida de solicitudes detectada")

if hubo_failover:
    print("  [OK] Failover automatico funcionando")
else:
    print("  [WARN] Failover no se ejecuto")

if exitosas >= 50:
    print(f"  [OK] Alta disponibilidad ({exitosas}/{TOTAL_SOLICITUDES} completadas)")
else:
    print(f"  [WARN] Baja disponibilidad ({exitosas}/{TOTAL_SOLICITUDES} completadas)")
print()

if sin_perdidas and hubo_failover and exitosas >= 50:
    print("  PRUEBA EXITOSA - El sistema manejo la carga con failover automatico")
    print(f"  El sistema manejo {TOTAL_SOLICITUDES} solicitudes concurrentes con failover automatico")
else:
    print("  Revisa los resultados - puede haber problemas en el sistema")

print()
print("=" * 42)
