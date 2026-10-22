@echo off
rem Arret de G-mix (double-clic) : voir scripts\stop.ps1. Option : -KeepInfra (garde les conteneurs).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1" %*
pause
