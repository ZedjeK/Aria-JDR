import json

import pytest

from aria.personnage import Etat
from aria.sante_mentale import Trouble, TypeTrouble
from aria.sauvegarde import Partie, SauvegardeInvalide, charger, partie_vers_dict, sauvegarder
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from tests.test_univers import CYBERPUNK, fiche_kaito


def partie_en_cours() -> Partie:
    """Une partie avec un perso bien abîmé, pour vérifier que tout son état survit à la sauvegarde."""
    univers = charger_univers(CYBERPUNK)
    kaito = univers.creer_personnage("Netrunner", **fiche_kaito())
    kaito.pv = 3
    kaito.sm = 41
    kaito.etat = Etat.INCONSCIENT
    kaito.blessure_grave = True
    kaito.blessure_grave_soignee = True
    kaito.dernier_repos = Moment(2, Periode.APRES_MIDI)
    kaito.derniere_therapie = Moment(1, Periode.NUIT)
    kaito.troubles = [Trouble(TypeTrouble.PARANOIA, 50, "Assister à un massacre")]
    kaito.chocs_vecus = {"MASSACRE": 1}
    kaito.competences_cochees = {"Technologie", "Esquive"}
    kaito.xp = 4
    return Partie(kaito, univers, Moment(2, Periode.NUIT),
                  armes=["Pistolet lourd Arasaka", "Couteau"], arme_en_main="Pistolet lourd Arasaka",
                  armure="Veste renforcée")


def test_sauvegarder_puis_charger(tmp_path):
    partie = partie_en_cours()
    chemin = tmp_path / "parties" / "kaito.json"
    sauvegarder(partie, chemin)
    assert charger(chemin) == partie


def test_fichier_lisible_et_sans_temporaire(tmp_path):
    chemin = tmp_path / "kaito.json"
    sauvegarder(partie_en_cours(), chemin)
    texte = chemin.read_text(encoding="utf-8")
    assert "Néo-Tokyo 2087" in texte  # les accents restent lisibles
    assert '"paranoïa"' in texte
    assert list(tmp_path.iterdir()) == [chemin]


def test_ecraser_une_sauvegarde(tmp_path):
    chemin = tmp_path / "kaito.json"
    partie = partie_en_cours()
    sauvegarder(partie, chemin)
    partie.personnage.pv = 8
    sauvegarder(partie, chemin)
    assert charger(chemin).personnage.pv == 8


def test_format_inconnu(tmp_path):
    donnees = partie_vers_dict(partie_en_cours())
    donnees["format"] = 99
    chemin = tmp_path / "futur.json"
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    with pytest.raises(SauvegardeInvalide):
        charger(chemin)


def test_fichier_corrompu(tmp_path):
    chemin = tmp_path / "corrompu.json"
    chemin.write_text("{ pas du json", encoding="utf-8")
    with pytest.raises(SauvegardeInvalide):
        charger(chemin)
