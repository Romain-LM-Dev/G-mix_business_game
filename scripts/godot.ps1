<#
.SYNOPSIS
  .\scripts\godot.ps1          ouvre l'éditeur Godot sur le projet
  .\scripts\godot.ps1 -Run     lance le jeu
  .\scripts\godot.ps1 -Check   vérification headless : import + chargement de tous les scripts et scènes (code 0/1)
  .\scripts\godot.ps1 -Smoke   liaison headless avec le backend (API + worker system_ping démarrés)
  .\scripts\godot.ps1 -Tour [-Snapshot]  contrôle de lisibilité des écrans avant-jeu et des panneaux du HUD (code 0/1)
  .\scripts\godot.ps1 -Flow [-NoLlm]     parcours formateur de bout en bout : génération, lobby, monde, semaines, débrief
      -Full      sortie complète (toute la sortie Godot, étapes) au lieu du bilan compact ; le journal complet est
                 toujours écrit dans %TEMP%\gmix_logs\ (son chemin est affiché)
      -Snapshot  captures PNG dans %TEMP%\gmix_imgs\ui_tour (fenêtre Godot, GPU requis ; sortie non capturée)
      -NoLlm     sans dialogues avec les agents, donc sans appel à Ollama
      -Tour et -Flow : API locale démarrée si elle ne répond pas (et arrêtée ensuite), comptes jetables créés puis
      supprimés en base, même en cas d'échec. Le code de sortie est celui de Godot (0 = OK).
  -Api http://192.168.1.20:8000   avec -Run ou -Smoke : se connecter à un autre serveur (réseau local, distance)
#>
param(
    [switch]$Run, [switch]$Check, [switch]$Smoke, [switch]$Tour, [switch]$Flow, [switch]$Snapshot, [switch]$NoLlm,
    [switch]$Full, [string]$Api = ''
)
. "$PSScriptRoot\_common.ps1"
$console = Get-GodotExe -Console
if (-not (Test-Path -LiteralPath $console)) { throw "Godot introuvable : $console (GODOT_CONSOLE_EXE dans .env)" }

## Étape affichée seulement en mode -Full ; le bilan compact porte les verdicts.
function Write-StepFull([string]$Text) { if ($Full) { Write-Step $Text } }

## /docs répond (comme start.ps1) : l'API est là, même si un processus orphelin tient le port.
function Test-ApiUp([string]$Url) {
    try { $null = Invoke-WebRequest -Uri "$Url/docs" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop; return $true } catch { return $false }
}

## Bilan d'un contrôle -Tour ou -Flow : verdict et nombre de vérifications, défauts et premières erreurs si échec.
## Le verdict et le code de sortie viennent de Godot, inchangés ; -Full affiche toute la sortie.
function Show-UiReport($Run, [string]$Label, [int]$Code, [string]$Journal) {
    if ($Full) { Write-Raw $Run }
    $verdict = @($Run.Out | Where-Object { $_ -match '^(TOUR|FLOW) (OK|KO) : ' }) | Select-Object -Last 1
    $text = 'pas de bilan Godot (voir le journal)'
    if ($null -ne $verdict) { $text = $verdict -replace '^(TOUR|FLOW) (OK|KO) : ', '' }
    if ($Code -eq 0) { Write-Ok "$Label : $text" } else { Write-Ko "$Label : $text (code $Code)" }
    $fails = @($Run.Out + $Run.Err | Where-Object { $_ -match '^TOUR DEFAUT |^FLOW ECHEC |^  KO  ' })
    $scriptErrors = @($Run.Out + $Run.Err | Where-Object { $_ -match 'SCRIPT ERROR' })
    if ($Code -ne 0) {
        if ($fails.Count -gt 0) { Write-Capped $fails 40 } else { Write-Capped @($Run.Out + $Run.Err | Select-Object -Last 20) 20 }
    }
    if ($scriptErrors.Count -gt 0) {
        Write-Warn "$($scriptErrors.Count) erreur(s) de script dans la sortie Godot"
        Write-Capped $scriptErrors 10
    }
    Write-Host "  Journal complet : $Journal"
}

## -Tour et -Flow : contrôles du client contre l'API locale et la base. Les comptes jetables viennent de
## gmix.tools.ui_accounts ; leurs jetons ne vont qu'aux variables d'environnement de Godot (jamais affichés ni écrits).
function Invoke-UiCheck {
    if ($Tour -and $Flow) { throw '-Tour et -Flow : choisir un seul contrôle' }
    if ($Flow -and $Snapshot) { throw '-Snapshot se lance avec -Tour' }
    if ($Api) { throw '-Tour et -Flow écrivent dans la base locale : pas de -Api' }
    $url = Get-ApiUrl
    $label = 'Tour'
    if ($Flow) { $label = 'Flow' }
    $journal = New-LogPath $label.ToLower()
    $apiProcess = $null
    $accounts = $null
    $code = 1
    try {
        if (-not (Test-ApiUp $url)) {
            Write-Step "API absente sur $url : démarrage temporaire"
            $apiProcess = Start-Process -FilePath $VenvPython -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
                -ArgumentList @('-m', 'uvicorn', 'gmix.api.main:app', '--host', (Get-DotEnv 'API_HOST' '127.0.0.1'), '--port', (Get-DotEnv 'API_PORT' '8000'))
            for ($i = 0; $i -lt 120 -and -not $apiProcess.HasExited -and -not (Test-ApiUp $url); $i++) { Start-Sleep -Milliseconds 500 }
            if (-not (Test-ApiUp $url)) { throw "API non joignable sur $url (port occupé par un processus orphelin ? Get-NetTCPConnection -LocalPort 8000)" }
        }
        $scenario = 'tour'
        if ($Flow) { $scenario = 'flow' }
        Write-StepFull 'Comptes jetables'
        $raw = & $VenvPython -m gmix.tools.ui_accounts create --scenario $scenario
        if ($LASTEXITCODE -ne 0) { throw 'création des comptes jetables impossible (voir ci-dessus)' }
        $accounts = ($raw | Select-Object -Last 1) | ConvertFrom-Json
        foreach ($variable in $accounts.env.PSObject.Properties) { Set-Item -Path ('env:' + $variable.Name) -Value $variable.Value }
        if ($Flow) {
            Write-StepFull 'Parcours formateur de bout en bout (flow_test, headless)'
            $godot = $console
            $godotArgs = @('--headless', '--path', $GodotDir, 'res://scenes/tools/flow_test/flow_test.tscn', '--', "--api=$url")
            if ($NoLlm) { $godotArgs += '--no-llm' }
        } elseif ($Snapshot) {
            $shots = Join-Path $env:TEMP 'gmix_imgs\ui_tour'
            New-Item -ItemType Directory -Force -Path $shots | Out-Null
            Write-Step "Écrans avant-jeu (fenêtre Godot) : captures dans $shots"
            $godot = Get-GodotExe
            $godotArgs = @('--path', $GodotDir, '--rendering-method', 'gl_compatibility', 'res://scenes/tools/ui_tour/ui_tour.tscn', '--', "--api=$url", '--sizes=1280x720,1366x768,1920x1080,1024x600', "--snapshot=$shots")
        } else {
            Write-StepFull 'Écrans avant-jeu et panneaux du HUD (ui_tour, headless)'
            $godot = $console
            $godotArgs = @('--headless', '--path', $GodotDir, 'res://scenes/tools/ui_tour/ui_tour.tscn', '--', "--api=$url", '--sizes=1280x720,1366x768,1920x1080,1024x600')
        }
        if ($Snapshot) {
            # Fenêtre Godot (exécutable graphique) : sa sortie n'est pas capturée, comme avant.
            & $godot @godotArgs | Out-Host
            $code = $LASTEXITCODE
        } else {
            $run = Invoke-Captured $godot $godotArgs $journal $label
            $code = $run.Code
            Show-UiReport $run $label $code $journal
        }
    } finally {
        if ($accounts) {
            & $VenvPython -m gmix.tools.ui_accounts cleanup @($accounts.ids) | Out-Host
            if ($LASTEXITCODE -ne 0) { Write-Ko ('nettoyage en échec, à relancer : ui_accounts cleanup ' + ($accounts.ids -join ' ')); $code = 1 }
            foreach ($variable in $accounts.env.PSObject.Properties) { Remove-Item -Path ('env:' + $variable.Name) -ErrorAction SilentlyContinue }
        }
        if ($apiProcess) { & taskkill.exe /PID $apiProcess.Id /T /F *> $null; Write-Ok 'API temporaire arrêtée' }
    }
    Write-StepFull 'Bilan'
    if ($code -eq 0) { Write-Ok 'Contrôle réussi' } else { Write-Ko "Contrôle en échec (code $code)" }
    exit $code
}

if ($Tour -or $Flow) { Invoke-UiCheck }
if ($Check) {
    $journal = New-LogPath 'godot-check'
    Write-StepFull 'Import des ressources'
    $import = Invoke-Captured $console @('--headless', '--path', $GodotDir, '--import') $journal 'import'
    $importErrors = @($import.Out + $import.Err | Where-Object { $_ -cmatch 'ERROR|Parse Error' })
    Write-StepFull 'Chargement des scripts et scènes'
    $load = Invoke-Captured $console @('--headless', '--path', $GodotDir, '--script', 'res://tools/check_project.gd') $journal 'check_project'
    $loadLines = @($load.Out + $load.Err | Where-Object { $_ -cmatch 'ÉCHEC|ERROR|Parse Error|Fichiers vérifiés' })
    $summary = [string](@($loadLines | Where-Object { $_ -match 'Fichiers vérifiés' }) | Select-Object -Last 1)
    $ok = ($import.Code -eq 0 -and $load.Code -eq 0 -and $importErrors.Count -eq 0)
    if ($Full) {
        foreach ($line in $loadLines) { Write-Host "  $line" }
        foreach ($line in $importErrors) { Write-Ko $line.Trim() }
    }
    if ($ok) {
        $okText = 'Projet Godot valide'
        if ($summary.Trim() -ne '') { $okText += ' (' + $summary.Trim() + ')' }
        Write-Ok $okText
    } else {
        if (-not $Full) {
            if ($summary.Trim() -ne '') { Write-Host "  $($summary.Trim())" }
            $problems = @($importErrors | ForEach-Object { $_.Trim() }) + @($loadLines | Where-Object { $_ -cmatch 'ÉCHEC|ERROR|Parse Error' } | ForEach-Object { $_.Trim() })
            Write-Capped $problems 30
        }
        Write-Ko 'Erreurs dans le projet Godot'
    }
    Write-Host "  Journal complet : $journal"
    if ($ok) { exit 0 }
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
