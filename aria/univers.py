"""Les univers : réglages, habillage des compétences, compétences thématiques, parcours et armurerie.

Référence : REGLES.md 1.2 et 4. Un univers se décrit dans un fichier JSON (voir le dossier
`univers/`), qu'il soit écrit à la main ou généré par le LLM ; le code le vérifie toujours.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from aria.equipement import (
    Arme,
    Armure,
    BonusArme,
    BonusArmure,
    Munitions,
    Portee,
    Propriete,
    Rarete,
    Recharge,
    verifier_arme,
    verifier_armure,
)
from aria.personnage import (
    COMPETENCES_SOCLE,
    MAGIE,
    NB_COMPETENCES_PARCOURS,
    DefCompetence,
    Personnage,
    creer_personnage,
)
from aria.reglages import Curseur
from aria.sante_mentale import Choc, ReglagesMentaux

MAX_COMPETENCES_THEMATIQUES = 3
BASE_MAX_THEMATIQUE = 10
DOMAINE_THEMATIQUE = "Thématique"


class UniversInvalide(ValueError):
    """L'univers ne respecte pas les règles. `erreurs` liste tous les problèmes trouvés."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("Univers invalide :\n- " + "\n- ".join(erreurs))


@dataclass
class Univers:
    nom: str
    genre: str
    cadre: str = ""
    curseur: Curseur = Curseur.STANDARD
    monde_impitoyable: bool = False
    magie_active: bool = True
    habillage: dict[str, str] = field(default_factory=dict)  # nom de socle → nom dans l'univers
    competences_thematiques: tuple[DefCompetence, ...] = ()
    parcours: dict[str, list[str]] = field(default_factory=dict)  # nom du parcours → 8 compétences de socle
    armes: tuple[Arme, ...] = ()
    armures: tuple[Armure, ...] = ()
    chocs_banals: frozenset[Choc] = frozenset()
    chocs_normaux: frozenset[Choc] = frozenset()

    def nom_affiche(self, competence: str) -> str:
        """Le nom qu'une compétence de socle porte dans cet univers (« Technologie » → « Piratage »)."""
        return self.habillage.get(competence, competence)

    def competences_disponibles(self) -> dict[str, DefCompetence]:
        disponibles = {nom: c for nom, c in COMPETENCES_SOCLE.items() if self.magie_active or nom != MAGIE}
        disponibles.update({c.nom: c for c in self.competences_thematiques})
        return disponibles

    def reglages_mentaux(self) -> ReglagesMentaux:
        return ReglagesMentaux(self.curseur, self.monde_impitoyable, self.chocs_banals, self.chocs_normaux)

    def arme(self, nom: str) -> Arme:
        return _trouver(self.armes, nom, "arme")

    def armure(self, nom: str) -> Armure:
        return _trouver(self.armures, nom, "armure")

    def creer_personnage(self, parcours: str, **fiche) -> Personnage:
        """Crée un perso dans cet univers : parcours, magie, compétences thématiques et points de destin."""
        if parcours not in self.parcours:
            raise UniversInvalide([f"Parcours inconnu dans {self.nom} : « {parcours} »."])
        perso = creer_personnage(
            parcours=parcours,
            competences_parcours=self.parcours[parcours],
            magie_active=self.magie_active,
            competences_thematiques=self.competences_thematiques,
            **fiche,
        )
        perso.points_destin = self.curseur.points_destin
        return perso

    def verifier(self, genere: bool = False) -> list[str]:
        """Liste tous les problèmes de l'univers (vide s'il est valide).

        `genere` : True s'il vient du LLM (les objets légendaires sont alors refusés).
        """
        erreurs = []
        if not self.nom.strip():
            erreurs.append("L'univers n'a pas de nom.")
        for socle in self.habillage:
            if socle not in COMPETENCES_SOCLE:
                erreurs.append(f"Habillage d'une compétence qui n'est pas du socle : « {socle} ».")

        if len(self.competences_thematiques) > MAX_COMPETENCES_THEMATIQUES:
            erreurs.append(f"Au plus {MAX_COMPETENCES_THEMATIQUES} compétences thématiques par univers.")
        for thematique in self.competences_thematiques:
            if thematique.nom in COMPETENCES_SOCLE:
                erreurs.append(f"« {thematique.nom} » existe déjà dans le socle.")
            if thematique.base is None or not 0 <= thematique.base <= BASE_MAX_THEMATIQUE:
                erreurs.append(f"« {thematique.nom} » : la base d'une compétence thématique va de 0 à {BASE_MAX_THEMATIQUE}.")
            if not thematique.description.strip():
                erreurs.append(f"« {thematique.nom} » n'a pas de description de son champ d'action.")

        disponibles = self.competences_disponibles()
        for nom_parcours, competences in self.parcours.items():
            if len(competences) != NB_COMPETENCES_PARCOURS or len(set(competences)) != len(competences):
                erreurs.append(f"Le parcours « {nom_parcours} » doit avoir {NB_COMPETENCES_PARCOURS} compétences distinctes.")
            for competence in competences:
                if competence not in disponibles:
                    erreurs.append(f"Le parcours « {nom_parcours} » utilise une compétence absente : « {competence} ».")

        for arme in self.armes:
            erreurs += [f"{arme.nom} : {e}" for e in verifier_arme(arme, genere)]
        for armure in self.armures:
            erreurs += [f"{armure.nom} : {e}" for e in verifier_armure(armure, genere)]
            for competence in armure.malus:
                if competence not in disponibles:
                    erreurs.append(f"{armure.nom} : malus sur une compétence absente « {competence} ».")
        return erreurs


def _trouver(objets, nom: str, genre: str):
    for objet in objets:
        if objet.nom == nom:
            return objet
    raise KeyError(f"Pas d'{genre} nommée « {nom} » dans cet univers.")


# --- Lecture et écriture en JSON ------------------------------------------------------------

def univers_depuis_dict(donnees: dict, genere: bool = False) -> Univers:
    """Construit un univers à partir de son JSON, et le vérifie. Lève UniversInvalide s'il est faux."""
    try:
        univers = Univers(
            nom=donnees["nom"],
            genre=donnees["genre"],
            cadre=donnees.get("cadre", ""),
            curseur=Curseur(donnees.get("curseur", "standard")),
            monde_impitoyable=donnees.get("monde_impitoyable", False),
            magie_active=donnees.get("magie", True),
            habillage=dict(donnees.get("habillage", {})),
            competences_thematiques=tuple(
                DefCompetence(c["nom"], DOMAINE_THEMATIQUE, c.get("base", 0), c.get("description", ""))
                for c in donnees.get("competences_thematiques", [])
            ),
            parcours={nom: list(competences) for nom, competences in donnees.get("parcours", {}).items()},
            armes=tuple(_arme_depuis_dict(a) for a in donnees.get("armes", [])),
            armures=tuple(_armure_depuis_dict(a) for a in donnees.get("armures", [])),
            chocs_banals=frozenset(Choc[c] for c in donnees.get("chocs_banals", [])),
            chocs_normaux=frozenset(Choc[c] for c in donnees.get("chocs_normaux", [])),
        )
    except (KeyError, ValueError, TypeError) as erreur:
        raise UniversInvalide([f"Fichier d'univers mal formé : {erreur}"]) from erreur
    erreurs = univers.verifier(genere)
    if erreurs:
        raise UniversInvalide(erreurs)
    return univers


def _arme_depuis_dict(d: dict) -> Arme:
    munitions = d.get("munitions")
    bonus = d.get("bonus", {})
    return Arme(
        nom=d["nom"],
        competence=d["competence"],
        degats=d["degats"],
        portee=Portee(d["portee"]),
        munitions=Munitions(munitions["capacite"], Recharge(munitions["recharge"])) if munitions else None,
        proprietes=frozenset(Propriete(p) for p in d.get("proprietes", [])),
        rarete=Rarete.depuis_libelle(d.get("rarete", "commune")),
        bonus=BonusArme(bonus.get("jet", 0), bonus.get("degats", 0),
                        frozenset(Propriete(p) for p in bonus.get("proprietes", []))),
    )


def _armure_depuis_dict(d: dict) -> Armure:
    bonus = d.get("bonus", {})
    return Armure(
        nom=d["nom"],
        protection=d["protection"],
        malus=dict(d.get("malus", {})),
        proprietes=frozenset(d.get("proprietes", [])),
        rarete=Rarete.depuis_libelle(d.get("rarete", "commune")),
        bonus=BonusArmure(bonus.get("protection", 0), bonus.get("malus_en_moins", 0),
                          frozenset(bonus.get("proprietes", []))),
    )


def univers_vers_dict(univers: Univers) -> dict:
    """L'inverse de `univers_depuis_dict` : le JSON d'un univers."""
    return {
        "nom": univers.nom,
        "genre": univers.genre,
        "cadre": univers.cadre,
        "curseur": univers.curseur.value,
        "monde_impitoyable": univers.monde_impitoyable,
        "magie": univers.magie_active,
        "habillage": dict(univers.habillage),
        "competences_thematiques": [
            {"nom": c.nom, "base": c.base, "description": c.description} for c in univers.competences_thematiques
        ],
        "parcours": {nom: list(competences) for nom, competences in univers.parcours.items()},
        "armes": [_arme_vers_dict(a) for a in univers.armes],
        "armures": [_armure_vers_dict(a) for a in univers.armures],
        "chocs_banals": sorted(c.name for c in univers.chocs_banals),
        "chocs_normaux": sorted(c.name for c in univers.chocs_normaux),
    }


def _arme_vers_dict(arme: Arme) -> dict:
    return {
        "nom": arme.nom,
        "competence": arme.competence,
        "degats": arme.degats,
        "portee": arme.portee.value,
        "munitions": {"capacite": arme.munitions.capacite, "recharge": arme.munitions.recharge.value}
        if arme.munitions else None,
        "proprietes": sorted(p.value for p in arme.proprietes),
        "rarete": arme.rarete.libelle,
        "bonus": {"jet": arme.bonus.jet, "degats": arme.bonus.degats,
                  "proprietes": sorted(p.value for p in arme.bonus.proprietes)},
    }


def _armure_vers_dict(armure: Armure) -> dict:
    return {
        "nom": armure.nom,
        "protection": armure.protection,
        "malus": dict(armure.malus),
        "proprietes": sorted(armure.proprietes),
        "rarete": armure.rarete.libelle,
        "bonus": {"protection": armure.bonus.protection, "malus_en_moins": armure.bonus.malus_en_moins,
                  "proprietes": sorted(armure.bonus.proprietes)},
    }


def charger_univers(chemin: str | Path, genere: bool = False) -> Univers:
    """Lit et vérifie un univers depuis un fichier JSON."""
    with open(chemin, encoding="utf-8") as fichier:
        return univers_depuis_dict(json.load(fichier), genere)
