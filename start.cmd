@echo off
rem Lancement rapide de G-mix (double-clic) : voir scripts\start.ps1. Option : -Lan (jeu en salle).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
pause
