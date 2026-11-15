"""Une seule instance de l'appli par session Windows. Relancer l'exe ne démarre pas un second serveur : il rouvre l'interface
de celui qui tourne déjà, dans le navigateur.

L'instance qui tourne publie son port et son jeton dans un secret du coffre (chiffré pour le compte de l'utilisateur) ; la
suivante le lit pour ouvrir la bonne adresse.
"""

import ctypes
import json
import sys
import webbrowser
from pathlib import Path

from appli import coffre, identite

_NOM_MUTEX = f"Local\\{identite.EXE}.Instance"
_DEJA_EXISTANT = 183  # ERROR_ALREADY_EXISTS
_SECRET = "instance"


def adresse(port: int, jeton: str) -> str:
    """L'adresse qui ouvre l'interface : le jeton passe une fois dans l'adresse, puis dans un cookie."""
    return f"http://127.0.0.1:{port}/?j={jeton}"


class Instance:
    """Devient l'exemplaire de la session. Hors Windows (essais), l'appli est toujours seule."""

    def __init__(self, nom: str = _NOM_MUTEX):
        self._nom = nom
        self._poignee = None

    def prendre(self) -> bool:
        """Vrai si cet exemplaire est le premier ; faux si un autre tourne déjà."""
        if sys.platform != "win32":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        poignee = kernel32.CreateMutexW(None, True, self._nom)
        if ctypes.get_last_error() == _DEJA_EXISTANT:
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle(poignee)
            return False
        self._poignee = poignee
        return True

    def rendre(self) -> None:
        """Rend la place (fin de l'appli, ou juste avant de lancer une autre version)."""
        if self._poignee is not None and sys.platform == "win32":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.ReleaseMutex(self._poignee)
            kernel32.CloseHandle(self._poignee)
        self._poignee = None


def publier(port: int, jeton: str, racine: Path | None = None) -> None:
    coffre.enregistrer(_SECRET, json.dumps({"port": port, "jeton": jeton}), racine)


def retirer(racine: Path | None = None) -> None:
    coffre.supprimer(_SECRET, racine)


def ramener(racine: Path | None = None) -> bool:
    """Rouvre l'interface de l'exemplaire qui tourne. Faux si on ne sait pas où elle est."""
    try:
        brut = coffre.lire(_SECRET, racine)
        infos = json.loads(brut) if brut else None
        port, jeton = int(infos["port"]), str(infos["jeton"])
    except (OSError, ValueError, TypeError, KeyError):
        return False
    return webbrowser.open(adresse(port, jeton))
