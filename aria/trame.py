"""La trame d'une campagne (REGLES.md 14) : son type, et l'expérience de départ du personnage.

Le type fixe la longueur de la trame (ses actes et ses missions principales), la vitesse de progression et
la façon d'ouvrir. Il est choisi à la création de la campagne, avec l'expérience de départ, et rangé dans
le dossier de la campagne (campagne.json) : la création du personnage, l'amorce puis la trame le relisent.
"""

import json
from dataclasses import asdict, dataclass
from functools import lru_cache

from aria import chemins, monde
from aria.campagne import Campagne
from aria.des import Des
from aria.personnage import AGUERRI, CRANS, DEBUTANT, VETERAN  # noqa: F401 (réexportés pour le menu)

AU_COEUR, PLAN, QUOTIDIEN = "au cœur du problème", "la situation lance le plan", "le quotidien"
CONSIGNES = {
    AU_COEUR: "L'ouverture se fait au cœur du problème : le commanditaire ou la menace est déjà dans la "
              "situation, et le personnage doit réagir tout de suite.",
    PLAN: "",
    QUOTIDIEN: "L'ouverture se fait sur le quotidien du personnage : la situation montre sa vie ordinaire, et le "
               "plan n'y apparaît que comme un détail qui cloche. Le vrai problème viendra plus tard.",
}


@dataclass(frozen=True)
class TypeCampagne:
    nom: str
    actes: tuple[int, ...]  # les missions principales de chaque acte
    xp: int  # par mission principale réussie
    depart: str  # l'expérience de départ conseillée
    ouverture: str
    description: str
    sans_fin: bool = False  # un arc terminé en ouvre un autre

    @property
    def consigne(self) -> str:
        """Ce que l'amorce doit savoir de l'ouverture (vide : l'amorce ordinaire)."""
        return CONSIGNES[self.ouverture]

    @property
    def principales(self) -> int:
        return sum(self.actes)


CONTRAT, COURTE, STANDARD, LONGUE, SANS_FIN = "contrat", "courte", "standard", "longue", "sans fin"
TYPES = {t.nom: t for t in (
    TypeCampagne(CONTRAT, (1,), 0, AGUERRI, AU_COEUR, "une seule mission, une soirée"),
    TypeCampagne(COURTE, (1, 2, 1), 3, AGUERRI, AU_COEUR, "3 actes, 4 missions principales"),
    TypeCampagne(STANDARD, (2, 4, 2), 2, DEBUTANT, PLAN, "3 actes, 8 missions principales"),
    TypeCampagne(LONGUE, (2, 3, 4, 3, 2), 1, DEBUTANT, QUOTIDIEN, "5 actes, 14 missions principales"),
    TypeCampagne(SANS_FIN, (2, 4, 2), 1, DEBUTANT, QUOTIDIEN, "des arcs qui s'enchaînent, sans dernière page",
                 sans_fin=True),
)}


@dataclass
class Format:
    """Ce qui a été choisi à la création de la campagne."""

    type: str = STANDARD
    cran: str = DEBUTANT


def lire_format(campagne: Campagne) -> Format:
    """Le format de la campagne ; celui par défaut si elle n'en a pas (une campagne d'avant) ou s'il est abîmé."""
    try:
        donnees = json.loads(campagne.format.read_text(encoding="utf-8"))
        format = Format(donnees["type"], donnees["cran"])
    except (OSError, ValueError, KeyError, TypeError):
        return Format()
    return format if format.type in TYPES and format.cran in CRANS else Format()


def ecrire_format(campagne: Campagne, format: Format):
    campagne.dossier.mkdir(parents=True, exist_ok=True)
    campagne.format.write_text(json.dumps(asdict(format), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --- La trame d'une campagne (REGLES.md 14.9 et 14.10) --------------------------------------------------
#
# Elle vit dans l'état du monde (etat["trame"]), donc dans la sauvegarde. Le code la tient : l'antagoniste,
# l'acte en cours, les missions principales faites, les indices et les couches du secret déjà ouvertes.
# Le MJ n'en reçoit que ce qu'il doit jouer maintenant (voir bloc).

BIBLIOTHEQUE = chemins.RESSOURCES / "bibliotheque" / "trame.json"

DANGERS = ("un service", "simple", "risquée", "dangereuse", "très dangereuse", "exceptionnelle")
# Le danger des missions principales monte d'un cran par acte
DANGERS_PAR_ACTE = {CONTRAT: ("risquée",), COURTE: ("risquée", "dangereuse", "très dangereuse"),
                    STANDARD: ("risquée", "dangereuse", "très dangereuse"),
                    LONGUE: ("simple", "risquée", "dangereuse", "très dangereuse", "exceptionnelle"),
                    SANS_FIN: ("risquée", "dangereuse", "très dangereuse")}
CRAN_DE_DANGER = {DEBUTANT: 0, AGUERRI: 1, VETERAN: 2}  # un personnage aguerri ou vétéran affronte plus fort
INDICES_PAR_COUCHE = {CONTRAT: 1, COURTE: 2, STANDARD: 3, LONGUE: 4, SANS_FIN: 3}
COUCHES = 3  # quelque chose cloche ; qui ; pourquoi
NOMS_DES_COUCHES = ("Ce qui cloche", "Qui est derrière", "Toute la vérité")
PREMIERE_PISTE = {AU_COEUR: 0, PLAN: 3, QUOTIDIEN: 5}  # 1dN jours avant la première mission principale
PAUSE_APRES_UN_TOURNANT = 5  # 1d5 jours
DETTE_DE_CICATRICE = 1000
INDICE_MAX = 200  # caractères

CONTACT_PERDU, QUARTIER_QUI_BASCULE, DETTE, LIEN_BLESSE = ("un contact perdu", "un quartier qui bascule",
                                                           "une dette", "une blessure pour le lien")
CICATRICES = (CONTACT_PERDU, QUARTIER_QUI_BASCULE, DETTE, LIEN_BLESSE)
CONSIGNES_DE_CICATRICE = {
    CONTACT_PERDU: "Un PNJ que le personnage connaît disparaît, se détourne de lui ou passe à l'ennemi : choisis "
                   "lequel, et note-le (noter_pnj).",
    LIEN_BLESSE: "Son lien paie pour lui : blessé, menacé ou compromis. Raconte-le, et joue le choc s'il y en a un.",
}
ROLES_DES_ACTES = ("L'antagoniste reste dans l'ombre : le personnage ne croise que ses hommes et ses traces.",
                   "L'antagoniste sait qu'on le cherche : il riposte, se couvre, achète ou menace.",
                   "L'affrontement : l'antagoniste est à découvert, et il joue tout.")


class TrameImpossible(ValueError):
    """Ce que les règles de la trame ne permettent pas : le message est renvoyé tel quel au MJ."""


@lru_cache(maxsize=1)
def _bibliotheque() -> dict:
    return json.loads(BIBLIOTHEQUE.read_text(encoding="utf-8"))


def creer(etat: dict, des: Des, type_: str = STANDARD, cran: str = DEBUTANT, jour: int = 1) -> dict:
    """Tire la trame d'une campagne dans son monde : l'antagoniste (une faction de la carte), le visage qui se
    cache derrière et ce qu'il veut. La première mission principale arrive tout de suite, ou quelques jours
    plus tard, selon la façon d'ouvrir du type de campagne."""
    b = _bibliotheque()
    visages = b["visages"].get(etat.get("genre", ""), b["visages"]["generique"])
    attente = PREMIERE_PISTE[TYPES[type_].ouverture]
    etat["trame"] = {
        "type": type_, "cran": cran,
        "antagoniste": monde._choisir(des, sorted(etat["factions"])),
        "visage": monde._choisir(des, visages), "but": monde._choisir(des, b["buts"]),
        "acte": 1, "faites": 0, "reussies": 0, "ratees": 0,
        "prochaine": jour + (des.lancer(attente) if attente else 0), "principale": None,
        "secret": [], "couches": 0, "indices": [], "dus": 0, "enquete": False, "cicatrices": [],
    }
    return etat["trame"]


def trame_de(etat: dict | None) -> dict | None:
    """La trame du monde, si la campagne en a une."""
    return etat.get("trame") if etat else None


def nombre_d_actes(t: dict) -> int:
    return len(TYPES[t["type"]].actes)


def dernier_acte(t: dict) -> bool:
    return t["acte"] >= nombre_d_actes(t)


def finie(t: dict) -> bool:
    return "fin" in t


def est_la_finale(t: dict) -> bool:
    """La prochaine mission principale est-elle la dernière du dernier acte ?"""
    return dernier_acte(t) and t["faites"] + 1 >= TYPES[t["type"]].actes[t["acte"] - 1]


def danger_principal(t: dict) -> str:
    """Le danger des missions principales de l'acte en cours, selon l'expérience de départ du personnage."""
    par_acte = DANGERS_PAR_ACTE[t["type"]]
    rang = DANGERS.index(par_acte[min(t["acte"], len(par_acte)) - 1]) + CRAN_DE_DANGER.get(t["cran"], 0)
    return DANGERS[min(rang, len(DANGERS) - 1)]


# --- Le secret et les indices ---------------------------------------------------------------------------

def poser_le_secret(t: dict, couches: list[str]):
    """Les trois couches du secret, écrites à l'amorce : ce qui cloche, qui, pourquoi."""
    t["secret"] = [c for c in couches if c][:COUCHES] if len([c for c in couches if c]) == COUCHES else []


def _ouvrir_les_couches(t: dict) -> list[dict]:
    """Ouvre les couches que les indices réunis permettent ; la dernière attend le dernier acte. Renvoie les
    révélations à jouer."""
    ouvrables = min(len(t["indices"]) // INDICES_PAR_COUCHE[t["type"]], COUCHES)
    if not dernier_acte(t):
        ouvrables = min(ouvrables, COUCHES - 1)
    revelations = []
    while t["couches"] < ouvrables:
        t["couches"] += 1
        texte = t["secret"][t["couches"] - 1] if len(t["secret"]) >= t["couches"] else ""
        revelations.append({"couche": NOMS_DES_COUCHES[t["couches"] - 1], "ce_qu_il_comprend": texte,
                            "consigne": "Joue une scène de révélation : le personnage comprend, et tu le dis au "
                                        "joueur en clair."})
    return revelations


def accorder_un_indice(t: dict):
    """Le moteur doit un indice au joueur : le MJ le décrira avec l'outil indice."""
    t["dus"] += 1


def texte_d_indice(description: str) -> str:
    """L'indice nettoyé ; refusé s'il est vide ou trop long."""
    texte = " ".join(str(description or "").split())
    if not 0 < len(texte) <= INDICE_MAX:
        raise TrameImpossible(f"L'indice : une phrase, {INDICE_MAX} caractères au plus ({len(texte)} ici).")
    return texte


def noter_un_indice(t: dict, jour: int, description: str) -> list[dict]:
    """Range l'indice décrit par le MJ, et ouvre les couches qu'il permet. Renvoie les révélations à jouer."""
    t["indices"].append({"jour": jour, "texte": texte_d_indice(description)})
    return _ouvrir_les_couches(t)


def indices_en_trop(t: dict) -> int:
    """Les indices au-delà de ce que demandent les trois couches : ils serviront dans la mission finale."""
    return max(0, len(t["indices"]) - COUCHES * INDICES_PAR_COUCHE[t["type"]])


# --- Après une mission ----------------------------------------------------------------------------------

def _cicatrice(etat: dict, des: Des, perso, jour: int) -> str:
    """Une mission principale ratée laisse une trace, tirée par le code."""
    t = etat["trame"]
    nature = monde._choisir(des, CICATRICES)
    if nature == QUARTIER_QUI_BASCULE:
        siens = {q for q, f in etat["quartiers"].items() if f["maitre"] == t["antagoniste"]}
        voisins = sorted({v for q in siens for v in etat["quartiers"][q]["voisins"]} - siens)
        if not voisins:
            nature = CONTACT_PERDU
        else:
            pris = monde._choisir(des, voisins)
            q = etat["quartiers"][pris]
            ancien = q["maitre"]
            q["maitre"], q["controle"], q["attaque"], q["attaquant"] = t["antagoniste"], monde.CONTROLE_PRISE, None, None
            q.pop("annoncee", None)
            monde.noter(etat, jour, monde.QUARTIER, pris, f"{pris} change de mains : victoire "
                        f"{monde.de(t['antagoniste'])} sur {ancien}.", [t["antagoniste"], ancien], "cicatrice")
            monde.planifier(etat, des, jour)
            texte = f"{QUARTIER_QUI_BASCULE} : {pris} passe {monde.a(t['antagoniste'])}."
    if nature == DETTE:
        perso.dettes.append({"creancier": t["antagoniste"], "echeance": DETTE_DE_CICATRICE // 10,
                             "reste": DETTE_DE_CICATRICE // 10 * 12, "manquees": 0})
        texte = (f"{DETTE} : il doit maintenant {DETTE_DE_CICATRICE} {monde.a(t['antagoniste'])}, "
                 f"{DETTE_DE_CICATRICE // 10} par semaine pendant 12 semaines.")
    if nature in CONSIGNES_DE_CICATRICE:
        texte = f"{nature} : {CONSIGNES_DE_CICATRICE[nature]}"
    t["cicatrices"].append({"jour": jour, "nature": nature})
    return texte


def apres_mission(etat: dict, des: Des, mission: dict, reussie: bool, jour: int, perso) -> dict:
    """Ce qu'une mission terminée change à la trame. Une mission principale : l'XP du type de campagne (la
    moitié si elle est ratée), un indice si elle est réussie, une cicatrice sinon, et le passage à l'acte
    suivant quand l'acte a eu toutes ses missions. Une mission secondaire qui touche la trame, réussie : un
    indice. Renvoie ce que le MJ doit en savoir."""
    t = trame_de(etat)
    if t is None or finie(t):
        return {}
    resultat = {}
    if mission.get("principale"):
        t["principale"] = None
        t["faites"] += 1
        t["reussies" if reussie else "ratees"] += 1
        gain = TYPES[t["type"]].xp if reussie else TYPES[t["type"]].xp // 2
        perso.xp += gain
        resultat["xp_gagnee"] = gain
        if reussie:
            accorder_un_indice(t)
        else:
            resultat["cicatrice"] = _cicatrice(etat, des, perso, jour)
        if mission.get("finale"):
            t["fin"] = {"finale_reussie": reussie, "jour": jour}
            resultat["finale"] = "réussie" if reussie else "ratée"
            resultat["fin_de_la_campagne"] = finir(etat, des, jour)
        elif t["faites"] >= TYPES[t["type"]].actes[t["acte"] - 1]:
            t["acte"], t["faites"] = t["acte"] + 1, 0
            t["prochaine"] = jour + des.lancer(PAUSE_APRES_UN_TOURNANT)
            resultat["tournant"] = (f"L'acte se termine : joue son tournant. L'acte {t['acte']} sur "
                                    f"{nombre_d_actes(t)} commence. {role_de_l_acte(t)}")
            revelations = _ouvrir_les_couches(t)  # la dernière couche attendait le dernier acte
            if revelations:
                resultat["revelation"] = revelations
        else:
            t["prochaine"] = jour
    elif mission.get("touche_la_trame") and reussie:
        accorder_un_indice(t)
    if t["dus"]:
        resultat["indice_a_decrire"] = ("Le joueur a gagné un indice sur le secret : décris-le avec l'outil indice, "
                                        "d'après ce qu'il doit encore découvrir.")
    return resultat


# --- Ce que le MJ et le joueur en lisent ----------------------------------------------------------------

def role_de_l_acte(t: dict) -> str:
    if nombre_d_actes(t) == 1 or dernier_acte(t):
        return ROLES_DES_ACTES[2]
    return ROLES_DES_ACTES[0] if t["acte"] == 1 else ROLES_DES_ACTES[1]


def bloc(etat: dict | None) -> str:
    """Ce que le MJ sait de la trame à cet instant : l'antagoniste, l'acte, ce que le personnage a compris, et
    la seule couche du secret qu'il peut semer. Jamais la suite. Vide sans trame."""
    t = trame_de(etat)
    if t is None:
        return ""
    lignes = ["### La trame (pour toi seul)", "",
              f"- L'antagoniste : {t['antagoniste']} ; derrière, {t['visage']}. Il veut {t['but']}."]
    if finie(t):
        lignes.append("- La trame est terminée.")
        return "\n".join(lignes) + "\n"
    lignes.append(f"- Acte {t['acte']} sur {nombre_d_actes(t)}. {role_de_l_acte(t)}")
    for i in range(t["couches"]):
        if len(t["secret"]) > i:
            lignes.append(f"- Le personnage a compris — {NOMS_DES_COUCHES[i].lower()} : {t['secret'][i]}")
    if t["couches"] < COUCHES and len(t["secret"]) > t["couches"]:
        lignes.append(f"- Ce qu'il doit encore découvrir, que tu sèmes sans jamais le dire : {t['secret'][t['couches']]}")
    lignes.append("- Tu ne relances jamais la trame de toi-même : la mission principale attend que le joueur y aille. "
                  "Deviner n'est pas prouver : tant qu'il n'a pas compris, les PNJ nient.")
    if t["dus"]:
        lignes.append("- Un indice est dû au joueur : décris-le avec l'outil indice.")
    return "\n".join(lignes) + "\n"


def pistes(etat: dict | None) -> list[str]:
    """Pour le joueur : ce que son personnage a compris, et ses indices dans l'ordre. Jamais ce qui manque."""
    t = trame_de(etat)
    if t is None:
        return ["Pas de trame dans cette campagne (elle date d'avant)."]
    lignes = []
    compris = [(NOMS_DES_COUCHES[i], t["secret"][i]) for i in range(t["couches"]) if len(t["secret"]) > i]
    if compris:
        lignes.append("Ce que tu as compris :")
        lignes += [f"  {nom} — {texte}" for nom, texte in compris]
    if t["indices"]:
        lignes.append("Tes indices :")
        lignes += [f"  Jour {i['jour']} — {i['texte']}" for i in t["indices"]]
    return lignes or ["Aucune piste pour l'instant."]


# --- La fin (REGLES.md 14.11) ---------------------------------------------------------------------------

TRIOMPHE, VICTOIRE_AMERE, DEFAITE_HONORABLE, CHUTE, MORT = ("triomphe", "victoire amère", "défaite honorable",
                                                           "chute", "mort")
REUSSI, RATE = "contrat réussi", "contrat raté"
ATOUTS_MAX = 3
FAIBLESSE, RENFORTS, ENTREE_SURE = "une faiblesse de l'antagoniste", "des renforts", "une entrée sûre"
PERTE_DE_L_ANTAGONISTE, GAIN_DE_L_ANTAGONISTE = 3, 2  # points de contrôle, dans tous ses quartiers
PAUSE_ENTRE_DEUX_ARCS = (20, 10)  # 1d20 + 10 jours
ARRET, SUITE = "arrêtée", "continuée"
# Ce que valent les hommes de l'antagoniste dans la finale, selon l'expérience de départ du personnage
MENACES = (("faible", 40), ("moyenne", 55), ("forte", 70), ("élite", 80))
MENACE_FINALE = {DEBUTANT: 1, AGUERRI: 2, VETERAN: 3}
CRAN_SUIVANT = {DEBUTANT: AGUERRI, AGUERRI: VETERAN, VETERAN: VETERAN}


def atouts(etat: dict, lieu: str) -> list[dict]:
    """Ce que le joueur a accumulé et qui sert dans la mission finale, trois atouts au plus : un indice en
    trop (le bras armé de l'antagoniste perd un cran de menace), une faction amie ou dont il est membre (un
    allié se bat à ses côtés), le quartier de la finale tenu par une faction amie (une entrée sûre)."""
    t = etat["trame"]
    trouves = []
    if indices_en_trop(t):
        trouves.append({"atout": FAIBLESSE, "effet": "Ses hommes valent un cran de menace de moins."})
    amies = sorted(f for f in etat["factions"]
                   if f != t["antagoniste"] and monde.reputation(etat, f) in (monde.AMI, monde.MEMBRE))
    if amies:
        trouves.append({"atout": RENFORTS, "faction": amies[0],
                        "effet": f"Un allié {monde.de(amies[0])} se bat à ses côtés : il est déjà créé."})
    maitre = etat["quartiers"][lieu]["maitre"] if lieu in etat["quartiers"] else None
    if maitre and maitre != t["antagoniste"] and monde.reputation(etat, maitre) in (monde.AMI, monde.MEMBRE):
        trouves.append({"atout": ENTREE_SURE, "effet": "Pas de barrage sur son chemin ; au premier combat de la "
                                                       "finale, les ennemis sont surpris (debut_combat, surpris)."})
    return trouves[:ATOUTS_MAX]


def menace_finale(t: dict, affaiblie: bool = False) -> tuple[str, int]:
    """La menace des hommes de l'antagoniste dans la finale : son nom, et leur pourcentage de combat."""
    rang = MENACE_FINALE.get(t["cran"], 1) - (1 if affaiblie else 0)
    return MENACES[max(0, rang)]


def nom_de_la_fin(t: dict) -> str:
    """La fin que le code donne à la campagne : la finale, et la part de missions principales réussies."""
    fin = t["fin"]
    if fin.get("mort"):
        return MORT
    if nombre_d_actes(t) == 1:
        return REUSSI if fin["finale_reussie"] else RATE
    part = t["reussies"] / TYPES[t["type"]].principales
    if fin["finale_reussie"]:
        return TRIOMPHE if part >= 0.75 else VICTOIRE_AMERE
    return DEFAITE_HONORABLE if part >= 0.5 else CHUTE


def _fin_sur_la_carte(etat: dict, des: Des, jour: int) -> list[str]:
    """Ce que la fin change sur la carte : battu, l'antagoniste perd 3 points dans tous ses quartiers (ceux qui
    tombent à 0 passent à un voisin hostile) ; vainqueur, il en gagne 2, et le joueur devient recherché chez lui."""
    t = etat["trame"]
    antagoniste, changements = t["antagoniste"], []
    siens = sorted(q for q, f in etat["quartiers"].items() if f["maitre"] == antagoniste)
    if t["fin"]["finale_reussie"]:
        for nom in siens:
            q = etat["quartiers"][nom]
            q["controle"] -= PERTE_DE_L_ANTAGONISTE
            if q["controle"] <= 0:
                voisins = monde.attaquants(etat, nom)
                if voisins:
                    q["maitre"], q["controle"] = monde._choisir(des, voisins), monde.CONTROLE_PRISE
                    q["attaque"], q["attaquant"] = None, None
                    q.pop("annoncee", None)
                    changements.append(f"{nom} passe {monde.a(q['maitre'])}")
                else:
                    q["controle"] = 1
        monde.planifier(etat, des, jour)
        monde.noter(etat, jour, monde.VILLE, etat["quartiers"][etat["ici"]]["district"],
                    f"Coup dur pour {antagoniste} : ses positions cèdent dans toute la ville.", [antagoniste], "fin")
    else:
        for nom in siens:
            q = etat["quartiers"][nom]
            q["controle"] = min(monde.CONTROLE_MAX, q["controle"] + GAIN_DE_L_ANTAGONISTE)
        etat["reputation"][antagoniste] = monde.RECHERCHE
        changements.append(f"{antagoniste} : il y est maintenant recherché")
        monde.noter(etat, jour, monde.VILLE, etat["quartiers"][etat["ici"]]["district"],
                    f"Victoire {monde.de(antagoniste)} : son emprise se resserre sur toute la ville.", [antagoniste],
                    "fin")
    return changements


def faits_de_fin(etat: dict) -> dict:
    """Les faits que le code donne au MJ pour écrire l'épilogue : la fin, le secret entier cette fois, les
    cicatrices, la réputation, et qui domine quoi."""
    t = etat["trame"]
    fin = nom_de_la_fin(t)
    court = nombre_d_actes(t) == 1
    return {
        "fin": fin,
        "antagoniste": f"{t['antagoniste']} ; derrière, {t['visage']}, qui voulait {t['but']}",
        "missions_principales": f"{t['reussies']} réussies sur {t['reussies'] + t['ratees']}",
        "secret_entier": list(t["secret"]),
        "cicatrices": [c["nature"] for c in t["cicatrices"]],
        "reputation": {f: r for f, r in etat["reputation"].items() if r != monde.NEUTRE},
        "districts": {d: monde.domine(etat, d) or "guerre ouverte" for d in etat["districts"]},
        "consigne": ("Écris l'épilogue en quelques lignes : ce que ce contrat laisse au personnage." if court else
                     f"La campagne se termine : {fin}. Écris l'épilogue d'après ces faits, sans en changer aucun : ce "
                     "que deviennent son lien, ses contacts et son quartier, et le secret, entier cette fois, même "
                     "s'il n'avait pas tout trouvé. Puis rends la main au joueur."),
    }


def finir(etat: dict, des: Des, jour: int) -> dict:
    """La mission finale vient d'être jouée : le code fixe la fin, l'applique à la carte, et donne au MJ les
    faits de l'épilogue."""
    changements = _fin_sur_la_carte(etat, des, jour)
    faits = faits_de_fin(etat)
    etat["trame"]["fin"]["nom"] = faits["fin"]
    return faits | ({"carte": changements} if changements else {})


def mourir(etat: dict, jour: int) -> dict:
    """Le personnage est mort avant la fin de la trame : c'est la cinquième fin. Renvoie les faits de l'épilogue."""
    t = etat["trame"]
    t["fin"] = {"finale_reussie": False, "jour": jour, "mort": True, "nom": MORT}
    return faits_de_fin(etat)


def decider_la_suite(etat: dict, des: Des, jour: int, continuer: bool) -> str:
    """Après la fin : arrêter, ou continuer dans le même monde. Une nouvelle trame commence alors 1d20 + 10
    jours plus tard, avec un autre antagoniste, pris parmi les factions qui tiennent encore un quartier."""
    t = etat["trame"]
    if not continuer:
        t["apres"] = ARRET
        return ARRET
    debout = sorted({q["maitre"] for q in etat["quartiers"].values()} - {t["antagoniste"]})
    if not debout:  # il a tout pris : c'est encore lui
        debout = sorted({q["maitre"] for q in etat["quartiers"].values()})
    t["apres"] = SUITE
    etat.setdefault("trames_passees", []).append(t)
    nouvelle = creer(etat, des, t["type"], t["cran"], jour)
    nouvelle["antagoniste"] = monde._choisir(des, debout)
    faces, plus = PAUSE_ENTRE_DEUX_ARCS
    nouvelle["prochaine"] = jour + des.lancer(faces) + plus
    return SUITE


def suite_decidee(t: dict) -> bool:
    return "apres" in t


def arretee(etat: dict | None) -> bool:
    """La campagne a-t-elle été arrêtée après sa fin ?"""
    t = trame_de(etat)
    return bool(t) and t.get("apres") == ARRET
