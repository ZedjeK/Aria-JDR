# Journal des versions

Un bloc par version, le plus récent en haut. Les notes complètes d'une version
sont dans `docs/releases/`.

## Non publié

### Ajouté

- Première version d'Aria JDR.
- Le dépôt suit le modèle des applis Aria : fiche projet, licences des composants, sécurité, interface commune des scripts (`build.ps1`, `tools\tester.ps1`, `tools\version.ps1`) et chaîne de release.
- Le logo d'Aria JDR (le A glitché néon de la famille Aria, avec un d20 orange entre les jambages) et l'icône de l'exe, en plusieurs tailles.

- L'interface web locale d'Aria JDR, sur le squelette `python-fastapi` du modèle : serveur sur `127.0.0.1:8420` gardé par un jeton, réglages (dont le fond animé de d20), journal, sauvegardes, instance unique. Les écrans de jeu viennent ensuite.

### Modifié

- L'exe ouvre l'interface web dans le navigateur au lieu du menu en console, qui reste disponible depuis les sources (`python -m aria`). L'exe n'a donc pas encore les écrans de jeu.

- L'exe se décompresse dans `cache\` du dossier de données et non plus dans `%TEMP%`.
- `construire.ps1` devient `build.ps1` ; l'exe est construit dans `.work\sortie\` et non plus dans `dist\`.
