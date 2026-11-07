"""Un univers composé depuis la bibliothèque, et l'équipement de départ choisi dans les listes (REGLES.md 1.3 et 5)."""

import json

import pytest

from aria import banc
from aria.bibliotheque import charger
from aria.univers import UniversInvalide, charger_univers, univers_depuis_dict
from tests.test_univers import CYBERPUNK, fiche_kaito


@pytest.fixture(scope="module")
def bibliotheque():
    return charger()


def test_neo_tokyo_est_compose_depuis_la_bibliotheque(bibliotheque):
    fichier = json.loads(CYBERPUNK.read_text(encoding="utf-8"))
    compose = bibliotheque.composer("Cyberpunk", False, fichier["nom"], fichier["cadre"], fichier["curseur"],
                                    fichier["monde_impitoyable"], fichier["chocs_banals"])
    assert fichier == compose  # régénérer le fichier si la bibliothèque change
    u = univers_depuis_dict(compose)
    assert len(u.parcours) == 19 and u.parcours["Netrunner"][-1] == "Esquive"
    assert u.descriptions["Solo"].startswith("Mercenaire augmenté")
    assert u.implants and u.vehicules and not u.domaines
    assert u.arme("Pistolet lourd Arasaka").fabricant == "Arasaka"  # les modèles de marque sont là


def test_la_magie_suit_le_reglage(bibliotheque):
    avec = univers_depuis_dict(bibliotheque.composer("Fantasy", True, "Avec"))
    sans = univers_depuis_dict(bibliotheque.composer("Fantasy", False, "Sans"))
    assert avec.domaines and not sans.domaines
    assert len(avec.parcours) > len(sans.parcours)  # les parcours de lanceurs de sorts disparaissent
    assert not avec.implants


def kaito(univers):
    return univers.creer_personnage("Netrunner", **fiche_kaito())


def test_kaito_choisit_dans_les_listes_du_netrunner():
    u = charger_univers(CYBERPUNK)
    perso = kaito(u)
    depart = u.equiper(perso, **banc.EQUIPEMENT_KAITO)
    assert (depart.arme, depart.armure, depart.vehicule) == ("Pistolet silencieux", "Veste renforcée", None)
    assert perso.implants[0]["nom"] == "Neuroport" and perso.sm_max == 48
    assert perso.objets == ["deck", "fausse identité numérique"]


@pytest.mark.parametrize(
    "choix, erreur",
    [
        (dict(arme="Fusil d'assaut"), "n'est pas dans la liste « armes »"),
        (dict(implant="Lames-mantis"), "n'est pas dans la liste « implants »"),
        (dict(vehicule="Moto sportive"), "ne propose rien pour « vehicules »"),
        (dict(objets=["deck"]), "2 objets différents"),
        (dict(objets=["deck", "un tank"]), "2 objets différents"),
    ],
)
def test_un_choix_hors_des_listes_est_refuse(choix, erreur):
    u = charger_univers(CYBERPUNK)
    valides = dict(banc.EQUIPEMENT_KAITO)
    with pytest.raises(UniversInvalide) as e:
        u.equiper(kaito(u), **(valides | choix))
    assert any(erreur in x for x in e.value.erreurs), e.value.erreurs


def test_rien_quand_la_liste_le_permet():
    u = charger_univers(CYBERPUNK)
    depart = u.equiper(kaito(u), arme=None, armure=None, implant="Paume d'interface",
                       objets=["câbles d'interface", "lunettes AR"])
    assert depart.arme is None and depart.armure is None


def test_le_coursier_part_avec_sa_moto():
    u = charger_univers(CYBERPUNK)
    listes = u.equipements["Coursier"]
    assert listes["vehicules"] and all(u.vehicule(v).gabarit in ("léger", "moyen") for v in listes["vehicules"])


@pytest.mark.parametrize(
    "case, option, erreur",
    [
        ("armures", "Armure tactique", "protège plus de 3"),
        ("armes", "Pistolet lourd Arasaka", "d'origine et sans fabricant"),
        ("implants", "Réflexes câblés Kerenzikov", "gamme standard"),
        ("vehicules", "Blindé de transport", "trop lourd"),
        ("armes", "Sabre laser", "Introuvable"),
    ],
)
def test_les_listes_de_depart_sont_verifiees(case, option, erreur):
    donnees = json.loads(CYBERPUNK.read_text(encoding="utf-8"))
    donnees["equipements"]["Netrunner"][case] = [option]
    with pytest.raises(UniversInvalide) as e:
        univers_depuis_dict(donnees)
    assert any(erreur in x for x in e.value.erreurs), e.value.erreurs
