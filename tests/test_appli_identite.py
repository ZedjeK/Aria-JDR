import re
from pathlib import Path

from appli import identite


def test_noms_derives_du_nom_de_l_appli():
    assert identite.NOM.startswith("Aria ") and identite.EXE == identite.NOM.replace(" ", "-")
    assert identite.DOSSIER == "." + identite.EXE


def test_le_dossier_de_donnees_est_dans_le_profil_et_nulle_part_ailleurs():
    assert identite.dossier_donnees() == Path.home() / identite.DOSSIER


def test_la_version_vient_de_pyproject_et_a_la_forme_x_y_z():
    assert re.fullmatch(r"\d+\.\d+\.\d+", identite.version())
    assert identite.version() != "0.0.0"


def test_sans_port_dans_la_fiche_le_systeme_en_choisit_un():
    assert identite.PORT == (int(identite.PORT_TEXTE) if identite.PORT_TEXTE.isdigit() else 0)
