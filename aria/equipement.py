"""Les armes et les armures : qualité, modifications et fabricants.

Référence : REGLES.md 7.5. Chaque univers a sa propre armurerie : ce module ne définit que le
format des fiches et les vérifications communes. Les bonus d'un objet viennent de ses
modifications (un viseur, un nouveau calibre, des plaques de renfort…), dont le nombre dépend de
sa qualité : usé, d'origine, personnalisé, unique.
"""

from dataclasses import dataclass, field
from enum import Enum

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
    PERFORANTE = "perforante"  # l'armure ne compte qu'à moitié
    DISSIMULABLE = "dissimulable"
    LANCER = "lancer"
    SILENCIEUSE = "silencieuse"
    ENCOMBRANTE = "encombrante"
    FRAGILE = "fragile"  # peut casser sur une maladresse


class Recharge(Enum):
    """Le type d'action que coûte un rechargement."""

    MINEURE = "mineure"
    SIMPLE = "simple"


class Qualite(Enum):
    """L'échelle de qualité (REGLES.md 7.5) : elle donne les emplacements de modification."""

    USE = "usé"
    ORIGINE = "d'origine"
    PERSONNALISE = "personnalisé"
    UNIQUE = "unique"
    LEGENDAIRE = "légendaire"  # écrit à la main pour la campagne, hors échelle

    @property
    def emplacements(self) -> int | None:
        return {Qualite.USE: 0, Qualite.ORIGINE: 1, Qualite.PERSONNALISE: 2, Qualite.UNIQUE: 3}.get(self)


# Les effets d'une modification (REGLES.md 7.5)
PRECISION, PUISSANCE, PROPRIETE, MUNITIONS, CONFORT, UTILITAIRE = (
    "précision", "puissance", "propriété", "munitions", "confort", "utilitaire")
CHARGEUR_DOUBLE, RECHARGE_RAPIDE = "chargeur doublé", "recharge rapide"
PLAFOND_JET, PLAFOND_DEGATS, PLAFOND_PROTECTION, PLAFOND_PROPRIETES = 10, 2, 2, 1
# Le défaut d'un objet usé
DEFAUT_JET, DEFAUT_FRAGILE = "−5 au jet", "fragile"
DEFAUT_PROTECTION, DEFAUT_MALUS = "−1 de protection", "malus de −10 en plus"
DEFAUTS_ARME = (DEFAUT_JET, DEFAUT_FRAGILE)
DEFAUTS_ARMURE = (DEFAUT_PROTECTION, DEFAUT_MALUS)


@dataclass(frozen=True)
class Modification:
    """Une modification : un seul petit effet (REGLES.md 7.5)."""

    nom: str
    effet: str
    valeur: int = 0
    propriete: Propriete | None = None  # pour l'effet « propriété »
    competence: str | None = None  # pour un confort qui ne vaut que pour une compétence
    munitions: str | None = None  # pour l'effet « munitions » : chargeur doublé ou recharge rapide
    description: str = ""


@dataclass(frozen=True)
class Munitions:
    capacite: int
    recharge: Recharge


@dataclass(frozen=True)
class BonusArme:
    """Ce que les modifications (et le défaut) apportent à une arme, tout compte fait."""

    jet: int = 0
    degats: int = 0
    proprietes: frozenset[Propriete] = frozenset()


def _somme(modifications, effet: str) -> int:
    return sum(m.valeur for m in modifications if m.effet == effet)


@dataclass(frozen=True)
class Arme:
    nom: str
    competence: str  # CORPS_A_CORPS ou ARMES_A_DISTANCE
    degats: str  # formule de dés, par exemple « 2d6+2 »
    portee: Portee
    munitions: Munitions | None = None  # le chargeur d'origine ; vide pour une arme de mêlée ou de lancer
    proprietes: frozenset[Propriete] = frozenset()
    qualite: Qualite = Qualite.ORIGINE
    modifications: tuple[Modification, ...] = ()
    fabricant: str | None = None
    defaut: str | None = None  # le défaut d'une arme usée
    categorie: str = ""

    @property
    def corps_a_corps(self) -> bool:
        return self.competence == CORPS_A_CORPS

    @property
    def bonus(self) -> BonusArme:
        jet = _somme(self.modifications, PRECISION) - (5 if self.defaut == DEFAUT_JET else 0)
        proprietes = {m.propriete for m in self.modifications if m.effet == PROPRIETE and m.propriete}
        if self.defaut == DEFAUT_FRAGILE:
            proprietes.add(Propriete.FRAGILE)
        return BonusArme(jet, _somme(self.modifications, PUISSANCE), frozenset(proprietes))

    @property
    def chargeur(self) -> Munitions | None:
        """Le chargeur réel : un chargeur grande capacité double la capacité, un rechargeur rapide
        rend la recharge mineure."""
        if self.munitions is None:
            return None
        effets = {m.munitions for m in self.modifications if m.effet == MUNITIONS}
        capacite = self.munitions.capacite * (2 if CHARGEUR_DOUBLE in effets else 1)
        recharge = Recharge.MINEURE if RECHARGE_RAPIDE in effets else self.munitions.recharge
        return Munitions(capacite, recharge)

    def a(self, propriete: Propriete) -> bool:
        """Vrai si l'arme a cette propriété, de base ou grâce à une modification."""
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
    qualite: Qualite = Qualite.ORIGINE
    modifications: tuple[Modification, ...] = ()
    fabricant: str | None = None
    defaut: str | None = None  # le défaut d'une armure usée
    categorie: str = "armures"

    @property
    def bonus(self) -> BonusArmure:
        protection = _somme(self.modifications, PUISSANCE) - (1 if self.defaut == DEFAUT_PROTECTION else 0)
        confort = sum(m.valeur for m in self.modifications if m.effet == CONFORT and m.competence is None)
        return BonusArmure(protection, confort)

    @property
    def protection_totale(self) -> int:
        """La protection avec les modifications ; un défaut ne la fait jamais tomber sous 1."""
        return max(1 if self.protection else 0, self.protection + self.bonus.protection)

    def malus_pour(self, competence: str) -> int:
        """Le malus que l'armure impose à une compétence (0 ou un nombre négatif). Le confort en retire,
        sans jamais en faire un bonus ; le défaut d'une armure usée en ajoute."""
        malus = self.malus.get(competence, 0)
        if self.defaut == DEFAUT_MALUS and (malus < 0 or (not self.malus and competence == "Discrétion")):
            malus -= 10
        if malus >= 0:
            return 0
        confort = sum(m.valeur for m in self.modifications
                      if m.effet == CONFORT and m.competence in (None, competence))
        return min(0, malus + confort)


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
    """La formule complète des dégâts : arme, modifications, et bonus de Force au corps à corps."""
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

# Bornes de l'armurerie (REGLES.md 7.5), avant les modifications ; un objet légendaire y échappe
MOYENNE_MIN, MOYENNE_MAX, MAXIMUM_DEGATS = 2.5, 9, 14  # de 1d4 à 2d6+2
MOYENNE_UNE_MAIN = 5.5  # au-delà de 1d10, il faut deux mains
PROTECTION_MAX = 4
PROTECTION_LOURDE, MALUS_LOURD = 3, -10  # dès 3 de protection, au moins un malus de −10
EFFETS_ARME = {PRECISION, PUISSANCE, PROPRIETE, MUNITIONS, UTILITAIRE}
EFFETS_ARMURE = {PUISSANCE, CONFORT, UTILITAIRE}


def _verifier_qualite(objet, generee: bool, effets_permis: set[str], defauts: tuple[str, ...],
                      plafond_puissance: int) -> list[str]:
    """Qualité, défaut, emplacements et plafond des modifications (REGLES.md 7.5)."""
    if objet.qualite is Qualite.LEGENDAIRE:
        return ["Un objet légendaire s'écrit à la main pour la campagne : il ne peut pas être généré."] if generee else []
    erreurs = []
    mods = objet.modifications
    if objet.qualite is Qualite.USE:
        if objet.defaut not in defauts:
            erreurs.append(f"Un objet usé a un défaut, parmi : {', '.join(defauts)}.")
    elif objet.defaut is not None:
        erreurs.append("Seul un objet usé a un défaut.")
    if len(mods) > objet.qualite.emplacements:
        erreurs.append(f"Un objet {objet.qualite.value} a {objet.qualite.emplacements} emplacement(s) de "
                       f"modification, pas {len(mods)}.")
    noms = [m.nom for m in mods]
    if len(set(noms)) != len(noms):
        erreurs.append("Une modification ne se pose qu'une fois par objet.")
    for m in mods:
        if m.effet not in effets_permis:
            erreurs.append(f"« {m.nom} » : l'effet « {m.effet} » ne va pas sur cet objet.")
        if m.effet in (PRECISION, CONFORT) and m.valeur != 5 or m.effet == PUISSANCE and m.valeur != 1:
            erreurs.append(f"« {m.nom} » : une modification vaut +5 (précision, confort) ou +1 (puissance).")
    if _somme(mods, PRECISION) > PLAFOND_JET:
        erreurs.append(f"Plafond : +{PLAFOND_JET} au jet au plus.")
    if _somme(mods, PUISSANCE) > plafond_puissance:
        erreurs.append(f"Plafond : +{plafond_puissance} au plus.")
    if sum(1 for m in mods if m.effet == PROPRIETE) > PLAFOND_PROPRIETES:
        erreurs.append("Plafond : une seule propriété ajoutée.")
    return erreurs


def _verifier_degats(arme: Arme, degats: Formule) -> list[str]:
    moyenne = (degats.minimum + degats.maximum) / 2
    erreurs = []
    if not MOYENNE_MIN <= moyenne <= MOYENNE_MAX or degats.maximum > MAXIMUM_DEGATS:
        erreurs.append(f"Les dégâts vont de 1d4 à 2d6+2 (moyenne de {MOYENNE_MIN} à {MOYENNE_MAX}, "
                       f"{MAXIMUM_DEGATS} au plus), pas {degats}.")
    if moyenne > MOYENNE_UNE_MAIN and not arme.a(Propriete.DEUX_MAINS):
        erreurs.append(f"Au-delà de 1d10, une arme se tient à deux mains : {degats} sans « deux mains ».")
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
        degats = Formule.lire(arme.degats)
    except ValueError as erreur:
        erreurs.append(str(erreur))
    else:
        if arme.qualite is not Qualite.LEGENDAIRE:
            erreurs += _verifier_degats(arme, degats)
    if arme.corps_a_corps:
        if arme.portee is not Portee.CONTACT:
            erreurs.append("Une arme de corps à corps a une portée « contact ».")
        if arme.munitions:
            erreurs.append("Une arme de corps à corps n'a pas de munitions.")
        if any(m.effet == MUNITIONS for m in arme.modifications):
            erreurs.append("Une arme de corps à corps n'a pas de modification de munitions.")
    elif arme.competence == ARMES_A_DISTANCE:
        if arme.munitions is None and not arme.a(Propriete.LANCER):
            erreurs.append("Une arme à distance a des munitions, sauf si elle se lance.")
        if arme.munitions and arme.munitions.capacite < 1:
            erreurs.append("La capacité en munitions doit être d'au moins 1.")
    for m in arme.modifications:
        if m.effet == PROPRIETE and m.propriete is Propriete.DISSIMULABLE and Propriete.DEUX_MAINS in arme.proprietes:
            erreurs.append(f"« {m.nom} » : une arme à deux mains ne devient pas dissimulable.")
    erreurs += _verifier_qualite(arme, generee, EFFETS_ARME, DEFAUTS_ARME, PLAFOND_DEGATS)
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
    if armure.qualite is not Qualite.LEGENDAIRE:
        if armure.protection == 0 or armure.protection > PROTECTION_MAX:
            erreurs.append(f"La protection va de 1 à {PROTECTION_MAX}, pas {armure.protection}.")
        if armure.protection >= PROTECTION_LOURDE and min(armure.malus.values(), default=0) > MALUS_LOURD:
            erreurs.append(f"Dès {PROTECTION_LOURDE} de protection, l'armure a au moins un malus de {MALUS_LOURD}.")
    erreurs += _verifier_qualite(armure, generee, EFFETS_ARMURE, DEFAUTS_ARMURE, PLAFOND_PROTECTION)
    return erreurs


def modification_depuis_dict(d: dict) -> Modification:
    """Une modification, telle que l'écrivent un univers ou la bibliothèque."""
    propriete = d.get("propriete")
    munitions = None
    if d["effet"] == MUNITIONS:
        description = d.get("description", "")
        munitions = CHARGEUR_DOUBLE if "doubl" in description else RECHARGE_RAPIDE
    return Modification(d["nom"], d["effet"], d.get("valeur", 0),
                        Propriete(propriete) if propriete in {p.value for p in Propriete} else None,
                        d.get("competence"), d.get("munitions", munitions), d.get("description", ""))


def modification_vers_dict(m: Modification) -> dict:
    d = {"nom": m.nom, "effet": m.effet}
    if m.valeur:
        d["valeur"] = m.valeur
    if m.propriete:
        d["propriete"] = m.propriete.value
    if m.competence:
        d["competence"] = m.competence
    if m.munitions:
        d["munitions"] = m.munitions
    if m.description:
        d["description"] = m.description
    return d

