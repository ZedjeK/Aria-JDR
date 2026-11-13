"""Les outils du MJ : le moteur exposé au LLM sous forme d'appels de fonctions.

Le LLM ne lance jamais un dé lui-même : il appelle un outil, le moteur applique les
règles et renvoie le résultat, que le LLM raconte. Chaque outil a un schéma JSON au
format « function calling » compatible OpenAI (celui que comprend llama.cpp). Les listes
fermées (difficultés, chocs, défenses…) y sont des énumérations : le LLM ne peut pas
inventer une valeur, et le moteur vérifie de toute façon chaque argument.

Une erreur ne fait jamais planter la partie : elle est renvoyée au LLM sous la forme
{"erreur": "…"} pour qu'il corrige son appel.
"""

import json
from dataclasses import dataclass, field
from typing import Callable

from aria import commerce, economie, gains, implants as implants_, magie, poursuite as poursuite_, progression, sante_mentale, soins
from aria import combat as combat_, lieux as lieux_, meteo as meteo_, missions, monde as monde_, noms as noms_, pnj as pnj_
from aria import rencontres as rencontres_, trame as trame_, vehicules as vehicules_
from aria.campagne import Campagne
from aria.compte_rendu import decrire
from aria.combat import (
    ActionImpossible,
    BonusMajeure,
    BudgetRound,
    Combat,
    Combattant,
    Couvert,
    Defense,
    FichePnj,
    NATURE_IEM,
    RapportAttaque,
    RapportZone,
    TIREURS,
    TypeAction,
    blesser,
    combattant_drone,
    laisser_pour_mort,
    tester_embuscade,
)
from aria.des import Des
from aria import inventaire as inventaire_
from aria.inventaire import Inventaire, ReservePnj
from aria.memoire import LONGUEURS, MORT, VIVANT, Memoire
from aria.personnage import Caracteristique, Etat, Personnage
from aria.reglages import Jalon
from aria.resolution import Degre, Difficulte, Resultat, forcer, tester
from aria.temps import Moment, Periode
from aria.univers import Univers

JOUEUR = "joueur"
DIFFICULTES = {"facile": Difficulte.FACILE, "normale": Difficulte.NORMALE,
               "difficile": Difficulte.DIFFICILE, "extrême": Difficulte.EXTREME}
DEFENSES = {"esquive": Defense.ESQUIVE, "riposte": Defense.RIPOSTE, "aucune": None}
COUVERTS = {"aucun": Couvert.AUCUN, "partiel": Couvert.PARTIEL, "lourd": Couvert.LOURD}
BONUS_MAJEURE = {"dé de dégâts": BonusMajeure.DE_SUPPLEMENTAIRE, "désarmer": BonusMajeure.DESARMER,
                 "repousser": BonusMajeure.REPOUSSER}
JALONS = {"objectif": Jalon.OBJECTIF, "arc": Jalon.ARC, "motivation": Jalon.MOTIVATION, "session": Jalon.SESSION}
REPOS = {"court": soins.Repos.COURT, "moyen": soins.Repos.MOYEN, "long": soins.Repos.LONG}
# Bornes d'un PNJ créé par le MJ : il choisit sa force, dans des limites raisonnables
PNJ_COMBAT = (5, 85)
PNJ_PV = (1, 40)
PNJ_COMPETENCE = (0, 90)
PNJ_PM = (0, 30)
RAPPEL_REUSSITE = "Test réussi : raconte-le. Il ne se relance pas pour faire mieux, même si le joueur le demande."
MOMENTS_FORTS_MAX = 600  # caractères : trois phrases, pas un roman


class ErreurOutil(Exception):
    """Un appel d'outil invalide. Le message est renvoyé tel quel au LLM."""


# --- Vérification des arguments (un petit sous-ensemble de JSON Schema) ---------------------

def _verifier(valeur, schema: dict, chemin: str):
    attendu = schema.get("type")
    types = {"string": str, "integer": int, "boolean": bool, "array": list, "object": dict}
    if attendu and (not isinstance(valeur, types[attendu]) or (attendu == "integer" and isinstance(valeur, bool))):
        raise ErreurOutil(f"« {chemin} » doit être de type {attendu}.")
    if "enum" in schema and valeur not in schema["enum"]:
        raise ErreurOutil(f"« {chemin} » vaut {valeur!r}, mais doit être l'une de ces valeurs : {schema['enum']}.")
    if "minimum" in schema and valeur < schema["minimum"]:
        raise ErreurOutil(f"« {chemin} » doit valoir au moins {schema['minimum']}.")
    if "maximum" in schema and valeur > schema["maximum"]:
        raise ErreurOutil(f"« {chemin} » doit valoir au plus {schema['maximum']}.")
    if attendu == "array":
        for i, element in enumerate(valeur):
            _verifier(element, schema.get("items", {}), f"{chemin}[{i}]")
    if attendu == "object":
        _verifier_objet(valeur, schema, chemin)


def _verifier_objet(arguments: dict, schema: dict, chemin: str = "arguments"):
    proprietes = schema.get("properties", {})
    for cle in arguments:
        if cle not in proprietes and schema.get("additionalProperties") is not True:
            raise ErreurOutil(f"Paramètre inconnu : « {cle} ». Paramètres possibles : {sorted(proprietes)}.")
    for cle in schema.get("required", []):
        if cle not in arguments:
            raise ErreurOutil(f"Paramètre obligatoire manquant : « {cle} ».")
    for cle, valeur in arguments.items():
        if cle in proprietes:
            _verifier(valeur, proprietes[cle], cle)


@dataclass
class Outil:
    nom: str
    description: str
    parametres: Callable[["Session"], dict]  # le schéma dépend de la session (PNJ présents, univers…)
    fonction: Callable[..., dict]
    disponible: Callable[["Session"], bool] = lambda s: True  # sans magie dans l'univers, pas de lancer_sort


def _resume(resultat: Resultat) -> dict:
    return {"jet": resultat.jet, "valeur": resultat.valeur, "degre": resultat.degre.libelle, "reussi": resultat.reussi}


def _test(resultat: Resultat) -> dict:
    """Le résumé d'un test du joueur, avec le rappel au moment où le MJ en a besoin."""
    return _resume(resultat) | ({"consigne": RAPPEL_REUSSITE} if resultat.reussi else {})


# --- La session de jeu ------------------------------------------------------------------------

@dataclass
class Session:
    """Tout ce que le MJ manipule pendant une partie : l'univers, le perso, les PNJ, le combat, le temps."""

    univers: Univers
    personnage: Personnage
    des: Des = field(default_factory=Des)
    moment: Moment = Moment(1, Periode.MATIN)
    arme: str | None = None
    armure: str | None = None
    vehicule: "vehicules_.Engin | str | dict | None" = None  # un nom de l'univers, ou sa sauvegarde
    pnj: dict[str, Combattant] = field(default_factory=dict)
    engins: dict[str, vehicules_.Engin] = field(default_factory=dict)  # les véhicules des PNJ
    poursuite: poursuite_.Poursuite | None = None
    combat: Combat | None = None
    dernier_test: dict | None = None
    journal: list[dict] = field(default_factory=list)
    campagne: Campagne | None = None  # None : rien n'est écrit sur le disque (le banc d'essai)
    rounds: list[tuple[int, list[str]]] = field(default_factory=list)  # le combat en cours, round par round
    trouvailles: dict[str, list[dict]] = field(default_factory=dict)  # ce que les fouilles ont trouvé, pas encore pris
    fouilles: set[str] = field(default_factory=set)  # les PNJ déjà fouillés
    debut_round: int = 0  # l'indice, dans le journal, du premier appel du round en cours
    monde: dict | None = None  # la carte et les factions (voir aria.monde) ; None : une campagne d'avant
    melee: dict | None = None  # la mêlée où le joueur se bat en ce moment : quartier, camp, adversaires

    def __post_init__(self):
        u = self.univers
        self.joueur = Combattant(self.personnage, "joueur", None, u.armure(self.armure) if self.armure else None)
        # Avec un inventaire, les munitions sont comptées, et seules les armes possédées se dégainent
        self.inventaire = Inventaire(self.personnage, u) if self.personnage.inventaire is not None else None
        if self.inventaire:
            self.joueur.reserve = self.inventaire
            # Ce que la session met en main ou sur le dos entre dans l'inventaire, s'il n'y est pas déjà
            if self.arme and not self.inventaire.a(self.arme, inventaire_.ARME):
                fiche = u.arme(self.arme)
                self.inventaire.ajouter(self.arme, inventaire_.ARME, charge=fiche.chargeur.capacite if fiche.munitions else 0)
                if fiche.munitions and not fiche.usage_unique:
                    self.inventaire.ajouter_chargeur(fiche)
            if self.armure and not self.inventaire.a(self.armure, inventaire_.ARMURE):
                self.inventaire.ajouter(self.armure, inventaire_.ARMURE, portee=True)
            self.charger_les_armes()
        if self.arme:
            self.joueur.arme = self.arme_par_nom(self.arme)
            if self.joueur.arme not in self.joueur.munitions:
                self.joueur._charger(self.joueur.arme)
        self.equiper_implants()
        if isinstance(self.vehicule, str):
            self.vehicule = vehicules_.Engin(u.vehicule(self.vehicule))
        elif isinstance(self.vehicule, dict):
            self.vehicule = vehicules_.engin_depuis_dict(self.vehicule, {v.nom: v for v in u.vehicules})
        # Le LLM parle avec les noms de l'univers (« Piratage ») ; le moteur, avec ceux du socle.
        self.noms_competences = {u.nom_affiche(nom): nom for nom in self.personnage.competences}
        self.memoire = Memoire(self.campagne)
        self.jour_du_monde = self.moment.jour  # le dernier jour jusqu'où le monde a vécu

    # --- Outils : catalogue et appel ---

    def schemas(self) -> list[dict]:
        """La liste des outils au format OpenAI, à envoyer au LLM à chaque tour."""
        return [{"type": "function",
                 "function": {"name": o.nom, "description": o.description, "parameters": o.parametres(self)}}
                for o in OUTILS.values() if o.disponible(self)]

    def appeler(self, nom: str, arguments: "dict | str | None" = None) -> dict:
        """Appelle un outil par son nom. Ne lève jamais d'exception : les erreurs sont renvoyées en clair."""
        try:
            if nom not in OUTILS or not OUTILS[nom].disponible(self):
                disponibles = sorted(n for n, o in OUTILS.items() if o.disponible(self))
                raise ErreurOutil(f"Outil inconnu : « {nom} ». Outils disponibles : {disponibles}.")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments.strip() else {}
                except json.JSONDecodeError as erreur:
                    raise ErreurOutil(f"Arguments illisibles (JSON invalide) : {erreur}.") from erreur
            arguments = dict(arguments or {})
            outil = OUTILS[nom]
            arguments = self._normaliser(arguments)
            _verifier_objet(arguments, outil.parametres(self))
            resultat = outil.fonction(self, **arguments)
            if self.monde is not None and self.moment.jour != self.jour_du_monde:
                resultat = resultat | self.vivre()  # le temps a passé : le monde a bougé
        except (ErreurOutil, monde_.MondeImpossible, lieux_.LieuImpossible, pnj_.PnjImpossible, trame_.TrameImpossible, ActionImpossible, soins.SoinImpossible, progression.ProgressionImpossible,
                implants_.ImplantImpossible, vehicules_.VehiculeImpossible, poursuite_.PoursuiteImpossible,
                ValueError, KeyError) as erreur:  # dont InventaireImpossible et CommerceImpossible
            resultat = {"erreur": str(erreur).strip("'\"")}
        self.journal.append({"outil": nom, "arguments": arguments, "resultat": resultat})
        return resultat

    def _normaliser(self, arguments: dict) -> dict:
        """Accepte aussi les noms de socle (« Technologie ») là où le schéma attend ceux de l'univers."""
        if "competence" in arguments:
            inverse = {socle: affiche for affiche, socle in self.noms_competences.items()}
            arguments["competence"] = inverse.get(arguments["competence"], arguments["competence"])
        return arguments

    # --- Aides internes ---

    def combattant(self, identifiant: str) -> Combattant:
        if identifiant == JOUEUR:
            return self.joueur
        if identifiant not in self.pnj:
            raise ErreurOutil(f"PNJ inconnu : « {identifiant} ». PNJ présents : {sorted(self.pnj)}.")
        return self.pnj[identifiant]

    def combat_en_cours(self) -> Combat:
        if self.combat is None:
            raise ErreurOutil("Aucun combat en cours : appelle d'abord debut_combat.")
        return self.combat

    def participant(self, identifiant: str) -> Combattant:
        """Un combattant du combat en cours ; refuse celui qui n'y est pas (créé mais jamais entré)."""
        combattant = self.combattant(identifiant)
        if combattant not in self.combat_en_cours().ordre:
            raise ErreurOutil(f"{combattant.nom} ({identifiant}) ne fait pas partie du combat : "
                              "fais-le entrer avec rejoindre_combat.")
        return combattant

    def ids(self) -> list[str]:
        return [JOUEUR] + sorted(self.pnj)

    def identifiant(self, combattant: Combattant) -> str:
        return JOUEUR if combattant is self.joueur else next(i for i, c in self.pnj.items() if c is combattant)

    def corps(self) -> implants_.Corps:
        """Les implants du joueur, avec le catalogue de l'univers."""
        u = self.univers
        return implants_.Corps({i.nom: i for i in u.implants}, {s.nom: s for s in u.systemes}, self.personnage.implants)

    def engin(self, identifiant: str) -> "vehicules_.Engin | None":
        """Le véhicule de quelqu'un : celui du joueur, ou celui donné au PNJ à sa création."""
        self.combattant(identifiant)
        return self.vehicule if identifiant == JOUEUR else self.engins.get(identifiant)

    def tous_les_engins(self) -> list:
        drones = [c.drone for c in self.pnj.values() if c.drone]
        return [e for e in [self.vehicule, *self.engins.values(), *drones] if e]

    def verifier_portee(self, attaquant: str, cible: str, arme):
        """Pendant une poursuite, la distance dit quelles armes portent (REGLES.md 12.4)."""
        p = self.poursuite
        if p is None or p.issue:
            return
        fuyard = p.fuyard.identifiant
        poursuivant = cible if attaquant == fuyard else attaquant if cible == fuyard else None
        if poursuivant not in p.distances:
            return
        distance = p.distances[poursuivant]
        if distance == poursuite_.SEME:
            raise ErreurOutil("Semé : personne n'est plus à portée.")
        if distance == poursuite_.PROCHE and arme.corps_a_corps:
            raise ErreurOutil("À « proche », la mêlée ne porte pas : il faut être au contact.")
        if distance == poursuite_.LOIN and arme.portee.value != "longue":
            raise ErreurOutil(f"À « loin », seule la portée longue porte : pas {arme.nom} ({arme.portee.value}).")

    def blesser(self, victime: Combattant, degats: int):
        """Des dégâts hors des coups (un accident) : blessure grave, agonie, comme en combat."""
        return blesser(self.des, self.univers.curseur, victime, degats)

    def equiper_implants(self):
        """L'armure et les armes implantées du joueur, telles que le combat les voit."""
        if self.univers.implants:
            corps = self.corps()
            self.joueur.armure_implantee = corps.armure()
            self.joueur.armes_implantees = frozenset(a.nom for a in corps.armes())

    def armes_du_joueur(self) -> list:
        """Les armes que le joueur possède, plus ses armes implantées (des lames-mantis…). Sans inventaire
        (avant l'économie) : toute l'armurerie de l'univers."""
        possedees = self.inventaire.armes() if self.inventaire else list(self.univers.armes)
        return possedees + (self.corps().armes() if self.univers.implants else [])

    def charger_les_armes(self):
        """Reprend, pour chaque arme de l'inventaire, ce que contenait son chargeur à la dernière sauvegarde."""
        for objet in self.inventaire.objets:
            if objet["famille"] == inventaire_.ARME:
                arme = self.univers.arme(objet["nom"])
                if arme.munitions and arme not in self.joueur.munitions:
                    self.joueur.munitions[arme] = objet.get("charge", arme.chargeur.capacite)

    def noter_les_charges(self):
        """Écrit dans l'inventaire ce que contient chaque arme, pour la sauvegarde."""
        if self.inventaire:
            for objet in self.inventaire.objets:
                if objet["famille"] == inventaire_.ARME:
                    arme = self.univers.arme(objet["nom"])
                    if arme in self.joueur.munitions:
                        objet["charge"] = self.joueur.munitions[arme]

    def arme_par_nom(self, nom: str):
        for arme in self.armes_du_joueur():
            if arme.nom == nom:
                return arme
        raise ErreurOutil(f"Arme inconnue : « {nom} ».")

    @property
    def a_la_magie(self) -> bool:
        return self.univers.magie_active and bool(self.univers.domaines)

    def sorts_connus(self, combattant: Combattant) -> dict[str, magie.Sort]:
        """Le joueur connaît tous les sorts de ses deux domaines ; un PNJ, ceux qu'on lui a donnés."""
        if not self.a_la_magie:
            return {}
        if combattant is self.joueur:
            sorts = self.univers.sorts_connus(self.personnage.domaines)
        else:
            sorts = [self.univers.sort(nom) for nom in getattr(combattant.fiche, "sorts", ())]
        return {s.nom: s for s in sorts}

    def vivre(self) -> dict:
        """Fait vivre le monde jusqu'au jour courant, et renvoie ce que le MJ doit en raconter."""
        monde_.avancer(self.monde, self.des, self.moment.jour)
        self.jour_du_monde = self.moment.jour
        self.offres()
        fraiches = monde_.nouvelles(self.monde)
        resultat = {"nouvelles_du_monde": fraiches} if fraiches else {}
        if meteo_.actif(self.monde):
            meteo_.avancer(self.monde, self.des, self.moment.jour)
            resultat["temps_du_jour"] = meteo_.decrire(self.monde, self.univers.nom_affiche)
        return resultat

    def offres(self) -> list[dict]:
        """Les offres de mission ouvertes là où est le joueur, tenues à jour (REGLES.md 14.8)."""
        contacts = [p.nom for i, p in self.memoire.pnj.items() if not self.memoire.est_mort(i)]
        return missions.renouveler(self.monde, self.des, self.moment.jour, self.personnage.cran, contacts)

    def oublier_les_effets(self):
        """Les effets des sorts ne survivent ni à la fin d'un combat, ni à la fin de la demi-journée."""
        for combattant in [self.joueur, *self.pnj.values()]:
            combattant.effets = []

    def evenements_du_round(self) -> list[str]:
        return [ligne for entree in self.journal[self.debut_round:]
                for ligne in decrire(entree["outil"], entree["arguments"], entree["resultat"], self)]


OUTILS: dict[str, Outil] = {}


def outil(description: str, parametres: Callable[[Session], dict],
          disponible: Callable[[Session], bool] = lambda s: True):
    """Déclare une fonction comme outil du MJ. Son nom d'outil est son nom de fonction."""
    def enregistrer(fonction):
        OUTILS[fonction.__name__] = Outil(fonction.__name__, description, parametres, fonction, disponible)
        return fonction
    return enregistrer


def _objet(proprietes: dict, requis: list[str] = ()) -> dict:
    return {"type": "object", "properties": proprietes, "required": list(requis), "additionalProperties": False}


def _enum(valeurs, description: str = "") -> dict:
    schema = {"type": "string", "enum": list(valeurs)}
    if description:
        schema["description"] = description
    return schema


def _ids(session: Session, description: str) -> dict:
    return _enum(session.ids(), description)


def _difficulte() -> dict:
    return _enum(DIFFICULTES, "Facile +20, normale 0, difficile −20, extrême −40.")


# --- État -------------------------------------------------------------------------------------

def _effets(c: Combattant) -> list[str]:
    """Les effets des sorts sur un combattant, en clair."""
    textes = []
    for e in c.effets:
        if e.nature == "protection":
            textes.append(f"{e.sort} (armure +{e.valeur})")
        elif e.nature == "attaque":
            textes.append(f"{e.sort} (persistant)")
        elif e.nature == NATURE_IEM:
            textes.append(f"{e.sort} (électronique coupée)")
        else:
            textes.append(f"{e.sort} ({e.valeur:+d} à ses jets)")
    return textes


def _etat_combattant(c: Combattant) -> dict:
    f = c.fiche
    etat = {"nom": c.nom, "pv": f.pv, "pv_max": f.pv_max, "etat": f.etat.value, "blessure_grave": f.blessure_grave,
            "arme": c.arme.nom if c.arme else None, "armure": c.armure.nom if c.armure else None}
    if c.arme and c.arme.calibre:
        etat["calibre"] = c.arme.calibre
    if c.arme and c.arme.munitions:
        etat["munitions"] = c.munitions_restantes()
    if c.arme and c.arme.zone:
        etat["arme_de_zone"] = c.arme.zone
    if c.drone:
        etat["drone"] = f"télépiloté par {c.operateur.nom}" if c.operateur else "autonome"
    if getattr(f, "sorts", None):
        etat["pm"] = f.pm
    if c.effets:
        etat["effets_magiques"] = _effets(c)
    return etat


@outil("Consulter l'état du personnage joueur, du temps et du combat en cours. N'a aucun effet sur le jeu.",
       lambda s: _objet({}))
def etat(session: Session) -> dict:
    p = session.personnage
    resultat = {
        "moment": str(session.moment),
        "joueur": _etat_combattant(session.joueur) | {
            "sante_mentale": p.sm, "sm_max": p.sm_max, "points_destin": p.points_destin, "xp": p.xp,
            "argent": p.argent, "monnaie": session.univers.monnaie,
            "niveau_de_vie": economie.niveau_effectif(p).value, "prochaine_echeance": f"jour {p.echeance}",
            **({"dettes": [{"creancier": d["creancier"], "reste_du": d["reste"], "par_semaine": d["echeance"]}
                           for d in p.dettes]} if p.dettes else {}),
            **({"missions": {i: m["recompense"] for i, m in p.missions.items()}} if p.missions else {}),
            "troubles": [t.type.value for t in p.troubles], "folie": p.folie,
        } | ({"pm": p.pm, "pm_max": p.pm_max, "domaines": p.domaines} if session.a_la_magie else {})
          | ({"implants": [i["nom"] + (f" ({i['cote']})" if i.get("cote") else "") for i in p.implants]}
             if p.implants else {})
          | ({"vehicule": _etat_engin(session.vehicule)} if session.vehicule else {})
          | ({"objets": list(p.objets)} if p.objets else {})
          | ({"inventaire": session.inventaire.resume()} if session.inventaire else {}),
        "pnj": {i: _etat_combattant(c) for i, c in session.pnj.items()},
    }
    if session.combat:
        au_tour_de = session.combat.au_tour_de
        resultat["combat"] = {"round": session.combat.round, "ordre": [c.nom for c in session.combat.ordre],
                              "au_tour_de": au_tour_de.nom if au_tour_de else None,
                              "budget_joueur": {t.value: session.joueur.budget.restants(t) for t in TypeAction}}
        if session.combat.fumee:
            resultat["combat"]["fumee_rounds"] = session.combat.fumee
    if session.poursuite:
        resultat["poursuite"] = _etat_poursuite(session)
    return resultat


@outil("Faire avancer le temps à la période suivante (matin → après-midi → nuit → matin du jour suivant).",
       lambda s: _objet({}))
def avancer_temps(session: Session) -> dict:
    session.moment = session.moment.suivant()
    session.oublier_les_effets()
    resultat = {"moment": str(session.moment)}
    # Le coût de la vie tombe tout seul, tous les 7 jours (REGLES.md 13.2) : au MJ de le raconter
    echeances = _echeances_du_joueur(session)
    if session.inventaire and session.personnage.commandes:
        arrivees = commerce.livrer_les_commandes(session.personnage, session.inventaire, session.univers,
                                                 session.moment.jour)
        if arrivees:
            session.charger_les_armes()
            resultat["commandes_arrivees"] = arrivees
    if echeances:
        resultat["echeances"] = _echeances(echeances)
    return resultat


def _echeances(echeances) -> list[dict]:
    """Les échéances de la semaine, pour le MJ : le loyer, les dettes, le lien à charge."""
    lignes = []
    for e in echeances:
        ligne = {"jour": e.jour, "niveau_de_vie": e.niveau, "cout": e.cout, "argent": e.argent} if e.payee else {
            "jour": e.jour, "niveau_de_vie": e.niveau, "cout": e.cout, "impayee": True,
            "consequence": "il vit à la rue jusqu'à ce qu'une semaine soit payée"}
        if e.dettes_payees:
            ligne["dettes_payees"] = [{"creancier": c, "somme": s, "reste_du": r} for c, s, r in e.dettes_payees]
        if e.dettes_manquees:
            ligne["dettes_manquees"] = [
                {"creancier": c, "somme": s, "echeances_manquees": n,
                 "consequence": "le créancier fait monter la menace d'un cran : raconte-le"} for c, s, n in e.dettes_manquees]
        if e.lien is not None:
            ligne["lien_a_charge"] = "payé" if e.lien else (
                "impayé : le temps passé avec son lien ne le réconforte plus, ouvre un fil")
        lignes.append(ligne)
    return lignes


# --- Tests hors combat ------------------------------------------------------------------------

def _dehors(s: Session, quoi: str) -> dict:
    """Le champ « dehors » d'un outil, dans une campagne qui a sa météo (REGLES.md 15.3)."""
    if not meteo_.actif(s.monde):
        return {}
    return {"dehors": {"type": "boolean", "description": f"Vrai si {quoi} dehors : le moteur applique le temps qu'il "
                                                         "fait. Faux à l'abri."}}


@outil("Faire un test de compétence du personnage joueur. À utiliser dès qu'une action a une issue incertaine "
       "et des conséquences. Le moteur lance le d100 ; raconte ensuite le résultat selon son degré.",
       lambda s: _objet({
           "competence": _enum(sorted(s.noms_competences), "La compétence, avec son nom dans cet univers."),
           "difficulte": _difficulte(),
           "pourquoi": {"type": "string", "description": "Ce que le personnage tente, en une phrase."},
       } | _dehors(s, "l'action se passe"), ["competence", "difficulte"]))
def test_competence(session: Session, competence: str, difficulte: str, pourquoi: str = "",
                    dehors: bool = False) -> dict:
    socle = session.noms_competences[competence]
    meteo = meteo_.modificateur(session.monde, socle) if dehors else 0
    valeur = session.joueur.valeur(socle) + meteo
    resultat = tester(session.des, valeur, DIFFICULTES[difficulte])
    progression.cocher(session.personnage, socle, resultat)
    if not session.combat:
        session.joueur.consommer_effets_du_jet()
    session.dernier_test = {"valeur": valeur, "difficulte": difficulte, "resultat": resultat, "nom": competence}
    trouve = None
    if socle == "Investigation" and resultat.reussi and not session.combat and lieux_.actifs(session.monde):
        trouve = lieux_.reveler(session.monde)
    return {"competence": competence, **_test(resultat)} | (
        {"meteo": f"{meteo_.temps(session.monde)} : {meteo:+d}"} if meteo else {}) | (
        {"lieu_trouve": f"En cherchant, il découvre un lieu caché du quartier : {trouve['nom']}, tenu par "
                        f"{trouve['tenancier']['nom']}."} if trouve else {})


@outil("Faire un test de caractéristique du personnage joueur, quand aucune compétence ne correspond.",
       lambda s: _objet({
           "caracteristique": _enum([c.libelle for c in Caracteristique]),
           "difficulte": _difficulte(),
       }, ["caracteristique", "difficulte"]))
def test_caracteristique(session: Session, caracteristique: str, difficulte: str) -> dict:
    carac = next(c for c in Caracteristique if c.libelle == caracteristique)
    valeur = session.personnage.carac(carac) + session.joueur.modificateur_magique
    resultat = tester(session.des, valeur, DIFFICULTES[difficulte])
    if not session.combat:
        session.joueur.consommer_effets_du_jet()
    session.dernier_test = {"valeur": valeur, "difficulte": difficulte, "resultat": resultat, "nom": caracteristique}
    return {"caracteristique": caracteristique, **_test(resultat)}


@outil("Forcer le dernier test raté : le joueur retente en changeant d'approche, une seule fois. "
       "S'il rate encore, la conséquence doit être grave. À n'utiliser que si le joueur le demande.",
       lambda s: _objet({}))
def forcer_jet(session: Session) -> dict:
    if not session.dernier_test:
        raise ErreurOutil("Aucun test à forcer.")
    t = session.dernier_test
    resultat = forcer(session.des, t["valeur"], t["resultat"], DIFFICULTES[t["difficulte"]])
    session.dernier_test = dict(t, resultat=resultat)
    return {"test": t["nom"], **_resume(resultat), "consequence_grave": resultat.consequence_grave}


# --- Santé mentale, soins, repos ---------------------------------------------------------------

@outil("Infliger un choc au personnage joueur. Choisis le choc dans la liste ; le moteur calcule sa gravité "
       "(lien, accoutumance, réglages de l'univers) et lance le test de Santé mentale.",
       lambda s: _objet({
           "choc": _enum([c.name for c in sante_mentale.Choc],
                         " ; ".join(f"{c.name} : {c.description}" for c in sante_mentale.Choc)),
           "concerne_lien": {"type": "boolean", "description": "Vrai si le choc touche le lien du personnage."},
           "en_combat": {"type": "boolean", "description": "Vrai si le choc survient en plein combat."},
       }, ["choc"]))
def choc(session: Session, choc: str, concerne_lien: bool = False, en_combat: bool = False) -> dict:
    r = sante_mentale.subir_choc(session.des, session.personnage, sante_mentale.Choc[choc], session.moment,
                                 session.univers.reglages_mentaux(), concerne_lien, en_combat)
    if r.gravite is None:
        return {"choc": r.choc.description, "test": False, "explication": "Ce choc ne déclenche pas de test ici."}
    resultat = {"choc": r.choc.description, "gravite": r.gravite.name.lower(), **_resume(r.test),
                "perte": r.perte, "sante_mentale": r.sm_apres}
    if r.crise:
        resultat["crise"] = {"type": r.crise.value, "rounds": r.duree_crise}
    if r.trouble:
        resultat["trouble"] = r.trouble.type.value
    if r.folie:
        resultat["folie"] = True
    return resultat


@outil("Soigner le personnage joueur avec un jet de Médecine (un soin réussi par demi-journée ; après un échec, "
       "seul un autre soigneur peut retenter). "
       "Le soigneur peut être le joueur lui-même ou un PNJ créé avec creer_pnj.",
       lambda s: _objet({"soigneur": _ids(s, "Qui soigne.")}, ["soigneur"]))
def soigner(session: Session, soigneur: str) -> dict:
    r = soins.soigner(session.des, session.combattant(soigneur).fiche, session.personnage, session.moment)
    return {**_resume(r.test), "pv_gagnes": r.gain, "pv": r.pv_apres, "blessure_grave_soignee": r.blessure_grave_soignee}


@outil("Faire se reposer le personnage joueur : court (30 min) ou moyen (1 à 2 h) une fois par demi-journée, "
       "long la nuit.",
       lambda s: _objet({"type": _enum(REPOS), "interrompu": {"type": "boolean"}}, ["type"]))
def repos(session: Session, type: str, interrompu: bool = False) -> dict:
    r = soins.reposer(session.personnage, REPOS[type], session.moment, session.univers.curseur, interrompu,
                      sans_abri=economie.a_la_rue(session.personnage))
    resultat = {"repos": type, "pv_gagnes": r.gain, "pv": r.pv_apres, "blessure_grave_guerie": r.blessure_grave_guerie}
    if session.a_la_magie:
        resultat.update(pm_gagnes=r.pm_gagnes, pm=r.pm_apres)
    return resultat


@outil("Faire récupérer de la Santé mentale au joueur : une discussion (avec son lien ou longuement avec "
       "quelqu'un, une fois par jour) ou une thérapie pendant le repos long (une fois par nuit).",
       lambda s: _objet({
           "source": _enum(["discussion", "thérapie"]),
           "avec_son_lien": {"type": "boolean", "description": "Pour une discussion : il passe ce temps avec son lien."},
           "soignant": _ids(s, "Pour une thérapie : qui l'accompagne (le joueur seul, ou un PNJ)."),
           "competence": _enum(["Perspicacité", "Médecine"], "Pour une thérapie."),
       }, ["source"]))
def recuperer_sante_mentale(session: Session, source: str, soignant: str = JOUEUR,
                            competence: str = "Perspicacité", avec_son_lien: bool = False) -> dict:
    if source == "discussion":
        r = sante_mentale.discussion(session.des, session.personnage, session.moment, avec_son_lien)
    else:
        niveau = economie.niveau_effectif(session.personnage)
        if niveau is economie.NiveauDeVie.A_LA_RUE:
            raise ErreurOutil(f"{session.personnage.nom} vit à la rue : pas de récupération de Santé mentale la nuit, "
                              "faute d'un endroit sûr.")
        bonus = economie.BONUS_THERAPIE_CONFORTABLE if niveau is economie.NiveauDeVie.CONFORTABLE else 0
        r = sante_mentale.therapie(session.des, session.combattant(soignant).fiche, session.personnage,
                                   session.moment, competence, modificateur=bonus)
    resultat = {"sm_gagnee": r.gain, "sante_mentale": r.sm_apres}
    if r.test:
        resultat.update(_resume(r.test))
    if r.troubles_gueris:
        resultat["troubles_gueris"] = [t.type.value for t in r.troubles_gueris]
    return resultat


@outil("Enregistrer un jalon de campagne atteint par le joueur (objectif ou quête réussis, arc terminé, "
       "motivation accomplie, fin de session). Il rapporte de la Santé mentale et de l'XP.",
       lambda s: _objet({"jalon": _enum(JALONS)}, ["jalon"]))
def jalon(session: Session, jalon: str) -> dict:
    r = sante_mentale.jalon_atteint(session.des, session.personnage, JALONS[jalon])
    xp = progression.gagner_xp(session.personnage, JALONS[jalon])
    return {"jalon": jalon, "sm_gagnee": r.gain, "sante_mentale": r.sm_apres, "xp_gagnee": xp}


@outil("Utiliser un point de destin du joueur, seulement s'il l'accepte : « laisse_pour_mort » quand il "
       "vient de mourir, « sortir_de_la_folie » quand il a sombré.",
       lambda s: _objet({"usage": _enum(["laisse_pour_mort", "sortir_de_la_folie"])}, ["usage"]))
def point_de_destin(session: Session, usage: str) -> dict:
    if usage == "laisse_pour_mort":
        laisser_pour_mort(session.joueur)
    else:
        sante_mentale.sauver_de_la_folie(session.personnage)
    return {"usage": usage, "points_destin_restants": session.personnage.points_destin,
            "etat": session.personnage.etat.value, "sante_mentale": session.personnage.sm}


# --- PNJ et combat ----------------------------------------------------------------------------

def _champs_du_nom(s: Session) -> dict:
    """Le nom d'un PNJ dans le schéma d'un outil : libre dans une campagne d'avant, tiré par le moteur sinon
    (REGLES.md 15.1)."""
    if not noms_.actifs(s.monde):
        return {"nom": {"type": "string"}}
    return {"sexe": _enum(noms_.SEXES, "Pour un nouveau PNJ : le moteur tire son nom, ne l'invente pas."),
            "origine": _enum(s.monde["noms"]["origines"], "L'origine de son nom, seulement si l'histoire l'impose."),
            "faction": _enum(sorted(s.monde["factions"]), "La faction dont il est membre, s'il en a une.")}


def _nom_requis(s: Session) -> list[str]:
    return [] if noms_.actifs(s.monde) else ["nom"]


def _nom_du_pnj(session: Session, identifiant: str, nom: str | None, sexe: str | None = None,
                origine: str | None = None, faction: str | None = None) -> str:
    """Le nom d'un PNJ : celui qu'il porte déjà, sinon celui que le moteur tire."""
    if nom:
        return nom
    if not noms_.actifs(session.monde):
        raise ErreurOutil("Paramètre obligatoire manquant : « nom ».")
    if identifiant in session.memoire.pnj:
        return session.memoire.pnj[identifiant].nom
    if identifiant in session.pnj:
        return session.pnj[identifiant].nom
    if sexe is None:
        raise ErreurOutil("Précise « sexe » : le moteur tire le nom d'un nouveau PNJ.")
    gang = faction is not None and session.monde["factions"][faction]["type"] in monde_.HORS_LA_LOI
    try:
        return noms_.tirer(session.monde, session.des, sexe, origine, gang)
    except noms_.NomImpossible as e:
        raise ErreurOutil(str(e)) from e


def _dangers_en_cours(session: Session) -> list[str]:
    """Le danger de chaque mission ouverte : il plafonne la menace des PNJ (REGLES.md 15.2)."""
    dangers = [m.get("danger") or m.get("offre", {}).get("danger") for m in session.personnage.missions.values()]
    return [d for d in dangers if d]


def _schema_pnj_par_role(s: Session) -> dict:
    return _objet({
        "identifiant": {"type": "string", "description": "Court et unique, par exemple ganger_couteau."},
        **_champs_du_nom(s),
        "camp": _enum(["ennemis", "allies", "neutres"]),
        "role": _enum(pnj_.noms_des_roles(s.monde), "Ce qu'il est. Le moteur tire ses chiffres, son équipement et "
                                                    "ses deux traits : ne les invente pas."),
        "menace": _enum(pnj_.MENACES, "faible : sans danger ; moyenne : voyou ordinaire ; forte : professionnel ; "
                                      "élite : un seul par scène. Le danger de la mission la plafonne."),
    } | ({"tenancier": _enum([l["nom"] for l in lieux_.du_quartier(s.monde)],
                             "Pour le tenancier d'un lieu du quartier : son lieu. Son nom, son rôle et sa menace "
                             "sont déjà fixés : ne donne alors ni sexe, ni role, ni menace.")}
         if lieux_.actifs(s.monde) and lieux_.du_quartier(s.monde) else {}) | (
        {"rencontre": {"type": "boolean", "description": "Vrai pour le PNJ de la rencontre de rue en cours : son "
                                                         "nom, son rôle et sa menace sont déjà fixés."}}
        if rencontres_.en_cours(s.monde) else {}) | ({"vehicule": _enum([v.nom for v in s.univers.vehicules], "Ce qu'il conduit ou monte, pour une "
                            "poursuite.")} if s.univers.vehicules else {}) | ({
        "sorts": {"type": "array", "items": _enum(sorted(x.nom for d in s.univers.domaines for x in d.tous)),
                  "description": "Pour un lanceur de sorts : les sorts qu'il connaît. Sa Magie suit sa menace."},
    } if s.a_la_magie else {}), ["identifiant", *_nom_requis(s), "camp",
                                 *([] if lieux_.actifs(s.monde) or rencontres_.actives(s.monde)
                                   else ["role", "menace"])])


@outil("Créer un PNJ (ennemi, allié ou passant) avec un profil simplifié. Son identifiant sert ensuite "
       "dans les autres outils. L'arme et l'armure viennent de l'armurerie de l'univers.",
       lambda s: _schema_pnj_par_role(s) if pnj_.actifs(s.monde) else _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple ganger_couteau."},
           **_champs_du_nom(s),
           "camp": _enum(["ennemis", "allies", "neutres"]),
           "combat": {"type": "integer", "minimum": PNJ_COMBAT[0], "maximum": PNJ_COMBAT[1],
                      "description": "Pourcentage pour attaquer, esquiver et riposter (45 = voyou ordinaire)."},
           "pv": {"type": "integer", "minimum": PNJ_PV[0], "maximum": PNJ_PV[1]},
           "arme": _enum([a.nom for a in s.univers.armes]),
           "armure": _enum([a.nom for a in s.univers.armures]),
           "dexterite": {"type": "integer", "minimum": 15, "maximum": 90},
           "competences": {"type": "object", "additionalProperties": True,
                           "description": "Autres talents, par exemple {\"Médecine\": 70}."},
       } | ({"vehicule": _enum([v.nom for v in s.univers.vehicules], "Ce qu'il conduit ou monte, pour une "
                               "poursuite.")} if s.univers.vehicules else {}) | ({
           "magie": {"type": "integer", "minimum": PNJ_COMPETENCE[0], "maximum": PNJ_COMPETENCE[1],
                     "description": "Pour un lanceur de sorts : son pourcentage de Magie."},
           "pm": {"type": "integer", "minimum": PNJ_PM[0], "maximum": PNJ_PM[1], "description": "Ses points de magie."},
           "sorts": {"type": "array", "items": _enum(sorted(x.nom for d in s.univers.domaines for x in d.tous)),
                     "description": "Les sorts qu'il connaît, pris dans les domaines de l'univers."},
       } if s.a_la_magie else {}), ["identifiant", *_nom_requis(s), "camp", "combat", "pv"]))
def creer_pnj(session: Session, identifiant: str, camp: str, combat: int | None = None, pv: int | None = None,
              nom: str | None = None, arme: str | None = None, armure: str | None = None, dexterite: int = 50,
              competences: dict | None = None, magie: int | None = None, pm: int = 0,
              sorts: list | None = None, vehicule: str | None = None, sexe: str | None = None,
              origine: str | None = None, faction: str | None = None, role: str | None = None,
              menace: str | None = None, tenancier: str | None = None, rencontre: bool = False) -> dict:
    if session.memoire.est_mort(identifiant):
        raise ErreurOutil(f"{session.memoire.pnj[identifiant].nom} ({identifiant}) est mort : "
                          "la mémoire de la campagne s'en souvient.")
    if identifiant == JOUEUR or identifiant in session.pnj:
        # Le MJ voulait sans doute un nouveau PNJ : on lui dit qui existe déjà et quel identifiant est libre
        libre = next(f"{identifiant}_{n}" for n in range(2, 100) if f"{identifiant}_{n}" not in session.pnj)
        connus = ", ".join(f"{i} ({c.nom})" for i, c in session.pnj.items())
        raise ErreurOutil(f"L'identifiant « {identifiant} » est déjà pris. PNJ existants : {connus}. "
                          f"Pour un nouveau PNJ, prends un autre identifiant, par exemple « {libre} ».")
    profil, patron = None, None
    if pnj_.actifs(session.monde):
        if tenancier:
            patron = lieux_.lieu(session.monde, tenancier)["tenancier"]
        elif rencontre:
            croise = rencontres_.en_cours(session.monde)
            if croise is None:
                raise ErreurOutil("Aucune rencontre de rue n'est en cours ici.")
            patron = croise["pnj"]
        if patron:
            role, menace, nom = patron["role"], patron["menace"], patron["nom"]
        if role is None or menace is None:
            raise ErreurOutil("Précise « role » et « menace » : le moteur tire le reste.")
        elite = session.monde["pnj"]["elite"]
        if menace == pnj_.ELITE and elite in session.pnj and session.pnj[elite].fiche.etat is Etat.ACTIF:
            raise ErreurOutil(f"Un seul PNJ d'élite par scène : {session.pnj[elite].nom} est déjà là.")
        # Le tenancier d'un lieu garde la menace tirée avec la carte, quelle que soit la mission en cours
        dangers = ["exceptionnelle"] if patron else _dangers_en_cours(session)
        profil = pnj_.tirer(session.monde, session.des, session.univers, role, menace, dangers)
        if patron and patron["caractere"]:
            profil["caractere"], profil["signe"] = patron["caractere"], patron["signe"]
        combat, pv, dexterite = profil["combat"], profil["pv"], profil["dexterite"]
        arme, armure, competences = profil["arme"], profil["armure"], None
        if sorts:
            magie, pm = profil["niveau"], profil["niveau"] // 2
    elif combat is None or pv is None:
        raise ErreurOutil("Paramètres obligatoires manquants : « combat » et « pv ».")
    talents = dict(profil["competences"]) if profil else {}
    for nom_competence, valeur in (competences or {}).items():
        socle = session.noms_competences.get(nom_competence, nom_competence)
        if not isinstance(valeur, int) or not PNJ_COMPETENCE[0] <= valeur <= PNJ_COMPETENCE[1]:
            raise ErreurOutil(f"La compétence « {nom_competence} » d'un PNJ va de 0 à {PNJ_COMPETENCE[1]}.")
        talents[socle] = valeur
    if sorts and magie is None:
        raise ErreurOutil("Un PNJ qui connaît des sorts a un pourcentage de Magie : précise « magie ».")
    if magie is not None:
        talents["Magie"] = magie
    nom = _nom_du_pnj(session, identifiant, nom, sexe, origine, faction)
    fiche = FichePnj(nom, combat=combat, pv_max_base=pv, dexterite=dexterite, competences=talents, pm=pm,
                     sorts=tuple(sorts or ()))
    u = session.univers
    session.pnj[identifiant] = Combattant(fiche, camp, u.arme(arme) if arme else None,
                                          u.armure(armure) if armure else None)
    if session.inventaire:  # les munitions sont comptées pour tout le monde (REGLES.md 13.5)
        session.pnj[identifiant].reserve = ReservePnj(u.arme(arme) if arme else None)
    if vehicule:
        session.engins[identifiant] = vehicules_.Engin(u.vehicule(vehicule))
    if profil and menace == pnj_.ELITE:
        session.monde["pnj"]["elite"] = identifiant
    if profil and rencontre:
        rencontres_.clore(session.monde)  # le PNJ de la rencontre ne se crée qu'une fois
    return {"pnj": identifiant, **_etat_combattant(session.pnj[identifiant])} | (
        {"vehicule": vehicule} if vehicule else {}) | ({
            "role": role, "menace": menace, "combat": combat,
            "competences": {u.nom_affiche(c): v for c, v in profil["competences"].items()},
            "caractere": profil["caractere"], "signe": profil["signe"],
            "consigne": "Joue-le avec ce caractère et ce signe. S'il compte, garde-les dans son rôle (noter_pnj).",
        } if profil else {})


@outil("Tester une embuscade : la Perception du joueur contre la Discrétion des agresseurs.",
       lambda s: _objet({"discretion_agresseurs": {"type": "integer", "minimum": 0, "maximum": 100}},
                        ["discretion_agresseurs"]))
def embuscade(session: Session, discretion_agresseurs: int) -> dict:
    r = tester_embuscade(session.des, session.joueur.valeur("Perception"), discretion_agresseurs)
    return {"discretion": _resume(r.discretion), "perception": _resume(r.perception), "joueur_surpris": r.surpris}


@outil("Commencer un combat entre le joueur et des PNJ. Le moteur fixe l'ordre d'initiative et tient le tour "
       "de parole : chacun agit à son tour, puis fin_de_tour passe au suivant.",
       lambda s: _objet({
           "pnj": {"type": "array", "items": _enum(sorted(s.pnj)), "description": "Les PNJ qui combattent."},
           "surpris": _enum(["personne", "joueur", "ennemis"], "Le camp surpris perd son premier round."),
       } | _dehors(s, "le combat a lieu"), ["pnj"]))
def debut_combat(session: Session, pnj: list, surpris: str = "personne", dehors: bool = False) -> dict:
    if session.combat:
        raise ErreurOutil("Un combat est déjà en cours.")
    if not pnj:
        raise ErreurOutil("Il faut au moins un PNJ pour un combat.")
    participants = [session.joueur] + [session.combattant(i) for i in pnj]
    if surpris == "joueur":
        surpris_liste = [session.joueur]
    elif surpris == "ennemis":
        surpris_liste = [c for c in participants if c.camp == "ennemis"]
    else:
        surpris_liste = []
    session.combat = Combat(session.des, participants, session.univers.curseur, surpris_liste, tour_par_tour=True)
    session.rounds, session.debut_round = [], len(session.journal) + 1  # + 1 : cet appel-ci
    meteo = {}
    if dehors:
        session.combat.malus_tir, session.combat.malus_tir_long = meteo_.malus_de_tir(session.monde)
        if session.combat.malus_tir or session.combat.malus_tir_long:
            meteo = {"meteo": f"{meteo_.temps(session.monde)} : le moteur l'applique aux tirs"}
    return {"round": 1, "ordre_initiative": [c.nom for c in session.combat.ordre],
            "au_tour_de": _qui_joue(session), "consigne": _consigne(session), "fiche": _fiche(session)} | meteo


@outil("Faire entrer des PNJ dans le combat en cours (renforts, passant qui s'en mêle). Le moteur les place "
       "dans l'ordre d'initiative.",
       lambda s: _objet({"pnj": {"type": "array", "items": _enum(sorted(s.pnj)), "description": "Les PNJ qui entrent."}},
                        ["pnj"]))
def rejoindre_combat(session: Session, pnj: list) -> dict:
    c = session.combat_en_cours()
    if not pnj:
        raise ErreurOutil("Indique au moins un PNJ.")
    for identifiant in pnj:
        c.rejoindre(session.combattant(identifiant))
    return {"ordre_initiative": [x.nom for x in c.ordre], "au_tour_de": _qui_joue(session),
            "consigne": _consigne(session)}


@outil("Une action de combat sans attaque : se déplacer, viser (+20 au tir de ce round, interdit après un "
       "déplacement), recharger (changer de chargeur), garnir à la main (une action simple pour quelques "
       "cartouches, quand il n'y a plus de chargeur garni), ou dégainer une de ses armes (« aucune » pour ranger).",
       lambda s: _objet({
           "qui": _ids(s, "Qui agit."),
           "action": _enum(["deplacer", "viser", "recharger", "garnir", "degainer"]),
           "arme": _enum([a.nom for a in s.armes_du_joueur()] + ["aucune"], "Pour degainer."),
           "avec_la_mineure": {"type": "boolean", "description": "Pour garnir : y consacrer aussi son action "
                                                                 "mineure, pour 2 cartouches de plus."},
       }, ["qui", "action"]))
def action_combat(session: Session, qui: str, action: str, arme: str | None = None,
                  avec_la_mineure: bool = False) -> dict:
    c, combattant = session.combat_en_cours(), session.participant(qui)
    garnies = None
    if action == "deplacer":
        c.deplacer(combattant)
    elif action == "viser":
        c.viser(combattant)
    elif action == "recharger":
        c.recharger(combattant)
    elif action == "garnir":
        garnies = c.garnir(combattant, avec_la_mineure)
    else:
        if arme is None:
            raise ErreurOutil("Pour degainer, précise l'arme.")
        fiche = None if arme == "aucune" else session.arme_par_nom(arme)
        rangee = bool(fiche and combattant is session.joueur and session.inventaire
                      and session.inventaire.a(arme, inventaire_.ARME) and not session.inventaire.est_pret(arme))
        c.degainer(combattant, fiche, rangee=rangee)
    return {"qui": qui, "action": action,
            "budget_restant": {t.value: combattant.budget.restants(t) for t in TypeAction},
            **({"cartouches_garnies": garnies} if garnies is not None else {}),
            **({"munitions": combattant.munitions_restantes()} if combattant.arme and combattant.arme.munitions else {}),
            **(_reserve(session, combattant))}


def _reserve(session: Session, combattant: Combattant) -> dict:
    """Pour le joueur : ses chargeurs et son vrac, que le MJ sache ce qu'il lui reste."""
    if combattant is not session.joueur or not session.inventaire:
        return {}
    resume = session.inventaire.resume()
    return {"chargeurs": resume["chargeurs"], "cartouches_en_vrac": resume["vrac"]}


@outil("Gérer ce que porte le personnage joueur : mettre un objet sous la main (preparer), le remettre dans le "
       "sac (ranger), l'abandonner (poser), ou regarnir tous ses chargeurs avec ses cartouches en vrac "
       "(regarnir, hors combat seulement). En combat, sortir un objet du sac coûte une action simple, le "
       "ranger une action mineure.",
       lambda s: _objet({
           "action": _enum(["preparer", "ranger", "poser", "regarnir"]),
           "objet": _enum(s.inventaire.noms(), "L'objet, sauf pour regarnir."),
       }, ["action"]),
       disponible=lambda s: s.inventaire is not None)
def inventaire(session: Session, action: str, objet: str | None = None) -> dict:
    inv = session.inventaire
    if action == "regarnir":
        if session.combat is not None:
            raise ErreurOutil("En combat, on garnit à la main : action_combat, action « garnir ».")
        return {"action": action, "cartouches_garnies": inv.regarnir_tout(), **inv.resume()}
    if objet is None:
        raise ErreurOutil("Précise l'objet.")
    en_main = session.joueur.arme is not None and session.joueur.arme.nom == objet
    if action == "preparer":
        if inv.est_pret(objet):
            raise ErreurOutil(f"« {objet} » est déjà sous la main.")
        inv.preparer(objet)
        if session.combat is not None:
            session.combat._agir(session.joueur, TypeAction.SIMPLE)
    elif action == "ranger":
        inv.ranger(objet)
        if session.combat is not None:
            session.combat._agir(session.joueur, TypeAction.MINEURE)
    else:
        if objet == (session.joueur.armure.nom if session.joueur.armure else None):
            raise ErreurOutil("L'armure portée ne se pose pas en un geste.")
        inv.retirer(objet)
    if en_main and action != "preparer":
        session.joueur.arme = None
    return {"action": action, "objet": objet, **inv.resume()}


def _rapport_attaque(rapport: RapportAttaque) -> dict:
    resultat = {"attaquant": rapport.attaquant, "cible": rapport.cible, "attaque": _resume(rapport.attaque),
                "issue": rapport.issue.value}
    if rapport.defense:
        resultat["defense"] = _resume(rapport.defense)
    if rapport.touche:
        b = rapport.blessure
        resultat["touche"] = {"qui": rapport.touche, "degats_bruts": rapport.degats_bruts,
                              "armure": rapport.protection, "degats": b.degats, "pv": b.pv_apres,
                              "blessure_grave": b.blessure_grave, "etat": b.etat.value}
        if b.test_constitution:
            resultat["touche"]["test_constitution"] = _resume(b.test_constitution)
    if rapport.effets:
        resultat["effets"] = rapport.effets
    return resultat


@outil("Une attaque en combat (action simple). Le moteur gère la défense, les dégâts, l'armure et les blessures. "
       "Au corps à corps, la cible peut esquiver ou riposter ; contre un tir, seul le couvert compte. "
       "Une grenade, une roquette ou une charge passe par attaquer_zone.",
       lambda s: _objet({
           "attaquant": _ids(s, "Qui attaque."),
           "cible": _ids(s, "Qui est visé."),
           "defense": _enum(DEFENSES, "Au corps à corps seulement. Demande au joueur quand c'est lui la cible."),
           "couvert": _enum(COUVERTS, "Pour un tir : le couvert de la cible (partiel −20, lourd −40)."),
           "difficulte": _difficulte(),
           "bonus_majeure": _enum(BONUS_MAJEURE, "Le bonus choisi en cas de réussite majeure."),
       } | _tireur(s), ["attaquant", "cible"]))
def attaquer(session: Session, attaquant: str, cible: str, defense: str = "aucune", couvert: str = "aucun",
             difficulte: str = "normale", bonus_majeure: str = "dé de dégâts", tireur: str = "à pied") -> dict:
    if attaquant == cible:
        raise ErreurOutil("On ne s'attaque pas soi-même.")
    qui = session.participant(attaquant)
    session.verifier_portee(attaquant, cible, qui.arme_en_main)
    rapport = session.combat_en_cours().attaquer(
        qui, session.participant(cible), DEFENSES[defense], COUVERTS[couvert],
        BONUS_MAJEURE[bonus_majeure], DIFFICULTES[difficulte], tireur)
    return _rapport_attaque(rapport)


def _tireur(s: Session) -> dict:
    if not s.univers.vehicules:
        return {}
    return {"tireur": _enum([t for t in TIREURS if t != "tourelle"],
                            "D'un véhicule en mouvement : conducteur −20 (une main), passager −10.")}


def _armes_de_zone(s: Session) -> list[str]:
    """Les armes de zone qu'on porte à la main (les armes montées passent par tirer_arme_montee)."""
    return [a.nom for a in s.univers.armes if a.zone and not a.montee]


def _liste_ids(session: Session, description: str) -> dict:
    return {"type": "array", "items": _enum(session.ids()), "description": description}


def _rapport_zone(r: RapportZone) -> dict:
    resultat = {"attaquant": r.attaquant, "arme": r.arme, "competence": r.competence, "attaque": _resume(r.attaque),
                "issue": r.issue.value}
    if r.jet_degats:
        resultat["jet_degats"] = r.jet_degats
    cibles = []
    for c in r.cibles:
        cible = {"qui": c.qui}
        if c.esquive:
            cible["esquive"] = _resume(c.esquive)
        if c.couvert_lourd:
            cible["couvert_lourd"] = True
        if c.blessure:
            b = c.blessure
            cible |= {"degats_bruts": c.degats_bruts, "armure": c.protection, "degats": b.degats, "pv": b.pv_apres,
                      "blessure_grave": b.blessure_grave, "etat": b.etat.value}
            if b.test_constitution:
                cible["test_constitution"] = _resume(b.test_constitution)
        elif r.jet_degats:
            cible["degats"] = 0
        if c.test_constitution:
            cible["contre_l_eclat"] = _resume(c.test_constitution)
        if c.effets:
            cible["effets"] = c.effets
        cibles.append(cible)
    resultat["cibles"] = cibles
    if r.vehicules:
        resultat["vehicules"] = [{"vehicule": nom, "structure_perdue": perdue, "etat": etat}
                                 | ({"effets": effets} if effets else {}) for nom, perdue, etat, effets in r.vehicules]
    if r.effets:
        resultat["effets"] = r.effets
    return resultat


@outil("Une arme de zone (action simple) : grenade, lance-grenades, lance-flammes, roquette, charge posée. Elle "
       "touche toute la zone, alliés compris : petite 2 cibles, moyenne 4, grande 8. Le moteur lance l'attaque "
       "(ratée, elle dévie ; maladresse, elle tombe aux pieds du lanceur), l'esquive de chaque cible, les dégâts "
       "et les effets (brûlure, fumée, aveuglant, IEM).",
       lambda s: _objet({
           "attaquant": _ids(s, "Qui lance, tire ou fait sauter la charge."),
           "arme": _enum(_armes_de_zone(s), "L'arme de zone, si elle n'est pas déjà en main : la prendre coûte "
                                            "l'action mineure, comme dégainer."),
           "cibles": _liste_ids(s, "Tous ceux qui sont dans la zone, alliés compris."),
           "couvert_lourd": _liste_ids(s, "Ceux qui sont derrière un couvert lourd : les dégâts sont divisés par deux."),
           "sans_esquive": _liste_ids(s, "Ceux qui n'esquivent pas. Demande au joueur quand il est dans la zone."),
           "voisins": _liste_ids(s, "Ceux qui sont tout près du lanceur : touchés à la place des cibles "
                                    "s'il fait une maladresse."),
           "difficulte": _difficulte(),
       } | ({"vehicules": _liste_ids(s, "Ceux dont le véhicule est dans la zone : sa structure encaisse aussi.")}
            if s.univers.vehicules else {}) | _tireur(s), ["attaquant", "cibles"]),
       disponible=lambda s: s.combat is not None and bool(_armes_de_zone(s)))
def attaquer_zone(session: Session, attaquant: str, cibles: list, couvert_lourd: list = (),
                  sans_esquive: list = (), voisins: list = (), difficulte: str = "normale",
                  vehicules: list = (), tireur: str = "à pied", arme: str | None = None) -> dict:
    qui = session.participant(attaquant)
    c = session.combat_en_cours()
    if arme and (qui.arme is None or qui.arme.nom != arme):
        c.degainer(qui, session.arme_par_nom(arme) if qui is session.joueur else session.univers.arme(arme))
    engins = []
    for i in vehicules:
        engin = session.engin(i)
        if engin is None:
            raise ErreurOutil(f"{session.combattant(i).nom} n'a pas de véhicule.")
        engins.append(engin)
    utilisee = qui.arme
    rapport = c.attaquer_zone(
        qui, [session.participant(x) for x in cibles],
        [session.participant(x) for x in couvert_lourd], [session.participant(x) for x in sans_esquive],
        [session.participant(x) for x in voisins], DIFFICULTES[difficulte], engins, tireur)
    if qui is session.joueur and session.inventaire and utilisee and utilisee.usage_unique             and session.inventaire.a(utilisee.nom, inventaire_.ARME):
        session.inventaire.retirer(utilisee.nom, inventaire_.ARME)  # une grenade lancée n'est plus dans le sac
    if qui.drone and qui.drone.modele.kamikaze:
        qui.fiche.pv = qui.drone.structure = 0
        qui.fiche.etat = Etat.MORT
        rapport.effets.append(f"{qui.nom} se détruit en explosant.")
    return _rapport_zone(rapport)


# --- Véhicules et poursuites (REGLES.md 12) ---------------------------------------------------

def _etat_engin(e: vehicules_.Engin) -> dict:
    etat = {"nom": e.nom, "structure": e.structure, "structure_max": e.modele.structure_max, "etat": e.etat,
            "vitesse": e.vitesse, "maniabilite": e.maniabilite, "blindage": e.modele.blindage_total}
    if e.modele.nitro:
        etat["nitro"] = "utilisée" if e.nitro_utilisee else "prête"
    return etat


def _etat_poursuite(session: Session) -> dict:
    p = session.poursuite
    return {"zone": p.zone, "round": p.round, "fuyard": p.fuyard.nom,
            "distances": {c.identifiant: p.distance(c.identifiant) for c in p.poursuivants},
            "abandons": sorted(p.abandons)} | ({"issue": p.issue} if p.issue else {})


def _rapport_accident(a: vehicules_.RapportAccident) -> dict:
    occupants = []
    for qui, degats, blessure in a.occupants:
        o = {"qui": qui, "degats": degats}
        if blessure:
            o |= {"pv": blessure.pv_apres, "blessure_grave": blessure.blessure_grave, "etat": blessure.etat.value}
        occupants.append(o)
    return {"vehicule": a.vehicule, "vitesse": a.vitesse, "structure_perdue": a.structure_perdue, "etat": a.etat,
            "occupants": occupants}


def _vehicule_du_joueur(session: Session) -> vehicules_.Engin:
    if not session.vehicule:
        raise ErreurOutil("Le joueur n'a pas de véhicule.")
    return session.vehicule


@outil("Une manœuvre risquée au volant ou en selle (dérapage, se faufiler, sauter un obstacle, vitesse "
       "excessive) : jet de Pilotage plus la maniabilité. Conduire normalement ne demande aucun jet. "
       "En combat, c'est une action simple. Maladresse : l'accident.",
       lambda s: _objet({"difficulte": _difficulte()}),
       disponible=lambda s: bool(s.vehicule))
def piloter(session: Session, difficulte: str = "normale") -> dict:
    engin = _vehicule_du_joueur(session)
    if session.combat:
        session.combat.action_simple(session.joueur)
    r = vehicules_.piloter(session.des, session.joueur, engin, DIFFICULTES[difficulte], blesser=session.blesser)
    resultat = {"vehicule": engin.nom, **_test(r.test)}
    if r.cale:
        resultat["cale"] = "Le moteur cale : le véhicule usé refuse de repartir pour l'instant."
    if r.accident:
        resultat["accident"] = _rapport_accident(r.accident)
    return resultat


@outil("Réparer le véhicule du joueur (ou soigner sa monture), hors combat : une fois par demi-journée. "
       "Facile en atelier ; une épave ne se répare qu'en atelier.",
       lambda s: _objet({"reparateur": _ids(s, "Qui répare : le joueur ou un PNJ (mécano, palefrenier)."),
                         "atelier": {"type": "boolean", "description": "Dans un atelier (ou une écurie) ?"}},
                        ["reparateur"]),
       disponible=lambda s: bool(s.vehicule))
def reparer(session: Session, reparateur: str, atelier: bool = False) -> dict:
    if session.combat:
        raise ErreurOutil("On ne répare pas en plein combat.")
    engin = _vehicule_du_joueur(session)
    r = vehicules_.reparer(session.des, session.combattant(reparateur), engin, session.moment, atelier)
    return {"vehicule": engin.nom, **_resume(r.test), "structure_rendue": r.structure_rendue,
            "structure": r.structure, "etat": engin.etat}


@outil("Commencer une poursuite, en véhicule, en selle ou à pied. Le fuyard et ses poursuivants : chacun avec "
       "son véhicule (celui du joueur, ou celui donné au PNJ à sa création), sinon à pied. Elle commence en général "
       "à « proche ». Ensuite, un round_poursuite par round.",
       lambda s: _objet({
           "fuyard": _ids(s, "Celui qui fuit."),
           "poursuivants": {"type": "array", "items": _enum(s.ids()), "description": "Ceux qui le poursuivent."},
           "zone": _enum(poursuite_.ZONES, "Où commence la poursuite (le décor suit le genre)."),
           "distance": _enum(poursuite_.DISTANCES[:3], "La distance de départ."),
       }, ["fuyard", "poursuivants", "zone"]),
       disponible=lambda s: s.poursuite is None)
def debut_poursuite(session: Session, fuyard: str, poursuivants: list, zone: str, distance: str = "proche") -> dict:
    if fuyard in poursuivants:
        raise ErreurOutil("Le fuyard ne se poursuit pas lui-même.")
    conducteur = lambda i: poursuite_.Conducteur(i, session.combattant(i), session.engin(i))  # noqa: E731
    p = poursuite_.Poursuite(conducteur(fuyard), [conducteur(i) for i in dict.fromkeys(poursuivants)], zone,
                             {i: poursuite_.DISTANCES.index(distance) for i in poursuivants})
    session.poursuite = p
    return _etat_poursuite(session) | {
        "vehicules": {c.identifiant: c.engin.nom if c.engin else "à pied" for c in [p.fuyard, *p.poursuivants]}}


def _en_combat_avec_vehicules(s: Session) -> bool:
    return s.combat is not None and bool(s.univers.vehicules)


def _engin_de(session: Session, identifiant: str) -> vehicules_.Engin:
    engin = session.engin(identifiant)
    if engin is None:
        raise ErreurOutil(f"{session.combattant(identifiant).nom} n'a pas de véhicule.")
    return engin


@outil("Tirer sur un véhicule (action simple) : sa carrosserie (les dégâts moins le blindage vont à sa structure) "
       "ou ses pneus et son moteur (difficile, sans dégâts, un cran de vitesse en moins). Pour toucher un occupant, "
       "attaquer avec un couvert partiel (lourd si le véhicule est blindé).",
       lambda s: _objet({
           "attaquant": _ids(s, "Qui tire."),
           "vehicule_de": _ids(s, "Le conducteur du véhicule visé."),
           "partie": _enum(["carrosserie", "pneus"]),
           "difficulte": _difficulte(),
       } | _tireur(s), ["attaquant", "vehicule_de"]),
       disponible=_en_combat_avec_vehicules)
def tirer_sur_vehicule(session: Session, attaquant: str, vehicule_de: str, partie: str = "carrosserie",
                       difficulte: str = "normale", tireur: str = "à pied") -> dict:
    qui = session.participant(attaquant)
    session.verifier_portee(attaquant, vehicule_de, qui.arme_en_main)
    r = session.combat_en_cours().tirer_sur_vehicule(qui, _engin_de(session, vehicule_de), partie, tireur,
                                                     DIFFICULTES[difficulte])
    resultat = {"attaquant": r.attaquant, "vehicule": r.vehicule, "partie": r.partie, "touche": r.touche,
                "etat": r.etat}
    if r.attaque:
        resultat["attaque"] = _resume(r.attaque)
    if r.degats_bruts:
        resultat |= {"degats_bruts": r.degats_bruts, "blindage": r.blindage, "structure_perdue": r.structure_perdue}
    if r.effets:
        resultat["effets"] = r.effets
    return resultat


@outil("Éperonner (action simple), au contact seulement : Pilotage contre Pilotage, ou contre l'Esquive d'un "
       "piéton. Les dégâts suivent le gabarit du véhicule ; l'attaquant en prend la moitié.",
       lambda s: _objet({"attaquant": _ids(s, "Celui qui conduit le véhicule qui éperonne."),
                         "cible": _ids(s, "Le conducteur du véhicule visé, ou le piéton.")}, ["attaquant", "cible"]),
       disponible=_en_combat_avec_vehicules)
def eperonner(session: Session, attaquant: str, cible: str) -> dict:
    p = session.poursuite
    if p and not p.issue:
        paire = {attaquant, cible}
        if p.fuyard.identifiant in paire:
            autre = (paire - {p.fuyard.identifiant}).pop()
            if autre in p.distances and p.distances[autre] != poursuite_.AU_CONTACT:
                raise ErreurOutil(f"Pour éperonner, il faut être au contact (distance : {p.distance(autre)}).")
    r = session.combat_en_cours().eperonner(session.participant(attaquant), _engin_de(session, attaquant),
                                            session.participant(cible), session.engin(cible))
    resultat = {"attaquant": r.attaquant, "cible": r.cible, "attaque": _resume(r.attaque),
                "defense": _resume(r.defense), "touche": r.touche}
    if r.touche:
        resultat |= {"degats": r.degats, "recul": r.recul}
        if r.structure_cible is not None:
            resultat["structure_cible"] = r.structure_cible
        if r.blessure:
            b = r.blessure
            resultat |= {"pv": b.pv_apres, "blessure_grave": b.blessure_grave, "etat": b.etat.value}
    if r.effets:
        resultat["effets"] = r.effets
    return resultat


def _armes_montees(s: Session) -> list[str]:
    return sorted({m["arme"] for v in s.univers.vehicules for m in v.armes_montees})


@outil("Tirer avec une arme montée sur un véhicule (action simple), sans malus : elle est stabilisée. Une arme "
       "de zone montée (lance-grenades, roquettes) touche toute la zone, comme attaquer_zone.",
       lambda s: _objet({
           "attaquant": _ids(s, "Qui tire (un passager, ou le conducteur avec un pilote automatique)."),
           "vehicule_de": _ids(s, "Le conducteur du véhicule qui porte l'arme."),
           "arme": _enum(_armes_montees(s)),
           "cible": _ids(s, "Pour une arme ordinaire : qui est visé."),
           "cibles": _liste_ids(s, "Pour une arme de zone : tous ceux qui sont dans la zone."),
           "couvert": _enum(COUVERTS, "Le couvert de la cible."),
       }, ["attaquant", "vehicule_de", "arme"]),
       disponible=lambda s: _en_combat_avec_vehicules(s) and bool(_armes_montees(s)))
def tirer_arme_montee(session: Session, attaquant: str, vehicule_de: str, arme: str, cible: str | None = None,
                      cibles: list = (), couvert: str = "aucun") -> dict:
    engin = _engin_de(session, vehicule_de)
    if all(m["arme"] != arme for m in engin.modele.armes_montees):
        montees = ", ".join(m["arme"] for m in engin.modele.armes_montees) or "aucune"
        raise ErreurOutil(f"{engin.nom} ne porte pas de {arme} (armes montées : {montees}).")
    qui = session.participant(attaquant)
    montee = session.univers.arme(arme)
    en_main = qui.arme
    qui.arme = montee
    if montee not in qui.munitions:
        qui._charger(montee)
    try:
        c = session.combat_en_cours()
        if montee.zone:
            r = c.attaquer_zone(qui, [session.participant(x) for x in cibles], tireur="tourelle")
            return _rapport_zone(r)
        if cible is None:
            raise ErreurOutil("Précise la cible.")
        session.verifier_portee(attaquant, cible, montee)
        return _rapport_attaque(c.attaquer(qui, session.participant(cible), couvert=COUVERTS[couvert],
                                           tireur="tourelle"))
    finally:
        qui.arme = en_main


@outil("Déclencher les lance-fumigènes d'un véhicule (action mineure, une fois par scène) : un écran de fumée, "
       "couvert lourd (−40) pendant 3 rounds. Les leurres et le blindage IEM jouent tout seuls.",
       lambda s: _objet({"qui": _ids(s, "Le conducteur du véhicule.")}, ["qui"]),
       disponible=lambda s: _en_combat_avec_vehicules(s)
       and any(v.a(vehicules_.LANCE_FUMIGENES) for v in s.univers.vehicules))
def lance_fumigenes(session: Session, qui: str) -> dict:
    c = session.combat_en_cours()
    engin = _engin_de(session, qui)
    engin.utiliser(vehicules_.LANCE_FUMIGENES)
    c._agir(session.participant(qui), TypeAction.MINEURE)
    c.fumee = combat_.ROUNDS_FUMEE
    return {"vehicule": engin.nom, "fumee_rounds": c.fumee}


def _drones(s: Session) -> list[str]:
    return [v.nom for v in s.univers.vehicules if v.drone]


@outil("Lancer un drone : il devient un combattant, avec un identifiant. Autonome, il agit à son tour avec un "
       "score de 40 ; télépiloté, il agit avec l'action simple de son opérateur et son Pilotage (un seul drone par "
       "opérateur). Une IEM le grille, sauf blindage.",
       lambda s: _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple drone_1."},
           "modele": _enum(_drones(s)),
           "camp": _enum(["ennemis", "allies", "neutres"]),
           "operateur": _ids(s, "Pour un drone télépiloté : qui le pilote. Sans opérateur, il est autonome."),
       }, ["identifiant", "modele", "camp"]),
       disponible=lambda s: bool(_drones(s)))
def lancer_drone(session: Session, identifiant: str, modele: str, camp: str, operateur: str | None = None) -> dict:
    if identifiant == JOUEUR or identifiant in session.pnj:
        raise ErreurOutil(f"L'identifiant « {identifiant} » est déjà pris.")
    u = session.univers
    vehicule = u.vehicule(modele)
    if not vehicule.drone:
        raise ErreurOutil(f"{modele} n'est pas un drone.")
    op = session.combattant(operateur) if operateur else None
    if op and any(c.operateur is op and c.conscient for c in session.pnj.values()):
        raise ErreurOutil(f"{op.nom} pilote déjà un drone : un seul à la fois.")
    nom_arme = vehicule.arme_integree or next((m["arme"] for m in vehicule.armes_montees), None)
    arme = next((a for a in u.armes if a.nom == nom_arme), None)
    drone = combattant_drone(vehicules_.Engin(vehicule), camp, arme, op)
    session.pnj[identifiant] = drone
    if session.combat:
        session.combat.rejoindre(drone)
    return {"pnj": identifiant, "drone": modele, "mode": f"télépiloté par {op.nom}" if op else "autonome",
            **_etat_combattant(drone)}


def _rapport_round(r: poursuite_.RapportRound, session: Session) -> dict:
    resultat = {"round": r.round, "zone": r.zone, "evenement": r.evenement.value}
    if r.obstacles:
        resultat["obstacles"] = [{"qui": o.qui, **_resume(o.test), "effet": o.effet} for o in r.obstacles]
    duels = []
    for d in r.duels:
        duel = {"poursuivant": d.poursuivant, "gagnant": d.gagnant, "crans": d.crans, "distance": d.distance}
        if d.fuyard_test:
            duel |= {"fuyard": _resume(d.fuyard_test), "jet_poursuivant": _resume(d.poursuivant_test)}
        if d.effets:
            duel["effets"] = d.effets
        duels.append(duel)
    if duels:
        resultat["duels"] = duels
    if r.accidents:
        resultat["accidents"] = [_rapport_accident(a) for a in r.accidents]
    if r.effets:
        resultat["effets"] = r.effets
    if r.nouvelle_zone:
        resultat["nouvelle_zone"] = r.nouvelle_zone
    resultat["distances"] = _etat_poursuite(session)["distances"]
    if r.issue:
        resultat["issue"] = r.issue
    return resultat


@outil("Un round de poursuite : le moteur tire l'événement de la route, fait passer les obstacles, lance les jets "
       "opposés de Pilotage et déplace les distances. Au contact, on peut se battre ; semé, c'est fini.",
       lambda s: _objet({
           "difficulte": _enum(DIFFICULTES, "Le terrain, la même pour tous."),
           "nitro": {"type": "array", "items": _enum(s.ids()), "description": "Ceux qui allument leur nitro."},
           "raccourci": {"type": "boolean", "description": "Le fuyard tente le raccourci s'il se présente."},
           "vers_zone": _enum(poursuite_.ZONES, "Sur une réussite majeure, le fuyard entraîne la poursuite là "
                                                "(une zone voisine)."),
           "abandons": {"type": "array", "items": _enum(s.ids()),
                        "description": "Les poursuivants qui renoncent (blessés, à court de carburant…)."},
       }),
       disponible=lambda s: s.poursuite is not None)
def round_poursuite(session: Session, difficulte: str = "normale", nitro: list = (), raccourci: bool = False,
                    vers_zone: str | None = None, abandons: list = ()) -> dict:
    p = session.poursuite
    if p is None:
        raise ErreurOutil("Aucune poursuite en cours : appelle d'abord debut_poursuite.")
    for i in abandons:
        p.abandonner(i)
    if p.issue:
        return _etat_poursuite(session)
    r = p.jouer_round(session.des, DIFFICULTES[difficulte], set(nitro), raccourci, vers_zone, session.blesser)
    return _rapport_round(r, session)


@outil("Finir la poursuite (semé, rattrapé, ou le combat commence).", lambda s: _objet({}),
       disponible=lambda s: s.poursuite is not None)
def fin_poursuite(session: Session) -> dict:
    if session.poursuite is None:
        raise ErreurOutil("Aucune poursuite en cours.")
    etat = _etat_poursuite(session)
    session.poursuite = None
    return etat


def _rapport_sort(r: magie.RapportSort) -> dict:
    s = r.sort
    resultat = {"lanceur": r.lanceur, "sort": s.nom, "effet": s.effet.value, "puissance": s.puissance.value,
                "test": _resume(r.test), "pm_depenses": r.pm_depenses, "pm_restants": r.pm_restants}
    if r.pv_puises:
        resultat["pv_puises"] = r.pv_puises
    if r.sm_perdue:
        resultat["sm_perdue"] = r.sm_perdue
    cibles = []
    for c in r.cibles:
        if c.attaque:
            cible = _rapport_attaque(c.attaque).get("touche", {"qui": c.qui, "degats": 0})
            if c.effet:
                cible["effet"] = c.effet
        elif s.effet is magie.Effet.SOIN:
            cible = {"qui": c.qui, "pv_gagnes": c.gain}
        elif c.effet:
            cible = {"qui": c.qui, "effet": c.effet}
        else:
            continue
        cibles.append(cible)
    if cibles:
        resultat["cibles"] = cibles
    if r.retour:
        resultat["retour"] = r.retour
    if s.effet is magie.Effet.UTILITAIRE and r.test.reussi:
        resultat["consigne"] = (f"Raconte {magie.AMPLEUR[s.puissance]}, et seulement ce que permet « {s.nom} » : "
                                "aucun bonus chiffré.")
    return resultat


@outil("Lancer un sort (en combat : une action simple). Seulement un sort que le lanceur connaît, sorts appris ou "
       "improvisations : le moteur lance le jet de Magie, fait payer les PM (ou des PV s'il en manque) et applique "
       "l'effet. Une attaque se lance en combat ; un sort de zone peut viser une deuxième cible.",
       lambda s: _objet({
           "lanceur": _ids(s, "Qui lance le sort."),
           "sort": _enum(sorted({n for c in [s.joueur, *s.pnj.values()] for n in s.sorts_connus(c)}) or ["aucun"]),
           "cible": _ids(s, "Qui le sort vise (le lanceur lui-même pour se soigner ou se protéger)."),
           "cible2": _ids(s, "Seulement pour un sort de zone : la deuxième cible."),
           "couvert": _enum(COUVERTS, "Pour une attaque : le couvert de la cible (partiel −20, lourd −40)."),
       }, ["lanceur", "sort"]),
       disponible=lambda s: s.a_la_magie)
def lancer_sort(session: Session, lanceur: str, sort: str, cible: str | None = None, cible2: str | None = None,
                couvert: str = "aucun") -> dict:
    trouver = session.participant if session.combat else session.combattant
    qui = trouver(lanceur)
    connus = session.sorts_connus(qui)
    if sort not in connus:
        raise ErreurOutil(f"{qui.nom} ne connaît pas le sort « {sort} ». Ses sorts : {', '.join(sorted(connus))}."
                          if connus else f"{qui.nom} ne connaît aucun sort.")
    cibles = [trouver(i) for i in (cible, cible2) if i]
    r = magie.lancer(session.des, qui, connus[sort], cibles, session.combat, COUVERTS[couvert], session.moment,
                     coute_sm=session.univers.genre == "Horreur")
    return _rapport_sort(r)


@outil("Poser un implant au joueur, hors combat : le charcudoc (un PNJ, ou le joueur lui-même) fait un jet de "
       "Médecine ou de Cybernétique. Réussi, l'implant est posé et la Santé mentale maximum baisse de son prix. "
       "Les options demandent leur fondation (pas de lames-mantis sans bras cybernétique).",
       lambda s: _objet({
           "implant": _enum([i.nom for i in s.univers.implants]),
           "charcudoc": _ids(s, "Qui pose l'implant."),
           "cote": _enum(implants_.COTES, "Pour un bras ou une main : quel côté."),
           "qualite": _enum(["d'origine", "usé"], "Usé : d'occasion ou du marché noir, il coûte 2 points de plus."),
           "clandestine": {"type": "boolean", "description": "Une clinique clandestine : la pose coûte un palier de moins."},
           "offert": {"type": "boolean", "description": "Vrai si l'implant et la pose sont une récompense : rien à payer."},
       }, ["implant", "charcudoc"]),
       disponible=lambda s: bool(s.univers.implants))
def poser_implant(session: Session, implant: str, charcudoc: str, cote: str | None = None,
                  qualite: str = "d'origine", clandestine: bool = False, offert: bool = False) -> dict:
    if session.combat:
        raise ErreurOutil("On ne pose pas d'implant en plein combat.")
    if not offert:
        _exiger_un_lieu(session, lieux_.IMPLANTS)
    fiche, paye = session.univers.implant(implant), {}
    if session.inventaire and not offert:
        # L'implant et sa pose se paient avant le jet (REGLES.md 13.7) : on paie l'acte, pas le résultat
        if economie.disponibilite(fiche, session.univers) == economie.MILITAIRE:
            raise ErreurOutil(f"« {implant} » est un implant militaire : il ne s'achète pas. On le gagne ou on le trouve.")
        prix_implant = economie.decaler(economie.prix(fiche, session.univers), -1 if qualite == "usé" else 0)
        somme = prix_implant + commerce.prix_de_pose(fiche, clandestine)
        if session.personnage.argent < somme:
            raise ErreurOutil(f"Pas assez d'argent : l'implant et sa pose coûtent "
                              f"{economie.montant(somme, session.univers.monnaie)}.")
    r = implants_.poser(session.des, session.combattant(charcudoc).fiche, session.personnage, session.corps(),
                        fiche, qualite, cote)
    if session.inventaire and not offert:
        session.personnage.argent -= somme
        paye = {"prix": somme, "argent": session.personnage.argent, "monnaie": session.univers.monnaie}
    session.equiper_implants()
    return {"implant": implant, **_resume(r.test), "pose": r.pose, "sm_max_perdue": r.sm_max_perdue,
            "sm_max": session.personnage.sm_max, "sante_mentale": session.personnage.sm, **paye}


@outil("Stabiliser un combattant mourant avec un jet de Médecine (action simple).",
       lambda s: _objet({"soigneur": _ids(s, "Qui soigne."), "mourant": _ids(s, "Qui est mourant.")},
                        ["soigneur", "mourant"]))
def stabiliser(session: Session, soigneur: str, mourant: str) -> dict:
    r = session.combat_en_cours().stabiliser(session.participant(soigneur), session.participant(mourant))
    return {**_resume(r), "etat": session.combattant(mourant).fiche.etat.value}


# --- L'argent : acheter, vendre, payer (REGLES.md 13) ----------------------------------------------------

def _avec_economie(session: Session) -> bool:
    return session.inventaire is not None


def _regles_du_lieu(session: Session) -> dict:
    """Ce que le quartier où se trouve le joueur change au commerce (REGLES.md 14.5 à 14.7). Sans monde : rien."""
    if session.monde is None:
        return {"refus": None, "sans_receleur": False, "neuf": 0, "services": 0, "amical": False}
    regles = monde_.commerce(session.monde)
    if regles["refus"]:
        raise ErreurOutil(regles["refus"])
    return regles


def _exiger_un_lieu(session: Session, besoin: str):
    """Dans une campagne qui a ses lieux, on n'achète et on ne se soigne que là où un lieu le permet
    (REGLES.md 15.4)."""
    if lieux_.actifs(session.monde):
        lieux_.exiger(session.monde, besoin)


def _decalage(session: Session, categorie: str) -> int:
    return monde_.decalage(session.monde, categorie) if session.monde is not None else 0


def _echeances_du_joueur(session: Session):
    loge = session.monde is not None and monde_.loge(session.monde)
    return economie.passer_les_echeances(session.personnage, session.moment.jour, loge)


def _au_calme(session: Session) -> bool:
    """Hors combat et hors poursuite : le MJ ne voit les outils du commerce que là où ils servent (en combat,
    il lui reste l'inventaire, la fouille et la prise)."""
    en_poursuite = session.poursuite is not None and not session.poursuite.issue
    return _avec_economie(session) and session.combat is None and not en_poursuite


def _marchandage(session: Session, marchander: str, attitude: str):
    """Le test de marchandage demandé, ou None. « menace » : par l'Intimidation."""
    if marchander == "non":
        return None
    competence = commerce.INTIMIDATION if marchander == "menace" else commerce.PERSUASION
    m = commerce.marchander(session.des, session.joueur.valeur(competence), attitude, competence)
    progression.cocher(session.personnage, competence, m.test)
    return m


def _rapport_marchandage(m) -> dict:
    if m is None:
        return {}
    return {"marchandage": _resume(m.test)} | (
        {"attitude": "le vendeur lui en veut : baisse son attitude d'un cran (noter_pnj)"} if m.attitude_baisse else {})


_MARCHANDER = {"type": "string", "enum": ["non", "persuasion", "menace"],
               "description": "Marchander : un seul test par transaction. Par la menace, le PNJ lui en voudra."}
_ATTITUDE = {"type": "string", "enum": list(commerce.ATTITUDES), "description": "L'attitude du vendeur envers lui."}


@outil("Montrer ce qu'un vendeur propose cette semaine, en plus du matériel courant (toujours disponible en "
       "ville, au prix) : ses occasions, ou, pour un contact du marché noir, ses objets restreints. Le moteur "
       "tire le stock ; il se renouvelle tous les 7 jours.",
       lambda s: _objet({
           "vendeur": {"type": "string", "description": "Son identifiant (le même d'une visite à l'autre)."},
           "marche_noir": {"type": "boolean", "description": "Vrai pour un contact du marché noir."},
       }, ["vendeur"]),
       disponible=_au_calme)
def voir_boutique(session: Session, vendeur: str, marche_noir: bool = False) -> dict:
    if _regles_du_lieu(session)["sans_receleur"] and marche_noir:
        raise ErreurOutil("Les autorités tiennent ce quartier : pas de marché noir ici.")
    lignes = commerce.stock(session.univers, vendeur, session.moment.jour, marche_noir)
    return {"vendeur": vendeur, "stock": lignes, "argent": session.personnage.argent,
            "rappel": "Le matériel restreint hors de ce stock se commande (commander)." if marche_noir else
                      "Tout le matériel courant de l'univers se vend aussi ici, au prix (acheter, état « neuf »)."}


@outil("Acheter un objet pour le joueur : le moteur vérifie qu'il se vend, que l'argent et la place suffisent, "
       "débite et range l'objet. État « neuf » pour le matériel courant ; « occasion », « marque » ou « marché "
       "noir » pour un objet du stock d'un vendeur (voir_boutique). Le matériel militaire ne se vend pas.",
       lambda s: _objet({
           "objet": _enum(commerce.catalogue(s.univers, s.inventaire)),
           "etat": _enum([commerce.NEUF, commerce.OCCASION, commerce.MARQUE, commerce.MARCHE_NOIR]),
           "vendeur": {"type": "string", "description": "Pour un objet de stock : l'identifiant du vendeur."},
           "marchander": _MARCHANDER, "attitude": _ATTITUDE,
       }, ["objet"]),
       disponible=_au_calme)
def acheter(session: Session, objet: str, etat: str = commerce.NEUF, vendeur: str = "", marchander: str = "non",
            attitude: str = "neutre") -> dict:
    if session.combat:
        raise ErreurOutil("On n'achète rien en plein combat.")
    lieu = _regles_du_lieu(session)
    if etat == commerce.MARCHE_NOIR and lieu["sans_receleur"]:
        raise ErreurOutil("Les autorités tiennent ce quartier : pas de marché noir ici.")
    if etat != commerce.NEUF:
        en_stock = commerce.stock(session.univers, vendeur, session.moment.jour, etat == commerce.MARCHE_NOIR)
        if not any(ligne["objet"] == objet and ligne["etat"] == etat for ligne in en_stock):
            raise ErreurOutil(f"« {objet} » ({etat}) n'est pas dans le stock de « {vendeur} » cette semaine : "
                              f"{[ligne['objet'] for ligne in en_stock]}.")
    famille = commerce.article(session.univers, objet).famille
    if etat != commerce.MARCHE_NOIR:  # le marché noir passe par un contact, pas par une boutique
        _exiger_un_lieu(session, lieux_.ARMES if famille in commerce.CATEGORIES_DE_PRIX else lieux_.MATERIEL)
    decalage = (lieu["neuf"] if etat == commerce.NEUF else 0) + _decalage(
        session, commerce.CATEGORIES_DE_PRIX.get(famille, "tout"))
    m = _marchandage(session, marchander, "amical" if lieu["amical"] else attitude)
    a = commerce.acheter(session.personnage, session.inventaire, session.univers, objet, etat, m, decalage)
    session.charger_les_armes()
    if a.refuse:
        return {"objet": objet, "achete": False, "raison": "le vendeur se braque : il ne vendra rien aujourd'hui",
                **_rapport_marchandage(m)}
    return {"objet": objet, "achete": True, "prix": a.prix, "argent": a.argent, "monnaie": session.univers.monnaie,
            **({"geste": a.geste} if a.geste else {}), **_rapport_marchandage(m),
            "emplacements": session.inventaire.resume()["emplacements"]}


@outil("Vendre un objet du joueur à un receleur, deux paliers sous sa valeur. Le matériel militaire, ou marqué "
       "par une police ou une corporation, ne se vend que par un contact.",
       lambda s: _objet({
           "objet": _enum(s.inventaire.noms()),
           "par_un_contact": {"type": "boolean"},
           "marchander": _MARCHANDER, "attitude": _ATTITUDE,
       }, ["objet"]),
       disponible=_au_calme)
def vendre(session: Session, objet: str, par_un_contact: bool = False, marchander: str = "non",
           attitude: str = "neutre") -> dict:
    if session.combat:
        raise ErreurOutil("On ne vend rien en plein combat.")
    lieu = _regles_du_lieu(session)
    if lieu["sans_receleur"] and not par_un_contact:
        raise ErreurOutil("Les autorités tiennent ce quartier : pas de receleur ici. Il lui faut un contact, ou "
                          "un autre quartier.")
    if session.joueur.arme is not None and session.joueur.arme.nom == objet:
        session.joueur.arme = None
    m = _marchandage(session, marchander, "amical" if lieu["amical"] else attitude)
    v = commerce.vendre(session.personnage, session.inventaire, session.univers, objet, par_un_contact, m)
    if v.refuse:
        return {"objet": objet, "vendu": False, "raison": "le receleur se braque : il n'achètera rien aujourd'hui",
                **_rapport_marchandage(m)}
    return {"objet": objet, "vendu": True, "prix": v.prix, "argent": v.argent, "monnaie": session.univers.monnaie,
            **_rapport_marchandage(m)}


@outil("Faire payer un service au joueur : un service de la liste, ou, pour une information ou un pot-de-vin, "
       "un palier de prix. Une soirée de détente rend aussi de la Santé mentale (une fois par semaine). On paie "
       "l'acte, pas le résultat : le soin ou la thérapie se jouent ensuite avec leurs outils.",
       lambda s: _objet({
           "service": _enum([*commerce.SERVICES, "une information", "un pot-de-vin"]),
           "palier": {"type": "integer", "enum": list(commerce.PALIERS_LIBRES),
                      "description": "Pour une information ou un pot-de-vin seulement."},
       }, ["service"]),
       disponible=_au_calme)
def payer(session: Session, service: str, palier: int | None = None) -> dict:
    p, monnaie = session.personnage, session.univers.monnaie
    if service == commerce.DETENTE:
        gain = commerce.se_detendre(session.des, p, session.moment.jour)
        return {"service": service, "prix": commerce.SERVICES[service], "argent": p.argent, "monnaie": monnaie,
                "sm_gagnee": gain, "sante_mentale": p.sm}
    if service in commerce.SERVICES:
        # Le lieu et les événements déplacent le prix d'un service ; pas celui d'un pot-de-vin, que le MJ choisit
        lieu = _regles_du_lieu(session)
        if service in commerce.SOINS:
            _exiger_un_lieu(session, lieux_.SOINS)
        categorie = "soins" if service in commerce.SOINS else "services"
        somme = economie.decaler(commerce.SERVICES[service], lieu["services"] + _decalage(session, categorie))
    elif palier is None:
        raise ErreurOutil(f"Pour {service}, choisis un palier : {list(commerce.PALIERS_LIBRES)}.")
    else:
        somme = palier
    commerce.payer(p, somme, monnaie)
    return {"service": service, "prix": somme, "argent": p.argent, "monnaie": monnaie}


@outil("Commander un objet restreint par un contact : un test de Persuasion (difficulté selon le lieu), un délai "
       "de 1 à 3 jours, un palier au-dessus du prix. La somme est payée à la commande, et l'objet arrive tout "
       "seul le jour dit.",
       lambda s: _objet({
           "objet": _enum(commerce.catalogue(s.univers, s.inventaire)),
           "lieu": _enum(commerce.LIEUX),
       }, ["objet", "lieu"]),
       disponible=_au_calme)
def commander(session: Session, objet: str, lieu: str) -> dict:
    c = commerce.commander(session.des, session.personnage, session.univers, objet,
                           session.joueur.valeur(commerce.PERSUASION), lieu, session.moment.jour)
    progression.cocher(session.personnage, commerce.PERSUASION, c.test)
    if not c.passee:
        return {"objet": objet, "commande": False, **_test(c.test), "raison": "le contact ne peut pas l'obtenir"}
    return {"objet": objet, "commande": True, **_test(c.test), "prix": c.prix, "arrive": f"jour {c.jour}",
            "argent": session.personnage.argent, "monnaie": session.univers.monnaie}


@outil("Changer le niveau de vie du joueur (à la rue, modeste, confortable). Le nouveau tarif vaut à "
       "l'échéance suivante ; « payer_maintenant » règle tout de suite une semaine, pour quitter la rue.",
       lambda s: _objet({
           "niveau": _enum([n.value for n in economie.NiveauDeVie]),
           "payer_maintenant": {"type": "boolean"},
           "lien_a_charge": {"type": "boolean", "description": "Son lien dépend de lui : 200 par semaine, et le "
                                                               "temps passé avec lui rend 1d6 au lieu de 1d3."},
       }, ["niveau"]),
       disponible=_au_calme)
def niveau_de_vie(session: Session, niveau: str, payer_maintenant: bool = False,
                  lien_a_charge: bool | None = None) -> dict:
    p = session.personnage
    if lien_a_charge is not None:
        p.lien_a_charge, p.charge_payee = lien_a_charge, True
    economie.changer_niveau_de_vie(p, economie.NiveauDeVie(niveau))
    if payer_maintenant and not economie.payer_la_semaine(p):
        raise ErreurOutil(f"Pas assez d'argent pour une semaine en « {niveau} ».")
    return {"niveau_de_vie": economie.niveau_effectif(p).value, "choisi": niveau, "argent": p.argent,
            "prochaine_echeance": f"jour {p.echeance}", "lien_a_charge": p.lien_a_charge,
            "visage": session.univers.niveaux_de_vie.get(niveau, niveau)}


# --- Gagner : les missions, le métier, les dettes, le butin (REGLES.md 13.6 et 13.8) ---------------------

@outil("Ouvrir une mission payée : un fil de l'histoire avec sa récompense, que le moteur fixe d'après le danger "
       "et versera à la clôture du fil si la mission est réussie. Le joueur peut marchander : un seul test.",
       lambda s: _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple extraction_tanaka."},
           "fil": {"type": "string", "description": "La mission en une phrase : qui la donne, ce qu'il faut faire."},
           "danger": _enum(gains.RECOMPENSES),
           "marchander": _MARCHANDER, "attitude": _ATTITUDE,
       }, ["identifiant", "fil", "danger"]),
       disponible=_au_calme)
def ouvrir_mission(session: Session, identifiant: str, fil: str, danger: str, marchander: str = "non",
                   attitude: str = "neutre") -> dict:
    texte = session.memoire.ouvrir_fil(identifiant, fil).texte  # refuse un identifiant déjà pris, avant tout test
    m = _marchandage(session, marchander, attitude)
    mission = gains.ouvrir_mission(session.personnage, identifiant, danger, m)
    return {"mission": identifiant, "texte": texte, "recompense": mission.recompense, "avance": mission.avance,
            "argent": session.personnage.argent, "monnaie": session.univers.monnaie, **_rapport_marchandage(m),
            "rappel": "La récompense sera versée par clore_fil, avec reussie à vrai."}


@outil("Fouiller un adversaire vaincu ou une cache. Le moteur tire ce qu'on y trouve : l'argent va tout de suite "
       "dans la poche du joueur, les objets attendent qu'il les prenne (prendre). Un corps ne se fouille qu'une "
       "fois. En combat, on ne fouille pas : on ramasse seulement l'arme d'un adversaire à terre (action mineure).",
       lambda s: _objet({
           "cible": _enum(sorted(s.pnj) + ["cache"], "Un PNJ vaincu, ou « cache »."),
           "taille": _enum(gains.CACHES, "Pour une cache : sa taille."),
           "materiel_marque": {"type": "boolean", "description": "Vrai pour du matériel de police ou de corporation : "
                                                                 "traçable, il ne se revend que par un contact."},
       }, ["cible"]),
       disponible=_avec_economie)
def fouiller(session: Session, cible: str, taille: str | None = None, materiel_marque: bool = False) -> dict:
    p, u = session.personnage, session.univers
    if cible == "cache":
        if session.combat:
            raise ErreurOutil("On ne fouille pas une cache en plein combat.")
        if taille is None:
            raise ErreurOutil(f"Pour une cache, précise sa taille : {list(gains.CACHES)}.")
        videe = monde_.raison(session.monde, monde_.CACHES_VIDEES) if session.monde is not None else None
        if videe:  # une cache n'est vide que si un événement a touché son lieu (REGLES.md 13.8)
            return {"cible": "cache", "vide": True, "raison": videe, "argent_trouve": 0, "objets": []}
        butin = gains.fouiller_une_cache(session.des, u, taille)
        origine = f"cache_{len(session.trouvailles) + 1}"
    else:
        pnj = session.combattant(cible)
        if pnj.fiche.etat in (Etat.ACTIF,) and not pnj.surpris:
            raise ErreurOutil(f"{pnj.nom} est debout et conscient : on ne le fouille pas.")
        if cible in session.fouilles:
            raise ErreurOutil(f"{pnj.nom} a déjà été fouillé.")
        restants = len(pnj.reserve.chargeurs_restants) if isinstance(pnj.reserve, ReservePnj) else None
        butin = gains.fouiller_un_corps(session.des, u, pnj.fiche.combat, pnj.arme, pnj.armure,
                                        pnj.munitions_restantes() or 0, restants, materiel_marque)
        origine = cible
        if session.combat:  # sous le feu : son arme seulement, et rien d'autre
            session.combat._agir(session.joueur, TypeAction.MINEURE)
            butin = gains.Butin(0, [o for o in butin.objets if o["famille"] == inventaire_.ARME][:1], butin.menace)
            pnj.arme = None  # son arme est ramassée : on ne la retrouvera pas en le fouillant après le combat
        else:
            session.fouilles.add(cible)
    p.argent += butin.argent
    session.trouvailles[origine] = butin.objets
    return {"cible": cible, "argent_trouve": butin.argent, "argent": p.argent, "monnaie": u.monnaie,
            "objets": [_trouvaille(o) for o in butin.objets], "origine": origine,
            **({"menace": butin.menace} if butin.menace else {}),
            "rappel": "Le joueur choisit ce qu'il emporte : prendre, avec cette origine."}


def _trouvaille(o: dict) -> str:
    details = [o["qualite"]] if o.get("qualite") else []
    if "charge" in o:
        details.append(f"{o['charge']} cartouches dans l'arme")
    if o.get("chargeurs"):
        details.append(f"{o['chargeurs']} chargeur(s) de rechange")
    if o.get("marque"):
        details.append("marqué")
    return o["nom"] + (f" ({', '.join(details)})" if details else "")


@outil("Prendre un objet trouvé en fouillant : il entre dans l'inventaire du joueur, s'il a la place.",
       lambda s: _objet({
           "origine": _enum(sorted(s.trouvailles) or ["aucune"], "La fouille d'où il vient."),
           "objet": _enum(sorted({o["nom"] for objets in s.trouvailles.values() for o in objets}) or ["aucun"]),
       }, ["origine", "objet"]),
       disponible=lambda s: _avec_economie(s) and any(s.trouvailles.values()))
def prendre(session: Session, origine: str, objet: str) -> dict:
    trouves = session.trouvailles.get(origine, [])
    choisi = next((o for o in trouves if o["nom"] == objet), None)
    if choisi is None:
        raise ErreurOutil(f"« {objet} » n'est pas dans « {origine} » : {[o['nom'] for o in trouves]}.")
    gains.prendre(session.inventaire, session.univers, choisi)
    trouves.remove(choisi)
    session.charger_les_armes()
    return {"pris": _trouvaille(choisi), **session.inventaire.resume()}


@outil("Faire passer au joueur une semaine entière à exercer son métier, sans aventure : un test de sa "
       "compétence de métier donne le revenu de la semaine (parfois rien). La semaine passe pour de bon : le "
       "coût de la vie est débité, il se repose.",
       lambda s: _objet({}),
       disponible=_au_calme)
def semaine_de_travail(session: Session) -> dict:
    if session.combat or session.poursuite:
        raise ErreurOutil("Pas en plein combat ni en pleine poursuite.")
    p, u = session.personnage, session.univers
    competence = u.parcours[p.parcours][0]
    r = gains.travailler(session.des, p, competence, u.rangs.get(p.parcours, economie.RANG_PAR_DEFAUT))
    progression.cocher(p, competence, r.test)
    session.moment = Moment(session.moment.jour + economie.SEMAINE, session.moment.periode)
    session.oublier_les_effets()
    echeances = _echeances_du_joueur(session)
    if p.etat is Etat.ACTIF and not economie.a_la_rue(p):
        p.pv = p.pv_max if not p.blessure_grave else p.pv
    resultat = {"competence": u.nom_affiche(competence), **_resume(r.test), "revenu": r.revenu, "argent": p.argent,
                "monnaie": u.monnaie, "moment": str(session.moment), "echeances": _echeances(echeances)}
    if r.ennui:
        resultat["ennui"] = "une maladresse : raconte l'ennui que ce travail lui vaut (un client mécontent, une dette)"
    if session.personnage.commandes:
        arrivees = commerce.livrer_les_commandes(p, session.inventaire, u, session.moment.jour)
        if arrivees:
            session.charger_les_armes()
            resultat["commandes_arrivees"] = arrivees
    return resultat


@outil("Faire emprunter de l'argent au joueur auprès d'un usurier ou d'un fixer : un palier, jusqu'à 5 000. Il "
       "rembourse un dixième de la somme par semaine pendant 12 semaines ; le moteur débite l'échéance avant le "
       "loyer et te prévient quand une échéance est manquée.",
       lambda s: _objet({
           "creancier": {"type": "string", "description": "Son identifiant de PNJ, par exemple usurier_tanaka."},
           "somme": {"type": "integer", "enum": list(gains.SOMMES_EMPRUNTABLES)},
       }, ["creancier", "somme"]),
       disponible=_au_calme)
def emprunter(session: Session, creancier: str, somme: int) -> dict:
    dette = gains.emprunter(session.personnage, creancier, somme)
    return {"creancier": creancier, "somme": somme, "echeance_par_semaine": dette["echeance"],
            "total_a_rembourser": dette["reste"], "argent": session.personnage.argent,
            "monnaie": session.univers.monnaie}


# --- Le monde : la carte, les mêlées, la réputation (REGLES.md 14.3 à 14.6) ------------------------------

def _avec_monde(session: Session) -> bool:
    return session.monde is not None and session.combat is None


MENACES_DE_FACTION = {  # ce que valent les hommes d'une faction dans une mêlée : combat, PV
    monde_.GANG: (50, 12), monde_.CORPORATION: (65, 14), monde_.AUTORITES: (60, 14), monde_.SYNDICAT: (50, 12),
    monde_.MILICE: (55, 12)}
ADVERSAIRES_DE_MELEE = 2
BONUS_PREPARATIF = {Degre.COMPLICATION: 1, Degre.REUSSITE: 1, Degre.MAJEURE: 2, Degre.CRITIQUE: 3}
ACTES = {"un de ses hommes tué devant témoin": -1, "une trahison": -1, "un service rendu": 1}
DELAI_ENTRE_SERVICES = 7  # jours : un seul service rendu compte par faction et par semaine


@outil("Lire l'état du monde autour du joueur : le quartier où il se trouve (qui le tient, son contrôle, qui "
       "domine le district), ce que les factions pensent de lui, la mêlée annoncée s'il y en a une, et les "
       "nouvelles qu'il n'a pas encore apprises. Donne « ici » quand il a changé de quartier. Tu ne décides "
       "d'aucun de ces faits : tu les racontes.",
       lambda s: _objet({"ici": _enum(sorted(s.monde["quartiers"]), "Le quartier où le joueur se trouve maintenant.")}),
       disponible=_avec_monde)
def monde(session: Session, ici: str | None = None) -> dict:
    etat = session.monde
    avant = etat["ici"]
    if ici:
        etat["ici"] = ici
    monde_.avancer(etat, session.des, session.moment.jour)  # une mêlée peut être annoncée là où il arrive
    resultat = monde_.situation(etat)
    if meteo_.actif(etat):
        meteo_.avancer(etat, session.des, session.moment.jour)
        resultat["meteo"] = meteo_.decrire(etat, session.univers.nom_affiche)
    if lieux_.actifs(etat):
        lieux_.visiter(etat, etat["ici"])
        maitre = etat["quartiers"][etat["ici"]]["maitre"]
        indique = lieux_.reveler(etat) if monde_.reputation(etat, maitre) in (monde_.AMI, monde_.MEMBRE) else None
        resultat["lieux"] = lieux_.decrire(etat)
        resultat["consigne_lieux"] = ("Ces lieux sont ceux du quartier, avec leurs tenanciers : n'en invente aucun "
                                      "qui vende ou qui soigne. Le décor (rue, toit, appartement) reste libre.")
        if indique:
            resultat["lieu_indique"] = f"{maitre} lui indique un lieu caché du quartier : {indique['nom']}."
    ouvertes = session.offres()
    if ouvertes:
        resultat["offres_de_mission"] = [missions.resume(o) for o in ouvertes]
    en_poursuite = session.poursuite is not None and not session.poursuite.issue
    if rencontres_.actives(etat) and ici and ici != avant and not en_poursuite:
        croise = rencontres_.tirer(etat, session.des, session.moment.jour, session.moment.periode is Periode.NUIT)
        if croise:
            resultat["rencontre_de_rue"] = rencontres_.decrire(croise)
            if croise.get("offre"):  # la rumeur ouvre une vraie offre, que le moteur tire
                contacts = [p.nom for i, p in session.memoire.pnj.items() if not session.memoire.est_mort(i)]
                offre = missions.tirer_offre(etat, session.des, etat.get("prochaines_offres", session.moment.jour),
                                             session.personnage.cran, contacts)
                if offre:
                    offre["source"] = "rencontre"
                    etat.setdefault("offres", []).append(offre)
                    resultat.setdefault("offres_de_mission", []).append(missions.resume(offre))
                    resultat["rencontre_de_rue"]["offre_de_mission"] = offre["id"]
    fraiches = monde_.nouvelles(etat)
    return resultat | ({"nouvelles_du_monde": fraiches} if fraiches else {})


@outil("Faire accepter au joueur une offre de mission tirée par le moteur (voir l'outil monde). Le moteur ouvre "
       "le fil, fixe la récompense et te donne, à toi seul, le retournement s'il y en a un : ne le dis jamais au "
       "joueur, fais-le arriver dans l'histoire. La récompense sera versée par clore_fil, avec reussie. Le joueur "
       "peut marchander : un seul test.",
       lambda s: _objet({
           "offre": _enum([o["id"] for o in s.monde.get("offres", [])] or ["aucune"]),
           "marchander": _MARCHANDER, "attitude": _ATTITUDE,
       }, ["offre"]),
       disponible=lambda s: _au_calme(s) and s.monde is not None and bool(s.monde.get("offres")))
def accepter_mission(session: Session, offre: str, marchander: str = "non", attitude: str = "neutre") -> dict:
    etat = session.monde
    o = missions.offre(etat, offre)
    texte = session.memoire.ouvrir_fil(o["id"], o["texte"]).texte  # refuse un identifiant déjà pris, avant tout test
    amical = monde_.reputation(etat, o["commanditaire"]) in (monde_.AMI, monde_.MEMBRE)
    m = _marchandage(session, marchander, "amical" if amical else attitude)
    mission = gains.ouvrir_mission(session.personnage, o["id"], o["danger"], m, o.get("prime", 0))
    session.personnage.missions[o["id"]]["offre"] = missions.prendre(etat, o["id"])
    resultat = {"mission": o["id"], "texte": texte, "commanditaire": o["commanditaire"], "cible": o["cible"],
                "lieu": o["lieu"], "danger": o["danger"], "recompense": mission.recompense, "avance": mission.avance,
                "argent": session.personnage.argent, "monnaie": session.univers.monnaie, **_rapport_marchandage(m)}
    if o.get("retournement"):
        resultat["retournement_pour_toi_seul"] = o["retournement"]
    if o.get("principale"):
        resultat["mission_principale"] = "la mission finale de la campagne" if o.get("finale") else f"acte {o['acte']}"
    if o.get("finale"):
        resultat |= _preparer_la_finale(session, o)
    if o.get("touche_la_trame"):
        resultat["touche_la_trame"] = (f"Un homme {monde_.de(etat['trame']['antagoniste'])} s'en mêle, ou un indice "
                                       "traîne sur les lieux. Réussie, elle donnera un indice au joueur.")
    if o.get("camp"):
        resultat["rappel"] = f"C'est une mêlée : fais-le se battre avec l'outil melee, camp « {o['camp']} »."
    return resultat


def _arme_de_faction(session: Session):
    """Une arme de poing de l'univers ; à défaut, la première arme qui se porte."""
    armes = [a for a in session.univers.armes if not a.montee and not a.usage_unique]
    return next((a for a in armes if a.categorie == "armes de poing"), armes[0] if armes else None)


@outil("Faire participer le joueur à une mêlée annoncée. « preparer » : un seul préparatif par mêlée, un test "
       "de la compétence qui convient (barricades, guetteurs, piège, brouillage, repérage, complice, sabotage) ; "
       "réussite +1, réussite majeure +2, critique +3 au dé de son camp. « se_battre » : le moteur crée ses "
       "adversaires, joue ensuite le combat (debut_combat) ; à fin_combat, sa victoire donne +2 à son camp, sa "
       "défaite ou sa fuite −2, et la mêlée est jouée. S'il ne fait rien, les dés décident sans lui.",
       lambda s: _objet({
           "quartier": _enum(monde_.melees_annoncees(s.monde) or ["aucune"]),
           "camp": _enum([monde_.ATTAQUE, monde_.DEFENSE], "Le camp qu'il aide : l'attaquant, ou le défenseur."),
           "action": _enum(["preparer", "se_battre"]),
           "competence": _enum(sorted(s.noms_competences), "Pour preparer : la compétence testée."),
       }, ["quartier", "camp", "action"]),
       disponible=lambda s: _avec_monde(s) and bool(monde_.melees_annoncees(s.monde)))
def melee(session: Session, quartier: str, camp: str, action: str, competence: str | None = None) -> dict:
    etat = session.monde
    if session.melee:
        raise ErreurOutil("Il se bat déjà dans une mêlée : joue le combat, puis fin_combat.")
    factions = monde_.camps(etat, quartier) if quartier in etat["quartiers"] else {}
    if action == "preparer":
        if competence is None:
            raise ErreurOutil("Pour preparer, précise la compétence testée.")
        socle = session.noms_competences[competence]
        monde_._melee_du_joueur(etat, quartier, camp)  # refuse avant le test un camp déjà choisi autrement
        if "preparatif" in etat["quartiers"][quartier]["joueur"]:
            raise ErreurOutil("Un seul préparatif par mêlée : il a déjà préparé celle-ci.")
        test = tester(session.des, session.joueur.valeur(socle))
        progression.cocher(session.personnage, socle, test)
        bonus = BONUS_PREPARATIF.get(test.degre, 0)
        monde_.preparer(etat, quartier, camp, bonus)
        return {"quartier": quartier, "camp": camp, "pour": factions[camp], **_test(test), "bonus_au_de": bonus}
    monde_._melee_du_joueur(etat, quartier, camp)
    autre = factions[monde_.DEFENSE if camp == monde_.ATTAQUE else monde_.ATTAQUE]
    combat, pv = MENACES_DE_FACTION[etat["factions"][autre]["type"]]
    arme = _arme_de_faction(session)
    adversaires = []
    for _ in range(ADVERSAIRES_DE_MELEE):
        identifiant = next(f"melee_{n}" for n in range(1, 1000) if f"melee_{n}" not in session.pnj)
        fiche = FichePnj(f"Un homme {monde_.de(autre)}", combat=combat, pv_max_base=pv)
        session.pnj[identifiant] = Combattant(fiche, "ennemis", arme, None)
        if session.inventaire:
            session.pnj[identifiant].reserve = ReservePnj(arme)
        adversaires.append(identifiant)
    session.melee = {"quartier": quartier, "camp": camp, "adversaires": adversaires}
    return {"quartier": quartier, "camp": camp, "pour": factions[camp], "contre": autre, "adversaires": adversaires,
            "consigne": "Lance debut_combat avec ces adversaires. La mêlée sera jouée à fin_combat."}


def _preparer_la_finale(session: Session, offre: dict) -> dict:
    """Les atouts que le joueur a gagnés pour la mission finale (REGLES.md 14.11), et ce que valent les hommes
    de l'antagoniste. L'allié des renforts est créé tout de suite."""
    etat = session.monde
    t = etat["trame"]
    gagnes = trame_.atouts(etat, offre["lieu"])
    for atout in gagnes:
        if atout["atout"] == trame_.RENFORTS and "allie_finale" not in session.pnj:
            combat, pv = MENACES_DE_FACTION[etat["factions"][atout["faction"]]["type"]]
            arme = _arme_de_faction(session)
            fiche = FichePnj(f"Un allié {monde_.de(atout['faction'])}", combat=combat, pv_max_base=pv)
            session.pnj["allie_finale"] = Combattant(fiche, "allies", arme, None)
            if session.inventaire:
                session.pnj["allie_finale"].reserve = ReservePnj(arme)
            atout["pnj"] = "allie_finale"
    menace, combat = trame_.menace_finale(t, any(a["atout"] == trame_.FAIBLESSE for a in gagnes))
    session.personnage.missions[offre["id"]]["offre"]["atouts"] = [a["atout"] for a in gagnes]
    return {"atouts": gagnes or "aucun : il y va sans rien",
            "hommes_de_l_antagoniste": f"menace {menace} : combat {combat} (creer_pnj)"}


def _fin_de_melee(session: Session) -> dict:
    """Le joueur vient de se battre dans une mêlée : victoire s'il est debout et qu'il a mis hors de combat
    au moins la moitié de ses adversaires. La mêlée est jouée dans la foulée."""
    m, session.melee = session.melee, None
    hors_de_combat = sum(session.pnj[i].fiche.etat is not Etat.ACTIF for i in m["adversaires"] if i in session.pnj)
    victoire = session.personnage.etat is Etat.ACTIF and hors_de_combat * 2 >= len(m["adversaires"])
    monde_.se_battre(session.monde, m["quartier"], m["camp"], victoire)
    r = monde_.resoudre(session.monde, session.des, m["quartier"], session.moment.jour)
    return {"melee": {"quartier": r.quartier, "le_joueur_a_gagne_son_combat": victoire, "attaquant": r.attaquant,
                      "defenseur": r.defenseur, "vainqueur": r.vainqueur or "personne", "quartier_pris": r.pris,
                      "controle": r.controle, **({"reputation": r.reputation} if r.reputation else {})}}


@outil("Signaler un acte du joueur, hors mission, qui change ce qu'une faction pense de lui. Les missions et les "
       "mêlées changent déjà la réputation toutes seules : ne les signale pas ici.",
       lambda s: _objet({"faction": _enum(sorted(s.monde["factions"])), "acte": _enum(ACTES)}, ["faction", "acte"]),
       disponible=_avec_monde)
def reputation(session: Session, faction: str, acte: str) -> dict:
    etat, sens = session.monde, ACTES[acte]
    if sens > 0:
        services = etat.setdefault("services", {})
        if session.moment.jour - services.get(faction, -DELAI_ENTRE_SERVICES) < DELAI_ENTRE_SERVICES:
            raise ErreurOutil(f"Un service rendu {monde_.a(faction)} a déjà compté cette semaine.")
        services[faction] = session.moment.jour
    changements = monde_.bouger_reputation(etat, faction, sens)
    return {"faction": faction, "acte": acte, "reputation": monde_.reputation(etat, faction),
            "changements": changements or ["rien ne change"]}


# --- La trame : les indices et les révélations (REGLES.md 14.10) -----------------------------------------

def _avec_trame(session: Session) -> bool:
    t = trame_.trame_de(session.monde)
    return t is not None and not trame_.finie(t) and session.combat is None


@outil("Donner au joueur un indice sur le secret de la campagne. Deux cas. Le moteur vient d'en accorder un "
       "(une mission réussie) : décris-le. Ou le joueur fouille, interroge ou pirate dans une scène liée à "
       "l'antagoniste : donne la compétence, le moteur teste, une seule fois par scène. L'indice est un fait "
       "précis (un nom sur un reçu, un visage sur une vidéo) tiré de ce qu'il doit encore découvrir, sans le dire "
       "en entier. Quand le moteur renvoie une révélation, joue la scène où le personnage comprend.",
       lambda s: _objet({
           "description": {"type": "string", "description": f"L'indice, en une phrase. {trame_.INDICE_MAX} caractères "
                                                            "au plus."},
           "competence": _enum(sorted(s.noms_competences), "Pour une enquête seulement : la compétence testée."),
       }, ["description"]),
       disponible=_avec_trame)
def indice(session: Session, description: str, competence: str | None = None) -> dict:
    t = session.monde["trame"]
    trame_.texte_d_indice(description)  # refusé avant tout test : une enquête ne se perd pas sur une faute de forme
    resultat = {}
    if t["dus"] > 0:
        t["dus"] -= 1
    elif competence is None:
        raise ErreurOutil("Aucun indice n'est dû au joueur. S'il enquête dans une scène liée à l'antagoniste, donne "
                          "la compétence : le moteur teste.")
    elif t["enquete"]:
        raise ErreurOutil("Une seule enquête par scène : celle de cette scène a déjà été jouée.")
    else:
        t["enquete"] = True
        socle = session.noms_competences[competence]
        test = tester(session.des, session.joueur.valeur(socle))
        progression.cocher(session.personnage, socle, test)
        resultat = _test(test)
        if not test.reussi:
            return {"indice": None, **resultat, "consigne": "L'enquête ne donne rien : aucun indice."}
    revelations = trame_.noter_un_indice(t, session.moment.jour, description)
    resultat |= {"indice": t["indices"][-1]["texte"], "indices_trouves": len(t["indices"])}
    if revelations:
        resultat["revelation"] = revelations
    return resultat


# --- Le tour de parole et la fiche du combat ---------------------------------------------------

def _qui_joue(session: Session) -> str | None:
    qui = session.combat.au_tour_de
    return session.identifiant(qui) if qui else None


def _consigne(session: Session) -> str:
    qui, joueur = session.combat.au_tour_de, session.joueur
    if qui is None:
        return "Plus personne ne peut agir : termine le combat avec fin_combat."
    if qui is joueur:
        return ("C'est au tour du joueur : raconte ce qui vient de se passer, puis demande-lui ce qu'il fait. "
                "Ne joue pas son tour à sa place.")
    consigne = f"C'est au tour de {qui.nom} ({session.identifiant(qui)}) : joue son action, puis appelle fin_de_tour."
    if not joueur.conscient:
        consigne += (" Le joueur est hors de combat : décide ce que font les ennemis (achever, fouiller, fuir) "
                     "et termine le combat avec fin_combat dès que possible.")
    return consigne


def _ligne_combattant(c: Combattant) -> str:
    f = c.fiche
    etat = f.etat.value + (", blessure grave" if f.blessure_grave else "")
    arme = c.arme.nom if c.arme else "sans arme"
    if c.arme and c.arme.munitions:
        arme += f" ({c.munitions_restantes()} balles)"
    ligne = f"{c.nom} : {f.pv}/{f.pv_max} PV, {etat}, {arme}"
    if (isinstance(f, Personnage) and f.pm_max) or getattr(f, "sorts", None):
        ligne += f", {f.pm} PM"
    if c.effets:
        ligne += f" ; sorts : {', '.join(_effets(c))}"
    return ligne


def _puce(ligne: str) -> str:
    """Une ligne du compte rendu en puce Markdown ; ses détails (indentés) en sous-puces."""
    return f"  - {ligne.strip()}" if ligne.startswith(" ") else f"- {ligne}"


def _fiche(session: Session, historique: bool = False) -> str:
    """La fiche du combat en Markdown : l'état réel de chacun, puis ce qui s'est passé.
    Pour le MJ, le dernier round seulement ; dans combat.md, tout le combat."""
    c = session.combat
    lignes = [f"# Combat — round {c.round}", "", "Ordre d'initiative, la flèche montre qui joue :", ""]
    lignes += [f"- {'→ ' if x is c.au_tour_de else ''}{_ligne_combattant(x)}" for x in c.ordre]
    for numero, evenements in (session.rounds if historique else session.rounds[-1:]):
        lignes += ["", f"## Round {numero}", ""] + [_puce(e) for e in evenements]
    return "\n".join(lignes) + "\n"


@outil("Terminer le tour de celui qui joue : le moteur passe au suivant dans l'ordre d'initiative. Après le "
       "dernier, il clôt le round (tests des mourants) et te renvoie la fiche du combat : raconte d'après elle.",
       lambda s: _objet({"passe": {"type": "boolean",
                                   "description": "Vrai seulement si le joueur a dit qu'il ne fait rien ce tour."}}))
def fin_de_tour(session: Session, passe: bool = False) -> dict:
    c = session.combat_en_cours()
    joueur = session.joueur
    if c.au_tour_de is joueur and not passe and not any(joueur.budget.utilise.values()):
        raise ErreurOutil("Le joueur n'a encore rien fait ce tour : rends-lui la main (raconte, puis demande-lui "
                          "ce qu'il fait). S'il a dit qu'il ne fait rien, mets passe à vrai.")
    round_avant, evenements = c.round, session.evenements_du_round()
    tests = c.fin_de_tour()
    resultat = {"round": c.round, "nouveau_round": c.round != round_avant,
                "tests_des_mourants": [{"qui": nom, **_resume(t)} for nom, t in tests]}
    if c.sauvegardes:
        resultat["sauvegardes"] = [{"qui": s.qui, "sort": s.sort, **_resume(s.test), "degats": s.degats,
                                    "fini": s.fini} for s in c.sauvegardes]
        c.sauvegardes = []
    if resultat["nouveau_round"]:
        for engin in session.tous_les_engins():
            engin.coupe = max(0, engin.coupe - 1)
        session.rounds.append((round_avant, evenements + decrire("fin_de_tour", {}, resultat, session)[:-1]))
        session.debut_round = len(session.journal) + 1  # + 1 : cet appel-ci
        resultat["fiche"] = _fiche(session)
        if session.campagne:
            session.campagne.ecrire_combat(_fiche(session, historique=True))
    resultat.update(au_tour_de=_qui_joue(session), consigne=_consigne(session))
    return resultat


def _bilan(session: Session) -> list[str]:
    """Le résultat du combat, écrit par le moteur : ce sont des faits, pas du récit."""
    lignes = [_ligne_combattant(session.joueur)]
    for c in session.combat.ordre:
        if c is not session.joueur:
            pv = "" if c.fiche.etat.value == "mort" else f", {c.fiche.pv}/{c.fiche.pv_max} PV"
            lignes.append(f"{c.nom} : {c.fiche.etat.value}{pv}")
    return lignes


@outil("Terminer le combat (victoire, fuite, reddition…). Raconte ses moments forts en trois phrases au plus : "
       "le moteur les garde dans les souvenirs de la campagne, avec le résultat. Les PNJ restent connus.",
       lambda s: _objet({"moments_forts": {"type": "string",
                                           "description": "Les moments forts du combat, trois phrases au plus."}},
                        ["moments_forts"]))
def fin_combat(session: Session, moments_forts: str) -> dict:
    c = session.combat_en_cours()
    texte = _moments_forts(moments_forts, "du combat")
    evenements = session.evenements_du_round()
    if evenements:
        session.rounds.append((c.round, evenements))
    # Les PNJ connus de la mémoire gardent leur état réel : un mort ne revient pas
    for x in c.ordre:
        if x is not session.joueur:
            session.memoire.marquer_etat(session.identifiant(x), MORT if x.fiche.etat.value == MORT else VIVANT)
    adversaires = ", ".join(x.nom for x in c.ordre if x is not session.joueur)
    souvenir = (f"## {str(session.moment).capitalize()} — Combat contre {adversaires} "
                f"({c.round} round{'s' if c.round > 1 else ''})\n\n{texte}\n\n"
                + "\n".join(f"- {ligne}" for ligne in _bilan(session)) + "\n")
    # D'abord le souvenir ; la fiche n'est effacée que s'il est bien écrit
    try:
        session.memoire.ajouter_souvenir(souvenir)
    except OSError as erreur:
        raise ErreurOutil(f"Le souvenir n'a pas pu être écrit ({erreur}) : le combat reste ouvert.") from erreur
    if session.campagne:
        session.campagne.effacer_combat()
    session.combat, session.rounds = None, []
    session.oublier_les_effets()
    for combattant in [session.joueur, *session.pnj.values()]:
        combattant.surpris = combattant.vise = combattant.a_vise = combattant.sursis = False
        combattant.budget = BudgetRound()
        combattant.defenses_ce_round = 0
    resultat = {"etats": {i: session.combattant(i).fiche.etat.value for i in session.ids()}, "souvenir": souvenir}
    if session.melee and session.monde is not None:
        resultat |= _fin_de_melee(session)
    return resultat


# --- Mémoire de la campagne -------------------------------------------------------------------

def _moments_forts(texte: str, quoi: str) -> str:
    texte = texte.strip()
    if not texte:
        raise ErreurOutil(f"Raconte les moments forts {quoi}, en trois phrases au plus.")
    if len(texte) > MOMENTS_FORTS_MAX:
        raise ErreurOutil(f"Trop long ({len(texte)} caractères) : trois phrases au plus.")
    return texte


@outil("Terminer une scène qui a compté, quand le personnage quitte un lieu ou que le temps passe. "
       "Ses moments forts rejoignent les souvenirs de la campagne. Un combat se termine par fin_combat.",
       lambda s: _objet({
           "titre": {"type": "string", "description": "Quelques mots, par exemple « Chez Doc Mori »."},
           "moments_forts": {"type": "string", "description": "Ce qui s'est passé d'important, trois phrases au plus."},
       }, ["titre", "moments_forts"]))
def fin_scene(session: Session, titre: str, moments_forts: str) -> dict:
    if session.combat:
        raise ErreurOutil("Un combat est en cours : termine-le avec fin_combat.")
    titre = " ".join(titre.split())
    if not titre or len(titre) > LONGUEURS["titre"]:
        raise ErreurOutil(f"Le titre de la scène : quelques mots, {LONGUEURS['titre']} caractères au plus.")
    texte = _moments_forts(moments_forts, "de la scène")
    souvenir = f"## {str(session.moment).capitalize()} — {titre}\n\n{texte}\n"
    try:
        session.memoire.ajouter_souvenir(souvenir)
    except OSError as erreur:
        raise ErreurOutil(f"Le souvenir n'a pas pu être écrit ({erreur}).") from erreur
    session.poursuite = None
    for engin in session.tous_les_engins():
        engin.nouvelle_scene()  # la nitro, les fumigènes et les leurres reviennent
    t = trame_.trame_de(session.monde)
    if t:
        t["enquete"] = False  # une enquête par scène
    if pnj_.actifs(session.monde):
        session.monde["pnj"]["elite"] = None  # un seul PNJ d'élite par scène
    return {"souvenir": souvenir}


@outil("Noter un PNJ qui compte (nommé, qui reviendra, qui a un avis sur le personnage), à la rencontre "
       "puis quand son attitude change. Le moteur le garde dans la mémoire de la campagne.",
       lambda s: _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple doc_mori."},
           **_champs_du_nom(s),
           "role": {"type": "string", "description": "Qui il est, en quelques mots."},
           "attitude": {"type": "string", "description": "Ce qu'il pense du personnage, et pourquoi."},
       }, ["identifiant", *_nom_requis(s), "role", "attitude"]))
def noter_pnj(session: Session, identifiant: str, role: str, attitude: str, nom: str | None = None,
              sexe: str | None = None, origine: str | None = None, faction: str | None = None) -> dict:
    nom = _nom_du_pnj(session, identifiant, nom, sexe, origine, faction)
    pnj = session.memoire.noter_pnj(identifiant, nom, role, attitude)
    return {"pnj": identifiant, "nom": pnj.nom, "role": pnj.role, "attitude": pnj.attitude, "etat": pnj.etat}


@outil("Ouvrir un fil de l'histoire : une quête, une promesse, une dette ou une menace à suivre.",
       lambda s: _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple dette_mori."},
           "fil": {"type": "string", "description": "Le fil en une phrase."},
       }, ["identifiant", "fil"]))
def ouvrir_fil(session: Session, identifiant: str, fil: str) -> dict:
    return {"fil": identifiant, "texte": session.memoire.ouvrir_fil(identifiant, fil).texte}


@outil("Clore un fil de l'histoire quand il se règle (réussi, raté, abandonné), avec son issue.",
       lambda s: _objet({
           "identifiant": _enum(sorted(i for i, f in s.memoire.fils.items() if f.ouvert) or ["aucun"]),
           "issue": {"type": "string", "description": "Comment il s'est réglé, en une phrase."},
           "reussie": {"type": "boolean", "description": "Pour une mission payée : est-elle réussie ? Le moteur "
                                                         "verse alors la récompense."},
       }, ["identifiant", "issue"]))
def clore_fil(session: Session, identifiant: str, issue: str, reussie: bool | None = None) -> dict:
    mission = session.personnage.missions.get(identifiant)
    if mission is not None and reussie is None:
        raise ErreurOutil(f"« {identifiant} » est une mission payée : précise « reussie » (vrai ou faux).")
    fil = session.memoire.clore_fil(identifiant, issue)
    resultat = {"fil": identifiant, "texte": fil.texte, "issue": fil.issue}
    if mission is not None:
        verse = gains.clore_mission(session.personnage, identifiant, reussie)
        resultat |= {"mission_reussie": reussie, "recompense_versee": verse, "argent": session.personnage.argent,
                     "monnaie": session.univers.monnaie}
        if session.monde is not None and mission.get("offre"):  # une mission du générateur change le monde
            changements = missions.conclure(session.monde, session.des, mission["offre"], reussie,
                                            session.moment.jour)
            if changements:
                resultat["monde"] = changements
            suite = trame_.apres_mission(session.monde, session.des, mission["offre"], reussie, session.moment.jour,
                                         session.personnage)
            if suite:
                resultat["trame"] = suite
    return resultat
