<#
.SYNOPSIS
  Installe les modèles Ollama du catalogue ai/models.yaml qui manquent.
    -IncludeOptional  ajoute les modèles optionnels (tev1 : exige Ollama >= 0.40.4)
    -Tune             réglages Ollama pour 6 Go de VRAM (variables d'environnement UTILISATEUR,
                      à appliquer en quittant puis relançant Ollama)
#>
param([switch]$IncludeOptional, [switch]$Tune)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
$ollama = Get-DotEnv 'OLLAMA_EXE' "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
$ollamaUrl = Get-DotEnv 'OLLAMA_BASE_URL' 'http://localhost:11434'

if ($Tune) {
    [Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION', '1', 'User')
    [Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE', 'q8_0', 'User')
    Write-Ok 'OLLAMA_FLASH_ATTENTION=1 et OLLAMA_KV_CACHE_TYPE=q8_0 définis : cache KV environ divisé par 2.'
    Write-Warn 'Quittez puis relancez Ollama pour les appliquer.'
}

$filter = 'm.required'
if ($IncludeOptional) { $filter = 'True' }
$code = "from gmix.llm.catalog import load_catalog; print('\n'.join(sorted({m.tag for m in load_catalog().models.values() if $filter})))"
$wanted = @(& $VenvPython -c $code)
try {
    $installed = @((Invoke-RestMethod "$ollamaUrl/api/tags" -TimeoutSec 5).models | ForEach-Object { $_.name })
} catch {
    throw "Ollama injoignable sur $ollamaUrl : lancez l'application Ollama"
}
foreach ($tag in $wanted) {
    if ($installed -contains $tag) { Write-Ok "$tag déjà installé"; continue }
    Write-Step "ollama pull $tag"
    & $ollama pull $tag
    if ($LASTEXITCODE -ne 0) { Write-Ko "$tag : échec (version d'Ollama trop ancienne ? voir .\scripts\check-env.ps1)" }
}
