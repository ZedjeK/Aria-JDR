"""L'amorce d'une campagne : ce qui existe avant la première scène.

Juste après la création du personnage, le LLM écrit son passé, le lieu de départ, la situation
d'ouverture, les PNJ qu'il connaît déjà (dont celui de son lien) et les fils ouverts (dont un tiré de sa
motivation). Le code vérifie, puis range le tout dans la mémoire de la campagne : le MJ commence la
première scène en sachant d'où vient le personnage.

L'amorce part d'un plan, en une phrase : l'idée du joueur, ou, quand il n'est pas inspiré, un plan tiré
dans la bibliothèque (bibliotheque/amorces.json : les plans de tous les genres, ceux du genre de l'univers)
et corsé par une complication tirée à part.
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from aria import chemins
from aria.memoire import LONGUEURS, Memoire, MemoireRefusee, verifier_identifiant
from aria.personnage import Personnage
from aria.temps import Moment
from aria.univers import Univers

PLANS = chemins.RESSOURCES / "bibliotheque" / "amorces.json"
PLAN_MAX = 300  # caractères de l'idée du joueur
TEXTES = {"passe": 500, "lieu": 400, "situation": 400, "secret": 160}
FIL_SECRET = "secret_de_depart"  # le secret est un fil, que le MJ clôt quand le personnage le découvre
NB_PNJ, NB_FILS = (2, 4), (1, 3)
ESSAIS = 2
TITRE = "Avant la campagne"


def _charger() -> dict:
    """bibliotheque/amorces.json, vérifié : les plans de tous les genres, ceux de chaque genre, les complications.
    Lève ValueError s'il est mal formé."""
    donnees = json.loads(PLANS.read_text(encoding="utf-8"))
    par_genre = donnees.get("plans_par_genre", {})
    tous = [*donnees["plans"], *(p for plans in par_genre.values() for p in plans), *donnees["complications"]]
    erreurs = [f"texte vide ou trop long : « {p} »" for p in tous if not isinstance(p, str) or not 0 < len(p) <= PLAN_MAX]
    if len(set(tous)) != len(tous):
        erreurs.append("des textes sont en double")
    if erreurs:
        raise ValueError("bibliotheque/amorces.json : " + " ; ".join(erreurs))
    return donnees


def charger_plans(genre: str = "") -> list[str]:
    """Les plans d'amorce pour un univers de ce genre : ceux de tous les genres, puis les siens."""
    donnees = _charger()
    return [*donnees["plans"], *donnees.get("plans_par_genre", {}).get(genre, [])]


def charger_complications() -> list[str]:
    return list(_charger()["complications"])


def tirer_plan(genre: str = "", hasard: random.Random | None = None, vus: Path | None = None) -> str:
    """Un plan de la bibliothèque. `vus` : le fichier des plans déjà piochés, toutes campagnes confondues ;
    tant qu'il reste des plans neufs, aucun ne revient. Quand tout a été vu, on repart de zéro."""
    plans = charger_plans(genre)
    deja = _lire_vus(vus)
    restants = [p for p in plans if p not in deja]
    if not restants:
        deja, restants = [p for p in deja if p not in plans], plans
    plan = (hasard or random.Random()).choice(restants)
    if vus is not None:
        try:
            vus.parent.mkdir(parents=True, exist_ok=True)
            vus.write_text(json.dumps([*deja, plan], ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass  # au pire, un plan reviendra plus tôt
    return plan


def _lire_vus(vus: Path | None) -> list[str]:
    try:
        lus = json.loads(vus.read_text(encoding="utf-8")) if vus is not None and vus.is_file() else []
    except (OSError, ValueError):
        return []
    return [p for p in lus if isinstance(p, str)] if isinstance(lus, list) else []


def tirer_complication(hasard: random.Random | None = None) -> str:
    """Ce qui corse le plan : tirée à part, elle multiplie les débuts possibles."""
    return (hasard or random.Random()).choice(charger_complications())


@dataclass
class Amorce:
    plan: str
    passe: str
    lieu: str
    situation: str
    secret: str  # ce que le personnage ignore : pour le MJ seulement, jamais montré au joueur
    pnj: list[dict] = field(default_factory=list)  # identifiant, nom, role, attitude
    fils: list[dict] = field(default_factory=list)  # identifiant, texte

    @property
    def scene(self) -> str:
        """Ce que le MJ sait de la première scène."""
        return f"{self.lieu}\n\n{self.situation}\n\nCe que le personnage ignore encore : {self.secret}"

    def lignes(self) -> list[str]:
        """L'amorce, montrée au joueur : tout ce que son personnage sait déjà (le secret n'en fait pas partie)."""
        return ([f"Son passé : {self.passe}", f"Où tout commence : {self.lieu}", "Les gens de sa vie :"]
                + [f"  - {p['nom']}, {p['role'].rstrip('.')} — {p['attitude']}" for p in self.pnj]
                + ["Ce qui l'occupe :"] + [f"  - {f['texte']}" for f in self.fils])

    def ranger(self, memoire: Memoire, moment: Moment):
        """Écrit l'amorce dans la mémoire de la campagne."""
        for p in self.pnj:
            memoire.noter_pnj(p["identifiant"], p["nom"], p["role"], p["attitude"])
        for f in self.fils:
            memoire.ouvrir_fil(f["identifiant"], f["texte"])
        memoire.ouvrir_fil(FIL_SECRET, f"Secret, ignoré du personnage : {self.secret}")
        memoire.ajouter_souvenir(f"## {TITRE}\n\n{self.passe}\n\nLa campagne commence ici, {moment} : {self.lieu}\n")


def _texte(valeur) -> str:
    return " ".join(str(valeur or "").split())


def verifier(donnees: dict, plan: str = "") -> tuple[Amorce | None, list[str]]:
    """L'amorce proposée par le LLM, nettoyée, ou la liste de ses erreurs."""
    erreurs = []
    textes = {cle: _texte(donnees.get(cle)) for cle in TEXTES}
    for cle, maximum in TEXTES.items():
        if not 0 < len(textes[cle]) <= maximum:
            erreurs.append(f"« {cle} » : de 1 à {maximum} caractères ({len(textes[cle])} ici).")
    listes = {}
    for cle, (mini, maxi), champs in (("pnj", NB_PNJ, {"nom": "nom", "role": "rôle", "attitude": "attitude"}),
                                      ("fils", NB_FILS, {"texte": "fil"})):
        entrees = donnees.get(cle)
        entrees = [e for e in entrees if isinstance(e, dict)] if isinstance(entrees, list) else []
        if not mini <= len(entrees) <= maxi:
            erreurs.append(f"« {cle} » : de {mini} à {maxi} ({len(entrees)} ici).")
        propres, vus = [], set()
        for entree in entrees:
            identifiant = _texte(entree.get("identifiant"))
            try:
                verifier_identifiant(identifiant)
                if identifiant in vus or identifiant == FIL_SECRET:
                    raise MemoireRefusee(f"L'identifiant « {identifiant} » est en double dans « {cle} ».")
                propre = {"identifiant": identifiant}
                for champ, libelle in champs.items():
                    propre[champ] = _texte(entree.get(champ))
                    if not 0 < len(propre[champ]) <= LONGUEURS[libelle]:
                        raise MemoireRefusee(f"« {identifiant} », {libelle} : de 1 à {LONGUEURS[libelle]} caractères "
                                             f"({len(propre[champ])} ici).")
            except MemoireRefusee as erreur:
                erreurs.append(str(erreur))
                continue
            vus.add(identifiant)
            propres.append(propre)
        listes[cle] = propres
    if erreurs:
        return None, erreurs
    return Amorce(plan, textes["passe"], textes["lieu"], textes["situation"], textes["secret"], listes["pnj"],
                  listes["fils"]), []


def _chaine(description: str, maximum: int) -> dict:
    """Un texte de l'outil. Sa limite est écrite dans la description : sans elle, le LLM la dépasse une fois sur deux."""
    return {"type": "string", "description": f"{description} {maximum} caractères au plus."}


OUTIL_AMORCE = {"type": "function", "function": {
    "name": "amorcer_campagne",
    "description": "Poser ce qui existe avant la première scène : le passé du personnage, le lieu, la situation, "
                   "les gens qu'il connaît et ce qui l'occupe.",
    "parameters": {"type": "object", "additionalProperties": False,
                   "required": ["passe", "lieu", "situation", "secret", "pnj", "fils"], "properties": {
        "passe": _chaine("Le passé du personnage, en deux ou trois phrases : d'où il vient, ce qui l'a mené là.",
                         TEXTES["passe"]),
        "lieu": _chaine("Le lieu où la campagne commence, en une ou deux phrases concrètes.", TEXTES["lieu"]),
        "situation": _chaine("Ce qui se passe à l'instant où la campagne commence, en une ou deux phrases : un "
                             "problème qui demande une décision, sans la prendre à la place du joueur.",
                             TEXTES["situation"]),
        "secret": _chaine("Ce que le personnage ignore et que seul le MJ sait, en une phrase courte : qui ment, qui "
                          "tire les ficelles, ce qui se cache derrière. Le joueur ne le lira pas.", TEXTES["secret"]),
        "pnj": {"type": "array", "minItems": NB_PNJ[0], "maxItems": NB_PNJ[1],
                "description": "Les gens vivants que le personnage connaît déjà.",
                "items": {"type": "object", "additionalProperties": False,
                          "required": ["identifiant", "nom", "role", "attitude"], "properties": {
                              "identifiant": _chaine("Minuscules, chiffres et _ : par exemple doc_mori.", 40),
                              "nom": _chaine("Son nom.", LONGUEURS["nom"]),
                              "role": _chaine("Qui il est et ce qu'il fait, en quelques mots.", LONGUEURS["rôle"]),
                              "attitude": _chaine("Ce qu'il pense du personnage, et pourquoi, en une phrase.",
                                                  LONGUEURS["attitude"])}}},
        "fils": {"type": "array", "minItems": NB_FILS[0], "maxItems": NB_FILS[1],
                 "description": "Les fils de l'histoire déjà ouverts (quête, promesse, dette, menace), dont un tiré "
                                "de la motivation du personnage.",
                 "items": {"type": "object", "additionalProperties": False, "required": ["identifiant", "texte"],
                           "properties": {"identifiant": _chaine("Minuscules, chiffres et _ : par exemple "
                                                                 "dette_arasaka.", 40),
                                          "texte": _chaine("Le fil, en une phrase.", LONGUEURS["fil"])}}},
    }}}}


def _demande(univers: Univers, perso: Personnage, plan: str, erreurs: list[str]) -> list[dict]:
    p = perso
    qui = "une femme" if p.sexe == "femme" else "un homme" if p.sexe == "homme" else "un personnage"
    texte = (f"Univers : {univers.nom} ({univers.genre}). Cadre : {univers.cadre}\n"
             f"Le personnage du joueur : {p.nom}, {qui}, {p.parcours}. "
             f"{univers.descriptions.get(p.parcours, '')}\n"
             f"Motivation : {p.motivation}\nLien : {p.lien}\nDéfaut : {p.defaut}\n"
             + (f"Allure : {p.allure}\n" if p.allure else "")
             + (f"Objets : {', '.join(p.objets)}\n" if p.objets else "")
             + f"Métiers de cet univers : {', '.join(sorted(univers.parcours))}.\n\n"
             f"Le plan de départ de la campagne : {plan}\n\n"
             "Appelle amorcer_campagne pour adapter ce plan au cadre et au personnage. Les PNJ sont des gens "
             "vivants, qu'il peut croiser ; si son lien est une personne vivante, elle en fait partie. Un fil vient "
             "de sa motivation. La situation se passe dans le lieu, lance le plan et laisse la décision au joueur, "
             "sans lui poser de question. Ne recopie pas la complication : incarne-la dans un PNJ ou dans un fait "
             "précis. Le passé, le lieu, la situation, les PNJ et les fils ne disent que ce que le personnage "
             "sait ; ce qu'il ignore (un mensonge, un commanditaire caché) va dans le secret, et nulle part ailleurs. "
             "En français, à la troisième personne (jamais « tu »), sans chiffres de jeu, sans rien décider à la "
             "place du joueur. Des phrases courtes : "
             "chaque champ a une longueur maximum, respecte-la.")
    if erreurs:
        texte += "\nTa proposition précédente a des erreurs : " + " ; ".join(erreurs)
    return [{"role": "system", "content": "Tu prépares le début d'une campagne de jeu de rôle en solo."},
            {"role": "user", "content": texte}]


def proposer_amorce(serveur, univers: Univers, perso: Personnage, plan: str, budget: int | None = None) -> Amorce | None:
    """L'amorce, par le LLM, vérifiée par le code. None s'il n'y arrive pas : le MJ ouvrira seul la campagne."""
    erreurs = []
    for _ in range(ESSAIS):
        reponse = serveur.discuter(_demande(univers, perso, plan, erreurs), [OUTIL_AMORCE], budget)
        message = reponse["choices"][0]["message"]
        appel = next((a for a in message.get("tool_calls") or []
                      if a["function"]["name"] == "amorcer_campagne"), None)
        if appel is None:
            erreurs = ["tu n'as pas appelé l'outil amorcer_campagne"]
            continue
        arguments = appel["function"]["arguments"]
        try:
            donnees = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
        except (ValueError, TypeError):
            erreurs = ["arguments illisibles"]
            continue
        amorce, erreurs = verifier(donnees, plan)
        if amorce:
            return amorce
    return None
