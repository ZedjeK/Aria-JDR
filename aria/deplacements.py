"""Où aller sur la carte de combat (REGLES.md 7.11) : les destinations que l'IA des ennemis choisit, et celles que le
menu propose au joueur, chacune en un déplacement.

Chaque fonction renvoie une case qu'on peut atteindre d'un seul déplacement, ou None s'il n'y en a pas d'utile. Rien
ne bouge ici : `Combat.deplacer` fait le déplacement.
"""

from aria import grille
from aria.combat import Combat, Combattant, debout, meme_cote
from aria.equipement import Portee
from aria.grille import Abri, Case, distance

PORTEE_DES_SORTS = Portee.MOYENNE  # un sort à une cible porte comme une arme de portée moyenne (REGLES.md 7.11)


def atteignables(combat: Combat, qui: Combattant) -> dict[Case, int]:
    if combat.carte is None or qui not in combat.carte.positions:
        return {}
    return combat.carte.atteignables(qui, meme_cote, debout)


def peut_toucher_depuis(combat: Combat, qui: Combattant, depuis: Case, cible: Combattant) -> bool:
    """Depuis cette case, son arme en main atteindrait la cible : au contact pour la mêlée, à portée et avec une
    ligne de tir pour une arme à distance."""
    arme, vers = qui.arme_en_main, combat.carte.position(cible)
    ecart = distance(depuis, vers)
    if arme.corps_a_corps:
        return ecart == 1
    return ecart <= grille.portee_en_cases(arme.portee) and combat.carte.abri_entre(depuis, vers) is not Abri.COUPE


def abri_contre(combat: Combat, depuis: Case, menace: Combattant) -> Abri:
    """Ce qui le protège, sur cette case, des tirs de la menace."""
    return combat.carte.abri_entre(combat.carte.position(menace), depuis)


def _la_meilleure(cases: dict[Case, int], cle) -> Case | None:
    return min(cases, key=lambda c: (cle(c), cases[c], c)) if cases else None


def vers_le_contact(combat: Combat, qui: Combattant, cible: Combattant) -> Case | None:
    """Une case voisine de la cible, la moins chère à atteindre."""
    vers = combat.carte.position(cible)
    return _la_meilleure({c: k for c, k in atteignables(combat, qui).items() if distance(c, vers) == 1}, lambda c: 0)


def au_plus_pres(combat: Combat, qui: Combattant, cible: Combattant) -> Case | None:
    """La case la plus proche de la cible, si elle est plus proche qu'ici."""
    vers, ici = combat.carte.position(cible), combat.carte.position(qui)
    plus_pres = {c: k for c, k in atteignables(combat, qui).items() if distance(c, vers) < distance(ici, vers)}
    return _la_meilleure(plus_pres, lambda c: distance(c, vers))


def loin_de(combat: Combat, qui: Combattant, menace: Combattant) -> Case | None:
    """La case la plus éloignée de la menace, si elle est plus loin qu'ici."""
    vers, ici = combat.carte.position(menace), combat.carte.position(qui)
    plus_loin = {c: k for c, k in atteignables(combat, qui).items() if distance(c, vers) > distance(ici, vers)}
    return _la_meilleure(plus_loin, lambda c: -distance(c, vers))


def a_couvert_contre(combat: Combat, qui: Combattant, menace: Combattant, garder: Combattant | None = None) -> Case | None:
    """Une case à couvert des tirs de la menace (le couvert le plus fort, puis la moins chère). `garder` : une cible
    qu'il doit encore pouvoir toucher de là (un tireur qui se poste)."""
    bonnes = {}
    for c, k in atteignables(combat, qui).items():
        abri = abri_contre(combat, c, menace)
        if abri in (Abri.AUCUN, Abri.COUPE) and not (abri is Abri.COUPE and garder is None):
            continue
        if garder is not None and not peut_toucher_depuis(combat, qui, c, garder):
            continue
        bonnes[c] = k
    return _la_meilleure(bonnes, lambda c: -abri_contre(combat, c, menace).value)


def position_de_tir(combat: Combat, qui: Combattant, cible: Combattant) -> Case | None:
    """Une case d'où il pourra tirer sur la cible : à couvert d'elle si possible, la moins chère sinon."""
    bonnes = {c: k for c, k in atteignables(combat, qui).items() if peut_toucher_depuis(combat, qui, c, cible)}
    return _la_meilleure(bonnes, lambda c: -abri_contre(combat, c, cible).value)


def vers_le_bord(combat: Combat, qui: Combattant) -> Case | None:
    """La case la plus proche du bord de la carte (par là, on quitte le combat), si elle l'en rapproche."""
    bord = combat.carte.cases_du_bord()
    if not bord:
        return None
    reste = lambda c: min(distance(c, b) for b in bord)  # noqa: E731
    ici = combat.carte.position(qui)
    plus_pres = {c: k for c, k in atteignables(combat, qui).items() if reste(c) < reste(ici)}
    return _la_meilleure(plus_pres, reste)


def rejoindre(combat: Combat, qui: Combattant, allie: Combattant) -> Case | None:
    """Une case à côté de l'allié, ou au plus près de lui."""
    return vers_le_contact(combat, qui, allie) or au_plus_pres(combat, qui, allie)
