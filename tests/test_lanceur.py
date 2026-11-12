from aria import __main__ as lanceur
from aria import banc, chemins, llm


def entrees(*reponses):
    file = iter(reponses)
    return lambda _invite="": next(file)


def test_le_llm_a_cote_du_jeu_passe_en_premier(tmp_path, monkeypatch):
    monkeypatch.setattr(chemins, "RACINE", tmp_path)
    assert chemins.dossier_llm().parent != tmp_path
    (tmp_path / "Aria-LLM").mkdir()
    assert chemins.dossier_llm() == tmp_path / "Aria-LLM"


def test_le_menu_se_quitte(tmp_path, monkeypatch):
    monkeypatch.setattr(chemins, "DONNEES", tmp_path / ".Aria-JDR")
    lignes = []
    lanceur.menu(entrees("7", "5"), lignes.append)
    assert "Choisis de 1 à 5." in lignes
    assert (tmp_path / ".Aria-JDR").is_dir()


def test_sans_serveur_pas_de_mj(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "MOTEUR", tmp_path / "llama-server.exe")
    lignes = []
    assert not lanceur.mj_disponible(entrees(), lignes.append)
    assert "introuvable" in lignes[0]


def test_sans_profil_le_banc_est_propose(tmp_path, monkeypatch):
    (tmp_path / "llama-server.exe").touch()
    monkeypatch.setattr(llm, "MOTEUR", tmp_path / "llama-server.exe")
    monkeypatch.setattr(banc, "profil_valide", lambda: None)
    qualifie = []
    monkeypatch.setattr(banc, "qualifier", lambda afficher: qualifie.append(True) or {"modele": "M"})
    assert not lanceur.mj_disponible(entrees("n"), print)
    assert not qualifie
    assert lanceur.mj_disponible(entrees("o"), print)
    assert qualifie


# --- Le menu des campagnes ------------------------------------------------------------------------------

import os
import random
import shutil

import pytest

from aria import campagne, jeu
from aria.campagne import Campagne
from aria.creation import Brouillon, proposer_chiffres
from aria.sauvegarde import Partie, sauvegarder
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from tests.test_univers import CYBERPUNK


@pytest.fixture
def donnees(tmp_path, monkeypatch):
    """Un dossier .Aria-JDR vide, un MJ qualifié, et les parties lancées notées au lieu d'être jouées."""
    monkeypatch.setattr(chemins, "DONNEES", tmp_path / ".Aria-JDR")
    (tmp_path / "llama-server.exe").touch()
    monkeypatch.setattr(llm, "MOTEUR", tmp_path / "llama-server.exe")
    monkeypatch.setattr(banc, "profil_valide", lambda: {"modele": "M", "fichier": "m.gguf", "budget_reflexion": 512})
    lancees = []
    monkeypatch.setattr(jeu, "lancer", lambda c, choix=None, surprends_moi=False, predefini=None:
                        lancees.append((c, choix, surprends_moi, predefini)))
    return lancees


def une_campagne(nom, avec_personnage=True, mort=False):
    c = Campagne.nommee(nom)
    c.ouvrir()
    shutil.copy(CYBERPUNK, c.univers)
    if avec_personnage:
        univers = charger_univers(CYBERPUNK)
        b = proposer_chiffres(Brouillon(univers), random.Random(1), "Solo")
        b.fixer("roleplay", {"nom": "Yuki Sato", "motivation": "m", "lien": "l", "defaut": "d"})
        perso, _ = b.finaliser()
        if mort:
            perso.etat = lanceur.Etat.MORT
        sauvegarder(Partie(perso, univers, Moment(3, Periode.NUIT)), c.sauvegarde)
    return c


def test_une_nouvelle_campagne_par_le_menu(donnees):
    lignes = []
    lanceur.menu(entrees("1", "Ça !", "Osaka 2091", "99", "7", "Osaka 2091", "Osaka sous la pluie.", "an", "2091",
                         "réaliste", "", "5"), lignes.append)
    (c, choix, surprends_moi, predefini), = donnees
    assert predefini is None  # Entrée : le personnage sera créé pour cette campagne
    assert c.dossier == chemins.DONNEES / "campagnes" / "osaka-2091" and not surprends_moi
    assert (choix.genre, choix.nom, choix.cadre, choix.annee, choix.curseur) == (
        "Cyberpunk", "Osaka 2091", "Osaka sous la pluie.", 2091, "réaliste")
    assert sum("✗" in ligne for ligne in lignes) == 3  # le nom, le genre et l'année refusés une fois chacun
    assert any("Fantasy (contenu encore léger)" in ligne for ligne in lignes)


def test_surprends_moi_et_les_valeurs_du_genre(donnees):
    lanceur.menu(entrees("1", "essai", "7", "s", "", "", "1", "essai2", "1", "", "", "5"), lambda _: None)
    (_, choix, surprends_moi, _), (_, fantasy, sans_surprise, _) = donnees
    assert surprends_moi and choix.curseur == "standard" and not sans_surprise
    assert fantasy.genre == "Fantasy" and fantasy.nom == "Fantasy" and fantasy.magie
    une_campagne("essai")
    lignes = []
    lanceur.menu(entrees("1", "essai", "", "5"), lignes.append)  # le nom est pris, puis retour
    assert any("existe déjà" in ligne for ligne in lignes) and len(donnees) == 2


def test_reprendre_et_supprimer(donnees):
    lignes = []
    lanceur.menu(entrees("2", "5"), lignes.append)
    assert any("Aucune campagne" in ligne for ligne in lignes)
    une_campagne("osaka")
    une_campagne("valombre", avec_personnage=False)
    une_campagne("zone", mort=True)
    (campagne.racine() / "abimee").mkdir()
    (campagne.racine() / "abimee" / "sauvegarde.json").write_text("{", encoding="utf-8")
    lignes = []
    lanceur.menu(entrees("2", "9", "2", "5"), lignes.append)
    texte = "\n".join(lignes)
    assert "1. abimee — illisible" in texte
    assert "2. osaka — Néo-Tokyo 2087 (Cyberpunk, standard, sans magie) · Yuki Sato, Solo · jour 3, nuit" in texte
    assert "3. valombre —" in texte and "création du personnage à finir" in texte and "Yuki Sato, Solo · mort" in texte
    assert [lancee[0].dossier.name for lancee in donnees] == ["osaka"] and donnees[0][1] is None
    lanceur.menu(entrees("2", "s 2", "n", "s 2", "o", "", "5"), lignes.append)
    assert campagne.noms() == ["abimee", "valombre", "zone"] and len(campagne.jetees()) == 1


def test_la_corbeille(donnees):
    une_campagne("osaka")
    une_campagne("zone")
    campagne.supprimer("osaka")
    campagne.supprimer("zone")
    une_campagne("zone")  # une nouvelle campagne a repris le nom
    lignes = []
    lanceur.menu(entrees("4", "4", "2", "1", "vider", "n", "", "6", "5"), lignes.append)
    assert campagne.noms() == ["osaka", "zone"] and len(campagne.jetees()) == 1  # osaka restaurée, zone refusée
    assert any("existe déjà" in ligne for ligne in lignes)
    lanceur.menu(entrees("4", "4", "vider", "o", "4", "6", "5"), lignes.append)
    assert campagne.jetees() == [] and "La corbeille est vide." in "\n".join(lignes)
    assert campagne.noms() == ["osaka", "zone"]  # vider ne touche que la corbeille


def test_les_reglages(donnees, monkeypatch):
    ouverts = []
    monkeypatch.setattr(os, "startfile", ouverts.append, raising=False)
    lignes = []
    lanceur.menu(entrees("4", "1", "3", "9", "6", "5"), lignes.append)
    texte = "\n".join(lignes)
    assert "Modèle : M (m.gguf)" in texte and "512 jetons" in texte
    assert ouverts == [chemins.DONNEES] and f"Dossier des données : {chemins.DONNEES}" in texte
    assert not donnees and "Choisis de 1 à 6." in texte


def test_le_nom_d_une_campagne():
    assert campagne.nom_valide("  Osaka 2091 ") == "osaka-2091" and campagne.nom_valide("ma_campagne") == "ma-campagne"
    assert campagne.nom_valide("Néo") is None and campagne.nom_valide("") is None and campagne.nom_valide("x" * 41) is None
    assert campagne.nom_valide("../ailleurs") is None
