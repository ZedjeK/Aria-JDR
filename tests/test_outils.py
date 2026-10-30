"""Les outils du MJ, appelés comme le ferait le LLM : par leur nom, avec des arguments JSON."""

import json

import pytest

from aria.des import DesTruques
from aria.outils import OUTILS, Session
from aria.personnage import Etat
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from tests.test_univers import CYBERPUNK, fiche_kaito


def session(*des, **options) -> Session:
    """Kaito à Néo-Tokyo (23 PV, Esquive 50, Piratage 75), avec des dés truqués."""
    univers = charger_univers(CYBERPUNK)
    kaito = univers.creer_personnage("Netrunner", **fiche_kaito())
    options.setdefault("arme", "Pistolet lourd Arasaka")
    options.setdefault("armure", "Veste renforcée")
    return Session(univers, kaito, DesTruques(*des), **options)


def ganger(s: Session, identifiant="ganger", **profil):
    arguments = {"identifiant": identifiant, "nom": "Ganger", "camp": "ennemis", "combat": 45, "pv": 10,
                 "arme": "Couteau", "dexterite": 55} | profil
    assert "erreur" not in s.appeler("creer_pnj", arguments)


# --- Catalogue et garde-fous ------------------------------------------------------------------

def test_schemas_au_format_openai():
    schemas = session().schemas()
    assert {s["function"]["name"] for s in schemas} == set(OUTILS)
    for schema in schemas:
        assert schema["type"] == "function"
        assert schema["function"]["parameters"]["type"] == "object"
        json.dumps(schema)  # sérialisable tel quel pour l'API


def test_les_competences_sont_proposees_avec_les_noms_de_l_univers():
    schema = next(s for s in session().schemas() if s["function"]["name"] == "test_competence")
    enum = schema["function"]["parameters"]["properties"]["competence"]["enum"]
    assert "Piratage" in enum and "Technologie" not in enum
    assert "Cybernétique" in enum


@pytest.mark.parametrize(
    "nom, arguments, morceau_d_erreur",
    [
        ("lancer_un_d20", {}, "Outil inconnu"),
        ("test_competence", {"competence": "Piratage"}, "obligatoire manquant : « difficulte »"),
        ("test_competence", {"competence": "Piratage", "difficulte": "-35"}, "doit être l'une de ces valeurs"),
        ("test_competence", {"competence": "Être génial", "difficulte": "normale"}, "doit être l'une"),
        ("test_competence", {"competence": "Piratage", "difficulte": "normale", "bonus": 50}, "Paramètre inconnu"),
        ("creer_pnj", {"identifiant": "x", "nom": "X", "camp": "ennemis", "combat": 200, "pv": 10}, "au plus 85"),
        ("creer_pnj", {"identifiant": "x", "nom": "X", "camp": "ennemis", "combat": "45", "pv": 10}, "integer"),
        ("attaquer", {"attaquant": "joueur", "cible": "fantome"}, "doit être l'une"),
        ("attaquer", {"attaquant": "joueur", "cible": "joueur"}, "pas soi-même"),
        ("fin_de_round", {}, "Aucun combat en cours"),
        ("forcer_jet", {}, "Aucun test à forcer"),
    ],
)
def test_appels_refuses_sans_planter(nom, arguments, morceau_d_erreur):
    resultat = session().appeler(nom, arguments)
    assert morceau_d_erreur in resultat["erreur"]


def test_arguments_en_texte_json():
    s = session(30)
    assert s.appeler("test_competence", '{"competence": "Piratage", "difficulte": "normale"}')["reussi"]
    assert "JSON invalide" in s.appeler("test_competence", "{pas du json")["erreur"]


def test_le_journal_garde_chaque_appel():
    s = session(30)
    s.appeler("test_competence", {"competence": "Piratage", "difficulte": "normale"})
    s.appeler("lancer_un_d20")
    assert [e["outil"] for e in s.journal] == ["test_competence", "lancer_un_d20"]
    assert "erreur" in s.journal[1]["resultat"]


# --- Hors combat ------------------------------------------------------------------------------

def test_test_de_competence():
    s = session(70)
    r = s.appeler("test_competence", {"competence": "Piratage", "difficulte": "difficile", "pourquoi": "Ouvrir la porte"})
    assert (r["jet"], r["valeur"], r["degre"], r["reussi"]) == (70, 55, "échec", False)


def test_nom_de_socle_accepte_aussi():
    r = session(10).appeler("test_competence", {"competence": "Technologie", "difficulte": "normale"})
    assert r["competence"] == "Piratage" and r["reussi"]


def test_reussite_cochee_pour_la_progression():
    s = session(30)
    s.appeler("test_competence", {"competence": "Piratage", "difficulte": "normale"})
    assert s.personnage.competences_cochees == {"Technologie"}


def test_forcer_le_jet():
    s = session(90, 40)
    s.appeler("test_competence", {"competence": "Piratage", "difficulte": "normale"})
    r = s.appeler("forcer_jet")
    assert r["reussi"] and not r["consequence_grave"]
    assert "erreur" in s.appeler("forcer_jet")  # une seule fois


def test_test_de_caracteristique():
    r = session(80).appeler("test_caracteristique", {"caracteristique": "Intelligence", "difficulte": "normale"})
    assert (r["valeur"], r["reussi"]) == (75, False)


def test_choc():
    r = session(70, 6, 2, 4).appeler("choc", {"choc": "TORTURE"})
    assert (r["gravite"], r["perte"], r["sante_mentale"]) == ("serieux", 6, 44)
    assert r["crise"] == {"type": "paralysie", "rounds": 4}


def test_choc_sans_test_dans_un_monde_impitoyable():
    r = session().appeler("choc", {"choc": "CADAVRE_INCONNU"})
    assert r["test"] is False


def test_soins_par_un_pnj_puis_repos():
    s = session(40, 3, moment=Moment(1, Periode.APRES_MIDI))
    s.personnage.pv = 5
    s.appeler("creer_pnj", {"identifiant": "doc", "nom": "Doc Mori", "camp": "neutres", "combat": 20, "pv": 10,
                            "competences": {"Médecine": 70}})
    assert s.appeler("soigner", {"soigneur": "doc"})["pv"] == 8
    assert s.appeler("repos", {"type": "moyen"})["pv"] == 19  # + la moitié de 23
    assert "erreur" in s.appeler("repos", {"type": "long"})  # pas la nuit
    s.appeler("avancer_temps")
    assert s.appeler("repos", {"type": "long"})["pv"] == 23


def test_competence_de_pnj_hors_bornes():
    r = session().appeler("creer_pnj", {"identifiant": "doc", "nom": "Doc", "camp": "neutres", "combat": 20,
                                        "pv": 10, "competences": {"Médecine": 150}})
    assert "va de 0 à 90" in r["erreur"]


def test_sante_mentale_et_jalon():
    s = session(2, 5, 3, 3, 4)
    s.personnage.sm = 30
    assert s.appeler("recuperer_sante_mentale", {"source": "discussion"})["sante_mentale"] == 32
    assert "erreur" in s.appeler("recuperer_sante_mentale", {"source": "thérapie"})  # pas la nuit
    s.moment = Moment(1, Periode.NUIT)
    assert s.appeler("recuperer_sante_mentale", {"source": "thérapie"})["sm_gagnee"] == 6  # critique : 3 + 3
    r = s.appeler("jalon", {"jalon": "objectif"})
    assert (r["sm_gagnee"], r["xp_gagnee"]) == (4, 0)


def test_etat():
    r = session().appeler("etat")
    assert r["joueur"]["pv"] == 23
    assert r["joueur"]["arme"] == "Pistolet lourd Arasaka"
    assert r["joueur"]["munitions"] == 8
    assert "combat" not in r


# --- Combat -----------------------------------------------------------------------------------

def test_un_combat_complet():
    # Kaito tire (30 : réussite, 1d10 = 6, +1 de l'Arasaka), le ganger réussit sa Constitution (10),
    # puis le ganger frappe (82 : échec) et Kaito esquive (26).
    s = session(30, 6, 10, 82, 26)
    ganger(s)
    debut = s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert debut["ordre_initiative"] == ["Kaito", "Ganger"]
    tir = s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    touche = dict(tir["touche"])
    assert touche.pop("test_constitution")["reussi"]
    assert touche == {"qui": "Ganger", "degats_bruts": 7, "armure": 0, "degats": 7, "pv": 3,
                      "blessure_grave": True, "etat": "actif"}
    coup = s.appeler("attaquer", {"attaquant": "ganger", "cible": "joueur", "defense": "esquive"})
    assert coup["issue"] == "défenseur"
    assert s.appeler("etat")["combat"]["round"] == 1
    assert s.appeler("fin_de_round")["round"] == 2
    assert "etats" in s.appeler("fin_combat")
    assert "erreur" in s.appeler("fin_de_round")


def test_budget_du_round_respecte():
    s = session(30, 6, 10)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    r = s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    assert "budget du round" in r["erreur"]


def test_viser_recharger_degainer():
    s = session(80)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    r = s.appeler("action_combat", {"qui": "joueur", "action": "viser"})
    assert r["budget_restant"]["action mineure"] == 0
    assert s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})["attaque"]["valeur"] == 70
    assert "erreur" in s.appeler("action_combat", {"qui": "joueur", "action": "deplacer"})  # a visé
    s.appeler("fin_de_round")
    r = s.appeler("action_combat", {"qui": "joueur", "action": "degainer", "arme": "Couteau"})
    assert s.joueur.arme.nom == "Couteau" and "munitions" not in r


def test_embuscade_et_surprise():
    s = session(10, 40)
    ganger(s)
    assert s.appeler("embuscade", {"discretion_agresseurs": 60})["joueur_surpris"]
    s.appeler("debut_combat", {"pnj": ["ganger"], "surpris": "joueur"})
    assert "ne peut pas agir" in s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})["erreur"]


def test_mourant_stabilise_et_destin():
    s = session(3, 60)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    g = s.pnj["ganger"].fiche
    g.pv, g.etat = 0, Etat.MOURANT
    s.personnage.competences["Médecine"] = 40
    assert s.appeler("stabiliser", {"soigneur": "joueur", "mourant": "ganger"})["etat"] == "stable"
    s.personnage.etat, s.personnage.pv = Etat.MORT, 0
    r = s.appeler("point_de_destin", {"usage": "laisse_pour_mort"})
    assert (r["etat"], r["points_destin_restants"]) == ("stable", 1)


def test_deux_combats_d_affilee():
    s = session(30, 6, 10, 30, 3)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    s.appeler("fin_combat")
    ganger(s, "ganger2")
    s.appeler("debut_combat", {"pnj": ["ganger2"]})
    assert "erreur" not in s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger2"})  # budget remis à neuf
