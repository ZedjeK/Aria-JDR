"""La sauvegarde d'une partie en JSON : le personnage, son univers, son équipement et le moment.

Une sauvegarde contient tout l'univers, pour rester jouable même si son fichier
d'origine change ou disparaît (un univers généré par le LLM n'a pas d'autre copie).
"""

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path

from aria.personnage import Caracteristique, Etat, Personnage
from aria.sante_mentale import Trouble, TypeTrouble
from aria.temps import Moment, Periode
from aria.univers import Univers, univers_depuis_dict, univers_vers_dict

FORMAT = 1  # à augmenter si la structure des sauvegardes change


class SauvegardeInvalide(ValueError):
    """Le fichier de sauvegarde est illisible ou d'un format inconnu."""


@dataclass
class Partie:
    personnage: Personnage
    univers: Univers
    moment: Moment = Moment(1, Periode.MATIN)
    armes: list[str] = field(default_factory=list)  # noms des armes de l'univers que le perso possède
    arme_en_main: str | None = None
    armure: str | None = None


# --- Le personnage -------------------------------------------------------------------------

def _moment_vers_dict(moment: Moment | None) -> dict | None:
    return {"jour": moment.jour, "periode": moment.periode.value} if moment else None


def _moment_depuis_dict(d: dict | None) -> Moment | None:
    return Moment(d["jour"], Periode(d["periode"])) if d else None


_CHAMPS_MOMENT = ("dernier_repos", "dernier_soin_recu", "derniere_therapie")


def personnage_vers_dict(perso: Personnage) -> dict:
    donnees = {}
    for champ in fields(perso):
        valeur = getattr(perso, champ.name)
        if champ.name == "caracteristiques":
            valeur = {c.value: v for c, v in valeur.items()}
        elif champ.name == "etat":
            valeur = valeur.value
        elif champ.name in _CHAMPS_MOMENT:
            valeur = _moment_vers_dict(valeur)
        elif champ.name == "troubles":
            valeur = [{"type": t.type.value, "seuil": t.seuil, "origine": t.origine} for t in valeur]
        elif champ.name == "competences_cochees":
            valeur = sorted(valeur)
        donnees[champ.name] = valeur
    return donnees


def personnage_depuis_dict(donnees: dict) -> Personnage:
    d = dict(donnees)
    d["caracteristiques"] = {Caracteristique(c): v for c, v in d["caracteristiques"].items()}
    d["etat"] = Etat(d["etat"])
    for nom in _CHAMPS_MOMENT:
        d[nom] = _moment_depuis_dict(d.get(nom))
    d["troubles"] = [Trouble(TypeTrouble(t["type"]), t["seuil"], t["origine"]) for t in d.get("troubles", [])]
    d["competences_cochees"] = set(d.get("competences_cochees", []))
    return Personnage(**d)


# --- La partie -------------------------------------------------------------------------------

def partie_vers_dict(partie: Partie) -> dict:
    return {
        "format": FORMAT,
        "personnage": personnage_vers_dict(partie.personnage),
        "univers": univers_vers_dict(partie.univers),
        "moment": _moment_vers_dict(partie.moment),
        "armes": list(partie.armes),
        "arme_en_main": partie.arme_en_main,
        "armure": partie.armure,
    }


def partie_depuis_dict(donnees: dict) -> Partie:
    if donnees.get("format") != FORMAT:
        raise SauvegardeInvalide(f"Format de sauvegarde inconnu : {donnees.get('format')!r} (attendu : {FORMAT}).")
    try:
        return Partie(
            personnage=personnage_depuis_dict(donnees["personnage"]),
            univers=univers_depuis_dict(donnees["univers"]),
            moment=_moment_depuis_dict(donnees["moment"]),
            armes=list(donnees.get("armes", [])),
            arme_en_main=donnees.get("arme_en_main"),
            armure=donnees.get("armure"),
        )
    except (KeyError, ValueError, TypeError) as erreur:
        raise SauvegardeInvalide(f"Sauvegarde illisible : {erreur}") from erreur


def sauvegarder(partie: Partie, chemin: str | Path):
    """Écrit la partie en JSON. On écrit d'abord un fichier temporaire, puis on le met à la place
    de l'ancien : une coupure en pleine écriture ne détruit jamais la sauvegarde précédente."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(json.dumps(partie_vers_dict(partie), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaire, chemin)


def charger(chemin: str | Path) -> Partie:
    """Relit une partie sauvegardée."""
    try:
        donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except json.JSONDecodeError as erreur:
        raise SauvegardeInvalide(f"Le fichier n'est pas du JSON valide : {erreur}") from erreur
    return partie_depuis_dict(donnees)
