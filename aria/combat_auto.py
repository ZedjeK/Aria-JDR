"""Le combat à pied mené par le code : le mode, l'IA des ennemis, la boucle des tours et la fin du combat.

Référence : REGLES.md 7.8. L'IA est une fonction de décision (`prochaine_action`) qui lit l'état du combat et
renvoie la prochaine action de celui dont c'est le tour ; la boucle (`CombatAuto`) l'exécute, jusqu'à ce que
l'action ne soit plus possible ou qu'il ne reste rien à faire, puis passe la main. Le moteur (`aria.combat`)
lance tous les dés : ici, seul le tirage de la cible en lance un.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum

from aria.combat import (
    ActionImpossible,
    BonusMajeure,
    Combat,
    Combattant,
    Couvert,
    Decor,
    Defense,
    FichePnj,
    Moral,
    RapportAttaque,
    RapportMoral,
    RapportSauvegarde,
    TOURS_AVANT_DE_FUIR,
    TypeAction,
)
from aria import deplacements
from aria.equipement import Recharge
from aria.grille import Abri
from aria.resolution import Resultat

ROUNDS_MAX = 30  # au-delà, le combat s'essouffle : personne n'arrive à finir l'autre
ACTIONS_MAX_PAR_TOUR = 8  # garde-fou : un tour légal en compte 3 au plus
ATTAQUANTS_MAX_PAR_CIBLE = 2
POIDS_CIBLE, POIDS_CIBLE_FAIBLE, POIDS_REVANCHE = 1, 2, 1  # REGLES.md 7.8 : 1, +2 sous la moitié des PV, +1 revanche


# --- Le mode du combat ------------------------------------------------------------------------

class ModeCombat(Enum):
    """Qui mène le combat : le code (à pied), ou le MJ avec les outils du moteur (classique)."""

    A_PIED = "à pied"
    CLASSIQUE = "classique"


def choisir_mode(combattants: Iterable[Combattant], avec_vehicule: bool = False) -> ModeCombat:
    """Le mode d'un combat, choisi par le moteur à son ouverture (REGLES.md 7.8). Le combat à pied ne mène que les
    armes et les sorts à une seule cible : un drone, une arme de zone en main, un lanceur de sorts parmi les PNJ ou
    un véhicule le laissent au MJ. (Les sorts du joueur, eux, sont l'affaire de son menu.)"""
    if avec_vehicule:
        return ModeCombat.CLASSIQUE
    for c in combattants:
        if c.drone or c.operateur or (c.arme and c.arme.zone):
            return ModeCombat.CLASSIQUE
        if isinstance(c.fiche, FichePnj) and c.fiche.sorts:
            return ModeCombat.CLASSIQUE
    return ModeCombat.A_PIED


# --- Les camps --------------------------------------------------------------------------------

def _cote(combattant: Combattant) -> str | None:
    """Deux côtés : les ennemis contre le joueur et ses alliés ; les neutres ne se battent avec personne."""
    if combattant.camp == "neutres":
        return None
    return "ennemis" if combattant.camp == "ennemis" else "joueurs"


def _en_lice(combat: Combat, cote: str) -> list[Combattant]:
    return [c for c in combat.ordre if _cote(c) == cote and c.conscient and not c.hors_combat]


def _adversaires(combat: Combat, combattant: Combattant) -> list[Combattant]:
    """Ceux qu'il peut encore frapper : conscients et pas partis ni rendus (un fuyard, oui)."""
    cote = _cote(combattant)
    if cote is None:
        return []
    return _en_lice(combat, "joueurs" if cote == "ennemis" else "ennemis")


# --- La mémoire du round ----------------------------------------------------------------------

class Registre:
    """Ce que l'IA retient : qui a attaqué qui ce round (pas plus de deux attaquants par cible), et qui a blessé qui
    au round précédent (la revanche)."""

    def __init__(self):
        self.round = 1
        self.attaquants: dict[Combattant, set[Combattant]] = {}
        self.blessures: set[tuple[Combattant, Combattant]] = set()  # (qui a blessé, qui a été blessé), ce round
        self.blessures_precedentes: set[tuple[Combattant, Combattant]] = set()

    def ouvrir(self, round_: int):
        """À appeler au début de chaque tour : change de round si besoin."""
        if round_ != self.round:
            self.blessures_precedentes = self.blessures
            self.blessures, self.attaquants, self.round = set(), {}, round_

    def noter(self, attaquant: Combattant, cible: Combattant, rapport: RapportAttaque):
        self.attaquants.setdefault(cible, set()).add(attaquant)
        if rapport.blessure and rapport.blessure.degats > 0:
            if rapport.touche == cible.nom:
                self.blessures.add((attaquant, cible))
            else:  # une riposte : c'est l'attaquant qui a pris le coup
                self.blessures.add((cible, attaquant))

    def a_blesse_au_round_precedent(self, blesseur: Combattant, blesse: Combattant) -> bool:
        return (blesseur, blesse) in self.blessures_precedentes


# --- L'IA : la prochaine action ----------------------------------------------------------------

class Geste(Enum):
    FUIR = "fuir"
    RAMASSER = "ramasser son arme"
    DEBLOQUER = "débloquer son arme"
    RECHARGER = "recharger"
    COUVERT = "se mettre à couvert"
    VISER = "viser"
    ATTAQUER = "attaquer"
    SE_DEPLACER = "se déplacer"  # sur la carte (REGLES.md 7.11)


@dataclass(frozen=True)
class Action:
    geste: Geste
    cible: Combattant | None = None
    vers: tuple[int, int] | None = None  # sur la carte : la case où il va (se déplacer, fuir)


class Intention(Enum):
    """Ce qu'un PNJ veut faire ce round : la liste fermée dont le LLM choisit, quand il planifie (REGLES.md 7.8)."""

    ATTAQUER = "attaquer"
    S_ABRITER = "s'abriter"
    VISER = "viser"
    FUIR = "fuir"
    SE_RENDRE = "se rendre"

    @property
    def veut_une_cible(self) -> bool:
        return self in (Intention.ATTAQUER, Intention.VISER)


@dataclass(frozen=True)
class Choix:
    intention: Intention
    cible: Combattant | None = None


Plan = dict[Combattant, Choix]  # le choix de chaque PNJ pour le round ; un PNJ absent suit l'IA par défaut
INAPPLICABLE = object()  # l'intention ne peut pas se jouer ici : l'IA par défaut décide


def _action_de_recharge(combattant: Combattant) -> TypeAction:
    return TypeAction.MINEURE if combattant.arme.chargeur.recharge is Recharge.MINEURE else TypeAction.SIMPLE


def poids_des_cibles(combat: Combat, combattant: Combattant, registre: Registre) -> list[tuple[Combattant, int]]:
    """Les cibles possibles et leur poids (REGLES.md 7.8) : 1 par cible consciente, +2 si elle est sous la moitié
    de ses PV, +1 si elle l'a blessé au round précédent. Pas plus de deux attaquants par cible et par round : une
    cible déjà prise à deux n'est plus choisie, sauf s'il n'y a plus que des cibles prises à deux (ou une seule)."""
    adversaires = _adversaires(combat, combattant)
    libres = [c for c in adversaires if len(registre.attaquants.get(c, ())) < ATTAQUANTS_MAX_PAR_CIBLE]
    poids = []
    for cible in libres or adversaires:
        p = POIDS_CIBLE
        if cible.fiche.pv * 2 < cible.fiche.pv_max_base:
            p += POIDS_CIBLE_FAIBLE
        if registre.a_blesse_au_round_precedent(cible, combattant):
            p += POIDS_REVANCHE
        poids.append((cible, p))
    return poids


def tirer_la_cible(combat: Combat, poids: list[tuple[Combattant, int]]) -> Combattant | None:
    """Un tirage pondéré ; un seul candidat se choisit sans lancer de dé."""
    if not poids:
        return None
    if len(poids) == 1:
        return poids[0][0]
    tirage = combat.des.lancer(sum(p for _, p in poids))
    for cible, p in poids:
        tirage -= p
        if tirage <= 0:
            return cible
    return poids[-1][0]  # inatteignable : la somme des poids est le maximum du tirage


def _suivre_le_choix(combat: Combat, combattant: Combattant, registre: Registre, choix: Choix,
                     interdits: frozenset[Geste], tireur: bool) -> "Action | None | object":
    """Traduit une intention du plan en action, dans le budget du tour. None : l'intention est accomplie, le tour
    est fini ; INAPPLICABLE : elle ne se joue pas ici (cible morte ou déjà prise à deux, pas d'abri…), l'IA décide.
    Fuir et se rendre se jouent avant le tour, par le moral."""
    budget, intention = combattant.budget, choix.intention

    def possible(geste: Geste, type_action: TypeAction) -> bool:
        return geste not in interdits and budget.peut(type_action)

    if intention in (Intention.FUIR, Intention.SE_RENDRE):
        return INAPPLICABLE
    if intention is Intention.S_ABRITER and combat.carte is not None:
        menace = _menace_la_plus_proche(combat, combattant)
        if not tireur or menace is None:
            return INAPPLICABLE
        if deplacements.abri_contre(combat, combat.carte.position(combattant), menace) is not Abri.AUCUN:
            return None  # déjà à couvert d'elle : l'intention est accomplie
        if combattant.a_vise or not possible(Geste.SE_DEPLACER, TypeAction.DEPLACEMENT):
            return INAPPLICABLE
        vers = deplacements.a_couvert_contre(combat, combattant, menace)
        return Action(Geste.SE_DEPLACER, vers=vers) if vers else INAPPLICABLE
    if intention is Intention.S_ABRITER:
        if not tireur or combat.decor is Decor.DEGAGE:
            return INAPPLICABLE
        if combattant.couvert is Couvert.AUCUN and possible(Geste.COUVERT, TypeAction.DEPLACEMENT):
            return Action(Geste.COUVERT)
        return None
    # Attaquer ou viser : la cible choisie, si elle est encore légale (en lice, et pas déjà prise à deux attaquants)
    cible = choix.cible
    if cible is None or cible not in {c for c, _ in poids_des_cibles(combat, combattant, registre)}:
        return INAPPLICABLE
    if combat.raison_de_ne_pas_attaquer(combattant, cible):  # sur la carte : hors de portée ou sans ligne de tir
        return INAPPLICABLE
    if intention is Intention.VISER:
        if not tireur:
            return INAPPLICABLE
        if (not combattant.vise and not budget.utilise[TypeAction.DEPLACEMENT]
                and possible(Geste.VISER, TypeAction.MINEURE)):
            return Action(Geste.VISER)
    return Action(Geste.ATTAQUER, cible) if possible(Geste.ATTAQUER, TypeAction.SIMPLE) else None


def prochaine_action(combat: Combat, combattant: Combattant, registre: Registre,
                     interdits: frozenset[Geste] = frozenset(), choix: Choix | None = None) -> Action | None:
    """La prochaine action de celui dont c'est le tour, ou None : il a fini (REGLES.md 7.8, dans cet ordre).

    Le moral se teste avant, par `Combat.tester_moral`. Un fuyard court, sans rien d'autre. Sinon : l'état de son
    arme (la reprendre, la débloquer, recharger), le couvert pour un tireur, la visée s'il est à couvert sans avoir
    bougé, l'attaque. `interdits` : les gestes que le moteur vient de refuser (par exemple plus de chargeur).
    `choix` : l'intention du plan du round pour ce PNJ ; l'état de son arme passe avant, et si elle ne peut pas se
    jouer, l'IA décide comme sans plan."""
    budget = combattant.budget
    if not combat.peut_agir(combattant):  # parti ou rendu, à terre, surpris au premier round
        return None

    def possible(geste: Geste, type_action: TypeAction) -> bool:
        return geste not in interdits and budget.peut(type_action)

    if combattant.moral is Moral.EN_FUITE:
        if not possible(Geste.FUIR, TypeAction.DEPLACEMENT):
            return None
        if combat.carte is None:
            return Action(Geste.FUIR)
        vers = deplacements.vers_le_bord(combat, combattant)  # il gagne le bord de la carte (REGLES.md 7.11)
        return Action(Geste.FUIR, vers=vers) if vers else None

    arme = combattant.arme
    if arme is None and combattant.arme_lachee:
        return Action(Geste.RAMASSER) if possible(Geste.RAMASSER, TypeAction.MINEURE) else None
    if arme is not None and combattant.arme_enrayee is arme:
        return Action(Geste.DEBLOQUER) if possible(Geste.DEBLOQUER, TypeAction.MINEURE) else None
    en_main = combattant.arme_en_main
    tireur = not en_main.corps_a_corps
    if tireur and en_main.munitions and combattant.munitions_restantes() == 0:
        return (Action(Geste.RECHARGER)
                if possible(Geste.RECHARGER, _action_de_recharge(combattant)) else None)

    if choix is not None:
        suite = _suivre_le_choix(combat, combattant, registre, choix, interdits, tireur)
        if suite is not INAPPLICABLE:
            return suite
    if combat.carte is not None:
        return _sur_la_carte(combat, combattant, registre, tireur, possible)
    if not possible(Geste.ATTAQUER, TypeAction.SIMPLE):
        return None
    if tireur:
        a_couvert = combattant.couvert is not Couvert.AUCUN
        if (not a_couvert and combat.decor is not Decor.DEGAGE and not combattant.a_vise
                and possible(Geste.COUVERT, TypeAction.DEPLACEMENT)):
            return Action(Geste.COUVERT)
        if (a_couvert and not budget.utilise[TypeAction.DEPLACEMENT] and not combattant.vise
                and possible(Geste.VISER, TypeAction.MINEURE)):
            return Action(Geste.VISER)
    cible = tirer_la_cible(combat, poids_des_cibles(combat, combattant, registre))
    return Action(Geste.ATTAQUER, cible) if cible else None


def _menace_la_plus_proche(combat: Combat, combattant: Combattant) -> Combattant | None:
    adversaires = [a for a in _adversaires(combat, combattant) if a in combat.carte.positions]
    return min(adversaires, key=lambda a: combat.carte.ecart(combattant, a), default=None)


def _sur_la_carte(combat: Combat, combattant: Combattant, registre: Registre, tireur: bool,
                  possible: Callable[[Geste, TypeAction], bool]) -> Action | None:
    """L'IA sur la carte (REGLES.md 7.11), une fois l'état de son arme réglé. Une cible qu'il peut toucher d'ici :
    un tireur se poste d'abord à couvert d'elle s'il le peut sans la perdre de vue, vise s'il n'a pas bougé, puis
    tire ; un bretteur frappe. Sinon il se rapproche : un bretteur jusqu'au contact (deux déplacements s'il le faut),
    un tireur jusqu'à une position de tir, à couvert si possible."""
    poids = [(c, p) for c, p in poids_des_cibles(combat, combattant, registre) if c in combat.carte.positions]
    if not poids:
        return None
    budget = combattant.budget
    peut_bouger = not combattant.a_vise and possible(Geste.SE_DEPLACER, TypeAction.DEPLACEMENT)
    a_portee = [(c, p) for c, p in poids if combat.raison_de_ne_pas_attaquer(combattant, c) is None]
    if a_portee and not possible(Geste.ATTAQUER, TypeAction.SIMPLE):
        return None  # il a déjà frappé et quelqu'un reste à sa portée : il garde sa place
    if a_portee:
        cible = tirer_la_cible(combat, a_portee)
        if tireur:
            ici = combat.carte.position(combattant)
            a_couvert = deplacements.abri_contre(combat, ici, cible) is not Abri.AUCUN
            if not a_couvert and peut_bouger and not budget.utilise[TypeAction.DEPLACEMENT]:
                vers = deplacements.a_couvert_contre(combat, combattant, cible, garder=cible)
                if vers:
                    return Action(Geste.SE_DEPLACER, vers=vers)
            if (a_couvert and not budget.utilise[TypeAction.DEPLACEMENT] and not combattant.vise
                    and possible(Geste.VISER, TypeAction.MINEURE)):
                return Action(Geste.VISER)
        return Action(Geste.ATTAQUER, cible)
    if not peut_bouger:
        return None
    cible = tirer_la_cible(combat, poids)
    if tireur:
        vers = deplacements.position_de_tir(combat, combattant, cible) or deplacements.au_plus_pres(combat, combattant, cible)
    else:
        vers = deplacements.vers_le_contact(combat, combattant, cible) or deplacements.au_plus_pres(combat, combattant, cible)
    return Action(Geste.SE_DEPLACER, vers=vers) if vers else None


class Reactions:
    """Ce que le joueur tranche lui-même pendant les actions des autres : sa défense au corps à corps, et le bonus de
    ses réussites majeures. Par défaut, rien : le code décide (la meilleure défense, +1 dé)."""

    def defense(self, attaquant: Combattant, cible: Combattant) -> Defense | None:
        """None : le code choisit."""
        return None

    def bonus_majeure(self, source: Combattant, victime: Combattant, options: list[BonusMajeure]) -> BonusMajeure:
        return BonusMajeure.DE_SUPPLEMENTAIRE


def executer(combat: Combat, combattant: Combattant, action: Action,
             reactions: Reactions | None = None) -> RapportAttaque | None:
    """Fait faire l'action par le moteur, qui peut la refuser (ActionImpossible). Renvoie le rapport d'une attaque."""
    geste = action.geste
    if geste in (Geste.FUIR, Geste.SE_DEPLACER):
        combat.deplacer(combattant, action.vers)  # sans carte, vers est None : un déplacement sans destination
    elif geste is Geste.RAMASSER:
        combat.degainer(combattant, combattant.arme_lachee)
    elif geste is Geste.DEBLOQUER:
        combat.debloquer(combattant)
    elif geste is Geste.RECHARGER:
        combat.recharger(combattant)
    elif geste is Geste.COUVERT:
        combat.se_mettre_a_couvert(combattant)
    elif geste is Geste.VISER:
        combat.viser(combattant)
    else:
        cible = action.cible
        defense = None
        if reactions and combattant.arme_en_main.corps_a_corps and combat.peut_se_defendre(cible):
            defense = reactions.defense(combattant, cible)
        return combat.attaquer(combattant, cible, defense=defense or Combat.defense_par_defaut(cible),
                               bonus_majeure=reactions.bonus_majeure if reactions else BonusMajeure.DE_SUPPLEMENTAIRE)
    return None


# --- La boucle des tours ------------------------------------------------------------------------

class Fin(Enum):
    EN_COURS = "en cours"
    VICTOIRE = "victoire"  # plus aucun ennemi en lice : à terre, rendus ou partis
    DEFAITE = "défaite"  # plus personne en lice du côté du joueur
    ESSOUFFLE = "essoufflé"  # ROUNDS_MAX rounds sans issue


@dataclass
class Evenement:
    action: Action
    attaque: RapportAttaque | None = None


@dataclass
class RapportTour:
    """Un tour joué par le code, que le MJ raconte."""

    qui: Combattant
    round: int
    moral: RapportMoral | None = None
    evenements: list[Evenement] = field(default_factory=list)
    mourants: list[tuple[str, Resultat]] = field(default_factory=list)  # les tests de la fin du round, s'il se clôt
    sauvegardes: list[RapportSauvegarde] = field(default_factory=list)  # les effets persistants du tour suivant

    @property
    def passe(self) -> bool:
        """Il n'a rien fait de ce tour (hors son test de moral)."""
        return not self.evenements


def _est_pnj(combattant: Combattant) -> bool:
    return isinstance(combattant.fiche, FichePnj)


class CombatAuto:
    """La boucle d'un combat à pied. `mene` dit quels combattants l'IA joue : les PNJ par défaut, le joueur
    jouant son tour lui-même ; le simulateur lui confie tout le monde."""

    def __init__(self, combat: Combat, mene: Callable[[Combattant], bool] = _est_pnj,
                 reactions: Reactions | None = None,
                 planificateur: Callable[[Combat, Registre], Plan | None] | None = None):
        """`planificateur(combat, registre)` : donne le plan du round (un choix par PNJ), appelé une fois par round, au
        premier tour d'un PNJ ; None ou un PNJ absent du plan : l'IA par défaut joue, comme sans planificateur."""
        self.combat = combat
        self.mene = mene
        self.reactions = reactions
        self.planificateur = planificateur
        self.plan: Plan = {}
        self._round_planifie = 0
        self.registre = Registre()

    def fin(self) -> Fin:
        """La fin du combat, détectée par le code. Un ennemi qui fuit est encore en lice jusqu'à ce qu'il parte."""
        if not _en_lice(self.combat, "joueurs"):
            return Fin.DEFAITE
        if not _en_lice(self.combat, "ennemis"):
            return Fin.VICTOIRE
        return Fin.ESSOUFFLE if self.combat.round > ROUNDS_MAX else Fin.EN_COURS

    def jouer_le_tour(self) -> RapportTour:
        """Joue le tour de celui à qui c'est le tour : son moral, ses actions, puis la main passe au suivant."""
        combat = self.combat
        combattant = combat.au_tour_de
        if combattant is None:
            raise ActionImpossible("Plus personne ne peut agir.")
        self.registre.ouvrir(combat.round)
        if self.planificateur and self._round_planifie != combat.round:
            self._round_planifie = combat.round
            self.plan = self.planificateur(combat, self.registre) or {}
        choix = self.plan.get(combattant)
        rapport = RapportTour(combattant, combat.round, moral=combat.tester_moral(combattant))
        if choix and choix.intention in (Intention.FUIR, Intention.SE_RENDRE):
            rapport.moral = self._partir_de_son_plein_gre(combattant, choix.intention) or rapport.moral
        interdits: set[Geste] = set()
        while len(rapport.evenements) < ACTIONS_MAX_PAR_TOUR:
            action = prochaine_action(combat, combattant, self.registre, frozenset(interdits), choix)
            if action is None:
                break
            try:
                attaque = executer(combat, combattant, action, self.reactions)
            except ActionImpossible:
                interdits.add(action.geste)  # le moteur refuse : l'IA cherche autre chose
                continue
            if attaque:
                self.registre.noter(combattant, action.cible, attaque)
            rapport.evenements.append(Evenement(action, attaque))
        rapport.mourants, rapport.sauvegardes = self.finir_le_tour()
        return rapport

    def _partir_de_son_plein_gre(self, combattant: Combattant, intention: Intention):
        """Le plan du round fait fuir ou rendre un PNJ plus tôt, sans test, mais seulement si un déclencheur de moral
        est vrai (REGLES.md 7.8). Il ne peut jamais retenir quelqu'un que le test de moral a fait craquer."""
        if combattant.moral is not Moral.NORMAL or not isinstance(combattant.fiche, FichePnj):
            return None
        raisons = self.combat.declencheurs_de_moral(combattant)
        if not raisons:
            return None
        combattant.moral = Moral.EN_FUITE if intention is Intention.FUIR else Moral.RENDU
        if combattant.moral is Moral.EN_FUITE:
            combattant.tours_avant_de_partir = TOURS_AVANT_DE_FUIR
        return RapportMoral(combattant.nom, raisons, None, combattant.moral)

    def finir_le_tour(self) -> tuple[list[tuple[str, Resultat]], list[RapportSauvegarde]]:
        """Passe la main : renvoie les tests des mourants si le round se clôt, et les effets persistants qui
        mordent au début du tour suivant."""
        mourants = self.combat.fin_de_tour()
        sauvegardes, self.combat.sauvegardes = self.combat.sauvegardes, []
        return mourants, sauvegardes

    def avancer(self, apres_chaque_tour: Callable[[RapportTour], None] | None = None) -> list[RapportTour]:
        """Joue les tours que l'IA mène, jusqu'au tour de quelqu'un qu'elle ne mène pas (le joueur) ou la fin du
        combat. `apres_chaque_tour` : appelée avec le rapport de chaque tour dès qu'il est joué."""
        rapports = []
        while self.fin() is Fin.EN_COURS:
            combattant = self.combat.au_tour_de
            if combattant is None or not self.mene(combattant):
                break
            rapports.append(self.jouer_le_tour())
            if apres_chaque_tour:
                apres_chaque_tour(rapports[-1])
        return rapports
