"""Le combat sur la carte en cases hexagonales (REGLES.md 7.11) : déplacement, contact, portée, ligne de tir, couvert,
repousser, fuyard qui part. Sans carte, le combat ne change pas."""

import pytest

from aria.combat import ActionImpossible, Combat, Couvert, Moral, TypeAction, debout, meme_cote
from aria.des import DesTruques
from aria.grille import Carte, Terrain, case
from tests.test_combat import COUTEAU, FUSIL, PISTOLET, ganger, kaito


def sur_la_carte(*places, terrain=None, des=None, largeur=50, hauteur=30):
    """Un combat sur une carte : places = (combattant, colonne, ligne)."""
    carte = Carte(largeur, hauteur, dict(terrain or {}))
    for combattant, colonne, rang in places:
        carte.placer(combattant, case(colonne, rang))
    return Combat(des or DesTruques(), [p[0] for p in places], carte=carte)


# --- Les côtés


def test_le_joueur_et_ses_allies_d_un_cote_les_ennemis_de_l_autre_les_neutres_de_personne():
    k, g = kaito(), ganger()
    allie, neutre = ganger(nom="Mira"), ganger(nom="Passant")
    allie.camp, neutre.camp = "allies", "neutres"
    assert meme_cote(k, allie) and not meme_cote(k, g) and not meme_cote(neutre, neutre)
    assert debout(k)
    g.moral = Moral.RENDU
    assert not debout(g)


# --- Se déplacer


def test_sur_la_carte_un_deplacement_dit_ou_il_va_et_coute_un_deplacement():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 2, 5), (g, 20, 5))
    with pytest.raises(ActionImpossible, match="dit où il va"):
        c.deplacer(k)
    assert c.deplacer(k, case(8, 5)) == 6
    assert c.carte.position(k) == case(8, 5) and k.budget.utilise[TypeAction.DEPLACEMENT] == 1


def test_un_deplacement_ne_depasse_pas_six_cases_et_ne_coute_rien_s_il_est_refuse():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 2, 5), (g, 20, 5))
    with pytest.raises(ActionImpossible, match="ne peut pas atteindre"):
        c.deplacer(k, case(9, 5))
    assert k.budget.utilise[TypeAction.DEPLACEMENT] == 0 and c.carte.position(k) == case(2, 5)


def test_deux_deplacements_font_douze_cases_puis_le_budget_est_vide():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 2, 5), (g, 30, 5))
    c.deplacer(k, case(8, 5))
    c.deplacer(k, case(14, 5))
    with pytest.raises(ActionImpossible):
        c.deplacer(k, case(15, 5))


def test_un_ennemi_debout_bloque_le_couloir():
    k, g = kaito(), ganger()
    couloir = {case(colonne, rang): Terrain.PLEIN for colonne in range(50) for rang in (4, 6)}
    c = sur_la_carte((k, 2, 5), (g, 4, 5), terrain=couloir)
    with pytest.raises(ActionImpossible):
        c.deplacer(k, case(6, 5))


def test_apres_avoir_vise_on_ne_bouge_plus_et_apres_avoir_bouge_on_ne_vise_plus():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 2, 5), (g, 8, 5))
    c.viser(k)
    with pytest.raises(ActionImpossible, match="a visé"):
        c.deplacer(k, case(3, 5))
    k2, g2 = kaito(), ganger()
    c2 = sur_la_carte((k2, 2, 5), (g2, 8, 5))
    c2.deplacer(k2, case(3, 5))
    with pytest.raises(ActionImpossible, match="déplacé"):
        c2.viser(k2)


def test_sur_la_carte_se_mettre_a_couvert_n_est_plus_une_action():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 2, 5), (g, 8, 5))
    with pytest.raises(ActionImpossible, match="derrière un obstacle"):
        c.se_mettre_a_couvert(g)


# --- Le contact et la portée


def test_la_melee_exige_le_contact():
    k, g = kaito(COUTEAU), ganger()
    c = sur_la_carte((k, 2, 5), (g, 4, 5))
    assert "au contact" in c.raison_de_ne_pas_attaquer(g, k)
    with pytest.raises(ActionImpossible, match="au contact"):
        c.attaquer(g, k)
    assert g.budget.utilise[TypeAction.SIMPLE] == 0  # refusée : rien n'est dépensé
    c.carte.positions[g] = case(3, 5)
    assert c.raison_de_ne_pas_attaquer(g, k) is None


@pytest.mark.parametrize("arme, portee", [(PISTOLET, 8), (FUSIL, 40)])
def test_au_dela_de_sa_portee_une_arme_ne_tire_pas(arme, portee):
    k, g = kaito(arme), ganger()
    c = sur_la_carte((k, 0, 5), (g, portee, 5), largeur=60)
    assert c.raison_de_ne_pas_attaquer(k, g) is None
    c.carte.positions[g] = case(portee + 1, 5)
    assert "hors de portée" in c.raison_de_ne_pas_attaquer(k, g)
    with pytest.raises(ActionImpossible, match="hors de portée"):
        c.attaquer(k, g)
    assert c.chance_de_toucher(k, g) == 0


def test_un_tir_au_contact_n_a_pas_de_malus():
    k, g = kaito(), ganger()
    assert sur_la_carte((k, 2, 5), (g, 3, 5)).chance_de_toucher(k, g) == 50  # Armes à distance 50


# --- La ligne de tir et le couvert


@pytest.mark.parametrize("terrain, chance", [(None, 50), (Terrain.BAS, 30), (Terrain.BLINDE, 10)])
def test_le_couvert_vient_des_obstacles_de_la_carte(terrain, chance):
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 0, 5), (g, 6, 5), terrain={case(5, 5): terrain} if terrain else {})
    assert c.chance_de_toucher(k, g) == chance
    assert c.couvert_sur_la_carte(k, g) is {None: Couvert.AUCUN, Terrain.BAS: Couvert.PARTIEL,
                                            Terrain.BLINDE: Couvert.LOURD}[terrain]


def test_un_mur_coupe_la_ligne_de_tir():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 0, 5), (g, 6, 5), terrain={case(3, 5): Terrain.PLEIN})
    assert "coupe la ligne de tir" in c.raison_de_ne_pas_attaquer(k, g)
    assert c.chance_de_toucher(k, g) == 0
    with pytest.raises(ActionImpossible, match="coupe la ligne de tir"):
        c.attaquer(k, g)


def test_le_tireur_tire_par_dessus_l_obstacle_colle_a_lui():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 0, 5), (g, 6, 5), terrain={case(1, 5): Terrain.BAS})
    assert c.chance_de_toucher(k, g) == 50


def test_le_couvert_ne_joue_pas_au_corps_a_corps():
    k, g = kaito(COUTEAU), ganger()
    c = sur_la_carte((k, 2, 5), (g, 3, 5))
    assert c.couvert_sur_la_carte(g, k) is Couvert.AUCUN


@pytest.mark.parametrize("terrain, touche", [({}, True), ({case(5, 5): Terrain.BAS}, False)])
def test_le_jet_d_attaque_compte_le_couvert_de_la_carte(terrain, touche):
    # 31 touche à 50 %, rate à 30 % (50 −20 du couvert partiel) ; 1 aux dégâts : pas de blessure grave
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 0, 5), (g, 6, 5), terrain=terrain, des=DesTruques(31, 1))
    assert c.attaquer(k, g).attaque.reussi is touche


def test_un_combattant_hors_de_la_carte_ne_peut_ni_attaquer_ni_etre_vise():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 0, 5), (g, 6, 5))
    c.carte.retirer(g)
    assert "n'est pas sur la carte" in c.raison_de_ne_pas_attaquer(k, g)


# --- Repousser et partir


def test_repousser_fait_reculer_d_une_case_si_elle_est_libre():
    k, g = kaito(COUTEAU), ganger()
    c = sur_la_carte((k, 4, 5), (g, 5, 5))
    assert c._repousser(k, g) == "Ganger recule d'une case."
    assert c.carte.position(g) == case(6, 5)


def test_repousser_ne_deplace_rien_contre_un_mur():
    k, g = kaito(COUTEAU), ganger()
    c = sur_la_carte((k, 4, 5), (g, 5, 5), terrain={case(6, 5): Terrain.PLEIN})
    assert "ne peut pas reculer" in c._repousser(k, g)
    assert c.carte.position(g) == case(5, 5)


def test_un_fuyard_qui_part_quitte_la_carte():
    k, g = kaito(), ganger()
    c = sur_la_carte((k, 0, 5), (g, 6, 5))
    g.moral, g.tours_avant_de_partir = Moral.EN_FUITE, 1
    c._fin_du_tour(g)
    assert g.moral is Moral.PARTI and g not in c.carte.positions


# --- Sans carte, rien ne change


def test_sans_carte_le_combat_reste_celui_d_avant():
    k, g = kaito(), ganger()
    c = Combat(DesTruques(), [k, g])
    assert c.carte is None and c.raison_de_ne_pas_attaquer(k, g) is None
    assert c.chance_de_toucher(k, g) == 50
    assert c.deplacer(k) is None
    assert c.se_mettre_a_couvert(g) is Couvert.PARTIEL
