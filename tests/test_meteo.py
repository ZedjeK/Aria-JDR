"""Le temps qu'il fait (REGLES.md 15.3) : tiré chaque matin, appliqué dehors."""

import pytest

from aria import meteo
from aria.temps import Moment, Periode
from tests.test_monde import Imposes, petit
from tests.test_outils import ganger, session


def monde(*des, genre: str = "Cyberpunk", cadre: str = "Osaka sous la pluie acide") -> dict:
    """Un monde avec sa météo. Les dés : saison de départ, temps du premier jour."""
    etat = petit()
    meteo.installer(etat, Imposes(*des), genre, cadre)
    return etat


def test_la_bibliotheque_est_complete():
    assert meteo.verifier_tables() == []


def test_le_climat_vient_du_cadre_sinon_du_genre():
    assert meteo.climat_du_cadre("Cyberpunk", "") == "pluvieux"
    assert meteo.climat_du_cadre("Post-apo", "") == "aride"
    assert meteo.climat_du_cadre("Fantasy", "Le royaume d'Aldmar") == "tempéré"
    assert meteo.climat_du_cadre("Militaire", "Le Mékong, 1968") == "tropical"
    assert meteo.climat_du_cadre("Fantasy", "Les glaces du Nord") == "froid"


def test_installer_tire_la_saison_et_le_premier_temps():
    etat = monde(3, 3)  # automne ; troisième ligne de la table
    assert etat["meteo"] == {"climat": "pluvieux", "genre": "Cyberpunk", "depart": 2, "jour": 1, "temps": "pluie"}
    assert meteo.actif(etat) and not meteo.actif(petit()) and not meteo.actif(None)
    assert meteo.saison(etat, 1) == "automne"


def test_la_saison_tourne_tous_les_quatre_vingt_dix_jours():
    etat = monde(3, 1)
    assert [meteo.saison(etat, j) for j in (90, 91, 181, 271, 361)] == ["automne", "hiver", "printemps", "été",
                                                                        "automne"]
    tropiques = monde(2, 1, genre="Militaire", cadre="Le Mékong, 1968")
    assert [meteo.saison(tropiques, j) for j in (1, 180, 181, 361)] == ["humide", "humide", "sèche", "humide"]


def test_le_temps_dure_une_fois_sur_deux():
    etat = monde(3, 3)
    meteo.avancer(etat, Imposes(3), 2)  # 1 à 3 : le temps d'hier continue, sans dé de table
    assert (etat["meteo"]["jour"], meteo.temps(etat)) == (2, "pluie")
    meteo.avancer(etat, Imposes(4, 7), 3)  # 4 à 6 : on retire
    assert meteo.temps(etat) == "brouillard"
    meteo.avancer(etat, Imposes(), 3)  # le même jour : rien ne bouge, aucun dé
    assert meteo.temps(etat) == "brouillard"


def test_plusieurs_jours_d_un_coup():
    etat = monde(3, 3)
    meteo.avancer(etat, Imposes(1, 6, 8, 2), 4)  # jour 2 : dure ; jour 3 : vent fort ; jour 4 : dure
    assert (etat["meteo"]["jour"], meteo.temps(etat)) == (4, "vent fort")
    meteo.avancer(etat, Imposes(), 400)  # un long saut : trente jours tirés au plus
    assert etat["meteo"]["jour"] == 400


def test_l_orage_devient_le_temps_du_genre():
    assert meteo.table("pluvieux", "automne", "Cyberpunk")[8] == "pluie acide"
    assert meteo.table("pluvieux", "automne", "Fantasy")[8] == "orage"
    assert "tempête de cendres" in meteo.table("aride", "été", "Post-apo") or "orage" not in meteo.table(
        "aride", "été", "Fantasy")


@pytest.mark.parametrize("temps, competence, modificateur, tir", [
    ("clair", "Perception", 0, (0, 0)), ("pluie", "Perception", -10, (0, 0)),
    ("pluie acide", "Perception", -20, (-10, 0)), ("brouillard", "Discrétion", 10, (0, -20)),
    ("vent fort", "Perception", 0, (-10, 0)), ("neige", "Pilotage", -10, (0, 0)),
    ("canicule", "Athlétisme", -10, (0, 0)),
])
def test_les_effets_du_temps(temps, competence, modificateur, tir):
    etat = monde(3, 3)
    etat["meteo"]["temps"] = temps
    assert meteo.modificateur(etat, competence) == modificateur
    assert meteo.malus_de_tir(etat) == tir
    assert meteo.modificateur(None, competence) == 0 and meteo.malus_de_tir(petit()) == (0, 0)


def test_ce_que_le_mj_lit():
    etat = monde(3, 9)  # pluie acide
    vue = meteo.decrire(etat, lambda c: {"Perception": "Vigilance"}.get(c, c))
    assert vue["saison"] == "automne" and vue["temps"] == "pluie acide"
    assert vue["dehors"][:2] == ["Vigilance −20", "tir à distance −10"] and "dégâts" in vue["dehors"][2]
    assert meteo.bloc(etat).startswith("### Le temps qu'il fait") and "Automne, pluie acide." in meteo.bloc(etat)
    assert meteo.bloc(petit()) == "" and meteo.bloc(None) == ""
    etat["meteo"]["temps"] = "clair"
    assert "dehors" not in meteo.decrire(etat) and meteo.phrase(etat) == "Automne, clair."


# --- Les outils du MJ -------------------------------------------------------------------------

def avec_meteo(temps: str, *des, **options):
    etat = monde(3, 3)
    etat["meteo"]["temps"] = temps
    return session(*des, monde=etat, **options)


def test_un_test_dehors_prend_le_temps_qu_il_fait():
    s = avec_meteo("pluie acide", 50, 50)
    schema = next(o for o in s.schemas() if o["function"]["name"] == "test_competence")["function"]["parameters"]
    assert schema["properties"]["dehors"]["type"] == "boolean" and "dehors" not in schema["required"]
    base = s.joueur.valeur("Perception")
    dehors = s.appeler("test_competence", {"competence": "Vigilance", "difficulte": "normale", "dehors": True})
    assert dehors["valeur"] == base - 20 and dehors["meteo"] == "pluie acide : -20"
    abri = s.appeler("test_competence", {"competence": "Vigilance", "difficulte": "normale"})
    assert abri["valeur"] == base and "meteo" not in abri


def test_une_campagne_sans_meteo_n_a_pas_le_champ():
    s = session()
    schema = next(o for o in s.schemas() if o["function"]["name"] == "test_competence")["function"]["parameters"]
    assert "dehors" not in schema["properties"]
    assert "Paramètre inconnu" in s.appeler(
        "test_competence", {"competence": "Vigilance", "difficulte": "normale", "dehors": True})["erreur"]


def test_un_combat_dehors_gene_les_tirs():
    s = avec_meteo("pluie acide", 99, 50, 50)
    ganger(s)
    debut = s.appeler("debut_combat", {"pnj": ["ganger"], "dehors": True})
    assert "pluie acide" in debut["meteo"] and (s.combat.malus_tir, s.combat.malus_tir_long) == (-10, 0)
    base = s.joueur.valeur("Armes à distance")
    s.combat.actif = s.combat.ordre.index(s.joueur)
    tir = s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    assert tir["attaque"]["valeur"] == base - 10


def test_un_combat_a_l_abri_ne_change_rien():
    s = avec_meteo("pluie acide", 99)
    ganger(s)
    debut = s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert "meteo" not in debut and (s.combat.malus_tir, s.combat.malus_tir_long) == (0, 0)


def test_le_brouillard_ne_gene_que_la_longue_portee():
    s = avec_meteo("brouillard", 99)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"], "dehors": True})
    assert (s.combat.malus_tir, s.combat.malus_tir_long) == (0, -20)


def test_l_outil_monde_donne_le_temps_et_le_jour_qui_change_le_retire():
    s = avec_meteo("pluie")
    s.des = Imposes()
    assert s.appeler("monde", {})["meteo"]["temps"] == "pluie"
    s.moment = Moment(2, Periode.MATIN)
    s.des = Imposes(1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
    r = s.appeler("monde", {})
    assert r["meteo"]["temps"] == "pluie" and s.monde["meteo"]["jour"] == 2  # 1 au d6 : la pluie continue
