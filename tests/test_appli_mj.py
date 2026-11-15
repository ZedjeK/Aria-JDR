"""Le MJ retenu sur ce PC, tel que l'interface l'affiche (appli.gestion, route /api/mj)."""

import pytest
from fastapi.testclient import TestClient

from appli import serveur

PORT, JETON = 8765, "jeton-de-test"


def ouvrir(tmp_path, profil, moteur):
    app = serveur.creer_app(JETON, PORT, racine=tmp_path, profil_valide=lambda: profil, moteur=lambda: moteur)
    client = TestClient(app, base_url=f"http://127.0.0.1:{PORT}", follow_redirects=False)
    assert client.get(f"/?j={JETON}").status_code == 303
    return client


def test_sans_profil_aucun_mj_n_est_qualifie_et_on_dit_ou_est_le_serveur(tmp_path):
    absent = tmp_path / "Aria-LLM" / "llama-server.exe"
    reponse = ouvrir(tmp_path, None, absent).get("/api/mj").json()
    assert reponse == {"qualifie": False, "moteur_present": False, "moteur": str(absent)}


def test_avec_un_profil_le_mj_ses_budgets_et_le_serveur_sont_donnes(tmp_path):
    moteur = tmp_path / "llama-server.exe"
    moteur.write_bytes(b"")
    profil = {"modele": "Qwen3.8 27B", "fichier": "x.gguf", "budget_reflexion": 512, "reglages": {"contexte": 16384}}
    reponse = ouvrir(tmp_path, profil, moteur).get("/api/mj").json()
    assert reponse == {"qualifie": True, "modele": "Qwen3.8 27B", "fichier": "x.gguf", "budget_reflexion": 512,
                       "budget_generateur": 512, "moteur_present": True, "moteur": str(moteur)}


def test_le_budget_du_generateur_est_celui_du_banc_quand_il_a_tourne(tmp_path):
    profil = {"modele": "M", "budget_reflexion": 256, "budget_generateur": 512}
    assert ouvrir(tmp_path, profil, tmp_path / "x").get("/api/mj").json()["budget_generateur"] == 512


@pytest.mark.parametrize("profil", [{}, {"modele": "X"}, {"budget_reflexion": "beaucoup", "modele": "X"}])
def test_un_profil_incomplet_ne_casse_rien(tmp_path, profil):
    assert ouvrir(tmp_path, profil, tmp_path / "x").get("/api/mj").json()["qualifie"] is False
