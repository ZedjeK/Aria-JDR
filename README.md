# Aria-JDR

Application de jeu de rôle solo : on choisit son univers (fantasy, cyberpunk, post-apo…), et un LLM local fait le maître du jeu sur un socle de règles d100 commun à tous les univers.

Les règles du jeu sont dans [REGLES.md](REGLES.md).

## Principe

- **Le code arbitre** : jets de dés, points de vie, Santé mentale, progression. C'est le moteur, dans le dossier `aria/`.
- **Le LLM raconte** : il décrit les scènes, fait parler les personnages et appelle le moteur quand une règle s'applique.

## Installation (Windows)

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install pytest
```

## Lancer les tests

```bash
.venv\Scripts\python.exe -m pytest
```
