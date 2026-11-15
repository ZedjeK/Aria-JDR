"""Le choix du port au lancement (appli.__main__)."""

import socket

from appli import __main__ as lancement
from appli import identite


def test_le_port_de_la_fiche_est_pris_quand_il_est_libre(monkeypatch):
    monkeypatch.setattr(identite, "PORT", lancement._port_libre())
    assert lancement.choisir_port() == identite.PORT


def test_un_port_occupe_donne_un_autre_port_libre_au_lieu_d_un_echec(monkeypatch):
    with socket.socket() as occupant:
        occupant.bind(("127.0.0.1", 0))
        occupe = occupant.getsockname()[1]
        monkeypatch.setattr(identite, "PORT", occupe)
        choisi = lancement.choisir_port()
    assert choisi != occupe and 1024 <= choisi <= 65535


def test_sans_port_dans_la_fiche_le_systeme_en_choisit_un(monkeypatch):
    monkeypatch.setattr(identite, "PORT", 0)
    assert lancement.choisir_port() > 0
