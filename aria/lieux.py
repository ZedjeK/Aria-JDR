"""Les lieux d'un quartier (REGLES.md 15.4) : tirés une fois avec la carte, retrouvés toute la campagne.

Chaque quartier a de 3 à 5 lieux, un quartier sur trois en cache un de plus. Un lieu a un type, une enseigne
et un tenancier. Le commerce passe par eux : on achète une arme là où on en vend. L'état vit sous
`etat["lieux"]` ; une campagne sans cette clé garde le commerce d'avant.
"""

import json
from functools import lru_cache

from aria import chemins, monde, noms, pnj
from aria.des import Des

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "lieux.json"

TYPES_PAR_GENRE = 16
ENSEIGNES = 60
BOIRE, SOINS, ARMES, MATERIEL, IMPLANTS, VEHICULES = "boire", "soins", "armes", "materiel", "implants", "vehicules"
BESOINS = (BOIRE, SOINS, ARMES, MATERIEL, IMPLANTS, VEHICULES)
MINIMUM_PAR_DISTRICT = (BOIRE, SOINS, ARMES, MATERIEL)
CE_QU_IL_FAUT = {BOIRE: "un endroit où boire", SOINS: "un lieu où se faire soigner", ARMES: "une armurerie",
                 MATERIEL: "un marché", IMPLANTS: "un poseur d'implants", VEHICULES: "un garage"}
CHANCE_CACHE = 3  # un quartier sur trois cache un lieu de plus
QG = "quartier général"
MENACES_DU_TENANCIER = (pnj.FAIBLE, pnj.FAIBLE, pnj.FAIBLE, pnj.MOYENNE, pnj.MOYENNE, pnj.FORTE)  # sur 1d6
ATTITUDES = {monde.RECHERCHE: "hostile", monde.HOSTILE: "hostile", monde.NEUTRE: "neutre", monde.AMI: "amical",
             monde.MEMBRE: "amical"}


class LieuImpossible(ValueError):
    """Ce que les lieux ne permettent pas : le message est renvoyé tel quel au MJ."""


@lru_cache(maxsize=1)
def _bibliotheque() -> dict:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))


def _table(genre: str, cle: str) -> list:
    b = _bibliotheque()[cle]
    return b.get(genre, b["generique"])


def actifs(etat: dict | None) -> bool:
    return etat is not None and "lieux" in etat


# --- Le tirage, à la création de la carte ---------------------------------------------------------------

def _menace(des: Des, genre: str, role: str) -> str:
    """La menace d'un tenancier : 1d6 (1-3 faible, 4-5 moyenne, 6 forte), dans les bornes de son rôle."""
    r = pnj.roles(genre).get(role, {})
    rang = pnj.ORDRE.index(MENACES_DU_TENANCIER[des.lancer(6) - 1])
    rang = max(rang, pnj.ORDRE.index(r.get("min", pnj.FAIBLE)))
    return pnj.ORDRE[min(rang, pnj.ORDRE.index(r.get("max", pnj.ELITE)))]


def _tenancier(etat: dict, des: Des, genre: str, role: str) -> dict:
    """Ordre des dés : sexe, [le nom], menace, caractère, signe."""
    sexe = noms.SEXES[des.lancer(2) - 1]
    nom = noms.tirer(etat, des, sexe) if noms.actifs(etat) else "le tenancier"
    menace = _menace(des, genre, role)
    caractere, signe = pnj.traits(genre, des)
    return {"nom": nom, "sexe": sexe, "role": role, "menace": menace, "caractere": caractere, "signe": signe}


def _enseigne(des: Des, genre: str, type_: str, prises: dict[str, set]) -> str:
    """Une enseigne jamais vue sur la carte ; quand toutes ont servi, une que ce type de lieu n'a pas."""
    toutes = _table(genre, "enseignes")
    deja = {e for vues in prises.values() for e in vues}
    libres = [e for e in toutes if e not in deja] or [e for e in toutes if e not in prises.get(type_, set())]
    enseigne = monde._choisir(des, libres or toutes)
    prises.setdefault(type_, set()).add(enseigne)
    return enseigne


def _lieu(etat: dict, des: Des, genre: str, modele: dict, prises: dict, cache: bool = False) -> dict:
    """Ordre des dés : enseigne, puis le tenancier."""
    enseigne = _enseigne(des, genre, modele["nom"], prises)
    return {"nom": f"{modele['nom']} {enseigne}", "type": modele["nom"], "vend": list(modele["vend"]),
            "cache": cache, "trouve": not cache, "tenancier": _tenancier(etat, des, genre, modele["role"])}


def installer(etat: dict, des: Des, genre: str):
    """Tire les lieux de toute la carte. Par quartier : le nombre (1d3 + 2), puis chaque lieu (type, enseigne,
    tenancier) ; ensuite le minimum de chaque district, les quartiers généraux, et les lieux cachés (1d3 par
    quartier, puis le lieu)."""
    types, prises = _table(genre, "types"), {}
    par_quartier = {}
    for quartier in etat["quartiers"]:
        restants, lieux = list(types), []
        for _ in range(des.lancer(3) + 2):
            lieux.append(_lieu(etat, des, genre, restants.pop(des.lancer(len(restants)) - 1), prises))
        par_quartier[quartier] = lieux
    for district, membres in etat["districts"].items():
        for besoin in MINIMUM_PAR_DISTRICT:
            if not any(besoin in l["vend"] for q in membres for l in par_quartier[q]):
                modele = next(t for t in types if besoin in t["vend"])
                pauvre = min(membres, key=lambda q: len(par_quartier[q]))
                par_quartier[pauvre].append(_lieu(etat, des, genre, modele, prises))
        dominant = monde.domine(etat, district)
        if dominant:
            siege = next(q for q in membres if etat["quartiers"][q]["maitre"] == dominant)
            f = etat["factions"][dominant]
            par_quartier[siege].append({
                "nom": f"{QG} {monde.de(dominant)}", "type": QG, "vend": [], "cache": False, "trouve": True,
                "faction": dominant,
                "tenancier": {"nom": f.get("chef") or "le chef", "sexe": noms.HOMME, "role": "chef",
                              "menace": pnj.FORTE, "caractere": "", "signe": ""}})
    for quartier in etat["quartiers"]:
        if des.lancer(CHANCE_CACHE) == 1:
            modele = monde._choisir(des, _table(genre, "caches"))
            par_quartier[quartier].append(_lieu(etat, des, genre, modele, prises, cache=True))
    etat["lieux"] = {"genre": genre, "connus": [etat["ici"]], "par_quartier": par_quartier}


# --- Ce que le joueur connaît ---------------------------------------------------------------------------

def du_quartier(etat: dict, quartier: str | None = None, caches: bool = False) -> list[dict]:
    """Les lieux d'un quartier (celui du joueur par défaut) ; sans les lieux cachés qu'il n'a pas trouvés."""
    lieux = etat["lieux"]["par_quartier"].get(quartier or etat["ici"], [])
    return [l for l in lieux if caches or l["trouve"]]


def visiter(etat: dict, quartier: str):
    if quartier not in etat["lieux"]["connus"]:
        etat["lieux"]["connus"].append(quartier)


def reveler(etat: dict) -> dict | None:
    """Le lieu caché du quartier où est le joueur, s'il ne l'avait pas trouvé : il le connaît maintenant."""
    for l in etat["lieux"]["par_quartier"].get(etat["ici"], []):
        if l["cache"] and not l["trouve"]:
            l["trouve"] = True
            return l
    return None


def lieu(etat: dict, nom: str) -> dict:
    """Un lieu du quartier où est le joueur, par son nom."""
    for l in du_quartier(etat):
        if l["nom"] == nom:
            return l
    raise LieuImpossible(f"Pas de lieu « {nom} » ici. Lieux du quartier : {[l['nom'] for l in du_quartier(etat)]}.")


def attitude(etat: dict, quartier: str | None = None) -> str:
    """L'attitude des tenanciers d'un quartier : elle suit la réputation du joueur chez celui qui le tient."""
    maitre = etat["quartiers"][quartier or etat["ici"]]["maitre"]
    return ATTITUDES[monde.reputation(etat, maitre)]


# --- Le commerce passe par les lieux --------------------------------------------------------------------

def plus_proche(etat: dict, besoin: str) -> tuple[str, str] | None:
    """Le lieu le plus proche qui répond au besoin, de quartier en quartier : (lieu, quartier)."""
    vus, file = {etat["ici"]}, [etat["ici"]]
    while file:
        quartier = file.pop(0)
        for l in du_quartier(etat, quartier):
            if besoin in l["vend"]:
                return l["nom"], quartier
        for voisin in etat["quartiers"][quartier]["voisins"]:
            if voisin not in vus:
                vus.add(voisin)
                file.append(voisin)
    return None


def exiger(etat: dict, besoin: str) -> str | None:
    """Vérifie que le quartier où est le joueur a un lieu pour ce besoin, et renvoie son nom. Refuse sinon, en
    disant où aller. None si la carte n'a aucun lieu pour ce besoin : le commerce reste alors libre."""
    ici = next((l["nom"] for l in du_quartier(etat) if besoin in l["vend"]), None)
    if ici:
        return ici
    proche = plus_proche(etat, besoin)
    if proche is None:
        return None
    raise LieuImpossible(f"Il n'y a pas d'endroit pour cela {monde.a(etat['ici'])} : il faut {CE_QU_IL_FAUT[besoin]}. "
                         f"Le plus proche : {proche[0]}, {monde.a(proche[1])}.")


def endroit(etat: dict, des: Des, quartier: str) -> str | None:
    """Un lieu du quartier où une mission peut se passer : jamais un lieu caché."""
    possibles = [l["nom"] for l in etat["lieux"]["par_quartier"].get(quartier, []) if not l["cache"]]
    return monde._choisir(des, possibles) if possibles else None


# --- Ce qu'on en montre ---------------------------------------------------------------------------------

def decrire(etat: dict) -> list[dict]:
    """Les lieux du quartier où est le joueur, pour le MJ : qui les tient, ce qu'on y trouve."""
    ton = attitude(etat)
    vues = []
    for l in du_quartier(etat):
        t = l["tenancier"]
        vue = {"lieu": l["nom"], "tenancier": t["nom"], "role": t["role"], "attitude": ton}
        if t["caractere"]:
            vue |= {"caractere": t["caractere"], "signe": t["signe"]}
        if l["vend"]:
            vue["on_y_trouve"] = l["vend"]
        if l["cache"]:
            vue["cache"] = True
        vues.append(vue)
    return vues


def carte(etat: dict) -> list[str]:
    """Les lieux que le joueur connaît, pour la commande « carte »."""
    lignes = ["Les lieux que tu connais :"]
    for quartier in etat["quartiers"]:
        if quartier in etat["lieux"]["connus"]:
            noms_ = [f"{l['nom']} ({l['tenancier']['nom']})" for l in du_quartier(etat, quartier)]
            lignes.append(f"  {quartier} : {', '.join(noms_)}")
    return lignes


def verifier_tables(roles_par_genre=pnj.roles) -> list[str]:
    """Ce qui cloche dans la bibliothèque des lieux."""
    b, fautes = _bibliotheque(), []
    for genre, types in b["types"].items():
        if len(types) != TYPES_PAR_GENRE or len({t["nom"] for t in types}) != TYPES_PAR_GENRE:
            fautes.append(f"types / {genre} : {TYPES_PAR_GENRE} types différents attendus")
        for besoin in MINIMUM_PAR_DISTRICT:
            if not any(besoin in t["vend"] for t in types):
                fautes.append(f"types / {genre} : aucun lieu pour « {besoin} »")
    for cle in ("types", "caches"):
        for genre, types in b[cle].items():
            for t in types:
                if set(t["vend"]) - set(BESOINS):
                    fautes.append(f"{cle} / {genre} / {t['nom']} : besoin inconnu")
                if t["role"] not in roles_par_genre(genre):
                    fautes.append(f"{cle} / {genre} / {t['nom']} : rôle inconnu « {t['role']} »")
    for genre, liste in b["enseignes"].items():
        if len(liste) != ENSEIGNES or len(set(liste)) != ENSEIGNES:
            fautes.append(f"enseignes / {genre} : {ENSEIGNES} enseignes différentes attendues, {len(set(liste))} trouvées")
    return fautes
