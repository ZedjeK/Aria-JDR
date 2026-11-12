"""Les personnages prédéfinis : préparés hors campagne pour un genre, puis posés dans l'univers d'une campagne."""

import random
from dataclasses import replace

import pytest

from aria import __main__ as lanceur
from aria import chemins, jeu, personnages
from aria.bibliotheque import charger
from aria.campagne import Campagne
from aria.creation import Brouillon, EtapeInvalide, proposer_chiffres
from aria.generateur import choix_par_defaut
from aria.personnages import KAITO, brouillon_dans, enregistrer, lister, univers_de_base
from test_amorce import appel, generation
from test_creation import ROLEPLAY
from test_lanceur import donnees, entrees  # noqa: F401 (donnees est une fixture)
from test_table import ServeurScripte


@pytest.fixture(scope="module")
def cyberpunk():
    return univers_de_base("Cyberpunk")


def yuki(univers, parcours="Solo"):
    b = proposer_chiffres(Brouillon(univers), random.Random(3), parcours)
    b.fixer("roleplay", ROLEPLAY | {"sexe": "femme"})
    return b


def test_enregistrer_et_relire(tmp_path, monkeypatch, cyberpunk):
    monkeypatch.setattr(chemins, "DONNEES", tmp_path)
    assert lister() == [KAITO] and "livré avec le jeu" in KAITO.titre()
    pret = enregistrer(yuki(cyberpunk), "Cyberpunk")
    autre = enregistrer(yuki(cyberpunk), "Cyberpunk")  # même nom : un autre fichier
    assert pret.fichier.name == "yuki-sato.json" and autre.fichier.name == "yuki-sato-2.json"
    (personnages.dossier() / "abime.json").write_text("{", encoding="utf-8")
    relus = lister("Cyberpunk")
    assert [p.nom for p in relus] == ["Kaito", "Yuki Sato", "Yuki Sato"] and lister("Fantasy") == []
    assert relus[1].titre() == "Yuki Sato — femme, Solo (Cyberpunk)" and relus[1].fiche == pret.fiche
    personnages.supprimer(relus[1])
    personnages.supprimer(KAITO)  # sans effet : il est livré avec le jeu
    assert [p.nom for p in lister()] == ["Kaito", "Yuki Sato"]


def test_poser_un_personnage_dans_un_univers(cyberpunk):
    brouillon, notes = brouillon_dans(cyberpunk, KAITO)
    perso, depart = brouillon.finaliser()
    assert not notes and perso.nom == "Kaito" and perso.parcours == "Netrunner" and perso.sexe == "homme"
    assert depart.arme == "Pistolet silencieux" and perso.objets == ["deck", "fausse identité numérique"]
    # Un cadre qui a renommé son métier et son arme : le personnage les retrouve sous leur nouveau nom
    listes = dict(cyberpunk.equipements["Netrunner"])
    listes["armes"] = ["Type-9 muet" if a == "Pistolet silencieux" else a for a in listes["armes"]]
    renomme = replace(
        cyberpunk,
        parcours={("Plongeur" if p == "Netrunner" else p): c for p, c in cyberpunk.parcours.items()},
        equipements={("Plongeur" if p == "Netrunner" else p): (listes if p == "Netrunner" else e)
                     for p, e in cyberpunk.equipements.items()},
        origines={"Plongeur": "Netrunner", "Type-9 muet": "Pistolet silencieux"})
    brouillon, notes = brouillon_dans(renomme, KAITO)
    assert not notes and brouillon.parcours == "Plongeur" and brouillon.equipement["arme"] == "Type-9 muet"
    # Une arme que le cadre a retirée : l'équipement est reproposé, et on le dit
    fiche = dict(KAITO.fiche, equipement=dict(KAITO.fiche["equipement"], arme="Canon orbital"))
    brouillon, notes = brouillon_dans(cyberpunk, replace(KAITO, fiche=fiche), random.Random(1))
    assert len(notes) == 1 and brouillon.equipement["arme"] in cyberpunk.equipements["Netrunner"]["armes"]
    with pytest.raises(EtapeInvalide, match="Parcours inconnu"):
        brouillon_dans(univers_de_base("Fantasy"), KAITO)


def partie(tmp_path, serveur, reponses, sortie, predefini):
    choix = choix_par_defaut(charger(), "Cyberpunk", "Osaka 2091", "Osaka sous la pluie.", 2091)
    reponses = iter(reponses)
    return jeu.Jeu(serveur, budget=128, entree=lambda _: next(reponses), sortie=sortie.append,
                   campagne=Campagne(tmp_path), choix=choix, creer=True, predefini=predefini)


def test_une_campagne_avec_un_personnage_predefini(tmp_path):
    # Le LLM veut retirer le Netrunner : le métier du personnage est gardé quand même
    script = generation()
    script[7] = [{"name": "trier_parcours", "arguments": {"retirer": ["Netrunner"], "renommer": []}}]
    sortie = []
    jouee = partie(tmp_path, ServeurScripte(*script, appel()), ["", ""], sortie, KAITO)
    k = jouee.session.personnage
    assert k.nom == "Kaito" and "Netrunner" in jouee.session.univers.parcours
    assert any("=== Ton personnage ===" in ligne for ligne in sortie)
    assert not any("Création de ton personnage" in ligne for ligne in sortie)  # pas de création guidée


def test_un_personnage_qui_ne_convient_pas_est_recree(tmp_path):
    mage = replace(KAITO, parcours="Mage de bataille")
    sortie = []
    # il ne peut pas vivre ici : création guidée (« tout », sexe, les quatre lignes, l'allure, valider), puis l'amorce
    jouee = partie(tmp_path, ServeurScripte(*generation(), "Hmm.", "Hmm."),
                   ["tout", "f", "Yuki", "Sa dette", "Sa mère", "Curieuse", "", "", ""], sortie, mage)
    assert jouee.session.personnage.nom == "Yuki"
    assert any("ne peut pas vivre dans cet univers" in ligne for ligne in sortie)


def test_le_menu_des_personnages(donnees):  # noqa: F811
    lignes = []
    # créer une Solo sans le MJ : genre 7, pas de MJ, « tout », femme, les quatre lignes, pas d'allure, valider
    lanceur.menu(entrees("3", "n", "7", "n", "tout", "f", "Yuki Sato", "Sa dette", "Sa mère", "Curieuse", "", "",
                         "x", "s 1", "s 2", "n", "", "5"), lignes.append)
    texte = "\n".join(lignes)
    assert "1. Kaito — homme, Netrunner (Cyberpunk) · livré avec le jeu" in texte and "2. Yuki Sato — femme" in texte
    assert "Yuki Sato est prêt" in texte and "il ne se supprime pas" in texte and "« n », « s »" in texte
    assert [p.nom for p in lister()] == ["Kaito", "Yuki Sato"]
    # la prendre pour une nouvelle campagne
    lanceur.menu(entrees("1", "osaka", "7", "", "", "9", "2", "5"), lignes.append)
    assert donnees[0][3].nom == "Yuki Sato" and donnees[0][1].genre == "Cyberpunk"
    lanceur.menu(entrees("3", "s 2", "o", "", "5"), lignes.append)
    assert lister() == [KAITO]


def test_abandonner_la_creation_d_un_personnage(donnees):  # noqa: F811
    lignes = []
    lanceur.menu(entrees("3", "n", "7", "n", "q", "", "5"), lignes.append)
    assert "Création abandonnée." in lignes and lister() == [KAITO]
