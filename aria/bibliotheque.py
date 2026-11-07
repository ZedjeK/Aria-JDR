"""La bibliothèque : tout ce qui peut exister dans une partie, rangé une seule fois (REGLES.md 1.3).

Chaque entrée porte ses étiquettes : ses genres (un par un ou par raccourci), sa condition de magie,
et si elle est électronique. Une campagne ne crée rien de zéro : le filtre ne garde que ce qui a droit
au genre et à la magie choisis, et le générateur pioche dedans.

Les données vivent dans le dossier `bibliotheque/` (un fichier JSON par catégorie). Ce module les
charge et les vérifie avec les règles du moteur : une entrée fausse est refusée au chargement.
"""

import json
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

from aria import chemins
from aria.equipement import verifier_arme, verifier_armure
from aria.magie import verifier_domaines
from aria.personnage import COMPETENCES_SOCLE, MAGIE, NB_COMPETENCES_PARCOURS

DOSSIER = chemins.RESSOURCES / "bibliotheque"
GENRES = ("Fantasy", "Dark fantasy", "Horreur", "Contemporain", "Militaire", "Science-fiction", "Cyberpunk", "Post-apo")
RACCOURCIS = {
    "médiéval": {"Fantasy", "Dark fantasy"},
    "moderne": {"Contemporain", "Horreur", "Militaire", "Cyberpunk", "Post-apo"},
    "futuriste": {"Cyberpunk", "Science-fiction"},
    "tous": set(GENRES),
}
QUALITES = ("usé", "d'origine", "personnalisé", "unique")
EMPLACEMENTS = {"usé": 0, "d'origine": 1, "personnalisé": 2, "unique": 3}
GAMMES = {"standard": 0, "avancée": 5, "militaire": 10}  # le bonus de compétence de chaque gamme
EFFETS_IMPLANT = ("arme", "armure", "bonus", "utilitaire", "esthétique", "médical")
POUR = ("armes à distance", "armes de mêlée", "armures", "implants", "objets électroniques", "véhicules", "montures")
EFFETS_MODIFICATION = {
    "armes à distance": {"précision", "puissance", "propriété", "munitions", "utilitaire"},
    "armes de mêlée": {"précision", "puissance", "propriété", "utilitaire"},
    "armures": {"puissance", "confort", "utilitaire"},
    "implants": {"puissance", "utilitaire"},
    "objets électroniques": {"utilitaire"},
    "véhicules": {"moteur", "châssis", "renfort", "blindage", "propriété", "support d'arme", "nitro", "utilitaire",
                  "défensif"},
    "montures": {"moteur", "châssis", "renfort", "blindage", "propriété"},
}
PLAFONDS = {"précision": 10, "puissance_arme": 2, "puissance_armure": 2, "puissance_implant": 10, "propriété": 1}
VITESSES = ("lente", "moyenne", "rapide", "très rapide")
MANIABILITES = (-10, 0, 10)
TYPES_VEHICULE = ("terrestre", "aérien", "nautique", "spatial")
# Les bornes des véhicules (REGLES.md 12.1 et 12.7) : structure, blindage, points d'emport
GABARITS = {
    "léger": ((10, 20), (0, 2), 0),
    "moyen": ((20, 40), (2, 4), 1),
    "lourd": ((40, 60), (4, 8), 2),
    "militaire": ((60, 100), (8, 12), 3),
    "drone": ((5, 10), (0, 1), 1),
}
CATEGORIES_IMPLANT = {
    "Visage et yeux": "implants optiques", "Cortex frontal": "implants neuro", "Système nerveux": "implants neuro",
    "Peau": "implants de peau", "Organes internes": "organes internes",
}
DECKS = {"Deck neural", "Deck militaire"}
CHAMPS_BIBLIOTHEQUE = {"genres"}


class BibliothequeInvalide(ValueError):
    """La bibliothèque ne respecte pas les règles. `erreurs` liste tous les problèmes trouvés."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("Bibliothèque invalide :\n- " + "\n- ".join(erreurs))


def genres_de(etiquettes: list[str]) -> set[str]:
    """Les genres d'une entrée, raccourcis dépliés : « moderne » vaut cinq genres."""
    genres = set()
    for etiquette in etiquettes:
        genres |= RACCOURCIS.get(etiquette, {etiquette})
    return genres


def categorie_implant(implant: dict) -> str:
    if implant["nom"] in DECKS:
        return "decks"
    return CATEGORIES_IMPLANT.get(implant["systeme"], "cybermembres")


def _arme_moteur(entree: dict):
    """L'arme telle que le moteur la connaît, sans les étiquettes de la bibliothèque."""
    from aria.univers import _arme_depuis_dict  # univers importe la magie, qui importe le combat
    return _arme_depuis_dict({k: v for k, v in entree.items() if k not in CHAMPS_BIBLIOTHEQUE})


def _armure_moteur(entree: dict):
    from aria.univers import _armure_depuis_dict
    return _armure_depuis_dict({k: v for k, v in entree.items() if k not in CHAMPS_BIBLIOTHEQUE})


@dataclass
class Bibliotheque:
    genres: dict = field(default_factory=dict)
    parcours: list = field(default_factory=list)
    armes: list = field(default_factory=list)
    armures: list = field(default_factory=list)
    modifications: list = field(default_factory=list)
    fabricants: list = field(default_factory=list)
    systemes: list = field(default_factory=list)
    implants: list = field(default_factory=list)
    vehicules: list = field(default_factory=list)
    modeles: list = field(default_factory=list)
    domaines: list = field(default_factory=list)

    # --- Recherche ---

    def _par_nom(self, liste: list, nom: str, quoi: str) -> dict:
        for entree in liste:
            if entree["nom"] == nom:
                return entree
        raise KeyError(f"Introuvable dans la bibliothèque : {quoi} « {nom} ».")

    def arme(self, nom: str) -> dict:
        return self._par_nom(self.armes, nom, "arme")

    def armure(self, nom: str) -> dict:
        return self._par_nom(self.armures, nom, "armure")

    def modification(self, nom: str) -> dict:
        return self._par_nom(self.modifications, nom, "modification")

    def fabricant(self, nom: str) -> dict:
        return self._par_nom(self.fabricants, nom, "fabricant")

    def implant(self, nom: str) -> dict:
        return self._par_nom(self.implants, nom, "implant")

    def vehicule(self, nom: str) -> dict:
        return self._par_nom(self.vehicules, nom, "véhicule")

    def competences_du_genre(self, genre: str) -> set[str]:
        return set(COMPETENCES_SOCLE) | {c["nom"] for c in self.genres[genre]["competences_thematiques"]}

    def categories(self) -> set[str]:
        """Toutes les catégories d'objets, celles qu'un fabricant peut revendiquer."""
        return ({e["categorie"] for e in self.armes + self.armures + self.vehicules}
                | {categorie_implant(i) for i in self.implants})

    # --- Le filtre de campagne (REGLES.md 1.3) ---

    def filtrer(self, genre: str, magie: bool) -> "Bibliotheque":
        """Ne garde que ce qui a droit au genre et à la magie choisis."""
        if genre not in GENRES:
            raise KeyError(f"Genre inconnu : « {genre} ». Genres : {', '.join(GENRES)}.")

        def permis(entree: dict) -> bool:
            return genre in genres_de(entree["genres"])

        implants = genre if self.genres[genre]["implants"] else None
        return replace(
            self,
            genres={genre: self.genres[genre]},
            parcours=[p for p in self.parcours if p["genre"] == genre and (magie or not p["magie"])],
            armes=[e for e in self.armes if permis(e)],
            armures=[e for e in self.armures if permis(e)],
            modifications=[e for e in self.modifications if permis(e)],
            fabricants=[e for e in self.fabricants if permis(e)],
            systemes=list(self.systemes) if implants else [],
            implants=[e for e in self.implants if permis(e)] if implants else [],
            vehicules=[e for e in self.vehicules if permis(e)],
            modeles=[e for e in self.modeles if permis(e)],
            domaines=[e for e in self.domaines if permis(e)] if magie else [],
        )

    # --- Vérifications ---

    def verifier(self) -> list[str]:
        """Liste tous les problèmes de la bibliothèque (vide si elle est valide)."""
        erreurs = []
        for f in fields(self):
            liste = getattr(self, f.name)
            if not isinstance(liste, list):
                continue
            # Un nom est unique dans sa liste ; un parcours, dans son genre (le Journaliste existe en Horreur et en Contemporain)
            noms = [(e.get("genre", ""), e["nom"]) if f.name == "parcours" else e["nom"] for e in liste]
            for nom in {n for n in noms if noms.count(n) > 1}:
                erreurs.append(f"{f.name} : « {nom if isinstance(nom, str) else nom[1]} » existe deux fois.")
            for entree in liste:
                if "genres" in entree:
                    inconnus = [g for g in entree["genres"] if g not in GENRES and g not in RACCOURCIS]
                    if inconnus:
                        erreurs.append(f"{entree['nom']} : genre inconnu {inconnus}.")
        erreurs += self._verifier_genres()
        erreurs += self._verifier_armes() + self._verifier_armures()
        erreurs += self._verifier_modifications() + self._verifier_fabricants()
        erreurs += self._verifier_implants() + self._verifier_vehicules()
        erreurs += self._verifier_modeles() + self._verifier_parcours()
        if self.domaines:
            from aria.univers import _domaine_depuis_dict
            erreurs += verifier_domaines(tuple(_domaine_depuis_dict(d) for d in self.domaines))
        return erreurs

    def _verifier_genres(self) -> list[str]:
        erreurs = [f"Genre manquant : {g}." for g in GENRES if g not in self.genres]
        for genre, fiche in self.genres.items():
            for socle in fiche["habillage"]:
                if socle not in COMPETENCES_SOCLE:
                    erreurs.append(f"{genre} : habillage d'une compétence qui n'est pas du socle « {socle} ».")
            if fiche["magie"]["statut"] not in ("activée", "désactivée", "option"):
                erreurs.append(f"{genre} : statut de magie inconnu.")
            for thematique in fiche["competences_thematiques"]:
                if not 0 <= thematique["base"] <= 10:
                    erreurs.append(f"{genre} : « {thematique['nom']} » a une base de 0 à 10.")
        return erreurs

    def _verifier_armes(self) -> list[str]:
        erreurs = []
        for entree in self.armes:
            try:
                erreurs += [f"{entree['nom']} : {e}" for e in verifier_arme(_arme_moteur(entree), generee=True)]
            except (KeyError, ValueError, TypeError) as erreur:
                erreurs.append(f"{entree['nom']} : fiche mal formée ({erreur}).")
        return erreurs

    def _verifier_armures(self) -> list[str]:
        erreurs = []
        for entree in self.armures:
            try:
                erreurs += [f"{entree['nom']} : {e}" for e in verifier_armure(_armure_moteur(entree), generee=True)]
            except (KeyError, ValueError, TypeError) as erreur:
                erreurs.append(f"{entree['nom']} : fiche mal formée ({erreur}).")
        return erreurs

    def _verifier_modifications(self) -> list[str]:
        erreurs = []
        for m in self.modifications:
            if m["pour"] not in POUR:
                erreurs.append(f"{m['nom']} : « pour » inconnu « {m['pour']} ».")
            elif m["effet"] not in EFFETS_MODIFICATION[m["pour"]]:
                erreurs.append(f"{m['nom']} : l'effet « {m['effet']} » ne va pas sur des {m['pour']}.")
            if m["effet"] in ("précision", "confort") and m.get("valeur") != 5:
                erreurs.append(f"{m['nom']} : une modification de {m['effet']} vaut 5.")
            if m["effet"] == "puissance" and m.get("valeur") not in (1, 5):
                erreurs.append(f"{m['nom']} : une modification de puissance vaut +1 (+5 pour un implant).")
            if m["effet"] == "propriété" and not m.get("propriete"):
                erreurs.append(f"{m['nom']} : quelle propriété ?")
        return erreurs

    def _verifier_fabricants(self) -> list[str]:
        erreurs, categories = [], self.categories()
        noms_mods = {m["nom"] for m in self.modifications}
        for f in self.fabricants:
            for categorie, modification in f["categories"].items():
                if categorie not in categories:
                    erreurs.append(f"{f['nom']} : catégorie inconnue « {categorie} ».")
                if modification is not None and modification not in noms_mods:
                    erreurs.append(f"{f['nom']} : modification d'usine inconnue « {modification} ».")
            if not f.get("reputation"):
                erreurs.append(f"{f['nom']} : il lui faut une réputation.")
        return erreurs

    def _verifier_implants(self) -> list[str]:
        from aria.implants import implant_depuis_dict, systeme_depuis_dict, verifier_catalogue
        from aria.univers import _arme_depuis_dict, _armure_depuis_dict
        competences = self.competences_du_genre("Cyberpunk") if "Cyberpunk" in self.genres else set(COMPETENCES_SOCLE)
        try:
            systemes = tuple(systeme_depuis_dict(s) for s in self.systemes)
            implants = tuple(implant_depuis_dict(i, _arme_depuis_dict, _armure_depuis_dict) for i in self.implants)
        except (KeyError, ValueError, TypeError) as erreur:
            return [f"Implants mal formés ({erreur})."]
        return verifier_catalogue(systemes, implants, competences)

    def _verifier_vehicules(self) -> list[str]:
        erreurs = []
        armes = {a["nom"]: a for a in self.armes}
        mods = {m["nom"]: m for m in self.modifications}
        noms = {v["nom"] for v in self.vehicules}
        for v in self.vehicules:
            nom = v["nom"]
            if v["gabarit"] not in GABARITS:
                erreurs.append(f"{nom} : gabarit inconnu « {v['gabarit']} ».")
                continue
            (s_min, s_max), (b_min, b_max), emports = GABARITS[v["gabarit"]]
            if not s_min <= v["structure"] <= s_max:
                erreurs.append(f"{nom} : en gabarit {v['gabarit']}, la structure va de {s_min} à {s_max}.")
            if not b_min <= v["blindage"] <= b_max:
                erreurs.append(f"{nom} : en gabarit {v['gabarit']}, le blindage va de {b_min} à {b_max}.")
            if v["vitesse"] not in VITESSES:
                erreurs.append(f"{nom} : vitesse inconnue « {v['vitesse']} ».")
            if v["maniabilite"] not in MANIABILITES:
                erreurs.append(f"{nom} : la maniabilité vaut −10, 0 ou +10.")
            if v["type"] not in TYPES_VEHICULE:
                erreurs.append(f"{nom} : type inconnu « {v['type']} ».")
            if len(v["armes_montees"]) > emports:
                erreurs.append(f"{nom} : {len(v['armes_montees'])} armes montées pour {emports} points d'emport.")
            for monte in v["armes_montees"]:
                arme = armes.get(monte["arme"])
                if arme is None:
                    erreurs.append(f"{nom} : arme montée inconnue « {monte['arme']} ».")
                elif (arme.get("zone") or arme.get("montee")) and monte["tourelle"] != "lourde":
                    erreurs.append(f"{nom} : « {monte['arme']} » demande une tourelle lourde.")
                elif monte["tourelle"] == "lourde" and v["gabarit"] in ("léger", "moyen", "drone"):
                    erreurs.append(f"{nom} : pas de tourelle lourde en gabarit {v['gabarit']}.")
            for systeme in v["systemes"]:
                if mods.get(systeme, {}).get("effet") != "défensif":
                    erreurs.append(f"{nom} : système défensif inconnu « {systeme} ».")
            if "drones" in v and v["drones"]["modele"] not in noms:
                erreurs.append(f"{nom} : drone inconnu « {v['drones']['modele']} ».")
        return erreurs

    def _verifier_modeles(self) -> list[str]:
        erreurs = []
        for m in self.modeles:
            nom = m["nom"]
            try:
                base = {"arme": self.arme, "armure": self.armure, "véhicule": self.vehicule}[m["type"]](m["base"])
            except KeyError as erreur:
                erreurs.append(f"{nom} : {erreur}")
                continue
            if m["qualite"] not in QUALITES:
                erreurs.append(f"{nom} : qualité inconnue « {m['qualite']} ».")
                continue
            if len(m["modifications"]) > EMPLACEMENTS[m["qualite"]]:
                erreurs.append(f"{nom} : trop de modifications pour un objet {m['qualite']}.")
            if len(set(m["modifications"])) != len(m["modifications"]):
                erreurs.append(f"{nom} : une modification ne se pose qu'une fois.")
            try:
                mods = [self.modification(n) for n in m["modifications"]]
            except KeyError as erreur:
                erreurs.append(f"{nom} : {erreur}")
                continue
            if m.get("fabricant"):
                try:
                    fabricant = self.fabricant(m["fabricant"])
                except KeyError as erreur:
                    erreurs.append(f"{nom} : {erreur}")
                    continue
                if base["categorie"] not in fabricant["categories"]:
                    erreurs.append(f"{nom} : {fabricant['nom']} ne fabrique pas de {base['categorie']}.")
                else:
                    usine = fabricant["categories"][base["categorie"]]
                    if usine and usine not in m["modifications"]:
                        erreurs.append(f"{nom} : il manque la modification d'usine « {usine} ».")
            if m["type"] in ("arme", "armure"):
                # Le moteur vérifie l'objet monté, avec sa qualité et ses modifications (7.5)
                objet = dict(base, qualite=m["qualite"], fabricant=m.get("fabricant"),
                             modifications=[{k: v for k, v in x.items() if k not in ("pour", "genres", "electronique")}
                                            for x in mods])
                verifier = verifier_arme if m["type"] == "arme" else verifier_armure
                monter = _arme_moteur if m["type"] == "arme" else _armure_moteur
                erreurs += [f"{nom} : {e}" for e in verifier(monter(objet), generee=True)]
            precision = sum(x.get("valeur", 0) for x in mods if x["effet"] == "précision")
            puissance = sum(x.get("valeur", 0) for x in mods if x["effet"] == "puissance")
            proprietes = sum(1 for x in mods if x["effet"] == "propriété")
            if precision > PLAFONDS["précision"] or puissance > 2 or proprietes > PLAFONDS["propriété"]:
                erreurs.append(f"{nom} : les modifications dépassent le plafond (7.5).")
        return erreurs

    def _verifier_parcours(self) -> list[str]:
        erreurs = []
        for p in self.parcours:
            nom = f"{p['nom']} ({p['genre']})"
            if p["genre"] not in GENRES:
                erreurs.append(f"{nom} : genre inconnu.")
                continue
            competences = p["competences"]
            if len(competences) != NB_COMPETENCES_PARCOURS or len(set(competences)) != len(competences):
                erreurs.append(f"{nom} : {NB_COMPETENCES_PARCOURS} compétences distinctes attendues.")
            permises = self.competences_du_genre(p["genre"])
            for c in competences:
                if c not in permises:
                    erreurs.append(f"{nom} : compétence inconnue dans ce genre « {c} ».")
            if p["magie"]:
                if MAGIE not in competences:
                    erreurs.append(f"{nom} : un parcours de magie contient la Magie.")
                if self.genres[p["genre"]]["magie"]["statut"] == "désactivée":
                    erreurs.append(f"{nom} : parcours de magie dans un genre sans magie.")
            elif MAGIE in competences:
                erreurs.append(f"{nom} : la Magie n'est que dans un parcours marqué magie.")
            if not p.get("description", "").strip():
                erreurs.append(f"{nom} : il lui faut une description.")
            if "equipement" in p:
                erreurs += self._verifier_equipement(nom, p["genre"], p["equipement"])
        return erreurs

    def _verifier_equipement(self, nom: str, genre: str, equipement: dict) -> list[str]:
        """Les listes de choix de l'équipement de départ (REGLES.md 5)."""
        erreurs = []
        cases = [("armes", self.arme), ("armures", self.armure), ("implants", self.implant), ("vehicules", self.vehicule)]
        for case, chercher in cases:
            options = equipement.get(case, [])
            if case != "vehicules" and not 1 <= len(options) <= 3 or len(options) > 3:
                erreurs.append(f"{nom} : de 1 à 3 options pour « {case} ».")
            for option in options:
                if option is None:
                    continue
                try:
                    objet = chercher(option)
                except KeyError as erreur:
                    erreurs.append(f"{nom} : {erreur}")
                    continue
                if genre not in genres_de(objet["genres"]):
                    erreurs.append(f"{nom} : « {option} » n'existe pas dans ce genre.")
                if case == "armures" and objet["protection"] > 3:
                    erreurs.append(f"{nom} : « {option} » protège plus de 3 : interdit à la création.")
                if case == "implants" and objet["gamme"] != "standard":
                    erreurs.append(f"{nom} : « {option} » n'est pas de gamme standard.")
                if case == "vehicules" and objet["gabarit"] not in ("léger", "moyen"):
                    erreurs.append(f"{nom} : « {option} » est trop lourd pour un départ.")
        if not 3 <= len(equipement.get("objets", [])) <= 4:
            erreurs.append(f"{nom} : de 3 à 4 objets racontés.")
        return erreurs


def charger(dossier: Path = DOSSIER) -> Bibliotheque:
    """Charge et vérifie la bibliothèque. Lève BibliothequeInvalide si une entrée enfreint les règles."""
    def lire(nom: str):
        return json.loads((dossier / nom).read_text(encoding="utf-8"))

    implants = lire("implants.json")
    bibliotheque = Bibliotheque(
        genres=lire("genres.json"), parcours=lire("parcours.json"), armes=lire("armes.json"),
        armures=lire("armures.json"), modifications=lire("modifications.json"), fabricants=lire("fabricants.json"),
        systemes=implants["systemes"], implants=implants["implants"], vehicules=lire("vehicules.json"),
        modeles=lire("modeles.json"), domaines=lire("domaines.json"),
    )
    erreurs = bibliotheque.verifier()
    if erreurs:
        raise BibliothequeInvalide(erreurs)
    return bibliotheque
