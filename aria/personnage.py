"""Le personnage : caractéristiques, valeurs dérivées, compétences et création.

Référence : REGLES.md, sections 3 (caractéristiques), 4 (compétences) et 5 (création).
Les compétences sont désignées par leur nom de socle (« Technologie »), jamais par
leur nom d'univers (« Piratage ») : l'habillage ne sert qu'à l'affichage.
"""

from dataclasses import dataclass, field
from enum import Enum

from aria.temps import Moment


class Caracteristique(Enum):
    FORCE = "force"
    CONSTITUTION = "constitution"
    DEXTERITE = "dexterite"
    INTELLIGENCE = "intelligence"
    VOLONTE = "volonte"
    PRESENCE = "presence"

    @property
    def libelle(self) -> str:
        return _LIBELLES_CARACTERISTIQUES[self]


_LIBELLES_CARACTERISTIQUES = {
    Caracteristique.FORCE: "Force",
    Caracteristique.CONSTITUTION: "Constitution",
    Caracteristique.DEXTERITE: "Dextérité",
    Caracteristique.INTELLIGENCE: "Intelligence",
    Caracteristique.VOLONTE: "Volonté",
    Caracteristique.PRESENCE: "Présence",
}

# Règles de création (REGLES.md 5) et plafonds (REGLES.md 6)
POINTS_CARACTERISTIQUES = 300
CARACTERISTIQUE_MIN_CREATION = 20
CARACTERISTIQUE_MAX_CREATION = 80
CARACTERISTIQUE_MAX = 90
NB_COMPETENCES_PARCOURS = 8
POINTS_PARCOURS = 300
POINTS_PERSONNELS = 100
PLAFOND_CREATION = 75
PLAFOND_MAGIE_CREATION = 50
PLAFOND_COMPETENCE = 95
MAGIE = "Magie"


class Etat(Enum):
    """L'état physique d'un personnage (REGLES.md 7.6)."""

    ACTIF = "actif"
    INCONSCIENT = "inconscient"
    MOURANT = "mourant"  # à 0 PV : test de Constitution à chaque fin de round
    STABLE = "stable"  # à 0 PV mais stabilisé : ne risque plus de mourir
    MORT = "mort"


MALUS_BLESSURE_GRAVE = -20


@dataclass(frozen=True)
class DefCompetence:
    """La définition d'une compétence : son nom de socle, son domaine et sa base."""

    nom: str
    domaine: str
    base: int | None  # None : la base se calcule à partir des caractéristiques (Esquive)
    description: str = ""

    def valeur_de_base(self, caracteristiques: dict[Caracteristique, int]) -> int:
        if self.base is not None:
            return self.base
        return caracteristiques[Caracteristique.DEXTERITE] // 2  # Esquive = Dextérité / 2


# Les 24 compétences du socle (REGLES.md 4.1)
SOCLE = (
    DefCompetence("Athlétisme", "Physique", 20),
    DefCompetence("Discrétion", "Physique", 20),
    DefCompetence("Esquive", "Physique", None),
    DefCompetence("Corps à corps", "Combat", 25),
    DefCompetence("Armes à distance", "Combat", 20),
    DefCompetence("Perception", "Perception & enquête", 25),
    DefCompetence("Perspicacité", "Perception & enquête", 10),
    DefCompetence("Survie", "Perception & enquête", 10),
    DefCompetence("Investigation", "Perception & enquête", 10),
    DefCompetence("Persuasion", "Social & ruse", 10),
    DefCompetence("Intimidation", "Social & ruse", 15),
    DefCompetence("Tromperie", "Social & ruse", 5),
    DefCompetence("Escamotage", "Social & ruse", 5),
    DefCompetence("Arts", "Social & ruse", 5),
    DefCompetence("Commandement", "Social & ruse", 5),
    DefCompetence("Érudition", "Savoirs", 10),
    DefCompetence("Sciences", "Savoirs", 5),
    DefCompetence("Médecine", "Savoirs", 5),
    DefCompetence("Occultisme", "Savoirs", 5),
    DefCompetence("Artisanat", "Technique", 5),
    DefCompetence("Technologie", "Technique", 5),
    DefCompetence("Sécurité", "Technique", 5),
    DefCompetence("Pilotage", "Technique", 20),
    DefCompetence(MAGIE, "Surnaturel", 0),
)
COMPETENCES_SOCLE = {c.nom: c for c in SOCLE}


@dataclass
class Personnage:
    """Une fiche de personnage. Les valeurs dérivées se recalculent à partir des caractéristiques."""

    nom: str
    parcours: str
    caracteristiques: dict[Caracteristique, int]
    competences: dict[str, int]  # valeur actuelle de chaque compétence connue
    motivation: str
    lien: str
    defaut: str
    magie_active: bool = True
    bonus_pv: int = 0  # donné par le curseur de l'univers (REGLES.md 3.2)
    # Valeurs actuelles ; laissées vides, elles démarrent au maximum.
    pv: int | None = None
    sm: int | None = None
    pm: int | None = None
    etat: Etat = Etat.ACTIF
    blessure_grave: bool = False  # tant qu'elle n'est pas guérie : PV max divisés par deux, −20 partout
    points_destin: int = 0  # fixés par le curseur de l'univers au début de la campagne

    # Suivi des soins (REGLES.md 8)
    blessure_grave_soignee: bool = False  # un jet de Médecine l'a traitée : elle peut guérir pendant la nuit
    nuits_depuis_soin: int = 0  # en Réaliste, la blessure grave soignée guérit au bout de quelques nuits
    dernier_repos: Moment | None = None
    dernier_soin_recu: Moment | None = None

    # Suivi de la Santé mentale (REGLES.md 9)
    folie: bool = False
    troubles: list = field(default_factory=list)  # objets Trouble (voir aria.sante_mentale)
    chocs_vecus: dict[str, int] = field(default_factory=dict)  # nombre de fois où chaque choc a été vécu
    jour_sm: int | None = None  # le jour en cours pour compter les pertes de SM
    sm_debut_jour: int = 0
    perte_sm_jour: int = 0
    trouble_aujourd_hui: bool = False
    derniere_therapie: Moment | None = None
    derniere_discussion: int | None = None  # numéro du jour

    # Progression (REGLES.md 6)
    competences_cochees: set[str] = field(default_factory=set)  # réussies pendant la session
    xp: int = 0

    def __post_init__(self):
        if self.pv is None:
            self.pv = self.pv_max
        if self.sm is None:
            self.sm = self.sm_max
        if self.pm is None:
            self.pm = self.pm_max

    def carac(self, caracteristique: Caracteristique) -> int:
        return self.caracteristiques[caracteristique]

    def competence(self, nom: str) -> int:
        if nom not in self.competences:
            raise KeyError(f"{self.nom} ne connaît pas la compétence « {nom} ».")
        return self.competences[nom]

    def valeur(self, nom: str) -> int:
        """La compétence avec le malus de blessure grave (−20 à toutes les actions)."""
        return self.competence(nom) + (MALUS_BLESSURE_GRAVE if self.blessure_grave else 0)

    @property
    def pv_max_base(self) -> int:
        """(Force + Constitution) / 10 + le bonus du curseur (REGLES.md 3.2), sans tenir compte des blessures."""
        return (self.carac(Caracteristique.FORCE) + self.carac(Caracteristique.CONSTITUTION)) // 10 + self.bonus_pv

    @property
    def pv_max(self) -> int:
        """Les PV max actuels : divisés par deux tant qu'une blessure grave n'est pas guérie."""
        return self.pv_max_base // 2 if self.blessure_grave else self.pv_max_base

    @property
    def sm_max(self) -> int:
        """La Volonté, et jamais plus de 99 − Mythe (compétence thématique de l'Horreur)."""
        return min(self.carac(Caracteristique.VOLONTE), 99 - self.competences.get("Mythe", 0))

    @property
    def pm_max(self) -> int:
        """Volonté / 5, ou 0 si l'univers n'a pas de magie."""
        return self.carac(Caracteristique.VOLONTE) // 5 if self.magie_active else 0


class CreationInvalide(ValueError):
    """La création ne respecte pas les règles. `erreurs` liste tous les problèmes trouvés."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("Création invalide :\n- " + "\n- ".join(erreurs))


def creer_personnage(
    nom: str,
    caracteristiques: dict[Caracteristique, int],
    parcours: str,
    competences_parcours: list[str],
    points_parcours: dict[str, int],
    points_personnels: dict[str, int],
    motivation: str,
    lien: str,
    defaut: str,
    magie_active: bool = True,
    competences_thematiques: tuple[DefCompetence, ...] = (),
    bonus_pv: int = 0,
) -> Personnage:
    """Crée un personnage en vérifiant toutes les règles de REGLES.md 5.

    Lève `CreationInvalide` avec la liste complète des erreurs, pour pouvoir
    toutes les corriger d'un coup.
    """
    erreurs: list[str] = []

    for texte, libelle in ((nom, "nom"), (parcours, "parcours"), (motivation, "motivation"), (lien, "lien"), (defaut, "défaut")):
        if not texte.strip():
            erreurs.append(f"Le champ « {libelle} » est vide.")

    erreurs += _verifier_caracteristiques(caracteristiques)

    # Les compétences que ce personnage peut avoir dans cet univers
    disponibles = {c.nom: c for c in SOCLE if magie_active or c.nom != MAGIE}
    for thematique in competences_thematiques:
        disponibles[thematique.nom] = thematique

    if len(competences_parcours) != NB_COMPETENCES_PARCOURS:
        erreurs.append(f"Un parcours donne {NB_COMPETENCES_PARCOURS} compétences, pas {len(competences_parcours)}.")
    if len(set(competences_parcours)) != len(competences_parcours):
        erreurs.append("Le parcours contient une compétence en double.")
    for nom_competence in competences_parcours:
        if nom_competence not in disponibles:
            erreurs.append(f"Compétence de parcours inconnue ou absente de cet univers : « {nom_competence} ».")

    erreurs += _verifier_points(points_parcours, POINTS_PARCOURS, "de parcours", disponibles)
    for nom_competence in points_parcours:
        if nom_competence not in competences_parcours:
            erreurs.append(f"« {nom_competence} » n'est pas une compétence du parcours : impossible d'y mettre des points de parcours.")
    erreurs += _verifier_points(points_personnels, POINTS_PERSONNELS, "personnels", disponibles)

    if erreurs:
        raise CreationInvalide(erreurs)

    # Valeurs finales : base + points de parcours + points personnels, sous les plafonds
    competences = {}
    for nom_competence, definition in disponibles.items():
        valeur = (
            definition.valeur_de_base(caracteristiques)
            + points_parcours.get(nom_competence, 0)
            + points_personnels.get(nom_competence, 0)
        )
        plafond = PLAFOND_MAGIE_CREATION if nom_competence == MAGIE else PLAFOND_CREATION
        if valeur > plafond:
            erreurs.append(f"« {nom_competence} » atteint {valeur}, au-dessus du plafond de création ({plafond}).")
        competences[nom_competence] = valeur

    if erreurs:
        raise CreationInvalide(erreurs)

    return Personnage(
        nom=nom.strip(),
        parcours=parcours.strip(),
        caracteristiques=dict(caracteristiques),
        competences=competences,
        motivation=motivation.strip(),
        lien=lien.strip(),
        defaut=defaut.strip(),
        magie_active=magie_active,
        bonus_pv=bonus_pv,
    )


def _verifier_caracteristiques(caracteristiques: dict[Caracteristique, int]) -> list[str]:
    erreurs = []
    manquantes = [c.libelle for c in Caracteristique if c not in caracteristiques]
    if manquantes:
        return [f"Caractéristiques manquantes : {', '.join(manquantes)}."]
    for carac, valeur in caracteristiques.items():
        if not CARACTERISTIQUE_MIN_CREATION <= valeur <= CARACTERISTIQUE_MAX_CREATION:
            erreurs.append(
                f"{carac.libelle} à {valeur} : à la création, une caractéristique va de "
                f"{CARACTERISTIQUE_MIN_CREATION} à {CARACTERISTIQUE_MAX_CREATION}."
            )
    total = sum(caracteristiques.values())
    if total != POINTS_CARACTERISTIQUES:
        erreurs.append(f"Les caractéristiques totalisent {total} points au lieu de {POINTS_CARACTERISTIQUES}.")
    return erreurs


def _verifier_points(points: dict[str, int], attendu: int, libelle: str, disponibles: dict) -> list[str]:
    erreurs = []
    for nom_competence, valeur in points.items():
        if nom_competence not in disponibles:
            erreurs.append(f"Points {libelle} sur une compétence inconnue ou absente de cet univers : « {nom_competence} ».")
        if valeur < 0:
            erreurs.append(f"Points {libelle} négatifs sur « {nom_competence} ».")
    total = sum(points.values())
    if total != attendu:
        erreurs.append(f"Les points {libelle} totalisent {total} au lieu de {attendu}.")
    return erreurs
