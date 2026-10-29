"""La progression : à l'usage, et avec l'XP (REGLES.md section 6)."""

from dataclasses import dataclass

from aria.des import Des
from aria.personnage import (
    CARACTERISTIQUE_MAX,
    PLAFOND_COMPETENCE,
    Caracteristique,
    DefCompetence,
    Personnage,
)
from aria.reglages import Jalon
from aria.resolution import Resultat

COUT_COMPETENCE = 1  # +5 dans une compétence
COUT_NOUVELLE_COMPETENCE = 3  # une compétence thématique (ou, plus tard, un sort)
COUT_CARACTERISTIQUE = 5  # +5 dans une caractéristique
GAIN = 5

# XP gagnée par jalon : les montants restent à définir (REGLES.md 10)
GAINS_XP = {jalon: 0 for jalon in Jalon}


class ProgressionImpossible(Exception):
    """La dépense d'XP demandée n'est pas permise."""


# --- À l'usage ----------------------------------------------------------------------------

def cocher(perso, competence: str, resultat: Resultat):
    """Coche une compétence réussie pendant la session. Appelé par le moteur à chaque jet.
    Les PNJ ne progressent pas : pour eux, rien n'est coché."""
    if isinstance(perso, Personnage) and resultat.reussi and competence in perso.competences:
        perso.competences_cochees.add(competence)


@dataclass
class Amelioration:
    competence: str
    jet: int
    avant: int
    gain: int  # 0 si le jet n'a pas dépassé la compétence

    @property
    def apres(self) -> int:
        return self.avant + self.gain


def fin_de_session(des: Des, perso: Personnage) -> list[Amelioration]:
    """Pour chaque compétence cochée : un d100, et +1d10 si le jet dépasse la compétence (plafond 95)."""
    ameliorations = []
    for competence in sorted(perso.competences_cochees):
        avant = perso.competences[competence]
        if avant >= PLAFOND_COMPETENCE:
            continue
        jet = des.d100()
        gain = 0
        if jet > avant:
            gain = min(des.jet("1d10"), PLAFOND_COMPETENCE - avant)
            perso.competences[competence] = avant + gain
        ameliorations.append(Amelioration(competence, jet, avant, gain))
    perso.competences_cochees.clear()
    return ameliorations


# --- Avec l'XP ------------------------------------------------------------------------------

def gagner_xp(perso: Personnage, jalon: Jalon) -> int:
    """Ajoute l'XP d'un jalon et renvoie le montant gagné."""
    gain = GAINS_XP[jalon]
    perso.xp += gain
    return gain


def _payer(perso: Personnage, cout: int):
    if perso.xp < cout:
        raise ProgressionImpossible(f"{perso.nom} a {perso.xp} XP, il en faut {cout}.")
    perso.xp -= cout


def ameliorer_competence(perso: Personnage, competence: str):
    """1 XP : +5 dans une compétence (plafond 95)."""
    if competence not in perso.competences:
        raise ProgressionImpossible(f"{perso.nom} ne connaît pas la compétence « {competence} ».")
    if perso.competences[competence] >= PLAFOND_COMPETENCE:
        raise ProgressionImpossible(f"« {competence} » est déjà au plafond ({PLAFOND_COMPETENCE}).")
    _payer(perso, COUT_COMPETENCE)
    perso.competences[competence] = min(PLAFOND_COMPETENCE, perso.competences[competence] + GAIN)


def apprendre_competence(perso: Personnage, competence: DefCompetence):
    """3 XP : apprendre une nouvelle compétence thématique, à sa valeur de base."""
    if competence.nom in perso.competences:
        raise ProgressionImpossible(f"{perso.nom} connaît déjà « {competence.nom} ».")
    _payer(perso, COUT_NOUVELLE_COMPETENCE)
    perso.competences[competence.nom] = competence.valeur_de_base(perso.caracteristiques)


def ameliorer_caracteristique(perso: Personnage, caracteristique: Caracteristique):
    """5 XP : +5 dans une caractéristique (plafond 90). PV, SM et PM suivent leur nouveau maximum."""
    avant = perso.caracteristiques[caracteristique]
    if avant >= CARACTERISTIQUE_MAX:
        raise ProgressionImpossible(f"{caracteristique.libelle} est déjà au plafond ({CARACTERISTIQUE_MAX}).")
    _payer(perso, COUT_CARACTERISTIQUE)
    maximums_avant = (perso.pv_max, perso.sm_max, perso.pm_max)
    perso.caracteristiques[caracteristique] = min(CARACTERISTIQUE_MAX, avant + GAIN)
    # Ce que le maximum gagne, la valeur actuelle le gagne aussi
    perso.pv += perso.pv_max - maximums_avant[0]
    if not perso.folie:
        perso.sm += perso.sm_max - maximums_avant[1]
    perso.pm += perso.pm_max - maximums_avant[2]
