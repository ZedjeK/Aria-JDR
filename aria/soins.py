"""Les soins et les repos (REGLES.md section 8)."""

from dataclasses import dataclass
from enum import Enum

from aria.des import Des
from aria.personnage import Etat, Personnage
from aria.progression import cocher
from aria.reglages import Curseur
from aria.resolution import Degre, Resultat, tester
from aria.temps import Moment, Periode

# Ce que rend un jet de soin selon son degré (même table pour les PV et la Santé mentale)
GAINS_PAR_DEGRE = {
    Degre.CRITIQUE: "2d6",
    Degre.MAJEURE: "1d6",
    Degre.REUSSITE: "1d3",
    Degre.COMPLICATION: "1d3",  # hors combat, une réussite avec complication reste une réussite
}
NUITS_GUERISON_REALISTE = 3  # « quelques jours » pour une blessure grave soignée en Réaliste


class SoinImpossible(Exception):
    """Le soin ou le repos demandé n'est pas permis par les règles à ce moment-là."""


class Repos(Enum):
    COURT = "court"  # 30 minutes
    MOYEN = "moyen"  # 1 à 2 heures
    LONG = "long"  # une nuit complète


# Part des PV max rendue par chaque repos, selon le curseur (REGLES.md 8.2)
FRACTIONS_REPOS = {
    Curseur.HEROIQUE: {Repos.COURT: 1 / 4, Repos.MOYEN: 1 / 2, Repos.LONG: 1},
    Curseur.STANDARD: {Repos.COURT: 1 / 4, Repos.MOYEN: 1 / 2, Repos.LONG: 1},
    Curseur.REALISTE: {Repos.COURT: 0, Repos.MOYEN: 1 / 4, Repos.LONG: 1 / 2},
}


def gain_selon_degre(des: Des, degre: Degre) -> int:
    """Le gain d'un jet de soin : 2d6, 1d6, 1d3, rien, ou −1 sur une maladresse."""
    if degre is Degre.MALADRESSE:
        return -1
    formule = GAINS_PAR_DEGRE.get(degre)
    return des.jet(formule) if formule else 0


def _modifier_pv(patient: Personnage, gain: int):
    patient.pv = max(0, min(patient.pv_max, patient.pv + gain))
    if patient.pv == 0 and patient.etat is Etat.ACTIF:
        patient.etat = Etat.MOURANT
    elif patient.pv > 0 and patient.etat in (Etat.INCONSCIENT, Etat.STABLE, Etat.MOURANT):
        patient.etat = Etat.ACTIF  # soigné, il reprend connaissance


@dataclass
class RapportSoin:
    patient: str
    test: Resultat
    gain: int
    pv_apres: int
    blessure_grave_soignee: bool = False


def soigner(des: Des, soigneur, patient: Personnage, moment: Moment) -> RapportSoin:
    """Un jet de Médecine sur un patient : un seul par patient et par demi-journée (REGLES.md 8.1).

    Le soigneur peut être un personnage ou un PNJ (`FichePnj` avec une valeur en Médecine).
    """
    if patient.etat is Etat.MORT:
        raise SoinImpossible(f"{patient.nom} est mort.")
    if not moment.periode.demi_journee:
        raise SoinImpossible("Les soins se font le matin ou l'après-midi, pas pendant la nuit.")
    if patient.dernier_soin_recu == moment:
        raise SoinImpossible(f"{patient.nom} a déjà reçu un jet de Médecine cette demi-journée.")
    test = tester(des, soigneur.valeur("Médecine"))
    cocher(soigneur, "Médecine", test)
    patient.dernier_soin_recu = moment
    gain = gain_selon_degre(des, test.degre)
    if test.reussi and patient.blessure_grave:
        patient.blessure_grave_soignee = True
    _modifier_pv(patient, gain)
    return RapportSoin(patient.nom, test, gain, patient.pv, patient.blessure_grave_soignee)


@dataclass
class RapportRepos:
    perso: str
    repos: Repos
    gain: int
    pv_apres: int
    blessure_grave_guerie: bool = False


def reposer(perso: Personnage, repos: Repos, moment: Moment, curseur: Curseur = Curseur.STANDARD,
            interrompu: bool = False) -> RapportRepos:
    """Un repos : court ou moyen une fois par demi-journée, long la nuit (REGLES.md 8.2).

    Un repos interrompu ne rapporte rien, mais le temps est passé : il compte comme pris.
    """
    if perso.etat in (Etat.MORT, Etat.MOURANT):
        raise SoinImpossible(f"{perso.nom} ne peut pas se reposer : il est {perso.etat.value}.")
    if repos is Repos.LONG and moment.periode is not Periode.NUIT:
        raise SoinImpossible("Le repos long se prend la nuit.")
    if repos is not Repos.LONG and moment.periode is Periode.NUIT:
        raise SoinImpossible("La nuit, c'est le repos long.")
    if perso.dernier_repos == moment:
        raise SoinImpossible(f"{perso.nom} s'est déjà reposé ({moment}).")
    perso.dernier_repos = moment
    if interrompu:
        return RapportRepos(perso.nom, repos, 0, perso.pv)

    guerie = False
    if repos is Repos.LONG and perso.blessure_grave:
        guerie = _guerir_pendant_la_nuit(perso, curseur)

    fraction = FRACTIONS_REPOS[curseur][repos]
    gain = max(1, int(perso.pv_max * fraction)) if fraction else 0
    avant = perso.pv
    _modifier_pv(perso, gain)
    return RapportRepos(perso.nom, repos, perso.pv - avant, perso.pv, guerie)


def _guerir_pendant_la_nuit(perso: Personnage, curseur: Curseur) -> bool:
    """Héroïque : toujours. Standard : si elle a été soignée. Réaliste : soignée, et après quelques nuits."""
    if curseur is Curseur.HEROIQUE:
        guerit = True
    elif not perso.blessure_grave_soignee:
        guerit = False
    elif curseur is Curseur.STANDARD:
        guerit = True
    else:
        perso.nuits_depuis_soin += 1
        guerit = perso.nuits_depuis_soin >= NUITS_GUERISON_REALISTE
    if guerit:
        perso.blessure_grave = False
        perso.blessure_grave_soignee = False
        perso.nuits_depuis_soin = 0
    return guerit
