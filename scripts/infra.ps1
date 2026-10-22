<#
.SYNOPSIS
  Infrastructure Docker du projet.
    up      démarre Kafka, PostgreSQL+pgvector, RustFS, attend qu'ils soient sains, puis bootstrap
            (topics Kafka, buckets S3, migrations Alembic, domaines)
    down    arrête les conteneurs (données conservées)
    status  état des conteneurs
    logs    journaux (-Service kafka|postgres|storage, -Follow pour suivre)
    tools   démarre la console Kafka (http://localhost:8085)
    reset   SUPPRIME toutes les données locales puis redémarre (confirmation demandée)
#>
param(
    [ValidateSet('up', 'down', 'status', 'logs', 'tools', 'reset')][string]$Action = 'up',
    [string]$Service = '',
    [switch]$Follow
)
. "$PSScriptRoot\_common.ps1"
$compose = @('compose', '-f', $ComposeFile)

function Wait-Healthy([string[]]$Containers, [int]$TimeoutSec = 180) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    foreach ($container in $Containers) {
        while ($true) {
            $state = docker inspect -f '{{.State.Health.Status}}' $container 2>$null
            if ($state -eq 'healthy') { Write-Ok "$container : healthy"; break }
            if ((Get-Date) -gt $deadline) { throw "$container n'est pas sain après $TimeoutSec s : .\scripts\infra.ps1 logs -Service ..." }
            Start-Sleep -Seconds 2
        }
    }
}

switch ($Action) {
    'up' {
        if (-not (Get-DockerVersion)) { throw "Docker Desktop n'est pas démarré" }
        Write-Step 'Démarrage des conteneurs'
        docker @compose up -d
        if ($LASTEXITCODE -ne 0) { throw 'docker compose up a échoué' }
        Wait-Healthy @('gmix-kafka', 'gmix-postgres', 'gmix-storage')
        Write-Step 'Bootstrap applicatif'
        Assert-Venv
        & $VenvPython -m gmix.bootstrap
        if ($LASTEXITCODE -ne 0) { throw 'Bootstrap en échec' }
        Write-Ok 'Infrastructure prête'
        Write-Host '  Console S3 : http://localhost:9001 (S3_ACCESS_KEY / S3_SECRET_KEY du .env)'
        Write-Host '  Console Kafka : .\scripts\infra.ps1 tools'
    }
    'down' {
        docker @compose --profile tools down
        Write-Ok 'Conteneurs arrêtés (volumes conservés)'
    }
    'status' { docker @compose ps -a }
    'logs' {
        $logArgs = @('logs', '--tail', '150')
        if ($Follow) { $logArgs += '-f' }
        if ($Service) { $logArgs += $Service }
        docker @compose @logArgs
    }
    'tools' {
        docker @compose --profile tools up -d kafka-console
        Write-Ok 'Console Kafka : http://localhost:8085'
    }
    'reset' {
        Write-Warn 'Cette action SUPPRIME les données locales : topics Kafka, base PostgreSQL, fichiers S3.'
        $answer = Read-Host 'Tapez RESET pour confirmer'
        if ($answer -ne 'RESET') { Write-Host 'Annulé.'; exit 1 }
        docker @compose --profile tools down -v
        & $PSCommandPath -Action up
    }
}
