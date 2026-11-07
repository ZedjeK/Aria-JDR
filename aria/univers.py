"""Les univers : réglages, habillage des compétences, compétences thématiques, parcours, armurerie
et domaines de magie.

Référence : REGLES.md 1.2, 4 et 10. Un univers se décrit dans un fichier JSON (voir le dossier
`univers/`), qu'il soit écrit à la main ou généré par le LLM ; le code le vérifie toujours.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from aria.equipement import (
    Arme,
    Armure,
    Munitions,
    Portee,
    Propriete,
    Qualite,
    Recharge,
    modification_depuis_dict,
    modification_vers_dict,
    verifier_arme,
    verifier_armure,
)
from aria.implants import Implant, Systeme, implant_depuis_dict, systeme_depuis_dict, verifier_catalogue
from aria.magie import (
    DOMAINES_PAR_PERSO,
    Domaine,
    Effet,
    ProprieteSort,
    Puissance,
    Sort,
    verifier_domaines,
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
from aria.vehicules import Vehicule, vehicule_depuis_dict, vehicule_vers_dict, verifier_vehicule

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
    domaines: tuple[Domaine, ...] = ()  # les domaines de magie, si l'univers en a
    systemes: tuple[Systeme, ...] = ()  # les systèmes du corps, si l'univers a des implants
    implants: tuple[Implant, ...] = ()  # le catalogue des implants (REGLES.md 11)
    vehicules: tuple[Vehicule, ...] = ()  # les véhicules et les montures (REGLES.md 12)

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

    def vehicule(self, nom: str) -> Vehicule:
        return _trouver(self.vehicules, nom, "véhicule")

    def domaine(self, nom: str) -> Domaine:
        return _trouver(self.domaines, nom, "domaine de magie")

    def sort(self, nom: str) -> Sort:
        return _trouver([s for d in self.domaines for s in d.tous], nom, "sort")

    def implant(self, nom: str) -> Implant:
        return _trouver(self.implants, nom, "implant")

    def sorts_connus(self, domaines: list[str]) -> list[Sort]:
        """Tous les sorts appris et toutes les improvisations de ces domaines (REGLES.md 10.5)."""
        return [s for nom in domaines for s in self.domaine(nom).tous]

    def creer_personnage(self, parcours: str, domaines: list[str] = (), **fiche) -> Personnage:
        """Crée un perso dans cet univers : parcours, magie, compétences thématiques, PV et points de destin.
        `domaines` : ses deux domaines de magie, si l'univers en a."""
        if parcours not in self.parcours:
            raise UniversInvalide([f"Parcours inconnu dans {self.nom} : « {parcours} »."])
        domaines = list(domaines)
        if domaines:
            erreurs = [f"Domaine de magie inconnu dans {self.nom} : « {d} »."
                       for d in domaines if d not in {x.nom for x in self.domaines}]
            if len(set(domaines)) != DOMAINES_PAR_PERSO:
                erreurs.append(f"Un personnage choisit {DOMAINES_PAR_PERSO} domaines de magie différents.")
            if erreurs:
                raise UniversInvalide(erreurs)
        perso = creer_personnage(
            parcours=parcours,
            competences_parcours=self.parcours[parcours],
            magie_active=self.magie_active,
            competences_thematiques=self.competences_thematiques,
            bonus_pv=self.curseur.bonus_pv,
            **fiche,
        )
        perso.points_destin = self.curseur.points_destin
        perso.domaines = domaines
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

        if self.domaines:
            if not self.magie_active:
                erreurs.append("L'univers a des domaines de magie, mais la magie y est désactivée.")
            erreurs += verifier_domaines(self.domaines)
        if self.implants:
            erreurs += verifier_catalogue(self.systemes, self.implants, set(disponibles))
        for vehicule in self.vehicules:
            erreurs += [f"{vehicule.nom} : {e}" for e in verifier_vehicule(vehicule, generee=genere)]
        return erreurs


def _trouver(objets, nom: str, genre: str):
    for objet in objets:
        if objet.nom == nom:
            return objet
    raise KeyError(f"Introuvable dans cet univers : {genre} « {nom} ».")


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
            domaines=tuple(_domaine_depuis_dict(d) for d in donnees.get("domaines", [])),
            systemes=tuple(systeme_depuis_dict(s) for s in donnees.get("implants", {}).get("systemes", [])),
            implants=tuple(implant_depuis_dict(i, _arme_depuis_dict, _armure_depuis_dict)
                           for i in donnees.get("implants", {}).get("implants", [])),
            vehicules=tuple(vehicule_depuis_dict(v) for v in donnees.get("vehicules", [])),
        )
    except (KeyError, ValueError, TypeError) as erreur:
        raise UniversInvalide([f"Fichier d'univers mal formé : {erreur}"]) from erreur
    erreurs = univers.verifier(genere)
    if erreurs:
        raise UniversInvalide(erreurs)
    return univers


def _qualite(d: dict) -> dict:
    """Ce que les armes et les armures ont en commun : qualité, modifications, fabricant, défaut."""
    return dict(qualite=Qualite(d.get("qualite", "d'origine")),
                modifications=tuple(modification_depuis_dict(m) for m in d.get("modifications", [])),
                fabricant=d.get("fabricant"), defaut=d.get("defaut"))


def _arme_depuis_dict(d: dict) -> Arme:
    munitions = d.get("munitions")
    return Arme(
        nom=d["nom"],
        competence=d["competence"],
        degats=d["degats"],
        portee=Portee(d["portee"]),
        munitions=Munitions(munitions["capacite"], Recharge(munitions["recharge"])) if munitions else None,
        proprietes=frozenset(Propriete(p) for p in d.get("proprietes", [])),
        categorie=d.get("categorie", ""),
        zone=d.get("zone"), effets=frozenset(d.get("effets", [])), usage_unique=d.get("usage_unique", False),
        posee=d.get("posee", False), montee=d.get("montee", False), electronique=d.get("electronique", False),
        **_qualite(d),
    )


def _armure_depuis_dict(d: dict) -> Armure:
    return Armure(
        nom=d["nom"],
        protection=d["protection"],
        malus=dict(d.get("malus", {})),
        proprietes=frozenset(d.get("proprietes", [])),
        categorie=d.get("categorie", "armures"),
        **_qualite(d),
    )


def _sort_depuis_dict(d: dict, domaine: str, improvisation: bool) -> Sort:
    propriete = d.get("propriete")
    return Sort(d["nom"], Effet(d["effet"]), Puissance(d["puissance"]),
                ProprieteSort(propriete) if propriete else None, d.get("description", ""), improvisation, domaine)


def _domaine_depuis_dict(d: dict) -> Domaine:
    return Domaine(
        nom=d["nom"],
        effets=frozenset(Effet(e) for e in d["effets"]),
        sorts=tuple(_sort_depuis_dict(s, d["nom"], False) for s in d.get("sorts", [])),
        improvisations=tuple(_sort_depuis_dict(s, d["nom"], True) for s in d.get("improvisations", [])),
        description=d.get("description", ""),
    )


def _sort_vers_dict(sort: Sort) -> dict:
    d = {"nom": sort.nom, "effet": sort.effet.value, "puissance": sort.puissance.value}
    if sort.propriete:
        d["propriete"] = sort.propriete.value
    if sort.description:
        d["description"] = sort.description
    return d


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
        "domaines": [
            {"nom": d.nom, "description": d.description, "effets": sorted(e.value for e in d.effets),
             "sorts": [_sort_vers_dict(s) for s in d.sorts],
             "improvisations": [_sort_vers_dict(s) for s in d.improvisations]}
            for d in univers.domaines
        ],
    } | ({"implants": {"systemes": [_systeme_vers_dict(s) for s in univers.systemes],
                       "implants": [_implant_vers_dict(i) for i in univers.implants]}} if univers.implants else {}) \
      | ({"vehicules": [vehicule_vers_dict(v) for v in univers.vehicules]} if univers.vehicules else {})


def _systeme_vers_dict(s: Systeme) -> dict:
    return {k: v for k, v in {"nom": s.nom, "emplacements": s.emplacements, "options": s.options,
                              "fondation": s.fondation, "requiert": s.requiert, "par": s.par}.items()
            if v is not None or k == "emplacements"}


def _implant_vers_dict(i: Implant) -> dict:
    d = {"nom": i.nom, "systeme": i.systeme, "effet": i.effet, "gamme": i.gamme, "fondation": i.fondation,
         "electronique": i.electronique}
    if i.competence:
        d["competence"] = i.competence
    if i.bonus:
        d["bonus"] = i.bonus
    if i.arme:
        d["arme"] = {k: v for k, v in _arme_vers_dict(i.arme).items() if k != "nom"}
    if i.armure:
        d["armure"] = {k: v for k, v in _armure_vers_dict(i.armure).items() if k != "nom"}
    if i.description:
        d["description"] = i.description
    return d


def _arme_vers_dict(arme: Arme) -> dict:
    return {
        "nom": arme.nom,
        "competence": arme.competence,
        "degats": arme.degats,
        "portee": arme.portee.value,
        "munitions": {"capacite": arme.munitions.capacite, "recharge": arme.munitions.recharge.value}
        if arme.munitions else None,
        "proprietes": sorted(p.value for p in arme.proprietes),
        "categorie": arme.categorie,
    } | {k: v for k, v in {"zone": arme.zone, "effets": sorted(arme.effets), "usage_unique": arme.usage_unique,
                           "posee": arme.posee, "montee": arme.montee, "electronique": arme.electronique}.items()
         if v} | _qualite_vers_dict(arme)


def _qualite_vers_dict(objet) -> dict:
    d = {"qualite": objet.qualite.value}
    if objet.modifications:
        d["modifications"] = [modification_vers_dict(m) for m in objet.modifications]
    if objet.fabricant:
        d["fabricant"] = objet.fabricant
    if objet.defaut:
        d["defaut"] = objet.defaut
    return d


def _armure_vers_dict(armure: Armure) -> dict:
    return {
        "nom": armure.nom,
        "protection": armure.protection,
        "malus": dict(armure.malus),
        "proprietes": sorted(armure.proprietes),
        "categorie": armure.categorie,
    } | _qualite_vers_dict(armure)


def charger_univers(chemin: str | Path, genere: bool = False) -> Univers:
    """Lit et vérifie un univers depuis un fichier JSON."""
    with open(chemin, encoding="utf-8") as fichier:
        return univers_depuis_dict(json.load(fichier), genere)
