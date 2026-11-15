<#
.SYNOPSIS
Lance les tests d'Aria JDR (pytest, dossier tests\).

.DESCRIPTION
Code de retour non nul si un test échoue. Utilise .venv\Scripts\python.exe s'il existe, sinon python.
Aucun modèle ni serveur llama : les tests ne touchent qu'au moteur et à des faux.

    .\tools\tester.ps1
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$racine = Split-Path -Parent $PSScriptRoot
$python = Join-Path $racine '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $commande = Get-Command python -ErrorAction SilentlyContinue
    if (-not $commande) { throw "Python est introuvable : installe Python 3.11 ou plus, ou crée .venv (voir le README)." }
    $python = $commande.Source
}

# Sous PowerShell 5.1, une sortie d'erreur d'un programme redirigée arrêterait le script : on lit son code de retour.
$ErrorActionPreference = 'Continue'
Push-Location $racine
& $python -m pytest
$code = $LASTEXITCODE
Pop-Location
$ErrorActionPreference = 'Stop'

if ($code -ne 0) {
    Write-Host "Les tests ont échoué." -ForegroundColor Red
    exit 1
}
Write-Host "Tous les tests passent." -ForegroundColor Cyan
exit 0
