<#
.SYNOPSIS
  Vérifications sans réseau : ruff (lint + format) + pytest + projet Godot.
    -Fast         Python seulement (pas de Godot)
    -Integration  ajoute les tests qui exigent l'infra Docker + Ollama
#>
param([switch]$Fast, [switch]$Integration)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
$ruff = Join-Path $BackendDir '.venv\Scripts\ruff.exe'
$failed = @()
Push-Location -LiteralPath $BackendDir
try {
    Write-Step 'Ruff'
    & $ruff check .
    if ($LASTEXITCODE -ne 0) { $failed += 'ruff check' }
    & $ruff format --check .
    if ($LASTEXITCODE -ne 0) { $failed += 'ruff format (lancer : .venv\Scripts\ruff format .)' }
    Write-Step 'Pytest'
    $pytestArgs = @('-m', 'pytest', '-q')
    if ($Integration) { $pytestArgs += @('-m', 'integration or not integration') }
    & $VenvPython @pytestArgs
    if ($LASTEXITCODE -ne 0) { $failed += 'pytest' }
} finally {
    Pop-Location
}
if (-not $Fast) {
    & (Join-Path $PSScriptRoot 'godot.ps1') -Check
    if ($LASTEXITCODE -ne 0) { $failed += 'godot' }
}
Write-Step 'Bilan'
if ($failed.Count -eq 0) { Write-Ok 'Toutes les vérifications passent'; exit 0 }
Write-Ko ('Échecs : ' + ($failed -join ', '))
exit 1
