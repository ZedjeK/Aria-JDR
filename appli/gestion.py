"""La gestion de ce qu'Aria JDR range dans le dossier de données : les campagnes, la corbeille, les personnages préparés
à l'avance et le MJ retenu sur ce PC. Rien ici ne démarre une partie : c'est le lot suivant.

Ce que le joueur ou le MJ ont écrit (noms d'univers, de personnages…) ne passe jamais par un chemin ni par du HTML : un
nom reçu d'une requête n'est utilisé que s'il est dans la liste que le moteur donne, et l'interface l'affiche en texte.
"""

import os
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from appli import donnees


def lire_profil_valide() -> dict | None:
    from aria import banc
    return banc.profil_valide()


def chercher_moteur() -> Path:
    from aria import llm
    return llm.MOTEUR


def decrire_campagne(nom: str) -> dict:
    """Une campagne en quelques champs : son univers, le ton, le personnage et où il en est. Une campagne abîmée ne doit
    pas empêcher de voir les autres : elle est signalée illisible."""
    from aria import campagne, trame
    from aria.personnage import Etat
    from aria.sauvegarde import charger
    from aria.univers import charger_univers

    c = campagne.Campagne.nommee(nom)
    try:
        if c.sauvegarde.is_file():
            partie = charger(c.sauvegarde)
            univers, perso = partie.univers, partie.personnage
            fin = ((partie.monde or {}).get("trame", {}).get("fin", {}) or {}).get("nom")
            if perso.etat is Etat.MORT:
                etat, etape = "mort", "mort"
            elif trame.arretee(partie.monde):
                etat, etape = "terminee", f"terminée ({fin})" if fin else "terminée"
            else:
                etat, etape = "en-cours", str(partie.moment)
            personnage = {"nom": perso.nom, "parcours": perso.parcours}
        else:
            univers = charger_univers(c.univers)
            etat, etape, personnage = "a-finir", "création du personnage à finir", None
    except Exception as erreur:  # noqa: BLE001 : n'importe quelle abîme du fichier, jamais l'ensemble de la liste
        return {"nom": nom, "lisible": False, "erreur": type(erreur).__name__}
    return {"nom": nom, "lisible": True, "univers": univers.nom, "genre": univers.genre, "ton": univers.curseur.value,
            "magie": bool(univers.magie_active), "personnage": personnage, "etat": etat, "etape": etape}


def _date_de_la_corbeille(jetee: str) -> str:
    """« nom_20261115-134500 » : la date lisible, ou rien si le nom n'a pas cette forme."""
    horodatage = jetee.rsplit("_", 1)[-1]
    try:
        jour, heure = horodatage.split("-")
        return f"{jour[:4]}-{jour[4:6]}-{jour[6:]} {heure[:2]}:{heure[2:4]}"
    except (ValueError, IndexError):
        return ""


def decrire_personnage(pret) -> dict:
    return {"id": pret.fichier.name if pret.fichier else "livre", "nom": pret.nom, "titre": pret.titre(),
            "genre": pret.genre, "parcours": pret.parcours, "cran": pret.cran, "livre": pret.fichier is None}


def routeur(racine: Path | None = None, profil_valide: Callable[[], dict | None] | None = None,
            moteur: Callable[[], Path] | None = None, partie=None) -> APIRouter:
    """Les routes de la gestion. `racine` : le dossier de données de l'appli (le journal) ; `profil_valide` et `moteur` :
    ce que dit le banc et où est le serveur llama, remplaçables dans les tests ; `partie` : la partie en cours, dont on
    ne jette pas la campagne."""
    profil_valide = profil_valide or lire_profil_valide
    moteur = moteur or chercher_moteur
    api = APIRouter(prefix="/api")

    @api.get("/mj")
    def mj():
        """Le MJ retenu sur ce PC, s'il vaut encore (même carte graphique, modèle toujours là), et si le serveur llama est là."""
        chemin = moteur()
        present = Path(chemin).is_file()
        base = {"moteur_present": present, "moteur": str(chemin)}
        profil = profil_valide()
        if not profil:
            return {"qualifie": False, **base}
        try:
            reflexion = int(profil["budget_reflexion"])
            return {"qualifie": True, "modele": str(profil["modele"]), "fichier": str(profil.get("fichier", "")),
                    "budget_reflexion": reflexion, "budget_generateur": int(profil.get("budget_generateur") or reflexion),
                    **base}
        except (KeyError, TypeError, ValueError):
            return {"qualifie": False, **base}

    @api.get("/campagnes")
    def lister_campagnes():
        from aria import campagne
        return [decrire_campagne(nom) for nom in campagne.noms()]

    @api.post("/campagnes/{nom}/corbeille")
    def jeter_campagne(nom: str):
        from aria import campagne
        if nom not in campagne.noms():
            raise HTTPException(404, "Cette campagne n'existe pas.")
        if partie is not None and partie.actif and partie.campagne == nom:
            raise HTTPException(409, "On joue cette campagne en ce moment : termine la partie d'abord.")
        campagne.supprimer(nom)
        donnees.noter("campagne", f"Campagne « {nom} » mise à la corbeille.", racine)
        return {"nom": nom}

    @api.get("/corbeille")
    def lister_corbeille():
        from aria import campagne
        return [{"id": j, "nom": j.rsplit("_", 1)[0], "date": _date_de_la_corbeille(j)} for j in campagne.jetees()]

    @api.post("/corbeille/{jetee}/restaurer")
    def restaurer(jetee: str):
        from aria import campagne
        if jetee not in campagne.jetees():
            raise HTTPException(404, "Cette campagne n'est pas dans la corbeille.")
        nom = campagne.restaurer(jetee)
        if nom is None:
            raise HTTPException(409, "Une campagne du même nom existe déjà : supprime-la d'abord.")
        donnees.noter("campagne", f"Campagne « {nom} » restaurée.", racine)
        return {"nom": nom}

    @api.post("/corbeille/vider")
    def vider(corps: dict = Body(...)):
        from aria import campagne
        if corps.get("confirme") is not True:
            raise HTTPException(400, "Vider la corbeille est définitif : il faut le confirmer.")
        nombre = campagne.vider_corbeille()
        donnees.noter("campagne", f"Corbeille vidée : {nombre} campagne(s) effacée(s).", racine)
        return {"effacees": nombre}

    @api.get("/personnages")
    def lister_personnages():
        from aria import personnages
        return [decrire_personnage(p) for p in personnages.lister()]

    @api.post("/personnages/{identifiant}/supprimer")
    def supprimer_personnage(identifiant: str):
        from aria import personnages
        pret = next((p for p in personnages.lister() if decrire_personnage(p)["id"] == identifiant), None)
        if pret is None:
            raise HTTPException(404, "Ce personnage n'existe pas.")
        if pret.fichier is None:
            raise HTTPException(403, f"{pret.nom} est livré avec le jeu : il ne se supprime pas.")
        personnages.supprimer(pret)
        donnees.noter("personnage", f"Personnage « {pret.nom} » supprimé.", racine)
        return {"nom": pret.nom}

    @api.post("/donnees/ouvrir")
    def ouvrir_donnees():
        """Ouvre le dossier des données dans l'Explorateur : on ne le change pas, on l'ouvre."""
        from aria import chemins
        if not hasattr(os, "startfile"):
            raise HTTPException(501, "L'ouverture du dossier n'existe que sous Windows.")
        try:
            os.startfile(chemins.DONNEES)
        except OSError as erreur:
            raise HTTPException(500, f"Impossible d'ouvrir le dossier : {erreur.strerror or erreur}") from erreur
        return {"dossier": str(chemins.DONNEES)}

    return api
