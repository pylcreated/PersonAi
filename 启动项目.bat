@echo off
setlocal
title Personal Agent Server

cd /d "%~dp0"
set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not defined PA_PORT set "PA_PORT=8765"

echo.
echo ========================================
echo       Starting Personal Agent Server
echo ========================================
echo.
echo Project: %CD%
echo Port:    %PA_PORT%
echo.

if not exist "%PYTHON%" goto missing_python

echo [1/3] Python environment found.
echo [2/3] Checking port %PA_PORT%...
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:%PA_PORT%/api/health' -TimeoutSec 2; if ($health.service -eq 'personal-agent' -and $health.api_version -eq 7) { exit 10 }; if ($health.service -eq 'personal-agent') { exit 12 } } catch { try { $tcp = New-Object Net.Sockets.TcpClient; $tcp.Connect('127.0.0.1', %PA_PORT%); $tcp.Close(); exit 11 } catch { exit 0 } }"
set "PORT_STATE=%ERRORLEVEL%"
if "%PORT_STATE%"=="10" goto already_running
if "%PORT_STATE%"=="11" goto port_busy
if "%PORT_STATE%"=="12" goto backend_outdated

echo [3/3] Starting backend and Web API...
echo.
echo Keep this window open.
echo Run the second script to open the UI.
echo Press Ctrl+C to stop the server.
echo ----------------------------------------
echo.

"%PYTHON%" -m personal_agent web --port %PA_PORT%
set "APP_EXIT_CODE=%ERRORLEVEL%"

echo.
echo ----------------------------------------
echo Server stopped. Exit code: %APP_EXIT_CODE%
echo.
pause
exit /b %APP_EXIT_CODE%

:already_running
echo.
echo Personal Agent is already running at:
echo http://127.0.0.1:%PA_PORT%
echo.
echo Run the UI launcher now.
echo.
pause
exit /b 0

:port_busy
echo.
echo [ERROR] Port %PA_PORT% is used by another program.
echo Close the old server using this port, then try again.
echo.
pause
exit /b 1

:backend_outdated
echo.
echo [UPDATE REQUIRED] An older Personal Agent backend is running.
echo Close its server window, then run this script again.
echo.
pause
exit /b 1

:missing_python
echo [ERROR] Python environment was not found:
echo %PYTHON%
echo.
echo Make sure the .venv folder exists in this project.
echo.
pause
exit /b 1
