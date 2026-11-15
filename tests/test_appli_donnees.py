import json
from datetime import datetime

import pytest

from appli import donnees


def test_assurer_cree_le_dossier_et_ses_sous_dossiers(tmp_path):
    dossier = donnees.assurer(tmp_path / "donnees")
    for sous_dossier in (donnees.DOSSIER_SAUVEGARDES, donnees.DOSSIER_CACHE, donnees.DOSSIER_SECRETS):
        assert (dossier / sous_dossier).is_dir()


def test_reglages_par_defaut_sans_fichier(tmp_path):
    r = donnees.charger_reglages(tmp_path)
    assert r.fond.actif and r.fond.vitesse == "normale" and (r.fond.minimum, r.fond.maximum) == (2, 5)


def test_reglages_aller_retour_avec_les_cles_en_francais(tmp_path):
    r = donnees.Reglages(fond=donnees.Fond(actif=False, vitesse="rapide", minimum=3, maximum=9))
    donnees.enregistrer_reglages(r, tmp_path)
    brut = json.loads((tmp_path / donnees.FICHIER_REGLAGES).read_text(encoding="utf-8"))
    assert brut["fond"] == {"actif": False, "vitesse": "rapide", "minimum": 3, "maximum": 9}
    assert donnees.charger_reglages(tmp_path) == r


def test_les_bornes_du_fond_sont_ramenees_entre_1_et_12_et_remises_dans_l_ordre():
    assert donnees.Fond(minimum=0, maximum=99).assaini().minimum == 1
    assert donnees.Fond(minimum=0, maximum=99).assaini().maximum == 12
    inverse = donnees.Fond(minimum=9, maximum=3).assaini()
    assert (inverse.minimum, inverse.maximum) == (3, 9)
    assert donnees.Fond(vitesse="vitesse-inconnue").assaini().vitesse == "normale"


@pytest.mark.parametrize("contenu", ["pas du json", "[]", '{"fond": null}', '{"fond": {"minimum": "beaucoup"}}', ""])
def test_un_fichier_modifie_a_la_main_ne_casse_rien(tmp_path, contenu):
    (tmp_path / donnees.FICHIER_REGLAGES).write_text(contenu, encoding="utf-8")
    r = donnees.charger_reglages(tmp_path)
    assert 1 <= r.fond.minimum <= r.fond.maximum <= 12


def test_le_journal_garde_les_500_dernieres_operations(tmp_path):
    for n in range(donnees.JOURNAL_MAX + 25):
        donnees.noter("essai", f"opération {n}", tmp_path, datetime(2026, 1, 1))
    entrees = donnees.lire_journal(tmp_path)
    assert len(entrees) == donnees.JOURNAL_MAX
    assert entrees[0]["bilan"] == "opération 25" and entrees[-1]["bilan"] == f"opération {donnees.JOURNAL_MAX + 24}"


def test_un_journal_qui_ne_s_ecrit_pas_ne_fait_pas_echouer_l_operation(tmp_path):
    fichier = tmp_path / "pas-un-dossier"
    fichier.write_text("x", encoding="utf-8")
    donnees.noter("essai", "bilan", fichier)  # ne lève pas
    assert donnees.lire_journal(fichier) == []


def test_sauvegarder_copie_sans_jamais_ecraser(tmp_path):
    source = tmp_path / "reglages.json"
    source.write_text("{}", encoding="utf-8")
    quand = datetime(2026, 11, 15, 12, 0, 0)
    premiere = donnees.sauvegarder(source, tmp_path, quand)
    seconde = donnees.sauvegarder(source, tmp_path, quand)
    assert premiere != seconde and premiere.read_text() == seconde.read_text() == "{}"
    assert premiere.name == "2026-11-15_12-00-00_reglages.json" and seconde.name.endswith("_2.json")


def test_sauvegarder_un_fichier_absent_leve_une_erreur(tmp_path):
    with pytest.raises(FileNotFoundError):
        donnees.sauvegarder(tmp_path / "absent.json", tmp_path)
