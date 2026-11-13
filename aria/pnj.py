"""Les PNJ tirés par le moteur (REGLES.md 15.2) : le MJ choisit un rôle et une menace, le code tire le reste.

La menace donne le combat, les points de vie et le niveau des compétences ; le rôle donne trois compétences,
l'équipement (pris dans l'armurerie de l'univers) et les menaces permises. Deux traits, un caractère et un signe
physique, évitent que les PNJ se ressemblent. Une campagne sans `etat["pnj"]` garde l'ancien fonctionnement.
"""

import json
from functools import lru_cache

from aria import chemins
from aria.des import Des
from aria.equipement import ARMES_A_DISTANCE, CORPS_A_CORPS, Portee, Propriete

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "roles.json"

FAIBLE, MOYENNE, FORTE, ELITE = "faible", "moyenne", "forte", "élite"
# menace : (combat = base + dés × faces), (points de vie = base + 1 dé), niveau des compétences du rôle
MENACES = {FAIBLE: ((20, 2, 10), (6, 6), 40), MOYENNE: ((40, 2, 10), (10, 6), 55),
           FORTE: ((55, 2, 10), (14, 8), 70), ELITE: ((75, 1, 10), (20, 10), 80)}
ORDRE = tuple(MENACES)
DEXTERITE = (40, 2, 10)
ROLES_PAR_GENRE = 12
TRAITS = 40  # caractères, et signes physiques par genre

# Le plafond de menace : en mission d'après son danger, hors mission forte au plus
PLAFONDS = {"un service": MOYENNE, "simple": MOYENNE, "risquée": FORTE}
HORS_MISSION = FORTE

MELEE, POING, LONGUE = "mêlée", "poing", "longue"
CLASSES_D_ARMES = (MELEE, POING, LONGUE)
# classe d'armure → la protection visée, par menace
ARMURES = {"aucune": {}, "légère": {FAIBLE: 1, MOYENNE: 1, FORTE: 2, ELITE: 2},
           "lourde": {FAIBLE: 2, MOYENNE: 3, FORTE: 3, ELITE: 4}}


class PnjImpossible(ValueError):
    """Ce que les règles des PNJ ne permettent pas : le message est renvoyé tel quel au MJ."""


@lru_cache(maxsize=1)
def _bibliotheque() -> dict:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))


def _table(genre: str, cle: str) -> list:
    b = _bibliotheque()[cle]
    return b.get(genre, b["generique"])


def roles(genre: str) -> dict[str, dict]:
    """Les rôles du genre, par leur nom ; ceux du jeu générique sinon."""
    return {r["nom"]: r for r in _table(genre, "roles")}


def installer(etat: dict, genre: str):
    etat["pnj"] = {"genre": genre, "elite": None}


def actifs(etat: dict | None) -> bool:
    return etat is not None and "pnj" in etat


def noms_des_roles(etat: dict) -> list[str]:
    return list(roles(etat["pnj"]["genre"]))


def plafond(dangers: list[str]) -> str:
    """La menace la plus haute permise : d'après la mission la plus dangereuse en cours, sinon forte."""
    if not dangers:
        return HORS_MISSION
    return max((PLAFONDS.get(d, ELITE) for d in dangers), key=ORDRE.index)


def verifier(etat: dict, role: str, menace: str, dangers: list[str] = ()):
    """Refuse un rôle inconnu, une menace que le rôle ne permet pas, ou plus haute que le plafond."""
    connus = roles(etat["pnj"]["genre"])
    if role not in connus:
        raise PnjImpossible(f"Le rôle « {role} » n'existe pas. Rôles : {list(connus)}.")
    if menace not in MENACES:
        raise PnjImpossible(f"La menace vaut {menace!r}, mais doit être l'une de ces valeurs : {list(MENACES)}.")
    r, rang = connus[role], ORDRE.index(menace)
    if "max" in r and rang > ORDRE.index(r["max"]):
        raise PnjImpossible(f"Un {role} est de menace {r['max']} au plus.")
    if "min" in r and rang < ORDRE.index(r["min"]):
        raise PnjImpossible(f"Un {role} est de menace {r['min']} au moins.")
    haut = plafond(list(dangers))
    if rang > ORDRE.index(haut):
        raison = "hors mission" if not dangers else "pour une mission de ce danger"
        raise PnjImpossible(f"Menace {haut} au plus, {raison}.")


def _somme(des: Des, base: int, nombre: int, faces: int) -> int:
    return base + sum(des.lancer(faces) for _ in range(nombre))


def _choisir(des: Des, liste):
    return liste[des.lancer(len(liste)) - 1]


def armes_de_classe(univers, classe: str) -> list:
    """Les armes ordinaires de l'armurerie pour une classe : ni marque, ni arme de zone, montée ou à usage unique."""
    ordinaires = [a for a in univers.armes
                  if not (a.montee or a.usage_unique or a.zone or a.fabricant or a.categorie == "drones")]
    if classe == MELEE:
        return [a for a in ordinaires if a.competence == CORPS_A_CORPS]
    tir = [a for a in ordinaires if a.competence == ARMES_A_DISTANCE and Propriete.LANCER not in a.proprietes]
    if classe == POING:
        return [a for a in tir if a.portee is Portee.COURTE and Propriete.DEUX_MAINS not in a.proprietes]
    return [a for a in tir if Propriete.DEUX_MAINS in a.proprietes and a.categorie != "armes lourdes"]


def _armure(des: Des, univers, classe: str, menace: str):
    vise = ARMURES[classe].get(menace, 0)
    while vise > 0:
        possibles = [a for a in univers.armures if a.protection == vise and not a.fabricant]
        if possibles:
            return _choisir(des, possibles)
        vise -= 1
    return None


def tirer(etat: dict, des: Des, univers, role: str, menace: str, dangers: list[str] = ()) -> dict:
    """Tire le profil d'un PNJ. Ordre des dés : combat, points de vie, Dextérité (2d10), [classe d'arme, arme],
    [armure], caractère, signe."""
    verifier(etat, role, menace, dangers)
    genre = etat["pnj"]["genre"]
    r = roles(genre)[role]
    combat, (base_pv, faces_pv), niveau = MENACES[menace]
    profil = {"combat": _somme(des, *combat), "pv": base_pv + des.lancer(faces_pv),
              "dexterite": _somme(des, *DEXTERITE), "niveau": niveau,
              "competences": {c: niveau for c in r["competences"]}, "arme": None, "armure": None}
    classes = [c for c in r["armes"] if armes_de_classe(univers, c)]
    if classes:
        profil["arme"] = _choisir(des, armes_de_classe(univers, _choisir(des, classes))).nom
    armure = _armure(des, univers, r["armure"], menace)
    if armure:
        profil["armure"] = armure.nom
    profil["caractere"] = _choisir(des, _bibliotheque()["caracteres"])
    profil["signe"] = _choisir(des, _table(genre, "signes"))
    return profil


def verifier_tables(competences: set[str] | None = None) -> list[str]:
    """Ce qui cloche dans la bibliothèque des rôles. `competences` : les compétences permises, si on les connaît."""
    b, fautes = _bibliotheque(), []
    for genre, liste in b["roles"].items():
        if len(liste) != ROLES_PAR_GENRE or len({r["nom"] for r in liste}) != ROLES_PAR_GENRE:
            fautes.append(f"rôles / {genre} : {ROLES_PAR_GENRE} rôles différents attendus")
        for r in liste:
            ou = f"{genre} / {r['nom']}"
            if len(set(r["competences"])) != 3:
                fautes.append(f"{ou} : trois compétences différentes attendues")
            if competences is not None and (inconnues := set(r["competences"]) - competences):
                fautes.append(f"{ou} : compétences inconnues {sorted(inconnues)}")
            if set(r["armes"]) - set(CLASSES_D_ARMES) or r["armure"] not in ARMURES:
                fautes.append(f"{ou} : classe d'arme ou d'armure inconnue")
            if {r.get("min", FAIBLE), r.get("max", ELITE)} - set(MENACES):
                fautes.append(f"{ou} : menace inconnue")
    for nom, liste in [("caractères", b["caracteres"]), *((f"signes / {g}", s) for g, s in b["signes"].items())]:
        if len(liste) != TRAITS or len(set(liste)) != TRAITS:
            fautes.append(f"{nom} : {TRAITS} entrées différentes attendues, {len(set(liste))} trouvées")
    return fautes
