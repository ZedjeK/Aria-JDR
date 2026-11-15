"""La partie en cours : le moteur tourne dans un fil de travail, ses sorties s'ajoutent à une liste d'événements que la
page lit, et ses questions attendent la réponse du joueur.

Le moteur parle par deux fonctions qu'on lui donne, `entree(invite)` et `sortie(texte)` : la console par défaut,
cette session ici. Une seule partie à la fois : elle tient le serveur du MJ (la carte graphique) du début à la fin.
"""

import threading
import traceback
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query

from appli import donnees

EVENEMENTS_MAX = 4000  # on garde les derniers : la page reprend le fil après un rechargement


class PartieEnCours(Exception):
    """Une partie tourne déjà."""


class Partie:
    def __init__(self, racine: Path | None = None):
        self._racine = racine
        self._verrou = threading.Condition()
        self._fil: threading.Thread | None = None
        self._evenements: list[dict] = []
        self._numero = 0
        self._reponse: str | None = None
        self.actif = False
        self.nature = ""  # « campagne » ou « personnage »
        self.titre = ""
        self.campagne: str | None = None  # la campagne ouverte, qu'on ne jette pas pendant qu'on y joue
        self.attend: str | None = None  # la question posée au joueur, tant qu'elle attend sa réponse
        self.arret = False
        self.erreur: str | None = None

    # --- Ce que le moteur utilise (depuis le fil de travail)

    def sortie(self, texte: str = "") -> None:
        self._ajouter("texte", str(texte))

    def entree(self, invite: str = "") -> str:
        """Pose la question et attend la réponse. Si on arrête la partie, lève EOFError : le moteur la ferme proprement."""
        with self._verrou:
            self._reponse = None
            self.attend = invite
            self._ajouter("invite", invite, deja_verrouille=True)
            while self._reponse is None and not self.arret:
                self._verrou.wait()
            self.attend = None
            if self.arret:
                raise EOFError
            reponse, self._reponse = self._reponse, None
        self._ajouter("joueur", reponse)
        return reponse

    # --- Ce que les routes utilisent

    def demarrer(self, nature: str, titre: str, campagne: str | None, travail: Callable[[Callable, Callable], None]) -> None:
        with self._verrou:
            if self.actif:
                raise PartieEnCours
            self._evenements, self._numero = [], 0
            self._reponse, self.attend, self.arret, self.erreur = None, None, False, None
            self.actif, self.nature, self.titre, self.campagne = True, nature, titre, campagne
            self._fil = threading.Thread(target=self._courir, args=(travail,), name="partie", daemon=True)
            self._fil.start()
        donnees.noter("partie", f"Partie démarrée : {titre}.", self._racine)

    def repondre(self, texte: str) -> None:
        with self._verrou:
            if self.attend is None or self._reponse is not None:
                raise ValueError("Le jeu n'attend pas de réponse en ce moment.")
            self._reponse = texte
            self.attend = None  # la question est répondue : la page voit tout de suite que le jeu a repris la main
            self._verrou.notify_all()

    def arreter(self) -> None:
        with self._verrou:
            self.arret = True
            self._verrou.notify_all()

    def attendre_la_fin(self, delai: float) -> bool:
        fil = self._fil
        if fil is not None:
            fil.join(delai)
        return not self.actif

    def etat(self) -> dict:
        with self._verrou:
            return {"actif": self.actif, "nature": self.nature, "titre": self.titre, "campagne": self.campagne,
                    "attend": self.attend, "arret": self.arret, "erreur": self.erreur, "dernier": self._numero}

    def evenements(self, apres: int, attente: float = 0.0) -> dict:
        """Les événements numérotés après `apres` ; attend jusqu'à `attente` secondes s'il n'y en a pas encore."""
        with self._verrou:
            if attente and self.actif and not self._apres(apres):
                self._verrou.wait(attente)
            return {"evenements": self._apres(apres), "actif": self.actif, "attend": self.attend, "dernier": self._numero}

    # --- Interne

    def _apres(self, apres: int) -> list[dict]:
        return [e for e in self._evenements if e["n"] > apres]

    def _ajouter(self, type_: str, texte: str, deja_verrouille: bool = False) -> None:
        def ajouter():
            self._numero += 1
            self._evenements.append({"n": self._numero, "type": type_, "texte": texte})
            del self._evenements[:-EVENEMENTS_MAX]
            self._verrou.notify_all()

        if deja_verrouille:
            ajouter()
        else:
            with self._verrou:
                ajouter()

    def _courir(self, travail) -> None:
        try:
            travail(self.entree, self.sortie)
        except EOFError:
            self.sortie("\nPartie interrompue.")
        except Exception as erreur:  # noqa: BLE001 : le fil ne doit jamais mourir sans le dire à la page
            self.erreur = f"{type(erreur).__name__} : {erreur}"
            self.sortie(f"\nLa partie s'est arrêtée sur une erreur ({self.erreur}).")
            donnees.noter("partie", f"Erreur : {self.erreur}", self._racine)
            traceback.print_exc()
        finally:
            with self._verrou:
                self.actif, self.attend = False, None
                self._ajouter("fin", "", deja_verrouille=True)
            donnees.noter("partie", f"Partie terminée : {self.titre}.", self._racine)


def _verifier_le_mj(profil_valide, moteur) -> None:
    """Sans serveur llama ni MJ qualifié, rien ne démarre : on le dit avant de lancer le fil."""
    if not Path(moteur()).is_file():
        raise HTTPException(409, f"Le serveur du MJ est introuvable : {moteur()}. Place le dossier Aria-LLM à côté de l'exe, "
                                 "ou dans ton dossier d'utilisateur.")
    if not profil_valide():
        raise HTTPException(409, "Pas encore de MJ qualifié sur ce PC. Le banc d'essai le qualifie : pour l'instant, "
                                 "lance-le depuis la console (python -m aria.banc).")


def options_de_creation() -> dict:
    """De quoi remplir les formulaires : les genres, les tons, les types de campagne, les crans, les personnages prêts."""
    from aria import generateur, personnages, trame
    from aria.bibliotheque import GENRES
    from aria.reglages import Curseur
    bibliotheque = generateur.charger()
    prets = personnages.lister()
    return {
        "genres": [{"nom": g, "complet": g == "Cyberpunk", "magie_au_choix": bibliotheque.genres[g]["magie"]["statut"] == generateur.OPTION,
                    "ton": generateur.choix_par_defaut(bibliotheque, g).curseur,
                    "personnages": [{"id": p.fichier.name if p.fichier else "livre", "titre": p.titre()} for p in prets if p.genre == g]}
                   for g in GENRES],
        "tons": [c.value for c in Curseur],
        "types": [{"nom": t.nom, "description": t.description, "cran": t.depart} for t in trame.TYPES.values()],
        "type_standard": trame.STANDARD,
        "crans": list(trame.CRANS),
    }


def routeur(partie: Partie, profil_valide: Callable[[], dict | None], moteur: Callable[[], Path]) -> APIRouter:
    api = APIRouter(prefix="/api")

    @api.get("/creation")
    def creation():
        return options_de_creation()

    @api.get("/partie")
    def etat():
        return partie.etat()

    @api.get("/partie/evenements")
    def evenements(apres: int = Query(0, ge=0), attente: float = Query(0.0, ge=0.0, le=30.0)):
        return partie.evenements(apres, attente)

    def lancer(nature, titre, campagne, travail):
        try:
            partie.demarrer(nature, titre, campagne, travail)
        except PartieEnCours:
            raise HTTPException(409, "Une partie est déjà ouverte : termine-la d'abord.") from None
        return partie.etat()

    @api.post("/partie/reprendre")
    def reprendre(corps: dict = Body(...)):
        from aria import campagne, jeu
        nom = corps.get("nom")
        if nom not in campagne.noms():  # un nom n'est jamais un chemin : seulement un élément de la liste du moteur
            raise HTTPException(404, "Cette campagne n'existe pas.")
        if partie.actif:
            raise HTTPException(409, "Une partie est déjà ouverte : termine-la d'abord.")
        _verifier_le_mj(profil_valide, moteur)
        return lancer("campagne", f"Campagne « {nom} »", nom,
                      lambda entree, sortie: jeu.lancer(campagne.Campagne.nommee(nom), entree=entree, sortie=sortie))

    @api.post("/partie/nouvelle")
    def nouvelle(corps: dict = Body(...)):
        from dataclasses import replace

        from aria import campagne, generateur, jeu, personnages, trame
        from aria.bibliotheque import GENRES
        from aria.reglages import Curseur
        if partie.actif:
            raise HTTPException(409, "Une partie est déjà ouverte : termine-la d'abord.")
        nom = campagne.nom_valide(str(corps.get("nom", "")))
        if nom is None:
            raise HTTPException(400, "Le nom : 40 caractères au plus, des lettres sans accent, des chiffres et des tirets.")
        if (campagne.racine() / nom).exists():
            raise HTTPException(409, f"La campagne « {nom} » existe déjà.")
        genre = corps.get("genre")
        if genre not in GENRES:
            raise HTTPException(400, "Ce genre n'existe pas.")
        bibliotheque = generateur.charger()
        choix = generateur.choix_par_defaut(bibliotheque, genre)
        surprends_moi = corps.get("surprends_moi") is True
        univers = str(corps.get("univers", "")).strip()
        if univers and not surprends_moi:
            annee = corps.get("annee")
            if annee not in (None, "") and not (isinstance(annee, int) or str(annee).lstrip("-").isdigit()):
                raise HTTPException(400, "L'année : des chiffres, par exemple 1925.")
            choix = replace(choix, nom=univers, cadre=str(corps.get("cadre", "")).strip(),
                            annee=int(annee) if annee not in (None, "") else None)
        ton = corps.get("ton")
        if ton:
            if ton not in [c.value for c in Curseur]:
                raise HTTPException(400, "Ce ton n'existe pas.")
            choix = replace(choix, curseur=ton)
        if bibliotheque.genres[genre]["magie"]["statut"] == generateur.OPTION:
            choix = replace(choix, magie=corps.get("magie") is True)
        erreurs = generateur.verifier_choix(bibliotheque, choix)
        if erreurs:
            raise HTTPException(400, " ".join(erreurs))
        type_ = corps.get("type") or trame.STANDARD
        if type_ not in trame.TYPES:
            raise HTTPException(400, "Ce type de campagne n'existe pas.")
        predefini = None
        if corps.get("personnage"):
            predefini = next((p for p in personnages.lister(genre)
                              if (p.fichier.name if p.fichier else "livre") == corps["personnage"]), None)
            if predefini is None:
                raise HTTPException(400, "Ce personnage n'existe pas pour ce genre.")
            cran = predefini.cran  # un personnage prêt garde l'expérience qu'on lui a donnée
        else:
            cran = corps.get("cran") or trame.TYPES[type_].depart
            if cran not in trame.CRANS:
                raise HTTPException(400, "Cette expérience n'existe pas.")
        _verifier_le_mj(profil_valide, moteur)

        def travail(entree, sortie):
            trame.ecrire_format(campagne.Campagne.nommee(nom), trame.Format(type_, cran))
            jeu.lancer(campagne.Campagne.nommee(nom), choix, surprends_moi, predefini=predefini, entree=entree, sortie=sortie)

        return lancer("campagne", f"Nouvelle campagne « {nom} »", nom, travail)

    @api.post("/partie/personnage")
    def personnage(corps: dict = Body(...)):
        from aria import personnages, trame
        from aria.bibliotheque import GENRES
        if partie.actif:
            raise HTTPException(409, "Une partie est déjà ouverte : termine-la d'abord.")
        genre, cran = corps.get("genre"), corps.get("cran") or trame.DEBUTANT
        if genre not in GENRES:
            raise HTTPException(400, "Ce genre n'existe pas.")
        if cran not in trame.CRANS:
            raise HTTPException(400, "Cette expérience n'existe pas.")
        avec_mj = corps.get("avec_mj") is True
        if avec_mj:
            _verifier_le_mj(profil_valide, moteur)
        return lancer("personnage", f"Nouveau personnage ({genre})", None,
                      lambda entree, sortie: personnages.creer(genre, cran, avec_mj, entree, sortie))

    @api.post("/partie/saisie")
    def saisie(corps: dict = Body(...)):
        texte = corps.get("texte")
        if not isinstance(texte, str) or len(texte) > 2000:
            raise HTTPException(400, "Le texte est absent, ou trop long (2 000 caractères au plus).")
        try:
            partie.repondre(texte)
        except ValueError as erreur:
            raise HTTPException(409, str(erreur)) from None
        return {"envoye": True}

    @api.post("/partie/arreter")
    def arreter():
        if not partie.actif:
            raise HTTPException(409, "Aucune partie n'est ouverte.")
        partie.arreter()
        return {"arret": True}

    return api
