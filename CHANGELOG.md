# Journal des versions

Un bloc par version, le plus récent en haut. Les notes complètes d'une version
sont dans `docs/releases/`.

## Non publié

### Ajouté

- Première version d'Aria JDR.
- Le dépôt suit le modèle des applis Aria : fiche projet, licences des composants, sécurité, interface commune des scripts (`build.ps1`, `tools\tester.ps1`, `tools\version.ps1`) et chaîne de release.
- Le logo d'Aria JDR (le A glitché néon de la famille Aria, avec un d20 orange entre les jambages) et l'icône de l'exe, en plusieurs tailles.
- L'interface web locale d'Aria JDR, sur le squelette `python-fastapi` du modèle : serveur sur `127.0.0.1:8420` gardé par un jeton, réglages (dont le fond animé de d20), journal, sauvegardes, instance unique.
- La gestion dans l'interface : les campagnes (avec l'étape où en est chacune), la corbeille (restaurer, vider), les personnages prêts, le MJ retenu sur ce PC et le dossier des données.
- La qualification du MJ dans l'interface (Réglages) : le banc, puis celui du générateur d'univers, avec la progression à l'écran et la possibilité de l'interrompre sans toucher au profil actuel.
- La partie dans l'interface : reprendre une campagne, en commencer une nouvelle (formulaire), créer un personnage, jouer avec le MJ (saisie, boutons d'état, d'inventaire, de carte, de monde et de pistes), interrompre. Le moteur tourne dans un fil du serveur ; la page relit le fil de la partie si on la recharge.

### Modifié

- L'exe ouvre l'interface web dans le navigateur au lieu du menu en console, qui reste disponible depuis les sources (`python -m aria`). 
- Pendant que le jeu travaille, la page dit depuis combien de temps, et le moteur annonce la création de l'univers (plusieurs minutes) avant qu'elle commence, au lieu de se taire.
- L'exe se décompresse dans `cache\` du dossier de données et non plus dans `%TEMP%`.
- `construire.ps1` devient `build.ps1` ; l'exe est construit dans `.work\sortie\` et non plus dans `dist\`.
- `jeu.lancer`, `jeu.mj_charge`, `personnages.creer` (nouveau, repris du menu console) et `banc_generateur.lancer` (nouveau, repris de sa ligne de commande) acceptent l'entrée et la sortie qu'on leur donne ; la console reste leur valeur par défaut.
