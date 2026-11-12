"""Le générateur d'univers (REGLES.md 1.3) : une campagne ne crée rien de zéro.

1. Le joueur choisit le genre, le cadre et les réglages ; ils sont préremplis par genre.
2. Le filtre de la bibliothèque ne garde que ce qui a droit au genre et à la magie.
3. Le générateur pioche dedans, et le LLM adapte les noms au cadre : il propose, le code
   vérifie chaque proposition et garde les noms de la bibliothèque en cas de doute.
4. L'univers est écrit dans le dossier de la campagne : une copie figée, que l'évolution de
   la bibliothèque ne touche plus.
"""

import json
from dataclasses import dataclass, field, replace

from aria import chemins
from aria.bibliotheque import GENRES, Bibliotheque, charger
from aria.campagne import Campagne
from aria.reglages import Curseur
from aria.personnage import NB_COMPETENCES_PARCOURS
from aria.sante_mentale import Choc
from aria.univers import Univers, UniversInvalide, charger_univers, univers_depuis_dict

ACTIVEE, DESACTIVEE, OPTION = "activée", "désactivée", "option"
NOM_MAX = 60
CADRE_MAX = 400
ANNEES = (-3000, 3000)


class ChoixInvalide(ValueError):
    """Les choix du joueur ne respectent pas les règles du genre. `erreurs` les liste tous."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("Choix invalides :\n- " + "\n- ".join(erreurs))


@dataclass(frozen=True)
class Choix:
    """Ce que le joueur choisit pour sa campagne."""

    genre: str
    nom: str
    cadre: str = ""
    magie: bool = False
    curseur: str = Curseur.STANDARD.value
    monde_impitoyable: bool = False
    chocs_banals: tuple[str, ...] = ()
    annee: int | None = None  # l'année du cadre : ce qui apparaît plus tard est retiré (sinon, le LLM la déduit)


def choix_par_defaut(bibliotheque: Bibliotheque, genre: str, nom: str = "", cadre: str = "",
                     annee: int | None = None) -> Choix:
    """Les réglages préremplis du genre (REGLES.md 1.2) : le joueur peut ensuite tout changer,
    sauf la magie là où le genre l'impose."""
    if genre not in bibliotheque.genres:
        raise ChoixInvalide([f"Genre inconnu : « {genre} ». Genres : {', '.join(GENRES)}."])
    fiche = bibliotheque.genres[genre]
    reglages = fiche["reglages"]
    return Choix(genre, nom or genre, cadre, fiche["magie"]["statut"] == ACTIVEE, reglages["curseur"],
                 reglages["monde_impitoyable"], tuple(reglages["chocs_banals"]), annee)


def verifier_choix(bibliotheque: Bibliotheque, choix: Choix) -> list[str]:
    if choix.genre not in bibliotheque.genres:
        return [f"Genre inconnu : « {choix.genre} »."]
    erreurs = []
    if not choix.nom.strip() or len(choix.nom) > NOM_MAX:
        erreurs.append(f"Le nom de l'univers : de 1 à {NOM_MAX} caractères.")
    if len(choix.cadre) > CADRE_MAX:
        erreurs.append(f"Le cadre : {CADRE_MAX} caractères au plus.")
    statut = bibliotheque.genres[choix.genre]["magie"]["statut"]
    if statut == DESACTIVEE and choix.magie:
        erreurs.append(f"Pas de magie en {choix.genre}.")
    if statut == ACTIVEE and not choix.magie:
        erreurs.append(f"La magie fait partie du genre {choix.genre} : elle reste activée.")
    if choix.curseur not in {c.value for c in Curseur}:
        erreurs.append(f"Curseur inconnu « {choix.curseur} ».")
    erreurs += [f"Choc inconnu « {c} »." for c in choix.chocs_banals if c not in Choc.__members__]
    if choix.annee is not None and not ANNEES[0] <= choix.annee <= ANNEES[1]:
        erreurs.append(f"L'année du cadre va de {ANNEES[0]} à {ANNEES[1]}.")
    return erreurs


def generer(bibliotheque: Bibliotheque, choix: Choix) -> dict:
    """Le JSON de l'univers, composé depuis la bibliothèque et vérifié par le moteur.
    Lève ChoixInvalide, ou UniversInvalide si l'univers composé enfreint les règles."""
    erreurs = verifier_choix(bibliotheque, choix)
    if erreurs:
        raise ChoixInvalide(erreurs)
    donnees = bibliotheque.composer(choix.genre, choix.magie, choix.nom.strip(), choix.cadre.strip(), choix.curseur,
                                    choix.monde_impitoyable, list(choix.chocs_banals))
    univers_depuis_dict(donnees)  # le moteur vérifie tout avant qu'on l'écrive
    return donnees


def creer_campagne(campagne: Campagne, choix: Choix, bibliotheque: Bibliotheque | None = None, serveur=None,
                   budget: int | None = None, gardes: set[str] = frozenset()) -> tuple[Univers, "Adaptation | None"]:
    """Génère l'univers et l'écrit dans le dossier de la campagne. Avec un serveur, le LLM adapte les
    noms au cadre. C'est une copie figée : on ne l'écrase jamais (FileExistsError si elle existe)."""
    if campagne.univers.exists():
        raise FileExistsError(f"La campagne a déjà son univers : {campagne.univers}")
    donnees = generer(bibliotheque or charger(), choix)
    adaptation = None
    if serveur is None:  # sans LLM : les noms de la bibliothèque, et les calibres de l'époque choisie
        donnees = appliquer(donnees, Adaptation(choix.nom, choix.cadre, choix.annee,
                                                calibres=calibres_par_epoque(donnees, choix.annee)))
    else:
        adaptation = adapter(serveur, donnees, choix, budget, gardes)
        adapte = appliquer(donnees, adaptation)
        try:
            univers_depuis_dict(adapte)
            donnees = adapte
        except UniversInvalide as erreur:  # ne devrait pas arriver : on garde la bibliothèque, sans rien perdre
            adaptation.refus += [f"univers adapté refusé : {e}" for e in erreur.erreurs]
            adaptation = Adaptation(adaptation.nom, adaptation.cadre, refus=adaptation.refus)
            donnees = dict(donnees, nom=adaptation.nom, cadre=adaptation.cadre)
    campagne.dossier.mkdir(parents=True, exist_ok=True)
    temporaire = campagne.univers.with_suffix(".tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporaire.replace(campagne.univers)
    return charger_univers(campagne.univers), adaptation


def avec(choix: Choix, **changements) -> Choix:
    """Le joueur change un réglage prérempli."""
    return replace(choix, **changements)


# --- Le LLM adapte les noms au cadre ------------------------------------------------------------
#
# Le LLM passe par des outils, comme le MJ : il ne peut proposer qu'un nom pour un objet qui existe
# (liste fermée). Le code valide chaque renommage ; un mauvais est écarté seul, la catégorie a droit à
# une relance avec ses erreurs, puis on garde les noms de la bibliothèque.

CONSIGNE = chemins.PROMPTS / "generateur.md"
CATEGORIES = {"armes": "les armes", "armures": "les armures", "implants": "les implants", "vehicules": "les véhicules"}
ORDRE_RETRAIT = ("vehicules", "armes", "armures")  # les véhicules d'abord : une arme montée suit son véhicule
MINIMUMS = {"armes": 5, "armures": 2, "vehicules": 0}  # ce qu'un univers garde au moins après les retraits
NOM_OBJET_MAX = 40
CADRE_PROPOSE_MAX = 300
DESCRIPTION_MAX = 600
OBJET_MAX = 80
ESSAIS = 2
# Les parcours (REGLES.md 5) : de 15 à 30 par univers, ajoutés par paquets de 5
PARCOURS_MIN, PARCOURS_MAX, PAQUET, PAQUETS_MAX = 15, 30, 5, 4
OPTIONS_PAR_CASE = 3
OBJETS_RACONTES = (3, 4)
RIEN = "rien"


@dataclass
class Adaptation:
    """Ce que le LLM a apporté, étape par étape, et ce que le code a écarté."""

    nom: str
    cadre: str
    annee: int | None = None
    retraits_epoque: dict[str, list[str]] = field(default_factory=dict)  # retirés par le code : apparus plus tard
    calibres: dict[str, str] = field(default_factory=dict)  # arme (nom de la bibliothèque) → son calibre
    retraits: dict[str, list[str]] = field(default_factory=dict)  # catégorie → objets retirés par le LLM
    renommages: dict[str, dict[str, str]] = field(default_factory=dict)  # catégorie → {ancien : nouveau}
    parcours_retires: list[str] = field(default_factory=list)
    parcours_renommes: dict[str, str] = field(default_factory=dict)
    parcours_ajoutes: list[dict] = field(default_factory=list)  # nom, description, competences (socle), equipement
    refus: list[str] = field(default_factory=list)


def _outil(nom: str, description: str, proprietes: dict, requis: list[str]) -> dict:
    return {"type": "function", "function": {"name": nom, "description": description, "parameters": {
        "type": "object", "properties": proprietes, "required": requis, "additionalProperties": False}}}


def _liste(valeurs: list[str], maximum: int | None = None) -> dict:
    schema = {"type": "array", "items": {"type": "string", "enum": valeurs}}
    if maximum is not None:
        schema["maxItems"] = maximum
    return schema


def _paires(noms: list[str]) -> dict:
    return {"type": "array", "items": {
        "type": "object", "properties": {"de": {"type": "string", "enum": noms}, "vers": {"type": "string"}},
        "required": ["de", "vers"], "additionalProperties": False}}


OUTIL_NOMMER = _outil("nommer_univers", "Donner un nom, un cadre et une année à l'univers.", {
    "nom": {"type": "string", "description": f"Le nom de l'univers, {NOM_MAX} caractères au plus."},
    "cadre": {"type": "string", "description": "Le cadre en deux phrases : où, quand, l'ambiance."},
    "annee": {"type": "integer", "description": "L'année où se passe la campagne (négative avant notre ère)."},
}, ["nom", "cadre", "annee"])


def outil_retirer(noms: list[str]) -> dict:
    return _outil("retirer", "Retirer les objets qui n'existent pas dans le cadre ou à son époque (liste vide si "
                             "tous y ont leur place).", {"retirer": _liste(noms)}, ["retirer"])


def outil_renommer(noms: list[str]) -> dict:
    return _outil("renommer", "Renommer les objets qui jurent avec le cadre (liste vide si aucun).",
                  {"renommages": _paires(noms)}, ["renommages"])


def outil_trier_parcours(noms: list[str]) -> dict:
    return _outil("trier_parcours", "Retirer les parcours qui n'ont pas leur place dans le cadre, et renommer ceux "
                                    "dont le nom jure (listes vides si rien ne change).",
                  {"retirer": _liste(noms), "renommer": _paires(noms)}, ["retirer", "renommer"])


def outil_ajouter_parcours(options: dict[str, list[str]], competences: list[str], maximum: int) -> dict:
    equipement = {
        "armes": _liste(options["armes"] + [RIEN], OPTIONS_PAR_CASE),
        "armures": _liste(options["armures"] + [RIEN], OPTIONS_PAR_CASE),
        "objets": {"type": "array", "items": {"type": "string"}, "minItems": OBJETS_RACONTES[0],
                   "maxItems": OBJETS_RACONTES[1], "description": "Des objets racontés, sans bonus chiffré."},
    }
    if options["implants"]:
        equipement["implants"] = _liste(options["implants"], OPTIONS_PAR_CASE)
    if options["vehicules"]:
        equipement["vehicules"] = _liste(options["vehicules"], OPTIONS_PAR_CASE)
    parcours = {"type": "object", "properties": {
        "nom": {"type": "string", "description": f"Le métier, {NOM_OBJET_MAX} caractères au plus."},
        "description": {"type": "string", "description": "Trois phrases : ce qu'il fait, comment le monde le voit, "
                                                         "sa force et sa faiblesse."},
        "competences": dict(_liste(competences), minItems=NB_COMPETENCES_PARCOURS, maxItems=NB_COMPETENCES_PARCOURS),
        "equipement": {"type": "object", "properties": equipement, "required": ["armes", "armures", "objets"],
                       "additionalProperties": False},
    }, "required": ["nom", "description", "competences", "equipement"], "additionalProperties": False}
    return _outil("ajouter_parcours", f"Ajouter de 0 à {maximum} parcours propres au cadre.",
                  {"parcours": {"type": "array", "items": parcours, "maxItems": maximum}}, ["parcours"])


def _consigne(choix: Choix, nom: str, cadre: str) -> dict:
    texte = CONSIGNE.read_text(encoding="utf-8").format(genre=choix.genre, nom=nom, cadre=cadre or "à inventer")
    return {"role": "system", "content": texte}


def _appel_outil(serveur, messages: list[dict], outil: dict, budget: int | None) -> dict | None:
    """Les arguments du premier appel à cet outil, ou None si le modèle ne l'a pas appelé."""
    reponse = serveur.discuter(messages, [outil], budget)
    message = reponse["choices"][0]["message"]
    for appel in message.get("tool_calls") or []:
        if appel["function"]["name"] == outil["function"]["name"]:
            arguments = appel["function"]["arguments"]
            try:
                return json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
            except (ValueError, TypeError):
                return None
    return None


def _demander(serveur, consigne: dict, demande: str, outil: dict, valider, budget: int | None):
    """Un appel d'outil validé par le code, avec une relance qui liste les erreurs.
    `valider(arguments)` renvoie (résultat, erreurs). Renvoie le dernier résultat et ses erreurs."""
    messages = [consigne, {"role": "user", "content": demande}]
    nom = outil["function"]["name"]
    for essai in range(ESSAIS):
        arguments = _appel_outil(serveur, messages, outil, budget)
        resultat, erreurs = valider(arguments) if arguments is not None else (None, [f"Tu n'as pas appelé l'outil {nom}."])
        if not erreurs or essai == ESSAIS - 1:
            return resultat, erreurs
        messages = [consigne, {"role": "user", "content": demande}, {"role": "user", "content": (
            "Ta proposition a des erreurs ; recommence en les corrigeant :\n" + "\n".join(f"- {e}" for e in erreurs))}]
    return None, []


def _nom_et_cadre(arguments: dict | None) -> tuple[str, str, int | None]:
    if not arguments:
        return "", "", None
    nom = " ".join(str(arguments.get("nom", "")).split())
    cadre = " ".join(str(arguments.get("cadre", "")).split())
    annee = arguments.get("annee")
    annee = annee if isinstance(annee, int) and not isinstance(annee, bool) and ANNEES[0] <= annee <= ANNEES[1] else None
    return (nom if 0 < len(nom) <= NOM_MAX else "", cadre if 0 < len(cadre) <= CADRE_PROPOSE_MAX else "", annee)


def proposer_cadre(serveur, choix: Choix, budget: int | None = None, deja_vus: list[str] = ()) -> Choix:
    """« Surprends-moi » : le LLM propose un nom et un cadre ; le joueur garde ou relance.
    `deja_vus` : les cadres déjà refusés, pour qu'il en propose un autre."""
    demande = f"Invente un cadre original pour une campagne de {choix.genre}."
    if deja_vus:
        demande += " Pas ceux-ci, déjà refusés : " + " | ".join(deja_vus)
    for _ in range(ESSAIS):
        arguments = _appel_outil(serveur, [_consigne(choix, choix.nom, ""), {"role": "user", "content": demande}],
                                 OUTIL_NOMMER, budget)
        nom, cadre, annee = _nom_et_cadre(arguments)
        if nom and cadre:
            return replace(choix, nom=nom, cadre=cadre, annee=annee)
    raise ChoixInvalide(["Le MJ n'a pas su proposer de cadre : écris-en un toi-même."])


def noms_de(donnees: dict, categorie: str) -> list[str]:
    if categorie == "implants":
        return [i["nom"] for i in donnees.get("implants", {}).get("implants", [])]
    return [x["nom"] for x in donnees.get(categorie, [])]


def tous_les_noms(donnees: dict) -> set[str]:
    return {n for c in CATEGORIES for n in noms_de(donnees, c)}


# --- Les validations : le code décide de ce que le LLM propose ----------------------------------

def valider_renommages(proposes, noms: list[str], pris: set[str]) -> tuple[dict[str, str], list[str]]:
    """Garde les renommages valides d'une liste de noms, et dit pourquoi chaque autre est refusé.
    `pris` : les noms déjà utilisés, plus les nouveaux noms déjà acceptés ailleurs."""
    if not isinstance(proposes, list):
        return {}, ["« renommages » doit être une liste."]
    acceptes, refus, nouveaux = {}, [], set()
    for r in proposes:
        if not isinstance(r, dict):
            refus.append(f"Renommage illisible : {r!r}.")
            continue
        ancien, nouveau = r.get("de"), " ".join(str(r.get("vers", "")).split())
        if ancien not in noms:
            refus.append(f"« {ancien} » n'existe pas dans cette liste.")
        elif ancien in acceptes:
            refus.append(f"« {ancien} » est renommé deux fois.")
        elif not 0 < len(nouveau) <= NOM_OBJET_MAX:
            refus.append(f"« {ancien} » : un nom de 1 à {NOM_OBJET_MAX} caractères.")
        elif nouveau == ancien:
            continue  # rien ne change
        elif nouveau in pris or nouveau in nouveaux:
            refus.append(f"« {ancien} » → « {nouveau} » : ce nom est déjà pris.")
        else:
            acceptes[ancien] = nouveau
            nouveaux.add(nouveau)
    return acceptes, refus


def _armes_portees(donnees: dict) -> set[str]:
    """Les armes que portent les véhicules (montées) et les drones (intégrées)."""
    portees = set()
    for v in donnees.get("vehicules", []):
        portees |= {m["arme"] for m in v.get("armes_montees", [])}
        if v.get("arme_integree"):
            portees.add(v["arme_integree"])
    return portees


def valider_retraits(proposes, categorie: str, donnees: dict) -> tuple[list[str], list[str]]:
    """Les objets qu'on peut retirer de cette catégorie : ils existent, ne sont pas portés par un véhicule
    gardé, et il en reste au moins le minimum."""
    if not isinstance(proposes, list):
        return [], ["« retirer » doit être une liste."]
    noms, acceptes, refus = noms_de(donnees, categorie), [], []
    portees = _armes_portees(donnees) if categorie == "armes" else set()
    for nom in dict.fromkeys(proposes):
        if nom not in noms:
            refus.append(f"« {nom} » n'existe pas dans cette catégorie.")
        elif nom in portees:
            refus.append(f"« {nom} » est porté par un véhicule ou un drone de l'univers : on le garde.")
        else:
            acceptes.append(nom)
    minimum = MINIMUMS.get(categorie, 0)
    if acceptes and len(noms) - len(acceptes) < minimum:  # l'époque a pu passer sous le minimum : ne rien retirer reste permis
        return [], refus + [f"Il faut garder au moins {minimum} objets dans {CATEGORIES[categorie]} "
                            f"({len(noms)} aujourd'hui) : retire-en moins."]
    return acceptes, refus


def valider_tri(proposes, donnees: dict, gardes: set[str]) -> tuple[tuple[list[str], dict[str, str]], list[str]]:
    """Les parcours retirés (pas un parcours gardé, pas plus que ce que les ajouts peuvent combler) et renommés."""
    if not isinstance(proposes, dict):
        return ([], {}), ["Réponse illisible."]
    noms = list(donnees["parcours"])
    retires, refus = [], []
    a_retirer = proposes.get("retirer", [])
    for nom in dict.fromkeys(a_retirer if isinstance(a_retirer, list) else []):
        if nom not in noms:
            refus.append(f"Parcours inconnu : « {nom} ».")
        elif nom in gardes:
            refus.append(f"« {nom} » doit rester : un personnage en a besoin.")
        else:
            retires.append(nom)
    plancher = PARCOURS_MIN - PAQUET
    if len(noms) - len(retires) < plancher:
        refus.append(f"Il faut garder au moins {plancher} parcours : retire-en moins.")
        retires = []
    restants = [n for n in noms if n not in retires]
    renommes, erreurs = valider_renommages(proposes.get("renommer", []), restants, set(noms))
    return (retires, renommes), refus + erreurs


def _competences(univers: Univers) -> dict[str, str]:
    """Nom affiché dans l'univers → nom du socle (ou de la compétence thématique)."""
    return {univers.nom_affiche(nom): nom for nom in univers.competences_disponibles()}


def options_de_depart(univers: Univers) -> dict[str, list[str]]:
    """Ce qu'un parcours peut proposer au départ (REGLES.md 5) : tout d'origine et générique, une protection
    de 3 au plus, un implant standard, un véhicule léger ou moyen."""
    from aria.equipement import Qualite
    origine = lambda o: o.qualite is Qualite.ORIGINE and not o.fabricant  # noqa: E731
    return {
        "armes": [a.nom for a in univers.armes if origine(a) and not a.montee],
        "armures": [a.nom for a in univers.armures if origine(a) and a.protection_totale <= 3],
        "implants": [i.nom for i in univers.implants if i.gamme in (None, "standard")],
        "vehicules": [v.nom for v in univers.vehicules if origine(v) and v.gabarit in ("léger", "moyen")],
    }


def valider_parcours(propose, donnees: dict, pris: set[str]) -> tuple[dict | None, list[str]]:
    """Un parcours ajouté : son nom, sa description, ses 8 compétences et ses listes de départ ; le moteur
    vérifie ensuite l'univers avec lui. Renvoie le parcours prêt à ajouter (compétences du socle)."""
    if not isinstance(propose, dict):
        return None, [f"Parcours illisible : {propose!r}."]
    nom = " ".join(str(propose.get("nom", "")).split())
    if not 0 < len(nom) <= NOM_OBJET_MAX:
        return None, [f"Un nom de parcours de 1 à {NOM_OBJET_MAX} caractères (« {nom} »)."]
    if nom in pris:
        return None, [f"« {nom} » : ce parcours existe déjà."]
    erreurs = []
    description = " ".join(str(propose.get("description", "")).split())
    if not 0 < len(description) <= DESCRIPTION_MAX:
        erreurs.append(f"{nom} : une description de 1 à {DESCRIPTION_MAX} caractères.")
    univers = univers_depuis_dict(donnees)
    correspondance = _competences(univers)
    affichees = propose.get("competences", [])
    competences = [correspondance.get(c) for c in affichees] if isinstance(affichees, list) else []
    if len(competences) != NB_COMPETENCES_PARCOURS or None in competences or len(set(competences)) != len(competences):
        erreurs.append(f"{nom} : {NB_COMPETENCES_PARCOURS} compétences distinctes de l'univers.")
    equipement = propose.get("equipement") if isinstance(propose.get("equipement"), dict) else {}
    options = options_de_depart(univers)
    listes = {}
    for case in ("armes", "armures", "implants", "vehicules"):
        choisies = equipement.get(case, [])
        if not isinstance(choisies, list):
            choisies = []
        if case in ("armes", "armures") and not 1 <= len(choisies) <= OPTIONS_PAR_CASE:
            erreurs.append(f"{nom} : de 1 à {OPTIONS_PAR_CASE} options pour « {case} » (« {RIEN} » compris).")
        elif len(choisies) > OPTIONS_PAR_CASE:
            erreurs.append(f"{nom} : {OPTIONS_PAR_CASE} options au plus pour « {case} ».")
        for option in choisies:
            if option != RIEN and option not in options[case]:
                erreurs.append(f"{nom} : « {option} » n'est pas une option de départ pour « {case} ».")
        if choisies:
            listes[case] = [None if o == RIEN else o for o in dict.fromkeys(choisies)]
    objets = [" ".join(str(o).split()) for o in equipement.get("objets", []) if str(o).strip()]
    if not OBJETS_RACONTES[0] <= len(set(objets)) <= OBJETS_RACONTES[1] or any(len(o) > OBJET_MAX for o in objets):
        erreurs.append(f"{nom} : de {OBJETS_RACONTES[0]} à {OBJETS_RACONTES[1]} objets racontés différents, "
                       f"{OBJET_MAX} caractères au plus chacun.")
    if erreurs:
        return None, erreurs
    parcours = {"nom": nom, "description": description, "competences": competences,
                "equipement": dict(listes, objets=list(dict.fromkeys(objets)))}
    try:  # le moteur vérifie l'univers avec ce parcours : rien d'autre n'a changé, ses erreurs sont les siennes
        univers_depuis_dict(_avec_parcours(donnees, parcours))
    except UniversInvalide as erreur:
        return None, [f"{nom} : {e}" for e in erreur.erreurs]
    return parcours, []


# --- Les étapes, appliquées sur une copie de l'univers ------------------------------------------

def _origine(d: dict, ancien: str, nouveau: str):
    origines = d.setdefault("origines", {})
    origines[nouveau] = origines.pop(ancien, ancien)


def _retirer_objets(d: dict, categorie: str, noms: list[str]):
    retires = set(noms)
    d[categorie] = [x for x in d.get(categorie, []) if x["nom"] not in retires]
    for listes in d.get("equipements", {}).values():
        if categorie in listes:
            listes[categorie] = [o for o in listes[categorie] if o not in retires]


def _renommer_objets(d: dict, tout: dict[str, str]):
    if not tout:
        return

    def renomme(nom):
        return tout.get(nom, nom)

    for categorie in ("armes", "armures", "vehicules"):
        for x in d.get(categorie, []):
            x["nom"] = renomme(x["nom"])
    for v in d.get("vehicules", []):
        for monte in v.get("armes_montees", []):
            monte["arme"] = renomme(monte["arme"])
        if v.get("arme_integree"):
            v["arme_integree"] = renomme(v["arme_integree"])
        if v.get("drones"):
            v["drones"]["modele"] = renomme(v["drones"]["modele"])
    implants = d.get("implants", {})
    for i in implants.get("implants", []):
        i["nom"] = renomme(i["nom"])
    for s in implants.get("systemes", []):
        for cle in ("fondation", "requiert"):
            if s.get(cle):
                s[cle] = renomme(s[cle])
    for listes in d.get("equipements", {}).values():
        for case in ("armes", "armures", "implants", "vehicules"):
            if case in listes:
                listes[case] = [renomme(o) if o else o for o in listes[case]]
    for ancien, nouveau in tout.items():
        _origine(d, ancien, nouveau)


def _retirer_parcours(d: dict, noms: list[str]):
    for nom in noms:
        for cle in ("parcours", "descriptions", "equipements"):
            d.get(cle, {}).pop(nom, None)


def _renommer_parcours(d: dict, renommes: dict[str, str]):
    for cle in ("parcours", "descriptions", "equipements"):
        if cle in d:
            d[cle] = {renommes.get(nom, nom): valeur for nom, valeur in d[cle].items()}
    for ancien, nouveau in renommes.items():
        _origine(d, ancien, nouveau)


def _avec_parcours(d: dict, p: dict) -> dict:
    copie = json.loads(json.dumps(d))
    _ajouter_parcours(copie, p)
    return copie


def _ajouter_parcours(d: dict, p: dict):
    d["parcours"][p["nom"]] = list(p["competences"])
    d.setdefault("descriptions", {})[p["nom"]] = p["description"]
    d.setdefault("equipements", {})[p["nom"]] = dict(p["equipement"])


def calibres_par_epoque(donnees: dict, annee: int | None) -> dict[str, str]:
    """Pour chaque arme à feu, le calibre le plus récent qui existe à l'année du cadre (le plus récent de
    tous, sans année). Une arme n'existe jamais avant son premier calibre : elle en a toujours un."""
    choisis = {}
    for arme in donnees.get("armes", []):
        possibles = [c for c in arme.get("calibres", []) if annee is None or c["apparition"] <= annee]
        if possibles:
            choisis[arme["nom"]] = possibles[-1]["nom"]
    return choisis


def retraits_par_epoque(donnees: dict, annee: int) -> dict[str, list[str]]:
    """Ce que le code retire tout seul : les objets apparus après l'année du cadre. La bibliothèque garantit
    qu'un véhicule n'est jamais plus ancien que ses armes : une arme retirée n'est jamais montée sur un
    véhicule gardé."""
    retraits = {}
    for categorie in ORDRE_RETRAIT:
        trop_recents = [x["nom"] for x in donnees.get(categorie, []) if x.get("apparition", ANNEES[0]) > annee]
        if trop_recents:
            retraits[categorie] = trop_recents
    return retraits


def appliquer(donnees: dict, adaptation: Adaptation) -> dict:
    """Rejoue l'adaptation sur une copie : retraits, renommages, tri et ajout des parcours. Garde la trace
    des noms de la bibliothèque. Ne change aucune règle."""
    d = json.loads(json.dumps(donnees))  # une copie profonde
    d["nom"], d["cadre"] = adaptation.nom, adaptation.cadre
    for arme in d.get("armes", []):  # le calibre de l'époque, avant les renommages
        liste = arme.pop("calibres", None)
        if liste is not None and arme["nom"] in adaptation.calibres:
            arme["calibre"] = adaptation.calibres[arme["nom"]]
    for retraits in (adaptation.retraits_epoque, adaptation.retraits):
        for categorie in ORDRE_RETRAIT:
            _retirer_objets(d, categorie, retraits.get(categorie, []))
    _renommer_objets(d, {a: n for r in adaptation.renommages.values() for a, n in r.items()})
    _retirer_parcours(d, adaptation.parcours_retires)
    _renommer_parcours(d, adaptation.parcours_renommes)
    for p in adaptation.parcours_ajoutes:
        _ajouter_parcours(d, p)
    return d


# --- L'adaptation, étape par étape ----------------------------------------------------------------

def adapter(serveur, donnees: dict, choix: Choix, budget: int | None = None, gardes: set[str] = frozenset()) -> Adaptation:
    """Le LLM complète le nom et le cadre s'ils manquent, retire les objets anachroniques, renomme ce qui
    jure, trie les parcours puis en ajoute par paquets. `gardes` : les parcours qui doivent rester."""
    nom, cadre, annee = choix.nom, choix.cadre, choix.annee
    if nom == choix.genre or not cadre or annee is None:
        demande = f"Donne un nom à cet univers de {choix.genre}"
        demande += f", dont le cadre est : {cadre}." if cadre else ", et un cadre original."
        demande += " Donne aussi l'année où se passe la campagne."
        nouveau_nom, nouveau_cadre, nouvelle_annee = _nom_et_cadre(
            _appel_outil(serveur, [_consigne(choix, nom, cadre), {"role": "user", "content": demande}],
                         OUTIL_NOMMER, budget))
        nom = nouveau_nom if nom == choix.genre and nouveau_nom else nom
        cadre = cadre or nouveau_cadre
        annee = annee if annee is not None else nouvelle_annee
    a = Adaptation(nom, cadre, annee, calibres=calibres_par_epoque(donnees, annee))
    if annee is None:
        a.refus.append("pas d'année pour le cadre : aucun objet n'est retiré par époque")
    else:
        a.retraits_epoque = retraits_par_epoque(donnees, annee)
    consigne = _consigne(choix, nom, cadre)
    d = appliquer(donnees, a)

    # 1. Ce qui n'existe pas dans le cadre ou à son époque
    for categorie in ORDRE_RETRAIT:
        noms = noms_de(d, categorie)
        if not noms:
            continue
        retires, erreurs = _demander(
            serveur, consigne, f"Voici {CATEGORIES[categorie]} de l'univers. Appelle retirer avec ceux qui "
            "n'existent pas dans le cadre ou à son époque (une liste vide si tous y ont leur place) :\n"
            + "\n".join(f"- {n}" for n in noms), outil_retirer(noms),
            lambda arguments, c=categorie: valider_retraits(arguments.get("retirer"), c, d), budget)
        a.refus += [f"retrait, {CATEGORIES[categorie]} : {e}" for e in erreurs]
        if retires:
            a.retraits[categorie] = retires
            _retirer_objets(d, categorie, retires)

    # 2. Ce qui reste et jure avec le cadre ; une arme se renomme d'après son calibre
    pris = set(tous_les_noms(d))
    calibres = {arme["nom"]: arme["calibre"] for arme in d.get("armes", []) if arme.get("calibre")}
    for categorie, libelle in CATEGORIES.items():
        noms = noms_de(d, categorie)
        if not noms:
            continue
        acceptes, erreurs = _demander(
            serveur, consigne, f"Voici {libelle} de l'univers. Appelle renommer avec ceux dont le nom jure avec le "
            "cadre (une liste vide si aucun). Un calibre entre parenthèses est celui de l'arme : son nouveau nom "
            "doit lui correspondre.\n" + "\n".join(f"- {n}" + (f" ({calibres[n]})" if n in calibres else "")
                                                     for n in noms), outil_renommer(noms),
            lambda arguments, n=noms: valider_renommages(arguments.get("renommages"), n, pris), budget)
        a.refus += [f"renommage, {libelle} : {e}" for e in erreurs]
        if acceptes:
            a.renommages[categorie] = acceptes
            pris |= set(acceptes.values())
    _renommer_objets(d, {x: y for r in a.renommages.values() for x, y in r.items()})

    # 3. Les parcours : ceux qui n'ont pas leur place, ceux dont le nom jure
    noms = list(d["parcours"])
    resultat, erreurs = _demander(
        serveur, consigne, "Voici les parcours (les métiers) de l'univers. Appelle trier_parcours : retire ceux qui "
        "n'ont pas leur place dans le cadre, renomme ceux dont le nom jure (listes vides si rien ne change) :\n"
        + "\n".join(f"- {n}" for n in noms) + (f"\nCeux-ci doivent rester : {', '.join(sorted(gardes))}." if gardes else ""),
        outil_trier_parcours(noms), lambda arguments: valider_tri(arguments, d, set(gardes)), budget)
    a.refus += [f"parcours : {e}" for e in erreurs]
    if resultat:
        a.parcours_retires, a.parcours_renommes = resultat
        _retirer_parcours(d, a.parcours_retires)
        _renommer_parcours(d, a.parcours_renommes)

    # 4. Des parcours propres au cadre, par paquets : toujours un paquet, d'autres tant qu'il en manque
    for paquet in range(PAQUETS_MAX):
        manque = PARCOURS_MIN - len(d["parcours"])
        place = min(PAQUET, PARCOURS_MAX - len(d["parcours"]))
        if place <= 0 or (paquet > 0 and manque <= 0):
            break
        univers = univers_depuis_dict(d)
        outil = outil_ajouter_parcours(options_de_depart(univers), sorted(_competences(univers)), place)
        combien = f"de {min(manque, place)} à {place}" if manque > 0 else f"de 0 à {place}"
        ajoutes, erreurs = _demander(
            serveur, consigne, f"L'univers a déjà ces parcours : {', '.join(d['parcours'])}. Appelle ajouter_parcours "
            f"avec {combien} parcours propres au cadre, différents de ceux-là : des métiers que le joueur, ses "
            "compagnons ou des PNJ pourraient exercer.", outil,
            lambda arguments: _valider_paquet(arguments.get("parcours"), d, place), budget)
        a.refus += [f"ajout de parcours : {e}" for e in erreurs]
        for p in ajoutes or []:
            _ajouter_parcours(d, p)
            a.parcours_ajoutes.append(p)
        if not ajoutes and manque <= 0:
            break
    return a


def _valider_paquet(proposes, d: dict, place: int) -> tuple[list[dict], list[str]]:
    """Les parcours valides d'un paquet ; un parcours fautif est écarté sans emporter les autres."""
    if not isinstance(proposes, list):
        return [], ["« parcours » doit être une liste."]
    valides, erreurs, pris = [], [], set(d["parcours"])
    essai = json.loads(json.dumps(d))
    for propose in proposes[:place]:
        parcours, refus = valider_parcours(propose, essai, pris)
        if parcours:
            valides.append(parcours)
            pris.add(parcours["nom"])
            _ajouter_parcours(essai, parcours)
        erreurs += refus
    return valides, erreurs
