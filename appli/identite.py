"""Nom de l'appli, de son exe et de son dossier de données : un seul endroit pour toute l'appli."""

import sys
import tomllib
from pathlib import Path

# Valeurs remplies par init.ps1 d'après la fiche projet
NOM = "Aria JDR"
EXE = "Aria-JDR"
DOSSIER = ".Aria-JDR"
# L'appli sert en arrière-plan (icône de notification, démarrage automatique proposé). Pas encore dans ce squelette.
EN_FOND = "false" == "true"
# L'exe propose de se ranger dans programme\ du dossier de données. Pas encore dans ce squelette.
INSTALLABLE = "false" == "true"
# Port local de l'interface web, tel que la fiche le donne. Sans port (« aucun »), le système en choisit un.
PORT_TEXTE = "8420"
PORT = int(PORT_TEXTE) if PORT_TEXTE.isdigit() else 0


def racine() -> Path:
    """Là où se trouvent pyproject.toml, docs\\ et appli\\ : le dossier du dépôt, ou celui où PyInstaller décompresse."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def dossier_donnees() -> Path:
    """%USERPROFILE%\\.Aria-JDR : données, réglages, journal, sauvegardes, secrets et cache. Jamais ailleurs."""
    return Path.home() / DOSSIER


def version() -> str:
    """X.Y.Z, lue dans pyproject.toml : la version ne vit qu'à cet endroit."""
    try:
        with open(racine() / "pyproject.toml", "rb") as fichier:
            return tomllib.load(fichier)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "0.0.0"
