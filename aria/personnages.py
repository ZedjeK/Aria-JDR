"""Les personnages prédéfinis : préparés à l'avance par le joueur, hors campagne, pour un genre.

Un personnage prédéfini est créé avec les métiers et l'équipement de base du genre, tels que la bibliothèque
les donne. Il est rangé dans .Aria-JDR\\personnages, un fichier par personnage. Quand une campagne de ce genre
commence avec lui, le générateur garde son métier dans l'univers, et son équipement prend les noms que le
cadre lui a donnés. Kaito, le Netrunner de la démo, est livré avec le jeu.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from aria import banc, chemins
from aria.bibliotheque import charger
from aria.campagne import nom_valide
from aria.creation import Brouillon, EtapeInvalide, proposer_chiffres, proposer_domaines, proposer_equipement
from aria.generateur import choix_par_defaut, generer
from aria.personnage import DEBUTANT, Caracteristique
from aria.univers import Univers, univers_depuis_dict

CASES = ("arme", "armure", "implant", "vehicule")


def dossier() -> Path:
    """Lu à chaque appel : les tests déplacent chemins.DONNEES."""
    return chemins.DONNEES / "personnages"


@dataclass
class Predefini:
    genre: str
    parcours: str  # son nom dans la bibliothèque
    fiche: dict  # caracteristiques, points_parcours, points_personnels, domaines, equipement, roleplay
    fichier: Path | None = None  # None : livré avec le jeu, on ne le supprime pas

    @property
    def nom(self) -> str:
        return self.fiche["roleplay"]["nom"]

    @property
    def cran(self) -> str:
        return self.fiche.get("cran", DEBUTANT)

    def titre(self) -> str:
        sexe = self.fiche["roleplay"].get("sexe")
        return (f"{self.nom} — {sexe + ', ' if sexe else ''}{self.parcours} ({self.genre})"
                + ("" if self.cran == DEBUTANT else f", {self.cran}")
                + ("" if self.fichier else " · livré avec le jeu"))


KAITO = Predefini("Cyberpunk", "Netrunner", {
    "caracteristiques": {c.value: v for c, v in banc.FICHE_KAITO["caracteristiques"].items()},
    "points_parcours": dict(banc.FICHE_KAITO["points_parcours"]),
    "points_personnels": dict(banc.FICHE_KAITO["points_personnels"]),
    "domaines": [],
    "equipement": {cle: banc.EQUIPEMENT_KAITO.get(cle) for cle in CASES} | {"objets": banc.EQUIPEMENT_KAITO["objets"]},
    "roleplay": {cle: banc.FICHE_KAITO[cle] for cle in ("nom", "motivation", "lien", "defaut")} | {"sexe": "homme"},
})


def univers_de_base(genre: str) -> Univers:
    """L'univers du genre tel que la bibliothèque le donne, sans cadre : celui où l'on prépare un personnage."""
    bibliotheque = charger()
    return univers_depuis_dict(generer(bibliotheque, choix_par_defaut(bibliotheque, genre)))


def enregistrer(brouillon: Brouillon, genre: str) -> Predefini:
    """Range un personnage créé dans l'univers de base du genre. Deux personnages du même nom ne s'écrasent pas."""
    b = brouillon
    predefini = Predefini(genre, b.parcours, {
        "caracteristiques": {c.value: v for c, v in b.caracteristiques.items()},
        "points_parcours": dict(b.points_parcours), "points_personnels": dict(b.points_personnels),
        "domaines": list(b.domaines), "equipement": dict(b.equipement), "roleplay": dict(b.roleplay),
        "cran": b.cran})
    dossier().mkdir(parents=True, exist_ok=True)
    base = nom_valide(b.roleplay["nom"]) or "personnage"
    numero, chemin = 1, dossier() / f"{base}.json"
    while chemin.exists():
        numero += 1
        chemin = dossier() / f"{base}-{numero}.json"
    chemin.write_text(json.dumps({"genre": genre, "parcours": b.parcours, **predefini.fiche}, ensure_ascii=False,
                                 indent=2), encoding="utf-8")
    predefini.fichier = chemin
    return predefini


def garder(perso, univers: Univers, cran: str, hasard: random.Random | None = None) -> Predefini | None:
    """Range parmi les personnages prêts celui d'une campagne terminée, à l'expérience donnée (REGLES.md 14.11) :
    le même métier, le même nom, la même personnalité, refait avec les chiffres de ce cran. None si son métier
    n'existe pas dans l'univers de base du genre (un métier propre au cadre)."""
    base = univers_de_base(univers.genre)
    parcours = univers.origines.get(perso.parcours, perso.parcours)
    if parcours not in base.parcours:
        return None
    b = proposer_chiffres(Brouillon(base, cran=cran), hasard or random.Random(), parcours)
    roleplay = {"nom": perso.nom, "motivation": perso.motivation, "lien": perso.lien, "defaut": perso.defaut}
    b.fixer("roleplay", roleplay | ({"allure": perso.allure} if perso.allure else {})
            | ({"sexe": perso.sexe} if perso.sexe else {}))
    return enregistrer(b, univers.genre)


def lister(genre: str | None = None) -> list[Predefini]:
    """Kaito, puis les personnages du joueur ; ceux d'un seul genre si on le donne. Un fichier abîmé est ignoré."""
    trouves = [KAITO]
    for chemin in sorted(dossier().glob("*.json")) if dossier().is_dir() else []:
        try:
            d = json.loads(chemin.read_text(encoding="utf-8"))
            trouves.append(Predefini(d.pop("genre"), d.pop("parcours"), d, chemin))
            trouves[-1].nom  # la fiche a bien un nom
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            trouves = [p for p in trouves if p.fichier != chemin]
    return [p for p in trouves if genre is None or p.genre == genre]


def supprimer(predefini: Predefini):
    if predefini.fichier is not None:
        predefini.fichier.unlink(missing_ok=True)


def brouillon_dans(univers: Univers, predefini: Predefini,
                   hasard: random.Random | None = None) -> tuple[Brouillon, list[str]]:
    """Le personnage prédéfini, posé dans l'univers d'une campagne. Son métier et son équipement prennent les
    noms que le cadre leur a donnés ; ce que le cadre a retiré est reproposé, et les notes le disent.
    Lève EtapeInvalide s'il ne peut pas y vivre (métier absent, magie sans magie…)."""
    f, local, notes, hasard = predefini.fiche, univers.nom_local, [], hasard or random.Random()
    b = Brouillon(univers, cran=predefini.cran)
    b.fixer("parcours", local(predefini.parcours))
    b.fixer("caracteristiques", {Caracteristique(c): v for c, v in f["caracteristiques"].items()})
    b.fixer("points_parcours", dict(f["points_parcours"]))
    b.fixer("points_personnels", dict(f["points_personnels"]))
    try:
        b.fixer("domaines", list(f.get("domaines", [])))
    except EtapeInvalide:
        b.fixer("domaines", proposer_domaines(b, hasard))
        notes.append("Ses domaines de magie n'existent pas ici : " + (", ".join(b.domaines) or "aucun") + ".")
    equipement = dict(f.get("equipement", {}))
    for case in CASES:
        if equipement.get(case):
            equipement[case] = local(equipement[case])
    if equipement.get("pieces"):
        equipement["pieces"] = [local(p) for p in equipement["pieces"]]
    try:
        b.fixer("equipement", equipement)
    except EtapeInvalide:
        b.fixer("equipement", proposer_equipement(b, hasard))
        notes.append("Son équipement ne colle pas à ce cadre : il a été reproposé dans les listes de son métier.")
    b.fixer("roleplay", dict(f["roleplay"]))
    b.finaliser()  # le moteur refait toutes les vérifications
    return b, notes
