"""Ce que la page dessine d'un combat sur la carte (REGLES.md 7.11) : les cases, les obstacles, les combattants et ce
que le joueur peut faire, en données simples (colonnes et lignes de la carte, textes déjà rédigés).

Les PV des ennemis n'y figurent que si le joueur a demandé à les voir (réglage « PV exacts ») : sinon, leur seul
état, comme dans l'écran en mots. Rien ici ne décide : le menu reste la seule façon d'agir, la carte le montre.
"""

from aria import deplacements
from aria.combat import Combat, Combattant, TypeAction
from aria.combat_auto import _cote
from aria.grille import Case, Terrain, colonne_ligne

MENU_DES_DESTINATIONS = "Où vas-tu ?"  # le titre du sous-menu dont la carte numérote les destinations
TERRAINS = {Terrain.BAS: "bas", Terrain.BLINDE: "blinde", Terrain.PLEIN: "plein", Terrain.DIFFICILE: "difficile"}


def _camp(combattant: Combattant, joueur: Combattant | None) -> str:
    if combattant is joueur:
        return "joueur"
    return "allie" if _cote(combattant) == "joueurs" else "ennemi"


def _pv(combattant: Combattant, camp: str, pv_exacts: bool) -> str | None:
    if camp == "ennemi" and not pv_exacts:
        return None
    return f"{combattant.fiche.pv}/{combattant.fiche.pv_max}"


def _peut_bouger(combat: Combat, joueur: Combattant) -> bool:
    return (combat.au_tour_de is joueur and not joueur.a_vise
            and joueur.budget.restants(TypeAction.DEPLACEMENT) > 0)


def _point(c: Case) -> list[int]:
    colonne, ligne = colonne_ligne(c)
    return [colonne, ligne]


def vue(combat: Combat | None, joueur: Combattant | None, pv_exacts: bool = False,
        destinations: list[tuple[str, Case]] | None = None) -> dict | None:
    """Le combat tel que la page le dessine ; None s'il n'y a pas de carte. `destinations` : celles du menu « Où
    vas-tu ? » qui attend la réponse du joueur, dans l'ordre du menu (la première porte le numéro 1)."""
    from aria.combat_joueur import etat_visible  # combat_joueur importe ce module

    if combat is None or combat.carte is None:
        return None
    carte = combat.carte
    combattants = []
    for c in combat.ordre:
        if _cote(c) is None or c not in carte.positions:
            continue
        camp = _camp(c, joueur)
        colonne, ligne = colonne_ligne(carte.position(c))
        combattants.append({"nom": c.nom, "camp": camp, "colonne": colonne, "ligne": ligne, "etat": etat_visible(c),
                            "pv": _pv(c, camp, pv_exacts), "debout": c.conscient and not c.hors_combat,
                            "actif": c is combat.au_tour_de})
    atteignables = []
    if joueur is not None and joueur in carte.positions and _peut_bouger(combat, joueur):
        ici = carte.position(joueur)
        atteignables = sorted(_point(c) for c in deplacements.atteignables(combat, joueur) if c != ici)
    return {
        "lieu": carte.lieu,
        "decor": combat.decor.value,
        "round": combat.round,
        "largeur": carte.largeur,
        "hauteur": carte.hauteur,
        "terrain": sorted([*_point(c), TERRAINS[t]] for c, t in carte.terrain.items()),
        "combattants": combattants,
        "atteignables": atteignables,
        "menu": MENU_DES_DESTINATIONS if destinations else None,
        "destinations": [{"numero": i, "libelle": libelle, "colonne": _point(vers)[0], "ligne": _point(vers)[1]}
                         for i, (libelle, vers) in enumerate(destinations or [], start=1)],
    }
