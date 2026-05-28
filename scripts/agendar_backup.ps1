# Agendador de Backup TonaIA
# Cria tarefa no Windows Task Scheduler para backup diario 23:00

$taskName = "TonaIA-Backup"
$scriptPath = "C:\Users\fr3us\Desktop\OPENCODE\tonaia\scripts\backup_auto.bat"

# Remove se ja existir
schtasks /Delete /TN $taskName /F 2>$null

schtasks /Create /TN $taskName /TR $scriptPath /SC DAILY /ST 23:00 /F /IT

Write-Host "Tarefa '$taskName' criada - executa todo dia as 23:00"
Write-Host "Script: $scriptPath"
