"""Le dossier d'une campagne : sa sauvegarde, ses souvenirs et la fiche du combat en cours.

Chaque campagne a son propre dossier dans .Aria-JDR\\campagnes : deux campagnes ne partagent jamais
leurs souvenirs. Le moteur écrit tout ; le MJ lit. Une campagne supprimée part dans
.Aria-JDR\\corbeille, d'où elle peut être restaurée.

- souvenirs.md : le journal de la campagne. Chaque combat terminé y ajoute ses moments forts
  (racontés par le MJ) et son résultat (écrit par le moteur) ; chaque scène terminée, les siens.
- pnj.md et fils.md : les PNJ rencontrés et les fils de l'histoire (voir memoire.py).
- univers.json : l'univers de la campagne, écrit une fois par le générateur (une copie figée).
- combat.md : la fiche du combat en cours, réécrite à chaque fin de round, puis supprimée
  quand le combat est versé dans les souvenirs.
"""

import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from aria import chemins

_NOM = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def racine() -> Path:
    """Le dossier des campagnes. Lu à chaque appel : les tests déplacent chemins.DONNEES."""
    return chemins.DONNEES / "campagnes"


def corbeille() -> Path:
    return chemins.DONNEES / "corbeille"


def nom_valide(texte: str) -> str | None:
    """Le nom de dossier d'une campagne (minuscules, chiffres, tirets), ou None s'il ne convient pas."""
    nom = re.sub(r"[\s_]+", "-", texte.strip().lower())
    return nom if _NOM.match(nom) else None


def noms() -> list[str]:
    """Les campagnes existantes : les dossiers qui ont un univers ou une sauvegarde."""
    if not racine().is_dir():
        return []
    return sorted(d.name for d in racine().iterdir()
                  if d.is_dir() and ((d / "univers.json").is_file() or (d / "sauvegarde.json").is_file()))


def supprimer(nom: str) -> Path:
    """Déplace la campagne dans la corbeille (rien n'est effacé). Renvoie son nouveau dossier."""
    corbeille().mkdir(parents=True, exist_ok=True)
    cible = corbeille() / f"{nom}_{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(str(racine() / nom), str(cible))
    return cible


def jetees() -> list[str]:
    """Les dossiers de la corbeille : « nom_date-heure »."""
    return sorted(d.name for d in corbeille().iterdir() if d.is_dir()) if corbeille().is_dir() else []


def restaurer(jetee: str) -> str | None:
    """Remet une campagne de la corbeille à sa place. None si une campagne du même nom existe déjà."""
    nom = jetee.rsplit("_", 1)[0]
    if (racine() / nom).exists():
        return None
    racine().mkdir(parents=True, exist_ok=True)
    shutil.move(str(corbeille() / jetee), str(racine() / nom))
    return nom


def vider_corbeille() -> int:
    """Efface pour de bon ce que contient la corbeille. Renvoie le nombre de campagnes effacées."""
    nombre = len(jetees())
    shutil.rmtree(corbeille(), ignore_errors=True)
    return nombre


@dataclass
class Campagne:
    dossier: Path

    @classmethod
    def nommee(cls, nom: str) -> "Campagne":
        return cls(racine() / nom)

    @property
    def univers(self) -> Path:
        """L'univers de la campagne, écrit une fois par le générateur : une copie figée."""
        return self.dossier / "univers.json"

    @property
    def format(self) -> Path:
        """Le type de la campagne et l'expérience de départ, choisis à sa création (voir aria.trame)."""
        return self.dossier / "campagne.json"

    @property
    def sauvegarde(self) -> Path:
        return self.dossier / "sauvegarde.json"

    @property
    def souvenirs(self) -> Path:
        return self.dossier / "souvenirs.md"

    @property
    def pnj(self) -> Path:
        return self.dossier / "pnj.md"

    @property
    def fils(self) -> Path:
        return self.dossier / "fils.md"

    @property
    def combat(self) -> Path:
        return self.dossier / "combat.md"

    def ouvrir(self):
        """Au lancement d'une partie : crée le dossier, et supprime la fiche d'un combat interrompu
        (la sauvegarde ne garde pas l'état d'un combat, cette fiche ne correspondrait plus à rien)."""
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.combat.unlink(missing_ok=True)

    def ecrire_combat(self, fiche: str):
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.combat.write_text(fiche, encoding="utf-8")

    def ajouter_souvenir(self, souvenir: str):
        """Ajoute un souvenir à la fin du fichier. Lève OSError si l'écriture échoue."""
        self.dossier.mkdir(parents=True, exist_ok=True)
        nouveau = not self.souvenirs.exists()
        with open(self.souvenirs, "a", encoding="utf-8") as fichier:
            fichier.write(("# Souvenirs de la campagne\n" if nouveau else "") + "\n" + souvenir.strip() + "\n")

    def effacer_combat(self):
        self.combat.unlink(missing_ok=True)
