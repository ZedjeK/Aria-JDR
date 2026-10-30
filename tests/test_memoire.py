import pytest

from aria.campagne import Campagne
from aria.memoire import MORT, Memoire, MemoireRefusee


def test_les_pnj_survivent_a_la_relecture(tmp_path):
    memoire = Memoire(Campagne(tmp_path))
    memoire.noter_pnj("doc_mori", "Doc Mori", "charcudoc du quartier", "méfiant")
    memoire.noter_pnj("doc_mori", "Doc Mori", "charcudoc du quartier", "amical, il doit un service à Kaito")
    memoire.marquer_etat("doc_mori", MORT)
    texte = (tmp_path / "pnj.md").read_text(encoding="utf-8")
    assert "## Doc Mori (doc_mori)" in texte and "- État : mort" in texte
    relue = Memoire(Campagne(tmp_path))
    assert relue.pnj["doc_mori"].attitude == "amical, il doit un service à Kaito"
    assert relue.est_mort("doc_mori")


def test_noter_un_pnj_ne_le_ressuscite_pas():
    memoire = Memoire()
    memoire.noter_pnj("ganger", "Ganger", "voyou", "hostile")
    memoire.marquer_etat("ganger", MORT)
    memoire.noter_pnj("ganger", "Ganger", "voyou", "repenti")
    assert memoire.est_mort("ganger")


def test_les_fils_s_ouvrent_et_se_closent(tmp_path):
    memoire = Memoire(Campagne(tmp_path))
    memoire.ouvrir_fil("dette_mori", "Doc Mori doit un service à Kaito.")
    with pytest.raises(MemoireRefusee, match="existe déjà"):
        memoire.ouvrir_fil("dette_mori", "Encore.")
    with pytest.raises(MemoireRefusee, match="dette_mori"):
        memoire.clore_fil("colis", "Livré.")
    memoire.clore_fil("dette_mori", "Mori a recousu Kaito gratuitement.")
    with pytest.raises(MemoireRefusee, match="déjà clos"):
        memoire.clore_fil("dette_mori", "Encore.")
    relue = Memoire(Campagne(tmp_path))
    assert relue.fils["dette_mori"].issue == "Mori a recousu Kaito gratuitement."


def test_le_moteur_valide_ce_que_le_mj_ecrit():
    memoire = Memoire()
    with pytest.raises(MemoireRefusee, match="Identifiant invalide"):
        memoire.noter_pnj("Doc Mori", "Doc Mori", "charcudoc", "amical")
    with pytest.raises(MemoireRefusee, match="vide"):
        memoire.ouvrir_fil("colis", "   ")
    with pytest.raises(MemoireRefusee, match="trop long"):
        memoire.noter_pnj("mori", "Mori", "charcudoc " * 30, "amical")
    assert not memoire.pnj and not memoire.fils


def test_un_disque_plein_ne_change_rien(tmp_path, monkeypatch):
    memoire = Memoire(Campagne(tmp_path))

    def disque_plein(*_args, **_kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr("aria.memoire.os.replace", disque_plein)
    with pytest.raises(MemoireRefusee, match="disque plein"):
        memoire.ouvrir_fil("colis", "Livrer un colis.")
    assert not memoire.fils


def test_les_souvenirs_se_relisent(tmp_path):
    campagne = Campagne(tmp_path)
    memoire = Memoire(campagne)
    memoire.ajouter_souvenir("## Jour 1, après-midi — La ruelle\n\nKaito repousse deux gangers.")
    memoire.ajouter_souvenir("## Jour 1, nuit — Chez Mori\n\nMori le recoud.")
    assert Memoire(campagne).souvenirs == memoire.souvenirs
    assert len(memoire.souvenirs) == 2


def test_un_fichier_retouche_a_la_main_reste_lisible(tmp_path):
    (tmp_path / "pnj.md").write_text("# PNJ\n\n## Hana (hana)\n- Rôle : la sœur de Kaito\n- Attitude : aimante\n\n"
                                     "## Section cassée\nn'importe quoi\n", encoding="utf-8")
    memoire = Memoire(Campagne(tmp_path))
    assert list(memoire.pnj) == ["hana"]


def test_le_bloc_est_borne():
    memoire = Memoire()
    assert memoire.bloc() == ""
    memoire.ouvrir_fil("dette", "Effacer la dette envers Arasaka.")
    memoire.ouvrir_fil("colis", "Livrer un colis.")
    memoire.clore_fil("colis", "Livré.")
    memoire.noter_pnj("mori", "Doc Mori", "charcudoc", "amical")
    for jour in range(1, 31):
        memoire.ajouter_souvenir(f"## Jour {jour}, matin — Scène {jour}\n\n" + "Il se passe des choses. " * 10)
    bloc = memoire.bloc(limite=2000)
    assert len(bloc) <= 2000
    assert "- dette : Effacer la dette" in bloc and "colis" not in bloc
    assert "Doc Mori (mori) — charcudoc — attitude : amical" in bloc
    assert "#### Jour 30, matin — Scène 30" in bloc  # le plus récent, en entier
    assert "souvenirs plus anciens" in bloc
    assert bloc.index("Scène 29") < bloc.index("Scène 30")
