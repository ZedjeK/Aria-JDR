"""Où le jeu trouve et range ses fichiers, qu'il tourne depuis les sources ou depuis l'exe.

Les ressources (univers, prompts) voyagent avec le code : dans l'exe, PyInstaller les
décompresse dans un dossier temporaire, effacé à la fermeture. Les données du joueur
(parties/) doivent survivre : elles vont à côté de l'exe, ou à la racine du dépôt.
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
PARTIES = RACINE / "parties"


def dossier_llm() -> Path:
    """Aria-LLM à côté du jeu (sur une clé USB, par exemple) s'il existe, sinon dans le dossier de l'utilisateur."""
    portable = RACINE / "Aria-LLM"
    return portable if portable.is_dir() else Path.home() / "Aria-LLM"
