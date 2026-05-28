# TôNaIA — Agendar Monitor Automático no Task Scheduler
# Este script cria uma tarefa no Windows pra rodar o monitor toda semana.
# Execute como Administrador:  powershell -ExecutionPolicy Bypass .\scripts\agendar_monitor.ps1

param(
    [switch]$Registrar
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "python"
$Script = "$Root\backend\monitor.py"
$LogDir = "$Root\data\logs"
$TaskName = "TonaIA-Monitor"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$LogFile = "$LogDir\monitor_task_$(Get-Date -Format 'yyyyMMdd').log"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Weekly -At 09:00 -DaysOfWeek Monday
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

if ($Registrar) {
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -Force
        Write-Host "[OK] Tarefa '$TaskName' registrada! Roda toda segunda 09:00." -ForegroundColor Green
        Write-Host "     Log: $LogDir\monitor_task_*.log" -ForegroundColor Gray

        # Testar rodando agora
        Write-Host "[Teste] Executando monitor agora..." -ForegroundColor Yellow
        & $Python $Script *>> $LogFile
        Write-Host "[OK] Monitor executado. Log em: $LogFile" -ForegroundColor Green
    } catch {
        Write-Host "[ERRO] $_" -ForegroundColor Red
        Write-Host "Tente executar como Administrador." -ForegroundColor Yellow
    }
} else {
    Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   TôNaIA — AGENDAR MONITOR SEMANAL        ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Este script cria uma tarefa no Windows Task Scheduler"
    Write-Host "para rodar o monitor de auditoria toda segunda 09:00."
    Write-Host ""
    Write-Host "Para registrar a tarefa, execute como ADMINISTRADOR:"
    Write-Host ""
    Write-Host "  powershell -ExecutionPolicy Bypass .\scripts\agendar_monitor.ps1 -Registrar"
    Write-Host ""
    Write-Host "Ou manualmente no Task Scheduler:"
    Write-Host "  1. Abra 'Task Scheduler'"
    Write-Host "  2. 'Create Task'"
    Write-Host "  3. Nome: TonaIA-Monitor"
    Write-Host "  4. Trigger: Weekly, Seg 09:00"
    Write-Host "  5. Action: Start a program"
    Write-Host "     Program: $Python"
    Write-Host "     Args: `"$Script`""
    Write-Host "     Start in: $Root"
    Write-Host ""

    # Mostrar preview do comando
    Write-Host "Comando equivalente (Task Scheduler):" -ForegroundColor Gray
    Write-Host "schtasks /CREATE /SC WEEKLY /D MON /TN `"$TaskName`" /TR `"$Python `"$Script`"`" /ST 09:00 /RL HIGHEST" -ForegroundColor Gray
}
