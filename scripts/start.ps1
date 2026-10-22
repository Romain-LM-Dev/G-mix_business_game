<#
.SYNOPSIS
  Démarrage rapide d'une séance : Docker, infrastructure, Ollama, API, worker de génération, puis le jeu.
  Premier lancement : crée le compte « admin » avec un mot de passe provisoire affiché ici (changé à la connexion).
    -Lan     API ouverte au réseau de la salle (les joueurs saisissent http://<IP-hôte>:8000 à la connexion)
    -NoGame  ne lance pas le client Godot
  Arrêt : fermer les fenêtres de l'API et du worker ; conteneurs : .\scripts\infra.ps1 down
#>
param([switch]$Lan, [switch]$NoGame)
. "$PSScriptRoot\_common.ps1"
Assert-Venv

function Wait-Until([scriptblock]$Ready, [int]$TimeoutSec, [string]$What) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while (-not (& $Ready)) {
        if ((Get-Date) -gt $deadline) { throw "$What ne répond pas après $TimeoutSec s" }
        Start-Sleep -Seconds 2
    }
}

function Test-Url([string]$Url) {
    try { $null = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 10; return $true } catch { return $false }
}

function Start-Window([string]$Script, [string[]]$Arguments) {
    $argList = @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', ('"' + (Join-Path $PSScriptRoot $Script) + '"')) + $Arguments
    Start-Process powershell.exe -ArgumentList $argList | Out-Null
}

Write-Step 'Docker Desktop'
if (-not (Get-DockerVersion)) {
    Start-Process (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
    Wait-Until { [bool](Get-DockerVersion) } 180 'Docker Desktop'
}
Write-Ok 'Docker démarré'
& (Join-Path $PSScriptRoot 'infra.ps1') up

Write-Step 'Ollama'
$ollamaUrl = Get-DotEnv 'OLLAMA_BASE_URL' 'http://localhost:11434'
if (-not (Test-Url "$ollamaUrl/api/version")) {
    Start-Process (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe')
    Wait-Until { Test-Url "$ollamaUrl/api/version" } 60 'Ollama'
}
Write-Ok "Ollama ($ollamaUrl)"

Write-Step 'Compte administrateur'
$created = & $VenvPython -m gmix.tools.create_user --username admin --role admin --provisional 2>$null
if ($LASTEXITCODE -eq 0) {
    $created | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    Write-Warn 'Notez ce mot de passe provisoire : il ne sera plus affiché.'
} else {
    Write-Ok 'Compte admin déjà présent'
}

Write-Step 'API et worker de génération (fenêtres séparées)'
$api = Get-ApiUrl
if (Test-Url "$api/docs") { Write-Ok "API déjà lancée ($api)" }  # /health interroge tous les services : lent
else {
    $apiArgs = @()
    if ($Lan) { $apiArgs = @('-Lan') }
    Start-Window 'api.ps1' $apiArgs
    Wait-Until { Test-Url "$api/docs" } 90 'API'
    Write-Ok "API prête : $api/docs"
}
$worker = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match 'gmix\.workers\.generation' }
if ($worker) { Write-Ok 'Worker de génération déjà lancé' }
else { Start-Window 'worker.ps1' @('generation'); Write-Ok 'Worker de génération lancé' }

if (-not $NoGame) {
    Write-Step 'Client Godot'
    Start-Process -FilePath (Get-GodotExe) -ArgumentList @('--path', ('"' + $GodotDir + '"'))
    Write-Ok "Jeu lancé : serveur $api, identifiant admin"
}
