"""La création de personnage guidée (REGLES.md 5).

Un brouillon se remplit étape par étape : caractéristiques, parcours, points de parcours, points
personnels, domaines de magie, équipement, puis le roleplay. Chaque étape a sa vérification et sa
proposition. « Tout proposer » : le code fait les chiffres (une répartition équilibrée, tirée du
parcours), le LLM écrit la personnalité par un outil, que le code vérifie aussi.

Ce module ne parle à personne : le parcours guidé en texte (aria.creation_texte) et, plus tard,
l'interface graphique s'en servent.
"""

import json
import random
from dataclasses import dataclass, field

from aria.personnage import (
    MAGIE,
    PLAFOND_CREATION,
    PLAFOND_MAGIE_CREATION,
    POINTS_CARACTERISTIQUES,
    POINTS_PARCOURS,
    POINTS_PERSONNELS,
    Caracteristique,
    CreationInvalide,
    Personnage,
)
from aria.univers import DOMAINES_PAR_PERSO, Depart, Univers, UniversInvalide

C = Caracteristique
CARACTERISTIQUE_MIN, CARACTERISTIQUE_MAX = 20, 80
# À quelle caractéristique chaque compétence du socle fait le plus appel, pour répartir les points
AFFINITES = {
    "Athlétisme": C.FORCE, "Corps à corps": C.FORCE,
    "Discrétion": C.DEXTERITE, "Esquive": C.DEXTERITE, "Armes à distance": C.DEXTERITE, "Escamotage": C.DEXTERITE,
    "Artisanat": C.DEXTERITE, "Sécurité": C.DEXTERITE, "Pilotage": C.DEXTERITE,
    "Perception": C.INTELLIGENCE, "Investigation": C.INTELLIGENCE, "Érudition": C.INTELLIGENCE,
    "Sciences": C.INTELLIGENCE, "Médecine": C.INTELLIGENCE, "Occultisme": C.INTELLIGENCE,
    "Technologie": C.INTELLIGENCE,
    "Perspicacité": C.VOLONTE, "Magie": C.VOLONTE,
    "Survie": C.CONSTITUTION,
    "Persuasion": C.PRESENCE, "Intimidation": C.PRESENCE, "Tromperie": C.PRESENCE, "Arts": C.PRESENCE,
    "Commandement": C.PRESENCE,
}
BASE_CARACTERISTIQUE = 40  # chaque caractéristique part de là : 6 × 40 = 240, les 60 restants suivent le parcours
PAS = 5
MODELE_PARCOURS = (60, 50, 45, 40, 35, 30, 25, 15)  # le cœur du métier d'abord
DEFENSES = ("Esquive", "Corps à corps", "Armes à distance", MAGIE)
ROLEPLAY_MAX = {"nom": 40, "motivation": 200, "lien": 200, "defaut": 200, "allure": 300}


class EtapeInvalide(ValueError):
    """Une étape du brouillon ne respecte pas les règles de création. `erreurs` les liste toutes."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("\n".join(erreurs))


@dataclass
class Brouillon:
    """Un personnage en cours de création, dans un univers."""

    univers: Univers
    caracteristiques: dict[Caracteristique, int] = field(default_factory=dict)
    parcours: str = ""
    points_parcours: dict[str, int] = field(default_factory=dict)
    points_personnels: dict[str, int] = field(default_factory=dict)
    domaines: list[str] = field(default_factory=list)
    equipement: dict = field(default_factory=dict)  # arme, armure, implant, vehicule, objets
    roleplay: dict[str, str] = field(default_factory=dict)  # nom, motivation, lien, defaut, allure

    # --- Ce que le brouillon sait déjà -------------------------------------------------------------

    @property
    def competences_parcours(self) -> list[str]:
        return list(self.univers.parcours.get(self.parcours, []))

    def base(self, competence: str) -> int:
        definition = self.univers.competences_disponibles()[competence]
        return definition.valeur_de_base(self.caracteristiques or {c: 50 for c in C})

    def valeur(self, competence: str) -> int:
        return self.base(competence) + self.points_parcours.get(competence, 0) + self.points_personnels.get(competence, 0)

    @staticmethod
    def plafond(competence: str) -> int:
        return PLAFOND_MAGIE_CREATION if competence == MAGIE else PLAFOND_CREATION

    def avertissements(self) -> list[str]:
        """Ce que la création signale sans l'interdire (REGLES.md 5)."""
        textes = []
        competences = set(self.competences_parcours) | {c for c, v in self.points_personnels.items() if v}
        if not competences & set(DEFENSES):
            textes.append("Ni Corps à corps, ni Armes à distance, ni Esquive, ni Magie : sans compagnon pour le "
                          "protéger, le premier combat peut lui être fatal.")
        if self.equipement and self.equipement.get("arme") is None and self.univers.equipements.get(self.parcours):
            textes.append("Aucune arme au départ : il devra en trouver une, ou compter sur ses compagnons.")
        return textes

    # --- Les vérifications, étape par étape ---------------------------------------------------------

    def verifier_caracteristiques(self, valeurs: dict[Caracteristique, int]) -> list[str]:
        erreurs = []
        if set(valeurs) != set(C):
            erreurs.append("Les six caractéristiques, chacune une fois.")
        for c, v in valeurs.items():
            if not CARACTERISTIQUE_MIN <= v <= CARACTERISTIQUE_MAX:
                erreurs.append(f"{c.libelle} : de {CARACTERISTIQUE_MIN} à {CARACTERISTIQUE_MAX}.")
        if sum(valeurs.values()) != POINTS_CARACTERISTIQUES:
            erreurs.append(f"{POINTS_CARACTERISTIQUES} points en tout, pas {sum(valeurs.values())}.")
        return erreurs

    def verifier_parcours(self, parcours: str) -> list[str]:
        return [] if parcours in self.univers.parcours else [f"Parcours inconnu dans cet univers : « {parcours} »."]

    def _verifier_points(self, points: dict[str, int], total: int, permises: set[str], autres: dict[str, int],
                         quoi: str) -> list[str]:
        erreurs = []
        for c, v in points.items():
            if c not in permises:
                erreurs.append(f"« {c} » : pas de points de {quoi} ici.")
            elif v < 0:
                erreurs.append(f"« {c} » : pas de points négatifs.")
            elif self.base(c) + autres.get(c, 0) + v > self.plafond(c):
                erreurs.append(f"« {c} » dépasserait {self.plafond(c)} à la création.")
        if sum(points.values()) != total:
            erreurs.append(f"{total} points de {quoi} en tout, pas {sum(points.values())}.")
        return erreurs

    def verifier_points_parcours(self, points: dict[str, int]) -> list[str]:
        return self._verifier_points(points, POINTS_PARCOURS, set(self.competences_parcours),
                                     self.points_personnels, "parcours")

    def verifier_points_personnels(self, points: dict[str, int]) -> list[str]:
        return self._verifier_points(points, POINTS_PERSONNELS, set(self.univers.competences_disponibles()),
                                     self.points_parcours, "personnels")

    def verifier_domaines(self, domaines: list[str]) -> list[str]:
        if not (self.univers.magie_active and self.univers.domaines):
            return [] if not domaines else ["Pas de magie dans cet univers."]
        connus = {d.nom for d in self.univers.domaines}
        erreurs = [f"Domaine inconnu : « {d} »." for d in domaines if d not in connus]
        if len(set(domaines)) != DOMAINES_PAR_PERSO:
            erreurs.append(f"{DOMAINES_PAR_PERSO} domaines différents.")
        return erreurs

    def verifier_equipement(self, equipement: dict) -> list[str]:
        if not self.univers.equipements.get(self.parcours):
            return []  # ce parcours n'a pas encore de listes dans cet univers : rien à choisir
        return self.univers.verifier_depart(self.parcours, equipement.get("arme"), equipement.get("armure"),
                                            equipement.get("implant"), equipement.get("vehicule"),
                                            equipement.get("objets", []))

    @staticmethod
    def verifier_roleplay(roleplay: dict) -> list[str]:
        erreurs = []
        for cle in ("nom", "motivation", "lien", "defaut"):
            texte = " ".join(str(roleplay.get(cle, "")).split())
            if not 0 < len(texte) <= ROLEPLAY_MAX[cle]:
                erreurs.append(f"« {cle} » : de 1 à {ROLEPLAY_MAX[cle]} caractères.")
        if len(str(roleplay.get("allure", ""))) > ROLEPLAY_MAX["allure"]:
            erreurs.append(f"« allure » : {ROLEPLAY_MAX['allure']} caractères au plus.")
        return erreurs

    # --- Fixer une étape : vérifiée d'abord -----------------------------------------------------------

    def fixer(self, etape: str, valeur):
        """Fixe une étape après l'avoir vérifiée (lève EtapeInvalide sinon). Changer les caractéristiques ou le
        parcours efface ce qui en dépend."""
        verifier = {"caracteristiques": self.verifier_caracteristiques, "parcours": self.verifier_parcours,
                    "points_parcours": self.verifier_points_parcours,
                    "points_personnels": self.verifier_points_personnels, "domaines": self.verifier_domaines,
                    "equipement": self.verifier_equipement, "roleplay": self.verifier_roleplay}[etape]
        erreurs = verifier(valeur)
        if erreurs:
            raise EtapeInvalide(erreurs)
        if etape == "caracteristiques":
            self.points_parcours, self.points_personnels = {}, {}
        if etape == "parcours" and valeur != self.parcours:
            self.points_parcours, self.points_personnels, self.equipement = {}, {}, {}
        if etape == "roleplay":
            valeur = {k: " ".join(str(v).split()) for k, v in valeur.items()}
        setattr(self, etape, valeur)

    def finaliser(self) -> tuple[Personnage, Depart | None]:
        """Le personnage, créé et vérifié par le moteur, et ce qu'il emporte en main."""
        r = self.roleplay
        try:
            perso = self.univers.creer_personnage(
                self.parcours, self.domaines, nom=r["nom"], caracteristiques=dict(self.caracteristiques),
                points_parcours=dict(self.points_parcours), points_personnels=dict(self.points_personnels),
                motivation=r["motivation"], lien=r["lien"], defaut=r["defaut"])
        except (CreationInvalide, UniversInvalide, KeyError) as erreur:
            raise EtapeInvalide(getattr(erreur, "erreurs", [str(erreur)])) from erreur
        perso.allure = r.get("allure", "")
        depart = None
        if self.univers.equipements.get(self.parcours):
            e = self.equipement
            depart = self.univers.equiper(perso, e.get("arme"), e.get("armure"), e.get("implant"), e.get("vehicule"),
                                          e.get("objets", []))
        return perso, depart


# --- Ce que le code propose : les chiffres ----------------------------------------------------------

def proposer_caracteristiques(b: Brouillon) -> dict[Caracteristique, int]:
    """240 points à parts égales, puis 60 points vers les caractéristiques que demande le parcours, par pas de 5."""
    valeurs = {c: BASE_CARACTERISTIQUE for c in C}
    poids = {c: 0 for c in C}
    for competence in b.competences_parcours or list(AFFINITES):
        poids[AFFINITES.get(competence, C.INTELLIGENCE)] += 1
    reste = POINTS_CARACTERISTIQUES - sum(valeurs.values())
    while reste > 0:
        # la caractéristique la plus demandée, relativement à ce qu'elle a déjà reçu
        c = max((c for c in C if valeurs[c] + PAS <= CARACTERISTIQUE_MAX),
                key=lambda c: (poids[c] / (1 + (valeurs[c] - BASE_CARACTERISTIQUE) / PAS), -list(C).index(c)))
        valeurs[c] += PAS
        reste -= PAS
    return valeurs


def _repartir(b: Brouillon, competences: list[str], montants: list[int], autres: dict[str, int]) -> dict[str, int]:
    """Donne à chaque compétence son montant sans dépasser son plafond ; ce qui déborde passe à la suivante,
    puis à toutes celles qui ont encore de la place."""
    points, report = {}, 0
    place = {c: b.plafond(c) - b.base(c) - autres.get(c, 0) for c in competences}
    for c, montant in zip(competences, montants):
        donne = max(0, min(montant + report, place[c]))
        points[c] = donne
        report = montant + report - donne
    for c in competences:
        if report <= 0:
            break
        donne = min(report, place[c] - points.get(c, 0))
        points[c] = points.get(c, 0) + donne
        report -= donne
    return {c: v for c, v in points.items() if v}


def proposer_points_parcours(b: Brouillon) -> dict[str, int]:
    return _repartir(b, b.competences_parcours, list(MODELE_PARCOURS), b.points_personnels)


def proposer_points_personnels(b: Brouillon) -> dict[str, int]:
    """30 en Esquive sans défense, 30 dans une arme sans compétence de combat, 20 en Perception, et le reste
    sur les meilleures compétences du parcours qui ont encore de la place."""
    parcours = set(b.competences_parcours)
    voeux = []
    if "Esquive" not in parcours:
        voeux.append(("Esquive", 30))
    if not parcours & {"Corps à corps", "Armes à distance", MAGIE}:
        voeux.append(("Armes à distance", 30))
    voeux.append(("Perception", 20))
    deja = sum(m for _, m in voeux)
    meilleures = sorted(b.competences_parcours, key=lambda c: -b.valeur(c))
    competences = [c for c, _ in voeux] + [c for c in meilleures if c not in dict(voeux)]
    montants = [m for _, m in voeux] + [POINTS_PERSONNELS - deja] + [0] * (len(competences) - len(voeux) - 1)
    return _repartir(b, competences, montants, b.points_parcours)


def proposer_domaines(b: Brouillon, hasard: random.Random) -> list[str]:
    if not (b.univers.magie_active and b.univers.domaines):
        return []
    return hasard.sample([d.nom for d in b.univers.domaines], DOMAINES_PAR_PERSO)


def proposer_equipement(b: Brouillon, hasard: random.Random) -> dict:
    """Les options se valent toutes (REGLES.md 5) : une au hasard par case, et 2 objets racontés."""
    listes = b.univers.equipements.get(b.parcours)
    if not listes:
        return {}
    choix = {case: hasard.choice(listes[cle]) for case, cle in (("arme", "armes"), ("armure", "armures"),
                                                                 ("implant", "implants"), ("vehicule", "vehicules"))
             if listes.get(cle)}
    choix["objets"] = hasard.sample(listes["objets"], 2)
    return choix


def proposer_chiffres(b: Brouillon, hasard: random.Random | None = None, parcours: str | None = None) -> Brouillon:
    """« Tout proposer », côté code : tout sauf le roleplay. Le parcours est tiré au hasard s'il n'est pas choisi."""
    hasard = hasard or random.Random()
    b.fixer("parcours", parcours or b.parcours or hasard.choice(sorted(b.univers.parcours)))
    b.fixer("caracteristiques", proposer_caracteristiques(b))
    b.fixer("points_parcours", proposer_points_parcours(b))
    b.fixer("points_personnels", proposer_points_personnels(b))
    b.fixer("domaines", proposer_domaines(b, hasard))
    b.fixer("equipement", proposer_equipement(b, hasard))
    return b


# --- Ce que le LLM propose : la personnalité --------------------------------------------------------

OUTIL_PERSONNAGE = {"type": "function", "function": {
    "name": "proposer_personnage",
    "description": "Donner au personnage un nom et une personnalité qui collent au cadre, à son métier et à son "
                   "équipement.",
    "parameters": {"type": "object", "additionalProperties": False, "required": list(ROLEPLAY_MAX), "properties": {
        "nom": {"type": "string", "description": "Son nom, dans le style du cadre."},
        "motivation": {"type": "string", "description": "Ce que le personnage cherche, en une phrase."},
        "lien": {"type": "string", "description": "Quelqu'un ou quelque chose qui compte à ses yeux, en une phrase."},
        "defaut": {"type": "string", "description": "Son défaut, en une phrase."},
        "allure": {"type": "string", "description": "Son apparence et son allure, en deux phrases."},
    }}}}
ESSAIS = 2
SEXES = ("une femme", "un homme")  # tiré par le code : laissé au LLM, le personnage est presque toujours un homme


INITIALES = "ABCDEFGHIJKLMNOPRSTVY"  # trois sont tirées : sans elles, les mêmes prénoms reviennent


def _demande_personnalite(b: Brouillon, erreurs: list[str], sexe: str, initiales: list[str]) -> list[dict]:
    u, e = b.univers, b.equipement
    objets = ", ".join(e.get("objets", [])) or "aucun"
    equipement = ", ".join(str(e[c]) for c in ("arme", "armure", "implant", "vehicule") if e.get(c)) or "rien"
    texte = (f"Univers : {u.nom} ({u.genre}). Cadre : {u.cadre}\n"
             f"Le personnage du joueur est {sexe}, {b.parcours} : {u.descriptions.get(b.parcours, '')}\n"
             f"Équipement de départ : {equipement} ; objets : {objets}.\n"
             "Appelle proposer_personnage avec son nom, sa motivation, son lien, son défaut et son allure. "
             "Une phrase chacun (deux pour l'allure), en français, sans chiffres de jeu. "
             "Surprends : évite le premier lien et la première silhouette qui te viennent pour ce métier. "
             f"Son prénom commence par l'une de ces lettres, celle qui va le mieux au cadre : {', '.join(initiales)}.")
    if erreurs:
        texte += "\nTa proposition précédente a des erreurs : " + " ; ".join(erreurs)
    return [{"role": "system", "content": "Tu aides un joueur à créer son personnage de jeu de rôle."},
            {"role": "user", "content": texte}]


def proposer_personnalite(serveur, b: Brouillon, budget: int | None = None,
                          hasard: random.Random | None = None) -> dict | None:
    """Le nom et la personnalité, par le LLM ; vérifiés par le code. None si le LLM n'y arrive pas :
    le joueur les écrit lui-même. Le code tire au sort si c'est une femme ou un homme."""
    erreurs = []
    hasard = hasard or random.Random()
    sexe, initiales = hasard.choice(SEXES), sorted(hasard.sample(INITIALES, 3))
    for _ in range(ESSAIS):
        reponse = serveur.discuter(_demande_personnalite(b, erreurs, sexe, initiales), [OUTIL_PERSONNAGE], budget)
        message = reponse["choices"][0]["message"]
        appel = next((a for a in message.get("tool_calls") or []
                      if a["function"]["name"] == "proposer_personnage"), None)
        if appel is None:
            erreurs = ["tu n'as pas appelé l'outil proposer_personnage"]
            continue
        arguments = appel["function"]["arguments"]
        try:
            roleplay = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
        except (ValueError, TypeError):
            erreurs = ["arguments illisibles"]
            continue
        roleplay = {k: " ".join(str(roleplay.get(k, "")).split()) for k in ROLEPLAY_MAX}
        erreurs = Brouillon.verifier_roleplay(roleplay)
        if not erreurs:
            return roleplay
    return None


def tout_proposer(univers: Univers, serveur=None, budget: int | None = None, hasard: random.Random | None = None,
                  parcours: str | None = None) -> Brouillon:
    """Un brouillon complet : les chiffres par le code, la personnalité par le LLM (si un serveur répond)."""
    b = proposer_chiffres(Brouillon(univers), hasard, parcours)
    if serveur is not None:
        roleplay = proposer_personnalite(serveur, b, budget, hasard)
        if roleplay:
            b.fixer("roleplay", roleplay)
    return b
