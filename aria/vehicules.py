"""Les véhicules et les montures (REGLES.md 12.1, 12.2, 12.5 et 12.6).

Le catalogue décrit des modèles (`Vehicule`) ; un véhicule en jeu (`Engin`) garde sa structure
du moment, sa nitro et sa dernière réparation. La poursuite vit dans `aria.poursuite`, les armes
montées et les drones dans 12.7.
"""

from dataclasses import dataclass, field

from aria.des import Des
from aria.equipement import Qualite
from aria.progression import cocher
from aria.resolution import Degre, Difficulte, Resultat, tester
from aria.temps import Moment, Periode

VITESSES = ("lente", "moyenne", "rapide", "très rapide")
MANIABILITES = (-10, 0, 10)
TYPES = ("terrestre", "aérien", "nautique", "spatial")
# Les bornes de chaque gabarit (12.1 et 12.7) : structure, blindage, points d'emport
GABARITS = {
    "léger": ((10, 20), (0, 2), 0),
    "moyen": ((20, 40), (2, 4), 1),
    "lourd": ((40, 60), (4, 8), 2),
    "militaire": ((60, 100), (8, 12), 3),
    "drone": ((5, 10), (0, 1), 1),
}
# Les modifications (12.6) et leur plafond total
MOTEUR, CHASSIS, RENFORT, BLINDAGE, PROPRIETE = "moteur", "châssis", "renfort", "blindage", "propriété"
SUPPORT, NITRO, UTILITAIRE, DEFENSIF = "support d'arme", "nitro", "utilitaire", "défensif"
EFFETS = {MOTEUR, CHASSIS, RENFORT, BLINDAGE, PROPRIETE, SUPPORT, NITRO, UTILITAIRE, DEFENSIF}
EFFETS_MONTURE = {MOTEUR, CHASSIS, RENFORT, BLINDAGE, PROPRIETE}
VALEURS = {MOTEUR: 1, CHASSIS: 5, RENFORT: 5, BLINDAGE: 1, SUPPORT: 1, NITRO: 10}
PLAFONDS = {MOTEUR: 1, CHASSIS: 10, RENFORT: 10, BLINDAGE: 2, PROPRIETE: 1, SUPPORT: 1}
# Le défaut d'un véhicule usé
MOTEUR_FATIGUE, DIRECTION_MOLLE, ROUILLE, CAPRICIEUX = (
    "moteur fatigué", "direction molle", "carrosserie rouillée", "capricieux")
DEFAUTS = (MOTEUR_FATIGUE, DIRECTION_MOLLE, ROUILLE, CAPRICIEUX)
# L'accident (12.5), selon la vitesse : dégâts à chaque occupant, dégâts à la structure
ACCIDENT = {"lente": ("1d4", "1d6"), "moyenne": ("1d6", "2d6"), "rapide": ("2d6", "3d6"), "très rapide": ("3d6", "4d6")}
# La réparation : la table de la Médecine, doublée (12.5)
REPARATION = {Degre.CRITIQUE: "4d6", Degre.MAJEURE: "2d6", Degre.REUSSITE: "1d6", Degre.COMPLICATION: "1d6"}
REPARER, SOIGNER_MONTURE, PILOTAGE = "Artisanat", "Survie", "Pilotage"
DRESSAGE = "dressage de guerre"
TOUT_TERRAIN = "tout-terrain"


class VehiculeImpossible(ValueError):
    """Ce que les règles des véhicules ne permettent pas."""


@dataclass(frozen=True)
class ModVehicule:
    nom: str
    effet: str
    valeur: int = 0
    propriete: str | None = None
    description: str = ""
    electronique: bool = False


@dataclass(frozen=True)
class Vehicule:
    """Un modèle de véhicule ou de monture, tel que le catalogue le décrit."""

    nom: str
    type: str
    gabarit: str
    vitesse: str
    maniabilite: int
    structure: int
    blindage: int
    places: int = 1
    proprietes: frozenset[str] = frozenset()
    armes_montees: tuple[dict, ...] = ()  # REGLES.md 12.7
    systemes: tuple[str, ...] = ()
    qualite: Qualite = Qualite.ORIGINE
    modifications: tuple[ModVehicule, ...] = ()
    defaut: str | None = None
    fabricant: str | None = None
    electronique: bool = False
    monture: bool = False
    categorie: str = ""
    effet: str = ""  # un drone : ce qu'il fait
    drones: dict | None = None

    def _somme(self, effet: str) -> int:
        return min(PLAFONDS.get(effet, 99), sum(m.valeur for m in self.modifications if m.effet == effet))

    @property
    def cran(self) -> int:
        """La vitesse en crans : 0 (lente) à 3 (très rapide), modifications et défaut compris."""
        cran = VITESSES.index(self.vitesse) + self._somme(MOTEUR) - (1 if self.defaut == MOTEUR_FATIGUE else 0)
        return max(0, min(len(VITESSES) - 1, cran))

    @property
    def maniabilite_totale(self) -> int:
        return self.maniabilite + self._somme(CHASSIS) - (5 if self.defaut == DIRECTION_MOLLE else 0)

    @property
    def structure_max(self) -> int:
        return self.structure + self._somme(RENFORT) - (5 if self.defaut == ROUILLE else 0)

    @property
    def blindage_total(self) -> int:
        return self.blindage + self._somme(BLINDAGE)

    @property
    def proprietes_totales(self) -> frozenset[str]:
        return self.proprietes | {m.propriete for m in self.modifications if m.effet == PROPRIETE and m.propriete}

    @property
    def nitro(self) -> bool:
        return any(m.effet == NITRO for m in self.modifications)


def verifier_vehicule(v: Vehicule, generee: bool = False) -> list[str]:
    """Les bornes de 12.1 (avant les modifications) et les règles de qualité de 12.6."""
    erreurs = []
    if v.gabarit not in GABARITS:
        return [f"Gabarit inconnu « {v.gabarit} »."]
    (s_min, s_max), (b_min, b_max), _ = GABARITS[v.gabarit]
    if not s_min <= v.structure <= s_max:
        erreurs.append(f"En gabarit {v.gabarit}, la structure va de {s_min} à {s_max}.")
    if not b_min <= v.blindage <= b_max:
        erreurs.append(f"En gabarit {v.gabarit}, le blindage va de {b_min} à {b_max}.")
    if v.vitesse not in VITESSES:
        erreurs.append(f"Vitesse inconnue « {v.vitesse} ».")
    if v.maniabilite not in MANIABILITES:
        erreurs.append("La maniabilité vaut −10, 0 ou +10.")
    if v.type not in TYPES:
        erreurs.append(f"Type inconnu « {v.type} ».")
    if v.qualite is Qualite.LEGENDAIRE:
        return erreurs + (["Un véhicule légendaire s'écrit à la main : il ne peut pas être généré."] if generee else [])
    if v.qualite is Qualite.USE:
        if v.defaut not in DEFAUTS:
            erreurs.append(f"Un véhicule usé a un défaut, parmi : {', '.join(DEFAUTS)}.")
    elif v.defaut is not None:
        erreurs.append("Seul un véhicule usé a un défaut.")
    mods = v.modifications
    if len(mods) > v.qualite.emplacements:
        erreurs.append(f"Un véhicule {v.qualite.value} a {v.qualite.emplacements} emplacement(s) de modification, "
                       f"pas {len(mods)}.")
    noms = [m.nom for m in mods]
    if len(set(noms)) != len(noms):
        erreurs.append("Une modification ne se pose qu'une fois par véhicule.")
    for m in mods:
        if m.effet not in (EFFETS_MONTURE if v.monture else EFFETS):
            erreurs.append(f"« {m.nom} » : l'effet « {m.effet} » ne va pas sur {'une monture' if v.monture else 'un véhicule'}.")
        elif m.effet in VALEURS and m.valeur != VALEURS[m.effet]:
            erreurs.append(f"« {m.nom} » : une modification {m.effet} vaut {VALEURS[m.effet]}.")
    for effet, plafond in PLAFONDS.items():
        total = sum(1 if effet == PROPRIETE else m.valeur for m in mods if m.effet == effet)
        if total > plafond:
            erreurs.append(f"Plafond : {effet} {plafond} au plus.")
    return erreurs


# --- Le véhicule en jeu -----------------------------------------------------------------------

INTACT, ENDOMMAGE, EPAVE, MOURANTE = "intact", "endommagé", "épave", "mourante"


@dataclass
class Engin:
    """Un véhicule (ou une monture) en jeu : sa structure du moment, sa nitro, sa dernière réparation."""

    modele: Vehicule
    structure: int | None = None
    nitro_utilisee: bool = False
    derniere_reparation: Moment | None = None

    def __post_init__(self):
        if self.structure is None:
            self.structure = self.modele.structure_max

    @property
    def nom(self) -> str:
        return self.modele.nom

    @property
    def etat(self) -> str:
        if self.structure <= 0:
            return MOURANTE if self.modele.monture else EPAVE
        return ENDOMMAGE if self.structure * 2 <= self.modele.structure_max else INTACT

    @property
    def cran(self) -> int:
        """La vitesse du moment : endommagé, un cran de moins (12.5)."""
        return max(0, self.modele.cran - (1 if self.etat == ENDOMMAGE else 0))

    @property
    def vitesse(self) -> str:
        return VITESSES[self.cran]

    @property
    def maniabilite(self) -> int:
        return self.modele.maniabilite_totale - (10 if self.etat == ENDOMMAGE else 0)

    def encaisser(self, degats: int, blindage: bool = True) -> int:
        """Retire des dégâts à la structure, moins le blindage ; renvoie ce qui a été retiré."""
        perte = max(0, degats - (self.modele.blindage_total if blindage else 0))
        self.structure = max(0, self.structure - perte)
        return perte

    def vers_dict(self) -> dict:
        d = {"nom": self.nom, "structure": self.structure}
        if self.nitro_utilisee:
            d["nitro_utilisee"] = True
        if self.derniere_reparation:
            d["derniere_reparation"] = {"jour": self.derniere_reparation.jour,
                                        "periode": self.derniere_reparation.periode.value}
        return d


def cocher_pour(qui, competence: str, test: Resultat):
    """Coche pour la progression, que `qui` soit un combattant ou une fiche."""
    if hasattr(qui, "cocher"):
        qui.cocher(competence, test)
    else:
        cocher(qui, competence, test)


def valeur_pilotage(fiche, engin: Engin | None, competence: str = PILOTAGE) -> int:
    """La compétence du conducteur, plus la maniabilité du véhicule (à pied : l'Athlétisme, sans rien)."""
    try:
        valeur = fiche.valeur(competence if engin else "Athlétisme")
    except KeyError:
        valeur = 0
    return valeur + (engin.maniabilite if engin else 0)


@dataclass
class RapportConduite:
    conducteur: str
    vehicule: str
    test: Resultat
    accident: "RapportAccident | None" = None
    cale: bool = False


def piloter(des: Des, conducteur, engin: Engin, difficulte: Difficulte = Difficulte.NORMALE,
            occupants: list = (), blesser=None) -> RapportConduite:
    """Une manœuvre risquée (12.2) : Pilotage plus la maniabilité. Maladresse : l'accident, ou,
    pour un véhicule capricieux, le moteur qui cale."""
    if engin.etat in (EPAVE, MOURANTE):
        raise VehiculeImpossible(f"{engin.nom} ne peut plus avancer ({engin.etat}).")
    test = tester(des, valeur_pilotage(conducteur, engin), difficulte)
    cocher_pour(conducteur, PILOTAGE, test)
    rapport = RapportConduite(conducteur.nom, engin.nom, test)
    if test.degre is Degre.MALADRESSE:
        if engin.modele.defaut == CAPRICIEUX:
            rapport.cale = True
        else:
            rapport.accident = accident(des, engin, occupants or [conducteur], blesser)
    return rapport


@dataclass
class RapportAccident:
    vehicule: str
    vitesse: str
    structure_perdue: int
    etat: str
    occupants: list[tuple[str, int, object]] = field(default_factory=list)  # (qui, dégâts, blessure)


def accident(des: Des, engin: Engin, occupants: list, blesser=None) -> RapportAccident:
    """L'accident (12.5) : des dégâts à chaque occupant (l'armure protège) et à la structure.
    Sur un véhicule léger, les occupants prennent 1d6 de plus.

    `occupants` : des combattants (avec leur armure) ou des fiches. `blesser(victime, degats)`
    applique les dégâts ; par défaut, ils sont seulement retirés des PV."""
    vitesse = engin.vitesse
    formule_occupant, formule_structure = ACCIDENT[vitesse]
    perte = engin.encaisser(des.jet(formule_structure), blindage=False)
    rapport = RapportAccident(engin.nom, vitesse, perte, engin.etat)
    for occupant in occupants:
        degats = des.jet(formule_occupant) + (des.lancer(6) if engin.modele.gabarit == "léger" else 0)
        degats = max(0, degats - getattr(occupant, "protection", 0))
        if blesser:
            blessure = blesser(occupant, degats)
        else:
            fiche = getattr(occupant, "fiche", occupant)
            fiche.pv = max(0, fiche.pv - degats)
            blessure = None
        rapport.occupants.append((occupant.nom, degats, blessure))
    return rapport


@dataclass
class RapportReparation:
    reparateur: str
    vehicule: str
    test: Resultat
    structure_rendue: int
    structure: int


def reparer(des: Des, reparateur, engin: Engin, moment: Moment, atelier: bool = False) -> RapportReparation:
    """Réparer (Artisanat), ou soigner une monture (Survie) : la table de la Médecine doublée,
    une fois par véhicule et par demi-journée. Une épave ne se répare qu'en atelier."""
    monture = engin.modele.monture
    if engin.derniere_reparation == moment:
        raise VehiculeImpossible(f"{engin.nom} a déjà été {'soigné' if monture else 'réparé'} cette demi-journée.")
    if engin.structure >= engin.modele.structure_max:
        raise VehiculeImpossible(f"{engin.nom} n'a rien à {'soigner' if monture else 'réparer'}.")
    if engin.etat == EPAVE and not atelier:
        raise VehiculeImpossible(f"{engin.nom} est une épave : seul un atelier peut la réparer.")
    competence = SOIGNER_MONTURE if monture else REPARER
    difficulte = Difficulte.FACILE if atelier and not monture else Difficulte.NORMALE
    try:
        valeur = reparateur.valeur(competence)
    except KeyError:
        valeur = 0
    test = tester(des, valeur, difficulte)
    cocher_pour(reparateur, competence, test)
    engin.derniere_reparation = moment
    if test.degre is Degre.MALADRESSE:
        gain = -des.lancer(6)
    elif test.degre in REPARATION:
        gain = des.jet(REPARATION[test.degre])
    else:
        gain = 0
    avant = engin.structure
    engin.structure = max(0, min(engin.modele.structure_max, engin.structure + gain))
    return RapportReparation(reparateur.nom, engin.nom, test, engin.structure - avant, engin.structure)


# --- Lecture depuis un univers ou la bibliothèque ----------------------------------------------

def mod_vehicule_depuis_dict(d: dict) -> ModVehicule:
    return ModVehicule(d["nom"], d["effet"], d.get("valeur") or 0, d.get("propriete"), d.get("description", ""),
                       d.get("electronique", False))


def vehicule_depuis_dict(d: dict, modifications: dict[str, dict] | None = None) -> Vehicule:
    """`modifications` : le catalogue, pour lire des modifications données par leur nom."""
    mods = tuple(mod_vehicule_depuis_dict(m if isinstance(m, dict) else modifications[m])
                 for m in d.get("modifications", []))
    return Vehicule(
        d["nom"], d["type"], d["gabarit"], d["vitesse"], d["maniabilite"], d["structure"], d["blindage"],
        d.get("places", 1), frozenset(d.get("proprietes", [])), tuple(d.get("armes_montees", [])),
        tuple(d.get("systemes", [])), Qualite(d.get("qualite", Qualite.ORIGINE.value)), mods, d.get("defaut"),
        d.get("fabricant"), d.get("electronique", False), d.get("monture", False), d.get("categorie", ""),
        d.get("effet", ""), d.get("drones"),
    )


def vehicule_vers_dict(v: Vehicule) -> dict:
    d = {"nom": v.nom, "type": v.type, "gabarit": v.gabarit, "vitesse": v.vitesse, "maniabilite": v.maniabilite,
         "structure": v.structure, "blindage": v.blindage, "places": v.places, "proprietes": sorted(v.proprietes),
         "armes_montees": list(v.armes_montees), "systemes": list(v.systemes), "categorie": v.categorie}
    if v.qualite is not Qualite.ORIGINE:
        d["qualite"] = v.qualite.value
    if v.modifications:
        d["modifications"] = [{k: val for k, val in vars(m).items() if val not in (None, "", False, 0) or k == "nom"}
                              for m in v.modifications]
    for cle in ("defaut", "fabricant", "electronique", "monture", "effet", "drones"):
        if getattr(v, cle):
            d[cle] = getattr(v, cle)
    return d


def engin_depuis_dict(d: dict, catalogue: dict[str, Vehicule]) -> Engin:
    moment = d.get("derniere_reparation")
    return Engin(catalogue[d["nom"]], d.get("structure"), d.get("nitro_utilisee", False),
                 Moment(moment["jour"], Periode(moment["periode"])) if moment else None)
