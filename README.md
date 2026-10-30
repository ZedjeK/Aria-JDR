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

Le banc lit la VRAM de la carte graphique, choisit le contexte et le cache qui tiennent, puis fait jouer au modèle 24 situations, dont 6 pièges où il serait tenté de trancher sans les dés. Il garde le plus petit budget de réflexion qui passe : au moins 90 % des situations normales et tous les pièges, chacune réussie deux fois. Le résultat va dans `parties/profil_mj.json`. Si aucun modèle ne passe, il n'y a pas de MJ sur ce PC. `--tous` qualifie tous les modèles présents, pour comparer.

## Lancer les tests

```bash
.venv\Scripts\python.exe -m pytest
```
