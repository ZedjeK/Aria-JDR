"""Le banc du générateur : le LLM adapte-t-il un univers comme il faut, et avec quel budget de réflexion ?

Cinq cadres de référence, joués deux fois chacun. Pour chaque essai, le code vérifie ce qu'il sait juger :
- l'univers adapté est valide pour le moteur ;
- les objets qui n'existent pas dans le cadre ont été retirés, sous quelque nom que ce soit ;
- les nouveaux noms ne sont ni anglais, ni anachroniques, ni fautifs (pas de lettre triplée) ;
- l'univers a de 15 à 30 parcours, garde ceux qu'il doit garder, et en a gagné au moins un ;
- un cadre déjà proche de la bibliothèque ne bouge presque pas.

On garde le plus petit budget de réflexion qui réussit au moins 9 essais sur 10 : il va dans le profil du MJ
(`budget_generateur`). Le jeu s'en sert pour créer les campagnes.

Lancement (après le banc du MJ, qui choisit le modèle) :
    .venv\\Scripts\\python.exe -m aria.banc_generateur --budgets 128 256 512
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

from aria import banc, chemins, generateur, llm, optimiseur
from aria.bibliotheque import Bibliotheque, charger
from aria.univers import UniversInvalide, univers_depuis_dict

BUDGETS = (128, 256, 512)
REPETITIONS = 2
SEUIL = 0.9
# Des mots anglais qu'un nom français n'a pas à porter (en mots entiers : « veste » n'est pas « vest »)
# « Gun » seul n'y est pas : il vit dans de vrais noms d'armes (le M3 « Grease Gun » du Mékong)
ANGLAIS = re.compile(r"\b(saw|flamethrower|shotgun|rifle|knife|armor|armour|truck|helmet|vest|blade|launcher|"
                     r"machine|bike|sword|axe|bow|smuggl\w*)\b", re.IGNORECASE)
TRIPLE = re.compile(r"(\w)\1\1", re.IGNORECASE)  # « Camionnettte »
DETAIL = chemins.DONNEES / "banc_generateur.json"


@dataclass(frozen=True)
class Cadre:
    """Un cadre de référence et ce qu'on attend du générateur."""

    nom_court: str
    genre: str
    nom: str
    cadre: str
    gardes: frozenset[str] = frozenset()
    interdits: tuple[str, ...] = ()  # des objets de la bibliothèque qui ne doivent pas rester, sous aucun nom
    mots_interdits: tuple[str, ...] = ()  # des noms anachroniques pour ce cadre
    changements_max: int | None = None  # retraits et renommages d'objets par le LLM, au plus
    annee: int | None = None  # donnée par le joueur ; sans elle, le LLM la déduit du cadre


ANNEES_20 = ("sten", "uzi", "glock", "kalach", "ak-47", "m16", "beretta 92", "mp5")
CADRES = (
    Cadre("osaka", "Cyberpunk", "Osaka 2091", "Osaka en 2091, sous une pluie acide permanente.",
          gardes=frozenset({"Netrunner"}), changements_max=6, annee=2091),
    Cadre("arkham", "Horreur", "Arkham 1925", "Arkham, Massachusetts, en 1925 : la Prohibition, l'université Miskatonic "
          "et des disparitions inexpliquées.",
          interdits=("Fusil d'assaut", "Lance-roquettes", "Minigun", "Grenade flash", "Scooter électrique", "Jet-ski",
                     "Blindé de transport", "Armure tactique"),
          mots_interdits=ANNEES_20, annee=1925),
    Cadre("mekong", "Militaire", "Mékong 1968", "Le delta du Mékong en 1968 : rizières, patrouilles fluviales et "
          "embuscades dans la jungle.",
          interdits=("Scooter électrique", "Jet-ski", "AV d'assaut", "Drone de reconnaissance", "Drone de combat",
                     "Drone kamikaze", "Charge IEM lourde", "Charge de drone kamikaze", "Grenade flash"),
          mots_interdits=("glock", "mp5", "famas", "drone"), annee=1968),
    Cadre("valombre", "Fantasy", "Les Marches de Valombre", "Un royaume médiéval de forêts et de forteresses, où la "
          "magie est rare et crainte.", changements_max=3, annee=1300),
    Cadre("lyon", "Post-apo", "Lyon 2061", "Lyon en 2061, vingt ans après l'effondrement : des quartiers barricadés, "
          "des convois et des pillards."),
)


@dataclass
class Essai:
    cadre: str
    budget: int
    reussi: bool
    raisons: list[str] = field(default_factory=list)
    duree: float = 0.0
    resume: dict = field(default_factory=dict)


def _nouveaux_noms(a: generateur.Adaptation) -> list[str]:
    noms = [n for r in a.renommages.values() for n in r.values()]
    return noms + list(a.parcours_renommes.values()) + [p["nom"] for p in a.parcours_ajoutes]


def verifier(cadre: Cadre, donnees: dict, a: generateur.Adaptation) -> list[str]:
    """Ce qui ne va pas dans l'adaptation (vide si l'essai est réussi)."""
    raisons = []
    d = generateur.appliquer(donnees, a)
    try:
        univers = univers_depuis_dict(d)
    except UniversInvalide as erreur:
        return [f"univers adapté invalide : {e}" for e in erreur.erreurs[:3]]
    restants = {univers.origines.get(n, n) for n in generateur.tous_les_noms(d)}
    raisons += [f"« {x} » est resté" for x in cadre.interdits if x in restants]
    for nom in _nouveaux_noms(a):
        if ANGLAIS.search(nom):
            raisons.append(f"nom anglais : « {nom} »")
        if TRIPLE.search(nom):
            raisons.append(f"faute : « {nom} »")
        if any(m in nom.lower() for m in cadre.mots_interdits):
            raisons.append(f"nom anachronique : « {nom} »")
    if not generateur.PARCOURS_MIN <= len(univers.parcours) <= generateur.PARCOURS_MAX:
        raisons.append(f"{len(univers.parcours)} parcours, au lieu de {generateur.PARCOURS_MIN} à {generateur.PARCOURS_MAX}")
    raisons += [f"parcours gardé perdu : {g}" for g in cadre.gardes if univers.nom_local(g) not in univers.parcours]
    if not a.parcours_ajoutes:
        raisons.append("aucun parcours propre au cadre")
    changements = sum(map(len, a.retraits.values())) + sum(map(len, a.renommages.values()))
    if cadre.changements_max is not None and changements > cadre.changements_max:
        raisons.append(f"{changements} objets retirés ou renommés pour un cadre proche de la bibliothèque "
                       f"({cadre.changements_max} au plus)")
    return raisons


def jouer(serveur, bibliotheque: Bibliotheque, cadre: Cadre, budget: int) -> Essai:
    choix = generateur.choix_par_defaut(bibliotheque, cadre.genre, cadre.nom, cadre.cadre, cadre.annee)
    donnees = generateur.generer(bibliotheque, choix)
    debut = time.time()
    try:
        a = generateur.adapter(serveur, donnees, choix, budget, set(cadre.gardes))
    except llm.ErreurLLM as erreur:
        return Essai(cadre.nom_court, budget, False, [f"le serveur n'a pas répondu : {erreur}"], time.time() - debut)
    raisons = verifier(cadre, donnees, a)
    resume = {"annee": a.annee, "retraits_epoque": a.retraits_epoque, "retraits": a.retraits, "renommages": a.renommages, "parcours_retires": a.parcours_retires,
              "parcours_renommes": a.parcours_renommes, "parcours_ajoutes": [p["nom"] for p in a.parcours_ajoutes],
              "refus": a.refus}
    return Essai(cadre.nom_court, budget, not raisons, raisons, round(time.time() - debut, 1), resume)


def qualifier(serveur, budgets=BUDGETS, cadres=CADRES, repetitions: int = REPETITIONS, afficher=print,
              bibliotheque: Bibliotheque | None = None) -> tuple[int | None, list[Essai]]:
    """Le plus petit budget qui réussit au moins 90 % des essais ; None si aucun."""
    bibliotheque = bibliotheque or charger()
    tous = []
    for budget in budgets:
        afficher(f" budget de réflexion {budget} :")
        essais = []
        for cadre in cadres:
            for _ in range(repetitions):
                essai = jouer(serveur, bibliotheque, cadre, budget)
                essais.append(essai)
                afficher(f"  {'✓' if essai.reussi else '✗'} {cadre.nom_court:<10} {essai.duree:6.1f} s"
                         + ("" if essai.reussi else "  " + " ; ".join(essai.raisons)))
        tous += essais
        reussis = sum(e.reussi for e in essais)
        taux = reussis / len(essais)
        afficher(f" → {'QUALIFIÉ' if taux >= SEUIL else 'raté'} : {reussis}/{len(essais)}, "
                 f"{sum(e.duree for e in essais) / len(essais):.0f} s par univers")
        if taux >= SEUIL:
            return budget, tous
    return None, tous


def enregistrer(budget: int | None, essais: list[Essai]):
    """Le budget retenu rejoint le profil du MJ ; le détail des essais va à côté."""
    DETAIL.write_text(json.dumps([vars(e) for e in essais], ensure_ascii=False, indent=2), encoding="utf-8")
    profil = json.loads(banc.PROFIL.read_text(encoding="utf-8"))
    profil["budget_generateur"] = budget
    profil["date_generateur"] = datetime.now().isoformat(timespec="seconds")
    banc.PROFIL.write_text(json.dumps(profil, ensure_ascii=False, indent=2), encoding="utf-8")


def budget_generateur(profil: dict) -> int | None:
    """Le budget du générateur, ou celui du MJ tant que le banc du générateur n'a pas tourné."""
    return profil.get("budget_generateur") or profil["budget_reflexion"]


def main(arguments: list[str] | None = None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="aria.banc_generateur", description="Qualifier le générateur d'univers.")
    parser.add_argument("--budgets", type=int, nargs="+", default=BUDGETS)
    arguments = parser.parse_args(arguments)
    profil = banc.profil_valide()
    if profil is None:
        print("Pas de MJ qualifié sur ce PC : lance d'abord le banc du MJ (python -m aria.banc).")
        return
    modele = optimiseur.decrire(llm.DOSSIER_MODELES / profil["fichier"], profil["modele"])
    reglages = optimiseur.Reglages(**profil["reglages"])
    print(f"{modele.nom} ({reglages})", flush=True)
    with llm.Serveur(modele, reglages) as serveur:
        if not serveur.demarrer():
            print("Le serveur ne démarre pas : la carte graphique est peut-être occupée.")
            return
        budget, essais = qualifier(serveur, arguments.budgets, afficher=lambda t: print(t, flush=True))
    enregistrer(budget, essais)
    print(f"Détail : {DETAIL}")
    print(f"Générateur retenu : réflexion {budget} jetons." if budget else
          "Aucun budget ne passe : le jeu gardera celui du MJ pour créer les campagnes.")


if __name__ == "__main__":
    main()
