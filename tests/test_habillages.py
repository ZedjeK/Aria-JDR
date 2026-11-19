"""L'habillage des cartes selon le genre (aria/habillages.py), et le jeu qui le joint aux cartes qu'il publie."""

import pytest

from aria import habillages
from aria.bibliotheque import GENRES
from tests.test_combat_partie import Serveur, appel, combat_a_pied, jeu_minimal
from tests.test_combat_joueur import Script


def test_chaque_genre_a_un_habillage_connu():
    assert all(habillages.du_genre(g) in habillages.HABILLAGES for g in GENRES)
    assert set(habillages.DU_GENRE.values()) == set(habillages.HABILLAGES)  # chacun sert au moins une fois


@pytest.mark.parametrize("genre, habillage", [("Cyberpunk", "neon"), ("Science-fiction", "neon"), ("Fantasy", "parchemin"),
                                               ("Dark fantasy", "gothique"), ("Horreur", "gothique"),
                                               ("Militaire", "etat-major"), ("Contemporain", "etat-major"),
                                               ("Post-apo", "rouille")])
def test_les_groupes_retenus(genre, habillage):
    assert habillages.du_genre(genre) == habillage


def test_un_genre_inconnu_prend_neon():
    assert habillages.du_genre("Western") == habillages.du_genre(None) == "neon"


def test_la_carte_du_combat_publiee_par_le_jeu_porte_l_habillage_du_genre():
    s = combat_a_pied(1)
    s.univers.genre = "Post-apo"
    serveur = Serveur([appel("fin_combat", moments_forts="Kaito abat le ganger.")], "Le ganger s'effondre.")
    jeu = jeu_minimal(s, serveur, Script("Attaquer", "Ganger"))
    vues = []
    jeu.publier_le_combat = vues.append
    jeu.combattre_a_pied()
    assert vues[0]["habillage"] == "rouille" and vues[-1] is None
