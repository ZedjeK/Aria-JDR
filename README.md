# Aria-JDR

Application de jeu de rôle solo : on choisit son univers (fantasy, cyberpunk, post-apo…), et un LLM local fait le maître du jeu sur un socle de règles d100 commun à tous les univers.

Les règles du jeu sont dans [REGLES.md](REGLES.md).

## Principe

- **Le code arbitre** : jets de dés, points de vie, Santé mentale, progression. C'est le moteur, dans le dossier `aria/`.
- **Le LLM raconte** : il décrit les scènes, fait parler les personnages et appelle le moteur quand une règle s'applique.
- **Les univers** sont des fichiers JSON dans le dossier `univers/` : réglages, noms des compétences, parcours et armurerie. Le moteur les vérifie au chargement.

## Installation (Windows)

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install pytest
```

## Jouer la démo

Une ruelle de Néo-Tokyo : tu joues Kaito, le Netrunner, contre deux gangers. Les dés sont vraiment aléatoires, chaque partie est différente.

```bash
.venv\Scripts\python.exe -m aria.demo
```

La partie est sauvegardée dans `parties/demo_kaito.json`.

## Le MJ : qualifier un modèle sur son PC

Le MJ tourne avec [le fork PrismML de llama.cpp](https://github.com/PrismML-Eng/llama.cpp), attendu par défaut dans `%USERPROFILE%\Aria-LLM\llama-prism\`, avec les modèles dans `%USERPROFILE%\Aria-LLM\modeles\` (la liste est dans `aria/optimiseur.py`).

```bash
.venv\Scripts\python.exe -m aria.banc
```

Le banc lit la VRAM de la carte graphique, choisit le contexte et le cache qui tiennent, puis fait jouer au modèle 26 situations, dont 7 pièges où il serait tenté de trancher sans les dés ou de jouer à la place du joueur. Il garde le plus petit budget de réflexion qui passe : au moins 90 % des situations normales et tous les pièges, chacune réussie deux fois. Le résultat va dans `parties/profil_mj.json`. Si aucun modèle ne passe, il n'y a pas de MJ sur ce PC. `--tous` qualifie tous les modèles présents, pour comparer.

## Jouer avec le MJ

La même ruelle, mais en texte libre : tu écris ce que fait Kaito, et le MJ retenu par le banc appelle le moteur puis raconte. Chaque jet s'affiche avant la narration, pour que tu voies toujours ce que disent les dés.

```bash
.venv\Scripts\python.exe -m aria.jeu
```

En combat, le moteur tient le tour de parole : chacun agit à son tour, dans l'ordre d'initiative, et le MJ te rend la main à chacun de tes tours. À chaque fin de round, le moteur écrit la fiche du combat (`combat.md`) et la donne au MJ, pour qu'il raconte avec les vrais PV. Quand le combat se termine, ses moments forts (racontés par le MJ) et son résultat (écrit par le moteur) rejoignent les souvenirs de la campagne (`souvenirs.md`), puis la fiche est effacée.

`etat` affiche ta fiche, `quitter` termine la session (progression des compétences, puis sauvegarde). Chaque campagne a son dossier, ici `parties/neo-tokyo-kaito/` : sauvegarde, souvenirs et fiche du combat en cours. Quand la conversation devient trop longue pour le modèle, les plus vieux échanges sont oubliés ; les souvenirs, eux, restent sur le disque.

## L'exe portable

`Aria-JDR.exe` regroupe tout dans un seul fichier, avec un menu : jouer avec le MJ, la démo sans MJ, ou qualifier le MJ. Pas besoin d'installer Python sur le PC qui le lance. Si aucun MJ n'est qualifié sur ce PC, l'exe propose de lancer le banc d'abord.

Le serveur llama et les modèles ne sont pas dans l'exe, car ils pèsent plusieurs Go. L'exe cherche le dossier `Aria-LLM` à côté de lui, puis dans le dossier de l'utilisateur. Les parties s'enregistrent dans `parties/`, à côté de l'exe :

```
Aria-JDR\
  Aria-JDR.exe
  Aria-LLM\      (facultatif : llama-prism\ et modeles\)
  parties\       (créé au premier lancement)
```

Pour le construire (`dist\Aria-JDR.exe`), installe PyInstaller une fois, puis lance le script :

```bash
.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
```

```bash
powershell -ExecutionPolicy Bypass -File construire.ps1
```

Certains antivirus signalent à tort les exe PyInstaller : c'est un faux positif connu.

`python -m aria` ouvre le même menu depuis les sources.

## Lancer les tests

```bash
.venv\Scripts\python.exe -m pytest
```
