"""Gagner de l'argent (REGLES.md 13.6 et 13.8) : les missions, le métier, les dettes, le butin et les caches.

Comme pour le reste de l'économie, le MJ choisit dans des listes fermées (le danger d'une mission, la taille
d'une cache) et le moteur tire, compte et verse.
"""

from dataclasses import dataclass, field

from aria import economie, inventaire as inv
from aria.commerce import Marchandage, article
from aria.des import Des
from aria.economie import MILITAIRE, PALIERS, decaler
from aria.equipement import Arme, Armure
from aria.personnage import Personnage
from aria.resolution import Degre, Resultat, tester

# --- Les missions ---------------------------------------------------------------------------------------

RECOMPENSES = {"un service": 200, "simple": 500, "risquée": 2000, "dangereuse": 5000, "très dangereuse": 10000,
               "exceptionnelle": 20000}


class GainImpossible(ValueError):
    """Ce que les règles des gains ne permettent pas : le message est renvoyé tel quel au MJ."""


@dataclass
class Mission:
    recompense: int
    avance: int = 0
    retiree: bool = False  # une maladresse au marchandage : le commanditaire retire son offre


def ouvrir_mission(perso: Personnage, identifiant: str, danger: str,
                   marchandage: Marchandage | None = None, paliers: int = 0) -> Mission:
    """Fixe la récompense d'une mission à son ouverture. Marchandée : un critique la monte d'un palier, une
    réussite obtient une avance (deux paliers sous la récompense, versée tout de suite et déduite à la fin),
    une maladresse la baisse d'un palier. `paliers` : ce que le commanditaire paie au-dessus du barème."""
    recompense = decaler(RECOMPENSES[danger], paliers)
    avance = 0
    if marchandage:
        if marchandage.critique:
            recompense = decaler(recompense, 1)
        elif marchandage.refus:
            recompense = decaler(recompense, -1)
        elif marchandage.geste:
            avance = decaler(recompense, -2)
    perso.missions[identifiant] = {"recompense": recompense, "avance": avance}
    perso.argent += avance
    return Mission(recompense, avance)


def clore_mission(perso: Personnage, identifiant: str, reussie: bool) -> int:
    """Verse ce qui reste de la récompense si la mission est réussie. Une avance déjà touchée reste acquise."""
    mission = perso.missions.pop(identifiant)
    reste = mission["recompense"] - mission["avance"] if reussie else 0
    perso.argent += reste
    return reste


# --- Exercer son métier ---------------------------------------------------------------------------------

@dataclass
class SemaineDeTravail:
    test: Resultat
    competence: str
    revenu: int
    ennui: bool  # une maladresse : une dette, un client mécontent, que le MJ raconte


def travailler(des: Des, perso: Personnage, competence: str, rang: str) -> SemaineDeTravail:
    """Une semaine entière sans aventure : un test de la compétence principale du métier."""
    test = tester(des, perso.valeur(competence))
    base = economie.RANGS.get(rang, economie.RANGS[economie.RANG_PAR_DEFAUT]).revenu
    facteur = {Degre.CRITIQUE: 2, Degre.MAJEURE: 1.5, Degre.REUSSITE: 1, Degre.COMPLICATION: 1}.get(test.degre, 0)
    revenu = int(base * facteur)
    perso.argent += revenu
    return SemaineDeTravail(test, competence, revenu, test.degre is Degre.MALADRESSE)


# --- Les dettes -----------------------------------------------------------------------------------------

EMPRUNT_MAX = 5000
SEMAINES_DE_REMBOURSEMENT = 12
SOMMES_EMPRUNTABLES = tuple(p for p in PALIERS if 100 <= p <= EMPRUNT_MAX)


def emprunter(perso: Personnage, creancier: str, somme: int) -> dict:
    """Jusqu'à 5 000 : on rembourse un dixième de la somme par semaine pendant 12 semaines (20 % d'intérêt)."""
    if somme not in SOMMES_EMPRUNTABLES:
        raise GainImpossible(f"On emprunte un palier, de 100 à {EMPRUNT_MAX} : {list(SOMMES_EMPRUNTABLES)}.")
    if sum(d["reste"] for d in perso.dettes) + somme > EMPRUNT_MAX * 1.2:
        raise GainImpossible(f"{perso.nom} doit déjà trop : personne ne lui prêtera davantage.")
    dette = {"creancier": creancier, "echeance": somme // 10, "reste": somme // 10 * SEMAINES_DE_REMBOURSEMENT,
             "manquees": 0}
    perso.dettes.append(dette)
    perso.argent += somme
    return dette


# --- Le butin (13.8) ------------------------------------------------------------------------------------

MENACES = (("faible", 40, 10, 1), ("moyenne", 60, 20, 2), ("forte", 75, 50, 3), ("élite", 100, 100, 4))
CHANCE_USEE = 6  # sur 10 : l'arme d'un adversaire vaincu est usée
CACHES = {"petite": (50, 500), "moyenne": (500, 2000), "grosse": (2000, 10000), "un trésor": (10000, 50000)}
OBJET_DE_VALEUR = "un objet de valeur, à revendre"


def menace(combat: int) -> tuple[str, int, int]:
    """Le niveau de menace d'un PNJ, d'après son pourcentage de combat : (nom, argent par point de d6, chances
    sur 6 d'un objet en plus)."""
    for nom, plafond, argent, chances in MENACES:
        if combat <= plafond:
            return nom, argent, chances
    return MENACES[-1][0], MENACES[-1][2], MENACES[-1][3]


def table_du_genre(univers) -> list[str]:
    """Ce qu'on peut trouver en plus sur un adversaire : des grenades de l'univers, une boîte de cartouches,
    un garnisseur, un objet de valeur."""
    grenades = [a.nom for a in univers.armes if a.categorie == "grenades"]
    return [*grenades[:3], inv.GARNISSEUR, OBJET_DE_VALEUR, OBJET_DE_VALEUR]


@dataclass
class Butin:
    """Ce qu'une fouille a trouvé. L'argent est déjà dans la poche ; les objets attendent d'être pris."""

    argent: int = 0
    objets: list[dict] = field(default_factory=list)  # nom, famille, et selon le cas qualite, charge, chargeurs, marque
    menace: str = ""


def fouiller_un_corps(des: Des, univers, combat: int, arme: Arme | None, armure: Armure | None,
                      dans_l_arme: int = 0, chargeurs: int | None = None, marque: bool = False) -> Butin:
    """Ce qu'un adversaire vaincu avait vraiment : son arme (usée 6 fois sur 10) avec ce qu'il restait dans son
    chargeur et ses chargeurs de rechange (ceux qu'il lui restait, ou de 0 à 2), son armure (toujours usée),
    de l'argent selon sa menace, et parfois un objet en plus."""
    nom_menace, par_point, chances = menace(combat)
    butin = Butin(argent=des.jet("1d6") * par_point, menace=nom_menace)
    extra = {"marque": True} if marque else {}
    if arme and not arme.montee and arme.nom != "Mains nues":
        objet = {"nom": arme.nom, "famille": inv.ARME, **extra}
        if des.lancer(10) <= CHANCE_USEE:
            objet["qualite"] = "usé"
        if arme.munitions and not arme.usage_unique:
            objet["charge"] = dans_l_arme
            objet["chargeurs"] = chargeurs if chargeurs is not None else des.lancer(3) - 1
        butin.objets.append(objet)
    if armure:
        butin.objets.append({"nom": armure.nom, "famille": inv.ARMURE, "qualite": "usé", **extra})
    if des.lancer(6) <= chances:
        table = table_du_genre(univers)
        trouve = table[des.lancer(len(table)) - 1]
        if trouve == OBJET_DE_VALEUR:
            butin.objets.append({"nom": trouve, "famille": inv.OBJET, "valeur": 100})
        elif trouve == inv.GARNISSEUR:
            butin.objets.append({"nom": trouve, "famille": inv.OUTIL})
        else:
            butin.objets.append({"nom": trouve, "famille": inv.ARME})
    return butin


def fouiller_une_cache(des: Des, univers, taille: str) -> Butin:
    """La valeur est tirée deux fois dans la fourchette de la taille, et on garde le plus petit résultat. Le
    contenu : à peu près la moitié en argent, le reste en objets de l'univers. Une cache n'est jamais vide."""
    mini, maxi = CACHES[taille]
    echelle = [p for p in PALIERS if mini <= p <= maxi]
    valeur = min(echelle[des.lancer(len(echelle)) - 1], echelle[des.lancer(len(echelle)) - 1])
    reste = valeur // 2
    butin = Butin(argent=valeur - reste)
    vendables = sorted((a for a in [*univers.armes, *univers.armures]
                        if not getattr(a, "montee", False)
                        and economie.disponibilite(a, univers) != MILITAIRE), key=lambda o: o.nom)
    while reste >= 20:
        possibles = [o for o in vendables if economie.prix(o, univers) <= reste]
        if not possibles:
            break
        choisi = possibles[des.lancer(len(possibles)) - 1]
        reste -= economie.prix(choisi, univers)
        objet = {"nom": choisi.nom, "famille": inv.ARME if isinstance(choisi, Arme) else inv.ARMURE}
        if isinstance(choisi, Arme) and choisi.munitions and not choisi.usage_unique:
            objet |= {"charge": choisi.chargeur.capacite, "chargeurs": 0}
        butin.objets.append(objet)
    butin.argent += reste  # ce qui n'a pas trouvé d'objet à sa mesure reste en argent
    return butin


def prendre(inventaire: inv.Inventaire, univers, objet: dict) -> dict:
    """Range dans l'inventaire un objet trouvé. Un objet de valeur se revendra à son prix."""
    details = {cle: objet[cle] for cle in ("qualite", "marque") if cle in objet}
    if objet["famille"] == inv.ARME:
        arme = univers.arme(objet["nom"])
        entree = inventaire.ajouter(objet["nom"], inv.ARME, charge=objet.get("charge", 0), **details)
        for _ in range(objet.get("chargeurs", 0)):
            inventaire.ajouter_chargeur(arme)
        return entree
    if objet["famille"] == inv.OBJET:
        return inventaire.ajouter(objet["nom"], inv.OBJET, petit=True, valeur=objet.get("valeur", 0))
    return inventaire.ajouter(objet["nom"], objet["famille"], **details)


def valeur_de_revente(univers, objet: dict) -> int | None:
    """Pour un objet de valeur trouvé en butin : ce qu'en donne un receleur. None pour tout autre objet."""
    if objet.get("valeur"):
        return objet["valeur"]
    try:
        article(univers, objet["nom"])
    except ValueError:
        return 0
    return None
