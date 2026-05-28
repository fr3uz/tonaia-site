@echo off
echo ====================================
echo  TonaIA - AGENDAR MONITOR SEMANAL
echo ====================================
echo.
echo Isso vai criar uma tarefa no Windows
echo para auditar seus clientes toda segunda 09:00
echo.
schtasks /CREATE /SC WEEKLY /D MON /TN "TonaIA-Monitor" /TR "python C:\Users\fr3us\Desktop\OPENCODE\tonaia\backend\monitor.py" /ST 09:00 /RL HIGHEST /F
echo.
if %ERRORLEVEL% equ 0 (
    echo [OK] Tarefa criada com sucesso!
    echo Voce pode ver em: Task Scheduler ^> TonaIA-Monitor
) else (
    echo [ERRO] Nao foi possivel criar. Tente executar como Administrador.
)
pause
