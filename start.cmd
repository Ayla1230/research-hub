@echo off
rem Research Hub - double-click to start.  Options: start.cmd [--port 8770] [--demo] [--lang en]
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
title Research Hub

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  Python was not found on this computer.
  echo.
  echo  1. Download Python 3.10 or newer from https://www.python.org/downloads/
  echo  2. In the installer, tick "Add python.exe to PATH", then install.
  echo  3. Double-click start.cmd again.
  echo.
  pause
  exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo.
  echo  Research Hub needs Python 3.10 or newer. Installed version:
  %PY% --version
  echo  Download a newer one from https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

echo  Starting Research Hub... the dashboard opens in your browser.
echo  Keep this window open while you use it. Close it to stop.
echo.
%PY% -m research_hub serve %*
if errorlevel 1 (
  echo.
  echo  Research Hub stopped with an error. The message above says why.
  echo  If it mentions the port being in use, Research Hub may already be running:
  echo  open http://127.0.0.1:8770/ in your browser, or run: start.cmd --port 8771
  echo.
  pause
)
