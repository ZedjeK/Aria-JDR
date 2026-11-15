"""Le serveur local : l'interface web (appli\\statique) et son API, sur 127.0.0.1 seulement.

Chaque appli ajoute ses routes ici. Les lectures sont des GET ; tout ce qui modifie quelque chose est un POST ou un PUT.
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from appli import donnees, fond, gestion, identite, partie, securite


def creer_app(jeton: str, port: int, racine: Path | None = None, arreter: Callable[[], None] | None = None,
              profil_valide: Callable[[], dict | None] | None = None, moteur: Callable[[], Path] | None = None) -> FastAPI:
    """`racine` : le dossier de données de l'appli (celui de l'utilisateur par défaut) ; `arreter` : ce que fait « Quitter » ;
    `profil_valide` et `moteur` : ce que disent le banc et le dossier du serveur llama (remplaçables dans les tests)."""
    app = FastAPI(title=identite.NOM, version=identite.version(), docs_url=None, redoc_url=None, openapi_url=None)
    securite.installer(app, port, jeton)
    profil_valide = profil_valide or gestion.lire_profil_valide
    moteur = moteur or gestion.chercher_moteur
    app.state.partie = session = partie.Partie(racine)
    app.include_router(gestion.routeur(racine, profil_valide, moteur, session))
    app.include_router(partie.routeur(session, profil_valide, moteur))

    @app.get("/api/etat")
    def etat():
        return {"nom": identite.NOM, "exe": identite.EXE, "version": identite.version(),
                "en_fond": identite.EN_FOND, "installable": identite.INSTALLABLE}

    @app.get("/api/reglages")
    def lire_reglages():
        return donnees.charger_reglages(racine).en_dict()

    @app.put("/api/reglages")
    def ecrire_reglages(brut: dict = Body(...)):
        nouveaux = donnees.Reglages.depuis_dict(brut)
        fichier = (Path(racine) if racine is not None else identite.dossier_donnees()) / donnees.FICHIER_REGLAGES
        try:
            if fichier.is_file():
                donnees.sauvegarder(fichier, racine)  # sans copie, pas de modification
            donnees.enregistrer_reglages(nouveaux, racine)
        except OSError as erreur:
            raise HTTPException(500, f"Réglages non enregistrés : {erreur.strerror or erreur}") from erreur
        donnees.noter("réglages", "Réglages enregistrés.", racine)
        return nouveaux.en_dict()

    @app.get("/api/fond")
    def lire_fond():
        """Ce que le navigateur a besoin de savoir pour dessiner le fond : les règles sont dans appli.fond."""
        reglage = donnees.charger_reglages(racine).fond
        return {"actif": reglage.actif, "duree": fond.duree_passage(reglage), "minimum": reglage.minimum,
                "maximum": reglage.maximum}

    @app.post("/api/quitter")
    def quitter():
        if arreter is None:
            raise HTTPException(409, "Cette appli ne sait pas s'arrêter seule.")
        if session.actif:
            raise HTTPException(409, "Une partie ou un banc est en cours : termine-le d'abord (le serveur du MJ doit être arrêté proprement).")
        donnees.noter("arrêt", "Arrêt demandé depuis l'interface.", racine)
        arreter()
        return {"arret": True}

    @app.get("/logo.svg", include_in_schema=False)
    def logo():
        return FileResponse(identite.racine() / "docs" / "logo.svg", media_type="image/svg+xml")

    app.mount("/", StaticFiles(directory=identite.racine() / "appli" / "statique", html=True), name="statique")
    return app
