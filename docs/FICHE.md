# Fiche projet : Aria JDR

Ce que cette appli a de propre. À relire avant toute modification, et à tenir à
jour quand l'appli change.

| | |
| --- | --- |
| Nom | Aria JDR (dépôt et exe : `Aria-JDR`) |
| Promesse | Un jeu de rôle solo : un LLM local raconte, le code arbitre les règles. |
| Élément orange du logo | proposé : un dé à cent faces, à valider avec le logo |
| Fond animé | aucun pour l'instant : le jeu n'a pas de fenêtre. Il se définira avec elle |
| Stack | Python 3.11 ou plus, aucune dépendance à l'exécution, exe PyInstaller en un seul fichier (console). La stack `python-fastapi` du modèle n'existe pas encore |
| Droits administrateur | non |
| Démarrage automatique | non |
| Installation par l'exe | non : exe portable, ni installation ni mise à jour automatique |
| Port local (interface web) | pas d'interface web. Le serveur llama, lancé par le jeu, écoute sur `127.0.0.1:8080` |
| Données de l'utilisateur | `%USERPROFILE%\.Aria-JDR` ; secrètes : aucune |
| Écritures hors du dossier de données | la décompression temporaire de l'exe dans `%TEMP%` (PyInstaller, un seul fichier), effacée à la fermeture ; rien d'autre : ni démarrage automatique ni raccourci |
| Connexions sortantes | aucune vers Internet dans le code du jeu ; seulement `127.0.0.1:8080`, le serveur llama local |
| Composants tiers embarqués | l'interpréteur Python 3.11 et ses bibliothèques natives (OpenSSL, libffi, bzip2, liblzma, runtime Visual C++), le chargeur de PyInstaller 6.22.3 : voir `LICENCES-TIERS.txt`. Le serveur llama (fork PrismML) et les modèles ne sont pas embarqués |
| Réussite de la v0.1 | le banc qualifie un MJ sur la carte de référence : les 21 pièges et au moins 90 % des situations normales, chacune réussie deux fois (80 situations ; atteint le 2026-11-15 avec Qwen3.8 27B sur une RTX 4080 SUPER) |

Les lignes « à renseigner » se complètent avant la première ligne de code.
