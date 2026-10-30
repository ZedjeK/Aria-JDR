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
from aria.campagne import Campagne
from aria.compte_rendu import decrire
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
from aria.memoire import LONGUEURS, MORT, VIVANT, Memoire
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
RAPPEL_REUSSITE = "Test réussi : raconte-le. Il ne se relance pas pour faire mieux, même si le joueur le demande."
MOMENTS_FORTS_MAX = 600  # caractères : trois phrases, pas un roman


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


def _test(resultat: Resultat) -> dict:
    """Le résumé d'un test du joueur, avec le rappel au moment où le MJ en a besoin."""
    return _resume(resultat) | ({"consigne": RAPPEL_REUSSITE} if resultat.reussi else {})


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
    campagne: Campagne | None = None  # None : rien n'est écrit sur le disque (le banc d'essai)
    rounds: list[tuple[int, list[str]]] = field(default_factory=list)  # le combat en cours, round par round
    debut_round: int = 0  # l'indice, dans le journal, du premier appel du round en cours

    def __post_init__(self):
        u = self.univers
        self.joueur = Combattant(self.personnage, "joueur",
                                 u.arme(self.arme) if self.arme else None,
                                 u.armure(self.armure) if self.armure else None)
        # Le LLM parle avec les noms de l'univers (« Piratage ») ; le moteur, avec ceux du socle.
        self.noms_competences = {u.nom_affiche(nom): nom for nom in self.personnage.competences}
        self.memoire = Memoire(self.campagne)

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

    def participant(self, identifiant: str) -> Combattant:
        """Un combattant du combat en cours ; refuse celui qui n'y est pas (créé mais jamais entré)."""
        combattant = self.combattant(identifiant)
        if combattant not in self.combat_en_cours().ordre:
            raise ErreurOutil(f"{combattant.nom} ({identifiant}) ne fait pas partie du combat : "
                              "fais-le entrer avec rejoindre_combat.")
        return combattant

    def ids(self) -> list[str]:
        return [JOUEUR] + sorted(self.pnj)

    def identifiant(self, combattant: Combattant) -> str:
        return JOUEUR if combattant is self.joueur else next(i for i, c in self.pnj.items() if c is combattant)

    def evenements_du_round(self) -> list[str]:
        return [ligne for entree in self.journal[self.debut_round:]
                for ligne in decrire(entree["outil"], entree["arguments"], entree["resultat"], self)]


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
        au_tour_de = session.combat.au_tour_de
        resultat["combat"] = {"round": session.combat.round, "ordre": [c.nom for c in session.combat.ordre],
                              "au_tour_de": au_tour_de.nom if au_tour_de else None,
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
    return {"competence": competence, **_test(resultat)}


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
    return {"caracteristique": caracteristique, **_test(resultat)}


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
    if session.memoire.est_mort(identifiant):
        raise ErreurOutil(f"{session.memoire.pnj[identifiant].nom} ({identifiant}) est mort : "
                          "la mémoire de la campagne s'en souvient.")
    if identifiant == JOUEUR or identifiant in session.pnj:
        # Le MJ voulait sans doute un nouveau PNJ : on lui dit qui existe déjà et quel identifiant est libre
        libre = next(f"{identifiant}_{n}" for n in range(2, 100) if f"{identifiant}_{n}" not in session.pnj)
        connus = ", ".join(f"{i} ({c.nom})" for i, c in session.pnj.items())
        raise ErreurOutil(f"L'identifiant « {identifiant} » est déjà pris. PNJ existants : {connus}. "
                          f"Pour un nouveau PNJ, prends un autre identifiant, par exemple « {libre} ».")
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


@outil("Commencer un combat entre le joueur et des PNJ. Le moteur fixe l'ordre d'initiative et tient le tour "
       "de parole : chacun agit à son tour, puis fin_de_tour passe au suivant.",
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
    session.combat = Combat(session.des, participants, session.univers.curseur, surpris_liste, tour_par_tour=True)
    session.rounds, session.debut_round = [], len(session.journal) + 1  # + 1 : cet appel-ci
    return {"round": 1, "ordre_initiative": [c.nom for c in session.combat.ordre],
            "au_tour_de": _qui_joue(session), "consigne": _consigne(session), "fiche": _fiche(session)}


@outil("Faire entrer des PNJ dans le combat en cours (renforts, passant qui s'en mêle). Le moteur les place "
       "dans l'ordre d'initiative.",
       lambda s: _objet({"pnj": {"type": "array", "items": _enum(sorted(s.pnj)), "description": "Les PNJ qui entrent."}},
                        ["pnj"]))
def rejoindre_combat(session: Session, pnj: list) -> dict:
    c = session.combat_en_cours()
    if not pnj:
        raise ErreurOutil("Indique au moins un PNJ.")
    for identifiant in pnj:
        c.rejoindre(session.combattant(identifiant))
    return {"ordre_initiative": [x.nom for x in c.ordre], "au_tour_de": _qui_joue(session),
            "consigne": _consigne(session)}


@outil("Une action de combat sans attaque : se déplacer, viser (+20 au tir de ce round, interdit après un "
       "déplacement), recharger, ou dégainer une arme de l'armurerie (« aucune » pour ranger).",
       lambda s: _objet({
           "qui": _ids(s, "Qui agit."),
           "action": _enum(["deplacer", "viser", "recharger", "degainer"]),
           "arme": _enum([a.nom for a in s.univers.armes] + ["aucune"], "Pour degainer."),
       }, ["qui", "action"]))
def action_combat(session: Session, qui: str, action: str, arme: str | None = None) -> dict:
    c, combattant = session.combat_en_cours(), session.participant(qui)
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
        session.participant(attaquant), session.participant(cible), DEFENSES[defense], COUVERTS[couvert],
        BONUS_MAJEURE[bonus_majeure], DIFFICULTES[difficulte])
    return _rapport_attaque(rapport)


@outil("Stabiliser un combattant mourant avec un jet de Médecine (action simple).",
       lambda s: _objet({"soigneur": _ids(s, "Qui soigne."), "mourant": _ids(s, "Qui est mourant.")},
                        ["soigneur", "mourant"]))
def stabiliser(session: Session, soigneur: str, mourant: str) -> dict:
    r = session.combat_en_cours().stabiliser(session.participant(soigneur), session.participant(mourant))
    return {**_resume(r), "etat": session.combattant(mourant).fiche.etat.value}


# --- Le tour de parole et la fiche du combat ---------------------------------------------------

def _qui_joue(session: Session) -> str | None:
    qui = session.combat.au_tour_de
    return session.identifiant(qui) if qui else None


def _consigne(session: Session) -> str:
    qui, joueur = session.combat.au_tour_de, session.joueur
    if qui is None:
        return "Plus personne ne peut agir : termine le combat avec fin_combat."
    if qui is joueur:
        return ("C'est au tour du joueur : raconte ce qui vient de se passer, puis demande-lui ce qu'il fait. "
                "Ne joue pas son tour à sa place.")
    consigne = f"C'est au tour de {qui.nom} ({session.identifiant(qui)}) : joue son action, puis appelle fin_de_tour."
    if not joueur.conscient:
        consigne += (" Le joueur est hors de combat : décide ce que font les ennemis (achever, fouiller, fuir) "
                     "et termine le combat avec fin_combat dès que possible.")
    return consigne


def _ligne_combattant(c: Combattant) -> str:
    f = c.fiche
    etat = f.etat.value + (", blessure grave" if f.blessure_grave else "")
    arme = c.arme.nom if c.arme else "sans arme"
    if c.arme and c.arme.munitions:
        arme += f" ({c.munitions_restantes()} balles)"
    return f"{c.nom} : {f.pv}/{f.pv_max} PV, {etat}, {arme}"


def _puce(ligne: str) -> str:
    """Une ligne du compte rendu en puce Markdown ; ses détails (indentés) en sous-puces."""
    return f"  - {ligne.strip()}" if ligne.startswith(" ") else f"- {ligne}"


def _fiche(session: Session, historique: bool = False) -> str:
    """La fiche du combat en Markdown : l'état réel de chacun, puis ce qui s'est passé.
    Pour le MJ, le dernier round seulement ; dans combat.md, tout le combat."""
    c = session.combat
    lignes = [f"# Combat — round {c.round}", "", "Ordre d'initiative, la flèche montre qui joue :", ""]
    lignes += [f"- {'→ ' if x is c.au_tour_de else ''}{_ligne_combattant(x)}" for x in c.ordre]
    for numero, evenements in (session.rounds if historique else session.rounds[-1:]):
        lignes += ["", f"## Round {numero}", ""] + [_puce(e) for e in evenements]
    return "\n".join(lignes) + "\n"


@outil("Terminer le tour de celui qui joue : le moteur passe au suivant dans l'ordre d'initiative. Après le "
       "dernier, il clôt le round (tests des mourants) et te renvoie la fiche du combat : raconte d'après elle.",
       lambda s: _objet({"passe": {"type": "boolean",
                                   "description": "Vrai seulement si le joueur a dit qu'il ne fait rien ce tour."}}))
def fin_de_tour(session: Session, passe: bool = False) -> dict:
    c = session.combat_en_cours()
    joueur = session.joueur
    if c.au_tour_de is joueur and not passe and not any(joueur.budget.utilise.values()):
        raise ErreurOutil("Le joueur n'a encore rien fait ce tour : rends-lui la main (raconte, puis demande-lui "
                          "ce qu'il fait). S'il a dit qu'il ne fait rien, mets passe à vrai.")
    round_avant, evenements = c.round, session.evenements_du_round()
    tests = c.fin_de_tour()
    resultat = {"round": c.round, "nouveau_round": c.round != round_avant,
                "tests_des_mourants": [{"qui": nom, **_resume(t)} for nom, t in tests]}
    if resultat["nouveau_round"]:
        session.rounds.append((round_avant, evenements + decrire("fin_de_tour", {}, resultat, session)[:-1]))
        session.debut_round = len(session.journal) + 1  # + 1 : cet appel-ci
        resultat["fiche"] = _fiche(session)
        if session.campagne:
            session.campagne.ecrire_combat(_fiche(session, historique=True))
    resultat.update(au_tour_de=_qui_joue(session), consigne=_consigne(session))
    return resultat


def _bilan(session: Session) -> list[str]:
    """Le résultat du combat, écrit par le moteur : ce sont des faits, pas du récit."""
    lignes = [_ligne_combattant(session.joueur)]
    for c in session.combat.ordre:
        if c is not session.joueur:
            pv = "" if c.fiche.etat.value == "mort" else f", {c.fiche.pv}/{c.fiche.pv_max} PV"
            lignes.append(f"{c.nom} : {c.fiche.etat.value}{pv}")
    return lignes


@outil("Terminer le combat (victoire, fuite, reddition…). Raconte ses moments forts en trois phrases au plus : "
       "le moteur les garde dans les souvenirs de la campagne, avec le résultat. Les PNJ restent connus.",
       lambda s: _objet({"moments_forts": {"type": "string",
                                           "description": "Les moments forts du combat, trois phrases au plus."}},
                        ["moments_forts"]))
def fin_combat(session: Session, moments_forts: str) -> dict:
    c = session.combat_en_cours()
    texte = _moments_forts(moments_forts, "du combat")
    evenements = session.evenements_du_round()
    if evenements:
        session.rounds.append((c.round, evenements))
    # Les PNJ connus de la mémoire gardent leur état réel : un mort ne revient pas
    for x in c.ordre:
        if x is not session.joueur:
            session.memoire.marquer_etat(session.identifiant(x), MORT if x.fiche.etat.value == MORT else VIVANT)
    adversaires = ", ".join(x.nom for x in c.ordre if x is not session.joueur)
    souvenir = (f"## {str(session.moment).capitalize()} — Combat contre {adversaires} "
                f"({c.round} round{'s' if c.round > 1 else ''})\n\n{texte}\n\n"
                + "\n".join(f"- {ligne}" for ligne in _bilan(session)) + "\n")
    # D'abord le souvenir ; la fiche n'est effacée que s'il est bien écrit
    try:
        session.memoire.ajouter_souvenir(souvenir)
    except OSError as erreur:
        raise ErreurOutil(f"Le souvenir n'a pas pu être écrit ({erreur}) : le combat reste ouvert.") from erreur
    if session.campagne:
        session.campagne.effacer_combat()
    session.combat, session.rounds = None, []
    for combattant in [session.joueur, *session.pnj.values()]:
        combattant.surpris = combattant.vise = combattant.a_vise = combattant.sursis = False
        combattant.budget = BudgetRound()
        combattant.defenses_ce_round = 0
    return {"etats": {i: session.combattant(i).fiche.etat.value for i in session.ids()}, "souvenir": souvenir}


# --- Mémoire de la campagne -------------------------------------------------------------------

def _moments_forts(texte: str, quoi: str) -> str:
    texte = texte.strip()
    if not texte:
        raise ErreurOutil(f"Raconte les moments forts {quoi}, en trois phrases au plus.")
    if len(texte) > MOMENTS_FORTS_MAX:
        raise ErreurOutil(f"Trop long ({len(texte)} caractères) : trois phrases au plus.")
    return texte


@outil("Terminer une scène qui a compté, quand le personnage quitte un lieu ou que le temps passe. "
       "Ses moments forts rejoignent les souvenirs de la campagne. Un combat se termine par fin_combat.",
       lambda s: _objet({
           "titre": {"type": "string", "description": "Quelques mots, par exemple « Chez Doc Mori »."},
           "moments_forts": {"type": "string", "description": "Ce qui s'est passé d'important, trois phrases au plus."},
       }, ["titre", "moments_forts"]))
def fin_scene(session: Session, titre: str, moments_forts: str) -> dict:
    if session.combat:
        raise ErreurOutil("Un combat est en cours : termine-le avec fin_combat.")
    titre = " ".join(titre.split())
    if not titre or len(titre) > LONGUEURS["titre"]:
        raise ErreurOutil(f"Le titre de la scène : quelques mots, {LONGUEURS['titre']} caractères au plus.")
    texte = _moments_forts(moments_forts, "de la scène")
    souvenir = f"## {str(session.moment).capitalize()} — {titre}\n\n{texte}\n"
    try:
        session.memoire.ajouter_souvenir(souvenir)
    except OSError as erreur:
        raise ErreurOutil(f"Le souvenir n'a pas pu être écrit ({erreur}).") from erreur
    return {"souvenir": souvenir}


@outil("Noter un PNJ qui compte (nommé, qui reviendra, qui a un avis sur le personnage), à la rencontre "
       "puis quand son attitude change. Le moteur le garde dans la mémoire de la campagne.",
       lambda s: _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple doc_mori."},
           "nom": {"type": "string"},
           "role": {"type": "string", "description": "Qui il est, en quelques mots."},
           "attitude": {"type": "string", "description": "Ce qu'il pense du personnage, et pourquoi."},
       }, ["identifiant", "nom", "role", "attitude"]))
def noter_pnj(session: Session, identifiant: str, nom: str, role: str, attitude: str) -> dict:
    pnj = session.memoire.noter_pnj(identifiant, nom, role, attitude)
    return {"pnj": identifiant, "nom": pnj.nom, "role": pnj.role, "attitude": pnj.attitude, "etat": pnj.etat}


@outil("Ouvrir un fil de l'histoire : une quête, une promesse, une dette ou une menace à suivre.",
       lambda s: _objet({
           "identifiant": {"type": "string", "description": "Court et unique, par exemple dette_mori."},
           "fil": {"type": "string", "description": "Le fil en une phrase."},
       }, ["identifiant", "fil"]))
def ouvrir_fil(session: Session, identifiant: str, fil: str) -> dict:
    return {"fil": identifiant, "texte": session.memoire.ouvrir_fil(identifiant, fil).texte}


@outil("Clore un fil de l'histoire quand il se règle (réussi, raté, abandonné), avec son issue.",
       lambda s: _objet({
           "identifiant": _enum(sorted(i for i, f in s.memoire.fils.items() if f.ouvert) or ["aucun"]),
           "issue": {"type": "string", "description": "Comment il s'est réglé, en une phrase."},
       }, ["identifiant", "issue"]))
def clore_fil(session: Session, identifiant: str, issue: str) -> dict:
    fil = session.memoire.clore_fil(identifiant, issue)
    return {"fil": identifiant, "texte": fil.texte, "issue": fil.issue}
