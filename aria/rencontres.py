"""Les rencontres de rue (REGLES.md 15.5) : ce qui arrive au joueur quand il entre dans un quartier.

À chaque entrée, 1d10 : une rencontre sur 1 ou 2 dans un quartier calme, sur 1 à 4 dans un quartier disputé ou
un district en guerre ouverte, une face de plus la nuit. Une seule par jour. Le code tire la famille, la
rencontre et son PNJ ; le joueur peut passer son chemin. L'état vit sous `etat["rencontres"]`.
"""

import json
from functools import lru_cache

from aria import chemins, monde, noms, pnj
from aria.des import Des

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "rencontres.json"

SCENE, OCCASION, DANGER = "scène", "occasion", "danger"
FAMILLES = (SCENE, OCCASION, DANGER)
PAR_FAMILLE = 10
CHANCE_CALME, CHANCE_TENDUE, FACE_DE_NUIT = 2, 4, 1  # sur 1d10
# sur 1d6 : la famille de la rencontre ; chez une faction hostile, le danger prend une face de plus
FAMILLE_AU_DE = (SCENE, SCENE, SCENE, OCCASION, OCCASION, DANGER)
FAMILLE_HOSTILE = (SCENE, SCENE, SCENE, OCCASION, DANGER, DANGER)
MENACES = (pnj.FAIBLE, pnj.FAIBLE, pnj.FAIBLE, pnj.MOYENNE, pnj.MOYENNE, pnj.FORTE)  # sur 1d6 : forte au plus
CONSIGNES = {
    SCENE: "Une scène de rue : fais-la vivre en passant. Le joueur peut s'y arrêter ou continuer son chemin.",
    OCCASION: "Une occasion : présente-la, sans rien promettre de plus. Le joueur peut passer son chemin.",
    DANGER: "Un danger : le joueur choisit comment il réagit. Rien n'est joué d'avance.",
}
EMBUSCADE = "C'est une embuscade : joue-la avec l'outil embuscade avant tout combat."
PNJ_DE_RENCONTRE = ("S'il entre en scène, crée-le avec creer_pnj et « rencontre » à vrai : son nom, son rôle et sa "
                    "menace sont déjà fixés.")


@lru_cache(maxsize=1)
def _bibliotheque() -> dict:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))


def table(genre: str, famille: str) -> list[dict]:
    b = _bibliotheque()
    return b.get(genre, b["generique"])[famille]


def installer(etat: dict, genre: str):
    etat["rencontres"] = {"genre": genre, "jour": 0, "en_cours": None}


def actives(etat: dict | None) -> bool:
    return etat is not None and "rencontres" in etat


def chance(etat: dict, quartier: str, nuit: bool = False) -> int:
    """Sur 1d10, jusqu'à quelle face une rencontre a lieu dans ce quartier."""
    tendu = monde.dispute(etat, quartier) or monde.domine(etat, etat["quartiers"][quartier]["district"]) is None
    return (CHANCE_TENDUE if tendu else CHANCE_CALME) + (FACE_DE_NUIT if nuit else 0)


def _menace(des: Des, genre: str, role: str) -> str:
    r = pnj.roles(genre).get(role, {})
    rang = max(pnj.ORDRE.index(MENACES[des.lancer(6) - 1]), pnj.ORDRE.index(r.get("min", pnj.FAIBLE)))
    return pnj.ORDRE[min(rang, pnj.ORDRE.index(r.get("max", pnj.FORTE)), pnj.ORDRE.index(pnj.FORTE))]


def tirer(etat: dict, des: Des, jour: int, nuit: bool = False) -> dict | None:
    """La rencontre du joueur à son entrée dans le quartier où il vient d'arriver ; None s'il n'y en a pas.
    Ordre des dés : 1d10 (y a-t-il une rencontre), [1d6 la famille, sauf pour un joueur recherché], laquelle,
    puis le PNJ : sexe, [nom], menace, caractère, signe."""
    r = etat["rencontres"]
    quartier = etat["ici"]
    if r["jour"] == jour or des.lancer(10) > chance(etat, quartier, nuit):
        return None
    genre = r["genre"]
    cran = monde.reputation(etat, etat["quartiers"][quartier]["maitre"])
    if cran == monde.RECHERCHE:
        famille = DANGER
        entree = monde._choisir(des, [e for e in table(genre, DANGER) if e.get("traque")])
    else:
        famille = (FAMILLE_HOSTILE if cran == monde.HOSTILE else FAMILLE_AU_DE)[des.lancer(6) - 1]
        entree = monde._choisir(des, table(genre, famille))
    sexe = noms.SEXES[des.lancer(2) - 1]
    nom = noms.tirer(etat, des, sexe) if noms.actifs(etat) else "un inconnu"
    menace = _menace(des, genre, entree["role"])
    caractere, signe = pnj.traits(genre, des)
    rencontre = {"texte": entree["t"], "famille": famille, "quartier": quartier,
                 "pnj": {"nom": nom, "sexe": sexe, "role": entree["role"], "menace": menace,
                         "caractere": caractere, "signe": signe}}
    for cle in ("offre", "embuscade"):
        if entree.get(cle):
            rencontre[cle] = True
    r["jour"], r["en_cours"] = jour, rencontre
    return rencontre


def en_cours(etat: dict | None) -> dict | None:
    """La rencontre du jour, tant que son PNJ n'a pas été créé et que le joueur n'a pas changé de quartier."""
    if not actives(etat):
        return None
    rencontre = etat["rencontres"]["en_cours"]
    return rencontre if rencontre and rencontre["quartier"] == etat["ici"] else None


def clore(etat: dict):
    etat["rencontres"]["en_cours"] = None


def decrire(rencontre: dict) -> dict:
    """Ce que le MJ reçoit d'une rencontre."""
    consigne = CONSIGNES[rencontre["famille"]] + (f" {EMBUSCADE}" if rencontre.get("embuscade") else "")
    return {"rencontre": rencontre["texte"], "famille": rencontre["famille"], "pnj": dict(rencontre["pnj"]),
            "consigne": f"{consigne} {PNJ_DE_RENCONTRE}"}


def verifier_tables(roles_par_genre=pnj.roles) -> list[str]:
    """Ce qui cloche dans la bibliothèque des rencontres."""
    fautes = []
    for genre, familles in _bibliotheque().items():
        if set(familles) != set(FAMILLES):
            fautes.append(f"{genre} : familles attendues {list(FAMILLES)}")
            continue
        textes = [e["t"] for liste in familles.values() for e in liste]
        if len(set(textes)) != len(textes):
            fautes.append(f"{genre} : une rencontre en double")
        for famille, liste in familles.items():
            if len(liste) != PAR_FAMILLE:
                fautes.append(f"{genre} / {famille} : {PAR_FAMILLE} rencontres attendues, {len(liste)} trouvées")
            for e in liste:
                if e["role"] not in roles_par_genre(genre):
                    fautes.append(f"{genre} / {famille} : rôle inconnu « {e['role']} »")
                if e.get("offre") and famille != OCCASION:
                    fautes.append(f"{genre} / {famille} : seule une occasion ouvre une offre")
        if sum(bool(e.get("traque")) for e in familles[DANGER]) < 2:
            fautes.append(f"{genre} : au moins deux dangers pour un joueur recherché")
    return fautes
