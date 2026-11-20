"""Le lancement : une seule instance, un serveur local, puis l'interface dans le navigateur par défaut."""

import socket
import sys
import threading
import webbrowser

import uvicorn

from appli import donnees, identite, instance, mises_a_jour, securite, serveur


def _port_libre() -> int:
    with socket.socket() as essai:
        essai.bind(("127.0.0.1", 0))
        return essai.getsockname()[1]


def _port_disponible(port: int) -> bool:
    with socket.socket() as essai:
        try:
            essai.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def choisir_port() -> int:
    """Le port de la fiche ; si un autre programme l'occupe, un port libre plutôt qu'un échec muet (l'exe n'a pas de console)."""
    if identite.PORT and _port_disponible(identite.PORT):
        return identite.PORT
    return _port_libre()


def _sortie_vers_journal() -> None:
    """Sans console (exe lancé par double-clic), il n'y a pas de sortie standard : elle va dans cache\\appli.log."""
    if sys.stdout is None or sys.stderr is None:
        journal = open(donnees.assurer() / donnees.DOSSIER_CACHE / "appli.log", "w", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = journal


def main() -> int:
    try:
        donnees.assurer()
    except OSError as erreur:
        print(f"{identite.NOM} : le dossier de données {identite.dossier_donnees()} est inutilisable ({erreur}).")
        return 1
    _sortie_vers_journal()

    # Lancée par une mise à jour : l'ancienne version doit avoir rendu le port, l'instance et son exe
    ancienne = mises_a_jour.pid_a_attendre(sys.argv[1:])
    if ancienne is not None and not mises_a_jour.attendre_la_fin(ancienne):
        donnees.noter("mise à jour", "L'ancienne version ne s'est pas arrêtée à temps : la nouvelle démarre quand même.")

    exemplaire = instance.Instance()
    if not exemplaire.prendre():
        # Une instance tourne déjà : on rouvre son interface au lieu d'en démarrer une seconde
        instance.ramener()
        return 0

    exe = mises_a_jour.exe_en_cours()
    mises_a_jour.nettoyer(exe.parent if exe else None)  # restes d'une mise à jour : « .ancien », zip, extraction
    if ancienne is not None:
        donnees.noter("mise à jour", f"{identite.NOM} {identite.version()} démarre après sa mise à jour.")

    port = choisir_port()
    jeton = securite.nouveau_jeton()
    config = uvicorn.Config(None, host="127.0.0.1", port=port, log_config=None)
    serveur_http = uvicorn.Server(config)
    config.app = serveur.creer_app(jeton, port, arreter=lambda: setattr(serveur_http, "should_exit", True),
                                   chercher_au_lancement=exe is not None and donnees.charger_reglages().chercher_mises_a_jour)

    def ouvrir_quand_pret():
        while not serveur_http.started and not serveur_http.should_exit:
            threading.Event().wait(0.1)
        if serveur_http.started:
            instance.publier(port, jeton)
            webbrowser.open(instance.adresse(port, jeton))

    threading.Thread(target=ouvrir_quand_pret, daemon=True).start()
    donnees.noter("démarrage", f"{identite.NOM} {identite.version()} démarre sur le port {port}.")
    try:
        serveur_http.run()
    finally:
        instance.retirer()
        exemplaire.rendre()
        donnees.noter("arrêt", f"{identite.NOM} s'arrête.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
