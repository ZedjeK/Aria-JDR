# Journal des versions

Un bloc par version, le plus récent en haut. Les notes complètes d'une version
sont dans `docs/releases/`.

## Non publié

### Ajouté

- La carte de la campagne dans l'interface (onglet Carte) : les quartiers placés par le moteur (`aria/carte.py`), colorés par faction, avec les districts, le quartier du joueur, les quartiers disputés, une fiche au clic (contrôle, réputation, lieux connus) et « S'y rendre » pour un quartier voisin. Route `GET /api/carte`.
- Le moteur de la carte de combat en cases hexagonales (`aria/grille.py`, REGLES.md 7.11) : distances, déplacements (obstacles, terrain difficile, alliés traversables), ligne de tir et couvert, portées en cases. Un `Combat` peut porter une carte : la portée, le contact, la ligne de tir et le couvert y sont vérifiés, « repousser » fait reculer d'une case. Aucune partie ne crée encore de carte : le combat se joue comme avant.
- Le générateur des cartes de combat (`aria/carte_combat.py`) : six lieux (ruelle, entrepôt, bar, toit, parking, couloir), la densité d'obstacles selon le décor (blindés en fortifié), un peu de terrain difficile, les deux camps posés à leur distance de départ (12 cases, 8 dans un lieu exigu, 6 en embuscade) et reliés à pied, les renforts par leur bord. Pas encore branché aux parties.

## 0.2.0

### Ajouté

- Le combat à pied mené par le code (REGLES.md 7.8) : le moteur choisit l'action des ennemis avec une IA par profil (bretteur, tireur) qui tient compte du moral, de l'arme, du couvert et du nombre d'attaquants par cible ; le MJ ne tire plus leurs dés.
- Le menu du joueur en combat : attaquer, viser, recharger, débloquer, changer d'arme, se mettre à couvert, lancer un sort à une cible, stabiliser, parler, autre action, fuir, terminer le tour. Dans la page, des boutons (clic ou touches 1 à 9), les options impossibles grisées avec leur raison ; dans la console, un menu numéroté.
- Le récit du combat par le MJ, sans outils et à partir des faits du code (sans chiffre, sans fait inventé, sans rien décider à la place du joueur), à chaque round, à la fin seulement ou jamais ; à la fin, `fin_combat` avec les moments forts, et un repli du code si le MJ se tait.
- Les réactions du joueur : choisir sa défense à chaque attaque et le bonus d'une réussite majeure, selon le réglage.
- Les réglages de combat dans la page : moment du récit, PV exacts des ennemis, choix de sa défense, ennemis choisis par le MJ.
- Un essai, éteint par défaut : le plan du round par le MJ (une requête par round, intentions fermées, 25 secondes au plus, repli sur l'IA du code).
- Un simulateur de combats (`aria/simulateur_combat.py`, sept scénarios) et un mini-banc du plan (`python -m aria.banc_plan`).
- Au banc, dix situations de combat à pied (récits, « Parler », « Autre action », fuite, déclenchement) : 83 situations dont 23 pièges.

### Modifié

- Le prompt du MJ allège sa section combat quand le code mène ; les combats avec drone, arme de zone, lanceur de sorts ou véhicule restent menés par le MJ comme avant (`aria/prompts/combat_classique.md`).
- En combat à pied, le MJ n'a que les outils dont il a besoin (état, jets, choc, destin, PNJ, inventaire, fin du combat) ; appeler un outil de combat renvoie une erreur qui le dit.
- Fuir : le MJ clôt le combat puis ouvre la poursuite.
- Les réglages de l'interface se fusionnent avec l'existant au lieu de l'écraser.
- Le banc compare les récits sans tenir compte de l'apostrophe typographique du modèle.

## 0.1.0

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
