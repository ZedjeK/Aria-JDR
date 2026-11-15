# Journal des versions

Un bloc par version, le plus récent en haut. Les notes complètes d'une version
sont dans `docs/releases/`.

## Non publié

### Ajouté

- Première version d'Aria JDR.
- Le dépôt suit le modèle des applis Aria : fiche projet, licences des composants, sécurité, interface commune des scripts (`build.ps1`, `tools\tester.ps1`, `tools\version.ps1`) et chaîne de release.
- Le logo d'Aria JDR (le A glitché néon de la famille Aria, avec un d20 orange entre les jambages) et l'icône de l'exe, en plusieurs tailles.

### Modifié

- `construire.ps1` devient `build.ps1` ; l'exe est construit dans `.work\sortie\` et non plus dans `dist\`.
