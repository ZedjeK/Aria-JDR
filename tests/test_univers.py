import copy
import json
from pathlib import Path

import pytest

from aria.reglages import Curseur
from aria.sante_mentale import Choc
from aria.univers import UniversInvalide, charger_univers, univers_depuis_dict, univers_vers_dict
from tests.test_personnage import netrunner

CYBERPUNK = Path(__file__).parent.parent / "univers" / "cyberpunk.json"


def donnees_cyberpunk() -> dict:
    return json.loads(CYBERPUNK.read_text(encoding="utf-8"))


def erreurs_de(modifier) -> list[str]:
    donnees = donnees_cyberpunk()
    modifier(donnees)
    with pytest.raises(UniversInvalide) as exc:
        univers_depuis_dict(donnees, genere=True)
    return exc.value.erreurs


def fiche_kaito() -> dict:
    """La fiche du Netrunner, sans ce que l'univers fournit lui-même."""
    fiche = netrunner()
    for cle in ("parcours", "competences_parcours", "magie_active"):
        fiche.pop(cle)
    return fiche


def test_charger_l_univers_cyberpunk():
    univers = charger_univers(CYBERPUNK)
    assert univers.nom == "Néo-Tokyo 2087"
    assert univers.curseur is Curseur.STANDARD
    assert not univers.magie_active
    assert univers.nom_affiche("Technologie") == "Piratage"
    assert univers.nom_affiche("Esquive") == "Esquive"  # pas renommée
    assert univers.arme("Pistolet lourd Arasaka").bonus.degats == 1
    with pytest.raises(KeyError):
        univers.arme("Sabre laser")


def test_reglages_mentaux_de_l_univers():
    reglages = charger_univers(CYBERPUNK).reglages_mentaux()
    assert reglages.monde_impitoyable
    assert reglages.chocs_banals == frozenset({Choc.VIOLENCE_BRUTALE})


def test_creer_kaito_dans_l_univers():
    kaito = charger_univers(CYBERPUNK).creer_personnage("Netrunner", **fiche_kaito())
    assert kaito.competence("Technologie") == 75
    assert kaito.competence("Cybernétique") == 5  # compétence thématique à sa base
    assert kaito.points_destin == 2  # curseur standard
    assert kaito.pv == kaito.pv_max == 13  # (35 + 45) / 10 + 5 en standard
    assert "Magie" not in kaito.competences


def test_parcours_avec_competence_thematique():
    fiche = fiche_kaito()
    fiche["points_parcours"] = {"Armes à distance": 55, "Corps à corps": 40, "Esquive": 20, "Athlétisme": 30,
                                "Perception": 25, "Intimidation": 40, "Pilotage": 30, "Cybernétique": 60}
    fiche["points_personnels"] = {"Survie": 40, "Persuasion": 30, "Discrétion": 30}
    solo = charger_univers(CYBERPUNK).creer_personnage("Solo", **fiche)
    assert solo.competence("Cybernétique") == 65


def test_parcours_inconnu():
    with pytest.raises(UniversInvalide):
        charger_univers(CYBERPUNK).creer_personnage("Chevalier", **fiche_kaito())


def test_aller_retour_en_json():
    univers = charger_univers(CYBERPUNK)
    assert univers_depuis_dict(univers_vers_dict(univers)) == univers


def test_habillage_d_une_competence_hors_socle():
    erreurs = erreurs_de(lambda d: d["habillage"].update({"Piratage": "Hacking"}))
    assert any("« Piratage »" in e for e in erreurs)


def test_garde_fous_des_competences_thematiques():
    def modifier(d):
        d["competences_thematiques"] = [
            {"nom": "Être génial", "base": 80, "description": "Tout."},
            {"nom": "Médecine", "base": 5, "description": "Doublon du socle."},
            {"nom": "Sans description", "base": 5},
            {"nom": "Quatrième", "base": 5, "description": "Une de trop."},
        ]
    erreurs = erreurs_de(modifier)
    assert any("Au plus 3" in e for e in erreurs)
    assert any("« Être génial » : la base" in e for e in erreurs)
    assert any("« Médecine » existe déjà" in e for e in erreurs)
    assert any("« Sans description » n'a pas de description" in e for e in erreurs)


def test_parcours_invalides():
    def modifier(d):
        d["parcours"]["Mage"] = ["Magie", "Érudition", "Occultisme", "Perception",
                                 "Perspicacité", "Médecine", "Sciences", "Arts"]
        d["parcours"]["Court"] = ["Esquive"]
    erreurs = erreurs_de(modifier)
    assert any("« Mage » utilise une compétence absente : « Magie »" in e for e in erreurs)  # magie désactivée
    assert any("« Court » doit avoir 8" in e for e in erreurs)


def test_armurerie_verifiee():
    def modifier(d):
        d["armes"].append({"nom": "Épée du destin", "competence": "Corps à corps", "degats": "4d20",
                           "portee": "contact", "rarete": "légendaire"})
        d["armures"].append({"nom": "Exo", "protection": 5, "malus": {"Piratage": -20}})
    erreurs = erreurs_de(modifier)
    assert any("Épée du destin" in e and "légendaire" in e for e in erreurs)
    assert any("Exo : malus sur une compétence absente" in e for e in erreurs)


@pytest.mark.parametrize(
    "modifier",
    [
        lambda d: d.update({"curseur": "épique"}),
        lambda d: d.update({"chocs_banals": ["CHOC_INVENTE"]}),
        lambda d: d.pop("genre"),
        lambda d: d["armes"][0].update({"portee": "très loin"}),
    ],
)
def test_fichier_mal_forme(modifier):
    assert any("mal formé" in e for e in erreurs_de(modifier))


def test_le_fichier_d_origine_n_est_pas_modifie():
    avant = donnees_cyberpunk()
    univers_vers_dict(univers_depuis_dict(copy.deepcopy(avant)))
    assert donnees_cyberpunk() == avant
