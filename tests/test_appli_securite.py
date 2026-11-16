import json

import pytest
from fastapi.testclient import TestClient

from appli import donnees, securite, serveur

PORT, JETON = 8765, "jeton-de-test"


@pytest.fixture
def client(tmp_path):
    app = serveur.creer_app(JETON, PORT, racine=tmp_path, arreter=lambda: None)
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}", follow_redirects=False)


@pytest.fixture
def ouvert(client):
    """Un client qui est passé par l'adresse d'ouverture : il a le cookie."""
    assert client.get(f"/?j={JETON}").status_code == 303
    return client


def test_sans_jeton_rien_ne_s_ouvre(client):
    assert client.get("/").status_code == 403
    assert client.get("/api/etat").status_code == 403
    assert client.get("/app.js").status_code == 403


def test_un_mauvais_jeton_est_refuse_et_ne_donne_pas_de_cookie(client):
    reponse = client.get("/?j=autre")
    assert reponse.status_code == 403 and securite.COOKIE not in reponse.headers.get("set-cookie", "")


def test_le_bon_jeton_donne_un_cookie_reserve_et_redirige_sans_le_jeton(client):
    reponse = client.get(f"/?j={JETON}")
    assert reponse.status_code == 303 and reponse.headers["location"] == "/"
    cookie = reponse.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and JETON in reponse.headers["set-cookie"]


def test_apres_l_ouverture_l_interface_et_l_api_repondent(ouvert):
    assert ouvert.get("/").status_code == 200 and "<html" in ouvert.get("/").text
    assert ouvert.get("/app.css").status_code == 200
    assert ouvert.get("/logo.svg").status_code == 200
    etat = ouvert.get("/api/etat").json()
    assert etat["version"] != "0.0.0" and etat["nom"].startswith("Aria ")


@pytest.mark.parametrize("hote", ["evil.example", "127.0.0.1:9999", "127.0.0.1", "localhost"])
def test_un_autre_hote_est_refuse_meme_avec_le_cookie(ouvert, hote):
    assert ouvert.get("/api/etat", headers={"host": hote}).status_code == 403


def test_localhost_avec_le_bon_port_est_accepte(ouvert):
    assert ouvert.get("/api/etat", headers={"host": f"localhost:{PORT}"}).status_code == 200


def test_une_autre_origine_est_refusee_meme_en_lecture(ouvert):
    assert ouvert.get("/api/etat", headers={"origin": "https://evil.example"}).status_code == 403
    assert ouvert.put("/api/reglages", json={}, headers={"origin": "https://evil.example"}).status_code == 403
    assert ouvert.get("/api/etat", headers={"origin": f"http://127.0.0.1:{PORT}"}).status_code == 200


def test_aucun_cors_n_est_ouvert(ouvert):
    reponse = ouvert.get("/api/etat", headers={"origin": f"http://127.0.0.1:{PORT}"})
    assert not any(nom.lower().startswith("access-control-") for nom in reponse.headers)


def test_les_en_tetes_de_securite_sont_la(ouvert):
    entetes = ouvert.get("/api/etat").headers
    assert entetes["x-content-type-options"] == "nosniff" and "default-src 'self'" in entetes["content-security-policy"]
    assert entetes["cache-control"] == "no-store"


def test_la_documentation_automatique_de_l_api_n_est_pas_exposee(ouvert):
    for chemin in ("/docs", "/redoc", "/openapi.json"):
        assert ouvert.get(chemin).status_code == 404


def test_enregistrer_les_reglages_sauvegarde_l_ancien_fichier_et_ecrit_au_journal(ouvert, tmp_path):
    donnees.enregistrer_reglages(donnees.Reglages(fond=donnees.Fond(vitesse="lente")), tmp_path)
    nouveau = {"fond": {"actif": False, "vitesse": "rapide", "minimum": 9, "maximum": 3}}
    reponse = ouvert.put("/api/reglages", json=nouveau)
    assert reponse.status_code == 200
    assert reponse.json()["fond"] == {"actif": False, "vitesse": "rapide", "minimum": 3, "maximum": 9}
    assert donnees.charger_reglages(tmp_path).fond.vitesse == "rapide"
    copies = list((tmp_path / donnees.DOSSIER_SAUVEGARDES).glob("*_reglages.json"))
    assert len(copies) == 1 and json.loads(copies[0].read_text(encoding="utf-8"))["fond"]["vitesse"] == "lente"
    assert donnees.lire_journal(tmp_path)[-1]["type"] == "réglages"


def test_aucune_modification_ne_passe_par_un_get(ouvert):
    assert ouvert.get("/api/quitter").status_code in (404, 405)


def test_quitter_appelle_l_arret(tmp_path):
    arrets = []
    app = serveur.creer_app(JETON, PORT, racine=tmp_path, arreter=lambda: arrets.append(1))
    client = TestClient(app, base_url=f"http://127.0.0.1:{PORT}", follow_redirects=False)
    client.get(f"/?j={JETON}")
    assert client.post("/api/quitter").status_code == 200 and arrets == [1]


def test_enregistrer_le_fond_ne_remet_pas_les_reglages_de_combat_a_zero(ouvert, tmp_path):
    donnees.enregistrer_reglages(donnees.Reglages(combat=donnees.Combat("aucun", True, False)), tmp_path)
    reponse = ouvert.put("/api/reglages", json={"fond": {"actif": False}})
    assert reponse.json()["combat"] == {"recit": "aucun", "pvExacts": True, "choisirSaDefense": False,
                                        "pnjParLeLlm": False}
    ouvert.put("/api/reglages", json={"combat": {"recit": "fin", "pvExacts": False, "choisirSaDefense": True}})
    enregistres = donnees.charger_reglages(tmp_path)
    assert enregistres.combat == donnees.Combat("fin", False, True) and not enregistres.fond.actif
