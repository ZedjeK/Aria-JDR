"""Le temps de jeu, découpé en demi-journées et en nuits (REGLES.md 8.2)."""

from dataclasses import dataclass
from enum import Enum


class Periode(Enum):
    MATIN = "matin"
    APRES_MIDI = "après-midi"
    NUIT = "nuit"

    @property
    def demi_journee(self) -> bool:
        return self is not Periode.NUIT


_ORDRE = (Periode.MATIN, Periode.APRES_MIDI, Periode.NUIT)


@dataclass(frozen=True)
class Moment:
    """Un moment de la campagne : le jour et sa période. Le jour 1 est le premier jour."""

    jour: int
    periode: Periode

    def suivant(self) -> "Moment":
        """Le moment d'après : matin → après-midi → nuit → matin du jour suivant."""
        if self.periode is Periode.NUIT:
            return Moment(self.jour + 1, Periode.MATIN)
        return Moment(self.jour, _ORDRE[_ORDRE.index(self.periode) + 1])

    def __str__(self) -> str:
        return f"jour {self.jour}, {self.periode.value}"
