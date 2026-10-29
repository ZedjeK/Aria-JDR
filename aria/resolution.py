"""La résolution des actions : le jet de d100, ses degrés de réussite et la difficulté.

Référence : REGLES.md, section 2 (et 7.3 pour les jets en opposition).
"""

from dataclasses import dataclass
from enum import Enum, IntEnum

from aria.des import Des


class Degre(IntEnum):
    """Les degrés de réussite, du pire au meilleur. On peut les comparer : CRITIQUE > MAJEURE."""

    MALADRESSE = 0
    ECHEC = 1
    COMPLICATION = 2  # réussite avec complication (hors combat uniquement)
    REUSSITE = 3
    MAJEURE = 4
    CRITIQUE = 5

    @property
    def est_reussite(self) -> bool:
        return self >= Degre.COMPLICATION

    @property
    def libelle(self) -> str:
        return _LIBELLES_DEGRES[self]


_LIBELLES_DEGRES = {
    Degre.MALADRESSE: "maladresse",
    Degre.ECHEC: "échec",
    Degre.COMPLICATION: "réussite avec complication",
    Degre.REUSSITE: "réussite",
    Degre.MAJEURE: "réussite majeure",
    Degre.CRITIQUE: "critique",
}


class Difficulte(Enum):
    """La liste fermée des difficultés que le MJ peut choisir (REGLES.md 2.3)."""

    FACILE = 20
    NORMALE = 0
    DIFFICILE = -20
    EXTREME = -40

    @property
    def modificateur(self) -> int:
        return self.value


def calculer_degre(jet: int, valeur: int, combat: bool = False) -> Degre:
    """Donne le degré de réussite d'un jet de d100 contre une valeur finale (difficulté déjà appliquée).

    En combat, la réussite avec complication n'existe pas : elle compte comme une réussite simple.
    """
    if not 1 <= jet <= 100:
        raise ValueError(f"Un jet de d100 va de 1 à 100, pas {jet}.")

    seuil_maladresse = 100 if valeur >= 50 else 96
    if jet >= seuil_maladresse:
        return Degre.MALADRESSE

    if jet <= valeur // 5:
        degre = Degre.CRITIQUE
    elif jet <= valeur // 2:
        degre = Degre.MAJEURE
    elif jet <= valeur:
        degre = Degre.COMPLICATION if jet > valeur - 10 and not combat else Degre.REUSSITE
    else:
        degre = Degre.ECHEC

    # Un 01 est toujours une réussite, au minimum une réussite simple.
    if jet == 1 and degre < Degre.REUSSITE:
        degre = Degre.REUSSITE
    return degre


@dataclass(frozen=True)
class Resultat:
    """Le résultat complet d'un test."""

    jet: int
    valeur: int  # la valeur finale, après la difficulté
    degre: Degre
    force: bool = False  # True si c'est un jet forcé (REGLES.md 2.4)

    @property
    def reussi(self) -> bool:
        return self.degre.est_reussite

    @property
    def consequence_grave(self) -> bool:
        """Un jet forcé raté entraîne une conséquence grave."""
        return self.force and not self.reussi


def tester(
    des: Des,
    valeur: int,
    difficulte: Difficulte = Difficulte.NORMALE,
    combat: bool = False,
    modificateur: int = 0,
) -> Resultat:
    """Lance un d100 contre une compétence ou une caractéristique, avec sa difficulté.

    `modificateur` regroupe les autres bonus et malus imposés par les règles
    (couvert, blessure grave, armure, défenses multiples…), jamais choisis par le MJ.
    """
    valeur_finale = valeur + difficulte.modificateur + modificateur
    jet = des.d100()
    return Resultat(jet, valeur_finale, calculer_degre(jet, valeur_finale, combat))


def forcer(
    des: Des,
    valeur: int,
    premier: Resultat,
    difficulte: Difficulte = Difficulte.NORMALE,
    combat: bool = False,
    modificateur: int = 0,
) -> Resultat:
    """Relance un test raté, une seule fois. Si ce nouveau jet échoue, la conséquence est grave."""
    if premier.reussi:
        raise ValueError("On ne peut forcer qu'un jet raté.")
    if premier.force:
        raise ValueError("Un jet ne peut être forcé qu'une seule fois.")
    resultat = tester(des, valeur, difficulte, combat, modificateur)
    return Resultat(resultat.jet, resultat.valeur, resultat.degre, force=True)


class Issue(Enum):
    """Qui l'emporte dans un jet en opposition."""

    ATTAQUANT = "attaquant"
    DEFENSEUR = "défenseur"
    PERSONNE = "personne"


def opposer(attaque: Resultat, defense: Resultat, esquive: bool) -> Issue:
    """Compare une attaque et une défense au corps à corps (REGLES.md 7.3).

    Le meilleur degré de réussite l'emporte. En cas d'égalité, l'esquive gagne
    mais la riposte perd. Si personne ne réussit, il ne se passe rien.

    Quand le défenseur l'emporte, c'est au combat de traduire l'issue :
    une esquive évite le coup, une riposte touche l'attaquant.
    """
    attaque_ok, defense_ok = attaque.reussi, defense.reussi
    if not attaque_ok and not defense_ok:
        return Issue.PERSONNE
    if not defense_ok:
        return Issue.ATTAQUANT
    if not attaque_ok:
        return Issue.DEFENSEUR
    if attaque.degre > defense.degre:
        return Issue.ATTAQUANT
    if defense.degre > attaque.degre:
        return Issue.DEFENSEUR
    return Issue.DEFENSEUR if esquive else Issue.ATTAQUANT
