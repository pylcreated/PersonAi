@echo off
setlocal
title Personal Agent UI Launcher

cd /d "%~dp0"
set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not defined PA_PORT set "PA_PORT=8765"
set "URL=http://127.0.0.1:%PA_PORT%"

echo.
echo ========================================
echo        Opening Personal Agent UI
echo ========================================
echo.
echo [1/2] Checking backend at %URL% ...

powershell.exe -NoLogo -NoProfile -NonInteractive -Command "try { $health = Invoke-RestMethod -Uri '%URL%/api/health' -TimeoutSec 3; if ($health.service -eq 'personal-agent' -and $health.api_version -eq 7) { exit 0 }; if ($health.service -eq 'personal-agent') { exit 12 }; exit 1 } catch { exit 1 }"

if "%ERRORLEVEL%"=="12" goto backend_outdated
if errorlevel 1 goto start_backend

echo [2/2] Backend is online. Opening browser...
goto open_browser

:start_backend
echo Backend is offline. Starting it now...
if not exist "%PYTHON%" goto missing_python
start "Personal Agent Server" /min "%PYTHON%" -m personal_agent web --port %PA_PORT%
echo Waiting for the backend...
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$ready = $false; for ($i = 0; $i -lt 60; $i++) { try { $health = Invoke-RestMethod -Uri '%URL%/api/health' -TimeoutSec 1; if ($health.service -eq 'personal-agent' -and $health.api_version -eq 7) { $ready = $true; break } } catch {}; Start-Sleep -Milliseconds 500 }; if ($ready) { exit 0 } else { exit 1 }"
if errorlevel 1 goto backend_offline
echo Backend started successfully.

:open_browser
if defined PA_SKIP_BROWSER goto browser_done
start "" "%URL%"

:browser_done
echo.
echo UI opened successfully.
echo If the browser did not open, visit:
echo %URL%
echo.
timeout /t 3 /nobreak >nul
exit /b 0

:backend_offline
echo.
echo [ERROR] Cannot connect to the Personal Agent backend.
echo.
echo Start the first script and keep its window open:
echo   Start Project ^(the file named with Chinese characters^)
echo.
echo Then run this UI launcher again.
echo.
pause
exit /b 1

:backend_outdated
echo.
echo [UPDATE REQUIRED] An older backend is still running.
echo.
echo Close the existing Personal Agent Server window,
echo then run this UI launcher again.
echo.
pause
exit /b 1

:missing_python
echo.
echo [ERROR] Python environment was not found:
echo %PYTHON%
echo.
pause
exit /b 1
