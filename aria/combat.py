"""Le combat : initiative, budget d'actions, attaques, dégâts, blessures et points de destin.

Référence : REGLES.md section 7. Le moteur lance tous les dés, y compris ceux des
ennemis ; le MJ choisit seulement les actions et raconte les rapports renvoyés.
"""

from dataclasses import dataclass, field
from enum import Enum

from aria.des import Des
from aria.equipement import CORPS_A_CORPS, Arme, Armure, Portee, Propriete, Recharge, formule_degats
from aria.personnage import MALUS_BLESSURE_GRAVE, Caracteristique, Etat, Personnage
from aria.reglages import Curseur
from aria.resolution import Degre, Issue, Resultat, opposer, tester

MAINS_NUES = Arme("Mains nues", CORPS_A_CORPS, "1d3", Portee.CONTACT)
MALUS_DEFENSE_SUPPLEMENTAIRE = -20
BONUS_VISER = 20


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

    def utiliser(self, action: TypeAction):
        if not self.peut(action):
            raise ActionImpossible(f"Le budget du round ne permet plus : {action.value}.")
        self.utilise[action] += 1


@dataclass
class FichePnj:
    """Le profil simplifié d'un ennemi (REGLES.md 7.8). Un seul pourcentage sert à tout le combat."""

    nom: str
    combat: int
    pv_max_base: int
    dexterite: int = 50
    constitution: int = 50
    perception: int = 25
    pv: int | None = None
    etat: Etat = Etat.ACTIF
    blessure_grave: bool = False
    points_destin: int = 0

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
        return self.perception if nom == "Perception" else self.combat


class Combattant:
    """Un participant au combat : un personnage ou un ennemi, avec son équipement en main."""

    def __init__(self, fiche: Personnage | FichePnj, camp: str, arme: Arme | None = None, armure: Armure | None = None):
        self.fiche = fiche
        self.camp = camp
        self.arme = arme
        self.armure = armure
        self.munitions: dict[Arme, int] = {}
        self.budget = BudgetRound()
        self.defenses_ce_round = 0
        self.vise = False
        self.surpris = False
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
            self.munitions[arme] = arme.munitions.capacite

    def munitions_restantes(self) -> int | None:
        arme = self.arme
        return self.munitions.get(arme) if arme and arme.munitions else None

    def valeur(self, competence: str) -> int:
        """La compétence avec les malus subis : blessure grave et armure."""
        valeur = self.fiche.competence(competence)
        if self.fiche.blessure_grave:
            valeur += MALUS_BLESSURE_GRAVE
        if self.armure:
            valeur += self.armure.malus_pour(competence)
        return valeur

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


def tester_embuscade(des: Des, perception_victimes: int, discretion_agresseurs: int) -> bool:
    """Perception des victimes contre Discrétion des agresseurs. Vrai si les victimes sont surprises.

    Comme pour une esquive, une égalité profite aux victimes.
    """
    discretion = tester(des, discretion_agresseurs)
    perception = tester(des, perception_victimes)
    return opposer(discretion, perception, esquive=True) is Issue.ATTAQUANT


class Combat:
    """Un combat en cours. Les méthodes renvoient des rapports que le MJ raconte."""

    def __init__(self, des: Des, combattants: list[Combattant], curseur: Curseur = Curseur.STANDARD,
                 surpris: list[Combattant] = ()):
        self.des = des
        self.curseur = curseur
        self.round = 1
        # Initiative : Dextérité décroissante, Perception pour départager (REGLES.md 7.1)
        self.ordre = sorted(
            combattants,
            key=lambda c: (c.fiche.carac(Caracteristique.DEXTERITE), c.fiche.competence("Perception")),
            reverse=True,
        )
        for combattant in surpris:
            combattant.surpris = True

    # --- Ce que chacun peut faire --------------------------------------------------

    def peut_agir(self, combattant: Combattant) -> bool:
        return combattant.conscient and not (combattant.surpris and self.round == 1)

    def _agir(self, combattant: Combattant, action: TypeAction):
        if not self.peut_agir(combattant):
            raise ActionImpossible(f"{combattant.nom} ne peut pas agir.")
        combattant.budget.utiliser(action)

    def deplacer(self, combattant: Combattant):
        if combattant.vise:
            raise ActionImpossible(f"{combattant.nom} a visé : il ne peut plus se déplacer ce round.")
        self._agir(combattant, TypeAction.DEPLACEMENT)

    def viser(self, combattant: Combattant):
        """+20 au tir de ce round (action mineure), seulement sans se déplacer ce round."""
        if combattant.budget.utilise[TypeAction.DEPLACEMENT]:
            raise ActionImpossible(f"{combattant.nom} s'est déplacé : il ne peut plus viser ce round.")
        self._agir(combattant, TypeAction.MINEURE)
        combattant.vise = True

    def degainer(self, combattant: Combattant, arme: Arme | None):
        """Prendre une autre arme en main, ou la ranger avec None (action mineure)."""
        self._agir(combattant, TypeAction.MINEURE)
        if arme and arme not in combattant.munitions:
            combattant._charger(arme)
        combattant.arme = arme

    def recharger(self, combattant: Combattant):
        arme = combattant.arme
        if not arme or not arme.munitions:
            raise ActionImpossible(f"{combattant.nom} n'a rien à recharger.")
        action = TypeAction.MINEURE if arme.munitions.recharge is Recharge.MINEURE else TypeAction.SIMPLE
        self._agir(combattant, action)
        combattant.munitions[arme] = arme.munitions.capacite

    # --- L'attaque ---------------------------------------------------------------------

    def attaquer(
        self,
        attaquant: Combattant,
        cible: Combattant,
        defense: Defense | None = None,
        couvert: Couvert = Couvert.AUCUN,
        bonus_majeure: BonusMajeure = BonusMajeure.DE_SUPPLEMENTAIRE,
    ) -> RapportAttaque:
        """Une attaque complète : jets, défense, dégâts et blessures (REGLES.md 7.3 à 7.6)."""
        if cible.fiche.etat is Etat.MORT:
            raise ActionImpossible(f"{cible.nom} est déjà mort.")
        arme = attaquant.arme_en_main
        if not arme.corps_a_corps and arme.munitions and attaquant.munitions[arme] == 0:
            raise ActionImpossible(f"L'arme de {attaquant.nom} est vide : il faut recharger.")
        self._agir(attaquant, TypeAction.SIMPLE)

        modificateur = arme.bonus.jet
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

        attaque = tester(self.des, attaquant.valeur(arme.competence), combat=True, modificateur=modificateur)
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
                resultat_defense = tester(self.des, cible.valeur("Esquive"), combat=True, modificateur=malus)
            else:
                arme_riposte = cible.arme_de_melee
                resultat_defense = tester(
                    self.des, cible.valeur(CORPS_A_CORPS), combat=True, modificateur=malus + arme_riposte.bonus.jet
                )
            issue = opposer(attaque, resultat_defense, esquive=defense is Defense.ESQUIVE)
        else:
            issue = Issue.ATTAQUANT if attaque.reussi else Issue.PERSONNE

        rapport = RapportAttaque(attaquant.nom, cible.nom, attaque, resultat_defense, issue, effets=effets)
        if issue is Issue.ATTAQUANT:
            self._infliger(attaquant, arme, attaque.degre, cible, bonus_majeure, rapport)
        elif issue is Issue.DEFENSEUR and defense is Defense.RIPOSTE:
            self._infliger(cible, cible.arme_de_melee, resultat_defense.degre, attaquant, bonus_majeure, rapport)
        return rapport

    def _infliger(self, source: Combattant, arme: Arme, degre: Degre, victime: Combattant,
                  bonus_majeure: BonusMajeure, rapport: RapportAttaque):
        formule = formule_degats(arme, source.force)
        protection = victime.armure.protection_totale if victime.armure else 0
        if degre is Degre.CRITIQUE:
            # Dégâts maximum, et l'armure ne compte qu'à moitié
            brut = formule.maximum
            protection //= 2
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

    def appliquer_degats(self, victime: Combattant, degats: int) -> RapportBlessure:
        """Retire des PV et applique blessure grave, mort instantanée et agonie (REGLES.md 7.6)."""
        fiche = victime.fiche
        rapport = RapportBlessure(victime.nom, degats, fiche.pv, fiche.pv)
        if degats <= 0:
            rapport.etat = fiche.etat
            return rapport

        base = fiche.pv_max_base
        if self.curseur.mort_instantanee and degats >= base:
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
            if fiche.etat is not Etat.MORT:
                fiche.etat = Etat.MOURANT
        elif rapport.blessure_grave and fiche.etat is Etat.ACTIF:
            test = tester(self.des, fiche.carac(Caracteristique.CONSTITUTION))
            rapport.test_constitution = test
            if not test.reussi:
                fiche.etat = Etat.INCONSCIENT
        rapport.pv_apres = fiche.pv
        rapport.etat = fiche.etat
        return rapport

    # --- Après les coups ---------------------------------------------------------------

    def stabiliser(self, soigneur: Combattant, mourant: Combattant) -> Resultat:
        """Un jet de Médecine (action simple) pour stabiliser un mourant."""
        if mourant.fiche.etat is not Etat.MOURANT:
            raise ActionImpossible(f"{mourant.nom} n'est pas mourant.")
        self._agir(soigneur, TypeAction.SIMPLE)
        resultat = tester(self.des, soigneur.valeur("Médecine"))
        if resultat.reussi:
            mourant.fiche.etat = Etat.STABLE
        return resultat

    def fin_de_round(self) -> list[tuple[str, Resultat]]:
        """Les mourants font leur test de Constitution, puis on passe au round suivant."""
        tests = []
        for combattant in self.ordre:
            fiche = combattant.fiche
            if fiche.etat is Etat.MOURANT:
                test = tester(self.des, fiche.carac(Caracteristique.CONSTITUTION))
                tests.append((combattant.nom, test))
                if not test.reussi:
                    fiche.etat = Etat.MORT
            combattant.budget = BudgetRound()
            combattant.defenses_ce_round = 0
            combattant.vise = False  # la visée ne vaut que pour le round où elle est prise
            if self.round == 1:
                combattant.surpris = False
        self.round += 1
        return tests

    def actifs(self, camp: str) -> list[Combattant]:
        return [c for c in self.ordre if c.camp == camp and c.conscient]


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
