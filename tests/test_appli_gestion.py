"""La gestion des campagnes, de la corbeille et des personnages par l'interface (appli.gestion)."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from appli import donnees, gestion, serveur
from aria import campagne, chemins
from aria.sauvegarde import sauvegarder
from tests.test_sauvegarde import partie_en_cours
from tests.test_univers import CYBERPUNK

PORT, JETON = 8765, "jeton-de-test"


@pytest.fixture
def donnees_jeu(tmp_path, monkeypatch):
    """Un dossier de données jetable, pour le moteur comme pour l'interface."""
    dossier = tmp_path / ".Aria-JDR"
    dossier.mkdir()
    monkeypatch.setattr(chemins, "DONNEES", dossier)
    return dossier


@pytest.fixture
def client(donnees_jeu):
    app = serveur.creer_app(JETON, PORT, racine=donnees_jeu, profil_valide=lambda: None, moteur=lambda: donnees_jeu / "x")
    ouvert = TestClient(app, base_url=f"http://127.0.0.1:{PORT}", follow_redirects=False)
    assert ouvert.get(f"/?j={JETON}").status_code == 303
    return ouvert


def campagne_en_cours(nom: str):
    c = campagne.Campagne.nommee(nom)
    c.ouvrir()
    sauvegarder(partie_en_cours(), c.sauvegarde)
    return c


def campagne_a_finir(nom: str):
    c = campagne.Campagne.nommee(nom)
    c.ouvrir()
    c.univers.write_text(CYBERPUNK.read_text(encoding="utf-8"), encoding="utf-8")
    return c


def test_sans_campagne_la_liste_est_vide(client):
    assert client.get("/api/campagnes").json() == []


def test_une_campagne_en_cours_dit_son_univers_son_personnage_et_ou_elle_en_est(client):
    campagne_en_cours("neo-tokyo")
    [c] = client.get("/api/campagnes").json()
    assert c["nom"] == "neo-tokyo" and c["lisible"] and c["genre"] == "Cyberpunk" and c["etat"] == "en-cours"
    assert c["personnage"]["parcours"] == "Netrunner" and c["etape"] and c["magie"] is False


def test_une_campagne_sans_sauvegarde_attend_la_fin_de_la_creation_du_personnage(client):
    campagne_a_finir("osaka")
    [c] = client.get("/api/campagnes").json()
    assert c["etat"] == "a-finir" and c["personnage"] is None and "création" in c["etape"]


def test_une_campagne_abimee_est_signalee_sans_cacher_les_autres(client):
    campagne_en_cours("bonne")
    mauvaise = campagne.Campagne.nommee("abimee")
    mauvaise.ouvrir()
    mauvaise.sauvegarde.write_text("pas du json", encoding="utf-8")
    liste = {c["nom"]: c for c in client.get("/api/campagnes").json()}
    assert liste["bonne"]["lisible"] is True
    assert liste["abimee"]["lisible"] is False and "erreur" in liste["abimee"]


def test_jeter_une_campagne_la_met_a_la_corbeille_sans_rien_effacer(client, donnees_jeu):
    campagne_en_cours("neo-tokyo")
    assert client.post("/api/campagnes/neo-tokyo/corbeille").status_code == 200
    assert client.get("/api/campagnes").json() == []
    [jetee] = client.get("/api/corbeille").json()
    assert jetee["nom"] == "neo-tokyo" and len(jetee["date"]) == 16
    assert (donnees_jeu / "corbeille" / jetee["id"] / "sauvegarde.json").is_file()
    assert donnees.lire_journal(donnees_jeu)[-1]["type"] == "campagne"


@pytest.mark.parametrize("nom", ["inconnue", "..", "..%2Fcorbeille", "a b"])
def test_une_campagne_qui_n_existe_pas_n_est_pas_touchee(client, nom):
    assert client.post(f"/api/campagnes/{nom}/corbeille").status_code in (404, 405)


def test_restaurer_remet_la_campagne_et_refuse_un_doublon(client):
    campagne_en_cours("neo-tokyo")
    client.post("/api/campagnes/neo-tokyo/corbeille")
    [jetee] = client.get("/api/corbeille").json()
    assert client.post(f"/api/corbeille/{jetee['id']}/restaurer").json() == {"nom": "neo-tokyo"}
    assert [c["nom"] for c in client.get("/api/campagnes").json()] == ["neo-tokyo"]
    # Une autre campagne du même nom est jetée, puis on tente de restaurer l'ancienne par-dessus
    campagne.supprimer("neo-tokyo")
    campagne_en_cours("neo-tokyo")
    [jetee] = client.get("/api/corbeille").json()
    assert client.post(f"/api/corbeille/{jetee['id']}/restaurer").status_code == 409
    assert client.get("/api/corbeille").json() != []


def test_on_ne_restaure_que_ce_qui_est_dans_la_corbeille(client, donnees_jeu):
    assert client.post("/api/corbeille/inconnue_20260101-000000/restaurer").status_code == 404
    assert client.post("/api/corbeille/..%2Fcampagnes/restaurer").status_code in (404, 405)


def test_vider_la_corbeille_demande_une_confirmation(client):
    campagne_en_cours("a")
    client.post("/api/campagnes/a/corbeille")
    assert client.post("/api/corbeille/vider", json={}).status_code == 400
    assert client.post("/api/corbeille/vider", json={"confirme": "oui"}).status_code == 400
    assert len(client.get("/api/corbeille").json()) == 1
    assert client.post("/api/corbeille/vider", json={"confirme": True}).json() == {"effacees": 1}
    assert client.get("/api/corbeille").json() == []


def test_kaito_est_livre_et_ne_se_supprime_pas(client):
    [kaito, *autres] = client.get("/api/personnages").json()
    assert kaito["nom"] == "Kaito" and kaito["livre"] is True and autres == []
    assert client.post(f"/api/personnages/{kaito['id']}/supprimer").status_code == 403


def test_un_personnage_du_joueur_se_liste_et_se_supprime(client, donnees_jeu):
    dossier = donnees_jeu / "personnages"
    dossier.mkdir()
    fiche = {"genre": "Cyberpunk", "parcours": "Netrunner", "caracteristiques": {}, "points_parcours": {},
             "points_personnels": {}, "domaines": [], "equipement": {}, "roleplay": {"nom": "Mika", "sexe": "femme"}}
    (dossier / "mika.json").write_text(json.dumps(fiche), encoding="utf-8")
    ids = {p["nom"]: p for p in client.get("/api/personnages").json()}
    assert ids["Mika"]["id"] == "mika.json" and ids["Mika"]["livre"] is False and "Mika" in ids["Mika"]["titre"]
    assert client.post("/api/personnages/mika.json/supprimer").json() == {"nom": "Mika"}
    assert not (dossier / "mika.json").exists()
    assert client.post("/api/personnages/mika.json/supprimer").status_code == 404


def test_un_identifiant_de_personnage_ne_sort_pas_du_dossier(client, donnees_jeu):
    (donnees_jeu / "important.json").write_text("{}", encoding="utf-8")
    assert client.post("/api/personnages/..%2Fimportant.json/supprimer").status_code in (404, 405)
    assert (donnees_jeu / "important.json").exists()


@pytest.mark.skipif(not hasattr(os, "startfile"), reason="l'ouverture du dossier n'existe que sous Windows")
def test_ouvrir_le_dossier_des_donnees_appelle_l_explorateur(client, donnees_jeu, monkeypatch):
    ouverts = []
    monkeypatch.setattr(gestion.os, "startfile", lambda chemin: ouverts.append(chemin))
    assert client.post("/api/donnees/ouvrir").status_code == 200 and ouverts == [donnees_jeu]


def test_rien_ne_se_modifie_par_un_get(client):
    campagne_en_cours("a")
    for chemin in ("/api/campagnes/a/corbeille", "/api/corbeille/vider", "/api/donnees/ouvrir", "/api/personnages/x/supprimer"):
        assert client.get(chemin).status_code in (404, 405)
    assert [c["nom"] for c in client.get("/api/campagnes").json()] == ["a"]
