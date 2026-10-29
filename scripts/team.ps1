<#
.SYNOPSIS
  Mesures de l'équipe d'agents, calculées sur les transcripts Claude Code (scripts\team_metrics.py).
    -Report                   rapport Markdown (80 lignes au plus) : base du coach-equipe
    -Run <agentId>            un run : statistiques, brief, compte rendu (préfixe d'identifiant accepté)
    -Json                     toutes les données, run par run
    -CheckOwners              valide .claude/ownership.json contre .claude/agents (code 1 sinon)
  -Since AAAA-MM-JJ et -Session <id> filtrent -Report et -Json. Voir docs/equipe/README.md.
#>
param(
    [switch]$Report,
    [string]$Run,
    [switch]$Json,
    [switch]$CheckOwners,
    [string]$Since,
    [string]$Session
)
. "$PSScriptRoot\_common.ps1"

$modes = @($Report, ($Run -ne ''), $Json, $CheckOwners) | Where-Object { $_ }
if ($modes.Count -ne 1) {
    throw 'Choisir un seul mode : -Report, -Run <agentId>, -Json ou -CheckOwners.'
}

# Stdlib seule : le venv du backend si présent, sinon le lanceur Python.
if (Test-Path -LiteralPath $VenvPython) {
    $python = @($VenvPython)
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = @('py', '-3')
} else {
    $python = @('python')
}
$script = Join-Path $PSScriptRoot 'team_metrics.py'

$pyArgs = @()
if ($CheckOwners) { $pyArgs = @('check-owners') }
elseif ($Run) { $pyArgs = @('run', $Run) }
else {
    $pyArgs = @($(if ($Report) { 'report' } else { 'json' }))
    if ($Since) { $pyArgs += @('--since', $Since) }
    if ($Session) { $pyArgs += @('--session', $Session) }
}

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$exe = $python[0]
$exeArgs = @()
if ($python.Count -gt 1) { $exeArgs = $python[1..($python.Count - 1)] }
& $exe @exeArgs $script @pyArgs
exit $LASTEXITCODE
