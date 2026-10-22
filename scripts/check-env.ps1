<#
.SYNOPSIS
  Diagnostic du poste de développement : outils, Ollama, matériel, ports et services.
  Affiche ce qui bloque ; le code de sortie est le nombre de points bloquants.
#>
. "$PSScriptRoot\_common.ps1"
$blocking = New-Object System.Collections.Generic.List[string]
$advice = New-Object System.Collections.Generic.List[string]

Write-Step 'Outils'
$docker = Get-DockerVersion
if ($docker) { Write-Ok "Docker Engine $docker" } else { Write-Ko "Docker Desktop n'est pas démarré"; $blocking.Add('Démarrer Docker Desktop') }
if (Test-Path -LiteralPath $VenvPython) { Write-Ok ("Python du venv : " + (& $VenvPython --version)) }
else { Write-Ko 'venv backend absent'; $blocking.Add('Lancer .\scripts\setup.ps1') }
$godot = Get-GodotExe -Console
if (Test-Path -LiteralPath $godot) { Write-Ok "Godot : $godot" } else { Write-Ko "Godot introuvable : $godot"; $blocking.Add('Corriger GODOT_CONSOLE_EXE dans .env') }
if (Get-Command git -ErrorAction SilentlyContinue) { Write-Ok (git --version) } else { Write-Warn 'git absent'; $advice.Add('Installer git') }

Write-Step 'Ollama'
$ollamaUrl = Get-DotEnv 'OLLAMA_BASE_URL' 'http://localhost:11434'
try {
    $version = (Invoke-RestMethod "$ollamaUrl/api/version" -TimeoutSec 5).version
    Write-Ok "Ollama $version ($ollamaUrl)"
    if ((ConvertTo-Version $version) -lt [version]'0.40.4') {
        Write-Warn 'Ollama < 0.40.4 : tev1 ne peut pas être installé (repli automatique sur qwen2.5)'
        $advice.Add("Mettre à jour Ollama : icône Ollama > Restart to update, puis .\scripts\models.ps1 -IncludeOptional")
    }
    $installed = @((Invoke-RestMethod "$ollamaUrl/api/tags" -TimeoutSec 5).models | ForEach-Object { $_.name })
    Write-Ok ('Modèles : ' + ($installed -join ', '))
} catch {
    Write-Ko "Ollama injoignable sur $ollamaUrl"
    $blocking.Add("Lancer l'application Ollama")
}

Write-Step 'Matériel'
$gpu = nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader 2>$null
if ($LASTEXITCODE -eq 0 -and $gpu) { Write-Ok "GPU : $gpu" } else { Write-Warn 'Pas de GPU NVIDIA détecté : inférence sur CPU (lente)' }
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
if ($ram -lt 24) { Write-Warn "RAM $ram Go : Docker + Godot + Ollama sont à l'étroit (fermer les applications lourdes)" } else { Write-Ok "RAM $ram Go" }
$free = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
if ($free -lt 20) { Write-Warn "Disque C: $free Go libres"; $advice.Add('Libérer de l''espace disque') } else { Write-Ok "Disque C: $free Go libres" }

Write-Step 'Ports (hôte)'
$ports = [ordered]@{
    'Kafka'               = [int](Get-DotEnv 'KAFKA_PORT' '9092')
    'PostgreSQL (Docker)' = [int](Get-DotEnv 'POSTGRES_PORT' '5433')
    'PostgreSQL 18 local' = 5432
    'S3 RustFS'           = [int](Get-DotEnv 'S3_PORT' '9000')
    'Console S3'          = [int](Get-DotEnv 'S3_CONSOLE_PORT' '9001')
    'API'                 = [int](Get-DotEnv 'API_PORT' '8000')
    'Ollama'              = 11434
}
foreach ($name in $ports.Keys) {
    $port = $ports[$name]
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $owner = (Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        Write-Host ("  {0,-20} {1,5} : écoute ({2})" -f $name, $port, $owner)
    } else {
        Write-Host ("  {0,-20} {1,5} : libre" -f $name, $port)
    }
}

Write-Step 'Services applicatifs'
if (Test-Path -LiteralPath $VenvPython) {
    & $VenvPython -m gmix.tools.doctor
    if ($LASTEXITCODE -ne 0) { $blocking.Add('Services dégradés : .\scripts\infra.ps1 up') }
}

Write-Step 'Bilan'
foreach ($item in $advice) { Write-Warn $item }
if ($blocking.Count -eq 0) { Write-Ok 'Aucun point bloquant' } else { foreach ($item in $blocking) { Write-Ko $item } }
exit $blocking.Count
