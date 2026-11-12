"""Le monde qui vit (REGLES.md 14.3 à 14.6) : la carte, les factions, le contrôle des quartiers, les mêlées
et la réputation du joueur.

L'état du monde est un dictionnaire, rangé tel quel dans la sauvegarde. Le code tire tout : la carte à la
création de la campagne, puis les attaques et leur résultat au fil des jours. Le MJ ne décide de rien ici ;
il reçoit les nouvelles et les raconte.

Une campagne d'avant ce module n'a pas de monde (None) : elle se joue comme avant, sans carte.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache

from aria import chemins
from aria.des import Des

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "monde.json"

# La taille de la carte selon le cadre : districts, quartiers (de… à…), factions
TAILLES = {"bourg": (1, (3, 4), 3), "ville": (3, (8, 10), 5), "mégapole": (6, (18, 20), 8)}

GANG, CORPORATION, AUTORITES, SYNDICAT, MILICE = ("gang", "corporation", "autorités", "syndicat ou guilde",
                                                  "milice ou culte")
TYPES = (GANG, CORPORATION, AUTORITES, SYNDICAT, MILICE)
HORS_LA_LOI = (GANG, MILICE)

CONTROLE_MAX = 10
CONTROLE_PRISE = 5  # un quartier qui vient de changer de mains
BONUS_MAX = 3  # par camp, dans une mêlée
ECART_DOUBLE = 5  # un écart de dés de 5 ou plus déplace 2 points
ATTAQUE, DEFENSE = "attaque", "défense"

RECHERCHE, HOSTILE, NEUTRE, AMI, MEMBRE = "recherché", "hostile", "neutre", "ami", "membre"
REPUTATIONS = (RECHERCHE, HOSTILE, NEUTRE, AMI, MEMBRE)

QUARTIER, VILLE, MONDE = "quartier", "ville", "monde"
POIDS = {QUARTIER: 1, VILLE: 2, MONDE: 3}
NOUVELLES_AU_MJ = 3
JOURNAL_MAX = 200  # les entrées gardées dans la sauvegarde

# Ce qu'un clan prépare sans le joueur, quand son dé de préparation tombe sur 5 ou 6
PREPARATIFS = {ATTAQUE: ("un repérage des lieux", "un complice à l'intérieur", "un sabotage la veille",
                         "un arrivage d'armes"),
               DEFENSE: ("des barricades", "des guetteurs sur les toits", "un piège dans la rue principale",
                         "un brouillage des communications")}


class MondeImpossible(ValueError):
    """Ce que les règles du monde ne permettent pas : le message est renvoyé tel quel au MJ."""


# --- La bibliothèque ------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _bibliotheque() -> dict:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))


def noms_du_genre(genre: str) -> dict:
    """Les noms de districts, de quartiers, de factions et de chefs du genre ; ceux du jeu générique sinon."""
    b = _bibliotheque()
    return b["genres"].get(genre, b["generique"])


def _choisir(des: Des, liste):
    return liste[des.lancer(len(liste)) - 1]


def _melanger(des: Des, liste) -> list:
    reste, tire = list(liste), []
    while reste:
        tire.append(reste.pop(des.lancer(len(reste)) - 1))
    return tire


# --- La création de la carte ----------------------------------------------------------------------------

def creer(des: Des, genre: str, taille: str | None = None) -> dict:
    """Tire la carte d'une campagne : ses districts, ses quartiers et leurs voisins, ses factions, leurs
    rivales et leurs territoires, d'un seul tenant. Le joueur commence neutre partout."""
    noms = noms_du_genre(genre)
    nb_districts, (mini, maxi), nb_factions = TAILLES[taille or noms["taille"]]
    nb_quartiers = mini + des.lancer(maxi - mini + 1) - 1
    districts = _melanger(des, noms["districts"])[:nb_districts]
    quartiers = _melanger(des, noms["quartiers"])[:nb_quartiers]

    # Les quartiers répartis entre les districts, à parts presque égales
    carte, debut = {}, 0
    for i, district in enumerate(districts):
        nombre = nb_quartiers // nb_districts + (1 if i < nb_quartiers % nb_districts else 0)
        carte[district] = quartiers[debut:debut + nombre]
        debut += nombre

    # Les voisins : une boucle dans chaque district, et un passage d'un district au suivant
    voisins = {q: set() for q in quartiers}

    def relier(a: str, b: str):
        if a != b:
            voisins[a].add(b)
            voisins[b].add(a)

    for membres in carte.values():
        for a, b in zip(membres, membres[1:]):
            relier(a, b)
        if len(membres) > 2:
            relier(membres[-1], membres[0])
    for i, district in enumerate(districts):
        if nb_districts > 1 and (i + 1 < nb_districts or nb_districts > 2):
            relier(carte[district][-1], carte[districts[(i + 1) % nb_districts]][0])

    # Les factions : toujours des autorités si le genre en a, puis des types tirés
    reserve = {t: _melanger(des, n) for t, n in noms["factions"].items() if n}
    chefs = _melanger(des, noms["chefs"])
    factions = {}

    def ajouter(type_: str):
        factions[reserve[type_].pop()] = {"type": type_, "chef": chefs.pop() if chefs else "", "rivale": ""}

    if reserve.get(AUTORITES):
        ajouter(AUTORITES)
    while len(factions) < nb_factions and any(reserve.values()):
        ajouter(_choisir(des, sorted(t for t, n in reserve.items() if n)))
    ordre = _melanger(des, sorted(factions))
    for a, b in zip(ordre[::2], ordre[1::2]):
        factions[a]["rivale"], factions[b]["rivale"] = b, a
    if len(ordre) % 2 and len(ordre) > 1:
        factions[ordre[-1]]["rivale"] = _choisir(des, ordre[:-1])

    # Les territoires : chaque faction part d'un quartier et s'étend de proche en proche
    maitres = dict(zip(_melanger(des, quartiers), ordre))
    while len(maitres) < len(quartiers):
        for faction in ordre:
            libres = sorted({v for q, m in maitres.items() if m == faction for v in voisins[q] if v not in maitres})
            if libres:
                maitres[_choisir(des, libres)] = faction

    etat = {
        "districts": carte,
        "quartiers": {q: {"district": next(d for d, m in carte.items() if q in m), "voisins": sorted(voisins[q]),
                          "maitre": maitres[q], "controle": 3 + des.lancer(5), "attaque": None, "attaquant": None}
                      for q in quartiers},
        "factions": factions,
        "reputation": {f: NEUTRE for f in factions},
        "ici": _choisir(des, quartiers),
        "journal": [],
        "lu": 0,
    }
    planifier(etat, des, 1)
    return etat


# --- Qui est hostile à qui, qui domine quoi -------------------------------------------------------------

def hostiles(etat: dict, a: str, b: str) -> bool:
    """Deux factions se battent si l'une est la rivale désignée de l'autre, si ce sont deux bandes hors la
    loi, ou si l'une est hors la loi et l'autre représente les autorités."""
    if a == b:
        return False
    fa, fb = etat["factions"][a], etat["factions"][b]
    if fa["rivale"] == b or fb["rivale"] == a:
        return True
    types = {fa["type"], fb["type"]}
    return types <= set(HORS_LA_LOI) or (AUTORITES in types and bool(types & set(HORS_LA_LOI)))


def attaquants(etat: dict, quartier: str) -> list[str]:
    """Les factions hostiles qui tiennent un quartier voisin : celles qui peuvent l'attaquer."""
    q = etat["quartiers"][quartier]
    return sorted({etat["quartiers"][v]["maitre"] for v in q["voisins"]
                   if hostiles(etat, q["maitre"], etat["quartiers"][v]["maitre"])})


def dispute(etat: dict, quartier: str) -> bool:
    return bool(attaquants(etat, quartier))


def domine(etat: dict, district: str) -> str | None:
    """La faction qui tient plus de la moitié des quartiers du district ; None : la guerre y est ouverte."""
    membres = etat["districts"][district]
    compte = {}
    for q in membres:
        maitre = etat["quartiers"][q]["maitre"]
        compte[maitre] = compte.get(maitre, 0) + 1
    faction, nombre = max(compte.items(), key=lambda c: (c[1], c[0]))
    return faction if nombre * 2 > len(membres) else None


def planifier(etat: dict, des: Des, jour: int):
    """Chaque quartier disputé a sa prochaine attaque, 1d3 jours plus tard, et son attaquant ; un quartier
    qui n'est plus disputé n'en a plus."""
    for nom in sorted(etat["quartiers"]):
        q, possibles = etat["quartiers"][nom], attaquants(etat, nom)
        if not possibles:
            q["attaque"], q["attaquant"] = None, None
            q.pop("annoncee", None)
        elif q["attaque"] is None:
            q["attaque"], q["attaquant"] = jour + des.lancer(3), _choisir(des, possibles)
        elif q["attaquant"] not in possibles:
            q["attaquant"] = _choisir(des, possibles)


# --- La réputation --------------------------------------------------------------------------------------

def reputation(etat: dict, faction: str) -> str:
    return etat["reputation"].get(faction, NEUTRE)


def bouger_reputation(etat: dict, faction: str, sens: int, rivale: bool = True) -> list[str]:
    """Monte ou baisse d'un cran. On ne devient pas membre en montant : cela se demande (voir entrer). Aider
    une faction baisse d'un cran sa rivale désignée. Renvoie les changements, en clair."""
    avant = reputation(etat, faction)
    rang = REPUTATIONS.index(avant)
    if sens > 0:
        rang = rang if avant == MEMBRE else min(rang + 1, REPUTATIONS.index(AMI))
    else:
        rang = max(rang - 1, 0)
    etat["reputation"][faction] = REPUTATIONS[rang]
    changements = [] if REPUTATIONS[rang] == avant else [f"{faction} : {avant} → {REPUTATIONS[rang]}"]
    autre = etat["factions"][faction]["rivale"]
    if sens > 0 and rivale and autre:
        changements += bouger_reputation(etat, autre, -1, rivale=False)
    return changements


def entrer(etat: dict, faction: str) -> str:
    """Le joueur devient membre : il faut être ami, et avoir réussi la mission d'entrée."""
    if reputation(etat, faction) != AMI:
        raise MondeImpossible(f"Pour entrer chez {faction}, il faut d'abord y être ami.")
    etat["reputation"][faction] = MEMBRE
    return f"{faction} : {AMI} → {MEMBRE}"


# --- Le journal du monde --------------------------------------------------------------------------------

def noter(etat: dict, jour: int, echelle: str, lieu: str, texte: str, factions: list[str] = (), genre: str = "") -> dict:
    entree = {"jour": jour, "echelle": echelle, "lieu": lieu, "texte": texte, "factions": list(factions),
              "genre": genre}
    etat["journal"].append(entree)
    en_trop = len(etat["journal"]) - JOURNAL_MAX
    if en_trop > 0:
        del etat["journal"][:en_trop]
        etat["lu"] = max(0, etat["lu"] - en_trop)
    return entree


def _touche_le_joueur(etat: dict, entree: dict) -> bool:
    ici = etat["ici"]
    district = etat["quartiers"][ici]["district"]
    return (entree["lieu"] in (ici, district)
            or any(reputation(etat, f) != NEUTRE for f in entree.get("factions", [])))


def nouvelles(etat: dict, maximum: int = NOUVELLES_AU_MJ) -> list[str]:
    """Les nouvelles que le MJ n'a pas encore reçues, les plus importantes d'abord : la plus grande échelle,
    puis ce qui touche le joueur, puis le plus récent. Les autres restent dans le journal."""
    fraiches = etat["journal"][etat["lu"]:]
    etat["lu"] = len(etat["journal"])
    classees = sorted(fraiches, key=lambda e: (-POIDS[e["echelle"]], not _touche_le_joueur(etat, e), -e["jour"]))
    return [f"Jour {e['jour']} — {e['texte']}" for e in classees[:maximum]]


# --- Les mêlées -----------------------------------------------------------------------------------------

@dataclass
class Melee:
    quartier: str
    attaquant: str
    defenseur: str
    de_attaque: int
    de_defense: int
    bonus_attaque: int
    bonus_defense: int
    points: int  # ce que le quartier a gagné (défense victorieuse) ou perdu (attaque victorieuse)
    pris: bool
    controle: int
    raisons: list[str] = field(default_factory=list)  # ce que chaque camp avait préparé
    reputation: list[str] = field(default_factory=list)

    @property
    def vainqueur(self) -> str | None:
        return self.attaquant if self.points < 0 or self.pris else self.defenseur if self.points > 0 else None


def _bonus_du_clan(des: Des, camp: str, raisons: list[str]) -> int:
    jet = des.lancer(6)
    if jet < 5:
        return 0
    raisons.append(f"{camp} : {_choisir(des, PREPARATIFS[camp])}")
    return jet - 4


def resoudre(etat: dict, des: Des, quartier: str, jour: int | None = None) -> Melee:
    """La mêlée d'un quartier attaqué : 1d10 contre 1d10, avec les bonus de chaque camp (plafonnés à +3).
    Le vainqueur déplace 1 point de contrôle, 2 si l'écart est de 5 ou plus ; à 0, le quartier change de
    mains et repart à 5. Ce que le joueur a préparé ou gagné l'arme au poing compte pour son camp."""
    q = etat["quartiers"][quartier]
    attaquant, defenseur = q["attaquant"], q["maitre"]
    if attaquant is None:
        raise MondeImpossible(f"{quartier} n'est pas attaqué.")
    jour = q["attaque"] if jour is None else jour
    raisons, joueur = [], q.pop("joueur", None)
    bonus = {ATTAQUE: (1 if domine(etat, q["district"]) == attaquant else 0) + _bonus_du_clan(des, ATTAQUE, raisons),
             DEFENSE: (1 if domine(etat, q["district"]) == defenseur else 0) + _bonus_du_clan(des, DEFENSE, raisons)}
    if joueur:
        bonus[joueur["camp"]] += joueur.get("preparatif", 0) + joueur.get("combat", 0)
    bonus = {camp: min(valeur, BONUS_MAX) for camp, valeur in bonus.items()}
    de_attaque, de_defense = des.lancer(10), des.lancer(10)
    ecart = (de_attaque + bonus[ATTAQUE]) - (de_defense + bonus[DEFENSE])
    points = 0 if ecart == 0 else (2 if abs(ecart) >= ECART_DOUBLE else 1) * (-1 if ecart > 0 else 1)
    pris = False
    if points < 0:
        q["controle"] += points
        if q["controle"] <= 0:
            q["maitre"], q["controle"], pris = attaquant, CONTROLE_PRISE, True
            texte = f"{attaquant} prend {quartier} à {defenseur}."
        else:
            texte = f"{attaquant} gagne du terrain à {quartier}, que tient encore {defenseur}."
    elif points > 0:
        q["controle"] = min(CONTROLE_MAX, q["controle"] + points)
        texte = f"{defenseur} repousse {attaquant} à {quartier}."
    else:
        texte = f"{attaquant} et {defenseur} s'affrontent à {quartier}, sans vainqueur."
    melee = Melee(quartier, attaquant, defenseur, de_attaque, de_defense, bonus[ATTAQUE], bonus[DEFENSE], points,
                  pris, q["controle"], raisons)
    if joueur:  # s'en mêler se paie : le camp d'en face s'en souvient, le sien aussi s'il a gagné
        sien, autre = (attaquant, defenseur) if joueur["camp"] == ATTAQUE else (defenseur, attaquant)
        if melee.vainqueur == sien:
            melee.reputation += bouger_reputation(etat, sien, +1, rivale=False)
        melee.reputation += bouger_reputation(etat, autre, -1)
    noter(etat, jour, QUARTIER, quartier, texte, [attaquant, defenseur], "mêlée")
    q["attaque"], q["attaquant"] = None, None
    q.pop("annoncee", None)
    planifier(etat, des, jour)
    return melee


def _prevenu(etat: dict, quartier: str, jour: int) -> bool:
    """Le joueur sait-il qu'on va se battre ici ? La veille s'il est membre d'un des deux camps ; le jour
    même s'il y est ami, ou s'il se trouve dans le quartier."""
    q = etat["quartiers"][quartier]
    delai = q["attaque"] - jour
    crans = {reputation(etat, q["maitre"]), reputation(etat, q["attaquant"])}
    return (MEMBRE in crans and delai <= 1) or ((AMI in crans or quartier == etat["ici"]) and delai <= 0)


def melees_annoncees(etat: dict) -> list[str]:
    """Les quartiers où une mêlée est annoncée au joueur, et pas encore jouée."""
    return sorted(nom for nom, q in etat["quartiers"].items() if q.get("annoncee"))


def avancer(etat: dict, des: Des, jour: int) -> list[Melee]:
    """Fait vivre la carte jusqu'à ce jour : les attaques dont la date est passée sont jouées, dans l'ordre.
    Une mêlée dont le joueur est prévenu est d'abord annoncée, et attend la fin de sa journée : il peut s'y
    préparer ou s'y battre. Renvoie les mêlées jouées."""
    jouees = []
    for _ in range(2000):  # borne de sûreté : chaque mêlée repousse la suivante d'un jour au moins
        dues = sorted((q["attaque"], nom) for nom, q in etat["quartiers"].items()
                      if q["attaque"] is not None and q["attaque"] < jour
                      or (q["attaque"] == jour and not _prevenu(etat, nom, jour)))
        if not dues:
            break
        jouees.append(resoudre(etat, des, dues[0][1]))
    for nom in sorted(etat["quartiers"]):
        q = etat["quartiers"][nom]
        if q["attaque"] is not None and not q.get("annoncee") and _prevenu(etat, nom, jour):
            q["annoncee"] = True
            quand = "aujourd'hui" if q["attaque"] <= jour else "demain"
            noter(etat, jour, QUARTIER, nom, f"{q['attaquant']} s'apprête à attaquer {nom}, tenu par {q['maitre']} : "
                                             f"c'est pour {quand}.", [q["attaquant"], q["maitre"]], "annonce")
    return jouees


# --- Le joueur dans une mêlée ---------------------------------------------------------------------------

def _melee_du_joueur(etat: dict, quartier: str, camp: str) -> dict:
    q = etat["quartiers"].get(quartier)
    if q is None or not q.get("annoncee"):
        raise MondeImpossible(f"Aucune mêlée n'est annoncée à {quartier}. Annoncées : {melees_annoncees(etat) or 'aucune'}.")
    if camp not in (ATTAQUE, DEFENSE):
        raise MondeImpossible(f"Le camp : « {ATTAQUE} » ou « {DEFENSE} ».")
    joueur = q.setdefault("joueur", {"camp": camp})
    if joueur["camp"] != camp:
        raise MondeImpossible(f"Il a déjà choisi son camp dans cette mêlée : {joueur['camp']}.")
    return joueur


def preparer(etat: dict, quartier: str, camp: str, bonus: int):
    """Le préparatif du joueur, un seul par mêlée : +1, +2 ou +3 au dé de son camp (0 s'il a raté son test)."""
    joueur = _melee_du_joueur(etat, quartier, camp)
    if "preparatif" in joueur:
        raise MondeImpossible("Un seul préparatif par mêlée : il a déjà préparé celle-ci.")
    joueur["preparatif"] = bonus


def se_battre(etat: dict, quartier: str, camp: str, victoire: bool):
    """Le joueur s'est battu dans la mêlée : +2 au dé de son camp s'il a gagné, −2 s'il a perdu ou fui."""
    _melee_du_joueur(etat, quartier, camp)["combat"] = 2 if victoire else -2


def camps(etat: dict, quartier: str) -> dict[str, str]:
    q = etat["quartiers"][quartier]
    return {ATTAQUE: q["attaquant"], DEFENSE: q["maitre"]}


# --- Ce que le joueur et le MJ lisent -------------------------------------------------------------------

def situation(etat: dict, quartier: str | None = None) -> dict:
    """Ce qu'il faut savoir d'un quartier (celui du joueur par défaut) : qui le tient, qui domine le district."""
    nom = quartier or etat["ici"]
    q = etat["quartiers"][nom]
    maitre = q["maitre"]
    dominant = domine(etat, q["district"])
    resultat = {"quartier": nom, "district": q["district"], "maitre": maitre,
                "type": etat["factions"][maitre]["type"], "controle": q["controle"], "dispute": dispute(etat, nom),
                "district_domine_par": dominant or "personne : guerre ouverte",
                "reputation": {f: r for f, r in etat["reputation"].items() if r != NEUTRE}}
    if q.get("annoncee"):
        resultat["melee"] = {"attaquant": q["attaquant"], "defenseur": maitre}
    return resultat


def carte(etat: dict) -> list[str]:
    """La carte, pour le joueur : qui tient quoi, où l'on se bat, et ce que chaque faction pense de lui."""
    lignes = []
    for district, membres in etat["districts"].items():
        dominant = domine(etat, district)
        lignes.append(f"{district} — " + (f"dominé par {dominant}" if dominant else "guerre ouverte"))
        for nom in membres:
            q = etat["quartiers"][nom]
            details = [f"contrôle {q['controle']}"] + (["disputé"] if dispute(etat, nom) else [])
            lignes.append(f"  {nom} : {q['maitre']} ({', '.join(details)})" + ("  ← tu es ici" if nom == etat["ici"] else ""))
    lignes.append("Les factions :")
    for nom in sorted(etat["factions"]):
        f = etat["factions"][nom]
        tenus = sum(q["maitre"] == nom for q in etat["quartiers"].values())
        lignes.append(f"  {nom} ({f['type']}, {tenus} quartier{'s' if tenus > 1 else ''}) — {f['chef']} ; "
                      f"rivale : {f['rivale'] or 'aucune'} ; toi : {reputation(etat, nom)}")
    return lignes
