"""Les outils du MJ : le moteur exposé au LLM sous forme d'appels de fonctions.

Le LLM ne lance jamais un dé lui-même : il appelle un outil, le moteur applique les
règles et renvoie le résultat, que le LLM raconte. Chaque outil a un schéma JSON au
format « function calling » compatible OpenAI (celui que comprend llama.cpp). Les listes
fermées (difficultés, chocs, défenses…) y sont des énumérations : le LLM ne peut pas
inventer une valeur, et le moteur vérifie de toute façon chaque argument.

Une erreur ne fait jamais planter la partie : elle est renvoyée au LLM sous la forme
{"erreur": "…"} pour qu'il corrige son appel.
"""

import json
from dataclasses import dataclass, field
from typing import Callable

from aria import progression, sante_mentale, soins
from aria.combat import (
    ActionImpossible,
    BonusMajeure,
    BudgetRound,
    Combat,
    Combattant,
    Couvert,
    Defense,
    FichePnj,
    RapportAttaque,
    TypeAction,
    laisser_pour_mort,
    tester_embuscade,
)
from aria.des import Des
from aria.personnage import Caracteristique, Personnage
from aria.reglages import Jalon
from aria.resolution import Difficulte, Resultat, forcer, tester
from aria.temps import Moment, Periode
from aria.univers import Univers

JOUEUR = "joueur"
DIFFICULTES = {"facile": Difficulte.FACILE, "normale": Difficulte.NORMALE,
               "difficile": Difficulte.DIFFICILE, "extrême": Difficulte.EXTREME}
DEFENSES = {"esquive": Defense.ESQUIVE, "riposte": Defense.RIPOSTE, "aucune": None}
COUVERTS = {"aucun": Couvert.AUCUN, "partiel": Couvert.PARTIEL, "lourd": Couvert.LOURD}
BONUS_MAJEURE = {"dé de dégâts": BonusMajeure.DE_SUPPLEMENTAIRE, "désarmer": BonusMajeure.DESARMER,
                 "repousser": BonusMajeure.REPOUSSER}
JALONS = {"objectif": Jalon.OBJECTIF, "arc": Jalon.ARC, "motivation": Jalon.MOTIVATION, "session": Jalon.SESSION}
REPOS = {"court": soins.Repos.COURT, "moyen": soins.Repos.MOYEN, "long": soins.Repos.LONG}
# Bornes d'un PNJ créé par le MJ : il choisit sa force, dans des limites raisonnables
PNJ_COMBAT = (5, 85)
PNJ_PV = (1, 40)
PNJ_COMPETENCE = (0, 90)


class ErreurOutil(Exception):
    """Un appel d'outil invalide. Le message est renvoyé tel quel au LLM."""


# --- Vérification des arguments (un petit sous-ensemble de JSON Schema) ---------------------

def _verifier(valeur, schema: dict, chemin: str):
    attendu = schema.get("type")
    types = {"string": str, "integer": int, "boolean": bool, "array": list, "object": dict}
    if attendu and (not isinstance(valeur, types[attendu]) or (attendu == "integer" and isinstance(valeur, bool))):
        raise ErreurOutil(f"« {chemin} » doit être de type {attendu}.")
    if "enum" in schema and valeur not in schema["enum"]:
        raise ErreurOutil(f"« {chemin} » vaut {valeur!r}, mais doit être l'une de ces valeurs : {schema['enum']}.")
    if "minimum" in schema and valeur < schema["minimum"]:
        raise ErreurOutil(f"« {chemin} » doit valoir au moins {schema['minimum']}.")
    if "maximum" in schema and valeur > schema["maximum"]:
        raise ErreurOutil(f"« {chemin} » doit valoir au plus {schema['maximum']}.")
    if attendu == "array":
        for i, element in enumerate(valeur):
            _verifier(element, schema.get("items", {}), f"{chemin}[{i}]")
    if attendu == "object":
        _verifier_objet(valeur, schema, chemin)


def _verifier_objet(arguments: dict, schema: dict, chemin: str = "arguments"):
    proprietes = schema.get("properties", {})
    for cle in arguments:
        if cle not in proprietes and schema.get("additionalProperties") is not True:
            raise ErreurOutil(f"Paramètre inconnu : « {cle} ». Paramètres possibles : {sorted(proprietes)}.")
    for cle in schema.get("required", []):
        if cle not in arguments:
            raise ErreurOutil(f"Paramètre obligatoire manquant : « {cle} ».")
    for cle, valeur in arguments.items():
        if cle in proprietes:
            _verifier(valeur, proprietes[cle], cle)


@dataclass
class Outil:
    nom: str
    description: str
    parametres: Callable[["Session"], dict]  # le schéma dépend de la session (PNJ présents, univers…)
    fonction: Callable[..., dict]


def _resume(resultat: Resultat) -> dict:
    return {"jet": resultat.jet, "valeur": resultat.valeur, "degre": resultat.degre.libelle, "reussi": resultat.reussi}


# --- La session de jeu ------------------------------------------------------------------------

@dataclass
class Session:
    """Tout ce que le MJ manipule pendant une partie : l'univers, le perso, les PNJ, le combat, le temps."""

    univers: Univers
    personnage: Personnage
    des: Des = field(default_factory=Des)
    moment: Moment = Moment(1, Periode.MATIN)
    arme: str | None = None
    armure: str | None = None
    pnj: dict[str, Combattant] = field(default_factory=dict)
    combat: Combat | None = None
    dernier_test: dict | None = None
    journal: list[dict] = field(default_factory=list)

    def __post_init__(self):
        u = self.univers
        self.joueur = Combattant(self.personnage, "joueur",
                                 u.arme(self.arme) if self.arme else None,
                                 u.armure(self.armure) if self.armure else None)
        # Le LLM parle avec les noms de l'univers (« Piratage ») ; le moteur, avec ceux du socle.
        self.noms_competences = {u.nom_affiche(nom): nom for nom in self.personnage.competences}

    # --- Outils : catalogue et appel ---

    def schemas(self) -> list[dict]:
        """La liste des outils au format OpenAI, à envoyer au LLM à chaque tour."""
        return [{"type": "function",
                 "function": {"name": o.nom, "description": o.description, "parameters": o.parametres(self)}}
                for o in OUTILS.values()]

    def appeler(self, nom: str, arguments: "dict | str | None" = None) -> dict:
        """Appelle un outil par son nom. Ne lève jamais d'exception : les erreurs sont renvoyées en clair."""
        try:
            if nom not in OUTILS:
                raise ErreurOutil(f"Outil inconnu : « {nom} ». Outils disponibles : {sorted(OUTILS)}.")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments.strip() else {}
                except json.JSONDecodeError as erreur:
                    raise ErreurOutil(f"Arguments illisibles (JSON invalide) : {erreur}.") from erreur
            arguments = dict(arguments or {})
            outil = OUTILS[nom]
            arguments = self._normaliser(arguments)
            _verifier_objet(arguments, outil.parametres(self))
            resultat = outil.fonction(self, **arguments)
        except (ErreurOutil, ActionImpossible, soins.SoinImpossible, progression.ProgressionImpossible,
                ValueError, KeyError) as erreur:
            resultat = {"erreur": str(erreur).strip("'\"")}
        self.journal.append({"outil": nom, "arguments": arguments, "resultat": resultat})
        return resultat

    def _normaliser(self, arguments: dict) -> dict:
        """Accepte aussi les noms de socle (« Technologie ») là où le schéma attend ceux de l'univers."""
        if "competence" in arguments:
            inverse = {socle: affiche for affiche, socle in self.noms_competences.items()}
            arguments["competence"] = inverse.get(arguments["competence"], arguments["competence"])
        return arguments

    # --- Aides internes ---

    def combattant(self, identifiant: str) -> Combattant:
        if identifiant == JOUEUR:
            return self.joueur
        if identifiant not in self.pnj:
            raise ErreurOutil(f"PNJ inconnu : « {identifiant} ». PNJ présents : {sorted(self.pnj)}.")
        return self.pnj[identifiant]

    def combat_en_cours(self) -> Combat:
        if self.combat is None:
            raise ErreurOutil("Aucun combat en cours : appelle d'abord debut_combat.")
        return self.combat

    def ids(self) -> list[str]:
        return [JOUEUR] + sorted(self.pnj)


OUTILS: dict[str, Outil] = {}


def outil(description: str, parametres: Callable[[Session], dict]):
    """Déclare une fonction comme outil du MJ. Son nom d'outil est son nom de fonction."""
    def enregistrer(fonction):
        OUTILS[fonction.__name__] = Outil(fonction.__name__, description, parametres, fonction)
        return fonction
    return enregistrer


def _objet(proprietes: dict, requis: list[str] = ()) -> dict:
    return {"type": "object", "properties": proprietes, "required": list(requis), "additionalProperties": False}


def _enum(valeurs, description: str = "") -> dict:
    schema = {"type": "string", "enum": list(valeurs)}
    if description:
        schema["description"] = description
    return schema


def _ids(session: Session, description: str) -> dict:
    return _enum(session.ids(), description)


def _difficulte() -> dict:
    return _enum(DIFFICULTES, "Facile +20, normale 0, difficile −20, extrême −40.")


# --- État -------------------------------------------------------------------------------------

def _etat_combattant(c: Combattant) -> dict:
    f = c.fiche
    etat = {"nom": c.nom, "pv": f.pv, "pv_max": f.pv_max, "etat": f.etat.value, "blessure_grave": f.blessure_grave,
            "arme": c.arme.nom if c.arme else None, "armure": c.armure.nom if c.armure else None}
    if c.arme and c.arme.munitions:
        etat["munitions"] = c.munitions_restantes()
    return etat


@outil("Consulter l'état du personnage joueur, du temps et du combat en cours. N'a aucun effet sur le jeu.",
       lambda s: _objet({}))
def etat(session: Session) -> dict:
    p = session.personnage
    resultat = {
        "moment": str(session.moment),
        "joueur": _etat_combattant(session.joueur) | {
            "sante_mentale": p.sm, "sm_max": p.sm_max, "points_destin": p.points_destin, "xp": p.xp,
            "troubles": [t.type.value for t in p.troubles], "folie": p.folie,
        },
        "pnj": {i: _etat_combattant(c) for i, c in session.pnj.items()},
    }
    if session.combat:
        resultat["combat"] = {"round": session.combat.round, "ordre": [c.nom for c in session.combat.ordre],
                              "budget_joueur": {t.value: session.joueur.budget.restants(t) for t in TypeAction}}
    return resultat


@outil("Faire avancer le temps à la période suivante (matin → après-midi → nuit → matin du jour suivant).",
       lambda s: _objet({}))
def avancer_temps(session: Session) -> dict:
    session.moment = session.moment.suivant()
    return {"moment": str(session.moment)}


# --- Tests hors combat ------------------------------------------------------------------------

@outil("Faire un test de compétence du personnage joueur. À utiliser dès qu'une action a une issue incertaine "
       "et des conséquences. Le moteur lance le d100 ; raconte ensuite le résultat selon son degré.",
       lambda s: _objet({
           "competence": _enum(sorted(s.noms_competences), "La compétence, avec son nom dans cet univers."),
           "difficulte": _difficulte(),
           "pourquoi": {"type": "string", "description": "Ce que le personnage tente, en une phrase."},
       }, ["competence", "difficulte"]))
def test_competence(session: Session, competence: str, difficulte: str, pourquoi: str = "") -> dict:
    socle = session.noms_competences[competence]
    valeur = session.joueur.valeur(socle)
    resultat = tester(session.des, valeur, DIFFICULTES[difficulte])
    progression.cocher(session.personnage, socle, resultat)
    session.dernier_test = {"valeur": valeur, "difficulte": difficulte, "resultat": resultat, "nom": competence}
    return {"competence": competence, **_resume(resultat)}


@outil("Faire un test de caractéristique du personnage joueur, quand aucune compétence ne correspond.",
       lambda s: _objet({
           "caracteristique": _enum([c.libelle for c in Caracteristique]),
           "difficulte": _difficulte(),
       }, ["caracteristique", "difficulte"]))
def test_caracteristique(session: Session, caracteristique: str, difficulte: str) -> dict:
    carac = next(c for c in Caracteristique if c.libelle == caracteristique)
    valeur = session.personnage.carac(carac)
    resultat = tester(session.des, valeur, DIFFICULTES[difficulte])
    session.dernier_test = {"valeur": valeur, "difficulte": difficulte, "resultat": resultat, "nom": caracteristique}
    return {"caracteristique": caracteristique, **_resume(resultat)}


@outil("Forcer le dernier test raté : le joueur retente en changeant d'approche, une seule fois. "
       "S'il rate encore, la conséquence doit être grave. À n'utiliser que si le joueur le demande.",
       lambda s: _objet({}))
def forcer_jet(session: Session) -> dict:
    if not session.dernier_test:
        raise ErreurOutil("Aucun test à forcer.")
    t = session.dernier_test
    resultat = forcer(session.des, t["valeur"], t["resultat"], DIFFICULTES[t["difficulte"]])
    session.dernier_test = dict(t, resultat=resultat)
    return {"test": t["nom"], **_resume(resultat), "consequence_grave": resultat.consequence_grave}


# --- Santé mentale, soins, repos ---------------------------------------------------------------

@outil("Infliger un choc au personnage joueur. Choisis le choc dans la liste ; le moteur calcule sa gravité "
       "(lien, accoutumance, réglages de l'univers) et lance le test de Santé mentale.",
       lambda s: _objet({
           "choc": _enum([c.name for c in sante_mentale.Choc],
                         " ; ".join(f"{c.name} : {c.description}" for c in sante_mentale.Choc)),
           "concerne_lien": {"type": "boolean", "description": "Vrai si le choc touche le lien du personnage."},
           "en_combat": {"type": "boolean", "description": "Vrai si le choc survient en plein combat."},
       }, ["choc"]))
def choc(session: Session, choc: str, concerne_lien: bool = False, en_combat: bool = False) -> dict:
    r = sante_mentale.subir_choc(session.des, session.personnage, sante_mentale.Choc[choc], session.moment,
                                 session.univers.reglages_mentaux(), concerne_lien, en_combat)
    if r.gravite is None:
        return {"choc": r.choc.description, "test": False, "explication": "Ce choc ne déclenche pas de test ici."}
    resultat = {"choc": r.choc.description, "gravite": r.gravite.name.lower(), **_resume(r.test),
                "perte": r.perte, "sante_mentale": r.sm_apres}
    if r.crise:
        resultat["crise"] = {"type": r.crise.value, "rounds": r.duree_crise}
    if r.trouble:
        resultat["trouble"] = r.trouble.type.value
    if r.folie:
        resultat["folie"] = True
    return resultat


@outil("Soigner le personnage joueur avec un jet de Médecine (un seul par demi-journée). "
       "Le soigneur peut être le joueur lui-même ou un PNJ créé avec creer_pnj.",
       lambda s: _objet({"soigneur": _ids(s, "Qui soigne.")}, ["soigneur"]))
def soigner(session: Session, soigneur: str) -> dict:
    r = soins.soigner(session.des, session.combattant(soigneur).fiche, session.personnage, session.moment)
    return {**_resume(r.test), "pv_gagnes": r.gain, "pv": r.pv_apres, "blessure_grave_soignee": r.blessure_grave_soignee}


@outil("Faire se reposer le personnage joueur : court (30 min) ou moyen (1 à 2 h) une fois par demi-journée, "
       "long la nuit.",
       lambda s: _objet({"type": _enum(REPOS), "interrompu": {"type": "boolean"}}, ["type"]))
def repos(session: Session, type: str, interrompu: bool = False) -> dict:
    r = soins.reposer(session.personnage, REPOS[type], session.moment, session.univers.curseur, interrompu)
    return {"repos": type, "pv_gagnes": r.gain, "pv": r.pv_apres, "blessure_grave_guerie": r.blessure_grave_guerie}


@outil("Faire récupérer de la Santé mentale au joueur : une discussion (avec son lien ou longuement avec "
       "quelqu'un, une fois par jour) ou une thérapie pendant le repos long (une fois par nuit).",
       lambda s: _objet({
           "source": _enum(["discussion", "thérapie"]),
           "soignant": _ids(s, "Pour une thérapie : qui l'accompagne (le joueur seul, ou un PNJ)."),
           "competence": _enum(["Perspicacité", "Médecine"], "Pour une thérapie."),
       }, ["source"]))
def recuperer_sante_mentale(session: Session, source: str, soignant: str = JOUEUR,
                            competence: str = "Perspicacité") -> dict:
    if source == "discussion":
        r = sante_mentale.discussion(session.des, session.personnage, session.moment)
    else:
        r = sante_mentale.therapie(session.des, session.combattant(soignant).fiche, session.personnage,
                                   session.moment, competence)
    resultat = {"sm_gagnee": r.gain, "sante_mentale": r.sm_apres}
    if r.test:
        resultat.update(_resume(r.test))
    if r.troubles_gueris:
        resultat["troubles_gueris"] = [t.type.value for t in r.troubles_gueris]
    return resultat


@outil("Enregistrer un jalon de campagne atteint par le joueur (objectif ou quête réussis, arc terminé, "
       "motivation accomplie, fin de session). Il rapporte de la Santé mentale et de l'XP.",
       lambda s: _objet({"jalon": _enum(JALONS)}, ["jalon"]))
def jalon(session: Session, jalon: str) -> dict:
    r = sante_mentale.jalon_atteint(session.des, session.personnage, JALONS[jalon])
    xp = progression.gagner_xp(session.personnage, JALONS[jalon])
    return {"jalon": jalon, "sm_gagnee": r.gain, "sante_mentale": r.sm_apres, "xp_gagnee": xp}


@outil("Utiliser un point de destin du joueur, seulement s'il l'accepte : « laisse_pour_mort » quand il "
       "vient de mourir, « sortir_de_la_folie » quand il a sombré.",
       lambda s: _objet({"usage": _enum(["laisse_pour_mort", "sortir_de_la_folie"])}, ["usage"]))
def point_de_destin(session: Session, usage: str) -> dict:
    if usage == "laisse_pour_mort":
        laisser_pour_mort(session.joueur)
    else:
        sante_mentale.sauver_de_la_folie(session.personnage)
    return {"usage": usage, "points_destin_restants": session.personnage.points_destin,
            "etat": session.personnage.etat.value, "sante_mentale": session.personnage.sm}


# --- PNJ et combat ----------------------------------------------------------------------------

@outil("Créer un PNJ (ennemi, allié ou passant) avec un profil simplifié. Son identifiant sert ensuite "
       "dans les autres outils. L'arme et l'armure viennent de l'armurerie de l'univers.",
       lambda s: _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple ganger_couteau."},
           "nom": {"type": "string"},
           "camp": _enum(["ennemis", "allies", "neutres"]),
           "combat": {"type": "integer", "minimum": PNJ_COMBAT[0], "maximum": PNJ_COMBAT[1],
                      "description": "Pourcentage pour attaquer, esquiver et riposter (45 = voyou ordinaire)."},
           "pv": {"type": "integer", "minimum": PNJ_PV[0], "maximum": PNJ_PV[1]},
           "arme": _enum([a.nom for a in s.univers.armes]),
           "armure": _enum([a.nom for a in s.univers.armures]),
           "dexterite": {"type": "integer", "minimum": 15, "maximum": 90},
           "competences": {"type": "object", "additionalProperties": True,
                           "description": "Autres talents, par exemple {\"Médecine\": 70}."},
       }, ["identifiant", "nom", "camp", "combat", "pv"]))
def creer_pnj(session: Session, identifiant: str, nom: str, camp: str, combat: int, pv: int,
              arme: str | None = None, armure: str | None = None, dexterite: int = 50,
              competences: dict | None = None) -> dict:
    if identifiant == JOUEUR or identifiant in session.pnj:
        raise ErreurOutil(f"L'identifiant « {identifiant} » est déjà pris.")
    talents = {}
    for nom_competence, valeur in (competences or {}).items():
        socle = session.noms_competences.get(nom_competence, nom_competence)
        if not isinstance(valeur, int) or not PNJ_COMPETENCE[0] <= valeur <= PNJ_COMPETENCE[1]:
            raise ErreurOutil(f"La compétence « {nom_competence} » d'un PNJ va de 0 à {PNJ_COMPETENCE[1]}.")
        talents[socle] = valeur
    fiche = FichePnj(nom, combat=combat, pv_max_base=pv, dexterite=dexterite, competences=talents)
    u = session.univers
    session.pnj[identifiant] = Combattant(fiche, camp, u.arme(arme) if arme else None,
                                          u.armure(armure) if armure else None)
    return {"pnj": identifiant, **_etat_combattant(session.pnj[identifiant])}


@outil("Tester une embuscade : la Perception du joueur contre la Discrétion des agresseurs.",
       lambda s: _objet({"discretion_agresseurs": {"type": "integer", "minimum": 0, "maximum": 100}},
                        ["discretion_agresseurs"]))
def embuscade(session: Session, discretion_agresseurs: int) -> dict:
    r = tester_embuscade(session.des, session.joueur.valeur("Perception"), discretion_agresseurs)
    return {"discretion": _resume(r.discretion), "perception": _resume(r.perception), "joueur_surpris": r.surpris}


@outil("Commencer un combat entre le joueur et des PNJ. Le moteur fixe l'ordre d'initiative.",
       lambda s: _objet({
           "pnj": {"type": "array", "items": _enum(sorted(s.pnj)), "description": "Les PNJ qui combattent."},
           "surpris": _enum(["personne", "joueur", "ennemis"], "Le camp surpris perd son premier round."),
       }, ["pnj"]))
def debut_combat(session: Session, pnj: list, surpris: str = "personne") -> dict:
    if session.combat:
        raise ErreurOutil("Un combat est déjà en cours.")
    if not pnj:
        raise ErreurOutil("Il faut au moins un PNJ pour un combat.")
    participants = [session.joueur] + [session.combattant(i) for i in pnj]
    if surpris == "joueur":
        surpris_liste = [session.joueur]
    elif surpris == "ennemis":
        surpris_liste = [c for c in participants if c.camp == "ennemis"]
    else:
        surpris_liste = []
    session.combat = Combat(session.des, participants, session.univers.curseur, surpris_liste)
    return {"round": 1, "ordre_initiative": [c.nom for c in session.combat.ordre]}


@outil("Une action de combat sans attaque : se déplacer, viser (+20 au tir de ce round, interdit après un "
       "déplacement), recharger, ou dégainer une arme de l'armurerie (« aucune » pour ranger).",
       lambda s: _objet({
           "qui": _ids(s, "Qui agit."),
           "action": _enum(["deplacer", "viser", "recharger", "degainer"]),
           "arme": _enum([a.nom for a in s.univers.armes] + ["aucune"], "Pour degainer."),
       }, ["qui", "action"]))
def action_combat(session: Session, qui: str, action: str, arme: str | None = None) -> dict:
    c, combattant = session.combat_en_cours(), session.combattant(qui)
    if action == "deplacer":
        c.deplacer(combattant)
    elif action == "viser":
        c.viser(combattant)
    elif action == "recharger":
        c.recharger(combattant)
    else:
        if arme is None:
            raise ErreurOutil("Pour degainer, précise l'arme.")
        c.degainer(combattant, None if arme == "aucune" else session.univers.arme(arme))
    return {"qui": qui, "action": action,
            "budget_restant": {t.value: combattant.budget.restants(t) for t in TypeAction},
            **({"munitions": combattant.munitions_restantes()} if combattant.arme and combattant.arme.munitions else {})}


def _rapport_attaque(rapport: RapportAttaque) -> dict:
    resultat = {"attaquant": rapport.attaquant, "cible": rapport.cible, "attaque": _resume(rapport.attaque),
                "issue": rapport.issue.value}
    if rapport.defense:
        resultat["defense"] = _resume(rapport.defense)
    if rapport.touche:
        b = rapport.blessure
        resultat["touche"] = {"qui": rapport.touche, "degats_bruts": rapport.degats_bruts,
                              "armure": rapport.protection, "degats": b.degats, "pv": b.pv_apres,
                              "blessure_grave": b.blessure_grave, "etat": b.etat.value}
        if b.test_constitution:
            resultat["touche"]["test_constitution"] = _resume(b.test_constitution)
    if rapport.effets:
        resultat["effets"] = rapport.effets
    return resultat


@outil("Une attaque en combat (action simple). Le moteur gère la défense, les dégâts, l'armure et les blessures. "
       "Au corps à corps, la cible peut esquiver ou riposter ; contre un tir, seul le couvert compte.",
       lambda s: _objet({
           "attaquant": _ids(s, "Qui attaque."),
           "cible": _ids(s, "Qui est visé."),
           "defense": _enum(DEFENSES, "Au corps à corps seulement. Demande au joueur quand c'est lui la cible."),
           "couvert": _enum(COUVERTS, "Pour un tir : le couvert de la cible (partiel −20, lourd −40)."),
           "difficulte": _difficulte(),
           "bonus_majeure": _enum(BONUS_MAJEURE, "Le bonus choisi en cas de réussite majeure."),
       }, ["attaquant", "cible"]))
def attaquer(session: Session, attaquant: str, cible: str, defense: str = "aucune", couvert: str = "aucun",
             difficulte: str = "normale", bonus_majeure: str = "dé de dégâts") -> dict:
    if attaquant == cible:
        raise ErreurOutil("On ne s'attaque pas soi-même.")
    rapport = session.combat_en_cours().attaquer(
        session.combattant(attaquant), session.combattant(cible), DEFENSES[defense], COUVERTS[couvert],
        BONUS_MAJEURE[bonus_majeure], DIFFICULTES[difficulte])
    return _rapport_attaque(rapport)


@outil("Stabiliser un combattant mourant avec un jet de Médecine (action simple).",
       lambda s: _objet({"soigneur": _ids(s, "Qui soigne."), "mourant": _ids(s, "Qui est mourant.")},
                        ["soigneur", "mourant"]))
def stabiliser(session: Session, soigneur: str, mourant: str) -> dict:
    r = session.combat_en_cours().stabiliser(session.combattant(soigneur), session.combattant(mourant))
    return {**_resume(r), "etat": session.combattant(mourant).fiche.etat.value}


@outil("Terminer le round : les mourants font leur test de Constitution, puis chacun retrouve ses actions.",
       lambda s: _objet({}))
def fin_de_round(session: Session) -> dict:
    c = session.combat_en_cours()
    tests = [{"qui": nom, **_resume(t)} for nom, t in c.fin_de_round()]
    return {"round": c.round, "tests_des_mourants": tests,
            "etats": {i: session.combattant(i).fiche.etat.value for i in session.ids()}}


@outil("Terminer le combat (fuite, reddition, victoire…). Les PNJ restent connus pour la suite.",
       lambda s: _objet({}))
def fin_combat(session: Session) -> dict:
    session.combat_en_cours()
    session.combat = None
    for combattant in [session.joueur, *session.pnj.values()]:
        combattant.surpris = combattant.vise = combattant.a_vise = combattant.sursis = False
        combattant.budget = BudgetRound()
        combattant.defenses_ce_round = 0
    return {"etats": {i: session.combattant(i).fiche.etat.value for i in session.ids()}}
