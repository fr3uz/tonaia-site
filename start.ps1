# TôNaIA — Launcher Completo
# Inicia todos os servicos em segundo plano

param(
    [ValidateSet('tudo','server','whatsapp','monitor','qr')]
    [string]$Modo = 'tudo'
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Path $Logs -Force | Out-Null
$data = Get-Date -Format "yyyyMMdd_HHmm"

function Start-Server {
    $log = Join-Path $Logs "server_$data.log"
    $proc = Start-Process -WindowStyle Hidden -FilePath "python" `
        -ArgumentList "backend/server.py" `
        -WorkingDirectory $Root `
        -PassThru
    Write-Host "[Server] Iniciado (PID $($proc.Id)) — http://localhost:5000" -ForegroundColor Green
    return $proc
}

function Start-WhatsApp {
    $log = Join-Path $Logs "whatsapp_$data.log"
    $proc = Start-Process -WindowStyle Hidden -FilePath "node" `
        -ArgumentList "server.js" `
        -WorkingDirectory (Join-Path $Root "backend\whatsapp") `
        -PassThru
    Write-Host "[WhatsApp] Iniciado (PID $($proc.Id)) — http://localhost:3001" -ForegroundColor Green
    return $proc
}

function Start-Monitor {
    Write-Host "[Monitor] Executando ciclo de auditoria..." -ForegroundColor Yellow
    $proc = Start-Process -WindowStyle Hidden -FilePath "python" `
        -ArgumentList "-c", "from backend.monitor import executar_ciclo; executar_ciclo()" `
        -WorkingDirectory $Root `
        -PassThru
    Write-Host "[Monitor] Ciclo iniciado (PID $($proc.Id))" -ForegroundColor Green
    return $proc
}

function Show-QR {
    Write-Host "[WhatsApp] Exibindo QR Code..." -ForegroundColor Yellow
    & node server.js --qr
}

Write-Host "`n"
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║         TôNaIA — LAUNCHER           ║" -ForegroundColor Cyan
Write-Host "  ║   www.tonaia.com.br                 ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "`n"

$procs = @()

switch ($Modo) {
    'tudo' {
        $procs += Start-Server
        $procs += Start-WhatsApp
        Start-Sleep -Seconds 2
        Write-Host "[Tudo pronto] Abrindo navegador..." -ForegroundColor Cyan
        Start-Process "http://localhost:5000"
        Write-Host "`nPressione ENTER para parar tudo." -ForegroundColor Gray
        Read-Host | Out-Null
        $procs | ForEach-Object { if (!$_.HasExited) { $_.Kill() } }
        Write-Host "Servicos parados." -ForegroundColor Yellow
    }
    'server' {
        $procs += Start-Server
        Write-Host "`nPressione ENTER para parar." -ForegroundColor Gray
        Read-Host | Out-Null
        $procs | ForEach-Object { if (!$_.HasExited) { $_.Kill() } }
    }
    'whatsapp' {
        $procs += Start-WhatsApp
        Write-Host "`nPressione ENTER para parar." -ForegroundColor Gray
        Read-Host | Out-Null
        $procs | ForEach-Object { if (!$_.HasExited) { $_.Kill() } }
    }
    'monitor' {
        Start-Monitor
    }
    'qr' {
        Show-QR
    }
}
