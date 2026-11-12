@echo off
rem Research Hub - start from the repository root.  Usage: start.cmd [--port 8770] [--demo] [--lang en]
cd /d "%~dp0"
where py >nul 2>nul && (py -3 -m research_hub serve %*) || (python -m research_hub serve %*)
