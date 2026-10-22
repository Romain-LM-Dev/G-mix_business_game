<#
.SYNOPSIS
  Test de bout en bout : santé des services, pipeline API -> Kafka -> worker -> Ollama -> WebSocket,
  aller-retour RAG (rien n'est conservé), puis la même liaison vue depuis Godot (headless).
  Si l'API ne répond pas, l'API et le worker system_ping sont démarrés le temps du test.
#>
param([switch]$KeepRunning, [switch]$NoGodot)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
$api = Get-ApiUrl

function Test-Api {
    try { $null = Invoke-RestMethod "$api/health" -TimeoutSec 10; return $true } catch { return $false }
}

$started = @()
if (-not (Test-Api)) {
    Write-Step "API absente : démarrage temporaire de l'API et du worker system_ping"
    $started += Start-Process -FilePath $VenvPython -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
        -ArgumentList @('-m', 'uvicorn', 'gmix.api.main:app', '--host', (Get-DotEnv 'API_HOST' '127.0.0.1'), '--port', (Get-DotEnv 'API_PORT' '8000'))
    $started += Start-Process -FilePath $VenvPython -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
        -ArgumentList @('-m', 'gmix.workers.system_ping')
    for ($i = 0; $i -lt 60 -and -not (Test-Api); $i++) { Start-Sleep -Milliseconds 500 }
}

$code = 0
try {
    Write-Step 'Backend (Python) puis client Godot headless, avec un compte admin jetable'
    $smokeArgs = @('-m', 'gmix.tools.smoke', '--api', $api)
    if (-not $NoGodot) { $smokeArgs += @('--godot', (Get-GodotExe -Console)) }
    & $VenvPython @smokeArgs
    if ($LASTEXITCODE -ne 0) { $code = 1 }
} finally {
    if (-not $KeepRunning) { $started | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } }
}
Write-Step 'Bilan'
if ($code -eq 0) { Write-Ok 'Environnement opérationnel de bout en bout' } else { Write-Ko 'Au moins un test a échoué (voir ci-dessus)' }
exit $code
