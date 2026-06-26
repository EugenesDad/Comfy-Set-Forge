@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py
  goto :done
)

where python >nul 2>nul
if %errorlevel%==0 (
  python app.py
  goto :done
)

echo Python was not found.
echo Please install Python 3, then run this file again.

:done
echo.
echo If the window closed because of an error, copy the message above.
pause
