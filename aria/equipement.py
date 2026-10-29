"""Les armes et les armures, et leurs garde-fous de rareté.

Référence : REGLES.md 7.5. Chaque univers a sa propre armurerie : ce module ne
définit que le format des fiches et les vérifications communes.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum

from aria.des import Formule

CORPS_A_CORPS = "Corps à corps"
ARMES_A_DISTANCE = "Armes à distance"


class Portee(Enum):
    CONTACT = "contact"
    COURTE = "courte"
    MOYENNE = "moyenne"
    LONGUE = "longue"


class Propriete(Enum):
    DEUX_MAINS = "deux mains"
    RAFALE = "rafale"
    PERFORANTE = "perforante"
    DISSIMULABLE = "dissimulable"
    LANCER = "lancer"
    SILENCIEUSE = "silencieuse"
    ENCOMBRANTE = "encombrante"
    FRAGILE = "fragile"  # peut casser sur une maladresse


class Recharge(Enum):
    """Le type d'action que coûte un rechargement."""

    MINEURE = "mineure"
    SIMPLE = "simple"


class Rarete(IntEnum):
    COMMUNE = 0
    PEU_COMMUNE = 1
    RARE = 2
    EXCEPTIONNELLE = 3
    LEGENDAIRE = 4

    @property
    def libelle(self) -> str:
        return ("commune", "peu commune", "rare", "exceptionnelle", "légendaire")[self]

    @classmethod
    def depuis_libelle(cls, libelle: str) -> "Rarete":
        for rarete in cls:
            if rarete.libelle == libelle:
                return rarete
        raise ValueError(f"Rareté inconnue : « {libelle} ».")


@dataclass(frozen=True)
class Munitions:
    capacite: int
    recharge: Recharge


@dataclass(frozen=True)
class BonusArme:
    jet: int = 0
    degats: int = 0
    proprietes: frozenset[Propriete] = frozenset()


@dataclass(frozen=True)
class Arme:
    nom: str
    competence: str  # CORPS_A_CORPS ou ARMES_A_DISTANCE
    degats: str  # formule de dés, par exemple « 2d6+2 »
    portee: Portee
    munitions: Munitions | None = None  # vide pour une arme de mêlée ou de lancer
    proprietes: frozenset[Propriete] = frozenset()
    rarete: Rarete = Rarete.COMMUNE
    bonus: BonusArme = BonusArme()

    @property
    def corps_a_corps(self) -> bool:
        return self.competence == CORPS_A_CORPS

    def a(self, propriete: Propriete) -> bool:
        """Vrai si l'arme a cette propriété, de base ou grâce à son bonus de rareté."""
        return propriete in self.proprietes or propriete in self.bonus.proprietes


@dataclass(frozen=True)
class BonusArmure:
    protection: int = 0
    malus_en_moins: int = 0  # points de malus retirés à chaque compétence pénalisée
    proprietes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Armure:
    nom: str
    protection: int  # points de dégâts retirés à chaque coup reçu
    malus: dict[str, int] = field(default_factory=dict)  # par exemple {"Discrétion": -20}
    proprietes: frozenset[str] = frozenset()
    rarete: Rarete = Rarete.COMMUNE
    bonus: BonusArmure = BonusArmure()

    @property
    def protection_totale(self) -> int:
        return self.protection + self.bonus.protection

    def malus_pour(self, competence: str) -> int:
        """Le malus que l'armure impose à une compétence (0 ou un nombre négatif)."""
        malus = self.malus.get(competence, 0)
        return min(0, malus + self.bonus.malus_en_moins) if malus < 0 else 0


def bonus_force(force: int) -> str | None:
    """Le bonus de Force aux dégâts au corps à corps (REGLES.md 7.5), sous forme de formule."""
    if force <= 40:
        return "-1"
    if force <= 60:
        return None
    if force <= 75:
        return "1d4"
    return "1d6"


def formule_degats(arme: Arme, force: int | None = None) -> Formule:
    """La formule complète des dégâts : arme, bonus de rareté, et bonus de Force au corps à corps."""
    morceaux = [arme.degats]
    if arme.bonus.degats:
        morceaux.append(str(arme.bonus.degats))
    if arme.corps_a_corps and force is not None:
        bonus = bonus_force(force)
        if bonus:
            morceaux.append(bonus)
    texte = morceaux[0] + "".join(m if m.startswith("-") else "+" + m for m in morceaux[1:])
    return Formule.lire(texte)


# --- Vérifications -----------------------------------------------------------------

# Plafonds par « emplacement » de bonus (REGLES.md 7.5) : (au jet, aux dégâts ou à la protection)
_PLAFONDS = {Rarete.PEU_COMMUNE: (5, 1), Rarete.RARE: (10, 2), Rarete.EXCEPTIONNELLE: (10, 2)}
_EMPLACEMENTS = {Rarete.COMMUNE: 0, Rarete.PEU_COMMUNE: 1, Rarete.RARE: 1, Rarete.EXCEPTIONNELLE: 2}


def _verifier_rarete(
    rarete: Rarete, jet: int, degats: int, nb_proprietes: int, generee: bool, nom_jet: str, nom_degats: str
) -> list[str]:
    if rarete is Rarete.LEGENDAIRE:
        return ["Un objet légendaire s'écrit à la main pour la campagne : il ne peut pas être généré."] if generee else []
    erreurs = []
    if jet < 0 or degats < 0:
        erreurs.append("Un bonus de rareté ne peut pas être négatif.")
    utilises = (jet > 0) + (degats > 0) + nb_proprietes
    autorises = _EMPLACEMENTS[rarete]
    if utilises > autorises:
        erreurs.append(f"Un objet {rarete.libelle} a droit à {autorises} bonus, pas {utilises}.")
    if rarete is Rarete.PEU_COMMUNE and nb_proprietes:
        erreurs.append("Un objet peu commun ne peut pas gagner de propriété.")
    if rarete in _PLAFONDS:
        plafond_jet, plafond_degats = _PLAFONDS[rarete]
        if jet > plafond_jet:
            erreurs.append(f"Un objet {rarete.libelle} a au plus +{plafond_jet} {nom_jet}, pas +{jet}.")
        if degats > plafond_degats:
            erreurs.append(f"Un objet {rarete.libelle} a au plus +{plafond_degats} {nom_degats}, pas +{degats}.")
    return erreurs


def verifier_arme(arme: Arme, generee: bool = False) -> list[str]:
    """Liste les problèmes d'une fiche d'arme (vide si elle est valide).

    `generee` : True si l'arme vient du LLM et pas d'un humain (les légendaires sont alors refusées).
    """
    erreurs = []
    if not arme.nom.strip():
        erreurs.append("L'arme n'a pas de nom.")
    if arme.competence not in (CORPS_A_CORPS, ARMES_A_DISTANCE):
        erreurs.append(f"Compétence d'arme inconnue : « {arme.competence} ».")
    try:
        Formule.lire(arme.degats)
    except ValueError as erreur:
        erreurs.append(str(erreur))
    if arme.corps_a_corps:
        if arme.portee is not Portee.CONTACT:
            erreurs.append("Une arme de corps à corps a une portée « contact ».")
        if arme.munitions:
            erreurs.append("Une arme de corps à corps n'a pas de munitions.")
    elif arme.competence == ARMES_A_DISTANCE:
        if arme.munitions is None and not arme.a(Propriete.LANCER):
            erreurs.append("Une arme à distance a des munitions, sauf si elle se lance.")
        if arme.munitions and arme.munitions.capacite < 1:
            erreurs.append("La capacité en munitions doit être d'au moins 1.")
    erreurs += _verifier_rarete(
        arme.rarete, arme.bonus.jet, arme.bonus.degats, len(arme.bonus.proprietes), generee, "au jet", "aux dégâts"
    )
    return erreurs


def verifier_armure(armure: Armure, generee: bool = False) -> list[str]:
    """Liste les problèmes d'une fiche d'armure (vide si elle est valide)."""
    erreurs = []
    if not armure.nom.strip():
        erreurs.append("L'armure n'a pas de nom.")
    if armure.protection < 0:
        erreurs.append("La protection ne peut pas être négative.")
    if any(valeur > 0 for valeur in armure.malus.values()):
        erreurs.append("Un malus d'armure est négatif (par exemple −20).")
    erreurs += _verifier_rarete(
        armure.rarete,
        armure.bonus.malus_en_moins,
        armure.bonus.protection,
        len(armure.bonus.proprietes),
        generee,
        "de malus en moins",
        "de protection",
    )
    return erreurs
