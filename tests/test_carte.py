"""La carte de la campagne, pour l'afficher : la disposition des quartiers et ce que la page en montre (aria.carte)."""

import itertools
import math

import pytest

from aria import carte, jeu, lieux, monde, noms, pnj
from aria.campagne import Campagne
from aria.des import Des, DesTruques
from test_table import ServeurScripte
from tests.test_monde import Imposes, petit


def distance(places, a, b):
    return math.dist(places[a], places[b])


# --- La disposition


@pytest.mark.parametrize("genre, quartiers", [("Cyberpunk", (18, 20)), ("Fantasy", (8, 10))])
def test_la_disposition_est_la_meme_a_chaque_fois_et_tient_dans_le_carre(genre, quartiers):
    for graine in range(1, 4):
        etat = monde.creer(Des(graine), genre)
        places = carte.disposition(etat)
        assert places == carte.disposition(etat)
        assert set(places) == set(etat["quartiers"]) and quartiers[0] <= len(places) <= quartiers[1]
        for x, y in places.values():
            assert 0 <= x <= carte.LARGEUR and 0 <= y <= carte.LARGEUR


@pytest.mark.parametrize("genre", ["Cyberpunk", "Fantasy"])
def test_les_quartiers_ne_se_chevauchent_pas_et_les_voisins_sont_proches(genre):
    etat = monde.creer(Des(1), genre)
    places = carte.disposition(etat)
    assert min(distance(places, a, b) for a, b in itertools.combinations(places, 2)) > 8  # la place d'un point et de son nom
    voisins = [distance(places, q, v) for q in places for v in etat["quartiers"][q]["voisins"]]
    autres = [distance(places, a, b) for a, b in itertools.combinations(places, 2)
              if b not in etat["quartiers"][a]["voisins"]]
    assert sum(voisins) / len(voisins) * 2 < sum(autres) / len(autres)


def test_un_quartier_seul_est_au_centre():
    etat = {"districts": {"Bourg": ["Place"]}, "quartiers": {"Place": {"district": "Bourg", "voisins": []}}}
    assert carte.disposition(etat) == {"Place": (50.0, 50.0)}


def test_la_disposition_ne_change_pas_la_carte_ni_la_sauvegarde():
    etat = monde.creer(Des(1), "Cyberpunk")
    avant = repr(etat)
    carte.disposition(etat)
    carte.vue(etat)
    assert repr(etat) == avant


# --- Ce que la page montre


def test_une_campagne_sans_monde_n_a_pas_de_carte():
    assert carte.vue(None) is None


def test_la_vue_dit_qui_tient_quoi_ou_est_le_joueur_et_ce_qui_est_dispute():
    etat = petit()
    etat["quartiers"]["B"] |= {"attaque": 3, "attaquant": "Lames"}
    vue = carte.vue(etat)
    assert vue["ici"] == "D"
    assert {d["nom"]: d["quartiers"] for d in vue["districts"]} == {"Nord": ["A", "B", "C"], "Sud": ["D"]}
    assert {d["nom"]: d["dominant"] for d in vue["districts"]} == {"Nord": "Rats", "Sud": "Helix"}
    b = vue["quartiers"]["B"]
    assert (b["maitre"], b["controle"], b["dispute"], b["voisins"]) == ("Rats", 3, True, ["A", "C"])
    assert not vue["quartiers"]["D"]["dispute"]
    assert {"x", "y"} <= set(b)
    assert b["pour_y_aller"] == monde.a("B")


def test_la_vue_donne_les_factions_et_la_reputation_du_joueur():
    etat = petit()
    etat["reputation"]["Rats"] = monde.AMI
    f = carte.vue(etat)["factions"]
    assert f["Rats"] == {"type": "gang", "chef": "Nour", "rivale": "Lames", "reputation": monde.AMI, "quartiers": 2}
    assert f["Helix"]["reputation"] == monde.NEUTRE and f["Helix"]["quartiers"] == 1


def test_la_vue_ne_montre_les_lieux_que_des_quartiers_visites_et_trouves():
    etat = petit()
    etat["ici"] = "D"
    noms.installer(etat, "Cyberpunk", "Osaka")
    pnj.installer(etat, "Cyberpunk")
    lieux.installer(etat, Imposes(), "Cyberpunk")
    vue = carte.vue(etat)
    assert vue["quartiers"]["D"]["visite"] and vue["quartiers"]["D"]["lieux"]
    for lieu in vue["quartiers"]["D"]["lieux"]:
        assert set(lieu) == {"nom", "type", "tenancier"}
    for q in "ABC":  # jamais visités : rien à en dire
        assert not vue["quartiers"][q]["visite"] and vue["quartiers"][q]["lieux"] == []
    cache = next((l for l in etat["lieux"]["par_quartier"]["D"] if l["cache"]), None)
    if cache:  # un lieu caché qu'on n'a pas trouvé n'apparaît pas
        assert cache["nom"] not in [l["nom"] for l in vue["quartiers"]["D"]["lieux"]]


def test_la_vue_marche_sans_les_lieux():
    vue = carte.vue(petit())  # une campagne d'avant les lieux : pas de clé « lieux »
    assert all(not q["visite"] and q["lieux"] == [] for q in vue["quartiers"].values())


# --- Le jeu la publie avant chaque saisie du joueur


def test_le_jeu_publie_la_carte_avant_chaque_saisie(tmp_path):
    serveur = ServeurScripte("La ruelle.", "Le MJ répond.")
    entrees = iter(["Je regarde autour de moi.", "quitter"])
    publiees = []
    partie = jeu.Jeu(serveur, budget=128, des=DesTruques(30, 50), entree=lambda _: next(entrees),
                     sortie=lambda _: None, campagne=Campagne(tmp_path), publier_la_carte=publiees.append)
    partie.jouer()
    assert len(publiees) == 2  # avant la première saisie, puis après l'action du joueur
    assert all(v is None or "quartiers" in v for v in publiees)
    assert all(v is None or v["habillage"] == "neon" for v in publiees)  # Néo-Tokyo : du Cyberpunk


def test_une_sauvegarde_etrange_ne_arrete_pas_la_partie(tmp_path):
    serveur = ServeurScripte("La ruelle.")
    publiees = []
    partie = jeu.Jeu(serveur, budget=128, des=DesTruques(30, 50), entree=lambda _: "quitter", sortie=lambda _: None,
                     campagne=Campagne(tmp_path), publier_la_carte=publiees.append)
    partie.session.monde = {"quartiers": {}, "districts": {"X": ["A"]}}  # il manque ce que la carte lit
    partie.jouer()
    assert publiees == [None]  # la carte manque, la partie continue
