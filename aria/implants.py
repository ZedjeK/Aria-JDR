"""Les implants : le corps amélioré, au prix d'un peu d'humanité (REGLES.md 11).

Le corps est découpé en systèmes, chacun avec ses emplacements. Certains implants sont des
fondations (un bras cybernétique, des yeux cybernétiques…) qui ouvrent des options. Un implant
imite une mécanique que le moteur connaît déjà : une arme, une armure, un bonus de compétence,
ou un effet raconté. Son prix : la Santé mentale maximum, selon sa gamme.

Le catalogue (systèmes et implants) vient de l'univers ; les implants posés vivent sur la fiche
du personnage, sous forme de dictionnaires simples, pour que la sauvegarde les garde tels quels.
"""

from dataclasses import dataclass

from aria.des import Des
from aria.equipement import Arme, Armure, verifier_arme, verifier_armure
from aria.progression import cocher
from aria.resolution import Resultat, tester

ARME, ARMURE, BONUS, UTILITAIRE, ESTHETIQUE, MEDICAL = ("arme", "armure", "bonus", "utilitaire", "esthétique", "médical")
GAMMES = {"standard": 0, "avancée": 5, "militaire": 10}  # le bonus de compétence de chaque gamme
COUT_GAMME = {"standard": 2, "avancée": 4, "militaire": 6}  # la Santé mentale maximum perdue (REGLES.md 11.4)
COUT_USE, COUT_MODIFICATION = 2, 1
PLAFOND_BONUS = 10
SYSTEME_EXPLOITATION = "Système d'exploitation"
COTES = ("gauche", "droit")


class ImplantImpossible(ValueError):
    """La pose demandée enfreint les règles des implants."""


@dataclass(frozen=True)
class Systeme:
    nom: str
    emplacements: int | None = None  # None : sans limite (le médical)
    options: int | None = None  # pour un système à fondation : le nombre d'options qu'elle ouvre
    fondation: str | None = None
    requiert: str | None = None  # le cortex frontal demande un neuroport
    par: str | None = None  # « bras » ou « main » : les emplacements se comptent de chaque côté


@dataclass(frozen=True)
class Implant:
    nom: str
    systeme: str
    effet: str
    gamme: str | None = None
    fondation: bool = False
    competence: str | None = None
    bonus: int = 0
    arme: Arme | None = None
    armure: Armure | None = None
    description: str = ""
    electronique: bool = True

    @property
    def cout(self) -> int:
        """La Santé mentale maximum que coûte cet implant, d'origine et sans modification."""
        return 0 if self.effet in (ESTHETIQUE, MEDICAL) else COUT_GAMME[self.gamme]


def cout_de_pose(implant: Implant, use: bool = False, modifications: int = 0) -> int:
    """Le prix complet en Santé mentale maximum : la gamme, +2 s'il est usé, +1 par modification."""
    if implant.effet in (ESTHETIQUE, MEDICAL):
        return 0
    return implant.cout + (COUT_USE if use else 0) + COUT_MODIFICATION * modifications


# --- Le catalogue ---------------------------------------------------------------------------

def verifier_catalogue(systemes: tuple[Systeme, ...], implants: tuple[Implant, ...],
                       competences: set[str]) -> list[str]:
    """Les règles de 11.1 et 11.2 sur un catalogue d'implants."""
    erreurs = []
    par_nom = {s.nom: s for s in systemes}
    fondations = {s.fondation for s in systemes if s.fondation}
    for i in implants:
        if i.systeme not in par_nom:
            erreurs.append(f"{i.nom} : système inconnu « {i.systeme} ».")
        if i.effet not in (ARME, ARMURE, BONUS, UTILITAIRE, ESTHETIQUE, MEDICAL):
            erreurs.append(f"{i.nom} : effet inconnu « {i.effet} ».")
            continue
        if i.effet in (ESTHETIQUE, MEDICAL):
            if i.gamme is not None:
                erreurs.append(f"{i.nom} : l'esthétique et le médical n'ont pas de gamme.")
            continue
        if i.gamme not in GAMMES:
            erreurs.append(f"{i.nom} : gamme inconnue « {i.gamme} ».")
            continue
        if i.effet == BONUS:
            if i.gamme == "standard" or i.bonus != GAMMES[i.gamme]:
                erreurs.append(f"{i.nom} : en gamme {i.gamme}, le bonus vaut +{GAMMES[i.gamme]}.")
            if i.competence is not None and i.competence not in competences:
                erreurs.append(f"{i.nom} : compétence inconnue « {i.competence} ».")
        elif i.gamme != "standard":
            erreurs.append(f"{i.nom} : une arme, une armure ou un utilitaire est de gamme standard.")
        if i.effet == ARME:
            erreurs += [f"{i.nom} : {e}" for e in verifier_arme(i.arme)] if i.arme else [f"{i.nom} : quelle arme ?"]
        if i.effet == ARMURE:
            erreurs += [f"{i.nom} : {e}" for e in verifier_armure(i.armure)] if i.armure else [f"{i.nom} : quelle armure ?"]
        if i.fondation and i.nom not in fondations and not any(s.requiert == i.nom for s in systemes):
            erreurs.append(f"{i.nom} : fondation d'aucun système.")
    return erreurs


# --- Les implants posés sur un personnage ----------------------------------------------------

@dataclass
class Corps:
    """Ce qu'un personnage porte comme implants, et ce que les règles lui permettent encore."""

    catalogue: dict[str, Implant]
    systemes: dict[str, Systeme]
    poses: list[dict]

    def implant(self, pose: dict) -> Implant:
        return self.catalogue[pose["nom"]]

    def poses_du_systeme(self, systeme: str, cote: str | None = None) -> list[dict]:
        return [p for p in self.poses if self.implant(p).systeme == systeme and p.get("cote") == cote]

    def verifier_pose(self, implant: Implant, cote: str | None) -> list[str]:
        """Peut-on poser cet implant ? Fondations, emplacements, système d'exploitation unique (11.2)."""
        if implant.effet == ESTHETIQUE:
            return []  # l'esthétique n'occupe pas d'emplacement
        systeme = self.systemes[implant.systeme]
        if systeme.par and cote not in COTES:
            return [f"{implant.nom} se pose d'un côté : gauche ou droit."]
        if not systeme.par:
            cote = None
        deja = [p for p in self.poses_du_systeme(systeme.nom, cote) if self.implant(p).effet != ESTHETIQUE]
        if any(p["nom"] == implant.nom for p in deja):
            return [f"{implant.nom} est déjà posé{' à ' + cote if cote else ''}."]
        if systeme.requiert and not any(p["nom"] == systeme.requiert for p in self.poses):
            return [f"Le {systeme.nom.lower()} demande d'abord un {systeme.requiert.lower()}."]
        if systeme.fondation:
            fondation_posee = any(p["nom"] == systeme.fondation for p in deja)
            if implant.nom == systeme.fondation:
                return []
            if not fondation_posee:
                return [f"{implant.nom} demande d'abord la fondation : {systeme.fondation.lower()}."]
            options = [p for p in deja if p["nom"] != systeme.fondation]
            if len(options) >= systeme.options:
                return [f"La fondation {systeme.fondation.lower()} n'a plus d'emplacement libre "
                        f"({systeme.options} options)."]
            return []
        if systeme.emplacements is not None and len(deja) >= systeme.emplacements:
            if systeme.nom == SYSTEME_EXPLOITATION:
                return [f"Un seul système d'exploitation : {deja[0]['nom']} est déjà posé."]
            return [f"Le système {systeme.nom.lower()} est plein ({systeme.emplacements} emplacements)."]
        return []

    def bonus(self, competence: str) -> int:
        """Le meilleur bonus d'implant pour cette compétence : ils ne se cumulent pas (11.3)."""
        return max((p.get("bonus", 0) for p in self.poses if p.get("competence") == competence), default=0)

    def armure(self) -> Armure | None:
        """L'armure implantée qui protège le mieux."""
        armures = [self.implant(p).armure for p in self.poses if self.implant(p).effet == ARMURE]
        return max(armures, key=lambda a: a.protection_totale, default=None)

    def armes(self) -> list[Arme]:
        return [self.implant(p).arme for p in self.poses if self.implant(p).effet == ARME]


def pose(implant: Implant, qualite: str = "d'origine", cote: str | None = None) -> dict:
    """La trace d'un implant posé, telle qu'elle vit sur la fiche et dans la sauvegarde."""
    trace = {"nom": implant.nom, "qualite": qualite, "sm": cout_de_pose(implant, use=qualite == "usé")}
    if cote:
        trace["cote"] = cote
    if implant.effet == BONUS and implant.competence:
        trace.update(competence=implant.competence, bonus=min(PLAFOND_BONUS, implant.bonus))
    return trace


@dataclass
class RapportPose:
    patient: str
    implant: str
    test: Resultat
    pose: bool
    sm_max_perdue: int = 0


def poser(des: Des, charcudoc, patient, corps: Corps, implant: Implant, qualite: str = "d'origine",
          cote: str | None = None) -> RapportPose:
    """Un charcudoc pose un implant, hors combat : un jet de Médecine ou de Cybernétique (le meilleur).
    Réussi, l'implant est posé et la Santé mentale maximum baisse ; raté, il ne l'est pas ce jour-là."""
    erreurs = corps.verifier_pose(implant, cote)
    if erreurs:
        raise ImplantImpossible(" ".join(erreurs))
    competence = max(("Médecine", "Cybernétique"), key=lambda c: _valeur(charcudoc, c))
    test = tester(des, _valeur(charcudoc, competence))
    cocher(charcudoc, competence, test)
    rapport = RapportPose(patient.nom, implant.nom, test, test.reussi)
    if test.reussi:
        trace = pose(implant, qualite, cote if corps.systemes[implant.systeme].par else None)
        patient.implants.append(trace)
        rapport.sm_max_perdue = trace["sm"]
        patient.sm = min(patient.sm, patient.sm_max)
    return rapport


def _valeur(fiche, competence: str) -> int:
    try:
        return fiche.valeur(competence)
    except KeyError:
        return 0


# --- Lecture depuis un univers ou la bibliothèque ----------------------------------------------

def systeme_depuis_dict(d: dict) -> Systeme:
    return Systeme(d["nom"], d.get("emplacements"), d.get("options"), d.get("fondation"), d.get("requiert"), d.get("par"))


def implant_depuis_dict(d: dict, arme_depuis_dict, armure_depuis_dict) -> Implant:
    arme = arme_depuis_dict(dict(d["arme"], nom=d["nom"])) if d.get("arme") else None
    armure = armure_depuis_dict(dict(d["armure"], nom=d["nom"])) if d.get("armure") else None
    return Implant(d["nom"], d["systeme"], d["effet"], d.get("gamme"), d.get("fondation", False), d.get("competence"),
                   d.get("bonus", 0), arme, armure, d.get("description", ""), d.get("electronique", True))
