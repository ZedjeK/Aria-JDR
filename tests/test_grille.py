"""La géométrie de la carte de combat en cases hexagonales (aria.grille, REGLES.md 7.11)."""

import pytest

from aria import grille
from aria.equipement import Portee
from aria.grille import Abri, Carte, Terrain, case, colonne_ligne, distance, ligne, voisins


class Pion:
    """Un combattant réduit à ce que la carte regarde : un nom, un côté, debout ou non."""

    def __init__(self, nom, cote="joueurs", debout=True):
        self.nom, self.cote, self.est_debout = nom, cote, debout


def allies(a, b):
    return a.cote == b.cote


def debout(x):
    return x.est_debout


def carte(largeur=30, hauteur=30, **terrain):
    return Carte(largeur, hauteur, dict(terrain.get("terrain", {})))


# --- La géométrie


def test_six_voisines_chacune_a_un_pas():
    c = case(5, 5)
    assert len(set(voisins(c))) == 6
    assert all(distance(c, v) == 1 for v in voisins(c))


@pytest.mark.parametrize("a, b, attendu", [((0, 0), (0, 0), 0), ((0, 0), (3, 0), 3), ((0, 0), (2, -4), 4),
                                           ((1, 2), (-2, 5), 3), ((0, 0), (-3, 1), 3)])
def test_la_distance_compte_les_pas(a, b, attendu):
    assert distance(a, b) == attendu == distance(b, a)


def test_sur_une_meme_ligne_de_la_carte_la_distance_est_l_ecart_des_colonnes():
    for rang in range(4):
        assert distance(case(1, rang), case(9, rang)) == 8


@pytest.mark.parametrize("colonne, rang", [(0, 0), (3, 1), (7, 4), (12, 9)])
def test_colonne_et_ligne_aller_retour(colonne, rang):
    assert colonne_ligne(case(colonne, rang)) == (colonne, rang)


def test_la_ligne_va_d_une_case_a_l_autre_pas_a_pas():
    pas = ligne(case(0, 0), case(4, 0))
    assert [p for p in pas] == [{case(i, 0)} for i in range(5)]


def test_une_ligne_qui_passe_entre_deux_cases_donne_les_deux():
    pas = ligne((0, 0), (2, -4))
    assert pas[1] == {(0, -1), (1, -1)} and pas[3] == {(1, -3), (2, -3)}
    assert pas[2] == {(1, -2)}


def test_les_portees_en_cases():
    assert [grille.portee_en_cases(p) for p in (Portee.CONTACT, Portee.COURTE, Portee.MOYENNE, Portee.LONGUE)] == [1, 8, 20, 40]


# --- La carte : placer


def test_on_ne_place_pas_sur_un_obstacle_ni_sur_une_case_prise_ni_hors_de_la_carte():
    k, g = Pion("Kaito"), Pion("Ganger", "ennemis")
    c = carte(10, 10, terrain={case(2, 2): Terrain.PLEIN})
    c.placer(k, case(1, 1))
    with pytest.raises(ValueError):
        c.placer(g, case(2, 2))
    with pytest.raises(ValueError):
        c.placer(g, case(1, 1))
    with pytest.raises(ValueError):
        c.placer(g, case(10, 0))
    c.placer(g, case(3, 3))
    assert c.ecart(k, g) == distance(case(1, 1), case(3, 3))


# --- Les déplacements


def test_en_terrain_libre_un_deplacement_atteint_toutes_les_cases_a_six_pas():
    k = Pion("Kaito")
    c = carte()
    c.placer(k, case(15, 15))
    possibles = c.atteignables(k, allies, debout)
    assert len(possibles) == 3 * 6 * 7  # les cases à 1 à 6 pas, sans celle du départ
    assert max(possibles.values()) == 6


def test_le_bord_de_la_carte_arrete_le_deplacement():
    k = Pion("Kaito")
    c = carte(5, 5)
    c.placer(k, case(0, 0))
    assert all(c.dans(x) for x in c.atteignables(k, allies, debout))


def test_un_mur_oblige_a_faire_le_tour():
    k = Pion("Kaito")
    mur = {case(6, rang): Terrain.PLEIN for rang in range(0, 9)}
    c = carte(20, 20, terrain=mur)
    c.placer(k, case(5, 4))
    possibles = c.atteignables(k, allies, debout)
    assert case(7, 4) not in possibles  # derrière le mur : bien plus de 6 pas par le bout
    assert case(4, 4) in possibles


def test_le_terrain_difficile_coute_deux_cases():
    k = Pion("Kaito")
    boue = {case(colonne, rang): Terrain.DIFFICILE for colonne in range(6, 9) for rang in range(20)}
    c = carte(20, 20, terrain=boue)
    c.placer(k, case(5, 10))
    possibles = c.atteignables(k, allies, debout)
    assert possibles[case(6, 10)] == 2 and possibles[case(8, 10)] == 6
    assert case(9, 10) not in possibles


def test_on_traverse_un_allie_sans_s_arreter_sur_sa_case():
    k, m = Pion("Kaito"), Pion("Mira")
    couloir = {case(colonne, rang): Terrain.PLEIN for colonne in range(20) for rang in (3, 5)}
    c = carte(20, 9, terrain=couloir)
    c.placer(k, case(2, 4))
    c.placer(m, case(3, 4))
    possibles = c.atteignables(k, allies, debout)
    assert case(3, 4) not in possibles and case(4, 4) in possibles


def test_un_ennemi_debout_bloque_le_passage_mais_pas_un_ennemi_a_terre():
    k, g = Pion("Kaito"), Pion("Ganger", "ennemis")
    couloir = {case(colonne, rang): Terrain.PLEIN for colonne in range(20) for rang in (3, 5)}
    c = carte(20, 9, terrain=couloir)
    c.placer(k, case(2, 4))
    c.placer(g, case(3, 4))
    assert case(4, 4) not in c.atteignables(k, allies, debout)
    g.est_debout = False
    possibles = c.atteignables(k, allies, debout)
    assert case(4, 4) in possibles and case(3, 4) not in possibles


def test_deplacer_pose_le_pion_et_dit_ce_que_le_chemin_a_coute():
    k = Pion("Kaito")
    c = carte()
    c.placer(k, case(5, 5))
    assert c.deplacer(k, case(9, 5), allies, debout) == 4
    assert c.position(k) == case(9, 5)
    with pytest.raises(ValueError):
        c.deplacer(k, case(16, 5), allies, debout)


# --- La ligne de tir et le couvert


def tir(terrain, tireur=case(0, 0), cible=case(6, 0)):
    k, g = Pion("Kaito"), Pion("Ganger", "ennemis")
    c = carte(terrain=terrain)
    c.placer(k, tireur)
    c.placer(g, cible)
    return c.abri(k, g)


def test_sans_obstacle_pas_d_abri():
    assert tir({}) is Abri.AUCUN


@pytest.mark.parametrize("terrain, abri", [(Terrain.BAS, Abri.PARTIEL), (Terrain.BLINDE, Abri.LOURD),
                                           (Terrain.PLEIN, Abri.COUPE), (Terrain.DIFFICILE, Abri.AUCUN)])
def test_un_obstacle_sur_la_ligne_donne_son_abri(terrain, abri):
    assert tir({case(4, 0): terrain}) is abri


def test_le_plus_protecteur_des_obstacles_compte():
    assert tir({case(2, 0): Terrain.BAS, case(4, 0): Terrain.BLINDE}) is Abri.LOURD


def test_un_obstacle_bas_ou_blinde_colle_au_tireur_ne_compte_pas_mais_un_mur_coupe():
    assert tir({case(1, 0): Terrain.BAS}) is Abri.AUCUN
    assert tir({case(1, 0): Terrain.BLINDE}) is Abri.AUCUN
    assert tir({case(1, 0): Terrain.PLEIN}) is Abri.COUPE


def test_un_obstacle_colle_a_la_cible_compte():
    assert tir({case(5, 0): Terrain.BAS}) is Abri.PARTIEL


def test_un_obstacle_hors_de_la_ligne_ne_compte_pas():
    assert tir({case(3, 3): Terrain.PLEIN}) is Abri.AUCUN


@pytest.mark.parametrize("obstacle", [(1, -3), (2, -3)])
def test_entre_deux_cases_celle_qui_protege_le_plus_compte(obstacle):
    k, g = Pion("Kaito"), Pion("Ganger", "ennemis")
    c = Carte(30, 30, {obstacle: Terrain.BAS})
    c.positions = {k: (0, 0), g: (2, -4)}
    assert c.abri(k, g) is Abri.PARTIEL


def test_derriere_la_victime_a_l_oppose_de_celui_qui_frappe():
    k, g = Pion("Kaito"), Pion("Ganger", "ennemis")
    c = carte()
    c.placer(k, case(4, 4))
    c.placer(g, case(5, 4))
    assert c.derriere(k, g) == case(6, 4)
    c.placer(g, case(8, 4))
    assert c.derriere(k, g) is None
