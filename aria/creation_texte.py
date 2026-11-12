"""La création de personnage guidée, en texte (en attendant l'interface graphique).

À chaque étape, le code propose ; le joueur garde (Entrée), saisit lui-même, ou relance. « tout » au
début : tout est proposé d'un coup (les chiffres par le code, la personnalité par le LLM), puis on
relit le récapitulatif.
"""

import random

from aria.creation import (
    SEXES,
    Brouillon,
    EtapeInvalide,
    proposer_caracteristiques,
    proposer_domaines,
    proposer_equipement,
    proposer_personnalite,
    proposer_points_parcours,
    proposer_points_personnels,
    tout_proposer,
)
from aria.personnage import Caracteristique, Personnage
from aria.univers import Depart, Univers

ABREVIATIONS = {"for": Caracteristique.FORCE, "con": Caracteristique.CONSTITUTION, "dex": Caracteristique.DEXTERITE,
                "int": Caracteristique.INTELLIGENCE, "vol": Caracteristique.VOLONTE, "pre": Caracteristique.PRESENCE,
                "pré": Caracteristique.PRESENCE}


class Abandon(Exception):
    """Le joueur a quitté la création."""


def _paires(texte: str) -> list[tuple[str, int]]:
    """« Piratage 70, Esquive 15 » → [("Piratage", 70), ("Esquive", 15)]."""
    paires = []
    for morceau in texte.split(","):
        mots = morceau.strip().rsplit(" ", 1)
        if len(mots) != 2 or not mots[1].lstrip("-").isdigit():
            raise EtapeInvalide([f"Je ne comprends pas « {morceau.strip()} » : écris « Nom valeur »."])
        paires.append((mots[0].strip(), int(mots[1])))
    return paires


def lire_caracteristiques(texte: str) -> dict[Caracteristique, int]:
    """« for 50, con 45, dex 60, int 65, vol 40, pré 40 »."""
    valeurs = {}
    for nom, valeur in _paires(texte):
        cle = ABREVIATIONS.get(nom.lower()[:3])
        if cle is None:
            raise EtapeInvalide([f"Caractéristique inconnue : « {nom} » (for, con, dex, int, vol, pré)."])
        valeurs[cle] = valeur
    return valeurs


def lire_points(univers: Univers, texte: str) -> dict[str, int]:
    """Les compétences sous leur nom dans l'univers (« Piratage ») ou dans le socle (« Technologie »)."""
    inverse = {c.lower(): c for c in univers.competences_disponibles()}
    inverse.update({univers.nom_affiche(c).lower(): c for c in univers.competences_disponibles()})
    points = {}
    for nom, valeur in _paires(texte):
        socle = inverse.get(nom.lower())
        if socle is None:
            raise EtapeInvalide([f"Compétence inconnue dans cet univers : « {nom} »."])
        points[socle] = points.get(socle, 0) + valeur
    return points


def resume(b: Brouillon) -> list[str]:
    u = b.univers
    lignes = [f"Parcours : {b.parcours}"]
    if b.caracteristiques:
        lignes.append("Caractéristiques : " + ", ".join(f"{c.libelle} {v}" for c, v in b.caracteristiques.items()))
    if b.points_parcours or b.points_personnels:
        competences = sorted(set(b.points_parcours) | set(b.points_personnels), key=lambda c: -b.valeur(c))
        lignes.append("Compétences : " + ", ".join(f"{u.nom_affiche(c)} {b.valeur(c)}" for c in competences))
    if b.domaines:
        lignes.append("Domaines : " + ", ".join(b.domaines))
    e = b.equipement
    if e:
        objets = [str(e[c]) for c in ("arme", "armure", "implant", "vehicule") if e.get(c)] + list(e.get("objets", []))
        lignes.append("Équipement : " + (", ".join(objets) or "rien"))
    r = b.roleplay
    if r:
        lignes += [f"Nom : {r['nom']}" + (f" ({r['sexe']})" if r.get("sexe") else ""), f"Motivation : {r['motivation']}", f"Lien : {r['lien']}",
                   f"Défaut : {r['defaut']}"] + ([f"Allure : {r['allure']}"] if r.get("allure") else [])
    return lignes + [f"⚠ {a}" for a in b.avertissements()]


class Guide:
    """Le dialogue de création ; `entree` et `sortie` comme input et print, pour les tests."""

    def __init__(self, univers: Univers, entree=input, sortie=print, serveur=None, budget: int | None = None,
                 hasard: random.Random | None = None):
        self.univers, self.entree, self.dire = univers, entree, sortie
        self.serveur, self.budget = serveur, budget
        self.hasard = hasard or random.Random()

    def demander(self, question: str) -> str:
        reponse = self.entree(question).strip()
        if reponse.lower() in ("q", "quitter"):
            raise Abandon()
        return reponse

    def etape(self, b: Brouillon, nom: str, titre: str, proposer, lire=None, aide: str = ""):
        """Propose, puis garde, relance ou lit la saisie du joueur, jusqu'à une valeur valide."""
        propose = proposer()
        while True:
            self.dire(f"\n{titre} — proposé : {self.lisible(nom, propose)}")
            reponse = self.demander(f"Entrée pour garder, « r » pour relancer{', ou ' + aide if aide else ''} : ")
            try:
                if reponse == "":
                    b.fixer(nom, propose)
                    return
                if reponse.lower() == "r":
                    propose = proposer()
                    continue
                if lire is None:
                    raise EtapeInvalide(["Ici, garde ou relance."])
                b.fixer(nom, lire(reponse))
                return
            except EtapeInvalide as erreur:
                for e in erreur.erreurs:
                    self.dire(f"  ✗ {e}")

    def lisible(self, nom: str, valeur) -> str:
        u = self.univers
        if nom == "caracteristiques":
            return ", ".join(f"{c.libelle} {v}" for c, v in valeur.items())
        if nom in ("points_parcours", "points_personnels"):
            return ", ".join(f"{u.nom_affiche(c)} +{v}" for c, v in valeur.items())
        if nom == "equipement":
            objets = [str(valeur[c]) for c in ("arme", "armure", "implant", "vehicule") if valeur.get(c)]
            return ", ".join(objets + list(valeur.get("objets", []))) or "rien"
        if nom == "domaines":
            return ", ".join(valeur) or "aucun"
        return str(valeur)

    def creer(self) -> tuple[Personnage, Depart | None]:
        """Le personnage créé, et ce qu'il emporte en main."""
        return self.composer().finaliser()

    def composer(self) -> Brouillon:
        """Tout le dialogue, jusqu'à un brouillon complet que le moteur accepte."""
        u = self.univers
        self.dire(f"\n=== Création de ton personnage — {u.nom} ===")
        if self.demander("« tout » pour tout proposer d'un coup, Entrée pour y aller pas à pas : ").lower() == "tout":
            b = tout_proposer(u, self.serveur, self.budget, self.hasard)
        else:
            b = self.pas_a_pas()
        while True:
            if not b.roleplay:
                self.roleplay(b)
            self.dire("\n" + "\n".join(resume(b)))
            reponse = self.demander("Entrée pour valider, « p » pour reprendre pas à pas : ").lower()
            if reponse == "p":
                b = self.pas_a_pas(b.parcours)
                continue
            try:
                b.finaliser()  # le moteur refait toutes les vérifications ; le personnage sera créé à partir du brouillon
                return b
            except EtapeInvalide as erreur:
                for e in erreur.erreurs:
                    self.dire(f"  ✗ {e}")
                b = self.pas_a_pas(b.parcours)

    def pas_a_pas(self, parcours: str = "") -> Brouillon:
        u, b = self.univers, Brouillon(self.univers)
        noms = sorted(u.parcours)
        self.dire("\nLes parcours :")
        for i, nom in enumerate(noms, 1):
            self.dire(f"  {i}. {nom} — {u.descriptions.get(nom, '')}")
        while True:
            reponse = self.demander(f"Ton parcours (numéro ou nom{', Entrée pour ' + parcours if parcours else ''}) : ")
            choisi = parcours if not reponse else noms[int(reponse) - 1] if reponse.isdigit() and \
                0 < int(reponse) <= len(noms) else reponse
            try:
                b.fixer("parcours", choisi)
                break
            except EtapeInvalide as erreur:
                self.dire(f"  ✗ {erreur.erreurs[0]}")
        self.etape(b, "caracteristiques", "Caractéristiques (300 points, de 20 à 80)",
                   lambda: proposer_caracteristiques(b), lire_caracteristiques,
                   "écris « for 50, con 45, dex 60, int 65, vol 40, pré 40 »")
        self.etape(b, "points_parcours", "Points de parcours (300, sur ses 8 compétences)",
                   lambda: proposer_points_parcours(b), lambda t: lire_points(u, t), "écris « Piratage 70, … »")
        self.etape(b, "points_personnels", "Points personnels (100, sur n'importe quelles compétences)",
                   lambda: proposer_points_personnels(b), lambda t: lire_points(u, t), "écris « Esquive 20, … »")
        if u.magie_active and u.domaines:
            self.etape(b, "domaines", "Domaines de magie (2)", lambda: proposer_domaines(b, self.hasard),
                       lambda t: [d.strip() for d in t.split(",")], "écris « Pyromancie, Guérison »")
        if u.equipements.get(b.parcours):
            self.etape(b, "equipement", "Équipement de départ", lambda: proposer_equipement(b, self.hasard))
        return b

    def roleplay(self, b: Brouillon):
        """La personnalité : proposée par le LLM s'il répond, sinon écrite par le joueur."""
        reponse = self.demander("Une femme ou un homme ? (f / h, Entrée pour laisser le hasard) : ").lower()[:1]
        sexe = {"f": SEXES[0], "h": SEXES[1]}.get(reponse) or self.hasard.choice(SEXES)
        propose = proposer_personnalite(self.serveur, b, self.budget, self.hasard, sexe) \
            if self.serveur is not None else None
        while True:
            if propose:
                self.dire(f"\nPersonnalité proposée ({sexe}) :\n"
                          + "\n".join(f"  {k} : {v}" for k, v in propose.items() if k != "sexe"))
                reponse = self.demander("Entrée pour garder, « r » pour une autre, « m » pour l'écrire toi-même : ")
                if reponse == "":
                    b.fixer("roleplay", propose)
                    return
                if reponse.lower() == "r":
                    propose = proposer_personnalite(self.serveur, b, self.budget, self.hasard, sexe)
                    continue
            roleplay = {cle: self.demander(f"{question} : ") for cle, question in (
                ("nom", "Son nom"), ("motivation", "Ce qu'il cherche"), ("lien", "Qui ou quoi compte pour lui"),
                ("defaut", "Son défaut"), ("allure", "Son allure (facultatif)"))}
            try:
                b.fixer("roleplay", roleplay | {"sexe": sexe})
                return
            except EtapeInvalide as erreur:
                for e in erreur.erreurs:
                    self.dire(f"  ✗ {e}")
                propose = None
