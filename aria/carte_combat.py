"""Le générateur des cartes de combat (REGLES.md 7.11) : six gabarits de lieu, la densité d'obstacles selon le décor,
et le placement des deux camps à l'ouverture.

Le MJ choisit seulement le gabarit et le décor, dans des listes fermées ; le code dessine la carte et place tout le
monde. Tout est tiré avec les dés de la session : la même graine donne la même carte. Une carte où les deux camps ne
peuvent pas se rejoindre, ou où ils ne tiennent pas, est retirée.
"""

from collections.abc import Callable
from dataclasses import dataclass

from aria.combat import Decor
from aria.des import Des
from aria.grille import Carte, Case, Terrain, case, colonne_ligne, distance

RUELLE, ENTREPOT, BAR, TOIT, PARKING, COULOIR = "ruelle", "entrepôt", "bar", "toit", "parking", "couloir"
LIEUX = (RUELLE, ENTREPOT, BAR, TOIT, PARKING, COULOIR)
LIEU_PAR_DEFAUT = RUELLE

ECART_DE_DEPART = 12  # entre les deux camps, au moins (REGLES.md 7.11)
ECART_EMBUSCADE = 6  # le camp qui surprend commence plus près
ECART_EXIGU = 8  # couloir, bar
# La part des cases libres couvertes d'obstacles, selon le décor ; en fortifié, un sur trois est blindé
DENSITE = {Decor.DEGAGE: 0.015, Decor.ENCOMBRE: 0.07, Decor.FORTIFIE: 0.09}
PART_BLINDEE = 3
ESSAIS = 30
JOUEURS, ENNEMIS = "joueurs", "ennemis"


def _entre(des: Des, mini: int, maxi: int) -> int:
    return mini + des.lancer(maxi - mini + 1) - 1


@dataclass(frozen=True)
class Gabarit:
    nom: str
    largeur: tuple[int, int]
    hauteur: tuple[int, int]
    exigu: bool
    structure: Callable[[Carte, Des], None]  # les murs et le mobilier propres au lieu, avant les obstacles du décor


def _mur(carte: Carte, colonnes, rangs, terrain: Terrain = Terrain.PLEIN):
    for rang in rangs:
        for colonne in colonnes:
            c = case(colonne, rang)
            if carte.dans(c):
                carte.terrain[c] = terrain


def _ouvrir(carte: Carte, colonnes, rangs):
    for rang in rangs:
        for colonne in colonnes:
            carte.terrain.pop(case(colonne, rang), None)


def _ruelle(carte: Carte, des: Des):
    """Deux façades de part et d'autre, quelques renfoncements de porte, des bennes et des poubelles."""
    largeur, hauteur = carte.largeur, carte.hauteur
    _mur(carte, range(largeur), (0, hauteur - 1))
    for _ in range(_entre(des, 2, 4)):  # des portes en retrait
        colonne = _entre(des, 3, largeur - 4)
        _ouvrir(carte, (colonne,), (0 if des.lancer(2) == 1 else hauteur - 1,))
    for _ in range(_entre(des, 2, 3)):  # des bennes contre un mur
        colonne, rang = _entre(des, 4, largeur - 6), 1 if des.lancer(2) == 1 else hauteur - 2
        _mur(carte, (colonne, colonne + 1), (rang,), Terrain.BAS)


def _entrepot(carte: Carte, des: Des):
    """Quatre murs percés de portes, des rangées de rayonnages, des caisses."""
    largeur, hauteur = carte.largeur, carte.hauteur
    _mur(carte, range(largeur), (0, hauteur - 1))
    _mur(carte, (0, largeur - 1), range(hauteur))
    milieu = hauteur // 2
    _ouvrir(carte, (0, largeur - 1), (milieu - 1, milieu, milieu + 1))
    for colonne in range(6, largeur - 6, 5):  # des rayonnages, avec une allée au milieu
        _mur(carte, (colonne,), [r for r in range(3, hauteur - 3) if abs(r - milieu) > 1])


def _bar(carte: Carte, des: Des):
    """Une salle fermée, un comptoir, des tables."""
    largeur, hauteur = carte.largeur, carte.hauteur
    _mur(carte, range(largeur), (0, hauteur - 1))
    _mur(carte, (0, largeur - 1), range(hauteur))
    milieu = hauteur // 2
    _ouvrir(carte, (0, largeur - 1), (milieu,))
    colonne = _entre(des, largeur // 2 - 2, largeur // 2 + 2)
    _mur(carte, (colonne,), range(2, hauteur // 2), Terrain.BAS)  # le comptoir
    for _ in range(_entre(des, 3, 5)):
        _mur(carte, (_entre(des, 3, largeur - 4),), (_entre(des, 2, hauteur - 3),), Terrain.BAS)


def _toit(carte: Carte, des: Des):
    """Pas de murs : des blocs de climatisation, des cheminées, une cage d'escalier."""
    largeur, hauteur = carte.largeur, carte.hauteur
    for _ in range(_entre(des, 3, 5)):
        colonne, rang = _entre(des, 3, largeur - 5), _entre(des, 2, hauteur - 4)
        _mur(carte, (colonne, colonne + 1), (rang, rang + 1), Terrain.BAS)
    for _ in range(_entre(des, 2, 4)):
        _mur(carte, (_entre(des, 3, largeur - 4),), (_entre(des, 2, hauteur - 3),))
    colonne, rang = _entre(des, largeur // 3, 2 * largeur // 3), _entre(des, 2, hauteur - 5)
    _mur(carte, (colonne, colonne + 1, colonne + 2), (rang, rang + 1, rang + 2))


def _parking(carte: Carte, des: Des):
    """Un grand espace ouvert, des piliers réguliers, des voitures garées."""
    largeur, hauteur = carte.largeur, carte.hauteur
    for colonne in range(5, largeur - 3, 7):
        for rang in range(3, hauteur - 2, 6):
            _mur(carte, (colonne,), (rang,))
    for _ in range(_entre(des, 5, 9)):
        colonne, rang = _entre(des, 4, largeur - 6), _entre(des, 1, hauteur - 2)
        _mur(carte, (colonne, colonne + 1), (rang,), Terrain.BAS)


def _couloir(carte: Carte, des: Des):
    """Un couloir étroit entre deux murs, des portes, quelques renfoncements."""
    largeur, hauteur = carte.largeur, carte.hauteur
    _mur(carte, range(largeur), (0, hauteur - 1))
    for _ in range(_entre(des, 2, 3)):
        colonne = _entre(des, 4, largeur - 5)
        _ouvrir(carte, (colonne,), (0 if des.lancer(2) == 1 else hauteur - 1,))


GABARITS = {
    RUELLE: Gabarit(RUELLE, (26, 34), (9, 11), False, _ruelle),
    ENTREPOT: Gabarit(ENTREPOT, (24, 30), (16, 20), False, _entrepot),
    BAR: Gabarit(BAR, (16, 20), (11, 13), True, _bar),
    TOIT: Gabarit(TOIT, (20, 28), (14, 18), False, _toit),
    PARKING: Gabarit(PARKING, (30, 36), (18, 22), False, _parking),
    COULOIR: Gabarit(COULOIR, (24, 30), (5, 6), True, _couloir),
}


def ecart_de_depart(lieu: str, embuscade: bool) -> int:
    """La distance entre les deux camps à l'ouverture (REGLES.md 7.11)."""
    if embuscade:
        return ECART_EMBUSCADE
    return ECART_EXIGU if GABARITS[lieu].exigu else ECART_DE_DEPART


def _decor(carte: Carte, decor: Decor, des: Des):
    """Les obstacles du décor sur les cases encore libres : caisses, épaves, barricades ; et un peu de terrain difficile."""
    libres = [c for c in carte.cases() if carte.praticable(c) and 1 <= colonne_ligne(c)[0] < carte.largeur - 1]
    nombre = round(len(libres) * DENSITE[decor])
    for i in range(nombre):
        if not libres:
            break
        c = libres.pop(des.lancer(len(libres)) - 1)
        blinde = decor is Decor.FORTIFIE and i % PART_BLINDEE == 0
        carte.terrain[c] = Terrain.BLINDE if blinde else Terrain.BAS
    for _ in range(des.lancer(3) - 1):  # 0 à 2 flaques de terrain difficile
        if not libres:
            break
        centre = libres[des.lancer(len(libres)) - 1]
        for c in [centre, *[v for v in libres if distance(v, centre) == 1]]:
            if carte.terrain.get(c) is None:
                carte.terrain[c] = Terrain.DIFFICILE


def dessiner(lieu: str, decor: Decor, des: Des) -> Carte:
    """Une carte vide de combattants : le lieu, puis les obstacles du décor."""
    gabarit = GABARITS[lieu]
    carte = Carte(_entre(des, *gabarit.largeur), _entre(des, *gabarit.hauteur), lieu=lieu)
    carte.bords = {JOUEURS: 0, ENNEMIS: carte.largeur - 1}
    gabarit.structure(carte, des)
    _decor(carte, decor, des)
    return carte


def _du_cote(carte: Carte, cote: str, combattants: list, des: Des, loin_de: list[Case], ecart: int) -> bool:
    """Pose les combattants d'un côté, près de son bord, en évitant de les coller ; ceux d'en face (loin_de) restent
    à `ecart` cases au moins. Faux si la place manque."""
    bord = carte.bords[cote]
    milieu = carte.hauteur // 2
    libres = carte.libres()
    if loin_de:
        libres = [c for c in libres if min(distance(c, x) for x in loin_de) >= ecart]
        # au plus près de l'écart voulu, pour que le combat s'engage vite
        libres.sort(key=lambda c: (min(distance(c, x) for x in loin_de), abs(colonne_ligne(c)[1] - milieu)))
    else:
        libres.sort(key=lambda c: (abs(colonne_ligne(c)[0] - bord), abs(colonne_ligne(c)[1] - milieu), des.lancer(6)))
    poses = []
    for combattant in combattants:
        place = next((c for c in libres if all(distance(c, p) >= 2 for p in poses)), None)
        if place is None:
            place = next((c for c in libres if c not in poses), None)
        if place is None:
            return False
        carte.placer(combattant, place)
        poses.append(place)
        libres.remove(place)
    return True


def ouvrir(lieu: str, decor: Decor, des: Des, joueurs: list, ennemis: list, embuscade: bool = False) -> Carte:
    """La carte d'un combat qui commence : dessinée, les deux camps posés à leur distance de départ, et reliés à pied.
    `joueurs` : le joueur et ses alliés ; `ennemis` : ceux d'en face."""
    if lieu not in GABARITS:
        raise ValueError(f"Lieu inconnu : {lieu}. Lieux possibles : {', '.join(LIEUX)}.")
    ecart = ecart_de_depart(lieu, embuscade)
    for _ in range(ESSAIS):
        carte = dessiner(lieu, decor, des)
        if not _du_cote(carte, JOUEURS, joueurs, des, [], 0):
            continue
        cote_joueurs = [carte.positions[j] for j in joueurs]
        if not _du_cote(carte, ENNEMIS, ennemis, des, cote_joueurs, ecart):
            continue
        if all(carte.relie(carte.positions[j], carte.positions[e]) for j in joueurs[:1] for e in ennemis):
            return carte
    raise ValueError(f"Impossible de dessiner un {lieu} où les deux camps tiennent et se rejoignent.")


def entrer(carte: Carte, combattant, cote: str, des: Des):
    """Un renfort entre par le bord de son côté, sur la case libre la plus proche du milieu de ce bord."""
    bord, milieu = carte.bords.get(cote, 0), carte.hauteur // 2
    libres = sorted(carte.libres(), key=lambda c: (abs(colonne_ligne(c)[0] - bord), abs(colonne_ligne(c)[1] - milieu)))
    if not libres:
        raise ValueError("Plus une case libre sur la carte.")
    carte.placer(combattant, libres[0])
