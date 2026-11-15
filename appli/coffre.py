"""Les secrets de l'appli (jetons, mots de passe, clés), chiffrés par la protection des données de Windows (DPAPI) pour le
compte de l'utilisateur : un fichier par secret dans secrets\\ du dossier de données. Jamais en clair dans reglages.json,
le journal ni les sauvegardes.

Contre quoi cette protection ne joue pas (à dire dans le README) : un programme lancé sous le même compte Windows peut
déchiffrer ces fichiers.
"""

import ctypes
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path

from appli import donnees, identite

_EXTENSION = ".dpapi"
_NOM_VALIDE = re.compile(r"\A[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z")
# Lie le chiffrement à cette appli : un secret d'une autre appli Aria ne se déchiffre pas ici par erreur
_ENTROPIE = identite.EXE.encode("utf-8")
_SANS_INTERFACE = 0x01  # CRYPTPROTECT_UI_FORBIDDEN


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(octets: bytes) -> tuple[_Blob, "ctypes.Array"]:
    tampon = ctypes.create_string_buffer(octets, len(octets))
    return _Blob(len(octets), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char))), tampon


def _appeler(fonction: str, octets: bytes) -> bytes:
    if sys.platform != "win32":
        raise OSError("DPAPI n'existe que sous Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    entree, _tampon = _blob(octets)
    entropie, _tampon_entropie = _blob(_ENTROPIE)
    sortie = _Blob()
    api = getattr(crypt32, fonction)
    api.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                    wintypes.DWORD, ctypes.POINTER(_Blob)]
    api.restype = wintypes.BOOL
    # Les deux fonctions (chiffrer, déchiffrer) ont la même forme d'appel
    if not api(ctypes.byref(entree), None, ctypes.byref(entropie), None, None, _SANS_INTERFACE, ctypes.byref(sortie)):
        raise OSError(ctypes.get_last_error(), f"{fonction} a échoué.")
    try:
        return ctypes.string_at(sortie.pbData, sortie.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(sortie.pbData, ctypes.c_void_p))


def _dossier(racine: Path | None) -> Path:
    return (Path(racine) if racine is not None else identite.dossier_donnees()) / donnees.DOSSIER_SECRETS


def chemin(nom: str, racine: Path | None = None) -> Path:
    """Le nom devient un nom de fichier : rien qui puisse sortir du dossier des secrets."""
    if not _NOM_VALIDE.match(nom):
        raise ValueError("Nom de secret refusé : lettres minuscules, chiffres et tirets, 64 caractères au plus.")
    return _dossier(racine) / (nom + _EXTENSION)


def enregistrer(nom: str, secret: str, racine: Path | None = None) -> None:
    """Enregistre un secret sous ce nom (lettres minuscules, chiffres et tirets)."""
    fichier = chemin(nom, racine)
    fichier.parent.mkdir(parents=True, exist_ok=True)
    temporaire = fichier.with_name(fichier.name + ".tmp")
    temporaire.write_bytes(_appeler("CryptProtectData", secret.encode("utf-8")))
    os.replace(temporaire, fichier)


def lire(nom: str, racine: Path | None = None) -> str | None:
    """Le secret enregistré sous ce nom ; None s'il n'existe pas ou ne se déchiffre pas (fichier abîmé, autre compte)."""
    fichier = chemin(nom, racine)
    try:
        return _appeler("CryptUnprotectData", fichier.read_bytes()).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def supprimer(nom: str, racine: Path | None = None) -> None:
    """Supprime le secret ; sans effet s'il n'existe pas."""
    chemin(nom, racine).unlink(missing_ok=True)
