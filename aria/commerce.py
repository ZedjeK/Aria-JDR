"""Acheter, vendre, payer (REGLES.md 13.3, 13.6, 13.7 et 13.10).

Le MJ ne manie jamais un nombre : il nomme un article, un service ou un palier, et le moteur vérifie,
calcule, débite, crédite ou refuse.
"""

import random
from dataclasses import dataclass

from aria import economie, inventaire as inv
from aria.des import Des
from aria.economie import COURANT, MILITAIRE, RESTREINT, decaler
from aria.inventaire import Inventaire
from aria.personnage import Personnage
from aria.resolution import Degre, Difficulte, Resultat, tester

BOITE, CHARGEUR = "Boîte de cartouches", "Chargeur"
NEUF, OCCASION, MARQUE, MARCHE_NOIR = "neuf", "occasion", "marque", "marché noir"
REVENTE = -2  # chez un receleur : deux paliers sous la valeur
PRIX_BOITE = {"armes de poing": 20, "armes intelligentes": 20, "fusils": 50, "fusils de précision": 100,
              "armes lourdes": 200, "armes de trait": 20}
SERVICES = {"un trajet en taxi": 20, "un repas correct": 20, "une consultation ou un soin": 100,
            "une séance de thérapie": 200, "soigner une blessure grave": 500, "poser une modification": 100,
            "une soirée de détente": 200}
DETENTE = "une soirée de détente"
PALIERS_LIBRES = (50, 100, 200, 500, 1000, 2000)  # une information, un pot-de-vin : au choix du MJ
POSE_IMPLANT = {"standard": 500, "avancée": 2000, "militaire": 5000}
POSE_SANS_GAMME = 500
LIEUX = {"grande ville": Difficulte.NORMALE, "petite ville": Difficulte.DIFFICILE, "village ou nature": None}
ATTITUDES = {"amical": Difficulte.FACILE, "neutre": Difficulte.NORMALE, "hostile": Difficulte.DIFFICILE}
PERSUASION, INTIMIDATION = "Persuasion", "Intimidation"
OCCASIONS_PAR_BOUTIQUE, OBJETS_PAR_CONTACT = 3, 4


class CommerceImpossible(ValueError):
    """Une transaction refusée : le message est renvoyé tel quel au MJ."""


@dataclass(frozen=True)
class Article:
    nom: str
    famille: str  # arme, armure, implant, véhicule, portage, sac, outil, munitions, chargeur
    prix: int
    disponibilite: str = COURANT
    arme: str | None = None  # pour une boîte ou un chargeur : l'arme concernée


def prix_boite(arme) -> int:
    return PRIX_BOITE.get(arme.categorie, 50)


def article(univers, nom: str) -> Article:
    """Ce qui se vend sous ce nom dans l'univers. « Boîte de cartouches (Pistolet lourd) » et
    « Chargeur (Pistolet lourd) » sont formés sur le nom de l'arme."""
    for prefixe, famille in ((BOITE, "munitions"), (CHARGEUR, "chargeur")):
        if nom.startswith(prefixe + " (") and nom.endswith(")"):
            arme = _trouver(univers.armes, nom[len(prefixe) + 2:-1])
            if arme is None or not arme.munitions or arme.usage_unique or arme.montee:
                break
            return Article(nom, famille, prix_boite(arme) if famille == "munitions" else inv.PRIX_CHARGEUR,
                           economie.disponibilite(arme, univers) if arme.categorie == "armes lourdes" else COURANT,
                           arme.nom)
    for famille, objets in (("arme", univers.armes), ("armure", univers.armures), ("implant", univers.implants),
                            ("véhicule", univers.vehicules)):
        objet = _trouver(objets, nom)
        if objet is not None:
            return Article(nom, famille, economie.prix(objet, univers), economie.disponibilite(objet, univers))
    if nom in inv.PORTAGES:
        return Article(nom, "portage", inv.PORTAGES[nom].prix)
    if nom in inv.SACS:
        return Article(nom, "sac", inv.SACS[nom].prix)
    if nom in inv.OUTILS:
        return Article(nom, "outil", inv.OUTILS[nom])
    raise CommerceImpossible(f"« {nom} » ne se vend pas dans {univers.nom}.")


def _trouver(objets, nom: str):
    return next((o for o in objets if o.nom == nom), None)


def catalogue(univers, inventaire: Inventaire | None = None) -> list[str]:
    """Les noms de tout ce qui peut s'acheter : pour la liste fermée de l'outil. Les boîtes et les chargeurs
    ne sont proposés que pour les armes que le personnage possède."""
    noms = [o.nom for famille in (univers.armes, univers.armures, univers.vehicules) for o in famille
            if not getattr(o, "montee", False)]
    noms += [*inv.PORTAGES, *inv.SACS, *inv.OUTILS]
    for arme in (inventaire.armes() if inventaire else []):
        if arme.munitions and not arme.usage_unique:
            noms += [f"{BOITE} ({arme.nom})", f"{CHARGEUR} ({arme.nom})"]
    return noms


# --- Le marchandage (13.10) -----------------------------------------------------------------------------

@dataclass
class Marchandage:
    test: Resultat
    competence: str

    @property
    def degre(self) -> Degre:
        return self.test.degre

    @property
    def refus(self) -> bool:
        return self.degre is Degre.MALADRESSE

    @property
    def geste(self) -> bool:
        return self.degre >= Degre.COMPLICATION

    @property
    def critique(self) -> bool:
        return self.degre is Degre.CRITIQUE

    @property
    def attitude_baisse(self) -> bool:
        """Par la menace, le PNJ en veut au personnage, réussite ou non."""
        return self.competence == INTIMIDATION


def marchander(des: Des, valeur: int, attitude: str = "neutre", competence: str = PERSUASION) -> Marchandage:
    """Un test de Persuasion (ou d'Intimidation), une seule fois par transaction."""
    return Marchandage(tester(des, valeur, ATTITUDES[attitude]), competence)


# --- Acheter (13.3 et 13.7) -----------------------------------------------------------------------------

@dataclass
class Achat:
    article: Article
    etat: str
    prix: int
    argent: int
    geste: str = ""
    refuse: bool = False


def prix_de_vente(a: Article, etat: str = NEUF) -> int:
    """Usé : un palier en dessous. De marque ou au marché noir : un palier au-dessus."""
    return decaler(a.prix, {NEUF: 0, OCCASION: -1, MARQUE: 0, MARCHE_NOIR: 1}[etat])


def acheter(perso: Personnage, inventaire: Inventaire, univers, nom: str, etat: str = NEUF,
            marchandage: Marchandage | None = None) -> Achat:
    """Achète un article et le range dans l'inventaire. Le matériel restreint ne s'achète qu'au marché noir
    (dans le stock d'un contact, ou sur commande) ; le matériel militaire, jamais."""
    a = article(univers, nom)
    if a.famille in ("implant", "véhicule"):
        raise CommerceImpossible("Un implant s'achète avec sa pose (poser_implant) ; un véhicule ne s'achète pas "
                                 "encore par cet outil.")
    if a.disponibilite == MILITAIRE:
        raise CommerceImpossible(f"« {nom} » est du matériel militaire : il ne se vend nulle part. On le gagne "
                                 "(une récompense de mission) ou on le trouve.")
    if a.disponibilite == RESTREINT and etat != MARCHE_NOIR:
        raise CommerceImpossible(f"« {nom} » est du matériel restreint : il passe par un contact (voir_boutique "
                                 "au marché noir, ou commander).")
    if marchandage and marchandage.refus:
        return Achat(a, etat, 0, perso.argent, refuse=True)
    cout = prix_de_vente(a, etat)
    if marchandage and marchandage.critique:
        cout = decaler(cout, -1)
    if perso.argent < cout:
        raise CommerceImpossible(f"Pas assez d'argent pour « {nom} » : {economie.montant(cout, univers.monnaie)}, "
                                 f"et il n'a que {economie.montant(perso.argent, univers.monnaie)}.")
    geste = _livrer(inventaire, univers, a, etat)
    if marchandage and marchandage.geste and a.famille == "arme" and univers.arme(nom).munitions \
            and not univers.arme(nom).usage_unique:
        inventaire.ajouter_cartouches(univers.arme(nom), inv.BOITE)
        geste = "une boîte de cartouches offerte"
    elif marchandage and marchandage.geste:
        geste = "un geste du vendeur, à raconter (un conseil, un rabais sur la prochaine visite)"
    perso.argent -= cout
    return Achat(a, etat, cout, perso.argent, geste)


def _livrer(inventaire: Inventaire, univers, a: Article, etat: str) -> str:
    """Range l'article dans l'inventaire. Une arme est vendue chargée, avec son chargeur."""
    qualite = {"qualite": "usé"} if etat == OCCASION else {}
    if a.famille == "arme":
        arme = univers.arme(a.nom)
        inventaire.ajouter(a.nom, inv.ARME, charge=arme.chargeur.capacite if arme.munitions else 0, **qualite)
    elif a.famille == "armure":
        inventaire.ajouter(a.nom, inv.ARMURE, **qualite)
    elif a.famille in ("portage", "sac", "outil"):
        inventaire.ajouter(a.nom, {"portage": inv.PORTAGE, "sac": inv.SAC, "outil": inv.OUTIL}[a.famille])
    elif a.famille == "munitions":
        inventaire.ajouter_cartouches(univers.arme(a.arme), inv.BOITE)
    elif a.famille == "chargeur":
        inventaire.ajouter_chargeur(univers.arme(a.arme), cartouches=0)
    return ""


# --- Vendre (13.6) --------------------------------------------------------------------------------------

@dataclass
class Vente:
    nom: str
    prix: int
    argent: int
    refuse: bool = False


def prix_de_revente(univers, objet: dict, marchandage: Marchandage | None = None) -> int:
    a = article(univers, objet["nom"])
    valeur = decaler(a.prix, -1) if objet.get("qualite") == "usé" else a.prix
    crans = REVENTE + (1 if marchandage and marchandage.geste else 0)
    return decaler(valeur, crans)


def vendre(perso: Personnage, inventaire: Inventaire, univers, nom: str, par_un_contact: bool = False,
           marchandage: Marchandage | None = None) -> Vente:
    """Vend un objet de l'inventaire à un receleur, deux paliers sous sa valeur. Le matériel militaire, ou
    marqué, ne se vend que par un contact."""
    objet = inventaire.trouver(nom)
    if objet.get("valeur"):  # un objet de valeur trouvé en butin : il se revend à sa valeur
        if marchandage and marchandage.refus:
            return Vente(nom, 0, perso.argent, refuse=True)
        inventaire.retirer(nom)
        perso.argent += objet["valeur"]
        return Vente(nom, objet["valeur"], perso.argent)
    if objet["famille"] == inv.OBJET:
        raise CommerceImpossible(f"« {nom} » n'a pas de valeur marchande.")
    if objet.get("portee"):
        raise CommerceImpossible(f"« {nom} » est sur son dos : il faut d'abord l'enlever.")
    a = article(univers, nom)
    if (a.disponibilite == MILITAIRE or objet.get("marque")) and not par_un_contact:
        raise CommerceImpossible(f"« {nom} » ne se vend pas au premier venu : il faut un contact.")
    if marchandage and marchandage.refus:
        return Vente(nom, 0, perso.argent, refuse=True)
    gain = prix_de_revente(univers, objet, marchandage)
    inventaire.retirer(nom)
    perso.argent += gain
    return Vente(nom, gain, perso.argent)


# --- Payer un service (13.7) ----------------------------------------------------------------------------

def payer(perso: Personnage, somme: int, monnaie: str = "") -> int:
    """Débite une somme, qui doit être un palier. Renvoie ce qu'il reste."""
    if somme not in economie.PALIERS:
        raise CommerceImpossible(f"{somme} n'est pas un palier de prix.")
    if perso.argent < somme:
        raise CommerceImpossible(f"Pas assez d'argent : {economie.montant(somme, monnaie)} demandés, "
                                 f"{economie.montant(perso.argent, monnaie)} en poche.")
    perso.argent -= somme
    return perso.argent


def se_detendre(des: Des, perso: Personnage, jour: int) -> int:
    """Une soirée, un plaisir, une offrande : 200 pour 1d6 de Santé mentale, une fois par semaine."""
    if perso.derniere_detente and jour - perso.derniere_detente < economie.SEMAINE:
        raise CommerceImpossible(f"{perso.nom} s'est déjà détendu cette semaine (jour {perso.derniere_detente}).")
    payer(perso, SERVICES[DETENTE])
    perso.derniere_detente = jour
    avant = perso.sm
    perso.sm = min(perso.sm_max, perso.sm + des.jet("1d6"))
    return perso.sm - avant


def prix_de_pose(implant, clandestine: bool = False) -> int:
    """La pose d'un implant, en plus de son prix. Une clinique clandestine : un palier de moins."""
    pose = POSE_SANS_GAMME if implant.gamme is None or implant.cout == 0 else POSE_IMPLANT[implant.gamme]
    return decaler(pose, -1) if clandestine else pose


# --- Commander un objet restreint (13.3) ----------------------------------------------------------------

@dataclass
class Commande:
    test: Resultat
    passee: bool
    prix: int = 0
    jour: int = 0  # le jour où l'objet arrive


def commander(des: Des, perso: Personnage, univers, nom: str, valeur: int, lieu: str, jour: int) -> Commande:
    """Passe par un contact pour un objet restreint : un test, un délai de 1 à 3 jours, un palier au-dessus.
    La somme est payée à la commande ; l'objet arrive tout seul le jour dit."""
    a = article(univers, nom)
    if a.disponibilite == MILITAIRE:
        raise CommerceImpossible(f"« {nom} » est du matériel militaire : aucun contact ne peut le fournir.")
    if a.disponibilite != RESTREINT:
        raise CommerceImpossible(f"« {nom} » est en vente libre : il s'achète en boutique.")
    if LIEUX[lieu] is None:
        raise CommerceImpossible("Ici, personne ne peut fournir du matériel restreint : il faut une ville.")
    cout = prix_de_vente(a, MARCHE_NOIR)
    if perso.argent < cout:
        raise CommerceImpossible(f"Pas assez d'argent pour commander « {nom} » : "
                                 f"{economie.montant(cout, univers.monnaie)}.")
    test = tester(des, valeur, LIEUX[lieu])
    if test.degre < Degre.COMPLICATION:
        return Commande(test, False)
    arrivee = jour + des.jet("1d3")
    perso.argent -= cout
    perso.commandes.append({"objet": nom, "prix": cout, "jour": arrivee})
    return Commande(test, True, cout, arrivee)


def livrer_les_commandes(perso: Personnage, inventaire: Inventaire, univers, jour: int) -> list[str]:
    """Les commandes arrivées : elles entrent dans l'inventaire (au risque de la surcharge)."""
    arrivees = [c for c in perso.commandes if c["jour"] <= jour]
    for commande in arrivees:
        _livrer(inventaire, univers, article(univers, commande["objet"]), MARCHE_NOIR)
        perso.commandes.remove(commande)
    return [c["objet"] for c in arrivees]


# --- Le stock d'une boutique (13.7) ---------------------------------------------------------------------

def stock(univers, vendeur: str, jour: int, marche_noir: bool = False) -> list[dict]:
    """Ce qu'un vendeur a cette semaine, en plus du matériel courant : 3 occasions (usées ou de marque) pour
    une boutique, 4 objets restreints pour un contact du marché noir. Le tirage ne dépend que de l'univers,
    du vendeur et de la semaine : il se renouvelle tous les 7 jours, et reste le même d'ici là."""
    hasard = random.Random(f"{univers.nom}|{vendeur}|{(jour - 1) // economie.SEMAINE}|{marche_noir}")
    vendables = [o for o in [*univers.armes, *univers.armures] if not getattr(o, "montee", False)]
    if marche_noir:
        restreints = [o for o in vendables if economie.disponibilite(o, univers) == RESTREINT]
        choisis = hasard.sample(restreints, min(OBJETS_PAR_CONTACT, len(restreints)))
        return [{"objet": o.nom, "etat": MARCHE_NOIR, "prix": prix_de_vente(article(univers, o.nom), MARCHE_NOIR)}
                for o in choisis]
    courants = [o for o in vendables if economie.disponibilite(o, univers) == COURANT]
    choisis = hasard.sample(courants, min(OCCASIONS_PAR_BOUTIQUE, len(courants)))
    lignes = []
    for o in choisis:
        etat = MARQUE if getattr(o, "fabricant", None) else OCCASION
        lignes.append({"objet": o.nom, "etat": etat, "prix": prix_de_vente(article(univers, o.nom), etat)})
    return lignes
