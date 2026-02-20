# Script de prueba de carga con failover aleatorio
# Envía 60 solicitudes en paralelo e induce error durante el proceso
# Ejecutar: .\test-carga-failover.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PRUEBA DE CARGA CON FAILOVER ALEATORIO" -ForegroundColor Cyan
Write-Host "  60 solicitudes en paralelo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$RECEPTOR = "http://localhost:5000"
$MONITOR = "http://localhost:5003"
$PRINCIPAL = "http://localhost:5001"

# Verificar que los servicios están activos
Write-Host "Verificando servicios..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$RECEPTOR/health" -Method Get -ErrorAction Stop
    Write-Host "  Receptor activo" -ForegroundColor Green
} catch {
    Write-Host "  Receptor no responde. Asegurate de ejecutar 'docker-compose up' primero." -ForegroundColor Red
    exit 1
}

try {
    $monitor = Invoke-RestMethod -Uri "$MONITOR/health" -Method Get -ErrorAction Stop
    Write-Host "  Monitor activo" -ForegroundColor Green
} catch {
    Write-Host "  Monitor no responde" -ForegroundColor Red
    exit 1
}

# Limpiar metricas anteriores (opcional)
Write-Host ""
Write-Host "Preparando entorno..." -ForegroundColor Yellow

# Asegurar que el servicio principal esta activo
try {
    $estado = Invoke-RestMethod -Uri "$MONITOR/estado" -Method Get
    if (-not $estado.available) {
        Write-Host "  Servicio principal no disponible. Restaurando..." -ForegroundColor Yellow
        Invoke-RestMethod -Uri "$PRINCIPAL/inducir-error" -Method Post | Out-Null
        Start-Sleep -Seconds 15
        Invoke-RestMethod -Uri "$RECEPTOR/limpiar-cache" -Method Post | Out-Null
    }
    Write-Host "  Servicio principal disponible" -ForegroundColor Green
} catch {
    Write-Host "  No se pudo verificar estado del monitor" -ForegroundColor Yellow
}

# Variables para tracking
$solicitudes = New-Object System.Collections.ArrayList
$errorInducidoEn = Get-Random -Minimum 15 -Maximum 35
$errorInducido = $false

Write-Host ""
Write-Host "Configuracion de la prueba:" -ForegroundColor Yellow
Write-Host "  Total de solicitudes: 60" -ForegroundColor Cyan
Write-Host "  Solicitudes en paralelo: 10" -ForegroundColor Cyan
Write-Host "  Error se inducira despues de: $errorInducidoEn solicitudes" -ForegroundColor Cyan
Write-Host ""

# Obtener metricas iniciales
$metricasIniciales = Invoke-RestMethod -Uri "$RECEPTOR/metricas" -Method Get

Write-Host "Iniciando envio de solicitudes..." -ForegroundColor Yellow
Write-Host ""

$startTime = Get-Date

# Enviar 60 solicitudes en bloques de 10 en paralelo
for ($i = 1; $i -le 60; $i += 10) {
    $bloque = $i
    $hasta = [Math]::Min($i + 9, 60)
    
    Write-Host "  Enviando solicitudes $bloque-$hasta..." -ForegroundColor Gray
    
    # Enviar bloque de solicitudes en paralelo
    $bloque_actual = $bloque
    $receptor_url = $RECEPTOR
    $errorNum = $errorInducidoEn
    $errorInducidoRef = $errorInducido
    $jobs = $bloque_actual..($hasta) | ForEach-Object {
        Start-Job -ScriptBlock {
            param($num, $receptor, $principal, $errorNum, $errorInducidoRef)
            
            # Verificar si esta solicitud debe inducir el error
            if (-not $errorInducidoRef -and $num -eq $errorNum) {
                Write-Host "    [Sol $num] INDUCIENDO ERROR..." -ForegroundColor Yellow
                try {
                    Invoke-RestMethod -Uri "$principal/inducir-error" -Method Post | Out-Null
                    Invoke-RestMethod -Uri "$receptor/limpiar-cache" -Method Post | Out-Null
                    Start-Sleep -Seconds 3
                } catch {
                    # Silenciar errores
                }
            }
            
            $timestampEnvio = Get-Date
            
            $body = @{
                tipo = "crear_reserva"
                datos = @{
                    solicitud_num = $num
                    cliente_id = "CLI-LOAD-$num"
                    fecha = "2026-02-25"
                    servicio = "Hotel Load Test"
                    huespedes = 2
                    timestamp = $timestampEnvio.ToString("yyyy-MM-dd HH:mm:ss.fff")
                }
            } | ConvertTo-Json
            
            try {
                $response = Invoke-RestMethod -Uri "$receptor/solicitud" -Method Post -Body $body -ContentType "application/json" -ErrorAction Stop
                $timestampRespuesta = Get-Date
                
                # Esperar y consultar el resultado con reintentos
                Start-Sleep -Milliseconds 200
                
                $resultado = $null
                $maxRetries = 3
                for ($retry = 0; $retry -lt $maxRetries; $retry++) {
                    try {
                        $resultado = Invoke-RestMethod -Uri "$receptor/solicitud/$($response.solicitud_id)" -Method Get -ErrorAction Stop
                        if ($resultado.estado -ne "pendiente") {
                            break
                        }
                        if ($retry -lt $maxRetries - 1) {
                            Start-Sleep -Milliseconds 300
                        }
                    } catch {
                        if ($retry -eq $maxRetries - 1) {
                            throw
                        }
                        Start-Sleep -Milliseconds 300
                    }
                }
                
                $timestampFinal = Get-Date
                
                if ($resultado) {
                    return @{
                        num = $num
                        solicitud_id = $response.solicitud_id
                        instancia = $response.instancia
                        status = "enviada"
                        timestamp_envio = $timestampEnvio
                        timestamp_respuesta = $timestampRespuesta
                        latencia_envio_ms = ($timestampRespuesta - $timestampEnvio).TotalMilliseconds
                        estado_final = $resultado.estado
                        instancia_final = $resultado.instancia
                        timestamp_final = $timestampFinal
                        latencia_total_ms = ($timestampFinal - $timestampEnvio).TotalMilliseconds
                        error = $null
                    }
                } else {
                    return @{
                        num = $num
                        solicitud_id = $response.solicitud_id
                        instancia = $response.instancia
                        status = "enviada"
                        timestamp_envio = $timestampEnvio
                        timestamp_respuesta = $timestampRespuesta
                        latencia_envio_ms = ($timestampRespuesta - $timestampEnvio).TotalMilliseconds
                        estado_final = "pendiente"
                        error = $null
                    }
                }
            } catch {
                $timestampError = Get-Date
                
                # Si es error 500 (servicio cayéndose), reintentar después de 3 segundos
                if ($_.Exception.Message -like "*500*") {
                    Start-Sleep -Seconds 3
                    try {
                        # El retry comienza aquí - nueva medición de tiempo
                        $timestampRetry = Get-Date
                        $response = Invoke-RestMethod -Uri "$receptor/solicitud" -Method Post -Body $body -ContentType "application/json" -ErrorAction Stop
                        $timestampRespuesta = Get-Date
                        
                        # Continuar con el flujo normal de consulta
                        Start-Sleep -Milliseconds 200
                        
                        $resultado = $null
                        $maxRetries = 3
                        for ($retry = 0; $retry -lt $maxRetries; $retry++) {
                            try {
                                $resultado = Invoke-RestMethod -Uri "$receptor/solicitud/$($response.solicitud_id)" -Method Get -ErrorAction Stop
                                if ($resultado.estado -ne "pendiente") {
                                    break
                                }
                                if ($retry -lt $maxRetries - 1) {
                                    Start-Sleep -Milliseconds 300
                                }
                            } catch {
                                if ($retry -eq $maxRetries - 1) {
                                    throw
                                }
                                Start-Sleep -Milliseconds 300
                            }
                        }
                        
                        $timestampFinal = Get-Date
                        
                        if ($resultado) {
                            return @{
                                num = $num
                                solicitud_id = $response.solicitud_id
                                instancia = $response.instancia
                                status = "enviada"
                                timestamp_envio = $timestampRetry
                                timestamp_respuesta = $timestampRespuesta
                                latencia_envio_ms = ($timestampRespuesta - $timestampRetry).TotalMilliseconds
                                estado_final = $resultado.estado
                                instancia_final = $resultado.instancia
                                timestamp_final = $timestampFinal
                                latencia_total_ms = ($timestampFinal - $timestampRetry).TotalMilliseconds
                                error = $null
                            }
                        }
                    } catch {
                        # Si el reintento también falla, registrar el error
                    }
                }
                
                return @{
                    num = $num
                    solicitud_id = $null
                    instancia = $null
                    status = "error_envio"
                    timestamp_envio = $timestampEnvio
                    timestamp_respuesta = $timestampError
                    latencia_envio_ms = ($timestampError - $timestampEnvio).TotalMilliseconds
                    error = $_.Exception.Message
                }
            }
        } -ArgumentList $_, $receptor_url, $PRINCIPAL, $errorNum, $errorInducidoRef
    }
    
    # Verificar si el error fue inducido en este bloque
    if (-not $errorInducido -and $hasta -ge $errorInducidoEn) {
        $errorInducido = $true
    }
    
    # Esperar que terminen los jobs del bloque
    $results = $jobs | Wait-Job | Receive-Job
    $jobs | Remove-Job
    
    # Guardar resultados
    foreach ($result in $results) {
        [void]$solicitudes.Add([PSCustomObject]$result)
    }
    
    # Pequena pausa entre bloques para no saturar
    if ($hasta -lt 60) {
        Start-Sleep -Milliseconds 500
    }
}

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

Write-Host ""
$duracionStr = [Math]::Round($duration, 2)
Write-Host "  Todas las solicitudes enviadas en ${duracionStr} segundos" -ForegroundColor Green
Write-Host ""

# Esperar a que se procesen las solicitudes
Write-Host "Esperando procesamiento de solicitudes..." -ForegroundColor Yellow
Write-Host "  Las solicitudes se procesan en paralelo (concurrencia de 10 workers por instancia)..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Variables para seguimiento
$intentos = 0
$maxIntentos = 5

Write-Host ""
Write-Host "Verificando solicitudes pendientes..." -ForegroundColor Yellow

# Solo reconsultar las pendientes
$pendientes = ($solicitudes | Where-Object { $_.estado_final -eq "pendiente" }).Count
while ($pendientes -gt 0 -and $intentos -lt $maxIntentos) {
    Write-Host "  Hay $pendientes solicitudes pendientes. Esperando 1 segundo mas..." -ForegroundColor Yellow
    Start-Sleep -Seconds 1
    $intentos++
    
    # Consultar nuevamente las pendientes
    foreach ($sol in ($solicitudes | Where-Object { $_.estado_final -eq "pendiente" })) {
        try {
            $resultado = Invoke-RestMethod -Uri "$RECEPTOR/solicitud/$($sol.solicitud_id)" -Method Get -ErrorAction Stop
            $timestampFinal = Get-Date
            
            $sol.estado_final = $resultado.estado
            $sol.instancia_final = $resultado.instancia
            $sol.timestamp_final = $timestampFinal
            $sol.latencia_total_ms = ($timestampFinal - $sol.timestamp_envio).TotalMilliseconds
        } catch {
            # Mantener como pendiente
        }
    }
    
    $pendientes = ($solicitudes | Where-Object { $_.estado_final -eq "pendiente" }).Count
}

Write-Host "  Consulta de resultados completada" -ForegroundColor Green
Write-Host ""

# Restaurar servicio principal
Write-Host ""
Write-Host "Restaurando servicio principal..." -ForegroundColor Yellow
try {
    Invoke-RestMethod -Uri "$PRINCIPAL/inducir-error" -Method Post | Out-Null
    Write-Host "  Servicio restaurado" -ForegroundColor Green
} catch {
    Write-Host "  No se pudo restaurar el servicio" -ForegroundColor Yellow
}

# Obtener metricas finales
Start-Sleep -Seconds 2
$metricasFinales = Invoke-RestMethod -Uri "$RECEPTOR/metricas" -Method Get

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ANALISIS DE LATENCIAS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Separar por instancia (basado en la primera respuesta)
$porPrincipal = ($solicitudes | Where-Object { $_.instancia -like "*principal*" }).Count
$porRedundancia = ($solicitudes | Where-Object { $_.instancia -like "*redundancia*" }).Count

Write-Host "Envio de Solicitudes:" -ForegroundColor White
Write-Host "  Principal: $porPrincipal solicitudes" -ForegroundColor Cyan
Write-Host "  Redundancia: $porRedundancia solicitudes" -ForegroundColor Cyan
Write-Host ""

# Calcular estadisticas de latencia por instancia
$latenciasPrincipal = ($solicitudes | Where-Object { $_.instancia -like "*principal*" -and $_.latencia_total_ms -ne $null }).latencia_total_ms
$latenciasRedundancia = ($solicitudes | Where-Object { $_.instancia -like "*redundancia*" -and $_.latencia_total_ms -ne $null }).latencia_total_ms

Write-Host "Estadisticas de Latencia Total (envio + procesamiento):" -ForegroundColor White
Write-Host ""

if ($latenciasPrincipal.Count -gt 0) {
    $latenciaPrincipalMin = ($latenciasPrincipal | Measure-Object -Minimum).Minimum
    $latenciaPrincipalMax = ($latenciasPrincipal | Measure-Object -Maximum).Maximum
    $latenciaPrincipalAvg = ($latenciasPrincipal | Measure-Object -Average).Average
    $latenciaPrincipalP50 = ($latenciasPrincipal | Sort-Object)[[Math]::Floor($latenciasPrincipal.Count * 0.5)]
    $latenciaPrincipalP95 = ($latenciasPrincipal | Sort-Object)[[Math]::Floor($latenciasPrincipal.Count * 0.95)]
    
    $numSolicitudesPrincipal = $porPrincipal
    $minStr = [Math]::Round($latenciaPrincipalMin, 2)
    $avgStr = [Math]::Round($latenciaPrincipalAvg, 2)
    $p50Str = [Math]::Round($latenciaPrincipalP50, 2)
    $p95Str = [Math]::Round($latenciaPrincipalP95, 2)
    $maxStr = [Math]::Round($latenciaPrincipalMax, 2)
    
    Write-Host "  Principal (${numSolicitudesPrincipal} solicitudes):" -ForegroundColor Cyan
    Write-Host "    Min:  ${minStr} ms" -ForegroundColor Gray
    Write-Host "    Avg:  ${avgStr} ms" -ForegroundColor Gray
    Write-Host "    P50:  ${p50Str} ms" -ForegroundColor Gray
    Write-Host "    P95:  ${p95Str} ms" -ForegroundColor Gray
    Write-Host "    Max:  ${maxStr} ms" -ForegroundColor Gray
} else {
    Write-Host "  Principal: No hay datos" -ForegroundColor Gray
}

Write-Host ""

if ($latenciasRedundancia.Count -gt 0) {
    $latenciaRedundanciaMin = ($latenciasRedundancia | Measure-Object -Minimum).Minimum
    $latenciaRedundanciaMax = ($latenciasRedundancia | Measure-Object -Maximum).Maximum
    $latenciaRedundanciaAvg = ($latenciasRedundancia | Measure-Object -Average).Average
    $latenciaRedundanciaP50 = ($latenciasRedundancia | Sort-Object)[[Math]::Floor($latenciasRedundancia.Count * 0.5)]
    $latenciaRedundanciaP95 = ($latenciasRedundancia | Sort-Object)[[Math]::Floor($latenciasRedundancia.Count * 0.95)]
    
    $numSolicitudesRedundancia = $porRedundancia
    $minStr = [Math]::Round($latenciaRedundanciaMin, 2)
    $avgStr = [Math]::Round($latenciaRedundanciaAvg, 2)
    $p50Str = [Math]::Round($latenciaRedundanciaP50, 2)
    $p95Str = [Math]::Round($latenciaRedundanciaP95, 2)
    $maxStr = [Math]::Round($latenciaRedundanciaMax, 2)
    
    Write-Host "  Redundancia (${numSolicitudesRedundancia} solicitudes):" -ForegroundColor Cyan
    Write-Host "    Min:  ${minStr} ms" -ForegroundColor Gray
    Write-Host "    Avg:  ${avgStr} ms" -ForegroundColor Gray
    Write-Host "    P50:  ${p50Str} ms" -ForegroundColor Gray
    Write-Host "    P95:  ${p95Str} ms" -ForegroundColor Gray
    Write-Host "    Max:  ${maxStr} ms" -ForegroundColor Gray
} else {
    Write-Host "  Redundancia: No hay datos" -ForegroundColor Gray
}

# Comparacion de latencias
if ($latenciasPrincipal.Count -gt 0 -and $latenciasRedundancia.Count -gt 0) {
    $diferencia = $latenciaRedundanciaAvg - $latenciaPrincipalAvg
    $porcentajeDif = ($diferencia / $latenciaPrincipalAvg) * 100
    
    Write-Host ""
    Write-Host "  Comparacion:" -ForegroundColor Cyan
    if ($diferencia -gt 0) {
        $difMs = [Math]::Round([Math]::Abs($diferencia), 2)
        $difPct = [Math]::Round([Math]::Abs($porcentajeDif), 1)
        Write-Host "    Redundancia es ${difMs} ms mas lenta" -ForegroundColor Yellow
        Write-Host "    Diferencia: +${difPct} porciento" -ForegroundColor Yellow
    } else {
        $difMs = [Math]::Round([Math]::Abs($diferencia), 2)
        $difPct = [Math]::Round([Math]::Abs($porcentajeDif), 1)
        Write-Host "    Redundancia es ${difMs} ms mas rapida" -ForegroundColor Green
        Write-Host "    Diferencia: -${difPct} porciento" -ForegroundColor Green
    }
}

# Top 5 solicitudes mas lentas
$top5Lentas = $solicitudes | Where-Object { $_.latencia_total_ms -ne $null } | Sort-Object latencia_total_ms -Descending | Select-Object -First 5
if ($top5Lentas.Count -gt 0) {
    Write-Host ""
    Write-Host "  Top 5 solicitudes mas lentas:" -ForegroundColor Yellow
    foreach ($sol in $top5Lentas) {
        $latStr = [Math]::Round($sol.latencia_total_ms, 2)
        $numSol = $sol.num
        $instSol = $sol.instancia
        Write-Host "    - Solicitud ${numSol}: ${latStr} ms (${instSol})" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RESUMEN DE RESULTADOS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Contar resultados por instancia (basado en respuesta final)
$solicitudesPrincipal = ($solicitudes | Where-Object { $_.instancia_final -like "*principal*" }).Count
$solicitudesRedundancia = ($solicitudes | Where-Object { $_.instancia_final -like "*redundancia*" }).Count

Write-Host "Procesamiento Final:" -ForegroundColor White
Write-Host "  Enviadas a principal: $solicitudesPrincipal" -ForegroundColor Cyan
Write-Host "  Enviadas a redundancia: $solicitudesRedundancia" -ForegroundColor Cyan
$totalProcesadas = $solicitudesPrincipal + $solicitudesRedundancia
Write-Host "  Total: ${totalProcesadas}" -ForegroundColor Cyan
Write-Host ""

# Verificar si hubo failover
$huboFailover = $solicitudesRedundancia -gt 0
if ($huboFailover) {
    Write-Host "  Failover detectado" -ForegroundColor Green
    if ($solicitudesPrincipal -gt 0) {
        Write-Host "    - Algunas solicitudes fueron procesadas por el principal" -ForegroundColor Green
    }
    Write-Host "    - Solicitudes redirigidas a redundancia: $solicitudesRedundancia" -ForegroundColor Green
} else {
    Write-Host "  No se detecto failover - todas las solicitudes fueron al principal" -ForegroundColor Yellow
}

Write-Host ""

# Analisis de estados
$exitosas = ($solicitudes | Where-Object { $_.estado_final -eq "completada" }).Count
$fallidas = ($solicitudes | Where-Object { $_.estado_final -like "*error*" }).Count
$pendientes = ($solicitudes | Where-Object { $_.estado_final -eq "pendiente" }).Count
$erroresEnvio = ($solicitudes | Where-Object { $_.status -eq "error_envio" }).Count

Write-Host "Estados de Solicitudes:" -ForegroundColor White
Write-Host "  Total registradas: $($solicitudes.Count)" -ForegroundColor Gray
if ($exitosas -eq 60) {
    Write-Host "  Completadas: $exitosas" -ForegroundColor Green
} else {
    Write-Host "  Completadas: $exitosas" -ForegroundColor Yellow
}

if ($fallidas -eq 0) {
    Write-Host "  Fallidas: $fallidas" -ForegroundColor Green
} else {
    Write-Host "  Fallidas: $fallidas" -ForegroundColor Red
}

if ($pendientes -eq 0) {
    Write-Host "  Pendientes: $pendientes" -ForegroundColor Green
} else {
    Write-Host "  Pendientes: $pendientes" -ForegroundColor Yellow
}

if ($erroresEnvio -gt 0) {
    Write-Host "  Errores de envío: $erroresEnvio" -ForegroundColor Red
    Write-Host ""
    Write-Host "Solicitudes con error de envío:" -ForegroundColor Yellow
    $solicitudes | Where-Object { $_.status -eq "error_envio" } | ForEach-Object {
        Write-Host "    - Solicitud $($_.num): $($_.error)" -ForegroundColor Gray
    }
}
Write-Host ""

# Evaluacion del sistema
$sinPerdidas = ($exitosas + $fallidas + $pendientes) -eq 60

Write-Host "Evaluacion del Sistema:" -ForegroundColor White
if ($sinPerdidas) {
    Write-Host "  [OK] Sin perdida de solicitudes (60/60)" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Perdida de solicitudes detectada" -ForegroundColor Red
}

if ($huboFailover) {
    Write-Host "  [OK] Failover automatico funcionando" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Failover no se ejecuto" -ForegroundColor Red
}

if ($exitosas -ge 50) {
    Write-Host "  [OK] Alta disponibilidad (${exitosas}/60 completadas)" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Baja disponibilidad (${exitosas}/60 completadas)" -ForegroundColor Yellow
}
Write-Host ""

if ($sinPerdidas -and $huboFailover -and $exitosas -ge 50) {
    Write-Host "  PRUEBA EXITOSA - El sistema manejo la carga con failover automatico" -ForegroundColor Green
    Write-Host "  El sistema manejo 60 solicitudes concurrentes con failover automatico" -ForegroundColor Green
} else {
    Write-Host "  Revisa los resultados - puede haber problemas en el sistema" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
