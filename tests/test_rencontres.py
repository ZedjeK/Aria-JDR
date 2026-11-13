"""Les rencontres de rue (REGLES.md 15.5) : ce qui arrive au joueur quand il entre dans un quartier."""

import pytest

from aria import noms, pnj, rencontres
from aria.monde import HOSTILE, RECHERCHE
from aria.rencontres import DANGER, OCCASION, SCENE
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from test_inventaire import session
from tests.test_monde import Imposes, petit
from tests.test_univers import CYBERPUNK


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def monde(ici: str = "A") -> dict:
    """Le petit monde, avec ses noms, ses rôles et ses rencontres. A est disputé (les Rats sont à côté) ; D est
    calme, dans un district que Helix domine."""
    etat = petit()
    etat["ici"] = ici
    noms.installer(etat, "Cyberpunk", "Osaka")
    pnj.installer(etat, "Cyberpunk")
    rencontres.installer(etat, "Cyberpunk")
    return etat


def partie(u, etat, *des):
    s, _ = session(u, des=Imposes(*des))
    s.monde = etat
    return s


def test_la_bibliotheque_est_complete():
    assert rencontres.verifier_tables() == []


def test_la_chance_depend_du_quartier_et_de_l_heure():
    etat = monde()
    assert rencontres.chance(etat, "D") == 2  # calme
    assert rencontres.chance(etat, "A") == 4  # disputé
    assert rencontres.chance(etat, "D", nuit=True) == 3 and rencontres.chance(etat, "A", nuit=True) == 5
    assert rencontres.actives(etat) and not rencontres.actives(petit()) and not rencontres.actives(None)


def test_pas_de_rencontre_au_dessus_du_seuil():
    etat = monde("D")
    assert rencontres.tirer(etat, Imposes(3), 1) is None
    assert rencontres.tirer(etat, Imposes(3), 1, nuit=True) is not None  # la nuit ajoute une face


@pytest.mark.parametrize("de, famille", [(1, SCENE), (3, SCENE), (4, OCCASION), (5, OCCASION), (6, DANGER)])
def test_la_famille_se_tire_sur_un_de_a_six(de, famille):
    assert rencontres.tirer(monde(), Imposes(1, de), 1)["famille"] == famille


def test_une_rencontre_a_son_texte_et_son_pnj():
    r = rencontres.tirer(monde(), Imposes(1, 1, 1), 1)
    assert r["texte"].startswith("Un vendeur de nouilles ambulant") and r["quartier"] == "A"
    assert r["pnj"] == {"nom": "Haruto Sato", "sexe": "homme", "role": "commerçant", "menace": "faible",
                        "caractere": "méfiant", "signe": "un œil cybernétique qui ne cligne pas"}


def test_une_seule_rencontre_par_jour():
    etat = monde()
    assert rencontres.tirer(etat, Imposes(1), 1) is not None
    assert rencontres.tirer(etat, Imposes(1), 1) is None  # aucun dé n'est lancé
    assert rencontres.tirer(etat, Imposes(1), 2) is not None


def test_chez_une_faction_hostile_le_danger_prend_une_face_de_plus():
    etat = monde()
    etat["reputation"]["Lames"] = HOSTILE
    assert rencontres.tirer(etat, Imposes(1, 5), 1)["famille"] == DANGER
    assert rencontres.tirer(etat, Imposes(1, 4), 2)["famille"] == OCCASION


def test_recherche_c_est_toujours_un_controle_ou_une_traque():
    etat = monde()
    etat["reputation"]["Lames"] = RECHERCHE
    premier = rencontres.tirer(etat, Imposes(1, 1), 1)  # pas de dé de famille : le suivant choisit la rencontre
    second = rencontres.tirer(etat, Imposes(1, 2), 2)
    assert (premier["famille"], second["famille"]) == (DANGER, DANGER)
    assert premier["texte"].startswith("Une patrouille t'arrête") and premier["pnj"]["role"] == "policier"
    assert second["texte"].startswith("Des hommes de main du quartier") and second["pnj"]["role"] == "tueur"


def test_la_menace_du_pnj_ne_depasse_pas_forte_ni_les_bornes_du_role():
    assert rencontres._menace(Imposes(6), "Cyberpunk", "tueur") == pnj.FORTE
    assert rencontres._menace(Imposes(6), "Cyberpunk", "passant") == pnj.FAIBLE
    assert rencontres._menace(Imposes(4), "Cyberpunk", "voyou") == pnj.MOYENNE


def test_ce_que_le_mj_recoit():
    r = rencontres.tirer(monde(), Imposes(1, 6, 5), 1)  # un danger, la cinquième : l'embuscade
    vue = rencontres.decrire(r)
    assert vue["famille"] == DANGER and vue["rencontre"].startswith("Une embuscade")
    assert "outil embuscade" in vue["consigne"] and "« rencontre » à vrai" in vue["consigne"]
    assert "continuer son chemin" in rencontres.decrire(rencontres.tirer(monde(), Imposes(1, 1), 1))["consigne"]


def test_la_rencontre_en_cours_s_efface_quand_le_joueur_change_de_quartier():
    etat = monde()
    rencontres.tirer(etat, Imposes(1), 1)
    assert rencontres.en_cours(etat)["quartier"] == "A"
    etat["ici"] = "B"
    assert rencontres.en_cours(etat) is None and rencontres.en_cours(petit()) is None


# --- Les outils du MJ -------------------------------------------------------------------------

def test_entrer_dans_un_quartier_peut_amener_une_rencontre(u):
    s = partie(u, monde("B"), 1, 1, 1)  # la rencontre, une scène, la première
    r = s.appeler("monde", {"ici": "A"})
    vue = r["rencontre_de_rue"]
    assert vue["famille"] == SCENE and vue["pnj"]["nom"] == "Haruto Sato"
    assert "rencontre_de_rue" not in s.appeler("monde", {"ici": "B"})  # une seule par jour


def test_relire_le_monde_sans_bouger_ne_tire_rien(u):
    s = partie(u, monde("A"), 1, 1, 1)
    assert "rencontre_de_rue" not in s.appeler("monde", {})
    assert "rencontre_de_rue" not in s.appeler("monde", {"ici": "A"})
    assert s.monde["rencontres"]["jour"] == 0


def test_la_nuit_ajoute_une_face(u):
    s = partie(u, monde("C"), 3)
    s.moment = Moment(1, Periode.NUIT)
    s.jour_du_monde = 1
    assert "rencontre_de_rue" in s.appeler("monde", {"ici": "D"})  # 3 sur 1d10 : de jour, rien


def test_une_rumeur_ouvre_une_offre_de_mission(u):
    s = partie(u, monde("B"), 1, 4, 2)  # une occasion, la deuxième : le fixer qui a un travail
    r = s.appeler("monde", {"ici": "A"})
    identifiant = r["rencontre_de_rue"]["offre_de_mission"]
    assert identifiant in [o["id"] for o in r["offres_de_mission"]]
    assert next(o for o in s.monde["offres"] if o["id"] == identifiant)["source"] == "rencontre"


def test_creer_le_pnj_de_la_rencontre(u):
    s = partie(u, monde("B"), 1, 6, 1)  # un danger : trois voyous
    croise = s.appeler("monde", {"ici": "A"})["rencontre_de_rue"]["pnj"]
    schema = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert schema["properties"]["rencontre"]["type"] == "boolean"
    r = s.appeler("creer_pnj", {"identifiant": "racketteur", "camp": "ennemis", "rencontre": True})
    assert (r["nom"], r["role"], r["menace"]) == (croise["nom"], "voyou", croise["menace"])
    assert (r["caractere"], r["signe"]) == (croise["caractere"], croise["signe"])
    # Il ne se crée qu'une fois : le champ disparaît, et ses complices se créent comme les autres PNJ
    schema = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert "rencontre" not in schema["properties"]
    autre = s.appeler("creer_pnj", {"identifiant": "complice", "camp": "ennemis", "sexe": "homme", "role": "voyou",
                                    "menace": "faible"})
    assert autre["nom"] != croise["nom"]


def test_sans_rencontre_en_cours_le_champ_n_existe_pas(u):
    s = partie(u, monde("A"))
    schema = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert "rencontre" not in schema["properties"]
    assert "Paramètre inconnu" in s.appeler(
        "creer_pnj", {"identifiant": "x", "camp": "ennemis", "rencontre": True})["erreur"]
