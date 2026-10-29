# Fonctions communes aux scripts du projet. Usage : . "$PSScriptRoot\_common.ps1"
# Compatible Windows PowerShell 5.1 : pas de &&, ??, ternaire. Erreurs natives vérifiées via $LASTEXITCODE.

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$GodotDir = Join-Path $RepoRoot 'godot'
$VenvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
$ComposeFile = Join-Path $RepoRoot 'docker-compose.yml'
$env:PYTHONUTF8 = '1'

function Get-DotEnv {
    param([string]$Key, [string]$Default = '')
    $file = Join-Path $RepoRoot '.env'
    if (-not (Test-Path -LiteralPath $file)) { $file = Join-Path $RepoRoot '.env.example' }
    foreach ($line in Get-Content -LiteralPath $file -Encoding UTF8) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.*)$") { return $Matches[1].Trim() }
    }
    return $Default
}

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "  [!!] $Text" -ForegroundColor Yellow }
function Write-Ko([string]$Text) { Write-Host "  [KO] $Text" -ForegroundColor Red }

function Assert-Venv {
    if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Environnement Python absent : lancez .\scripts\setup.ps1' }
}

function Get-DockerVersion {
    $ErrorActionPreference = 'Continue'
    $version = docker version --format '{{.Server.Version}}' 2>$null
    if ($LASTEXITCODE -eq 0) { return $version }
    return $null
}

function Get-GodotExe([switch]$Console) {
    if ($Console) {
        return Get-DotEnv 'GODOT_CONSOLE_EXE' 'C:\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64_console.exe'
    }
    return Get-DotEnv 'GODOT_EXE' 'C:\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64.exe'
}

function Get-ApiUrl { return "http://$(Get-DotEnv 'API_HOST' '127.0.0.1'):$(Get-DotEnv 'API_PORT' '8000')" }

function ConvertTo-Version([string]$Text) {
    if ($Text -match '^(\d+)\.(\d+)\.(\d+)') { return [version]"$($Matches[1]).$($Matches[2]).$($Matches[3])" }
    return [version]'0.0.0'
}

## Journal complet d'une exécution : %TEMP%\gmix_logs\<horodatage>-<nom>-<pid>.log (chemin affiché par les scripts).
function New-LogPath([string]$Name) {
    $dir = Join-Path $env:TEMP 'gmix_logs'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return Join-Path $dir ('{0}-{1}-{2}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $Name, $PID)
}

## Ajoute une section au journal (UTF-8 sans BOM, plusieurs sections possibles dans le même fichier).
function Add-Journal([string]$LogPath, [string]$Title, $Lines) {
    $text = @("=== $Title ===") + @($Lines | Where-Object { $null -ne $_ })
    [IO.File]::AppendAllLines($LogPath, [string[]]$text, (New-Object Text.UTF8Encoding $false))
}

## Lance un exécutable en séparant sortie et erreurs (pas de 2>&1 : PowerShell 5.1 en ferait des erreurs).
## Le journal reçoit toute la sortie ; renvoie Code, Out et Err.
function Invoke-Captured([string]$Exe, [string[]]$Arguments, [string]$LogPath, [string]$Title) {
    $outFile = [IO.Path]::GetTempFileName()
    $errFile = [IO.Path]::GetTempFileName()
    $quoted = @($Arguments | ForEach-Object { if ($_ -match '\s' -or $_ -eq '') { '"' + $_ + '"' } else { $_ } })
    try {
        $process = Start-Process -FilePath $Exe -ArgumentList $quoted -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $outFile -RedirectStandardError $errFile
        $out = @(Get-Content -LiteralPath $outFile -Encoding UTF8)
        $err = @(Get-Content -LiteralPath $errFile -Encoding UTF8)
    } finally {
        Remove-Item -LiteralPath $outFile, $errFile -ErrorAction SilentlyContinue
    }
    Add-Journal $LogPath $Title ($out + $err)
    return @{ Code = $process.ExitCode; Out = $out; Err = $err }
}

## Sortie complète d'une exécution capturée (mode -Full).
function Write-Raw($Run) { foreach ($line in (@($Run.Out) + @($Run.Err))) { Write-Host $line } }

## Détail d'échec plafonné : au plus $Max lignes affichées, le reste est dans le journal.
function Write-Capped($Lines, [int]$Max) {
    $items = @($Lines | Where-Object { $null -ne $_ })
    foreach ($line in @($items | Select-Object -First $Max)) { Write-Host "    $line" }
    if ($items.Count -gt $Max) { Write-Host "    ... $($items.Count - $Max) ligne(s) de plus dans le journal" }
}
