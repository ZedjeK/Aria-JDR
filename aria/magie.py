"""La magie : puissance, effets, domaines, et le lancer d'un sort (REGLES.md 10).

Un sort imite une mécanique que le moteur connaît déjà : une attaque, un soin, une armure,
un bonus ou un malus. Il ne peut donc jamais faire plus que ce que le moteur sait arbitrer.
Le MJ choisit un sort parmi ceux que le lanceur connaît ; le moteur lance le jet de Magie,
fait payer les PM et applique l'effet.
"""

import math
from dataclasses import dataclass, field
from enum import Enum

from aria.combat import ActionImpossible, Combat, Combattant, Couvert, EffetEnCours, RapportAttaque, TypeAction
from aria.des import Des
from aria.personnage import MAGIE, Etat, Personnage
from aria.progression import cocher
from aria.resolution import Degre, Difficulte, Resultat, tester
from aria.sante_mentale import payer_sante_mentale
from aria.temps import Moment


class Puissance(Enum):
    """La puissance fixe le coût et la difficulté (REGLES.md 10.2)."""

    MINEUR = "mineur"
    MODERE = "modéré"
    MAJEUR = "majeur"

    @property
    def cout(self) -> int:
        return {Puissance.MINEUR: 1, Puissance.MODERE: 3, Puissance.MAJEUR: 6}[self]

    @property
    def difficulte(self) -> Difficulte:
        return {Puissance.MINEUR: Difficulte.FACILE, Puissance.MODERE: Difficulte.NORMALE,
                Puissance.MAJEUR: Difficulte.DIFFICILE}[self]


class Effet(Enum):
    """Un sort a un seul effet (REGLES.md 10.3)."""

    ATTAQUE = "attaque"
    SOIN = "soin"
    PROTECTION = "protection"
    RENFORT = "renfort"
    ENTRAVE = "entrave"
    UTILITAIRE = "utilitaire"

    @property
    def nocif(self) -> bool:
        return self in (Effet.ATTAQUE, Effet.ENTRAVE)


class ProprieteSort(Enum):
    ZONE = "zone"  # 2 cibles proches, un seul jet
    PERSISTANT = "persistant"  # l'effet continue après le round du lancer
    SILENCIEUX = "silencieux"  # ni bruit ni geste visible


# Les valeurs de chaque effet selon la puissance (REGLES.md 10.3)
DES_ATTAQUE = {Puissance.MINEUR: "1d6", Puissance.MODERE: "2d6", Puissance.MAJEUR: "3d6"}
DES_SOIN = {Puissance.MINEUR: "1d3", Puissance.MODERE: "1d6", Puissance.MAJEUR: "2d6"}
PROTECTION = {Puissance.MINEUR: 1, Puissance.MODERE: 2, Puissance.MAJEUR: 3}
MODIFICATEUR = {Puissance.MINEUR: 10, Puissance.MODERE: 20, Puissance.MAJEUR: 20}
DUREE = {Puissance.MINEUR: 1, Puissance.MODERE: 1, Puissance.MAJEUR: None}  # en rounds ; None : tout le combat
AMPLEUR = {Puissance.MINEUR: "un petit effet", Puissance.MODERE: "un effet notable",
           Puissance.MAJEUR: "un effet spectaculaire"}

COUT_PROPRIETE = 1
DOMAINES_MIN, DOMAINES_MAX = 3, 6
SORTS_MIN, SORTS_MAX = 4, 6
IMPROVISATIONS_MIN, IMPROVISATIONS_MAX = 3, 5
DOMAINES_PAR_PERSO = 2
DEGATS_RETOURNES = "1d6"  # la maladresse d'un sort qui n'était pas nocif
# Une propriété n'a de sens que pour certains effets
PROPRIETES_PERMISES = {
    ProprieteSort.ZONE: {Effet.ATTAQUE, Effet.SOIN, Effet.PROTECTION, Effet.RENFORT, Effet.ENTRAVE},
    ProprieteSort.PERSISTANT: {Effet.ATTAQUE, Effet.RENFORT, Effet.ENTRAVE},
    ProprieteSort.SILENCIEUX: set(Effet),
}


class SortImpossible(ActionImpossible):
    """Le sort demandé n'est pas permis par les règles à ce moment-là."""


@dataclass(frozen=True)
class Sort:
    nom: str
    effet: Effet
    puissance: Puissance
    propriete: ProprieteSort | None = None
    description: str = ""
    improvisation: bool = False  # un usage libre du domaine : un cran plus difficile, modéré au plus
    domaine: str = ""

    @property
    def cout(self) -> int:
        return self.puissance.cout + (COUT_PROPRIETE if self.propriete else 0)

    @property
    def difficulte(self) -> Difficulte:
        difficulte = self.puissance.difficulte
        if self.improvisation:
            crans = list(Difficulte)
            difficulte = crans[crans.index(difficulte) + 1]
        return difficulte

    def a(self, propriete: ProprieteSort) -> bool:
        return self.propriete is propriete


@dataclass(frozen=True)
class Domaine:
    nom: str
    effets: frozenset[Effet]  # les effets que ce domaine autorise (la Guérison n'attaque pas)
    sorts: tuple[Sort, ...]
    improvisations: tuple[Sort, ...]
    description: str = ""

    @property
    def tous(self) -> tuple[Sort, ...]:
        return self.sorts + self.improvisations


# --- Vérifications ----------------------------------------------------------------------------

def _verifier_sort(sort: Sort, domaine: Domaine) -> list[str]:
    erreurs = []
    if not sort.nom.strip():
        erreurs.append(f"{domaine.nom} : un sort n'a pas de nom.")
    if sort.effet not in domaine.effets:
        erreurs.append(f"{sort.nom} : l'effet « {sort.effet.value} » n'est pas permis dans le domaine {domaine.nom}.")
    if sort.improvisation:
        if sort.puissance is Puissance.MAJEUR:
            erreurs.append(f"{sort.nom} : une improvisation est modérée au plus.")
        if sort.propriete:
            erreurs.append(f"{sort.nom} : une improvisation n'a jamais de propriété.")
    elif sort.propriete and sort.effet not in PROPRIETES_PERMISES[sort.propriete]:
        erreurs.append(f"{sort.nom} : la propriété « {sort.propriete.value} » ne va pas avec un effet "
                       f"« {sort.effet.value} ».")
    elif sort.a(ProprieteSort.PERSISTANT) and sort.effet is not Effet.ATTAQUE and DUREE[sort.puissance] is None:
        erreurs.append(f"{sort.nom} : un effet qui dure tout le combat ne peut pas être persistant.")
    return erreurs


def verifier_domaine(domaine: Domaine) -> list[str]:
    erreurs = []
    if not domaine.nom.strip():
        erreurs.append("Un domaine de magie n'a pas de nom.")
    if not domaine.effets:
        erreurs.append(f"Le domaine {domaine.nom} n'autorise aucun effet.")
    if not SORTS_MIN <= len(domaine.sorts) <= SORTS_MAX:
        erreurs.append(f"Le domaine {domaine.nom} a {len(domaine.sorts)} sorts appris, "
                       f"de {SORTS_MIN} à {SORTS_MAX} attendus.")
    if not IMPROVISATIONS_MIN <= len(domaine.improvisations) <= IMPROVISATIONS_MAX:
        erreurs.append(f"Le domaine {domaine.nom} a {len(domaine.improvisations)} improvisations, "
                       f"de {IMPROVISATIONS_MIN} à {IMPROVISATIONS_MAX} attendues.")
    for sort in domaine.tous:
        erreurs += _verifier_sort(sort, domaine)
    return erreurs


def verifier_domaines(domaines: tuple[Domaine, ...]) -> list[str]:
    """Les domaines d'un univers : de 3 à 6, et des noms de sorts uniques (le MJ les désigne par leur nom)."""
    erreurs = []
    if not DOMAINES_MIN <= len(domaines) <= DOMAINES_MAX:
        erreurs.append(f"Un univers a de {DOMAINES_MIN} à {DOMAINES_MAX} domaines de magie, pas {len(domaines)}.")
    vus: set[str] = set()
    for domaine in domaines:
        erreurs += verifier_domaine(domaine)
        for sort in domaine.tous:
            if sort.nom in vus:
                erreurs.append(f"Le sort « {sort.nom} » existe deux fois.")
            vus.add(sort.nom)
    if len({d.nom for d in domaines}) != len(domaines):
        erreurs.append("Deux domaines de magie portent le même nom.")
    return erreurs


# --- Le lancer --------------------------------------------------------------------------------

@dataclass
class RapportCible:
    qui: str
    attaque: RapportAttaque | None = None  # une attaque
    gain: int = 0  # un soin
    effet: str = ""  # un renfort, une entrave, une protection


@dataclass
class RapportSort:
    lanceur: str
    sort: Sort
    test: Resultat
    pm_depenses: int
    pm_restants: int
    pv_puises: int = 0  # à court de PM, la vie paie le reste
    sm_perdue: int = 0  # en Horreur, chaque sort coûte aussi de la Santé mentale
    cibles: list[RapportCible] = field(default_factory=list)
    retour: str = ""  # la maladresse : le sort se retourne contre son lanceur


def cout_paye(sort: Sort, test: Resultat) -> int:
    """Une réussite coûte le prix du sort, un échec la moitié (arrondie au-dessus), une maladresse tout."""
    if test.degre is Degre.ECHEC:
        return math.ceil(sort.cout / 2)
    return sort.cout


def _perdre_pv(fiche, perte: int):
    fiche.pv = max(0, fiche.pv - perte)
    if fiche.pv == 0 and fiche.etat is Etat.ACTIF:
        fiche.etat = Etat.MOURANT


def _modifier_pv(fiche, gain: int):
    fiche.pv = max(0, min(fiche.pv_max, fiche.pv + gain))
    if fiche.pv > 0 and fiche.etat in (Etat.INCONSCIENT, Etat.STABLE, Etat.MOURANT):
        fiche.etat = Etat.ACTIF  # soigné, il reprend connaissance


def _verifier_soin(lanceur: Combattant, patient: Combattant, moment: Moment | None):
    """Les mêmes limites que la Médecine, mais séparées (REGLES.md 10.7)."""
    fiche = patient.fiche
    if moment is None:
        return
    if not moment.periode.demi_journee:
        raise SortImpossible("Pas de soin magique la nuit : la nuit est au repos long.")
    if fiche.dernier_soin_magique == moment:
        raise SortImpossible(f"{patient.nom} a déjà reçu un soin magique cette demi-journée.")
    if fiche.moment_echecs_magie == moment and lanceur.nom in fiche.lanceurs_en_echec:
        raise SortImpossible(f"{lanceur.nom} a déjà raté un soin sur {patient.nom} cette demi-journée : "
                             "un autre lanceur peut tenter.")


def _noter_soin(lanceur: Combattant, patient: Combattant, moment: Moment | None, reussi: bool):
    fiche = patient.fiche
    if moment is None:
        return
    if reussi:
        fiche.dernier_soin_magique = moment
        return
    if fiche.moment_echecs_magie != moment:
        fiche.lanceurs_en_echec, fiche.moment_echecs_magie = [], moment
    fiche.lanceurs_en_echec.append(lanceur.nom)


def _jet_d_effet(des: Des, formule: str, degre: Degre) -> int:
    """Critique : effet maximum. Réussite majeure : un dé de plus (REGLES.md 10.4)."""
    nombre, faces = (int(x) for x in formule.split("d"))
    if degre is Degre.CRITIQUE:
        return nombre * faces
    return des.jet(formule) + (des.lancer(faces) if degre is Degre.MAJEURE else 0)


def lancer(des: Des, lanceur: Combattant, sort: Sort, cibles: list[Combattant], combat: Combat | None = None,
           couvert: Couvert = Couvert.AUCUN, moment: Moment | None = None, coute_sm: bool = False) -> RapportSort:
    """Lance un sort que le lanceur connaît : jet de Magie, coût, puis l'effet sur chaque cible.

    `moment` : pour la limite des soins magiques ; `coute_sm` : vrai en Horreur.
    """
    zone = sort.a(ProprieteSort.ZONE)
    if sort.effet is not Effet.UTILITAIRE and not 1 <= len(cibles) <= (2 if zone else 1):
        raise SortImpossible(f"{sort.nom} vise {'une ou deux cibles' if zone else 'une cible'}.")
    if len(set(map(id, cibles))) != len(cibles):
        raise SortImpossible("La même cible deux fois.")
    if not lanceur.conscient:
        raise SortImpossible(f"{lanceur.nom} ne peut pas lancer de sort : il est {lanceur.fiche.etat.value}.")
    if sort.effet is Effet.ATTAQUE:
        if combat is None:
            raise SortImpossible("Un sort d'attaque se lance en combat : commence d'abord le combat.")
        for cible in cibles:
            if cible.fiche.etat is Etat.MORT:
                raise SortImpossible(f"{cible.nom} est déjà mort.")
    if sort.effet is Effet.SOIN:
        for cible in cibles:
            _verifier_soin(lanceur, cible, moment)
    if combat:
        combat.action_simple(lanceur)

    modificateur = couvert.value if sort.effet is Effet.ATTAQUE else 0
    test = tester(des, lanceur.valeur(MAGIE), sort.difficulte, combat=combat is not None, modificateur=modificateur)
    cocher(lanceur.fiche, MAGIE, test)

    # Le prix : les PM d'abord, puis la vie ; en Horreur, la Santé mentale aussi
    fiche, cout = lanceur.fiche, cout_paye(sort, test)
    depenses = min(fiche.pm, cout)
    fiche.pm -= depenses
    rapport = RapportSort(lanceur.nom, sort, test, depenses, fiche.pm, pv_puises=cout - depenses)
    if rapport.pv_puises:
        _perdre_pv(fiche, rapport.pv_puises)
    if coute_sm and isinstance(fiche, Personnage):
        rapport.sm_perdue = payer_sante_mentale(fiche, cout, moment)

    if test.degre is Degre.MALADRESSE:
        rapport.retour = _retourner(des, lanceur, sort)
    elif test.reussi:
        rapport.cibles = [_appliquer(des, lanceur, sort, cible, test, combat) for cible in cibles]
    if sort.effet is Effet.SOIN:
        for cible in cibles:
            _noter_soin(lanceur, cible, moment, test.reussi)
    return rapport


def _effet_en_cours(sort: Sort, valeur: int, persistant: bool = False) -> EffetEnCours:
    duree = None if sort.effet is Effet.PROTECTION else DUREE[sort.puissance]  # l'armure tient tout le combat
    if sort.a(ProprieteSort.PERSISTANT) and not persistant and duree is not None:
        duree += 1  # un renfort persistant dure un round de plus, sans jet
    return EffetEnCours(sort.nom, sort.effet.value, valeur, None if persistant else duree, persistant)


def _appliquer(des: Des, lanceur: Combattant, sort: Sort, cible: Combattant, test: Resultat,
               combat: Combat | None) -> RapportCible:
    rapport = RapportCible(cible.nom)
    p = sort.puissance
    if sort.effet is Effet.ATTAQUE:
        rapport.attaque = combat.toucher_par_sort(lanceur, cible, sort.nom, DES_ATTAQUE[p], test)
        if sort.a(ProprieteSort.PERSISTANT) and cible.fiche.etat is not Etat.MORT:
            cible.effets.append(EffetEnCours(sort.nom, sort.effet.value, 0, None, persistant=True))
            rapport.effet = "persistant : jet de Constitution au début de chacun de ses tours"
    elif sort.effet is Effet.SOIN:
        avant = cible.fiche.pv
        _modifier_pv(cible.fiche, _jet_d_effet(des, DES_SOIN[p], test.degre))
        rapport.gain = cible.fiche.pv - avant
    elif sort.effet is Effet.PROTECTION:
        cible.effets.append(_effet_en_cours(sort, PROTECTION[p]))
        rapport.effet = f"armure +{PROTECTION[p]} jusqu'à la fin du combat"
    elif sort.effet in (Effet.RENFORT, Effet.ENTRAVE):
        valeur = MODIFICATEUR[p] if sort.effet is Effet.RENFORT else -MODIFICATEUR[p]
        persistant = sort.effet is Effet.ENTRAVE and sort.a(ProprieteSort.PERSISTANT)
        effet = _effet_en_cours(sort, valeur, persistant)
        cible.effets.append(effet)
        duree = ("jusqu'à ce qu'il réussisse un jet de Volonté" if persistant
                 else "tout le combat" if effet.rounds is None else f"{effet.rounds} round{'s' if effet.rounds > 1 else ''}")
        rapport.effet = f"{valeur:+d} à ses jets, {duree}"
    return rapport


def _retourner(des: Des, lanceur: Combattant, sort: Sort) -> str:
    """La maladresse : le lanceur subit l'effet en mineur s'il était nocif, 1d6 dégâts sinon (REGLES.md 10.4)."""
    if sort.effet is Effet.ENTRAVE:
        lanceur.effets.append(EffetEnCours(sort.nom, Effet.ENTRAVE.value, -MODIFICATEUR[Puissance.MINEUR], 1))
        return f"{lanceur.nom} subit son propre sort : {-MODIFICATEUR[Puissance.MINEUR]} à ses jets pendant 1 round."
    formule = DES_ATTAQUE[Puissance.MINEUR] if sort.effet is Effet.ATTAQUE else DEGATS_RETOURNES
    degats = des.jet(formule)
    _perdre_pv(lanceur.fiche, degats)
    return f"Le sort se retourne contre {lanceur.nom} : {degats} dégâts ({lanceur.fiche.pv} PV)."
