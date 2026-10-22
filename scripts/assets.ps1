<#
.SYNOPSIS
  Chaîne des assets 3D (catalogue ai/assets.yaml) :
    .\scripts\assets.ps1                        export du catalogue + construction des scènes Godot + vérification
    .\scripts\assets.ps1 -Downloads <dossier>   importe d'abord les modèles depuis les zips Kenney extraits
                                                (<dossier>\<download_dir>\x\..., voir packs dans ai/assets.yaml)
    .\scripts\assets.ps1 -Gallery <dossier>     capture une image par catégorie (ouvre Godot quelques secondes)
    .\scripts\assets.ps1 -SyncDb                table assets + embeddings pour le choix par l'IA (infra et Ollama requis)
#>
param([string]$Downloads = '', [string]$Gallery = '', [switch]$SyncDb)
. "$PSScriptRoot\_common.ps1"
Assert-Venv
$console = Get-GodotExe -Console

Push-Location -LiteralPath $BackendDir
try {
    if ($Downloads) {
        Write-Step 'Import des modèles'
        & $VenvPython -m gmix.tools.assets import $Downloads
        if ($LASTEXITCODE -ne 0) { throw 'Import des modèles en échec' }
    }
    Write-Step 'Export du catalogue : godot/assets/catalog.json'
    & $VenvPython -m gmix.tools.assets export
    if ($LASTEXITCODE -ne 0) { throw 'Export du catalogue en échec' }
} finally {
    Pop-Location
}

Write-Step 'Construction des scènes Godot'
& $console --headless --path $GodotDir --import | Out-Null
& $console --headless --path $GodotDir --script 'res://tools/build_asset_scenes.gd'
if ($LASTEXITCODE -ne 0) { throw 'Construction des scènes en échec' }
& $console --headless --path $GodotDir --import | Out-Null
& (Join-Path $PSScriptRoot 'godot.ps1') -Check
if ($LASTEXITCODE -ne 0) { throw 'Projet Godot invalide après construction' }

if ($Gallery) {
    Write-Step "Galerie : $Gallery"
    & $console --path $GodotDir 'res://scenes/tools/asset_gallery/asset_gallery.tscn' -- "--screenshots=$Gallery"
}
if ($SyncDb) {
    Write-Step 'Synchronisation de la table assets'
    Push-Location -LiteralPath $BackendDir
    try { & $VenvPython -m gmix.tools.assets sync-db } finally { Pop-Location }
}
