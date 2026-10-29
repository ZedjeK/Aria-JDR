"""La Santé mentale : chocs, crises, troubles durables, folie et récupération (REGLES.md section 9).

Le MJ choisit un choc dans la liste fermée `Choc` ; le code calcule la gravité finale,
lance les dés et applique les conséquences.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum

from aria.des import Des
from aria.personnage import Personnage
from aria.reglages import Curseur, Jalon
from aria.resolution import Resultat, tester
from aria.soins import SoinImpossible, gain_selon_degre
from aria.temps import Moment, Periode


class Gravite(IntEnum):
    LEGER = 1
    SERIEUX = 2
    GRAVE = 3
    ABSOLUE = 4

    @property
    def pertes(self) -> tuple[str, str]:
        """Les pertes de SM (si le test est réussi, s'il est raté) (REGLES.md 9.2)."""
        return {
            Gravite.LEGER: ("0", "1d3"),
            Gravite.SERIEUX: ("1", "1d6"),
            Gravite.GRAVE: ("1d3", "1d10"),
            Gravite.ABSOLUE: ("1d6", "1d20"),
        }[self]


class Choc(Enum):
    """La liste fermée des chocs (REGLES.md 9.3) : (description, gravité de base)."""

    CADAVRE_INCONNU = ("Découvrir le cadavre d'un inconnu", Gravite.LEGER)
    VIOLENCE_BRUTALE = ("Assister à une violence brutale", Gravite.LEGER)
    BLESSURE_ATROCE = ("Voir une blessure atroce ou une mutilation", Gravite.LEGER)
    PIEGE_DANS_LE_NOIR = ("Rester piégé dans le noir ou dans un espace confiné", Gravite.LEGER)
    PHENOMENE_ETRANGE = ("Vivre un phénomène étrange et inexpliqué", Gravite.LEGER)

    PREMIER_MEURTRE = ("Tuer un humain pour la première fois", Gravite.SERIEUX)
    MORT_D_UN_ALLIE = ("Voir mourir un allié", Gravite.SERIEUX)
    TORTURE = ("Subir la torture ou une humiliation extrême", Gravite.SERIEUX)
    FROLER_LA_MORT = ("Frôler la mort (tomber à 0 PV)", Gravite.SERIEUX)
    CHARNIER = ("Découvrir un charnier ou plusieurs corps mutilés", Gravite.SERIEUX)
    SURNATUREL_INDENIABLE = ("Voir un phénomène surnaturel indéniable", Gravite.SERIEUX)
    TRAHIR_SA_PAROLE = ("Trahir sa parole ou ses propres principes", Gravite.SERIEUX)

    PERTE_DU_LIEN = ("Perdre son lien (mort ou trahison)", Gravite.GRAVE)
    MASSACRE = ("Assister à un massacre ou à une atrocité de masse", Gravite.GRAVE)
    POSSESSION = ("Être possédé ou contrôlé mentalement", Gravite.GRAVE)
    TRANSFORMATION = ("Voir son propre corps se transformer", Gravite.GRAVE)

    ENTITE_COSMIQUE = ("Contempler une entité cosmique ou divine", Gravite.ABSOLUE)
    VERITE_BRISEE = ("Découvrir une vérité qui brise la réalité", Gravite.ABSOLUE)
    DOUBLE = ("Se retrouver face à son propre double ou à son propre cadavre", Gravite.ABSOLUE)

    @property
    def description(self) -> str:
        return self.value[0]

    @property
    def gravite(self) -> Gravite:
        return self.value[1]


# En plein combat, ces chocs ne comptent qu'en Réaliste (REGLES.md 9.3)
CHOCS_DE_COMBAT = (Choc.PREMIER_MEURTRE, Choc.MORT_D_UN_ALLIE)
ACCOUTUMANCE = 3  # après trois chocs du même type, ce type descend d'un cran
SEUIL_CRISE = 5


class Crise(Enum):
    PANIQUE = "panique"
    PARALYSIE = "paralysie"
    FUITE = "fuite"
    RAGE = "rage"
    HALLUCINATION = "hallucination"


class TypeTrouble(Enum):
    PHOBIE = "phobie"
    CAUCHEMARS = "cauchemars"
    PARANOIA = "paranoïa"
    TREMBLEMENTS = "tremblements"


@dataclass
class Trouble:
    """Un trouble durable : −20 dans les situations liées, jusqu'à ce que la SM retrouve `seuil`,
    son niveau du début de la journée où il est apparu."""

    type: TypeTrouble
    seuil: int
    origine: str


@dataclass
class ReglagesMentaux:
    """Ce que l'univers change aux chocs (REGLES.md 1.2 et 9.3)."""

    curseur: Curseur = Curseur.STANDARD
    monde_impitoyable: bool = False
    chocs_banals: frozenset[Choc] = frozenset()  # descendent d'un cran
    chocs_normaux: frozenset[Choc] = frozenset()  # ne déclenchent plus de test


@dataclass
class RapportChoc:
    perso: str
    choc: Choc
    gravite: Gravite | None  # None : pas de test
    test: Resultat | None = None
    perte: int = 0
    sm_apres: int = 0
    crise: Crise | None = None
    duree_crise: int = 0  # en rounds
    trouble: Trouble | None = None
    folie: bool = False


def gravite_finale(perso: Personnage, choc: Choc, reglages: ReglagesMentaux,
                   concerne_lien: bool = False, en_combat: bool = False) -> Gravite | None:
    """La gravité après les modificateurs et les réglages, ou None si le choc ne déclenche pas de test."""
    if choc is Choc.PREMIER_MEURTRE and perso.chocs_vecus.get(choc.name, 0) > 0:
        return None  # ce n'est plus la première fois
    if en_combat and choc in CHOCS_DE_COMBAT and reglages.curseur is not Curseur.REALISTE:
        return None
    if choc in reglages.chocs_normaux:
        return None

    niveau = choc.gravite.value
    if concerne_lien:
        niveau += 1
    if perso.chocs_vecus.get(choc.name, 0) >= ACCOUTUMANCE:
        niveau -= 1
    if choc in reglages.chocs_banals:
        niveau -= 1
    niveau = min(niveau, Gravite.ABSOLUE.value)
    if niveau < Gravite.LEGER.value:
        return None

    gravite = Gravite(niveau)
    if gravite is Gravite.LEGER and reglages.monde_impitoyable:
        return None
    if reglages.curseur is Curseur.HEROIQUE and gravite < Gravite.GRAVE:
        return None
    return gravite


def subir_choc(des: Des, perso: Personnage, choc: Choc, moment: Moment,
               reglages: ReglagesMentaux = ReglagesMentaux(),
               concerne_lien: bool = False, en_combat: bool = False) -> RapportChoc:
    """Applique un choc : test de SM, perte, puis crise, trouble ou folie (REGLES.md 9.2 à 9.4)."""
    gravite = gravite_finale(perso, choc, reglages, concerne_lien, en_combat)
    perso.chocs_vecus[choc.name] = perso.chocs_vecus.get(choc.name, 0) + 1
    rapport = RapportChoc(perso.nom, choc, gravite, sm_apres=perso.sm)
    if gravite is None or perso.folie:
        return rapport

    _nouveau_jour(perso, moment)
    test = tester(des, perso.sm)
    perte_reussie, perte_ratee = gravite.pertes
    perte = des.jet(perte_reussie if test.reussi else perte_ratee)
    perso.sm = max(0, perso.sm - perte)
    perso.perte_sm_jour += perte
    rapport.test, rapport.perte, rapport.sm_apres = test, perte, perso.sm

    if perso.sm == 0:
        perso.folie = True
        rapport.folie = True
        return rapport
    if perte >= SEUIL_CRISE:
        rapport.crise = list(Crise)[des.lancer(len(Crise)) - 1]
        rapport.duree_crise = des.lancer(6)
    if not perso.trouble_aujourd_hui and perso.perte_sm_jour * 5 >= perso.sm_debut_jour:
        type_trouble = list(TypeTrouble)[des.lancer(len(TypeTrouble)) - 1]
        trouble = Trouble(type_trouble, perso.sm_debut_jour, choc.description)
        perso.troubles.append(trouble)
        perso.trouble_aujourd_hui = True
        rapport.trouble = trouble
    return rapport


def _nouveau_jour(perso: Personnage, moment: Moment):
    """Remet à zéro le compte des pertes du jour quand la journée change."""
    if perso.jour_sm != moment.jour:
        perso.jour_sm = moment.jour
        perso.sm_debut_jour = perso.sm
        perso.perte_sm_jour = 0
        perso.trouble_aujourd_hui = False


def sauver_de_la_folie(perso: Personnage):
    """Dépense un point de destin pour arracher le perso à la folie : il reste à 1 en SM."""
    if not perso.folie:
        raise ValueError(f"{perso.nom} n'a pas sombré dans la folie.")
    if perso.points_destin <= 0:
        raise ValueError(f"{perso.nom} n'a plus de point de destin.")
    perso.points_destin -= 1
    perso.folie = False
    perso.sm = 1


# --- Récupération (REGLES.md 9.5) -------------------------------------------------------

@dataclass
class RapportRecuperation:
    perso: str
    gain: int
    sm_apres: int
    test: Resultat | None = None
    troubles_gueris: list[Trouble] = field(default_factory=list)


def _recuperer(perso: Personnage, gain: int, test: Resultat | None = None) -> RapportRecuperation:
    perso.sm = max(0, min(perso.sm_max, perso.sm + gain))
    # Le seuil ne peut pas dépasser la SM max (si le Mythe l'a fait baisser entre-temps)
    gueris = [t for t in perso.troubles if perso.sm >= min(t.seuil, perso.sm_max)]
    perso.troubles = [t for t in perso.troubles if t not in gueris]
    return RapportRecuperation(perso.nom, gain, perso.sm, test, gueris)


def _verifier_pas_fou(perso: Personnage):
    if perso.folie:
        raise SoinImpossible(f"{perso.nom} a sombré dans la folie.")


def therapie(des: Des, soignant: Personnage, patient: Personnage, moment: Moment,
             competence: str = "Perspicacité") -> RapportRecuperation:
    """Pendant le repos long, un jet de Perspicacité ou de Médecine, une fois par nuit."""
    _verifier_pas_fou(patient)
    if competence not in ("Perspicacité", "Médecine"):
        raise SoinImpossible("La thérapie se fait en Perspicacité ou en Médecine.")
    if moment.periode is not Periode.NUIT:
        raise SoinImpossible("La thérapie accompagne le repos long, la nuit.")
    if patient.derniere_therapie == moment:
        raise SoinImpossible(f"{patient.nom} a déjà eu sa thérapie cette nuit.")
    patient.derniere_therapie = moment
    test = tester(des, soignant.competence(competence))
    return _recuperer(patient, gain_selon_degre(des, test.degre), test)


def discussion(des: Des, perso: Personnage, moment: Moment) -> RapportRecuperation:
    """Du temps avec son lien, ou une longue discussion avec quelqu'un : +1d3, une fois par jour."""
    _verifier_pas_fou(perso)
    if perso.derniere_discussion == moment.jour:
        raise SoinImpossible(f"{perso.nom} a déjà eu sa discussion aujourd'hui.")
    perso.derniere_discussion = moment.jour
    return _recuperer(perso, des.jet("1d3"))


GAINS_JALONS = {Jalon.OBJECTIF: "1d6", Jalon.ARC: "1d10", Jalon.MOTIVATION: "1d10"}


def jalon_atteint(des: Des, perso: Personnage, jalon: Jalon) -> RapportRecuperation:
    """Un objectif, une quête, un arc ou une motivation accomplis remontent le moral."""
    _verifier_pas_fou(perso)
    formule = GAINS_JALONS.get(jalon)
    return _recuperer(perso, des.jet(formule) if formule else 0)
