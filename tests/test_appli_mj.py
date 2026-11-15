"""L'état du MJ retenu sur ce PC, tel que l'interface l'affiche (appli.serveur, route /api/mj)."""

import json

import pytest
from fastapi.testclient import TestClient

from appli import serveur

PORT, JETON = 8765, "jeton-de-test"


@pytest.fixture
def client(tmp_path):
    app = serveur.creer_app(JETON, PORT, racine=tmp_path)
    ouvert = TestClient(app, base_url=f"http://127.0.0.1:{PORT}", follow_redirects=False)
    assert ouvert.get(f"/?j={JETON}").status_code == 303
    return ouvert


def test_sans_profil_aucun_mj_n_est_qualifie(client):
    assert client.get("/api/mj").json() == {"qualifie": False}


def test_avec_un_profil_le_mj_et_son_budget_sont_donnes(client, tmp_path):
    profil = {"modele": "Qwen3.8 27B", "fichier": "x.gguf", "budget_reflexion": 512, "reglages": {"contexte": 16384}}
    (tmp_path / "profil_mj.json").write_text(json.dumps(profil), encoding="utf-8")
    assert client.get("/api/mj").json() == {"qualifie": True, "modele": "Qwen3.8 27B", "budget_reflexion": 512}


@pytest.mark.parametrize("contenu", ["pas du json", "[]", "{}", '{"modele": "X"}'])
def test_un_profil_illisible_ou_incomplet_ne_casse_rien(client, tmp_path, contenu):
    (tmp_path / "profil_mj.json").write_text(contenu, encoding="utf-8")
    assert client.get("/api/mj").json() == {"qualifie": False}
