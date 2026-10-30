# Construit l'exe portable dist\Aria-JDR.exe avec PyInstaller.
# Préalable, une seule fois : .venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
# L'exe embarque le moteur, les univers et le prompt du MJ ; le serveur llama et les modèles
# restent dans Aria-LLM\ (à côté de l'exe, ou dans le dossier de l'utilisateur).

$ErrorActionPreference = "Stop"
$racine = $PSScriptRoot

& "$racine\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console `
    --name Aria-JDR `
    --paths "$racine" `
    --specpath "$racine\build" --workpath "$racine\build" --distpath "$racine\dist" `
    --add-data "$racine\univers;univers" `
    --add-data "$racine\aria\prompts;aria\prompts" `
    "$racine\aria\__main__.py"
if ($LASTEXITCODE -ne 0) { throw "La construction a échoué." }

Write-Host "Exe prêt : $racine\dist\Aria-JDR.exe"
