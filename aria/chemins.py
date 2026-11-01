"""Où le jeu trouve et range ses fichiers, qu'il tourne depuis les sources ou depuis l'exe.

Les ressources (univers, prompts) voyagent avec le code : dans l'exe, PyInstaller les
décompresse dans un dossier temporaire, effacé à la fermeture. Tout ce que le jeu écrit
(campagnes, profil du MJ, journaux) doit survivre : c'est dans le dossier .Aria-JDR de
l'utilisateur, le même pour l'exe et pour les sources. On peut ainsi remplacer l'exe par
une nouvelle version sans toucher aux parties.
"""

import sys
from pathlib import Path

EMBARQUE = getattr(sys, "frozen", False)  # vrai dans l'exe construit par PyInstaller

if EMBARQUE:
    RESSOURCES = Path(sys._MEIPASS)
    RACINE = Path(sys.executable).resolve().parent
else:
    RESSOURCES = RACINE = Path(__file__).resolve().parent.parent

UNIVERS = RESSOURCES / "univers"
PROMPTS = RESSOURCES / "aria" / "prompts"
DONNEES = Path.home() / ".Aria-JDR"


def dossier_llm() -> Path:
    """Aria-LLM à côté du jeu (sur une clé USB, par exemple) s'il existe, sinon dans le dossier de l'utilisateur."""
    portable = RACINE / "Aria-LLM"
    return portable if portable.is_dir() else Path.home() / "Aria-LLM"
