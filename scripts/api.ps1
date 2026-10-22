<#
.SYNOPSIS
  API FastAPI avec rechargement automatique (code Python, catalogue IA, prompts, schémas).
  Documentation interactive : http://127.0.0.1:8000/docs
    -Lan       écoute sur toutes les interfaces : les postes de la salle s'y connectent (pare-feu à ouvrir)
    -NoReload  sans rechargement automatique
#>
param([switch]$NoReload, [switch]$Lan)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
$apiHost = Get-DotEnv 'API_HOST' '127.0.0.1'
$apiPort = Get-DotEnv 'API_PORT' '8000'
if ($Lan) {
    $apiHost = '0.0.0.0'
    Write-Step 'Mode réseau local'
    $addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {
        $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback|Docker'
    }
    foreach ($address in $addresses) {
        Write-Host ("  Joueurs : .\scripts\godot.ps1 -Run -Api http://{0}:{1}   ({2})" -f $address.IPAddress, $apiPort, $address.InterfaceAlias)
    }
    if (-not (Get-NetFirewallRule -DisplayName 'G-mix API' -ErrorAction SilentlyContinue)) {
        Write-Warn "Pare-feu Windows : autoriser le port $apiPort (une fois, PowerShell administrateur) :"
        Write-Host "    New-NetFirewallRule -DisplayName 'G-mix API' -Direction Inbound -Protocol TCP -LocalPort $apiPort -Action Allow -Profile Private"
    }
    Write-Warn 'Réseau local uniquement : à distance, passer par un serveur avec HTTPS (docs/decisions/0005).'
}
$apiArgs = @('-m', 'uvicorn', 'gmix.api.main:app', '--host', $apiHost, '--port', $apiPort)
if (-not $NoReload) {
    $apiArgs += @('--reload', '--reload-dir', 'gmix', '--reload-dir', '..\ai',
        '--reload-include', '*.yaml', '--reload-include', '*.json', '--reload-include', '*.md')
}
Push-Location -LiteralPath $BackendDir
try { & $VenvPython @apiArgs } finally { Pop-Location }
