from aria import __main__ as lanceur
from aria import banc, chemins, llm


def entrees(*reponses):
    file = iter(reponses)
    return lambda _invite="": next(file)


def test_le_llm_a_cote_du_jeu_passe_en_premier(tmp_path, monkeypatch):
    monkeypatch.setattr(chemins, "RACINE", tmp_path)
    assert chemins.dossier_llm().parent != tmp_path
    (tmp_path / "Aria-LLM").mkdir()
    assert chemins.dossier_llm() == tmp_path / "Aria-LLM"


def test_le_menu_se_quitte(tmp_path, monkeypatch):
    monkeypatch.setattr(chemins, "PARTIES", tmp_path / "parties")
    lignes = []
    lanceur.menu(entrees("7", "4"), lignes.append)
    assert "Choisis 1, 2, 3 ou 4." in lignes
    assert (tmp_path / "parties").is_dir()


def test_sans_serveur_pas_de_mj(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "MOTEUR", tmp_path / "llama-server.exe")
    lignes = []
    assert not lanceur.mj_disponible(entrees(), lignes.append)
    assert "introuvable" in lignes[0]


def test_sans_profil_le_banc_est_propose(tmp_path, monkeypatch):
    (tmp_path / "llama-server.exe").touch()
    monkeypatch.setattr(llm, "MOTEUR", tmp_path / "llama-server.exe")
    monkeypatch.setattr(banc, "profil_valide", lambda: None)
    qualifie = []
    monkeypatch.setattr(banc, "qualifier", lambda afficher: qualifie.append(True) or {"modele": "M"})
    assert not lanceur.mj_disponible(entrees("n"), print)
    assert not qualifie
    assert lanceur.mj_disponible(entrees("o"), print)
    assert qualifie
