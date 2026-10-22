<#
.SYNOPSIS
  Installation initiale, idempotente : .env, venv Python + dépendances, images Docker, Git LFS.
#>
param([string]$PythonVersion = '3.14')
. "$PSScriptRoot\_common.ps1"

Write-Step 'Fichier .env'
$envFile = Join-Path $RepoRoot '.env'
if (Test-Path -LiteralPath $envFile) { Write-Ok '.env déjà présent (non modifié)' }
else { Copy-Item -LiteralPath (Join-Path $RepoRoot '.env.example') -Destination $envFile; Write-Ok '.env créé depuis .env.example' }

Write-Step 'Secret JWT (.env)'
$envText = [System.IO.File]::ReadAllText($envFile)
if ([regex]::Match($envText, '(?m)^JWT_SECRET=([^\r\n]*)').Groups[1].Value.Trim().Length -ge 32) { Write-Ok 'Secret JWT déjà défini' }
else {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
    if ($envText -match '(?m)^JWT_SECRET=') { $envText = [regex]::Replace($envText, '(?m)^JWT_SECRET=[^\r\n]*', "JWT_SECRET=$secret") }
    else { $envText = $envText.TrimEnd() + "`r`nJWT_SECRET=$secret`r`n" }
    [System.IO.File]::WriteAllText($envFile, $envText, (New-Object System.Text.UTF8Encoding $false))
    Write-Ok 'Secret JWT aléatoire écrit dans .env (les jetons déjà émis deviennent invalides)'
}

Write-Step "Python $PythonVersion : backend\.venv"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & py "-$PythonVersion" -m venv (Join-Path $BackendDir '.venv')
    if ($LASTEXITCODE -ne 0) { throw "Création du venv impossible (py -$PythonVersion)" }
}
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -e "$BackendDir[dev]" --quiet
if ($LASTEXITCODE -ne 0) { throw 'Installation des dépendances Python en échec' }
Write-Ok 'Dépendances Python installées'

Write-Step 'Images Docker'
if (Get-DockerVersion) {
    docker compose -f $ComposeFile pull
    if ($LASTEXITCODE -eq 0) { Write-Ok 'Images téléchargées' } else { Write-Ko 'docker compose pull a échoué' }
} else {
    Write-Warn 'Docker Desktop arrêté : relancez setup.ps1 une fois Docker démarré'
}

Write-Step 'Git LFS'
if (Test-Path -LiteralPath (Join-Path $RepoRoot '.git')) {
    git -C $RepoRoot lfs install --local | Out-Null
    Write-Ok 'Git LFS activé pour ce dépôt (assets binaires)'
}

Write-Step 'Étapes suivantes'
Write-Host '  .\scripts\infra.ps1 up        conteneurs + topics + buckets + migrations + domaines'
Write-Host '  .\scripts\models.ps1          modèles Ollama du catalogue ai/models.yaml'
Write-Host '  .\scripts\api.ps1             API (http://127.0.0.1:8000/docs)'
Write-Host '  .\scripts\worker.ps1 system_ping'
Write-Host '  .\scripts\smoke.ps1           test de bout en bout'
