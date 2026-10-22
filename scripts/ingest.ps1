<#
.SYNOPSIS
  Ingère dans le RAG les documents de knowledge\<domaine>\ déclarés (avec leur licence) dans SOURCES.md,
  puis mesure la couverture avec les questions de référence ai\evals\<domaine>.rag.jsonl si elles existent.
  Exemple : .\scripts\ingest.ps1 -Domain supply-chain
#>
param([Parameter(Mandatory = $true)][string]$Domain, [switch]$NoEval)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
Push-Location -LiteralPath $BackendDir
try {
    Write-Step "Ingestion : knowledge\$Domain"
    & $VenvPython -m gmix.rag.ingest_dir $Domain
    if ($LASTEXITCODE -ne 0) { throw 'Ingestion en échec' }
    $evalFile = Join-Path $RepoRoot "ai\evals\$Domain.rag.jsonl"
    if (-not $NoEval -and (Test-Path -LiteralPath $evalFile)) {
        Write-Step 'Couverture du corpus (questions de référence)'
        & $VenvPython -m gmix.tools.eval_rag $Domain
    }
} finally {
    Pop-Location
}
