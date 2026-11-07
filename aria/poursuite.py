"""Les poursuites (REGLES.md 12.3) : la distance en crans, les événements de la route, les zones.

Chaque round, le moteur tire un événement dans la colonne de la zone, fait passer les obstacles,
puis lance un jet opposé de Pilotage entre le fuyard et chaque poursuivant. Le MJ raconte.
"""

from dataclasses import dataclass, field
from enum import Enum

from aria.des import Des
from aria.resolution import Degre, Difficulte, Resultat, tester
from aria.vehicules import (
    CAPRICIEUX,
    DRESSAGE,
    PILOTAGE,
    TOUT_TERRAIN,
    Engin,
    RapportAccident,
    accident,
    cocher_pour,
    valeur_pilotage,
)

DISTANCES = ("au contact", "proche", "loin", "semé")
AU_CONTACT, PROCHE, LOIN, SEME = range(4)
BONUS_PAR_CRAN = 10
BONUS_CHANCE = 10
BONUS_NITRO = 10
MALUS_SANS_TOUT_TERRAIN = -20
ROUNDS_PAR_ZONE = 4  # une poursuite qui dure change d'elle-même de zone


class Evenement(Enum):
    DEGAGEE = "voie dégagée"
    LIGNE_DROITE = "ligne droite"
    CIRCULATION = "circulation dense"
    OBSTACLE = "obstacle soudain"
    VIRAGE = "virage serré"
    ACCIDENTE = "terrain accidenté"
    RACCOURCI = "raccourci"
    BARRAGE = "barrage"
    CHANCE = "coup de chance"


_D, _LD, _C, _O, _V, _A, _R, _B, _CH = Evenement
# La table des événements (1d10), une colonne par zone
ZONES = {
    "Centre-ville": (_D, _LD, _C, _C, _C, _O, _V, _R, _B, _CH),
    "Banlieue": (_D, _D, _LD, _LD, _C, _O, _V, _R, _B, _CH),
    "Bas-quartiers": (_D, _C, _O, _O, _V, _R, _R, _B, _B, _CH),
    "Zone industrielle": (_D, _LD, _LD, _C, _O, _O, _V, _R, _B, _CH),
    "Autoroute": (_D, _D, _LD, _LD, _LD, _LD, _C, _O, _B, _CH),
    "Hors de la ville": (_D, _LD, _LD, _LD, _A, _A, _A, _O, _R, _CH),
}
VOISINES = {
    "Centre-ville": ("Banlieue", "Bas-quartiers", "Autoroute"),
    "Banlieue": ("Centre-ville", "Autoroute", "Hors de la ville"),
    "Bas-quartiers": ("Centre-ville", "Zone industrielle"),
    "Zone industrielle": ("Bas-quartiers", "Autoroute"),
    "Autoroute": ("Centre-ville", "Banlieue", "Zone industrielle", "Hors de la ville"),
    "Hors de la ville": ("Banlieue", "Autoroute"),
}
OBSTACLES = {
    Evenement.OBSTACLE: Difficulte.NORMALE,
    Evenement.VIRAGE: Difficulte.DIFFICILE,
    Evenement.ACCIDENTE: Difficulte.DIFFICILE,
    Evenement.BARRAGE: Difficulte.DIFFICILE,
}


class PoursuiteImpossible(ValueError):
    """Ce que les règles de la poursuite ne permettent pas."""


@dataclass
class Conducteur:
    """Un participant : celui qui conduit (un combattant, avec son armure) et son véhicule ;
    sans véhicule, il court (l'Athlétisme, sans vitesse ni maniabilité)."""

    identifiant: str
    pilote: object
    engin: Engin | None = None

    @property
    def nom(self) -> str:
        return self.pilote.nom

    @property
    def cran(self) -> int:
        return self.engin.cran if self.engin else -1  # à pied, plus lent que tout véhicule

    def valeur(self) -> int:
        return valeur_pilotage(self.pilote, self.engin)

    @property
    def competence(self) -> str:
        return PILOTAGE if self.engin else "Athlétisme"

    def a(self, propriete: str) -> bool:
        return bool(self.engin) and propriete in self.engin.modele.proprietes_totales


@dataclass
class Obstacle:
    qui: str
    test: Resultat
    effet: str


@dataclass
class Duel:
    """Le jet opposé entre le fuyard et un poursuivant."""

    poursuivant: str
    fuyard_test: Resultat | None
    poursuivant_test: Resultat | None
    gagnant: str | None  # le nom du gagnant, ou None
    crans: int
    distance: str = ""
    effets: list[str] = field(default_factory=list)


@dataclass
class RapportRound:
    round: int
    zone: str
    de: int
    evenement: Evenement
    obstacles: list[Obstacle] = field(default_factory=list)
    duels: list[Duel] = field(default_factory=list)
    accidents: list[RapportAccident] = field(default_factory=list)
    nouvelle_zone: str | None = None
    issue: str | None = None
    effets: list[str] = field(default_factory=list)


@dataclass
class Poursuite:
    fuyard: Conducteur
    poursuivants: list[Conducteur]
    zone: str
    distances: dict[str, int] = field(default_factory=dict)
    round: int = 0
    rounds_dans_la_zone: int = 0
    abandons: set[str] = field(default_factory=set)
    issue: str | None = None  # « semé » ou « rattrapé » quand elle est finie

    def __post_init__(self):
        if self.zone not in ZONES:
            raise PoursuiteImpossible(f"Zone inconnue « {self.zone} ». Zones : {', '.join(ZONES)}.")
        if not self.poursuivants:
            raise PoursuiteImpossible("Une poursuite demande au moins un poursuivant.")
        for c in [self.fuyard, *self.poursuivants]:
            if c.engin and c.engin.etat in ("épave", "mourante"):
                raise PoursuiteImpossible(f"{c.engin.nom} ne peut plus avancer ({c.engin.etat}).")
        for p in self.poursuivants:
            self.distances.setdefault(p.identifiant, PROCHE)

    def actifs(self) -> list[Conducteur]:
        return [p for p in self.poursuivants
                if self.distances[p.identifiant] != SEME and p.identifiant not in self.abandons]

    def distance(self, poursuivant: str) -> str:
        return DISTANCES[self.distances[poursuivant]]

    def abandonner(self, identifiant: str):
        if identifiant not in self.distances:
            raise PoursuiteImpossible(f"« {identifiant} » ne poursuit personne.")
        self.abandons.add(identifiant)
        if not self.actifs():
            self.issue = "semé"

    # --- Un round ---------------------------------------------------------------------------

    def jouer_round(self, des: Des, difficulte: Difficulte = Difficulte.NORMALE, nitro: set[str] = frozenset(),
                    raccourci: bool = False, vers_zone: str | None = None, blesser=None) -> RapportRound:
        """`nitro` : ceux qui allument leur nitro ce round ; `raccourci` : le fuyard tente le raccourci
        s'il se présente ; `vers_zone` : où le fuyard entraîne la poursuite sur une réussite majeure ;
        `blesser(victime, degats)` : comment un accident blesse les occupants."""
        if self.issue:
            raise PoursuiteImpossible(f"La poursuite est finie : {self.issue}.")
        if vers_zone is not None and vers_zone not in VOISINES[self.zone]:
            raise PoursuiteImpossible(f"Depuis {self.zone}, on rejoint seulement : {', '.join(VOISINES[self.zone])}.")
        self.round += 1
        self.rounds_dans_la_zone += 1
        de = des.lancer(10)
        evenement = ZONES[self.zone][de - 1]
        r = RapportRound(self.round, self.zone, de, evenement)
        actifs = self.actifs()
        decalage = {p.identifiant: 0 for p in actifs}  # + : la distance augmente
        bloques, accidentes = set(), []

        def perdre_un_cran(c: Conducteur):
            if c is self.fuyard:
                for p in actifs:
                    decalage[p.identifiant] -= 1
            else:
                decalage[c.identifiant] += 1

        def accidente(c: Conducteur):
            if all(a is not c for a in accidentes):
                accidentes.append(c)

        # Les obstacles de la route
        if evenement in OBSTACLES:
            for c in [self.fuyard, *actifs]:
                malus = MALUS_SANS_TOUT_TERRAIN if evenement is Evenement.ACCIDENTE and c.engin and not c.a(TOUT_TERRAIN) else 0
                test = self._tester(des, c, OBSTACLES[evenement], malus)
                if test.degre is Degre.MALADRESSE:
                    accidente(c)
                    effet = "accident"
                elif not test.reussi:
                    if evenement is Evenement.BARRAGE:
                        bloques.add(c.identifiant)
                        effet = "bloqué : il ne bouge pas ce round"
                    else:
                        perdre_un_cran(c)
                        effet = "perd un cran"
                else:
                    effet = "passe"
                r.obstacles.append(Obstacle(c.nom, test, effet))
                if (c.engin and c.engin.modele.monture and evenement in (Evenement.OBSTACLE, Evenement.BARRAGE)
                        and test.degre is not Degre.MALADRESSE):
                    panique = self._tester(des, c, Difficulte.FACILE if c.a(DRESSAGE) else Difficulte.NORMALE)
                    if not panique.reussi:
                        perdre_un_cran(c)
                    r.obstacles.append(Obstacle(c.nom, panique, "la monture panique : perd un cran"
                                                if not panique.reussi else "garde sa monture en main"))

        # Le raccourci, que seul le fuyard peut tenter
        if evenement is Evenement.RACCOURCI and raccourci and self.fuyard not in accidentes:
            test = self._tester(des, self.fuyard, Difficulte.DIFFICILE)
            if test.degre is Degre.MALADRESSE:
                accidente(self.fuyard)
            for p in actifs:
                decalage[p.identifiant] += 1 if test.reussi else -1
            r.obstacles.append(Obstacle(self.fuyard.nom, test, "raccourci : un cran de plus" if test.reussi
                                        else "raccourci raté : un cran de moins"))

        # Les jets opposés, un par poursuivant
        nitro_fuyard = self._nitro(self.fuyard, nitro)
        zone_choisie, paires = None, []
        for p in actifs:
            if any(a is self.fuyard for a in accidentes):
                break
            if any(a is p for a in accidentes):
                continue
            duel = self._duel(des, p, evenement, difficulte, nitro_fuyard, self._nitro(p, nitro), bloques)
            nitro_fuyard = 0  # la nitro ne vaut que pour un seul jet
            for c, test in ((self.fuyard, duel.fuyard_test), (p, duel.poursuivant_test)):
                if test and test.degre is Degre.MALADRESSE:
                    accidente(c)
            if duel.gagnant == self.fuyard.nom:
                if duel.crans == 2 and vers_zone and zone_choisie is None:
                    zone_choisie, duel.crans = vers_zone, 1
                    duel.effets.append(f"entraîne la poursuite vers : {vers_zone}")
                decalage[p.identifiant] += duel.crans
            elif duel.gagnant:
                decalage[p.identifiant] -= duel.crans
            r.duels.append(duel)
            paires.append((duel, p))

        for p in actifs:
            self.distances[p.identifiant] = max(AU_CONTACT, min(SEME, self.distances[p.identifiant]
                                                                + decalage[p.identifiant]))

        # Les accidents : l'accidenté a perdu
        for c in accidentes:
            if c.engin and c.engin.modele.defaut == CAPRICIEUX:
                r.effets.append(f"{c.nom} : le moteur de {c.engin.nom} cale.")
            elif c.engin:
                r.accidents.append(accident(des, c.engin, [c.pilote], blesser))
            else:
                r.effets.append(f"{c.nom} chute.")
            if c is self.fuyard:
                for p in actifs:
                    self.distances[p.identifiant] = AU_CONTACT
                self.issue = "rattrapé"
            else:
                self.distances[c.identifiant] = SEME
        for duel, p in paires:
            duel.distance = self.distance(p.identifiant)

        # Changer de zone
        if zone_choisie:
            r.nouvelle_zone = zone_choisie
        elif self.rounds_dans_la_zone >= ROUNDS_PAR_ZONE:
            voisines = VOISINES[self.zone]
            r.nouvelle_zone = voisines[des.lancer(len(voisines)) - 1]
        if r.nouvelle_zone:
            self.zone, self.rounds_dans_la_zone = r.nouvelle_zone, 0
        if not self.issue and not self.actifs():
            self.issue = "semé"
        r.issue = self.issue
        return r

    def _tester(self, des: Des, c: Conducteur, difficulte: Difficulte, modificateur: int = 0) -> Resultat:
        test = tester(des, c.valeur(), difficulte, combat=True, modificateur=modificateur)
        cocher_pour(c.pilote, c.competence, test)
        return test

    @staticmethod
    def _nitro(c: Conducteur, nitro: set[str]) -> int:
        if c.identifiant not in nitro:
            return 0
        if not (c.engin and c.engin.modele.nitro):
            raise PoursuiteImpossible(f"{c.nom} n'a pas de nitro.")
        if c.engin.nitro_utilisee:
            raise PoursuiteImpossible(f"{c.nom} a déjà brûlé sa nitro dans cette scène.")
        c.engin.nitro_utilisee = True
        return BONUS_NITRO

    def _duel(self, des: Des, p: Conducteur, evenement: Evenement, difficulte: Difficulte, nitro_fuyard: int,
              nitro_poursuivant: int, bloques: set[str]) -> Duel:
        f = self.fuyard
        bloque_f, bloque_p = f.identifiant in bloques, p.identifiant in bloques
        if bloque_f and bloque_p:
            return Duel(p.nom, None, None, None, 0, effets=["les deux sont bloqués"])
        if bloque_f or bloque_p:
            gagnant = p if bloque_f else f
            return Duel(p.nom, None, None, gagnant.nom, 1, effets=[f"{(f if bloque_f else p).nom} est bloqué"])

        mod_f, mod_p = nitro_fuyard, nitro_poursuivant
        # La vitesse : +10 par cran d'écart au plus rapide (doublé en ligne droite, annulé dans la circulation)
        ecart = abs(f.cran - p.cran) * BONUS_PAR_CRAN
        ecart *= {Evenement.LIGNE_DROITE: 2, Evenement.CIRCULATION: 0}.get(evenement, 1)
        if f.cran > p.cran:
            mod_f += ecart
        elif p.cran > f.cran:
            mod_p += ecart
        if evenement is Evenement.CIRCULATION:  # la maniabilité doublée
            mod_f += f.engin.maniabilite if f.engin else 0
            mod_p += p.engin.maniabilite if p.engin else 0
        if evenement is Evenement.CHANCE:  # pour celui qui est en train de perdre
            if self.distances[p.identifiant] <= PROCHE:
                mod_f += BONUS_CHANCE
            else:
                mod_p += BONUS_CHANCE
        test_f = tester(des, f.valeur(), difficulte, combat=True, modificateur=mod_f)
        cocher_pour(f.pilote, f.competence, test_f)
        test_p = tester(des, p.valeur(), difficulte, combat=True, modificateur=mod_p)
        cocher_pour(p.pilote, p.competence, test_p)
        duel = Duel(p.nom, test_f, test_p, None, 0)
        if Degre.MALADRESSE in (test_f.degre, test_p.degre):
            return duel
        if test_f.reussi or test_p.reussi:
            degre_f = test_f.degre if test_f.reussi else Degre.ECHEC
            degre_p = test_p.degre if test_p.reussi else Degre.ECHEC
            if degre_f != degre_p:
                gagnant, degre = (f, degre_f) if degre_f > degre_p else (p, degre_p)
                duel.gagnant, duel.crans = gagnant.nom, 2 if degre >= Degre.MAJEURE else 1
        return duel
