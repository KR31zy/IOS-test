@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (python tools\release.py --target android --install-backend-deps) else (py -3 tools\release.py --target android --install-backend-deps)
set STATUS=%ERRORLEVEL%
echo Build exited with status %STATUS%.
pause
exit /b %STATUS%
