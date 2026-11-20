**Aria JDR** {VERSION} : un jeu de rôle solo, où un LLM local raconte et le code arbitre les règles.

<!-- Modèle des notes de version. À chaque version : copie ce fichier vers docs/releases/v{VERSION}.md dans la PR
     de version, remplace {VERSION} et {REPO_URL}, remplis les sections, supprime ce commentaire. Le workflow de
     release publie ce fichier tel quel. La base des nouveautés vient des notes générées par GitHub, rangées par
     label (.github/release.yml) : gh api repos/ZedjeK/Aria-JDR/releases/generate-notes -f tag_name=v{VERSION}
     -f previous_tag_name=vX.Y.Z --jq .body -->

## Nouveautés

- Ce qui change pour toi, une ligne par nouveauté.

## À savoir

- **Requalifie le MJ** si son prompt a changé (sinon, supprime cette ligne) : dans les Réglages, plus d'une heure avec le serveur du MJ qui occupe la carte graphique.
- **Mesures de cette version** : le résultat du banc (situations normales, pièges, budget de réflexion), sans rien affirmer qui n'a pas été mesuré.
- **Le serveur llama et les modèles ne sont pas dans l'exe** : ils pèsent plusieurs Go. L'exe cherche le dossier `Aria-LLM` (avec `llama-prism` et `modeles`) à côté de lui, puis dans le dossier de l'utilisateur. Le README explique où les trouver.
- **Matériel testé** et **modèle qualifié** : la carte et le modèle essayés, rien d'autre.
- Certains antivirus signalent à tort les exe PyInstaller : c'est un faux positif connu.

## Installation

1. Télécharge `Aria-JDR-{VERSION}.zip` ci-dessous.
2. Décompresse d'abord le zip en entier (clic droit, « Extraire tout »). Choisis un dossier stable : pas Téléchargements, car c'est là que les mises à jour remplacent le jeu. Lancé depuis l'aperçu du zip dans l'Explorateur, l'exe démarre sans les fichiers livrés à côté de lui.
3. Lance `Aria-JDR.exe` : l'interface s'ouvre dans ton navigateur par défaut.
4. L'exe n'est pas signé : si Windows affiche « Windows a protégé votre ordinateur », clique sur « Informations complémentaires », puis sur « Exécuter quand même ».

## Mise à jour depuis une version précédente

Depuis la 0.3.0, le jeu te propose lui-même la nouvelle version : un bandeau l'annonce, et sur ton clic « Installer la mise à jour », jamais pendant une partie ou un banc, il remplace ses fichiers là où il tourne et garde la version précédente dans `sauvegardes\versions\`.

Depuis la 0.2.0 ou avant : ferme le jeu (bouton « Quitter »), décompresse le nouveau zip en entier, puis remplace l'exe par le nouveau.

Tes parties sont dans `%USERPROFILE%\.Aria-JDR` et sont reprises telles quelles.

## Contenu

| Composant | Version | Source |
| --- | --- | --- |
| Aria JDR | {VERSION} | [ce dépôt]({REPO_URL}) |

Le détail des composants embarqués est dans `LICENCES-TIERS.txt`, joint au zip.

## Comment vérifier ce que tu as téléchargé

L'empreinte du zip est dans `Aria-JDR-{VERSION}.zip.sha256`. Dans PowerShell :

```powershell
(Get-FileHash .\Aria-JDR-{VERSION}.zip -Algorithm SHA256).Hash
```

L'empreinte seule ne prouve pas d'où vient le fichier. Pour vérifier qu'il a bien été construit par ce dépôt :

```powershell
gh attestation verify .\Aria-JDR-{VERSION}.zip --repo ZedjeK/Aria-JDR
```
