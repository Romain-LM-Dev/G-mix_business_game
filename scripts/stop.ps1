<#
.SYNOPSIS
  Arrête tout ce que lance start.ps1 : jeu Godot et serveurs de partie, API, workers, leurs fenêtres,
  puis les conteneurs Docker (données conservées). L'éditeur Godot, Docker Desktop et Ollama restent ouverts.
    -KeepInfra  laisse tourner Kafka, PostgreSQL et le stockage
#>
param([switch]$KeepInfra)
. "$PSScriptRoot\_common.ps1"

$godotPath = [regex]::Escape($GodotDir)
$targets = Get-CimInstance Win32_Process | Where-Object {
    $line = [string]$_.CommandLine
    ($_.Name -eq 'python.exe' -and $line -match 'gmix\.api\.main|gmix\.workers\.') -or
    ($_.Name -eq 'powershell.exe' -and $line -match 'scripts\\(api|worker)\.ps1') -or
    ($_.Name -like 'Godot*' -and $line -match $godotPath -and $line -notmatch '--editor')
}

Write-Step 'Jeu, serveurs de partie, API et workers'
if (-not $targets) { Write-Ok 'Rien à arrêter' }
foreach ($process in $targets) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Ok ("{0} (pid {1}) arrêté" -f $process.Name, $process.ProcessId)
}

if (-not $KeepInfra) {
    Write-Step 'Conteneurs Docker'
    if (Get-DockerVersion) { & (Join-Path $PSScriptRoot 'infra.ps1') down } else { Write-Ok 'Docker déjà arrêté' }
}
