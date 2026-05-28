@echo off
REM Backup automatico TonaIA - executa backup dos dados e git commit
REM Criado pelo motor B2AI

echo [%date% %time%] Iniciando backup TonaIA...

cd /d C:\Users\fr3us\Desktop\OPENCODE\tonaia

REM 1. Backup do banco de dados via API
echo Fazendo backup via API...
curl -s http://localhost:5000/api/backup > nul
if %errorlevel% equ 0 (echo Backup API OK) else (echo Backup API FALHOU - servidor offline?)

REM 2. Copiar bancos de dados para cerebro
if not exist cerebro\ mkdir cerebro
copy /Y data\tonaia.db cerebro\tonaia_backup.db > nul
copy /Y data\prospectos.db cerebro\prospectos_backup.db > nul
copy /Y data\questionarios.json cerebro\questionarios_backup.json > nul
echo Bancos copiados para cerebro/

REM 3. Git add, commit, push
git add -A
git commit -m "backup automatico %date% %time%" --quiet
git push --quiet
echo Git commit realizado

echo Backup concluido em %date% %time%
