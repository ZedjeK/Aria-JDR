"""Les familles d'outils du MJ : ce qu'il a sous la main, et ce qu'il va chercher.

Tous les outils ensemble pèsent plus de 10 000 jetons, envoyés à chaque requête. Avec les familles, le MJ
n'a d'office que le socle : de quoi savoir où on en est, arbitrer une action, faire entrer quelqu'un, ouvrir
un affrontement, tenir le temps et la mémoire. Le reste est rangé par famille :

- le moteur ouvre seul celles que l'état du jeu impose (un combat en cours ouvre « combat ») ;
- le MJ ouvre les autres avec l'outil `outils`, deux au plus, jusqu'à la fin de la scène.

Ce module ne porte que le découpage. La session (aria.outils) décide de ce qui est ouvert.
"""

PLAFOND = 2  # familles ouvertes par le MJ en même temps ; la troisième referme la plus ancienne

COMBAT, POURSUITE, COMMERCE, MISSIONS, SOINS, MAGIE = (
    "combat", "poursuite et véhicules", "commerce", "missions et trame", "soins et santé mentale", "magie")

# Pour chaque famille : ses outils, et ce qu'on en dit au MJ quand elle est fermée
FAMILLES: dict[str, tuple[tuple[str, ...], str]] = {
    COMBAT: (("attaquer_zone", "action_combat", "rejoindre_combat", "fin_de_tour", "fin_combat", "stabiliser",
              "lancer_drone"),
             "attaquer une zone, agir en combat, faire entrer un combattant, finir un tour ou le combat, "
             "stabiliser un mourant, lancer un drone"),
    POURSUITE: (("debut_poursuite", "round_poursuite", "fin_poursuite", "piloter", "reparer", "tirer_sur_vehicule",
                 "eperonner", "tirer_arme_montee", "lance_fumigenes"),
                "lancer une poursuite et la jouer, piloter, réparer, se battre en véhicule"),
    COMMERCE: (("voir_boutique", "acheter", "vendre", "payer", "commander", "niveau_de_vie", "emprunter",
                "semaine_de_travail", "poser_implant"),
               "voir une boutique, acheter, vendre, payer un service, commander, niveau de vie, emprunter, "
               "travailler, poser un implant"),
    MISSIONS: (("ouvrir_mission", "accepter_mission", "indice", "reputation", "melee"),
               "ouvrir ou accepter une mission, donner un indice, changer une réputation, jouer une mêlée"),
    SOINS: (("soigner", "repos", "choc", "recuperer_sante_mentale"),
            "soigner, se reposer, encaisser un choc, récupérer de la Santé mentale"),
    MAGIE: (("lancer_sort",), "lancer un sort"),
}

_FAMILLE_DE = {outil: famille for famille, (outils, _) in FAMILLES.items() for outil in outils}


def famille_de(outil: str) -> str | None:
    """La famille d'un outil ; None pour un outil du socle, toujours sous la main."""
    return _FAMILLE_DE.get(outil)


def resume(famille: str) -> str:
    return FAMILLES[famille][1]
