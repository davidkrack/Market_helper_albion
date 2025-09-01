@echo off
echo ========================================
echo Iniciando Albion Market Helper Backend
echo ========================================
echo.

cd backend

REM Activate virtual environment
call albion\Scripts\activate.bat

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo [ERROR] No se pudo activar el entorno virtual
    echo Ejecuta setup_windows.bat primero
    pause
    exit /b 1
)

echo [OK] Entorno virtual activado
echo.

REM Start the backend server
echo Iniciando servidor en http://localhost:8000
echo Presiona Ctrl+C para detener el servidor
echo.
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

pause