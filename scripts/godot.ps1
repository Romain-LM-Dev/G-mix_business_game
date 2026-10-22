<#
.SYNOPSIS
  .\scripts\godot.ps1          ouvre l'éditeur Godot sur le projet
  .\scripts\godot.ps1 -Run     lance le jeu
  .\scripts\godot.ps1 -Check   vérification headless : import + chargement de tous les scripts et scènes (code 0/1)
  .\scripts\godot.ps1 -Smoke   liaison headless avec le backend (API + worker system_ping démarrés)
  -Api http://192.168.1.20:8000   avec -Run ou -Smoke : se connecter à un autre serveur (réseau local, distance)
#>
param([switch]$Run, [switch]$Check, [switch]$Smoke, [string]$Api = '')
. "$PSScriptRoot\_common.ps1"
$console = Get-GodotExe -Console
if (-not (Test-Path -LiteralPath $console)) { throw "Godot introuvable : $console (GODOT_CONSOLE_EXE dans .env)" }

function Invoke-GodotCaptured([string[]]$Arguments) {
    $outFile = [IO.Path]::GetTempFileName()
    $errFile = [IO.Path]::GetTempFileName()
    $quoted = $Arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
    $process = Start-Process -FilePath $console -ArgumentList $quoted -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile
    $text = [string](Get-Content -LiteralPath $outFile -Raw -Encoding UTF8) + [string](Get-Content -LiteralPath $errFile -Raw -Encoding UTF8)
    Remove-Item -LiteralPath $outFile, $errFile -ErrorAction SilentlyContinue
    return @{ Code = $process.ExitCode; Lines = ($text -split "`r?`n") }
}

if ($Check) {
    Write-Step 'Import des ressources'
    $import = Invoke-GodotCaptured @('--headless', '--path', $GodotDir, '--import')
    $importErrors = @($import.Lines | Where-Object { $_ -cmatch 'ERROR|Parse Error' })
    Write-Step 'Chargement des scripts et scènes'
    $load = Invoke-GodotCaptured @('--headless', '--path', $GodotDir, '--script', 'res://tools/check_project.gd')
    $load.Lines | Where-Object { $_ -cmatch 'ÉCHEC|ERROR|Parse Error|Fichiers vérifiés' } | ForEach-Object { Write-Host "  $_" }
    foreach ($line in $importErrors) { Write-Ko $line.Trim() }
    if ($import.Code -eq 0 -and $load.Code -eq 0 -and $importErrors.Count -eq 0) { Write-Ok 'Projet Godot valide'; exit 0 }
    Write-Ko 'Erreurs dans le projet Godot'
    exit 1
}
$userArgs = @()
if ($Api) { $userArgs += "--api=$Api" }
if ($Smoke) {
    & $console --headless --path $GodotDir -- --smoke @userArgs
    exit $LASTEXITCODE
}
$editor = Get-GodotExe
if ($Run) { & $editor --path $GodotDir -- @userArgs; exit $LASTEXITCODE }
Start-Process -FilePath $editor -ArgumentList @('--path', ('"' + $GodotDir + '"'), '--editor')
