"""Les routes des mises à jour : lire l'état, chercher, installer (seulement sur un POST, seulement depuis l'exe, et
jamais pendant une partie ou un banc)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from appli import donnees, identite, mises_a_jour, serveur

PORT, JETON = 8765, "jeton-de-test"
NOUVELLE = mises_a_jour.MiseAJour("9.0.0", "https://github.com/x/releases/tag/v9.0.0",
                                  mises_a_jour.Fichier("x.zip", "https://github.com/x.zip", 3, "00" * 32))


@pytest.fixture
def lancer(tmp_path, monkeypatch):
    monkeypatch.setattr(mises_a_jour, "chercher", lambda: NOUVELLE)
    arrets = []

    def lancer(**options):
        app = serveur.creer_app(JETON, PORT, racine=tmp_path, arreter=lambda: arrets.append(True), **options)
        client = TestClient(app, base_url=f"http://127.0.0.1:{PORT}", follow_redirects=False)
        assert client.get(f"/?j={JETON}").status_code == 303
        client.arrets, client.partie = arrets, app.state.partie
        return client

    return lancer


@pytest.fixture
def depuis_l_exe(tmp_path, monkeypatch):
    """L'appli tourne depuis son exe, et l'installation réussit sans rien toucher pour de vrai."""
    exe = tmp_path / "jeu" / mises_a_jour.nom_exe()
    monkeypatch.setattr(mises_a_jour, "exe_en_cours", lambda: exe)
    appels = []
    monkeypatch.setattr(mises_a_jour, "telecharger",
                        lambda trouvee, dossier: appels.append(("telecharger", trouvee.version, dossier)) or dossier / "x.zip")
    monkeypatch.setattr(mises_a_jour, "installer",
                        lambda archive, exe_, versions, travail: appels.append(("installer", exe_, versions))
                        or mises_a_jour.Resultat(True, exe=exe_))
    monkeypatch.setattr(mises_a_jour, "relancer", lambda exe_, pid=None: appels.append(("relancer", exe_)))
    return exe, appels


def test_rien_n_est_cherche_si_on_ne_le_demande_pas(lancer):
    etat = lancer().get("/api/mise-a-jour").json()
    assert etat == {"actuelle": identite.version(), "cherchee": False, "enCours": False, "possible": False,
                    "disponible": None}


def test_chercher_trouve_la_nouvelle_version(lancer):
    etat = lancer().post("/api/mise-a-jour/chercher").json()
    assert etat["cherchee"] and etat["disponible"] == {"version": "9.0.0", "page": NOUVELLE.page}


def test_la_recherche_du_lancement_tourne_dans_un_fil(lancer):
    client = lancer(chercher_au_lancement=True)
    for _ in range(50):
        etat = client.get("/api/mise-a-jour").json()
        if etat["cherchee"]:
            break
        import time
        time.sleep(0.05)
    assert etat["disponible"]["version"] == "9.0.0"


def test_aucune_action_ne_passe_par_un_get(lancer, depuis_l_exe):
    client = lancer()
    for chemin in ("/api/mise-a-jour/chercher", "/api/mise-a-jour/installer"):
        assert client.get(chemin).status_code in (404, 405)
    assert client.get("/api/mise-a-jour").json()["cherchee"] is False
    assert depuis_l_exe[1] == [] and client.arrets == []


def test_installer_sans_version_connue_est_refuse(lancer, depuis_l_exe):
    client = lancer()
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 409 and depuis_l_exe[1] == []


def test_depuis_les_sources_rien_ne_s_installe(lancer, monkeypatch):
    monkeypatch.setattr(mises_a_jour, "exe_en_cours", lambda: None)
    client = lancer()
    client.post("/api/mise-a-jour/chercher")
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 409 and "sources" in reponse.json()["detail"]
    assert client.arrets == []


def test_pendant_une_partie_ou_un_banc_rien_ne_s_installe(lancer, depuis_l_exe):
    client = lancer()
    client.post("/api/mise-a-jour/chercher")
    client.partie.actif = True  # une partie ou un banc : le serveur du MJ tourne
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 409 and "termine-le d'abord" in reponse.json()["detail"]
    assert depuis_l_exe[1] == [] and client.arrets == []


def test_une_partie_lancee_pendant_le_telechargement_annule_l_installation(lancer, depuis_l_exe, monkeypatch):
    exe, appels = depuis_l_exe
    client = lancer()
    client.post("/api/mise-a-jour/chercher")

    def telecharger_pendant_qu_une_partie_demarre(trouvee, dossier):
        client.partie.actif = True
        return dossier / "x.zip"

    monkeypatch.setattr(mises_a_jour, "telecharger", telecharger_pendant_qu_une_partie_demarre)
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 500 and "termine-le d'abord" in reponse.json()["detail"]
    assert appels == [] and client.arrets == []


def test_installer_telecharge_installe_relance_puis_arrete(lancer, depuis_l_exe, tmp_path):
    exe, appels = depuis_l_exe
    client = lancer()
    client.post("/api/mise-a-jour/chercher")
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 200 and reponse.json() == {"installee": "9.0.0"}
    assert [a[0] for a in appels] == ["telecharger", "installer", "relancer"]
    assert appels[0][2] == mises_a_jour.dossier_travail(tmp_path)
    assert appels[1][2] == mises_a_jour.dossier_versions(tmp_path)
    assert client.arrets == [True]
    assert any("9.0.0 installée" in e["bilan"] for e in donnees.lire_journal(tmp_path))
    # Une seconde installation n'est pas lancée pendant l'arrêt
    assert client.post("/api/mise-a-jour/installer").status_code == 409


def test_un_echec_est_dit_note_et_ne_relance_rien(lancer, depuis_l_exe, monkeypatch, tmp_path):
    exe, appels = depuis_l_exe
    monkeypatch.setattr(mises_a_jour, "installer",
                        lambda *a: mises_a_jour.Resultat(False, "Il manque dans le zip : x.dll. Rien n'est installé."))
    client = lancer()
    client.post("/api/mise-a-jour/chercher")
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 500 and "x.dll" in reponse.json()["detail"]
    assert "relancer" not in [a[0] for a in appels] and client.arrets == []
    assert any("non installée" in e["bilan"] for e in donnees.lire_journal(tmp_path))
    # On peut réessayer
    monkeypatch.setattr(mises_a_jour, "installer", lambda archive, exe_, *a: mises_a_jour.Resultat(True, exe=exe_))
    assert client.post("/api/mise-a-jour/installer").status_code == 200


def test_un_telechargement_refuse_n_installe_rien(lancer, depuis_l_exe, monkeypatch):
    exe, appels = depuis_l_exe

    def refuse(trouvee, dossier):
        raise mises_a_jour.ErreurMiseAJour("Le fichier téléchargé ne correspond pas à l'empreinte annoncée par GitHub.")

    monkeypatch.setattr(mises_a_jour, "telecharger", refuse)
    client = lancer()
    client.post("/api/mise-a-jour/chercher")
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 500 and "empreinte" in reponse.json()["detail"]
    assert appels == [] and client.arrets == []


def test_une_relance_impossible_dit_comment_finir(lancer, depuis_l_exe, monkeypatch):
    def plante(exe_, pid=None):
        raise OSError("lancement refusé")

    monkeypatch.setattr(mises_a_jour, "relancer", plante)
    client = lancer()
    client.post("/api/mise-a-jour/chercher")
    reponse = client.post("/api/mise-a-jour/installer")
    assert reponse.status_code == 500 and "est installée" in reponse.json()["detail"]
    assert client.arrets == []


def test_le_reglage_de_la_recherche_s_enregistre(lancer, tmp_path):
    client = lancer()
    reglages = client.get("/api/reglages").json()
    assert reglages["chercherMisesAJour"] is True
    reglages["chercherMisesAJour"] = False
    assert client.put("/api/reglages", json=reglages).json()["chercherMisesAJour"] is False
    assert donnees.charger_reglages(tmp_path).chercher_mises_a_jour is False


def test_la_page_a_le_bandeau_et_le_reglage(lancer):
    page = lancer().get("/").text
    for repere in ('id="maj"', 'id="maj-installer"', 'id="chercher-maj"', 'id="maj-chercher"'):
        assert repere in page
