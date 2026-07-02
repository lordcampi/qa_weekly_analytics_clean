@echo off
cd /d "%~dp0"

set QA_PORT=8765
set VENV_PYTHON=%~dp0.venv\Scripts\python.exe

echo ================================================
echo   QA Weekly Analytics
echo   URL: http://localhost:%QA_PORT%
echo ================================================
echo.

:: Abrir navegador tras 5 segundos (espera a que Streamlit arranque en headless)
start "" cmd /c "ping -n 6 127.0.0.1 >nul && start http://localhost:%QA_PORT%/"

"%VENV_PYTHON%" -m streamlit run "%~dp0src\qa_weekly_analytics\app\streamlit_app.py" --server.port %QA_PORT% --server.address localhost --server.headless true

pause
