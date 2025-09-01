@echo off
REM ========================================
REM Albion Data Client - Private Ingestion Setup
REM ========================================

echo ==========================================
echo Albion Market Helper - ADC Setup
echo ==========================================
echo.

REM Check if ADC is installed
if not exist "C:\Program Files\Albion Data Client\albiondata-client.exe" (
    echo [ERROR] Albion Data Client not found!
    echo.
    echo Please download and install from:
    echo https://github.com/ao-data/albiondata-client/releases
    echo.
    echo Install to default location: C:\Program Files\Albion Data Client\
    echo.
    pause
    exit /b 1
)

echo Select ingestion mode:
echo.
echo [1] Private ONLY (data stays local, not shared with AODP)
echo [2] Dual Mode (share with AODP + local copy)
echo [3] Test Mode (dry run, no sharing)
echo.
set /p mode="Choose option (1-3): "

if "%mode%"=="1" goto private_only
if "%mode%"=="2" goto dual_mode
if "%mode%"=="3" goto test_mode
echo Invalid option
pause
exit /b 1

:private_only
echo.
echo Starting ADC in PRIVATE ONLY mode...
echo Your data will NOT be shared with AODP.
echo.
"C:\Program Files\Albion Data Client\albiondata-client.exe" -d -p "http://localhost:8000/api/ingest/adc"
goto end

:dual_mode
echo.
echo Starting ADC in DUAL mode...
echo Your data WILL be shared with AODP and stored locally.
echo.
"C:\Program Files\Albion Data Client\albiondata-client.exe" -i "http+pow://pow.west.albion-online-data.com,http://localhost:8000/api/ingest/adc"
goto end

:test_mode
echo.
echo Starting ADC in TEST mode...
echo No data will be sent anywhere (dry run).
echo.
"C:\Program Files\Albion Data Client\albiondata-client.exe" -d
goto end

:end
pause