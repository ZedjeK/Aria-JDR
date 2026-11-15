# Affiche la version sur sa dernière ligne, sans le « v ». Elle vit dans pyproject.toml, et nulle part ailleurs.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pyproject = Join-Path (Split-Path -Parent $PSScriptRoot) 'pyproject.toml'
$texte = Get-Content -LiteralPath $pyproject -Raw -Encoding UTF8
# La première ligne « version = "X.Y.Z" » : celle de la section [project]
if ($texte -notmatch '(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"\s*$') {
    throw "Version introuvable ou mal formée dans pyproject.toml (attendu : X.Y.Z)."
}
$Matches[1]
