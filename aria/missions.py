"""Le générateur de missions (REGLES.md 14.8) : le code tire l'ossature d'une offre, le MJ l'habille.

Une offre : un commanditaire (une faction de la carte), un objectif, un lieu (un quartier), une cible (une
faction adverse), un danger qui fixe la récompense, et parfois un retournement, que seul le MJ connaît.
Les offres s'ouvrent dans le district où se trouve le joueur, et se renouvellent toutes seules.
"""

import json
from functools import lru_cache

from aria import chemins, gains, lieux as lieux_, monde, trame
from aria.des import Des
from aria.economie import decaler
from aria.monde import AMI, HOSTILE, RECHERCHE, a, de
from aria.personnage import AGUERRI, DEBUTANT, VETERAN

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "missions.json"

DEFENDRE = "défendre un lieu"
OBJECTIFS = ("voler", "livrer", "protéger", "escorter", "éliminer", "retrouver quelqu'un", "extraire quelqu'un",
             "saboter", "infiltrer", "enquêter", "négocier", DEFENDRE)
CONTRE_LE_QUARTIER = ("éliminer", "saboter")  # réussis, ils coûtent 2 points de contrôle au maître du lieu
POINTS_DE_CONTROLE = 2
DANGERS = tuple(gains.RECOMPENSES)  # du service à l'exceptionnelle
DANGER_DE_DEPART = {DEBUTANT: "simple", AGUERRI: "risquée", VETERAN: "dangereuse"}
OFFRES_MAX = 3
RENOUVELLEMENT = 5  # 1d5 jours
CHANCE_RETOURNEMENT = 3  # 1 fois sur 3
CHANCE_ENTREE = 3  # 1 fois sur 3, l'offre d'une faction amie est sa mission d'entrée
CHANCE_CONTACT = 3  # 1 fois sur 3, l'offre passe par un PNJ que le joueur connaît
CHANCE_TRAME = 4  # 1 mission secondaire sur 4 touche la trame
TRAME = "trame"
MELEE = "mêlée"


@lru_cache(maxsize=1)
def retournements() -> list[str]:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))["retournements"]


def danger_tire(des: Des, cran: str, decalage: int = 0) -> str:
    """Le plus souvent le danger de l'expérience de départ ; parfois un cran en dessous (1 à 3 sur 1d10),
    rarement un cran au-dessus (10)."""
    jet = des.lancer(10)
    rang = DANGERS.index(DANGER_DE_DEPART.get(cran, "simple")) + decalage + (-1 if jet <= 3 else 1 if jet == 10 else 0)
    return DANGERS[max(0, min(len(DANGERS) - 1, rang))]


def _commanditaires(etat: dict) -> list[str]:
    """Qui peut proposer du travail au joueur ici : les factions du district qui ne lui sont pas hostiles (à
    défaut, celles de toute la carte). La faction dominante compte double : elle propose le plus."""
    district = etat["quartiers"][etat["ici"]]["district"]
    def acceptent(noms):
        return sorted(f for f in noms if monde.reputation(etat, f) not in (HOSTILE, RECHERCHE))
    locales = acceptent({etat["quartiers"][q]["maitre"] for q in etat["districts"][district]})
    dominant = monde.domine(etat, district)
    if dominant in locales:
        locales.append(dominant)
    return locales or acceptent(etat["factions"])


def _numero(etat: dict) -> str:
    etat["numero_offre"] = etat.get("numero_offre", 0) + 1
    return f"mission_{etat['numero_offre']}"


def _texte(offre: dict) -> str:
    """La mission en une phrase : ce que le joueur en sait."""
    return f"{offre['objectif'].capitalize()}, pour {offre['commanditaire']}, {a(offre['lieu'])}, contre {offre['cible']}."


def tirer_offre(etat: dict, des: Des, jour: int, cran: str = DEBUTANT, contacts: list[str] = ()) -> dict | None:
    """Tire l'ossature d'une mission. None si personne, sur la carte, ne veut du joueur."""
    possibles = _commanditaires(etat)
    autres = sorted(set(etat["factions"]))
    if not possibles or len(autres) < 2:
        return None
    commanditaire = monde._choisir(des, possibles)
    ennemies = [f for f in autres if monde.hostiles(etat, commanditaire, f)] or [f for f in autres if f != commanditaire]
    cible = monde._choisir(des, ennemies)
    objectif = monde._choisir(des, OBJECTIFS)
    tient = commanditaire if objectif == DEFENDRE else cible
    lieux = sorted(q for q, f in etat["quartiers"].items() if f["maitre"] == tient) or sorted(etat["quartiers"])
    lieu = monde._choisir(des, lieux)
    domine = monde.domine(etat, etat["quartiers"][etat["ici"]]["district"]) == commanditaire
    danger = danger_tire(des, cran)
    offre = {
        "id": _numero(etat), "commanditaire": commanditaire, "objectif": objectif, "lieu": lieu, "cible": cible,
        "danger": danger,
        # La faction qui domine le district paie le mieux : un palier au-dessus du barème
        "prime": 1 if domine else 0,
        "recompense": decaler(gains.RECOMPENSES[danger], 1 if domine else 0),
        "retournement": monde._choisir(des, retournements()) if des.lancer(CHANCE_RETOURNEMENT) == 1 else None,
        "expire": jour, "source": "faction",
    }
    if etat["quartiers"][lieu]["maitre"] == tient:
        if objectif == DEFENDRE:
            offre["controle"] = POINTS_DE_CONTROLE
        elif objectif in CONTRE_LE_QUARTIER:
            offre["controle"] = -POINTS_DE_CONTROLE
    if monde.reputation(etat, commanditaire) == AMI and des.lancer(CHANCE_ENTREE) == 1:
        offre["entree"] = True  # la réussir fait du joueur un membre
    if contacts and des.lancer(CHANCE_CONTACT) == 1:
        offre["contact"], offre["source"] = monde._choisir(des, sorted(contacts)), "contact"
    t = trame.trame_de(etat)
    if t and not trame.finie(t) and des.lancer(CHANCE_TRAME) == 1:
        offre["touche_la_trame"] = True  # un homme de l'antagoniste s'en mêle, ou un indice traîne
    occasion = next((e["texte"] for e in monde.en_cours(etat) if e["echelle"] == monde.QUARTIER), None)
    if occasion and offre["source"] == "faction" and not any(o.get("occasion") for o in etat.get("offres", [])):
        offre["occasion"], offre["source"] = occasion, "événement"
    offre["texte"] = _texte(offre)
    if lieux_.actifs(etat):
        ou = lieux_.endroit(etat, des, lieu)
        if ou:
            offre["endroit"] = ou
            offre["texte"] += f" Sur place : {ou}."
    return offre


def tirer_principale(etat: dict, des: Des) -> dict:
    """La mission principale suivante (REGLES.md 14.9) : sa cible est l'antagoniste, son danger celui de l'acte,
    et elle ne disparaît jamais. Le commanditaire est un ennemi de l'antagoniste qui veut bien du joueur ; à
    défaut, n'importe qui d'autre."""
    t = etat["trame"]
    antagoniste = t["antagoniste"]
    autres = [f for f in sorted(etat["factions"]) if f != antagoniste]
    fiables = [f for f in autres if monde.reputation(etat, f) not in (HOSTILE, RECHERCHE)]
    ennemis = [f for f in fiables if monde.hostiles(etat, f, antagoniste)]
    commanditaire = monde._choisir(des, ennemis or fiables or autres)
    objectif = monde._choisir(des, OBJECTIFS)
    tient = commanditaire if objectif == DEFENDRE else antagoniste
    lieux = sorted(q for q, f in etat["quartiers"].items() if f["maitre"] == tient) or sorted(etat["quartiers"])
    danger = trame.danger_principal(t)
    offre = {"id": _numero(etat), "commanditaire": commanditaire, "objectif": objectif,
             "lieu": monde._choisir(des, lieux), "cible": antagoniste, "danger": danger, "prime": 0,
             "recompense": gains.RECOMPENSES[danger],
             "retournement": monde._choisir(des, retournements()) if des.lancer(CHANCE_RETOURNEMENT) == 1 else None,
             "expire": None, "source": TRAME, "principale": True, "acte": t["acte"]}
    if trame.est_la_finale(t):
        offre["finale"] = True
    offre["texte"] = _texte(offre)
    return offre


def tenir_la_trame(etat: dict, des: Des, jour: int) -> dict | None:
    """Ouvre la mission principale quand son heure est venue : une seule à la fois, et jamais avant la date
    que le code a tirée. Renvoie l'offre ouverte, s'il y en a une."""
    t = trame.trame_de(etat)
    if t is None or trame.finie(t):
        return None
    offres = etat.setdefault("offres", [])
    if t["principale"] is None and jour >= t["prochaine"]:
        offre = tirer_principale(etat, des)
        offres.append(offre)
        t["principale"] = offre["id"]
        return offre
    return next((o for o in offres if o["id"] == t["principale"]), None)


def _offres_de_melee(etat: dict, des: Des, cran: str) -> list[dict]:
    """Chaque mêlée annoncée fait recruter les deux camps, s'ils veulent bien du joueur."""
    offres = []
    for quartier in monde.melees_annoncees(etat):
        if any(o["source"] == MELEE and o["lieu"] == quartier for o in etat.get("offres", [])):
            continue
        q = etat["quartiers"][quartier]
        for camp, (pour, contre) in ((monde.DEFENSE, (q["maitre"], q["attaquant"])),
                                     (monde.ATTAQUE, (q["attaquant"], q["maitre"]))):
            if monde.reputation(etat, pour) in (HOSTILE, RECHERCHE):
                continue
            danger = danger_tire(des, cran)
            offre = {"id": _numero(etat), "commanditaire": pour, "cible": contre, "lieu": quartier,
                     "objectif": DEFENDRE if camp == monde.DEFENSE else "prendre part à l'attaque", "danger": danger,
                     "prime": 0, "recompense": gains.RECOMPENSES[danger], "retournement": None,
                     "expire": q["attaque"] + 1, "source": MELEE, "camp": camp}
            offre["texte"] = (f"Se battre pour {pour} dans la mêlée {de(quartier)}, côté {camp}, contre {contre}.")
            offres.append(offre)
    return offres


def renouveler(etat: dict, des: Des, jour: int, cran: str = DEBUTANT, contacts: list[str] = ()) -> list[dict]:
    """Tient les offres à jour : celles dont la date est passée disparaissent (quelqu'un d'autre a fait le
    travail) ; quand vient le renouvellement, 1d3 offres neuves s'ouvrent dans le district, pour 1d5 jours.
    Une mêlée annoncée ajoute les offres des deux camps. Renvoie les offres ouvertes."""
    offres = etat.setdefault("offres", [])
    if jour >= etat.get("prochaines_offres", 0):
        offres[:] = [o for o in offres if o["source"] in (MELEE, TRAME)]  # la piste principale ne disparaît jamais
        nombre, prochain = des.lancer(OFFRES_MAX), jour + des.lancer(RENOUVELLEMENT)
        for _ in range(nombre):
            offre = tirer_offre(etat, des, prochain, cran, contacts)
            if offre:
                offres.append(offre)
        etat["prochaines_offres"] = prochain
    offres[:] = [o for o in offres if o["source"] != MELEE or o["expire"] > jour]
    offres += _offres_de_melee(etat, des, cran)
    tenir_la_trame(etat, des, jour)
    return offres


def offre(etat: dict, identifiant: str) -> dict:
    trouvee = next((o for o in etat.get("offres", []) if o["id"] == identifiant), None)
    if trouvee is None:
        ouvertes = [o["id"] for o in etat.get("offres", [])]
        raise monde.MondeImpossible(f"Pas d'offre « {identifiant} ». Offres ouvertes : {ouvertes or 'aucune'}.")
    return trouvee


def prendre(etat: dict, identifiant: str) -> dict:
    """Le joueur accepte une offre : elle quitte la liste. Renvoie ce qu'il faut garder pour sa conclusion."""
    prise = offre(etat, identifiant)
    etat["offres"].remove(prise)
    return {cle: prise[cle] for cle in ("commanditaire", "cible", "lieu", "objectif", "controle", "entree", "camp",
                                        "principale", "finale", "acte", "touche_la_trame") if cle in prise}


def resume(o: dict) -> dict:
    """Ce que le MJ montre d'une offre : tout, sauf le retournement."""
    vue = {cle: o[cle] for cle in ("id", "texte", "danger", "recompense") if cle in o}
    for cle in ("contact", "occasion"):
        if cle in o:
            vue[cle] = o[cle]
    if o.get("entree"):
        vue["mission_d_entree"] = f"réussie, elle le fait entrer chez {o['commanditaire']}"
    if o.get("principale"):
        vue["mission_principale"] = "la mission finale" if o.get("finale") else f"acte {o['acte']} : elle attend le joueur"
    return vue


def conclure(etat: dict, des: Des, mission: dict, reussie: bool, jour: int) -> list[str]:
    """Ce qu'une mission change à sa fin (REGLES.md 14.8), en plus de l'argent : la réputation chez le
    commanditaire et chez la cible, le contrôle du quartier si la mission le visait, et l'entrée dans la
    faction si c'était sa mission d'entrée. Renvoie les changements, en clair."""
    commanditaire, cible = mission["commanditaire"], mission["cible"]
    if not reussie:
        return monde.bouger_reputation(etat, commanditaire, -1)
    rivale = etat["factions"][commanditaire]["rivale"]
    changements = monde.bouger_reputation(etat, commanditaire, +1)  # sa rivale désignée baisse d'un cran
    if cible != rivale:
        changements += monde.bouger_reputation(etat, cible, -1)
    if mission.get("entree") and monde.reputation(etat, commanditaire) == AMI:
        changements.append(monde.entrer(etat, commanditaire))
    points, lieu = mission.get("controle"), mission.get("lieu")
    if points and lieu in etat["quartiers"]:
        q = etat["quartiers"][lieu]
        if points > 0 and q["maitre"] == commanditaire:
            q["controle"] = min(monde.CONTROLE_MAX, q["controle"] + points)
            changements.append(f"{lieu} : contrôle {q['controle']} pour {commanditaire}")
        elif points < 0 and q["maitre"] == cible:
            q["controle"] += points
            if q["controle"] <= 0:
                q["maitre"], q["controle"] = commanditaire, monde.CONTROLE_PRISE
                q["attaque"], q["attaquant"] = None, None
                q.pop("annoncee", None)
                changements.append(f"{lieu} change de mains : {commanditaire} le prend à {cible}")
                monde.noter(etat, jour, monde.QUARTIER, lieu,
                            f"{lieu} change de mains : victoire {de(commanditaire)} sur {cible}.",
                            [commanditaire, cible], "mission")
                monde.planifier(etat, des, jour)
            else:
                changements.append(f"{lieu} : contrôle {q['controle']} pour {cible}")
    return changements

