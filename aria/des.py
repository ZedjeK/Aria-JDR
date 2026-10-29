"""Les dés du moteur : le d100 et les formules de dégâts (« 2d6+2 », « 1d8+1d4 »…).

Tous les tirages passent par un objet `Des`. En jeu, il tire au hasard.
Dans les tests, `DesTruques` renvoie des valeurs imposées à l'avance,
pour vérifier qu'un résultat donné produit bien l'effet prévu par les règles.
"""

import random
import re
from dataclasses import dataclass

# Une formule complète : des termes « NdF » ou des nombres, séparés par + ou -.
_FORMULE_VALIDE = re.compile(r"[+-]?(\d*d\d+|\d+)([+-](\d*d\d+|\d+))*")
_TERME = re.compile(r"([+-]?)(\d*d\d+|\d+)")


@dataclass(frozen=True)
class Terme:
    """Un morceau de formule : soit des dés (« 2d6 »), soit une constante (« 2 »)."""

    signe: int  # +1 ou -1
    nombre: int  # nombre de dés, ou valeur de la constante
    faces: int = 0  # 0 pour une constante


@dataclass(frozen=True)
class Formule:
    """Une formule de dés, par exemple « 2d6+2 » ou « 1d8+1d4 »."""

    termes: tuple[Terme, ...]
    texte: str

    @classmethod
    def lire(cls, texte: str) -> "Formule":
        """Transforme un texte comme « 2d6+2 » en formule. Lève ValueError s'il est mal écrit."""
        propre = texte.replace(" ", "").lower()
        if not _FORMULE_VALIDE.fullmatch(propre):
            raise ValueError(f"Formule de dés invalide : {texte!r}")
        termes = []
        for signe, morceau in _TERME.findall(propre):
            facteur = -1 if signe == "-" else 1
            if "d" in morceau:
                nombre, faces = morceau.split("d")
                nombre = int(nombre) if nombre else 1
                faces = int(faces)
                if nombre < 1 or faces < 2:
                    raise ValueError(f"Formule de dés invalide : {texte!r}")
                termes.append(Terme(facteur, nombre, faces))
            else:
                termes.append(Terme(facteur, int(morceau)))
        return cls(tuple(termes), propre)

    @property
    def minimum(self) -> int:
        """Le plus petit résultat possible."""
        return sum(self._extreme(t, minimum=True) for t in self.termes)

    @property
    def maximum(self) -> int:
        """Le plus grand résultat possible (utile pour les critiques)."""
        return sum(self._extreme(t, minimum=False) for t in self.termes)

    @staticmethod
    def _extreme(terme: Terme, minimum: bool) -> int:
        if terme.faces == 0:
            return terme.signe * terme.nombre
        # Un terme soustrait atteint son minimum quand ses dés font leur maximum, et inversement.
        petit = minimum if terme.signe > 0 else not minimum
        valeur = terme.nombre if petit else terme.nombre * terme.faces
        return terme.signe * valeur

    def __str__(self) -> str:
        return self.texte


class Des:
    """Les dés du jeu, tirés au hasard. Une `graine` rend les tirages reproductibles."""

    def __init__(self, graine: int | None = None):
        self._hasard = random.Random(graine)

    def lancer(self, faces: int) -> int:
        """Lance un dé à `faces` faces et renvoie un résultat entre 1 et `faces`."""
        return self._hasard.randint(1, faces)

    def d100(self) -> int:
        return self.lancer(100)

    def jet(self, formule: "str | Formule") -> int:
        """Lance une formule complète, par exemple « 2d6+2 »."""
        if isinstance(formule, str):
            formule = Formule.lire(formule)
        total = 0
        for terme in formule.termes:
            if terme.faces == 0:
                total += terme.signe * terme.nombre
            else:
                total += terme.signe * sum(self.lancer(terme.faces) for _ in range(terme.nombre))
        return total


class DesTruques(Des):
    """Des dés pour les tests : chaque lancer renvoie la valeur suivante de la liste imposée."""

    def __init__(self, *valeurs: int):
        super().__init__()
        self._valeurs = list(valeurs)

    def lancer(self, faces: int) -> int:
        if not self._valeurs:
            raise AssertionError("Plus de valeurs truquées : le test a lancé plus de dés que prévu.")
        valeur = self._valeurs.pop(0)
        if not 1 <= valeur <= faces:
            raise ValueError(f"Valeur truquée {valeur} impossible sur un dé à {faces} faces.")
        return valeur

    @property
    def restantes(self) -> int:
        """Le nombre de valeurs truquées pas encore utilisées."""
        return len(self._valeurs)
