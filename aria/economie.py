"""L'économie (REGLES.md 13) : l'argent, les paliers de prix, le prix de chaque objet, le niveau de vie.

Le code tient tous les comptes. Un prix n'est jamais écrit à la main dans un univers : il est calculé à
partir de ce que l'objet est (ses dégâts, sa protection, son gabarit, sa gamme), puis arrondi au palier
le plus proche. La bibliothèque peut imposer un prix ou une disponibilité pour une exception
(bibliotheque/prix.json).
"""

import functools
import json
import math
from dataclasses import dataclass, field
from enum import Enum

from aria import chemins
from aria.equipement import PUISSANCE, Arme, Armure, Modification, Propriete, Qualite
from aria.implants import ESTHETIQUE, MEDICAL, Implant
from aria.personnage import Personnage
from aria.vehicules import Vehicule

# --- Les paliers (13.1) ---------------------------------------------------------------------------------

PALIERS = tuple(m * 10 ** e for e in range(1, 8) for m in (1, 2, 5))  # 10, 20, 50, 100… jusqu'à 50 millions


def palier(valeur: float) -> int:
    """Le palier le plus proche d'une valeur (en proportion : 300 est plus près de 200 que de 500)."""
    return min(PALIERS, key=lambda p: abs(math.log(p) - math.log(max(valeur, 1))))


def decaler(prix: int, crans: int) -> int:
    """Le prix, quelques paliers plus haut (crans > 0) ou plus bas. Jamais sous le premier palier."""
    return PALIERS[max(0, min(len(PALIERS) - 1, PALIERS.index(palier(prix)) + crans))]


# --- Le prix d'un objet (13.3) ---------------------------------------------------------------------------

EXCEPTIONS = chemins.RESSOURCES / "bibliotheque" / "prix.json"
COURANT, RESTREINT, MILITAIRE = "courant", "restreint", "militaire"
DISPONIBILITES = (COURANT, RESTREINT, MILITAIRE)

_DEGATS = {"1d4": 250, "1d6": 400, "1d8": 600, "1d10": 800, "1d12": 1000, "2d6": 1200, "2d6+1": 1400,
           "2d6+2": 1500, "3d6": 2500, "4d6": 5000}
_SANS_DEGATS = 300  # une grenade fumigène, une impulsion IEM
_CATEGORIES = {"armes de mêlée": 0.25, "armes de lancer": 0.1, "armes de trait": 0.5, "armes de poing": 1, "fusils": 1,
               "fusils de précision": 2, "armes intelligentes": 3, "armes lourdes": 4, "grenades": 0.1,
               "explosifs": 0.2, "drones": 0.2}
_PROPRIETES = {"silencieuse": 1.25, "perforante": 1.5, "rafale": 1.25, "encombrante": 0.9, "fragile": 0.75}
_PROTECTION = {1: 300, 2: 800, 3: 2000, 4: 6000}
_GABARITS = {"léger": 5000, "moyen": 20000, "lourd": 60000, "militaire": 500000, "drone": 2000}
_VITESSES = {"lente": 0.7, "moyenne": 1, "rapide": 1.3, "très rapide": 2}
GAMMES = {"standard": 2000, "avancée": 10000, "militaire": 50000}
SANS_GAMME = 500  # l'esthétique et le médical
_QUALITES = {Qualite.USE: -1, Qualite.ORIGINE: 0, Qualite.PERSONNALISE: 0, Qualite.UNIQUE: 2}
MARQUE = 1  # un objet de marque : un palier au-dessus, modification d'usine comprise
_CATEGORIES_MILITAIRES = ("armes lourdes", "explosifs", "drones")
_CATEGORIES_RESTREINTES = ("grenades", "fusils de précision", "armes intelligentes")


@functools.lru_cache(maxsize=1)
def _exceptions() -> dict:
    """Les prix et les disponibilités imposés par la bibliothèque, par nom d'objet."""
    try:
        return json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    except OSError:
        return {"prix": {}, "disponibilites": {}}


def verifier_exceptions(noms_connus: set[str]) -> list[str]:
    """bibliotheque/prix.json : des objets qui existent, des prix qui sont des paliers."""
    exceptions = _exceptions()
    erreurs = [f"prix.json : « {nom} » n'existe pas dans la bibliothèque."
               for cle in ("prix", "disponibilites") for nom in exceptions.get(cle, {}) if nom not in noms_connus]
    erreurs += [f"prix.json : le prix de « {nom} » ({prix}) n'est pas un palier."
                for nom, prix in exceptions.get("prix", {}).items() if prix not in PALIERS]
    erreurs += [f"prix.json : disponibilité inconnue pour « {nom} » : « {d} »."
                for nom, d in exceptions.get("disponibilites", {}).items() if d not in DISPONIBILITES]
    return erreurs


def _valeurs(proprietes) -> set[str]:
    return {p.value if isinstance(p, Propriete) else str(p) for p in proprietes}


def prix_modification(m) -> int:
    """De 200 à 2 000 selon l'effet."""
    valeur = abs(getattr(m, "valeur", 0) or 0)
    if getattr(m, "effet", "") == PUISSANCE:
        return 500 if valeur <= 1 else 2000
    return 1000 if valeur >= 10 else 500 if valeur >= 5 else 200


def _base(objet, univers=None) -> float:
    """Le prix de l'objet d'origine, sans marque ni modification, avant l'arrondi."""
    if isinstance(objet, Arme):
        total = _DEGATS.get(objet.degats, _SANS_DEGATS) * _CATEGORIES.get(objet.categorie, 1)
        for p in _valeurs(objet.proprietes):
            total *= _PROPRIETES.get(p, 1)
        return total
    if isinstance(objet, Armure):
        return _PROTECTION.get(objet.protection, _PROTECTION[4]) * (1 + sum(objet.malus.values()) / 100)
    if isinstance(objet, Vehicule):
        total = _GABARITS[objet.gabarit] * _VITESSES[objet.vitesse] * (1 + objet.blindage / 10)
        if univers is not None:
            total += sum(prix(univers.arme(montee["arme"]), univers)
                         for montee in objet.armes_montees if montee.get("arme"))
        return total
    if isinstance(objet, Implant):
        return SANS_GAMME if objet.effet in (ESTHETIQUE, MEDICAL) else GAMMES[objet.gamme]
    if isinstance(objet, Modification):
        return prix_modification(objet)
    raise TypeError(f"Pas de prix pour {type(objet).__name__}.")


def _origine(objet, univers) -> str:
    """Le nom de l'objet dans la bibliothèque (le cadre a pu le renommer)."""
    return univers.origines.get(objet.nom, objet.nom) if univers is not None else objet.nom


def prix(objet, univers=None) -> int:
    """Le prix d'un objet : toujours un palier. `univers` sert à retrouver son nom dans la bibliothèque
    (pour un prix imposé) et les armes montées d'un véhicule."""
    impose = _exceptions().get("prix", {}).get(_origine(objet, univers))
    resultat = impose if impose is not None else palier(_base(objet, univers))
    qualite = getattr(objet, "qualite", Qualite.ORIGINE)
    crans = _QUALITES.get(qualite, 2) + (MARQUE if getattr(objet, "fabricant", None) and impose is None else 0)
    resultat = decaler(resultat, crans)
    # Les modifications posées s'ajoutent, sauf celle d'usine d'un objet de marque (comprise dans son palier)
    posees = list(getattr(objet, "modifications", ()))[1 if getattr(objet, "fabricant", None) else 0:]
    if posees:
        resultat = palier(resultat + sum(prix_modification(m) for m in posees))
    return resultat


def disponibilite(objet, univers=None) -> str:
    """Courant (en boutique), restreint (par un contact) ou militaire (jamais en vente)."""
    imposee = _exceptions().get("disponibilites", {}).get(_origine(objet, univers))
    if imposee:
        return imposee
    if getattr(objet, "qualite", None) in (Qualite.UNIQUE, Qualite.LEGENDAIRE):
        return MILITAIRE  # un objet unique ne se trouve jamais en boutique
    if isinstance(objet, Arme):
        proprietes = _valeurs(objet.proprietes)
        if objet.categorie in _CATEGORIES_MILITAIRES or objet.montee:
            return MILITAIRE
        if objet.categorie in _CATEGORIES_RESTREINTES or "rafale" in proprietes \
                or ("silencieuse" in proprietes and objet.categorie == "armes de poing"):
            return RESTREINT
        return COURANT
    if isinstance(objet, Armure):
        return RESTREINT if objet.protection >= 3 else COURANT
    if isinstance(objet, Vehicule):
        return MILITAIRE if objet.gabarit == "militaire" or objet.armes_montees else COURANT
    if isinstance(objet, Implant):
        if objet.effet in (ESTHETIQUE, MEDICAL):
            return COURANT
        return {"standard": COURANT, "avancée": RESTREINT, "militaire": MILITAIRE}[objet.gamme]
    return COURANT


def catalogue(univers) -> list[tuple[str, str, int, str]]:
    """Tout ce qui a un prix dans l'univers : (famille, nom, prix, disponibilité), du moins cher au plus cher."""
    lignes = []
    for famille, objets in (("Armes", univers.armes), ("Armures", univers.armures), ("Implants", univers.implants),
                            ("Véhicules", univers.vehicules)):
        lignes += sorted(((famille, o.nom, prix(o, univers), disponibilite(o, univers)) for o in objets),
                         key=lambda ligne: (ligne[2], ligne[1]))
    return lignes


# --- Le niveau de vie (13.2) -----------------------------------------------------------------------------

class NiveauDeVie(Enum):
    A_LA_RUE = "à la rue"
    MODESTE = "modeste"
    CONFORTABLE = "confortable"


COUT_DE_LA_VIE = {NiveauDeVie.A_LA_RUE: 0, NiveauDeVie.MODESTE: 350, NiveauDeVie.CONFORTABLE: 1000}
SEMAINE = 7  # jours de jeu entre deux échéances
BONUS_THERAPIE_CONFORTABLE = 10


def niveau_effectif(perso: Personnage) -> NiveauDeVie:
    """Le niveau de vie que le personnage vit vraiment : à la rue tant que sa semaine n'est pas payée."""
    return NiveauDeVie(perso.niveau_de_vie) if perso.semaine_payee else NiveauDeVie.A_LA_RUE


def a_la_rue(perso: Personnage) -> bool:
    return niveau_effectif(perso) is NiveauDeVie.A_LA_RUE


def changer_niveau_de_vie(perso: Personnage, niveau: NiveauDeVie):
    """Le nouveau tarif vaut à l'échéance suivante ; descendre « à la rue » est immédiat."""
    perso.niveau_de_vie = niveau.value
    if niveau is NiveauDeVie.A_LA_RUE:
        perso.semaine_payee = True  # rien à payer : il vit ce qu'il a choisi


@dataclass
class Echeance:
    """Ce qu'une échéance hebdomadaire a changé, pour que le MJ le raconte."""

    jour: int
    niveau: str
    cout: int
    payee: bool
    argent: int
    dettes_payees: list = field(default_factory=list)  # (créancier, somme, reste dû)
    dettes_manquees: list = field(default_factory=list)  # (créancier, somme, échéances manquées)
    lien: bool | None = None  # None : pas de lien à charge ; sinon, sa semaine a-t-elle été payée


COUT_DU_LIEN = 200  # par semaine, pour un lien à charge (13.7)


def cout_de_la_semaine(perso: Personnage, loge: bool = False) -> int:
    """Ce que coûte sa semaine. Logé par son clan (REGLES.md 14.6), le niveau modeste ne coûte rien, et un
    niveau au-dessus ne coûte que la différence."""
    cout = COUT_DE_LA_VIE[NiveauDeVie(perso.niveau_de_vie)]
    return max(0, cout - COUT_DE_LA_VIE[NiveauDeVie.MODESTE]) if loge else cout


def payer_la_semaine(perso: Personnage, loge: bool = False) -> bool:
    """Paie une semaine du niveau de vie choisi, si l'argent suffit."""
    cout = cout_de_la_semaine(perso, loge)
    perso.semaine_payee = perso.argent >= cout
    if perso.semaine_payee:
        perso.argent -= cout
    return perso.semaine_payee


def passer_les_echeances(perso: Personnage, jour: int, loge: bool = False) -> list[Echeance]:
    """Débite chaque échéance arrivée (une tous les 7 jours). Sans l'argent, le personnage tombe à la rue
    jusqu'à ce qu'une semaine soit de nouveau payée. `loge` : son clan le loge sans payer."""
    passees = []
    while jour >= perso.echeance:
        # Dans l'ordre : les dettes passent avant tout, puis le lien à charge, puis le loyer
        payees, manquees = [], []
        for dette in list(perso.dettes):
            somme = min(dette["echeance"], dette["reste"])
            if perso.argent >= somme:
                perso.argent -= somme
                dette["reste"] -= somme
                payees.append((dette["creancier"], somme, dette["reste"]))
                if dette["reste"] <= 0:
                    perso.dettes.remove(dette)
            else:
                dette["manquees"] += 1
                manquees.append((dette["creancier"], somme, dette["manquees"]))
        lien = None
        if perso.lien_a_charge:
            lien = perso.charge_payee = perso.argent >= COUT_DU_LIEN
            if lien:
                perso.argent -= COUT_DU_LIEN
        cout = cout_de_la_semaine(perso, loge)
        payee = payer_la_semaine(perso, loge)
        passees.append(Echeance(perso.echeance, perso.niveau_de_vie, cout, payee, perso.argent, payees, manquees, lien))
        perso.echeance += SEMAINE
    return passees


# --- Le rang de revenu d'un métier (13.4) ----------------------------------------------------------------

@dataclass(frozen=True)
class Rang:
    nom: str
    argent_de_depart: int
    niveau_de_vie: NiveauDeVie
    revenu: int  # d'une semaine de travail réussie


RANGS = {r.nom: r for r in (Rang("précaire", 500, NiveauDeVie.MODESTE, 350),
                             Rang("établi", 2000, NiveauDeVie.MODESTE, 700),
                             Rang("aisé", 5000, NiveauDeVie.CONFORTABLE, 2000))}
RANG_PAR_DEFAUT = "établi"


def installer(perso: Personnage, rang: str = RANG_PAR_DEFAUT, paliers: int = 0):
    """L'argent et le niveau de vie de départ ; la première semaine est payée (première échéance au jour 8).
    `paliers` : un personnage aguerri ou vétéran part avec un ou deux paliers d'argent en plus."""
    fiche = RANGS.get(rang, RANGS[RANG_PAR_DEFAUT])
    perso.argent, perso.niveau_de_vie = decaler(fiche.argent_de_depart, paliers), fiche.niveau_de_vie.value
    perso.semaine_payee, perso.echeance = True, 1 + SEMAINE


def montant(somme: int, monnaie: str = "") -> str:
    """« 2 000 crédits »."""
    return f"{somme:,}".replace(",", " ") + (f" {monnaie}" if monnaie else "")


if __name__ == "__main__":  # la vue des prix d'un univers, pour l'annexe de REGLES.md
    import sys

    from aria.univers import charger_univers

    sys.stdout.reconfigure(encoding="utf-8")
    monde = charger_univers(sys.argv[1] if len(sys.argv) > 1 else chemins.UNIVERS / "cyberpunk.json")
    famille_en_cours = None
    for famille, nom, cout, dispo in catalogue(monde):
        if famille != famille_en_cours:
            print(f"\n**{famille}**\n\n| Objet | Prix | Disponibilité |\n|---|---|---|")
            famille_en_cours = famille
        print(f"| {nom} | {montant(cout)} | {dispo} |")
