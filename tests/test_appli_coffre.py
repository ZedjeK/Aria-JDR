import sys

import pytest

from appli import coffre

windows = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI n'existe que sous Windows")


@pytest.mark.parametrize("nom", ["", "Majuscule", "a b", "../dehors", "a/b", "-debut", "fin-", "x" * 65])
def test_un_nom_de_secret_qui_pourrait_sortir_du_dossier_est_refuse(tmp_path, nom):
    with pytest.raises(ValueError):
        coffre.chemin(nom, tmp_path)


@windows
def test_un_secret_se_retrouve_et_n_est_pas_en_clair_sur_le_disque(tmp_path):
    coffre.enregistrer("jeton-github", "s3cr3t-très-secret", tmp_path)
    assert coffre.lire("jeton-github", tmp_path) == "s3cr3t-très-secret"
    assert b"s3cr3t" not in coffre.chemin("jeton-github", tmp_path).read_bytes()


@windows
def test_un_secret_absent_ou_abime_donne_none(tmp_path):
    assert coffre.lire("absent", tmp_path) is None
    coffre.enregistrer("abime", "x", tmp_path)
    coffre.chemin("abime", tmp_path).write_bytes(b"pas du dpapi")
    assert coffre.lire("abime", tmp_path) is None


@windows
def test_supprimer_est_sans_effet_si_le_secret_n_existe_pas(tmp_path):
    coffre.enregistrer("a-supprimer", "x", tmp_path)
    coffre.supprimer("a-supprimer", tmp_path)
    coffre.supprimer("a-supprimer", tmp_path)
    assert coffre.lire("a-supprimer", tmp_path) is None
