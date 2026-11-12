"""Le temps qu'il fait (REGLES.md 15.3) : le code le tire chaque matin, le MJ le raconte.

Le cadre a un climat, la campagne une saison de départ. Chaque matin, 1d6 : sur 1 à 3 le temps de la veille
continue, sur 4 à 6 on retire 1d10 dans la table du climat et de la saison. Les effets ne jouent que dehors.
L'état vit sous `etat["meteo"]` ; une campagne sans cette clé n'a pas de météo.
"""

import json
from functools import lru_cache

from aria import chemins
from aria.des import Des

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "meteo.json"

SAISONS = ("printemps", "été", "automne", "hiver")
SAISONS_TROPICALES = ("sèche", "humide")
ANNEE = 360  # jours : quatre saisons de 90 jours, ou deux de 180
TROPICAL = "tropical"
ORAGE = "orage"
TEMPS = ("clair", "couvert", "pluie", ORAGE, "brouillard", "vent fort", "neige", "canicule")
CHANGE = 4  # sur 1d6 : à partir de 4, le temps change
RATTRAPAGE = 30  # jours : au-delà, on ne retire pas chaque jour sauté

# Ce que le moteur applique dehors : compétences, tir à distance, tir à longue portée ; et ce que le MJ applique
EFFETS = {
    "pluie": {"competences": {"Perception": -10}, "consigne": "Les traces s'effacent en une demi-journée."},
    ORAGE: {"competences": {"Perception": -20}, "tir": -10},
    "pluie acide": {"competences": {"Perception": -20}, "tir": -10,
                    "consigne": "1 point de dégâts par demi-journée passée dehors sans armure ni abri."},
    "tempête de cendres": {"competences": {"Perception": -20}, "tir": -10},
    "brouillard": {"competences": {"Discrétion": 10}, "tir_long": -20},
    "vent fort": {"tir": -10},
    "neige": {"competences": {"Pilotage": -10}, "consigne": "Poursuite à pied −10. Suivre une piste +10."},
    "canicule": {"competences": {"Athlétisme": -10}, "consigne": "Le repos pris dehors ne rend rien."},
}


@lru_cache(maxsize=1)
def _bibliotheque() -> dict:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))


def saisons_de(climat: str) -> tuple[str, ...]:
    return SAISONS_TROPICALES if climat == TROPICAL else SAISONS


def climat_du_cadre(genre: str, cadre: str = "") -> str:
    """Le climat que le cadre désigne (« sous la pluie acide » : pluvieux) ; sinon celui du genre."""
    b, texte = _bibliotheque(), cadre.lower()
    for climat, table in b["climats"].items():
        if any(indice in texte for indice in table["indices"]):
            return climat
    return b["climat_du_genre"].get(genre, b["climat_par_defaut"])


def installer(etat: dict, des: Des, genre: str, cadre: str = "", jour: int = 1):
    """Donne à une campagne son climat et sa saison de départ (1d4, ou 1d2 sous les tropiques), et tire le
    temps du premier jour."""
    climat = climat_du_cadre(genre, cadre)
    etat["meteo"] = {"climat": climat, "genre": genre, "depart": des.lancer(len(saisons_de(climat))) - 1,
                     "jour": jour - 1, "temps": None}
    avancer(etat, des, jour)


def actif(etat: dict | None) -> bool:
    return etat is not None and "meteo" in etat


def saison(etat: dict, jour: int) -> str:
    m = etat["meteo"]
    saisons = saisons_de(m["climat"])
    return saisons[(m["depart"] + (jour - 1) // (ANNEE // len(saisons))) % len(saisons)]


def table(climat: str, saison_: str, genre: str = "") -> list[str]:
    """Les dix temps possibles ; l'orage devient le temps propre au genre, s'il en a un."""
    b = _bibliotheque()
    propre = b["temps_du_genre"].get(genre, ORAGE)
    return [propre if t == ORAGE else t for t in b["climats"][climat][saison_]]


def avancer(etat: dict, des: Des, jour: int):
    """Tire le temps de chaque matin jusqu'au jour donné. Ordre des dés, par jour : 1d6 (sauf le premier jour),
    puis 1d10 si le temps change."""
    m = etat["meteo"]
    if jour - m["jour"] > RATTRAPAGE:
        m["jour"] = jour - RATTRAPAGE
    while m["jour"] < jour:
        m["jour"] += 1
        if m["temps"] is None or des.lancer(6) >= CHANGE:
            m["temps"] = table(m["climat"], saison(etat, m["jour"]), m["genre"])[des.lancer(10) - 1]


def temps(etat: dict) -> str:
    return etat["meteo"]["temps"]


def modificateur(etat: dict | None, competence: str) -> int:
    """Ce que le temps du jour change à une compétence, dehors."""
    if not actif(etat):
        return 0
    return EFFETS.get(temps(etat), {}).get("competences", {}).get(competence, 0)


def malus_de_tir(etat: dict | None) -> tuple[int, int]:
    """Dehors : (ce que perd tout tir à distance, ce que perd en plus un tir à longue portée)."""
    if not actif(etat):
        return 0, 0
    e = EFFETS.get(temps(etat), {})
    return e.get("tir", 0), e.get("tir_long", 0)


def _signe(n: int) -> str:
    return f"+{n}" if n > 0 else f"−{-n}"


def effets(etat: dict, nom_affiche=lambda c: c) -> list[str]:
    """Les effets du temps du jour, en clair. `nom_affiche` : le nom d'une compétence dans l'univers."""
    e = EFFETS.get(temps(etat), {})
    lignes = [f"{nom_affiche(c)} {_signe(v)}" for c, v in e.get("competences", {}).items()]
    if e.get("tir"):
        lignes.append(f"tir à distance {_signe(e['tir'])}")
    if e.get("tir_long"):
        lignes.append(f"tir à longue portée {_signe(e['tir_long'])}")
    if e.get("consigne"):
        lignes.append(e["consigne"])
    return lignes


def decrire(etat: dict, nom_affiche=lambda c: c) -> dict:
    """Ce que le MJ reçoit du temps qu'il fait."""
    m = etat["meteo"]
    vue = {"saison": saison(etat, m["jour"]), "temps": m["temps"]}
    if lignes := effets(etat, nom_affiche):
        vue["dehors"] = lignes
    return vue


def phrase(etat: dict, nom_affiche=lambda c: c) -> str:
    """Le temps du jour en une ligne, pour le joueur et pour le prompt du MJ."""
    vue = decrire(etat, nom_affiche)
    suite = f" Dehors : {' ; '.join(vue['dehors'])}" if "dehors" in vue else ""
    return f"{vue['saison'].capitalize()}, {vue['temps']}.{suite}"


def bloc(etat: dict | None, nom_affiche=lambda c: c) -> str:
    """La section du prompt du MJ sur le temps qu'il fait. Vide sans météo."""
    if not actif(etat):
        return ""
    return ("### Le temps qu'il fait\n\n"
            f"- {phrase(etat, nom_affiche)}\n"
            "- Tu le racontes, tu ne le choisis pas. Les effets ne jouent que dehors.\n")


def verifier_tables() -> list[str]:
    """Ce qui cloche dans la bibliothèque de la météo."""
    b, fautes = _bibliotheque(), []
    connus = set(TEMPS)
    for climat, t in b["climats"].items():
        for s in saisons_de(climat):
            if len(t.get(s, [])) != 10 or set(t[s]) - connus:
                fautes.append(f"{climat} / {s} : dix temps connus attendus")
        if set(t) - {"indices", *saisons_de(climat)}:
            fautes.append(f"{climat} : saison inconnue")
    for genre, climat in [*b["climat_du_genre"].items(), ("défaut", b["climat_par_defaut"])]:
        if climat not in b["climats"]:
            fautes.append(f"{genre} : climat inconnu « {climat} »")
    for genre, t in b["temps_du_genre"].items():
        if t not in EFFETS:
            fautes.append(f"{genre} : le temps « {t} » n'a pas d'effets")
    return fautes
