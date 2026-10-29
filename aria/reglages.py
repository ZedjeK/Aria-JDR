"""Les réglages d'univers qui modulent les règles (REGLES.md 1.2)."""

from enum import Enum


class Curseur(Enum):
    """Le curseur de létalité de l'univers."""

    HEROIQUE = "héroïque"
    STANDARD = "standard"
    REALISTE = "réaliste"

    @property
    def points_destin(self) -> int:
        """Points de destin par campagne (REGLES.md 7.7)."""
        return {Curseur.HEROIQUE: 3, Curseur.STANDARD: 2, Curseur.REALISTE: 1}[self]

    @property
    def bonus_pv(self) -> int:
        """PV ajoutés à (Force + Constitution) / 10 (REGLES.md 3.2)."""
        return {Curseur.HEROIQUE: 10, Curseur.STANDARD: 5, Curseur.REALISTE: 0}[self]

    @property
    def mort_instantanee(self) -> bool:
        """Un seul coup qui inflige au moins les PV max tue net (REGLES.md 7.6)."""
        return self is Curseur.REALISTE


class Jalon(Enum):
    """Les étapes de campagne enregistrées par le code. Elles donnent de la Santé mentale
    (REGLES.md 9.5) et, plus tard, de l'XP (montants à définir)."""

    SESSION = "session jouée"
    OBJECTIF = "objectif ou quête réussis"
    ARC = "arc de campagne terminé"
    MOTIVATION = "motivation accomplie"
