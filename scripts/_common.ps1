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
