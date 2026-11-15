import sys
import uuid

import pytest

from appli import instance

windows = pytest.mark.skipif(sys.platform != "win32", reason="le mutex nommé n'existe que sous Windows")


@windows
def test_un_seul_exemplaire_a_la_fois_puis_la_place_se_rend():
    nom = f"Local\\essai-{uuid.uuid4().hex}"
    premier, second = instance.Instance(nom), instance.Instance(nom)
    assert premier.prendre() is True
    assert second.prendre() is False
    premier.rendre()
    assert second.prendre() is True
    second.rendre()


def test_l_adresse_porte_le_port_et_le_jeton():
    assert instance.adresse(8123, "abc") == "http://127.0.0.1:8123/?j=abc"


@windows
def test_ramener_sans_instance_publiee_dit_faux(tmp_path):
    assert instance.ramener(tmp_path) is False


@windows
def test_ramener_ouvre_l_adresse_de_l_instance_publiee(tmp_path, monkeypatch):
    ouvertes = []
    monkeypatch.setattr(instance.webbrowser, "open", lambda adresse: ouvertes.append(adresse) or True)
    instance.publier(8123, "jeton-xyz", tmp_path)
    assert instance.ramener(tmp_path) is True and ouvertes == ["http://127.0.0.1:8123/?j=jeton-xyz"]
    instance.retirer(tmp_path)
    assert instance.ramener(tmp_path) is False
