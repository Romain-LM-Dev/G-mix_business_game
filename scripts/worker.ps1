<#
.SYNOPSIS
  Lance un worker Kafka du dossier backend\gmix\workers. Exemple : .\scripts\worker.ps1 system_ping
#>
param([Parameter(Mandatory = $true)][string]$Name)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
$workersDir = Join-Path $BackendDir 'gmix\workers'
if (-not (Test-Path -LiteralPath (Join-Path $workersDir "$Name.py"))) {
    $available = Get-ChildItem -LiteralPath $workersDir -Filter *.py |
        Where-Object { $_.BaseName -notin @('__init__', 'runtime') } | ForEach-Object { $_.BaseName }
    throw "Worker inconnu '$Name'. Disponibles : $($available -join ', ')"
}
& $VenvPython -m "gmix.workers.$Name"
