@echo off
echo =====================================
echo Albion Market Helper - Windows Setup
echo =====================================
echo.

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH
    echo Por favor instala Python 3.11+ desde https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion
    pause
    exit /b 1
)

echo [OK] Python encontrado
echo.

REM Create directory structure
echo Creando estructura de directorios...
if not exist backend mkdir backend
if not exist backend\services mkdir backend\services
if not exist backend\tests mkdir backend\tests
if not exist frontend mkdir frontend

REM Create virtual environment
echo.
echo Creando entorno virtual de Python...
cd backend
python -m venv albion

REM Activate virtual environment and install dependencies
echo.
echo Activando entorno virtual e instalando dependencias...
call albion\Scripts\activate.bat

REM Install dependencies
echo.
echo Instalando dependencias de Python...
pip install --upgrade pip
pip install fastapi==0.104.1
pip install uvicorn[standard]==0.24.0
pip install httpx==0.25.1
pip install pydantic==2.4.2
pip install python-dotenv==1.0.0
pip install pytest==7.4.3
pip install pytest-asyncio==0.21.1

REM Create .env file
echo.
echo Creando archivo .env...
(
echo # Albion Market Helper - Environment Variables
echo.
echo # AODP API Configuration
echo AODP_BASE=https://west.albion-online-data.com
echo.
echo # Cache Configuration  
echo CACHE_TTL_SECONDS=600
echo.
echo # Rate Limiting
echo RATE_LIMIT_PER_MIN=120
) > .env

echo.
echo =====================================
echo Configuracion completada!
echo =====================================
echo.
echo Para iniciar el backend:
echo   1. cd backend
echo   2. albion\Scripts\activate
echo   3. python app.py
echo.
echo Para usar el frontend:
echo   1. Abre frontend\index.html en tu navegador
echo.
pause