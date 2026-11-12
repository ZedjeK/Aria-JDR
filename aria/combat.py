"""Le combat : initiative, budget d'actions, attaques, dégâts, blessures et points de destin.

Référence : REGLES.md section 7. Le moteur lance tous les dés, y compris ceux des
ennemis ; le MJ choisit seulement les actions et raconte les rapports renvoyés.
"""

from dataclasses import dataclass, field
from enum import Enum

from aria.des import Des
from aria.equipement import ARMES_A_DISTANCE, CORPS_A_CORPS, Arme, Armure, Portee, Propriete, Recharge, formule_degats
from aria.inventaire import BONUS_ACTION_MINEURE, InventaireImpossible, a_chargeur, cadence
from aria.personnage import MALUS_BLESSURE_GRAVE, Caracteristique, Etat, Personnage
from aria.progression import cocher
from aria.reglages import Curseur
from aria.resolution import Degre, Difficulte, Issue, Resultat, opposer, tester
from aria.temps import Moment
from aria.vehicules import (
    EPERONNAGE,
    LEURRES,
    SCORE_DRONE_AUTONOME,
    Engin,
    cocher_pour,
    valeur_pilotage,
)

SAUVEGARDES_MAX = 3  # un effet persistant mord au plus 3 fois (REGLES.md 10.6)
DEGATS_PERSISTANTS = "1d3"
MAINS_NUES = Arme("Mains nues", CORPS_A_CORPS, "1d3", Portee.CONTACT)
MALUS_DEFENSE_SUPPLEMENTAIRE = -20
BONUS_VISER = 20
# Les armes de zone et l'IEM (REGLES.md 7.9 et 7.10)
TAILLE_ZONE = {"petite": 2, "moyenne": 4, "grande": 8}
BONUS_ESQUIVE_DEVIATION = 20
ROUNDS_FUMEE = 3
MALUS_AVEUGLE = -20
BRULURE, FUMEE, AVEUGLANT, IEM = "brûlure", "fumée", "aveuglant", "IEM"
NATURE_IEM = "iem"  # l'électronique d'un combattant est coupée
YEUX_CYBERNETIQUES = "Yeux cybernétiques"
NEUROPORT = "Neuroport"
# Tirer depuis un véhicule en mouvement (REGLES.md 12.4)
TIREURS = {"à pied": 0, "conducteur": -20, "passager": -10, "tourelle": 0}
PARTIES_VEHICULE = ("carrosserie", "pneus")


class ActionImpossible(Exception):
    """L'action demandée n'est pas permise par les règles à ce moment-là."""


class TypeAction(Enum):
    DEPLACEMENT = "déplacement"
    SIMPLE = "action simple"
    MINEURE = "action mineure"


class Defense(Enum):
    ESQUIVE = "esquive"
    RIPOSTE = "riposte"


class Couvert(Enum):
    """Le couvert de la cible, qui pénalise le tireur (REGLES.md 7.3)."""

    AUCUN = 0
    PARTIEL = -20
    LOURD = -40


class IssueZone(Enum):
    """Où tombe le projectile d'une arme de zone (REGLES.md 7.9)."""

    REUSSITE = "réussite"
    DEVIATION = "déviation"  # la moitié des dégâts, +20 pour esquiver
    MALADRESSE = "maladresse"  # aux pieds du lanceur


class BonusMajeure(Enum):
    """Le bonus choisi sur une réussite majeure (REGLES.md 7.4)."""

    DE_SUPPLEMENTAIRE = "+1 dé de dégâts"
    DESARMER = "désarmer"
    REPOUSSER = "repousser"


class BudgetRound:
    """Ce qu'un combattant peut encore faire ce round (REGLES.md 7.2) :
    1 déplacement + 1 action simple + 1 action mineure, ou 2 déplacements + 1 action mineure.
    """

    def __init__(self):
        self.utilise = {t: 0 for t in TypeAction}

    @staticmethod
    def _valide(deplacements: int, simples: int, mineures: int) -> bool:
        return mineures <= 1 and ((deplacements <= 1 and simples <= 1) or (deplacements <= 2 and simples == 0))

    def peut(self, action: TypeAction) -> bool:
        apres = dict(self.utilise)
        apres[action] += 1
        return self._valide(apres[TypeAction.DEPLACEMENT], apres[TypeAction.SIMPLE], apres[TypeAction.MINEURE])

    def restants(self, action: TypeAction) -> int:
        """Combien de fois ce type d'action est encore possible ce round, si on ne fait que lui."""
        nombre, apres = 0, dict(self.utilise)
        while True:
            apres[action] += 1
            if not self._valide(apres[TypeAction.DEPLACEMENT], apres[TypeAction.SIMPLE], apres[TypeAction.MINEURE]):
                return nombre
            nombre += 1

    def utiliser(self, action: TypeAction):
        if not self.peut(action):
            raise ActionImpossible(f"Le budget du round ne permet plus : {action.value}.")
        self.utilise[action] += 1


COMPETENCES_DE_COMBAT = (CORPS_A_CORPS, "Armes à distance", "Esquive")


@dataclass
class FichePnj:
    """Le profil simplifié d'un PNJ (REGLES.md 7.8). Un seul pourcentage sert à tout le combat.

    `competences` donne ses autres talents (par exemple {"Médecine": 60} pour un médecin) ;
    toute autre compétence vaut `competence_defaut`.
    """

    nom: str
    combat: int
    pv_max_base: int
    dexterite: int = 50
    constitution: int = 50
    perception: int = 25
    competences: dict[str, int] = field(default_factory=dict)
    competence_defaut: int = 25
    pv: int | None = None
    etat: Etat = Etat.ACTIF
    blessure_grave: bool = False
    points_destin: int = 0
    # Lanceur de sorts (REGLES.md 10.10) : sa Magie est dans `competences`
    pm: int = 0
    sorts: tuple[str, ...] = ()
    # Limite des soins magiques reçus (REGLES.md 10.7)
    dernier_soin_magique: Moment | None = None
    lanceurs_en_echec: list[str] = field(default_factory=list)
    moment_echecs_magie: Moment | None = None

    def __post_init__(self):
        if self.pv is None:
            self.pv = self.pv_max_base

    @property
    def pv_max(self) -> int:
        return self.pv_max_base // 2 if self.blessure_grave else self.pv_max_base

    def carac(self, caracteristique: Caracteristique) -> int:
        return {Caracteristique.DEXTERITE: self.dexterite, Caracteristique.CONSTITUTION: self.constitution}.get(
            caracteristique, 50
        )

    def competence(self, nom: str) -> int:
        if nom in self.competences:
            return self.competences[nom]
        if nom in COMPETENCES_DE_COMBAT:
            return self.combat
        if nom == "Perception":
            return self.perception
        return self.competence_defaut

    def valeur(self, nom: str) -> int:
        """La compétence avec le malus de blessure grave (−20 à toutes les actions)."""
        return self.competence(nom) + (MALUS_BLESSURE_GRAVE if self.blessure_grave else 0)


@dataclass
class EffetEnCours:
    """Ce qu'un sort laisse sur un combattant (REGLES.md 10.3 et 10.6).

    `nature` : « protection » (armure en plus), « renfort » ou « entrave » (bonus ou malus à
    tous ses jets), ou « attaque » pour une brûlure persistante. `rounds` : None jusqu'à la fin
    du combat ; hors combat, un effet d'un round vaut pour le prochain jet.
    """

    sort: str
    nature: str
    valeur: int
    rounds: int | None = 1
    persistant: bool = False  # s'arrête sur un jet de sauvegarde réussi, au début du tour de sa victime
    sauvegardes: int = 0


@dataclass
class RapportSauvegarde:
    qui: str
    sort: str
    test: Resultat
    degats: int = 0
    fini: bool = False  # l'effet s'arrête


class Combattant:
    """Un participant au combat : un personnage ou un ennemi, avec son équipement en main."""

    def __init__(self, fiche: Personnage | FichePnj, camp: str, arme: Arme | None = None, armure: Armure | None = None):
        self.fiche = fiche
        self.camp = camp
        self.arme = arme
        self.armure = armure
        self.munitions: dict[Arme, int] = {}
        # Ses chargeurs et ses cartouches (REGLES.md 13.5) : l'inventaire d'un personnage, ou la réserve d'un
        # PNJ. None : il recharge sans compter (avant l'économie, et au banc d'essai).
        self.reserve = None
        self.budget = BudgetRound()
        self.defenses_ce_round = 0
        self.vise = False  # bonus de visée en attente du prochain tir
        self.a_vise = False  # a visé ce round : ne peut plus se déplacer, même après avoir tiré
        self.surpris = False
        self.sursis = False  # tombé mourant ce round : son premier test attend la fin du round suivant
        self.effets: list[EffetEnCours] = []  # ce que les sorts lui ont laissé
        self.armure_implantee: Armure | None = None  # posée par la session, d'après les implants du personnage
        self.armes_implantees: frozenset[str] = frozenset()  # leurs noms : une IEM les rend inutilisables
        self.blindage_iem = False  # tout son équipement électronique est blindé
        self.drone: Engin | None = None  # ce combattant est un drone (REGLES.md 12.7)
        self.operateur: Combattant | None = None  # un drone télépiloté : il agit avec l'action de son opérateur
        if arme:
            self._charger(arme)

    @property
    def nom(self) -> str:
        return self.fiche.nom

    @property
    def force(self) -> int | None:
        """La Force pour le bonus de dégâts ; un ennemi l'a déjà dans son arme."""
        return self.fiche.carac(Caracteristique.FORCE) if isinstance(self.fiche, Personnage) else None

    @property
    def arme_en_main(self) -> Arme:
        return self.arme or MAINS_NUES

    @property
    def arme_de_melee(self) -> Arme:
        return self.arme if self.arme and self.arme.corps_a_corps else MAINS_NUES

    def _charger(self, arme: Arme):
        if arme.munitions:
            self.munitions[arme] = arme.chargeur.capacite

    def munitions_restantes(self) -> int | None:
        arme = self.arme
        return self.munitions.get(arme) if arme and arme.munitions else None

    def cocher(self, competence: str, resultat: Resultat):
        """Coche la compétence pour la progression, si c'est un personnage joueur."""
        cocher(self.fiche, competence, resultat)

    def valeur(self, competence: str) -> int:
        """La compétence avec les malus subis (blessure grave, armure) et les renforts ou entraves des sorts.
        Un drone télépiloté agit avec le Pilotage de son opérateur, ou son Piratage par un neuroport."""
        if self.operateur:
            op = self.operateur
            pilotage = _valeur_ou_zero(op, "Pilotage")
            if isinstance(op.fiche, Personnage) and any(p["nom"] == NEUROPORT for p in op.fiche.implants):
                pilotage = max(pilotage, _valeur_ou_zero(op, "Technologie"))
            return pilotage + self.modificateur_magique
        valeur = self.fiche.valeur(competence) + self.modificateur_magique
        if self.reserve is not None:
            valeur += self.reserve.malus(competence)  # la surcharge, un gilet lourd, un sac de randonnée
        if self.iem and isinstance(self.fiche, Personnage):
            valeur -= self.fiche.bonus_implants(competence)  # les implants sont coupés
        for armure in (self.armure, self.armure_implantee):
            if armure:
                valeur += armure.malus_pour(competence)
        return valeur

    @property
    def modificateur_magique(self) -> int:
        return sum(e.valeur for e in self.effets if e.nature in ("renfort", "entrave"))

    @property
    def iem(self) -> bool:
        """Une IEM lui a coupé l'électronique pour le round (REGLES.md 7.10)."""
        return any(e.nature == NATURE_IEM for e in self.effets)

    @property
    def protection(self) -> int:
        """La meilleure armure, portée ou implantée (elles ne se cumulent pas), plus celle des sorts.
        Sous une IEM, l'armure implantée ne protège plus."""
        magique = sum(e.valeur for e in self.effets if e.nature == "protection")
        implantee = None if self.iem else self.armure_implantee
        armures = [a.protection_totale for a in (self.armure, implantee) if a]
        return max(armures, default=0) + magique

    def consommer_effets_du_jet(self):
        """Hors combat, un renfort ou une entrave d'un round vaut pour le prochain jet seulement."""
        self.effets = [e for e in self.effets if e.persistant or e.rounds is None or e.nature == "protection"]

    @property
    def conscient(self) -> bool:
        return self.fiche.etat is Etat.ACTIF


@dataclass
class RapportBlessure:
    victime: str
    degats: int
    pv_avant: int
    pv_apres: int
    blessure_grave: bool = False
    test_constitution: Resultat | None = None
    etat: Etat = Etat.ACTIF
    mort_instantanee: bool = False


@dataclass
class RapportAttaque:
    attaquant: str
    cible: str
    attaque: Resultat
    defense: Resultat | None
    issue: Issue
    touche: str | None = None  # qui a pris le coup (la cible, ou l'attaquant sur une riposte)
    degats_bruts: int = 0
    protection: int = 0
    blessure: RapportBlessure | None = None
    effets: list[str] = field(default_factory=list)


def _valeur_ou_zero(combattant: Combattant, competence: str) -> int:
    try:
        return combattant.valeur(competence)
    except KeyError:
        return 0


def combattant_drone(engin: Engin, camp: str, arme: Arme | None = None, operateur: Combattant | None = None,
                     blindage_iem: bool = False) -> Combattant:
    """Un drone devient un combattant : sa structure fait ses PV, son blindage son armure.
    Autonome, il agit à son tour avec un score de 40 ; télépiloté, avec l'action de son opérateur."""
    fiche = FichePnj(engin.nom, combat=SCORE_DRONE_AUTONOME, pv_max_base=engin.modele.structure_max,
                     dexterite=50, perception=SCORE_DRONE_AUTONOME, pv=engin.structure)
    armure = Armure("Blindage", engin.modele.blindage_total) if engin.modele.blindage_total else None
    drone = Combattant(fiche, camp, arme, armure)
    drone.drone, drone.operateur, drone.blindage_iem = engin, operateur, blindage_iem
    return drone


@dataclass
class RapportTirVehicule:
    attaquant: str
    vehicule: str
    partie: str
    attaque: Resultat | None
    touche: bool = False
    degats_bruts: int = 0
    blindage: int = 0
    structure_perdue: int = 0
    etat: str = ""
    effets: list[str] = field(default_factory=list)


@dataclass
class RapportEperonnage:
    attaquant: str
    cible: str
    attaque: Resultat
    defense: Resultat
    touche: bool = False
    degats: int = 0
    structure_cible: int | None = None  # contre un véhicule
    blessure: RapportBlessure | None = None  # contre un piéton
    recul: int = 0  # ce que l'attaquant prend sur sa propre structure
    effets: list[str] = field(default_factory=list)


@dataclass
class RapportCibleZone:
    """Ce qu'une cible prend dans la zone : son esquive, ses dégâts, ses effets."""

    qui: str
    esquive: Resultat | None = None
    couvert_lourd: bool = False
    degats_bruts: int = 0  # après déviation, esquive et couvert, avant l'armure
    protection: int = 0
    blessure: RapportBlessure | None = None
    test_constitution: Resultat | None = None  # contre un éclat aveuglant
    effets: list[str] = field(default_factory=list)


@dataclass
class RapportZone:
    attaquant: str
    arme: str
    competence: str
    attaque: Resultat
    issue: IssueZone
    jet_degats: int = 0  # le jet de dégâts, le même pour toute la zone
    cibles: list[RapportCibleZone] = field(default_factory=list)
    vehicules: list[tuple[str, int, str, list[str]]] = field(default_factory=list)  # (nom, structure perdue, état, effets)
    effets: list[str] = field(default_factory=list)


@dataclass
class RapportEmbuscade:
    discretion: Resultat  # le jet des agresseurs
    perception: Resultat  # le jet des victimes
    surpris: bool  # vrai si les victimes sont surprises


def tester_embuscade(des: Des, perception_victimes: int, discretion_agresseurs: int) -> RapportEmbuscade:
    """Perception des victimes contre Discrétion des agresseurs (REGLES.md 7.1).

    Comme pour une esquive, une égalité profite aux victimes.
    """
    discretion = tester(des, discretion_agresseurs)
    perception = tester(des, perception_victimes)
    return RapportEmbuscade(discretion, perception, opposer(discretion, perception, esquive=True) is Issue.ATTAQUANT)


def _initiative(combattant: Combattant) -> tuple[int, int]:
    """Initiative : Dextérité décroissante, Perception pour départager (REGLES.md 7.1)."""
    return combattant.fiche.carac(Caracteristique.DEXTERITE), combattant.fiche.competence("Perception")


class Combat:
    """Un combat en cours. Les méthodes renvoient des rapports que le MJ raconte."""

    def __init__(self, des: Des, combattants: list[Combattant], curseur: Curseur = Curseur.STANDARD,
                 surpris: list[Combattant] = (), tour_par_tour: bool = False):
        """`tour_par_tour` : le moteur fait respecter l'ordre d'initiative (seul celui dont c'est le tour
        agit, puis fin_de_tour passe au suivant). La démo v1 et les tests de mécanique s'en passent."""
        self.des = des
        self.curseur = curseur
        self.round = 1
        self.tour_par_tour = tour_par_tour
        self.ordre = sorted(combattants, key=_initiative, reverse=True)
        for combattant in surpris:
            combattant.surpris = True
        self.actif = self._prochain(0)  # l'indice, dans l'ordre, de celui dont c'est le tour
        self.sauvegardes: list[RapportSauvegarde] = []  # les effets persistants, en attente d'être racontés
        self.fumee = 0  # les rounds de fumée qui restent : tirer à travers, c'est un couvert lourd

    # --- Le tour de parole ---------------------------------------------------------

    @property
    def au_tour_de(self) -> Combattant | None:
        """Celui qui joue ; None si plus personne ne peut agir."""
        return None if self.actif is None else self.ordre[self.actif]

    def rejoindre(self, combattant: Combattant):
        """Un nouveau venu entre dans le combat, à sa place dans l'ordre d'initiative. Placé après
        celui qui joue, il agit dès ce round ; placé avant, au round suivant."""
        if combattant in self.ordre:
            raise ActionImpossible(f"{combattant.nom} est déjà dans le combat.")
        joue = self.au_tour_de
        self.ordre = sorted(self.ordre + [combattant], key=_initiative, reverse=True)
        self.actif = self.ordre.index(joue) if joue else self._prochain(0)

    def _prochain(self, debut: int) -> int | None:
        return next((i for i in range(debut, len(self.ordre)) if self.peut_agir(self.ordre[i])), None)

    def fin_de_tour(self) -> list[tuple[str, Resultat]]:
        """Passe au suivant dans l'ordre d'initiative, en sautant ceux qui ne peuvent pas agir.
        Après le dernier, le round se clôt tout seul : renvoie alors les tests des mourants.
        Au début de chaque tour, les effets persistants mordent leur victime (voir `sauvegardes`)."""
        tests = []
        while True:
            suivant = None if self.actif is None else self._prochain(self.actif + 1)
            if suivant is None:
                tests += self.fin_de_round()
            else:
                self.actif = suivant
            if self.actif is None or self._debut_de_tour(self.ordre[self.actif]):
                return tests

    def _debut_de_tour(self, combattant: Combattant) -> bool:
        """Un jet de sauvegarde par effet persistant : Constitution contre une brûlure, Volonté contre
        une entrave (REGLES.md 10.6). Renvoie False si le combattant ne peut plus agir."""
        for effet in [e for e in combattant.effets if e.persistant]:
            carac = Caracteristique.CONSTITUTION if effet.nature == "attaque" else Caracteristique.VOLONTE
            test = tester(self.des, combattant.fiche.carac(carac))
            effet.sauvegardes += 1
            rapport = RapportSauvegarde(combattant.nom, effet.sort, test)
            if not test.reussi and effet.nature == "attaque":
                rapport.degats = self.des.jet(DEGATS_PERSISTANTS)
                self.appliquer_degats(combattant, rapport.degats)
            rapport.fini = test.reussi or effet.sauvegardes >= SAUVEGARDES_MAX
            if rapport.fini:
                combattant.effets.remove(effet)
            self.sauvegardes.append(rapport)
        return self.peut_agir(combattant)

    # --- Ce que chacun peut faire --------------------------------------------------

    def peut_agir(self, combattant: Combattant) -> bool:
        """Un drone télépiloté n'a pas de tour à lui ; un drone coupé par une IEM ne fait rien."""
        if combattant.operateur or (combattant.drone and combattant.iem):
            return False
        return combattant.conscient and not (combattant.surpris and self.round == 1)

    def action_simple(self, combattant: Combattant):
        """Une action simple sans autre effet sur le combat, par exemple lancer un sort."""
        self._agir(combattant, TypeAction.SIMPLE)

    def _agir(self, combattant: Combattant, action: TypeAction):
        if combattant.operateur:
            if combattant.iem or not combattant.conscient:
                raise ActionImpossible(f"{combattant.nom} ne répond plus.")
            self._agir(combattant.operateur, TypeAction.SIMPLE)  # piloter le drone coûte une action simple
            return
        if not self.peut_agir(combattant):
            raise ActionImpossible(f"{combattant.nom} ne peut pas agir.")
        if self.tour_par_tour and combattant is not self.au_tour_de:
            qui = self.au_tour_de.nom if self.au_tour_de else "personne"
            raise ActionImpossible(f"Ce n'est pas le tour de {combattant.nom} : c'est au tour de {qui}.")
        combattant.budget.utiliser(action)

    def deplacer(self, combattant: Combattant):
        if combattant.a_vise:
            raise ActionImpossible(f"{combattant.nom} a visé : il ne peut plus se déplacer ce round.")
        self._agir(combattant, TypeAction.DEPLACEMENT)

    def viser(self, combattant: Combattant):
        """+20 au tir de ce round (action mineure), seulement sans se déplacer ce round."""
        if combattant.budget.utilise[TypeAction.DEPLACEMENT]:
            raise ActionImpossible(f"{combattant.nom} s'est déplacé : il ne peut plus viser ce round.")
        self._agir(combattant, TypeAction.MINEURE)
        combattant.vise = combattant.a_vise = True

    def degainer(self, combattant: Combattant, arme: Arme | None, rangee: bool = False):
        """Prendre une autre arme en main, ou la ranger avec None (action mineure). `rangee` : l'arme était au
        fond du sac, et la sortir coûte une action simple (REGLES.md 13.9)."""
        self._agir(combattant, TypeAction.SIMPLE if rangee else TypeAction.MINEURE)
        if arme and arme not in combattant.munitions:
            combattant._charger(arme)
        combattant.arme = arme

    def recharger(self, combattant: Combattant):
        arme = combattant.arme
        if not arme or not arme.munitions:
            raise ActionImpossible(f"{combattant.nom} n'a rien à recharger.")
        action = TypeAction.MINEURE if arme.chargeur.recharge is Recharge.MINEURE else TypeAction.SIMPLE
        if combattant.reserve is None:
            self._agir(combattant, action)
            combattant.munitions[arme] = arme.chargeur.capacite
            return
        # Les munitions sont comptées (REGLES.md 13.5) : on change de chargeur s'il en reste un garni sous la
        # main ; un chargeur rapide recharge un barillet en une action mineure ; sinon, on garnit à la main.
        if combattant.reserve.chargeur_garni(arme):
            self._agir(combattant, action if a_chargeur(arme) else TypeAction.MINEURE)
            combattant.munitions[arme] = combattant.reserve.changer_chargeur(arme, combattant.munitions[arme])
        elif a_chargeur(arme):
            try:
                combattant.reserve.changer_chargeur(arme, combattant.munitions[arme])
            except InventaireImpossible as erreur:  # dit pourquoi : plus de chargeur garni, ou rangé dans le sac
                raise ActionImpossible(str(erreur)) from erreur
        else:
            self.garnir(combattant)

    def garnir(self, combattant: Combattant, avec_la_mineure: bool = False) -> int:
        """Garnit à la main (REGLES.md 13.5) : une action simple, pour un nombre de cartouches qui dépend de la
        compétence Armes à distance et du moyen (la main, un garnisseur, une lame-chargeur) ; l'action mineure du
        round, si elle y est consacrée, en ajoute 2. Une arme sans chargeur se garnit directement ; pour les
        autres, le chargeur de rechange le moins vide, ou à défaut celui de l'arme. Renvoie les cartouches garnies."""
        arme, reserve = combattant.arme, combattant.reserve
        if not arme or not arme.munitions:
            raise ActionImpossible(f"{combattant.nom} n'a rien à garnir.")
        if reserve is None:
            raise ActionImpossible("Les munitions ne sont pas comptées ici : recharge suffit.")
        try:
            competence = combattant.fiche.valeur(ARMES_A_DISTANCE)
        except KeyError:
            competence = 0
        nombre = cadence(competence, reserve.moyen_de_garnir(arme)) + (BONUS_ACTION_MINEURE if avec_la_mineure else 0)
        directe = not a_chargeur(arme)
        try:
            if directe:
                garnies, contenu = reserve.garnir(arme, nombre, combattant.munitions[arme])
            else:
                try:
                    garnies, contenu = reserve.garnir(arme, nombre)
                except InventaireImpossible:  # pas de chargeur de rechange à garnir : celui de l'arme
                    garnies, contenu = reserve.garnir(arme, nombre, combattant.munitions[arme])
        except InventaireImpossible as erreur:
            raise ActionImpossible(str(erreur)) from erreur
        self._agir(combattant, TypeAction.SIMPLE)
        if avec_la_mineure:
            self._agir(combattant, TypeAction.MINEURE)
        if contenu is not None:
            combattant.munitions[arme] = contenu
        return garnies

    # --- L'attaque ---------------------------------------------------------------------

    def attaquer(
        self,
        attaquant: Combattant,
        cible: Combattant,
        defense: Defense | None = None,
        couvert: Couvert = Couvert.AUCUN,
        bonus_majeure: BonusMajeure = BonusMajeure.DE_SUPPLEMENTAIRE,
        difficulte: Difficulte = Difficulte.NORMALE,
        tireur: str = "à pied",
    ) -> RapportAttaque:
        """Une attaque complète : jets, défense, dégâts et blessures (REGLES.md 7.3 à 7.6).

        `difficulte` : choisie par le MJ dans la liste fermée, par exemple Facile contre une cible sans défense.
        `tireur` : d'où il attaque, si c'est d'un véhicule en mouvement (12.4).
        """
        if cible.fiche.etat is Etat.MORT:
            raise ActionImpossible(f"{cible.nom} est déjà mort.")
        arme = attaquant.arme_en_main
        if arme.zone:
            raise ActionImpossible(f"{arme.nom} est une arme de zone : elle se joue avec l'attaque de zone (attaquer_zone).")
        self._verifier_arme_utilisable(attaquant, arme)
        self._verifier_tireur(arme, tireur)
        self._agir(attaquant, TypeAction.SIMPLE)

        modificateur = arme.bonus_sans(electronique=attaquant.iem).jet + TIREURS[tireur]
        effets = []
        if not arme.corps_a_corps:
            modificateur += couvert.value
            if attaquant.vise:
                modificateur += BONUS_VISER
                attaquant.vise = False
            if arme.munitions:
                attaquant.munitions[arme] -= 1
            elif arme.a(Propriete.LANCER):
                attaquant.arme = None
                effets.append(f"{arme.nom} est lancée et n'est plus en main.")

        attaque = tester(self.des, attaquant.valeur(arme.competence), difficulte, combat=True, modificateur=modificateur)
        attaquant.cocher(arme.competence, attaque)
        if attaque.degre is Degre.MALADRESSE and arme.a(Propriete.FRAGILE):
            attaquant.arme = None
            effets.append(f"{arme.nom} se brise.")

        # La défense : seulement au corps à corps, une gratuite par round, puis −20 par défense en plus
        resultat_defense = None
        peut_defendre = arme.corps_a_corps and defense and cible.conscient and not (cible.surpris and self.round == 1)
        if peut_defendre:
            malus = MALUS_DEFENSE_SUPPLEMENTAIRE * cible.defenses_ce_round
            cible.defenses_ce_round += 1
            if defense is Defense.ESQUIVE:
                competence_defense = "Esquive"
                resultat_defense = tester(self.des, cible.valeur("Esquive"), combat=True, modificateur=malus)
            else:
                competence_defense = CORPS_A_CORPS
                arme_riposte = cible.arme_de_melee
                resultat_defense = tester(
                    self.des, cible.valeur(CORPS_A_CORPS), combat=True, modificateur=malus + arme_riposte.bonus.jet
                )
            cible.cocher(competence_defense, resultat_defense)
            issue = opposer(attaque, resultat_defense, esquive=defense is Defense.ESQUIVE)
        else:
            issue = Issue.ATTAQUANT if attaque.reussi else Issue.PERSONNE

        rapport = RapportAttaque(attaquant.nom, cible.nom, attaque, resultat_defense, issue, effets=effets)
        if issue is Issue.ATTAQUANT:
            self._infliger(attaquant, arme, attaque.degre, cible, bonus_majeure, rapport)
        elif issue is Issue.DEFENSEUR and defense is Defense.RIPOSTE:
            self._infliger(cible, cible.arme_de_melee, resultat_defense.degre, attaquant, bonus_majeure, rapport)
        return rapport

    @staticmethod
    def _verifier_tireur(arme: Arme, tireur: str):
        if tireur not in TIREURS:
            raise ActionImpossible(f"Tireur inconnu « {tireur} » : {', '.join(TIREURS)}.")
        if tireur == "conducteur" and arme.a(Propriete.DEUX_MAINS):
            raise ActionImpossible(f"Au volant, on ne tire qu'à une main : pas avec {arme.nom}.")
        if arme.montee and tireur != "tourelle":
            raise ActionImpossible(f"{arme.nom} se tire seulement d'une tourelle (ou d'un trépied).")

    def _verifier_arme_utilisable(self, attaquant: Combattant, arme: Arme):
        if not arme.corps_a_corps and arme.munitions and attaquant.munitions[arme] == 0:
            raise ActionImpossible(f"L'arme de {attaquant.nom} est vide : il faut recharger.")
        if attaquant.iem and arme.nom in attaquant.armes_implantees:
            raise ActionImpossible(f"{arme.nom} est coupée par l'IEM jusqu'à la fin du round.")

    # --- Les véhicules en combat (REGLES.md 12.4) -----------------------------------------

    def tirer_sur_vehicule(self, attaquant: Combattant, engin: Engin, partie: str = "carrosserie",
                           tireur: str = "à pied", difficulte: Difficulte = Difficulte.NORMALE) -> RapportTirVehicule:
        """Viser la carrosserie (les dégâts moins le blindage vont à la structure) ou les pneus et le moteur
        (difficile, sans dégâts, mais un cran de vitesse en moins, pas sur un véhicule blindé).
        Les leurres font rater d'office la première roquette de la scène."""
        if partie not in PARTIES_VEHICULE:
            raise ActionImpossible(f"Partie inconnue « {partie} » : {', '.join(PARTIES_VEHICULE)}.")
        arme = attaquant.arme_en_main
        if partie == "pneus" and engin.modele.blinde:
            raise ActionImpossible(f"{engin.nom} est blindé : ses pneus et son moteur ne craignent rien.")
        if engin.etat == "épave":
            raise ActionImpossible(f"{engin.nom} est déjà une épave.")
        self._verifier_arme_utilisable(attaquant, arme)
        self._verifier_tireur(arme, tireur)
        self._agir(attaquant, TypeAction.SIMPLE)
        rapport = RapportTirVehicule(attaquant.nom, engin.nom, partie, None)
        modificateur = arme.bonus_sans(electronique=attaquant.iem).jet + TIREURS[tireur]
        if attaquant.vise and not arme.corps_a_corps:
            modificateur += BONUS_VISER
        attaquant.vise = False
        if not arme.corps_a_corps and arme.munitions:
            attaquant.munitions[arme] -= 1
        elif arme.usage_unique or arme.a(Propriete.LANCER):
            attaquant.arme = None
            rapport.effets.append(f"{arme.nom} est partie : plus en main.")
        if arme.zone and arme.munitions and engin.modele.a(LEURRES) and LEURRES not in engin.systemes_utilises:
            engin.systemes_utilises.add(LEURRES)
            rapport.effets.append("Les leurres détournent le projectile : il rate d'office.")
            rapport.etat = engin.etat
            return rapport
        if partie == "pneus":
            difficulte = Difficulte(min(difficulte.value, Difficulte.DIFFICILE.value))  # au moins difficile
        rapport.attaque = tester(self.des, attaquant.valeur(arme.competence), difficulte, combat=True,
                                 modificateur=modificateur)
        attaquant.cocher(arme.competence, rapport.attaque)
        rapport.touche = rapport.attaque.reussi
        if rapport.touche and partie == "pneus":
            engin.vitesse_perdue += 1
            rapport.effets.append(f"{engin.nom} perd un cran de vitesse ({engin.vitesse}).")
        elif rapport.touche and arme.degats:
            formule = formule_degats(arme, attaquant.force)
            critique = rapport.attaque.degre is Degre.CRITIQUE
            rapport.degats_bruts = formule.maximum if critique else self.des.jet(formule)
            blindage = engin.modele.blindage_total
            rapport.blindage = blindage // 2 if arme.a(Propriete.PERFORANTE) or critique else blindage
            rapport.structure_perdue = engin.encaisser(rapport.degats_bruts - rapport.blindage, blindage=False)
            for effet in arme.effets:
                if effet == IEM:
                    rapport.effets += iem_sur_engin(engin)
        rapport.etat = engin.etat
        if engin.etat == "épave":
            rapport.effets.append(f"{engin.nom} est une épave : les occupants doivent sortir.")
        return rapport

    def eperonner(self, attaquant: Combattant, engin: Engin, cible: Combattant,
                  engin_cible: Engin | None = None) -> RapportEperonnage:
        """Au contact : Pilotage contre Pilotage (ou contre l'Esquive d'un piéton). Les dégâts suivent le
        gabarit de l'attaquant, +1d6 s'il est rapide ; il en prend la moitié sur sa propre structure."""
        if engin.etat in ("épave", "mourante"):
            raise ActionImpossible(f"{engin.nom} ne peut plus avancer.")
        self._agir(attaquant, TypeAction.SIMPLE)
        attaque = tester(self.des, valeur_pilotage(attaquant, engin), combat=True)
        cocher_pour(attaquant, "Pilotage", attaque)
        if engin_cible:
            defense = tester(self.des, valeur_pilotage(cible, engin_cible), combat=True)
            cocher_pour(cible, "Pilotage", defense)
        else:
            defense = tester(self.des, _valeur_ou_zero(cible, "Esquive"), combat=True)
            cible.cocher("Esquive", defense)
        rapport = RapportEperonnage(attaquant.nom, engin_cible.nom if engin_cible else cible.nom, attaque, defense)
        degre_a = attaque.degre if attaque.reussi else Degre.ECHEC
        degre_d = defense.degre if defense.reussi else Degre.ECHEC
        if not attaque.reussi or degre_a <= degre_d:
            rapport.effets.append("La cible esquive le choc.")
            return rapport
        rapport.touche = True
        rapport.degats = self.des.jet(EPERONNAGE[engin.modele.gabarit]) + (self.des.lancer(6) if engin.cran >= 2 else 0)
        if engin_cible:
            engin_cible.encaisser(rapport.degats)
            rapport.structure_cible = engin_cible.structure
            if engin_cible.etat == "épave":
                rapport.effets.append(f"{engin_cible.nom} est une épave.")
        else:
            rapport.blessure = self.appliquer_degats(cible, max(0, rapport.degats - cible.protection))
        rapport.recul = engin.encaisser(rapport.degats // 2)
        return rapport

    # --- Les armes de zone (REGLES.md 7.9) ------------------------------------------------

    @staticmethod
    def competence_de_zone(combattant: Combattant, arme: Arme) -> str:
        """Athlétisme pour une grenade lancée, Explosifs (ou Artisanat) pour une charge posée,
        la compétence de l'arme pour un lanceur. Un PNJ a un seul pourcentage de combat (7.8)."""
        competence = "Athlétisme" if arme.a(Propriete.LANCER) else "Explosifs" if arme.posee else arme.competence
        fiche = combattant.fiche
        if isinstance(fiche, FichePnj):
            return competence if competence in fiche.competences else ARMES_A_DISTANCE
        if competence == "Explosifs" and competence not in fiche.competences:
            return "Artisanat"
        return competence

    def attaquer_zone(
        self,
        attaquant: Combattant,
        cibles: list[Combattant],
        couverts_lourds: list[Combattant] = (),
        sans_esquive: list[Combattant] = (),
        voisins: list[Combattant] = (),
        difficulte: Difficulte = Difficulte.NORMALE,
        vehicules: list[Engin] = (),
        tireur: str = "à pied",
    ) -> RapportZone:
        """Une grenade, une roquette, une charge : toute la zone est touchée, alliés compris.

        `voisins` : ceux qui sont tout près du lanceur, touchés à sa place s'il fait une maladresse.
        Chaque cible esquive (sa défense du round), sauf celles de `sans_esquive`.
        """
        arme = attaquant.arme
        if not arme or not arme.zone:
            raise ActionImpossible(f"{attaquant.nom} n'a pas d'arme de zone en main.")
        taille = TAILLE_ZONE[arme.zone]
        if len(cibles) > taille:
            raise ActionImpossible(f"Une zone {arme.zone} touche {taille} cibles au plus.")
        if len({id(c) for c in cibles}) != len(cibles):
            raise ActionImpossible("Une même cible apparaît deux fois.")
        self._verifier_arme_utilisable(attaquant, arme)
        self._verifier_tireur(arme, tireur)
        self._agir(attaquant, TypeAction.SIMPLE)

        effets = []
        modificateur = arme.bonus_sans(electronique=attaquant.iem).jet + TIREURS[tireur]
        if attaquant.vise and not arme.posee:
            modificateur += BONUS_VISER
        attaquant.vise = False
        if arme.munitions:
            attaquant.munitions[arme] -= 1
        elif arme.usage_unique:
            attaquant.arme = None
            effets.append(f"{arme.nom} est utilisée : elle ne sert qu'une fois.")

        competence = self.competence_de_zone(attaquant, arme)
        attaque = tester(self.des, attaquant.valeur(competence), difficulte, combat=True, modificateur=modificateur)
        attaquant.cocher(competence, attaque)
        if attaque.degre is Degre.MALADRESSE:
            issue = IssueZone.MALADRESSE
            cibles = [attaquant] + [v for v in voisins if v is not attaquant][:taille - 1]
            effets.append(f"Maladresse : {arme.nom} tombe aux pieds de {attaquant.nom}.")
        else:
            issue = IssueZone.REUSSITE if attaque.reussi else IssueZone.DEVIATION
            if issue is IssueZone.DEVIATION:
                effets.append("Le projectile dévie : la moitié des dégâts, et +20 pour esquiver.")

        rapport = RapportZone(attaquant.nom, arme.nom, competence, attaque, issue, effets=effets)
        if arme.degats:
            rapport.jet_degats = self.des.jet(formule_degats(arme))
        for cible in cibles:
            if cible.fiche.etat is Etat.MORT:
                continue
            rapport.cibles.append(self._subir_zone(arme, rapport.jet_degats, issue, cible,
                                                   any(c is cible for c in couverts_lourds),
                                                   not any(c is cible for c in sans_esquive)))
        if issue is not IssueZone.MALADRESSE:
            for engin in vehicules:
                perdue = 0
                if arme.degats:
                    degats = rapport.jet_degats // 2 if issue is IssueZone.DEVIATION else rapport.jet_degats
                    blindage = engin.modele.blindage_total
                    perdue = engin.encaisser(degats - (blindage // 2 if arme.a(Propriete.PERFORANTE) else blindage),
                                             blindage=False)
                textes = iem_sur_engin(engin) if IEM in arme.effets else []
                rapport.vehicules.append((engin.nom, perdue, engin.etat, textes))
        if FUMEE in arme.effets:
            self.fumee = ROUNDS_FUMEE
            effets.append(f"Fumée pendant {ROUNDS_FUMEE} rounds : tirer à travers, c'est un couvert lourd (−40).")
        return rapport

    def _subir_zone(self, arme: Arme, jet: int, issue: IssueZone, cible: Combattant, couvert_lourd: bool,
                    esquive: bool) -> RapportCibleZone:
        r = RapportCibleZone(cible.nom, couvert_lourd=couvert_lourd)
        touchee = True
        if arme.degats:
            degats = jet // 2 if issue is IssueZone.DEVIATION else jet
            if esquive and cible.conscient and not (cible.surpris and self.round == 1):
                malus = MALUS_DEFENSE_SUPPLEMENTAIRE * cible.defenses_ce_round
                cible.defenses_ce_round += 1
                bonus = BONUS_ESQUIVE_DEVIATION if issue is IssueZone.DEVIATION else 0
                r.esquive = tester(self.des, cible.valeur("Esquive"), combat=True, modificateur=malus + bonus)
                cible.cocher("Esquive", r.esquive)
                if r.esquive.degre in (Degre.MAJEURE, Degre.CRITIQUE):
                    degats = 0
                elif r.esquive.reussi:
                    degats //= 2
            if couvert_lourd:
                degats //= 2
            r.protection = cible.protection // 2 if arme.a(Propriete.PERFORANTE) else cible.protection
            r.degats_bruts = degats
            touchee = degats > 0
            if touchee:
                r.blessure = self.appliquer_degats(cible, max(0, degats - r.protection))
        for effet in sorted(arme.effets):
            if effet == BRULURE and touchee and cible.fiche.etat is not Etat.MORT:
                cible.effets.append(EffetEnCours(arme.nom, "attaque", 0, None, persistant=True))
                r.effets.append("brûlure : jet de Constitution au début de chacun de ses tours, 1d3 s'il est raté")
            elif effet == AVEUGLANT and cible.conscient:
                r.test_constitution = tester(self.des, cible.fiche.carac(Caracteristique.CONSTITUTION))
                if r.test_constitution.reussi:
                    r.effets.append("résiste à l'éclat")
                else:
                    cible.effets.append(EffetEnCours(arme.nom, "entrave", MALUS_AVEUGLE, 1))
                    r.effets.append(f"aveuglé : {MALUS_AVEUGLE} à tout pendant 1 round")
            elif effet == IEM:
                r.effets += subir_iem(cible, arme.nom)
        return r

    def _infliger(self, source: Combattant, arme: Arme, degre: Degre, victime: Combattant,
                  bonus_majeure: BonusMajeure, rapport: RapportAttaque):
        formule = formule_degats(arme, source.force)
        protection = victime.protection
        if arme.a(Propriete.PERFORANTE) or degre is Degre.CRITIQUE:
            protection //= 2  # perforante ou critique : l'armure ne compte qu'à moitié (une seule fois)
        if degre is Degre.CRITIQUE:
            brut = formule.maximum
            rapport.effets.append("Critique : dégâts maximum, armure à moitié.")
        else:
            brut = self.des.jet(formule)
            if degre is Degre.MAJEURE:
                if bonus_majeure is BonusMajeure.DE_SUPPLEMENTAIRE:
                    faces = next((t.faces for t in formule.termes if t.faces), 0)
                    if faces:
                        brut += self.des.lancer(faces)
                elif bonus_majeure is BonusMajeure.DESARMER and victime.arme:
                    rapport.effets.append(f"{victime.nom} est désarmé ({victime.arme.nom}).")
                    victime.arme = None
                rapport.effets.append(f"Réussite majeure : {bonus_majeure.value}.")
        rapport.touche = victime.nom
        rapport.degats_bruts = brut
        rapport.protection = protection
        rapport.blessure = self.appliquer_degats(victime, max(0, brut - protection))

    def toucher_par_sort(self, lanceur: Combattant, cible: Combattant, sort: str, formule: str,
                         test: Resultat) -> RapportAttaque:
        """Un sort d'attaque se joue comme un tir : pas de défense, les degrés du combat (REGLES.md 10.3).
        Le jet de Magie est déjà fait ; ici, seulement les dégâts."""
        rapport = RapportAttaque(lanceur.nom, cible.nom, test, None,
                                 Issue.ATTAQUANT if test.reussi else Issue.PERSONNE)
        if test.reussi:
            arme = Arme(sort, ARMES_A_DISTANCE, formule, Portee.MOYENNE)
            self._infliger(lanceur, arme, test.degre, cible, BonusMajeure.DE_SUPPLEMENTAIRE, rapport)
        return rapport

    def appliquer_degats(self, victime: Combattant, degats: int) -> RapportBlessure:
        """Retire des PV et applique blessure grave, mort instantanée et agonie (REGLES.md 7.6)."""
        return blesser(self.des, self.curseur, victime, degats)

    # --- Après les coups ---------------------------------------------------------------

    def stabiliser(self, soigneur: Combattant, mourant: Combattant) -> Resultat:
        """Un jet de Médecine (action simple) pour stabiliser un mourant."""
        if mourant.fiche.etat is not Etat.MOURANT:
            raise ActionImpossible(f"{mourant.nom} n'est pas mourant.")
        self._agir(soigneur, TypeAction.SIMPLE)
        resultat = tester(self.des, soigneur.valeur("Médecine"))
        soigneur.cocher("Médecine", resultat)
        if resultat.reussi:
            mourant.fiche.etat = Etat.STABLE
        return resultat

    def fin_de_round(self) -> list[tuple[str, Resultat]]:
        """Les mourants font leur test de Constitution, puis on passe au round suivant.

        Sursis : celui qui vient de tomber ne fait son premier test qu'à la fin du round suivant.
        """
        tests = []
        for combattant in self.ordre:
            fiche = combattant.fiche
            if combattant.sursis:
                combattant.sursis = False
            elif fiche.etat is Etat.MOURANT:
                test = tester(self.des, fiche.carac(Caracteristique.CONSTITUTION))
                tests.append((combattant.nom, test))
                if not test.reussi:
                    fiche.etat = Etat.MORT
            combattant.budget = BudgetRound()
            combattant.defenses_ce_round = 0
            combattant.vise = combattant.a_vise = False  # la visée ne vaut que pour le round où elle est prise
            for effet in combattant.effets:
                if not effet.persistant and effet.rounds is not None:
                    effet.rounds -= 1
            combattant.effets = [e for e in combattant.effets if e.persistant or e.rounds is None or e.rounds > 0]
            if self.round == 1:
                combattant.surpris = False
        self.fumee = max(0, self.fumee - 1)
        self.round += 1
        self.actif = self._prochain(0)
        return tests

    def actifs(self, camp: str) -> list[Combattant]:
        return [c for c in self.ordre if c.camp == camp and c.conscient]


def blesser(des: Des, curseur: Curseur, victime: Combattant, degats: int) -> RapportBlessure:
    """Retire des PV et applique blessure grave, mort instantanée et agonie (REGLES.md 7.6),
    en combat comme dehors (un accident de la route)."""
    fiche = victime.fiche
    rapport = RapportBlessure(victime.nom, degats, fiche.pv, fiche.pv)
    if degats <= 0:
        rapport.etat = fiche.etat
        return rapport
    if victime.drone:  # un drone n'a ni blessure grave ni agonie : à 0, c'est une épave
        fiche.pv = max(0, fiche.pv - degats)
        victime.drone.structure = fiche.pv
        if fiche.pv == 0:
            fiche.etat = Etat.MORT
        rapport.pv_apres, rapport.etat = fiche.pv, fiche.etat
        return rapport

    base = fiche.pv_max_base
    if curseur.mort_instantanee and degats >= base:
        fiche.pv = 0
        fiche.etat = Etat.MORT
        rapport.pv_apres, rapport.etat, rapport.mort_instantanee = 0, Etat.MORT, True
        return rapport

    fiche.pv = max(0, fiche.pv - degats)
    if degats * 2 >= base:
        rapport.blessure_grave = True
        fiche.blessure_grave = True
        fiche.pv = min(fiche.pv, fiche.pv_max)
    if fiche.pv == 0:
        if fiche.etat not in (Etat.MORT, Etat.MOURANT):
            fiche.etat = Etat.MOURANT
            victime.sursis = True
    elif rapport.blessure_grave and fiche.etat is Etat.ACTIF:
        test = tester(des, fiche.carac(Caracteristique.CONSTITUTION))
        rapport.test_constitution = test
        if not test.reussi:
            fiche.etat = Etat.INCONSCIENT
    rapport.pv_apres = fiche.pv
    rapport.etat = fiche.etat
    return rapport


def subir_iem(combattant: Combattant, source: str) -> list[str]:
    """Une IEM coupe l'électronique d'un combattant pendant 1 round (REGLES.md 7.10) : ses implants
    (bonus, armure, armes implantées) et les bonus électroniques de ses armes. Un implant ne grille
    jamais ; des yeux cybernétiques coupés l'aveuglent. Le blindage IEM le protège de tout."""
    if combattant.drone:
        if combattant.blindage_iem:
            combattant.effets.append(EffetEnCours(source, NATURE_IEM, 0, 1))
            return ["drone blindé : coupé 1 round"]
        combattant.fiche.pv = combattant.drone.structure = 0
        combattant.fiche.etat = Etat.MORT
        return ["drone grillé : une épave, à réparer en atelier"]
    if combattant.blindage_iem:
        return ["blindage IEM : aucun effet"]
    combattant.effets.append(EffetEnCours(source, NATURE_IEM, 0, 1))
    textes = ["électronique coupée 1 round : implants sans effet, viseurs et armes intelligentes sans bonus"]
    if isinstance(combattant.fiche, Personnage) and any(p["nom"] == YEUX_CYBERNETIQUES
                                                       for p in combattant.fiche.implants):
        combattant.effets.append(EffetEnCours(source, "entrave", MALUS_AVEUGLE, 1))
        textes.append(f"yeux cybernétiques coupés : aveuglé, {MALUS_AVEUGLE} à tout pendant 1 round")
    return textes


def iem_sur_engin(engin: Engin) -> list[str]:
    """Une IEM sur un véhicule (REGLES.md 7.10) : un cran de vitesse et le pilote automatique coupés
    1 round. Un véhicule aérien demande en plus un test de Pilotage difficile à son pilote (le MJ
    le fait passer avec piloter). Le blindage IEM le protège ; un véhicule mécanique ne craint rien."""
    from aria.vehicules import BLINDAGE_IEM
    if not engin.modele.electronique:
        return [f"{engin.nom} : mécanique, rien ne se passe"]
    if engin.modele.a(BLINDAGE_IEM):
        return [f"{engin.nom} : blindage IEM, aucun effet"]
    engin.coupe = 1
    textes = [f"{engin.nom} : électronique coupée 1 round, un cran de vitesse en moins, pilote automatique coupé"]
    if engin.modele.type == "aérien":
        textes.append(f"{engin.nom} : véhicule aérien, test de Pilotage difficile pour le pilote, sinon l'accident")
    return textes


def laisser_pour_mort(combattant: Combattant):
    """Dépense un point de destin pour transformer une mort en « laissé pour mort » (REGLES.md 7.7)."""
    fiche = combattant.fiche
    if fiche.etat is not Etat.MORT:
        raise ActionImpossible(f"{combattant.nom} n'est pas mort.")
    if fiche.points_destin <= 0:
        raise ActionImpossible(f"{combattant.nom} n'a plus de point de destin.")
    fiche.points_destin -= 1
    fiche.pv = 0
    fiche.etat = Etat.STABLE
