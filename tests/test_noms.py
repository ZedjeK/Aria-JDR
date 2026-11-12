"""Les noms des PNJ (REGLES.md 15.1) : le code les tire, jamais deux fois le même."""

import pytest

from aria import noms
from aria.noms import FEMME, HOMME, NomImpossible
from tests.test_monde import Imposes, petit
from tests.test_outils import session


def monde(cadre: str = "Osaka sous la pluie acide", genre: str = "Cyberpunk") -> dict:
    etat = petit()
    noms.installer(etat, genre, cadre)
    return etat


def test_la_bibliotheque_est_complete():
    assert noms.verifier_tables() == []


def test_l_origine_vient_du_cadre_sinon_du_genre():
    assert noms.origine_du_cadre("Cyberpunk", "Osaka sous la pluie acide") == "japonaise"
    assert noms.origine_du_cadre("Cyberpunk", "Séoul, 2077") == "coréenne"
    assert noms.origine_du_cadre("Fantasy", "Le royaume d'Aldmar") == "royaumes"
    assert noms.origine_du_cadre("Western", "") == "européenne"  # un genre sans table : le jeu générique


def test_installer_met_l_origine_du_cadre_en_tete_et_reserve_les_chefs():
    etat = monde("Séoul, 2077")
    assert etat["noms"]["origines"] == ["coréenne", "japonaise", "chinoise", "européenne", "arabe", "latine"]
    assert set(etat["noms"]["pris"]) == {f["chef"] for f in etat["factions"].values()}
    assert noms.actifs(etat) and not noms.actifs(petit()) and not noms.actifs(None)


def test_le_cadre_prend_cinq_faces_sur_dix():
    etat = monde()
    assert noms.tirer(etat, Imposes(5, 1, 1), HOMME) == "Haruto Sato"
    assert noms.tirer(etat, Imposes(6, 1, 1), HOMME) == "Min-jun Kim"
    assert noms.tirer(etat, Imposes(10, 1, 1), FEMME) == "Sofía García"


def test_une_origine_imposee_ne_lance_pas_le_de_d_origine():
    etat = monde()
    assert noms.tirer(etat, Imposes(2, 3), FEMME, origine="arabe") == "Nour Benali"
    with pytest.raises(NomImpossible, match="n'existe pas dans cette campagne"):
        noms.tirer(etat, Imposes(), HOMME, origine="elfique")


def test_un_nom_ne_sort_jamais_deux_fois():
    etat = monde()
    premier = noms.tirer(etat, Imposes(1, 1, 1), HOMME)
    second = noms.tirer(etat, Imposes(1, 1, 1, 1, 2), HOMME)  # le même tirage, puis un autre nom de famille
    assert (premier, second) == ("Haruto Sato", "Haruto Suzuki")
    assert etat["noms"]["pris"][-2:] == [premier, second]


def test_quand_tous_les_tirages_tombent_sur_un_nom_pris_le_code_prend_un_nom_libre():
    etat = monde()
    noms.reserver(etat, "Haruto Sato")
    assert noms.tirer(etat, Imposes(1), HOMME) == "Haruto Suzuki"  # vingt fois Haruto Sato, puis le premier libre


def test_une_origine_epuisee_le_dit():
    etat = monde()
    table = noms._bibliotheque()["origines"]["japonaise"]
    for prenom in table["m"]:
        for famille in table["famille"]:
            noms.reserver(etat, f"{prenom} {famille}")
    with pytest.raises(NomImpossible, match="ont servi"):
        noms.tirer(etat, Imposes(1), HOMME)


def test_un_membre_de_gang_porte_un_surnom_une_fois_sur_trois():
    etat = monde()
    assert noms.tirer(etat, Imposes(1, 1, 1, 1, 1), HOMME, gang=True) == "Haruto Sato, dit Rasoir"
    assert noms.tirer(etat, Imposes(1, 2, 1, 1, 1), FEMME, gang=True) == "Aoi Sato, dite Chrome"  # Rasoir est pris
    assert noms.tirer(etat, Imposes(1, 3, 1, 2), HOMME, gang=True) == "Daichi Sato"
    assert noms.tirer(etat, Imposes(1, 4, 1), HOMME) == "Sora Sato"  # hors d'un gang, pas de dé de surnom
    assert etat["noms"]["surnoms"] == ["Rasoir", "Chrome"]


# --- Les outils du MJ -------------------------------------------------------------------------

PROFIL = {"camp": "ennemis", "combat": 45, "pv": 10}


def test_creer_pnj_tire_le_nom():
    s = session(1, 1, 1, monde=monde())
    proprietes = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert "nom" not in proprietes["properties"] and "nom" not in proprietes["required"]
    assert proprietes["properties"]["sexe"]["enum"] == ["homme", "femme"]
    r = s.appeler("creer_pnj", {"identifiant": "ganger", "sexe": "homme"} | PROFIL)
    assert r["nom"] == "Haruto Sato" and s.pnj["ganger"].nom == "Haruto Sato"


def test_le_mj_ne_peut_plus_donner_de_nom_ni_oublier_le_sexe():
    s = session(monde=monde())
    assert "Paramètre inconnu" in s.appeler("creer_pnj", {"identifiant": "g", "nom": "Bob"} | PROFIL)["erreur"]
    assert "sexe" in s.appeler("creer_pnj", {"identifiant": "g"} | PROFIL)["erreur"]
    assert "g" not in s.pnj and s.monde["noms"]["pris"] == sorted(f["chef"] for f in s.monde["factions"].values())


def test_un_gang_donne_un_surnom_une_autre_faction_non():
    s = session(1, 1, 1, 1, 1, 1, 2, 1, monde=monde())
    assert s.appeler("creer_pnj", {"identifiant": "a", "sexe": "homme", "faction": "Lames"} | PROFIL)["nom"] \
        == "Haruto Sato, dit Rasoir"
    assert s.appeler("creer_pnj", {"identifiant": "b", "sexe": "homme", "faction": "Helix"} | PROFIL)["nom"] \
        == "Ren Sato"


def test_noter_un_pnj_deja_cree_garde_son_nom():
    s = session(1, 1, 1, monde=monde())
    s.appeler("creer_pnj", {"identifiant": "ganger", "sexe": "homme"} | PROFIL)
    r = s.appeler("noter_pnj", {"identifiant": "ganger", "role": "voyou du canal", "attitude": "méfiant"})
    assert r["nom"] == "Haruto Sato"
    encore = s.appeler("noter_pnj", {"identifiant": "ganger", "role": "voyou du canal", "attitude": "hostile"})
    assert encore["nom"] == "Haruto Sato" and encore["attitude"] == "hostile"


def test_noter_un_nouveau_pnj_tire_son_nom():
    s = session(6, 2, 2, monde=monde())
    r = s.appeler("noter_pnj", {"identifiant": "doc", "sexe": "femme", "role": "charcudoc", "attitude": "amicale"})
    assert r["nom"] == "Ji-woo Lee"
    assert "sexe" in s.appeler("noter_pnj", {"identifiant": "x", "role": "passant", "attitude": "neutre"})["erreur"]


def test_une_campagne_d_avant_garde_le_nom_libre():
    s = session()
    proprietes = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert "nom" in proprietes["required"] and "sexe" not in proprietes["properties"]
    assert s.appeler("creer_pnj", {"identifiant": "g", "nom": "Ganger"} | PROFIL)["nom"] == "Ganger"
    r = s.appeler("noter_pnj", {"identifiant": "g", "nom": "Ganger", "role": "voyou", "attitude": "hostile"})
    assert r["nom"] == "Ganger"
