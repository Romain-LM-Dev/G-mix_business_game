<#
.SYNOPSIS
  Vérifications sans réseau : ruff (lint + format) + pytest + projet Godot.
    -Fast          Python seulement (pas de Godot)
    -Integration   ajoute les tests qui exigent l'infra Docker + Ollama
    -Only <cible>  ne lance que cette cible, sans contrôle Godot : chemin de fichier ou de dossier (ruff et pytest),
                   ou expression pytest -k. Ex. : -Only backend/tests/test_engine.py  ou  -Only "test_engine and not slow"
                   Le test complet reste à lancer une fois en fin de mission.
    -Full          sortie complète (ruff et pytest bruts, contrôle Godot complet) en plus du bilan compact
  Le journal complet est toujours écrit dans %TEMP%\gmix_logs\ ; son chemin est affiché.
#>
param([switch]$Fast, [switch]$Integration, [string]$Only = '', [switch]$Full)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
$ruff = Join-Path $BackendDir '.venv\Scripts\ruff.exe'
$journal = New-LogPath 'test'
$failed = @()

## Cible : un chemin existant (relatif à la racine ou absolu, suffixe ::nom accepté) ou une expression -k.
$ruffTargets = @('.')
$pytestTargets = @()
if ($Only) {
    $pathPart = $Only -replace '::.*$', ''
    $absolute = $pathPart
    if (-not [IO.Path]::IsPathRooted($pathPart)) { $absolute = Join-Path $RepoRoot $pathPart }
    if (Test-Path -LiteralPath $absolute) {
        $resolved = (Resolve-Path -LiteralPath $absolute).Path
        $ruffTargets = @($resolved)
        $pytestTargets = @($resolved + $Only.Substring($pathPart.Length))
    } elseif ($Only -match '[\\/]|\.py') {
        throw "Cible introuvable : $Only"
    } else {
        $pytestTargets = @('-k', $Only)
    }
}

$pytestArgs = @('-m', 'pytest', '-q')
if (-not $Full) { $pytestArgs += '--tb=short' }
if ($Integration) { $pytestArgs += @('-m', 'integration or not integration') }
$pytestArgs += $pytestTargets
$ruffCheckArgs = @('check') + $ruffTargets
if (-not $Full) { $ruffCheckArgs = @('check', '--output-format=concise') + $ruffTargets }

## Nombre tiré de la première ligne qui correspond, sinon -1.
function Get-FirstNumber([string[]]$Lines, [string]$Pattern) {
    foreach ($line in $Lines) { if ($line -match $Pattern) { return [int]$Matches[1] } }
    return -1
}

## Compteurs de la ligne de résumé pytest (« 355 passed, 19 deselected in 6.37s ») ; $null si absente.
function Get-PytestCounts([string[]]$Lines) {
    $summary = ''
    foreach ($line in $Lines) { if ($line -match ' in \d+(\.\d+)?s( |\(|$)') { $summary = $line } }
    if ($summary -eq '') { return $null }
    $counts = @{ passed = 0; failed = 0; error = 0; skipped = 0; deselected = 0; duration = '' }
    foreach ($m in [regex]::Matches($summary, '(\d+) (passed|failed|errors?|skipped|deselected|xfailed|xpassed|warnings?)')) {
        $key = $m.Groups[2].Value
        if ($key -like 'error*') { $key = 'error' }
        $counts[$key] = [int]$m.Groups[1].Value
    }
    $counts.duration = [regex]::Match($summary, ' in (\d+(\.\d+)?)s').Groups[1].Value
    return $counts
}

## Échecs pytest : lignes FAILED/ERROR du résumé, puis les sections FAILURES/ERRORS (trace courte).
function Get-PytestDetail([string[]]$Lines) {
    $detail = @($Lines | Where-Object { $_ -match '^(FAILED|ERROR) ' })
    $inFailures = $false
    foreach ($line in $Lines) {
        if ($line -match '^=+ (FAILURES|ERRORS) =+$') { $inFailures = $true; continue }
        if ($line -match '^=+ .* =+$') { $inFailures = $false }
        if ($inFailures -and $line.Trim() -ne '') { $detail += $line }
    }
    return $detail
}

Push-Location -LiteralPath $BackendDir
try {
    $ruffCheck = Invoke-Captured $ruff $ruffCheckArgs $journal 'ruff check'
    $ruffFormat = Invoke-Captured $ruff (@('format', '--check') + $ruffTargets) $journal 'ruff format --check'
    $pytest = Invoke-Captured $VenvPython $pytestArgs $journal 'pytest'
} finally {
    Pop-Location
}

if ($Full) { Write-Step 'Ruff'; Write-Raw $ruffCheck; Write-Raw $ruffFormat; Write-Step 'Pytest'; Write-Raw $pytest }

if ($ruffCheck.Code -eq 0) {
    Write-Ok 'Ruff check : aucune erreur'
} else {
    $count = Get-FirstNumber $ruffCheck.Out 'Found (\d+) errors?'
    $countText = 'échec (voir le journal)'
    if ($count -ge 0) { $countText = "$count erreur(s)" }
    Write-Ko "Ruff check : $countText"
    $diag = @($ruffCheck.Out | Where-Object { $_ -match ':\d+:\d+: ' })
    if ($diag.Count -eq 0) { $diag = @($ruffCheck.Out + $ruffCheck.Err) }
    Write-Capped $diag 20
    $failed += 'ruff check'
}

if ($ruffFormat.Code -eq 0) {
    Write-Ok 'Ruff format : fichiers conformes'
} else {
    Write-Ko 'Ruff format : fichier(s) à reformater (lancer : .venv\Scripts\ruff format .)'
    Write-Capped @($ruffFormat.Out | Where-Object { $_ -match '^Would reformat' }) 20
    $failed += 'ruff format (lancer : .venv\Scripts\ruff format .)'
}

$all = @($pytest.Out) + @($pytest.Err)
$counts = Get-PytestCounts $all
if ($null -eq $counts) {
    Write-Ko "Pytest : aucun résumé (code $($pytest.Code))"
    Write-Capped @($all | Select-Object -Last 40) 40
    $failed += 'pytest'
} else {
    $line = "Pytest : $($counts.passed) passés, $($counts.failed) échec(s), $($counts.error) erreur(s), " +
        "$($counts.skipped) sauté(s), $($counts.deselected) désélectionné(s), en $($counts.duration) s"
    if ($pytest.Code -eq 0) {
        Write-Ok $line
    } else {
        Write-Ko $line
        $detail = Get-PytestDetail $all
        if ($detail.Count -eq 0) { $detail = @($all | Select-Object -Last 40) }
        Write-Capped $detail 60
        $failed += 'pytest'
    }
}

if ($Only) {
    Write-Host '  [--] Contrôle Godot ignoré (-Only)'
} elseif (-not $Fast) {
    & (Join-Path $PSScriptRoot 'godot.ps1') -Check -Full:$Full
    if ($LASTEXITCODE -ne 0) { $failed += 'godot' }
}

Write-Host "  Journal complet : $journal"
if ($failed.Count -eq 0) {
    if ($Only) { Write-Ok 'Vérifications ciblées passent (test complet à lancer en fin de mission)' }
    else { Write-Ok 'Toutes les vérifications passent' }
    exit 0
}
Write-Ko ('Échecs : ' + ($failed -join ', '))
exit 1
