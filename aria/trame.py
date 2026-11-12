"""La trame d'une campagne (REGLES.md 14) : son type, et l'expérience de départ du personnage.

Le type fixe la longueur de la trame (ses actes et ses missions principales), la vitesse de progression et
la façon d'ouvrir. Il est choisi à la création de la campagne, avec l'expérience de départ, et rangé dans
le dossier de la campagne (campagne.json) : la création du personnage, l'amorce puis la trame le relisent.
"""

import json
from dataclasses import asdict, dataclass

from aria.campagne import Campagne
from aria.personnage import AGUERRI, CRANS, DEBUTANT, VETERAN  # noqa: F401 (réexportés pour le menu)

AU_COEUR, PLAN, QUOTIDIEN = "au cœur du problème", "la situation lance le plan", "le quotidien"
CONSIGNES = {
    AU_COEUR: "L'ouverture se fait au cœur du problème : le commanditaire ou la menace est déjà dans la "
              "situation, et le personnage doit réagir tout de suite.",
    PLAN: "",
    QUOTIDIEN: "L'ouverture se fait sur le quotidien du personnage : la situation montre sa vie ordinaire, et le "
               "plan n'y apparaît que comme un détail qui cloche. Le vrai problème viendra plus tard.",
}


@dataclass(frozen=True)
class TypeCampagne:
    nom: str
    actes: tuple[int, ...]  # les missions principales de chaque acte
    xp: int  # par mission principale réussie
    depart: str  # l'expérience de départ conseillée
    ouverture: str
    description: str
    sans_fin: bool = False  # un arc terminé en ouvre un autre

    @property
    def consigne(self) -> str:
        """Ce que l'amorce doit savoir de l'ouverture (vide : l'amorce ordinaire)."""
        return CONSIGNES[self.ouverture]

    @property
    def principales(self) -> int:
        return sum(self.actes)


CONTRAT, COURTE, STANDARD, LONGUE, SANS_FIN = "contrat", "courte", "standard", "longue", "sans fin"
TYPES = {t.nom: t for t in (
    TypeCampagne(CONTRAT, (1,), 0, AGUERRI, AU_COEUR, "une seule mission, une soirée"),
    TypeCampagne(COURTE, (1, 2, 1), 3, AGUERRI, AU_COEUR, "3 actes, 4 missions principales"),
    TypeCampagne(STANDARD, (2, 4, 2), 2, DEBUTANT, PLAN, "3 actes, 8 missions principales"),
    TypeCampagne(LONGUE, (2, 3, 4, 3, 2), 1, DEBUTANT, QUOTIDIEN, "5 actes, 14 missions principales"),
    TypeCampagne(SANS_FIN, (2, 4, 2), 1, DEBUTANT, QUOTIDIEN, "des arcs qui s'enchaînent, sans dernière page",
                 sans_fin=True),
)}


@dataclass
class Format:
    """Ce qui a été choisi à la création de la campagne."""

    type: str = STANDARD
    cran: str = DEBUTANT


def lire_format(campagne: Campagne) -> Format:
    """Le format de la campagne ; celui par défaut si elle n'en a pas (une campagne d'avant) ou s'il est abîmé."""
    try:
        donnees = json.loads(campagne.format.read_text(encoding="utf-8"))
        format = Format(donnees["type"], donnees["cran"])
    except (OSError, ValueError, KeyError, TypeError):
        return Format()
    return format if format.type in TYPES and format.cran in CRANS else Format()


def ecrire_format(campagne: Campagne, format: Format):
    campagne.dossier.mkdir(parents=True, exist_ok=True)
    campagne.format.write_text(json.dumps(asdict(format), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
