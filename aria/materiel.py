"""Le matériel du PC : cartes graphiques NVIDIA (VRAM), mémoire vive et processeur.

Sert à choisir le modèle du MJ et ses réglages (voir optimiseur.py). L'empreinte du PC
permet de savoir quand refaire la qualification : si la carte graphique change, le
profil enregistré ne vaut plus. Inspiré du scan matériel d'Aria-Pilote.
"""

import ctypes
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

MIO = 1024 * 1024
_SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class CarteGraphique:
    nom: str
    vram_totale: int  # octets
    vram_libre: int


@dataclass(frozen=True)
class Materiel:
    cartes: tuple[CarteGraphique, ...]
    ram_totale: int | None  # octets
    coeurs: int | None

    @property
    def vram_libre(self) -> int | None:
        """La VRAM libre de la plus grosse carte (un modèle ne se répartit pas ici sur plusieurs cartes)."""
        return max((c.vram_libre for c in self.cartes), default=None)

    @property
    def vram_totale(self) -> int | None:
        return max((c.vram_totale for c in self.cartes), default=None)

    @property
    def empreinte(self) -> str:
        """Ce qui change le résultat de la qualification : la carte graphique et sa VRAM."""
        if not self.cartes:
            return "sans carte NVIDIA"
        carte = max(self.cartes, key=lambda c: c.vram_totale)
        return f"{carte.nom} ({carte.vram_totale // MIO} Mio)"


def lire_nvidia_smi(sortie: str) -> tuple[CarteGraphique, ...]:
    """Lit la sortie de « nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits »."""
    cartes = []
    for ligne in sortie.strip().splitlines():
        morceaux = [m.strip() for m in ligne.split(",")]
        if len(morceaux) != 3:
            continue
        try:
            cartes.append(CarteGraphique(morceaux[0], int(morceaux[1]) * MIO, int(morceaux[2]) * MIO))
        except ValueError:
            continue
    return tuple(cartes)


def _cartes() -> tuple[CarteGraphique, ...]:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return ()
    try:
        sortie = subprocess.run([exe, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=10, creationflags=_SANS_FENETRE).stdout
    except (OSError, subprocess.SubprocessError):
        return ()
    return lire_nvidia_smi(sortie)


class _EtatMemoire(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _ram() -> int | None:
    if sys.platform != "win32":
        return None
    etat = _EtatMemoire()
    etat.dwLength = ctypes.sizeof(etat)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(etat)):
        return None
    return etat.ullTotalPhys


def scanner() -> Materiel:
    return Materiel(_cartes(), _ram(), os.cpu_count())
