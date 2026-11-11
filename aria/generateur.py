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
from aria.sante_mentale import Choc
from aria.univers import Univers, UniversInvalide, charger_univers, univers_depuis_dict

ACTIVEE, DESACTIVEE, OPTION = "activée", "désactivée", "option"
NOM_MAX = 60
CADRE_MAX = 400


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


def choix_par_defaut(bibliotheque: Bibliotheque, genre: str, nom: str = "", cadre: str = "") -> Choix:
    """Les réglages préremplis du genre (REGLES.md 1.2) : le joueur peut ensuite tout changer,
    sauf la magie là où le genre l'impose."""
    if genre not in bibliotheque.genres:
        raise ChoixInvalide([f"Genre inconnu : « {genre} ». Genres : {', '.join(GENRES)}."])
    fiche = bibliotheque.genres[genre]
    reglages = fiche["reglages"]
    return Choix(genre, nom or genre, cadre, fiche["magie"]["statut"] == ACTIVEE, reglages["curseur"],
                 reglages["monde_impitoyable"], tuple(reglages["chocs_banals"]))


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
                   budget: int | None = None) -> tuple[Univers, "Adaptation | None"]:
    """Génère l'univers et l'écrit dans le dossier de la campagne. Avec un serveur, le LLM adapte les
    noms au cadre. C'est une copie figée : on ne l'écrase jamais (FileExistsError si elle existe)."""
    if campagne.univers.exists():
        raise FileExistsError(f"La campagne a déjà son univers : {campagne.univers}")
    donnees = generer(bibliotheque or charger(), choix)
    adaptation = None
    if serveur is not None:
        adaptation = adapter(serveur, donnees, choix, budget)
        adapte = appliquer(donnees, adaptation)
        try:
            univers_depuis_dict(adapte)
            donnees = adapte
        except UniversInvalide as erreur:  # ne devrait pas arriver : on garde la bibliothèque, sans rien perdre
            adaptation.refus += [f"univers adapté refusé : {e}" for e in erreur.erreurs]
            adaptation.renommages = {}
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
NOM_OBJET_MAX = 40
CADRE_PROPOSE_MAX = 300
ESSAIS = 2


@dataclass
class Adaptation:
    """Ce que le LLM a apporté : le nom, le cadre, et les renommages acceptés ou refusés."""

    nom: str
    cadre: str
    renommages: dict[str, dict[str, str]] = field(default_factory=dict)  # catégorie → {ancien : nouveau}
    refus: list[str] = field(default_factory=list)


def _outil(nom: str, description: str, proprietes: dict, requis: list[str]) -> dict:
    return {"type": "function", "function": {"name": nom, "description": description, "parameters": {
        "type": "object", "properties": proprietes, "required": requis, "additionalProperties": False}}}


OUTIL_NOMMER = _outil("nommer_univers", "Donner un nom et un cadre à l'univers.", {
    "nom": {"type": "string", "description": f"Le nom de l'univers, {NOM_MAX} caractères au plus."},
    "cadre": {"type": "string", "description": "Le cadre en deux phrases : où, quand, l'ambiance."},
}, ["nom", "cadre"])


def outil_renommer(noms: list[str]) -> dict:
    return _outil("renommer", "Renommer les objets qui jurent avec le cadre (liste vide si aucun).", {
        "renommages": {"type": "array", "items": {
            "type": "object", "properties": {"de": {"type": "string", "enum": noms}, "vers": {"type": "string"}},
            "required": ["de", "vers"], "additionalProperties": False}},
    }, ["renommages"])


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


def _nom_et_cadre(arguments: dict | None) -> tuple[str, str]:
    if not arguments:
        return "", ""
    nom = " ".join(str(arguments.get("nom", "")).split())
    cadre = " ".join(str(arguments.get("cadre", "")).split())
    return (nom if 0 < len(nom) <= NOM_MAX else "", cadre if 0 < len(cadre) <= CADRE_PROPOSE_MAX else "")


def proposer_cadre(serveur, choix: Choix, budget: int | None = None, deja_vus: list[str] = ()) -> Choix:
    """« Surprends-moi » : le LLM propose un nom et un cadre ; le joueur garde ou relance.
    `deja_vus` : les cadres déjà refusés, pour qu'il en propose un autre."""
    demande = f"Invente un cadre original pour une campagne de {choix.genre}."
    if deja_vus:
        demande += " Pas ceux-ci, déjà refusés : " + " | ".join(deja_vus)
    for _ in range(ESSAIS):
        arguments = _appel_outil(serveur, [_consigne(choix, choix.nom, ""), {"role": "user", "content": demande}],
                                 OUTIL_NOMMER, budget)
        nom, cadre = _nom_et_cadre(arguments)
        if nom and cadre:
            return replace(choix, nom=nom, cadre=cadre)
    raise ChoixInvalide(["Le MJ n'a pas su proposer de cadre : écris-en un toi-même."])


def noms_de(donnees: dict, categorie: str) -> list[str]:
    if categorie == "implants":
        return [i["nom"] for i in donnees.get("implants", {}).get("implants", [])]
    return [x["nom"] for x in donnees.get(categorie, [])]


def tous_les_noms(donnees: dict) -> set[str]:
    return {n for c in CATEGORIES for n in noms_de(donnees, c)}


def valider_renommages(proposes, noms: list[str], pris: set[str]) -> tuple[dict[str, str], list[str]]:
    """Garde les renommages valides d'une catégorie, et dit pourquoi chaque autre est refusé.
    `pris` : tous les noms de l'univers, plus les nouveaux noms déjà acceptés ailleurs."""
    if not isinstance(proposes, list):
        return {}, ["« renommages » doit être une liste."]
    acceptes, refus, nouveaux = {}, [], set()
    for r in proposes:
        if not isinstance(r, dict):
            refus.append(f"Renommage illisible : {r!r}.")
            continue
        ancien, nouveau = r.get("de"), " ".join(str(r.get("vers", "")).split())
        if ancien not in noms:
            refus.append(f"« {ancien} » n'existe pas dans cette catégorie.")
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


def adapter(serveur, donnees: dict, choix: Choix, budget: int | None = None) -> Adaptation:
    """Le LLM complète le nom et le cadre s'ils manquent, puis renomme catégorie par catégorie."""
    nom, cadre = choix.nom, choix.cadre
    if nom == choix.genre or not cadre:
        demande = f"Donne un nom à cet univers de {choix.genre}"
        demande += f", dont le cadre est : {cadre}." if cadre else ", et un cadre original."
        nouveau_nom, nouveau_cadre = _nom_et_cadre(
            _appel_outil(serveur, [_consigne(choix, nom, cadre), {"role": "user", "content": demande}],
                         OUTIL_NOMMER, budget))
        nom = nouveau_nom if nom == choix.genre and nouveau_nom else nom
        cadre = cadre or nouveau_cadre
    adaptation = Adaptation(nom, cadre)
    pris = set(tous_les_noms(donnees))
    for categorie, libelle in CATEGORIES.items():
        noms = noms_de(donnees, categorie)
        if not noms:
            continue
        demande = {"role": "user", "content": (
            f"Voici {libelle} de l'univers. Appelle renommer avec ceux qui jurent avec le cadre "
            "(une liste vide si aucun) :\n" + "\n".join(f"- {n}" for n in noms))}
        messages = [_consigne(choix, nom, cadre), demande]
        for essai in range(ESSAIS):
            arguments = _appel_outil(serveur, messages, outil_renommer(noms), budget)
            if arguments is None:
                acceptes, erreurs = {}, ["Tu n'as pas appelé l'outil renommer."]
            else:
                acceptes, erreurs = valider_renommages(arguments.get("renommages"), noms, pris)
            if not erreurs or essai == ESSAIS - 1:
                break
            messages = [messages[0], demande, {"role": "user", "content": (
                "Ta proposition a des erreurs ; recommence toute la liste en les corrigeant :\n"
                + "\n".join(f"- {e}" for e in erreurs))}]
        adaptation.refus += [f"{libelle} : {e}" for e in erreurs]
        if acceptes:
            adaptation.renommages[categorie] = acceptes
            pris |= set(acceptes.values())
    return adaptation


def appliquer(donnees: dict, adaptation: Adaptation) -> dict:
    """Renomme partout à la fois (armurerie, armes montées, drones, listes de départ, implants et leurs
    systèmes) et garde la trace des noms de la bibliothèque. Ne change aucune règle."""
    d = json.loads(json.dumps(donnees))  # une copie profonde
    d["nom"], d["cadre"] = adaptation.nom, adaptation.cadre
    tout = {ancien: nouveau for r in adaptation.renommages.values() for ancien, nouveau in r.items()}
    if not tout:
        return d

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
    origines = dict(d.get("origines", {}))
    for ancien, nouveau in tout.items():
        origines[nouveau] = origines.pop(ancien, ancien)
    d["origines"] = origines
    return d
