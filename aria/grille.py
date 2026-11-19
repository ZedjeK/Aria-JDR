"""La carte de combat en cases hexagonales (REGLES.md 7.11) : distances, déplacements, ligne de tir et couvert.

Les cases ont des coordonnées axiales (q, r), « pointe en haut ». La carte est un rectangle de colonnes et de lignes
décalées (une ligne sur deux est décalée d'une demi-case) : `case(colonne, ligne)` donne la case, `colonne_ligne`
fait l'inverse. Le module ne connaît pas les règles du combat : il dit qui est où, combien de cases les séparent, par
où on passe et ce qui se trouve sur la ligne de tir. `aria.combat` s'en sert pour la portée et le couvert.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from heapq import heappop, heappush

from aria.equipement import Portee

Case = tuple[int, int]  # coordonnées axiales (q, r)

VOISINS: tuple[Case, ...] = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
CASES_PAR_DEPLACEMENT = 6
METRES_PAR_CASE = 1.5
PORTEE_EN_CASES = {Portee.CONTACT: 1, Portee.COURTE: 8, Portee.MOYENNE: 20, Portee.LONGUE: 40}
_DECALAGE = 1e-6  # pour départager une ligne qui passe pile entre deux cases


class Terrain(Enum):
    """Ce qui occupe une case, en plus des combattants (REGLES.md 7.11)."""

    BAS = "obstacle bas"  # caisse, muret, véhicule : couvert partiel
    BLINDE = "obstacle blindé"  # véhicule blindé, barricade renforcée : couvert lourd
    PLEIN = "obstacle plein"  # mur : coupe la ligne de tir
    DIFFICILE = "terrain difficile"  # décombres, boue, eau basse : 2 cases par case


OBSTACLES = (Terrain.BAS, Terrain.BLINDE, Terrain.PLEIN)


class Abri(Enum):
    """Ce que la ligne de tir rencontre, du moins au plus protecteur pour la cible."""

    AUCUN = 0
    PARTIEL = 1
    LOURD = 2
    COUPE = 3  # pas de tir


ABRI_DU_TERRAIN = {Terrain.BAS: Abri.PARTIEL, Terrain.BLINDE: Abri.LOURD, Terrain.PLEIN: Abri.COUPE}


# --- La géométrie ------------------------------------------------------------------------------------------------

def voisins(case: Case) -> list[Case]:
    q, r = case
    return [(q + dq, r + dr) for dq, dr in VOISINS]


def distance(a: Case, b: Case) -> int:
    """Le plus petit nombre de pas d'une case à l'autre, chaque pas allant à une case voisine."""
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def case(colonne: int, ligne: int) -> Case:
    """La case à cette colonne et cette ligne de la carte (lignes impaires décalées d'une demi-case vers la droite)."""
    return colonne - (ligne - (ligne & 1)) // 2, ligne


def colonne_ligne(c: Case) -> tuple[int, int]:
    q, r = c
    return q + (r - (r & 1)) // 2, r


def _arrondir(fq: float, fr: float) -> Case:
    fs = -fq - fr
    q, r, s = round(fq), round(fr), round(fs)
    eq, er, es = abs(q - fq), abs(r - fr), abs(s - fs)
    if eq > er and eq > es:
        q = -r - s
    elif er > es:
        r = -q - s
    return q, r


def ligne(a: Case, b: Case) -> list[set[Case]]:
    """Les cases que traverse la ligne droite entre les centres de a et b, pas à pas, a et b compris. À chaque pas,
    un ensemble : une case, ou deux quand la ligne passe pile entre elles."""
    n = distance(a, b)
    if n == 0:
        return [{a}]
    pas = []
    for i in range(n + 1):
        t = i / n
        fq, fr = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        pas.append({_arrondir(fq + _DECALAGE, fr + 2 * _DECALAGE), _arrondir(fq - _DECALAGE, fr - 2 * _DECALAGE)})
    return pas


def portee_en_cases(portee: Portee) -> int:
    return PORTEE_EN_CASES[portee]


# --- La carte ----------------------------------------------------------------------------------------------------

@dataclass
class Carte:
    """Une carte de combat : ses dimensions, ses obstacles et la position de chaque combattant.

    `allies(a, b)` dit si deux combattants sont du même côté : on traverse un allié, jamais un ennemi. Un combattant
    à terre ou hors de combat ne bloque pas le passage, mais on ne s'arrête pas sur sa case."""

    largeur: int
    hauteur: int
    terrain: dict[Case, Terrain] = field(default_factory=dict)
    positions: dict = field(default_factory=dict)  # Combattant -> Case
    lieu: str = ""  # le gabarit dont elle vient (aria.carte_combat)
    bords: dict[str, int] = field(default_factory=dict)  # le côté (« joueurs », « ennemis ») -> la colonne de son bord

    def cases(self) -> list[Case]:
        return [case(colonne, rang) for rang in range(self.hauteur) for colonne in range(self.largeur)]

    def cases_du_bord(self) -> list[Case]:
        """Les cases praticables au bord de la carte : par là, on la quitte (fuir)."""
        return [c for c in self.cases() if self.praticable(c)
                and (colonne_ligne(c)[0] in (0, self.largeur - 1) or colonne_ligne(c)[1] in (0, self.hauteur - 1))]

    def libres(self) -> list[Case]:
        """Les cases praticables où personne ne se tient."""
        prises = set(self.positions.values())
        return [c for c in self.cases() if self.praticable(c) and c not in prises]

    def relie(self, a: Case, b: Case) -> bool:
        """On peut aller de a à b à pied, sans compter les combattants (le terrain difficile ralentit, il ne bloque pas)."""
        vus, pile = {a}, [a]
        while pile:
            c = pile.pop()
            if c == b:
                return True
            for v in voisins(c):
                if v not in vus and self.praticable(v):
                    vus.add(v)
                    pile.append(v)
        return False

    def dans(self, c: Case) -> bool:
        colonne, rang = colonne_ligne(c)
        return 0 <= colonne < self.largeur and 0 <= rang < self.hauteur

    def praticable(self, c: Case) -> bool:
        """Une case où l'on peut mettre le pied (sans compter qui s'y trouve)."""
        return self.dans(c) and self.terrain.get(c) not in OBSTACLES

    def cout(self, c: Case) -> int:
        return 2 if self.terrain.get(c) is Terrain.DIFFICILE else 1

    def position(self, combattant) -> Case:
        if combattant not in self.positions:
            raise KeyError(f"{combattant.nom} n'est pas sur la carte.")
        return self.positions[combattant]

    def occupants(self, c: Case) -> list:
        return [x for x, p in self.positions.items() if p == c]

    def placer(self, combattant, c: Case):
        """Pose un combattant sur une case libre et praticable (à l'ouverture, ou quand il rejoint le combat)."""
        if not self.praticable(c):
            raise ValueError(f"La case {colonne_ligne(c)} n'est pas praticable.")
        if any(x is not combattant for x in self.occupants(c)):
            raise ValueError(f"La case {colonne_ligne(c)} est déjà prise.")
        self.positions[combattant] = c

    def retirer(self, combattant):
        self.positions.pop(combattant, None)

    def atteignables(self, combattant, allies: Callable, debout: Callable, pas: int = CASES_PAR_DEPLACEMENT) -> dict[Case, int]:
        """Les cases où il peut finir un déplacement, avec ce qu'elles coûtent (REGLES.md 7.11) : `pas` cases au plus,
        2 par case de terrain difficile, sans traverser d'obstacle ni d'ennemi debout ; une case occupée se traverse
        (allié, ou combattant à terre) mais on ne s'y arrête pas. `debout(x)` : x bloque encore le passage."""
        depart = self.position(combattant)
        couts, file = {depart: 0}, [(0, depart)]
        while file:
            cout, c = heappop(file)
            if cout > couts.get(c, cout):
                continue
            for v in voisins(c):
                if not self.praticable(v):
                    continue
                if any(debout(x) and not allies(combattant, x) for x in self.occupants(v) if x is not combattant):
                    continue
                total = cout + self.cout(v)
                if total <= pas and total < couts.get(v, pas + 1):
                    couts[v] = total
                    heappush(file, (total, v))
        return {c: k for c, k in couts.items() if c != depart and not [x for x in self.occupants(c) if x is not combattant]}

    def deplacer(self, combattant, vers: Case, allies: Callable, debout: Callable, pas: int = CASES_PAR_DEPLACEMENT) -> int:
        """Le déplace s'il peut atteindre cette case ; renvoie le nombre de cases parcourues (coût du terrain compris)."""
        possibles = self.atteignables(combattant, allies, debout, pas)
        if vers not in possibles:
            raise ValueError(f"La case {colonne_ligne(vers)} est hors d'atteinte en un déplacement.")
        self.positions[combattant] = vers
        return possibles[vers]

    def ecart(self, a, b) -> int:
        return distance(self.position(a), self.position(b))

    def abri(self, tireur, cible) -> Abri:
        """Ce que la ligne de tir rencontre entre le tireur et la cible (REGLES.md 7.11) : le plus protecteur des
        obstacles traversés ; entre deux cases, celle qui protège le plus. Un obstacle bas ou blindé collé au tireur
        ne compte pas (il tire par-dessus) ; un obstacle plein coupe toujours la ligne."""
        return self.abri_entre(self.position(tireur), self.position(cible))

    def abri_entre(self, a: Case, b: Case) -> Abri:
        """Comme `abri`, entre deux cases : pour savoir ce que donnerait une position avant de s'y rendre."""
        pire = Abri.AUCUN
        for cases in ligne(a, b)[1:-1]:
            for c in cases:
                terrain = self.terrain.get(c)
                if terrain not in ABRI_DU_TERRAIN:
                    continue
                abri = ABRI_DU_TERRAIN[terrain]
                if abri is not Abri.COUPE and distance(c, a) == 1:
                    continue
                if abri.value > pire.value:
                    pire = abri
        return pire

    def derriere(self, source, victime) -> Case | None:
        """La case juste derrière la victime, à l'opposé de la source qui la touche au contact ; None si elles ne
        sont pas voisines."""
        s, v = self.position(source), self.position(victime)
        if distance(s, v) != 1:
            return None
        return 2 * v[0] - s[0], 2 * v[1] - s[1]
