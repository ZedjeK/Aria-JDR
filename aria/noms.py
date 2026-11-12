"""Les noms des PNJ (REGLES.md 15.1) : le code les tire, le MJ ne les invente plus.

Chaque genre a ses origines ; chaque origine a 20 prénoms d'homme, 20 de femme et 20 noms de famille. L'origine
du cadre sort une fois sur deux. Un nom tiré ne ressort plus de la campagne : il est rangé dans l'état du
monde, sous `etat["noms"]`. Une campagne sans cette clé garde l'ancien fonctionnement.
"""

import json
from functools import lru_cache

from aria import chemins
from aria.des import Des

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "noms.json"

HOMME, FEMME = "homme", "femme"
SEXES = (HOMME, FEMME)
PAR_LISTE = 20  # prénoms d'homme, prénoms de femme, noms de famille, par origine
SURNOMS = 40  # par genre
FACES_DU_CADRE = 5  # sur 1d10, l'origine du cadre
CHANCE_SURNOM = 3  # un membre de gang porte un surnom 1 fois sur 3
LONGUEUR_MAX = 40  # celle d'un nom dans la mémoire de la campagne
ESSAIS = 20


class NomImpossible(ValueError):
    """Le nom demandé ne peut pas être tiré : le message est renvoyé tel quel au MJ."""


@lru_cache(maxsize=1)
def _bibliotheque() -> dict:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))


def origines(genre: str) -> list[str]:
    """Les origines des noms du genre ; celles du jeu générique sinon."""
    b = _bibliotheque()
    return list(b["genres"].get(genre, b["generique"]))


def surnoms(genre: str) -> list[str]:
    b = _bibliotheque()["surnoms"]
    return b.get(genre, b["generique"])


def origine_du_cadre(genre: str, cadre: str = "") -> str:
    """L'origine que le cadre désigne (« Osaka sous la pluie acide » : japonaise) ; sinon la première du genre."""
    texte = cadre.lower()
    for origine, table in _bibliotheque()["origines"].items():
        if any(indice in texte for indice in table["indices"]):
            return origine
    return origines(genre)[0]


def installer(etat: dict, genre: str, cadre: str = ""):
    """Donne à une campagne ses tables de noms : l'origine du cadre d'abord, puis les autres du genre."""
    principale = origine_du_cadre(genre, cadre)
    etat["noms"] = {"genre": genre, "origines": [principale, *(o for o in origines(genre) if o != principale)],
                    "pris": sorted({f["chef"] for f in etat.get("factions", {}).values() if f.get("chef")}),
                    "surnoms": []}


def actifs(etat: dict | None) -> bool:
    return etat is not None and "noms" in etat


def reserver(etat: dict, nom: str):
    """Un nom donné ailleurs (par l'amorce, par la carte) ne sera pas tiré une seconde fois."""
    if nom not in etat["noms"]["pris"]:
        etat["noms"]["pris"].append(nom)


def _choisir(des: Des, liste):
    return liste[des.lancer(len(liste)) - 1]


def tirer(etat: dict, des: Des, sexe: str, origine: str | None = None, gang: bool = False) -> str:
    """Tire un nom qui n'a jamais servi dans la campagne. Ordre des dés : [origine d10], prénom, nom de
    famille (retirés tant que le nom est pris), puis pour un membre de gang : surnom d3, [lequel]."""
    n = etat["noms"]
    connues = n["origines"]
    if sexe not in SEXES:
        raise NomImpossible(f"Le sexe vaut {sexe!r}, mais doit être l'une de ces valeurs : {list(SEXES)}.")
    if origine is None:
        jet = des.lancer(10)
        autres = connues[1:]
        origine = connues[0] if jet <= FACES_DU_CADRE or not autres else autres[(jet - FACES_DU_CADRE - 1) % len(autres)]
    elif origine not in connues:
        raise NomImpossible(f"L'origine « {origine} » n'existe pas dans cette campagne. Origines : {connues}.")
    table = _bibliotheque()["origines"][origine]
    prenoms, familles, pris = table["m" if sexe == HOMME else "f"], table["famille"], set(n["pris"])
    for _ in range(ESSAIS):
        nom = f"{_choisir(des, prenoms)} {_choisir(des, familles)}"
        if nom not in pris:
            break
    else:
        libres = [f"{p} {f}" for p in prenoms for f in familles if f"{p} {f}" not in pris]
        if not libres:
            raise NomImpossible(f"Tous les noms d'origine {origine} ont servi : prends une autre origine.")
        nom = _choisir(des, libres)
    n["pris"].append(nom)
    if gang and des.lancer(CHANCE_SURNOM) == 1:
        libres = [s for s in surnoms(n["genre"]) if s not in n["surnoms"]]
        if libres:
            surnom = _choisir(des, libres)
            avec = f"{nom}, dit{'e' if sexe == FEMME else ''} {surnom}"
            if len(avec) <= LONGUEUR_MAX:
                n["surnoms"].append(surnom)
                nom = avec
    return nom


def verifier_tables() -> list[str]:
    """Ce qui cloche dans la bibliothèque des noms : listes incomplètes, doublons, origine inconnue."""
    b, fautes = _bibliotheque(), []
    for origine, table in b["origines"].items():
        for cle in ("m", "f", "famille"):
            if len(table[cle]) != PAR_LISTE or len(set(table[cle])) != PAR_LISTE:
                fautes.append(f"{origine} / {cle} : {PAR_LISTE} noms différents attendus, {len(set(table[cle]))} trouvés")
        longueur = max(len(p) for p in table["m"] + table["f"]) + 1 + max(len(f) for f in table["famille"])
        if longueur > LONGUEUR_MAX:
            fautes.append(f"{origine} : un nom peut faire {longueur} caractères, {LONGUEUR_MAX} au plus")
    for genre, liste in [*b["genres"].items(), ("generique", b["generique"])]:
        for origine in liste:
            if origine not in b["origines"]:
                fautes.append(f"{genre} : origine inconnue « {origine} »")
        if len(set(liste)) != len(liste) or not liste:
            fautes.append(f"{genre} : origines vides ou en double")
    for genre, liste in b["surnoms"].items():
        if len(liste) != SURNOMS or len(set(liste)) != SURNOMS:
            fautes.append(f"surnoms / {genre} : {SURNOMS} surnoms différents attendus, {len(set(liste))} trouvés")
    return fautes
