# Fiche projet : Aria JDR

Ce que cette appli a de propre. À relire avant toute modification, et à tenir à
jour quand l'appli change.

| | |
| --- | --- |
| Nom | Aria JDR (dépôt et exe : `Aria-JDR`) |
| Promesse | Un jeu de rôle solo : un LLM local raconte, le code arbitre les règles. |
| Élément orange du logo | un d20 vu de face (un icosaèdre, dix faces visibles), posé entre les jambages du A |
| Fond animé | des d20 (un hexagone et son triangle central) qui traversent la zone principale de gauche à droite en roulant ; hauteur, taille et départ tirés au hasard à chaque passage, 2 à 5 par défaut, un passage dure 14, 7 ou 3,5 s. Réglable, coupé si le système demande moins d'animations |
| Stack | Python 3.11 ou plus, FastAPI et uvicorn : interface web locale ouverte dans le navigateur par défaut, exe PyInstaller en un seul fichier sans console (stack `python-fastapi` du modèle) |
| Droits administrateur | non |
| Démarrage automatique | non |
| Installation par l'exe | non : exe portable |
| Mises à jour intégrées | pas encore : obligatoires pour toute appli Aria, elles arriveront avec la stack `python-fastapi` du modèle, qui ne les fournit pas encore. D'ici là, pas de nouvelle release publique |
| Port local (interface web) | `8420`, sur `127.0.0.1` seulement. Le serveur llama, lancé par le jeu, écoute en plus sur `127.0.0.1:8080` |
| Données de l'utilisateur | `%USERPROFILE%\.Aria-JDR` ; secrètes : le port et le jeton de l'instance en cours, chiffrés par DPAPI (`secrets\instance.dpapi`) et effacés à l'arrêt |
| Écritures hors du dossier de données | aucune : l'exe se décompresse dans `cache\` du dossier de données (PyInstaller, un seul fichier, `--runtime-tmpdir`), effacée à la fermeture ; ni démarrage automatique ni raccourci |
| Connexions sortantes | aucune vers Internet dans le code du jeu ; seulement `127.0.0.1` : l'interface (8420) et le serveur llama (8080). Le jeu lance le navigateur par défaut pour ouvrir l'interface |
| Composants tiers embarqués | l'interpréteur Python 3.11 et ses bibliothèques natives (OpenSSL, libffi, bzip2, liblzma, runtime Visual C++), le chargeur de PyInstaller 6.22.3, FastAPI, uvicorn et leurs dépendances (Starlette, pydantic, anyio, h11, click…), les polices Space Grotesk et IBM Plex Mono : voir `LICENCES-TIERS.txt`. Le serveur llama (fork PrismML) et les modèles ne sont pas embarqués |
| Réussite de la v0.1 | le banc qualifie un MJ sur la carte de référence : les 21 pièges et au moins 90 % des situations normales, chacune réussie deux fois (80 situations ; atteint le 2026-11-15 avec Qwen3.8 27B sur une RTX 4080 SUPER) |

Les lignes « à renseigner » se complètent avant la première ligne de code.
