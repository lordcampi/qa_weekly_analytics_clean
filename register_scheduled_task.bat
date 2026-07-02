@echo off
REM Registra tarea semanal en Windows Task Scheduler (lunes 08:00).
REM Ejecutar como administrador si falla schtasks.
cd /d "%~dp0"
set TASK_NAME=QA_Weekly_Analytics_Publish
set SCRIPT=%~dp0publish_week.bat
schtasks /Create /TN "%TASK_NAME%" /TR "\"%SCRIPT%\"" /SC WEEKLY /D MON /ST 08:00 /F
echo Tarea "%TASK_NAME%" creada. Verifica en Programador de tareas de Windows.
