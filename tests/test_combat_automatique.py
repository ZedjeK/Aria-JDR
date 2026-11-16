"""Le moteur du combat automatique : décor, couvert, maladresse, défense et difficulté par défaut, moral.

Référence : REGLES.md 7.2, 7.3, 7.4 et 7.8. Tous les dés sont truqués : l'ordre des tirages est celui du moteur
(jet d'attaque, d6 d'une maladresse, jet de défense, dégâts).
"""

import pytest

from aria import gains
from aria.combat import (
    SEUIL_MENACE_FORTE,
    ActionImpossible,
    BonusMajeure,
    Combat,
    Combattant,
    Couvert,
    Decor,
    Defense,
    FichePnj,
    Moral,
    TypeAction,
)
from aria.des import DesTruques
from aria.equipement import CORPS_A_CORPS, Arme, Portee, Propriete
from aria.personnage import Etat
from aria.resolution import Degre, Difficulte, chance_de_reussite
from tests.test_combat import COUTEAU, PISTOLET, combat, ganger, kaito


def chef(pv=10, **profil):
    """Une menace forte : 75 % en combat."""
    return Combattant(FichePnj("Chef", combat=75, pv_max_base=10, pv=pv, **profil), "ennemis", COUTEAU)


# --- Le décor et le couvert (7.2) -------------------------------------------------------------

def test_le_decor_par_defaut_est_encombre():
    assert combat(DesTruques(), kaito(), ganger()).decor is Decor.ENCOMBRE


@pytest.mark.parametrize("decor, couvert", [(Decor.ENCOMBRE, Couvert.PARTIEL), (Decor.FORTIFIE, Couvert.LOURD)])
def test_se_mettre_a_couvert_coute_un_deplacement(decor, couvert):
    g = ganger()
    c = combat(DesTruques(), kaito(), g, decor=decor)
    assert c.se_mettre_a_couvert(g) is couvert
    assert g.couvert is couvert
    assert g.budget.utilise[TypeAction.DEPLACEMENT] == 1


def test_un_decor_degage_refuse_le_couvert_et_ne_coute_rien():
    g = ganger()
    c = combat(DesTruques(), kaito(), g, decor=Decor.DEGAGE)
    with pytest.raises(ActionImpossible, match="dégagé"):
        c.se_mettre_a_couvert(g)
    assert g.budget.utilise[TypeAction.DEPLACEMENT] == 0 and g.couvert is Couvert.AUCUN


def test_le_couvert_pris_pese_sur_le_tireur():
    k, g = kaito(), ganger()
    combat_ = combat(DesTruques(90), k, g)
    combat_.se_mettre_a_couvert(g)
    assert combat_.attaquer(k, g).attaque.valeur == 50 - 20


def test_le_couvert_du_decor_et_celui_de_l_attaque_ne_se_cumulent_pas():
    k, g = kaito(), ganger()
    c = combat(DesTruques(90), k, g)
    c.se_mettre_a_couvert(g)
    assert c.attaquer(k, g, couvert=Couvert.LOURD).attaque.valeur == 50 - 40  # le plus fort des deux, pas −60


def test_tirer_ne_fait_pas_perdre_son_couvert():
    k, g = kaito(), ganger(arme=PISTOLET)
    c = combat(DesTruques(90), k, g)
    c.se_mettre_a_couvert(g)
    c.attaquer(g, k)
    assert g.couvert is Couvert.PARTIEL


def test_se_deplacer_autrement_fait_perdre_son_couvert():
    g = ganger()
    c = combat(DesTruques(), kaito(), g)
    c.se_mettre_a_couvert(g)
    c.deplacer(g)
    assert g.couvert is Couvert.AUCUN


def test_le_corps_a_corps_fait_perdre_le_couvert_aux_deux():
    k, g = kaito(COUTEAU), ganger()
    c = combat(DesTruques(90), k, g)
    c.se_mettre_a_couvert(g)
    k.couvert = Couvert.PARTIEL
    c.attaquer(k, g)
    assert g.couvert is Couvert.AUCUN and k.couvert is Couvert.AUCUN


def test_le_couvert_ne_protege_pas_du_corps_a_corps():
    k, g = kaito(COUTEAU), ganger()
    c = combat(DesTruques(90), k, g)
    c.se_mettre_a_couvert(g)
    assert c.attaquer(k, g).attaque.valeur == 25  # Corps à corps 25, aucun malus de couvert


# --- La conséquence d'une maladresse (7.4) -----------------------------------------------------

@pytest.mark.parametrize("d6", [1, 2])
def test_maladresse_1_ou_2_arme_lachee_reprise_par_une_action_mineure(d6):
    k, g = kaito(), ganger()
    c = combat(DesTruques(97, d6), k, g)
    rapport = c.attaquer(g, k)
    assert rapport.attaque.degre is Degre.MALADRESSE
    assert g.arme is None and g.arme_lachee is COUTEAU
    assert any("lâche" in e for e in rapport.effets)
    c.degainer(g, g.arme_lachee)
    assert g.arme is COUTEAU and g.arme_lachee is None
    assert g.budget.utilise[TypeAction.MINEURE] == 1


@pytest.mark.parametrize("d6", [3, 4])
def test_maladresse_3_ou_4_desequilibre_la_prochaine_defense_seulement(d6):
    k, g = kaito(COUTEAU), ganger()
    c = combat(DesTruques(97, d6, 20, 50, 2), k, g)
    rapport = c.attaquer(g, k)
    assert g.desequilibre and any("Déséquilibre" in e for e in rapport.effets)
    riposte = c.attaquer(k, g, Defense.ESQUIVE)  # Esquive du ganger : 45, moins 20
    assert riposte.defense.valeur == 45 - 20
    assert not g.desequilibre


@pytest.mark.parametrize("d6", [5, 6])
def test_maladresse_5_ou_6_enraye_une_arme_a_distance(d6):
    k, g = kaito(), ganger()
    c = combat(DesTruques(100, d6), k, g)  # Armes à distance 50 : maladresse sur 100 seulement
    rapport = c.attaquer(k, g)
    assert k.arme_enrayee is PISTOLET and any("enraye" in e for e in rapport.effets)
    c.fin_de_round()
    with pytest.raises(ActionImpossible, match="enrayée"):
        c.attaquer(k, g)
    c.debloquer(k)
    assert k.arme_enrayee is None and k.budget.utilise[TypeAction.MINEURE] == 1


@pytest.mark.parametrize("d6", [5, 6])
def test_maladresse_5_ou_6_au_corps_a_corps_arme_lachee(d6):
    k, g = kaito(), ganger()
    rapport = combat(DesTruques(97, d6), k, g).attaquer(g, k)
    assert g.arme is None and g.arme_lachee is COUTEAU and g.arme_enrayee is None
    assert any("lâche" in e for e in rapport.effets)


def test_une_arme_fragile_se_brise_et_le_d6_est_tire_en_plus():
    batte = Arme("Batte fêlée", CORPS_A_CORPS, "1d6", Portee.CONTACT, proprietes=frozenset({Propriete.FRAGILE}))
    k, g = kaito(), ganger(arme=batte)
    rapport = combat(DesTruques(97, 4), k, g).attaquer(g, k)
    assert g.arme is None and g.arme_lachee is None  # brisée, pas lâchée
    assert g.desequilibre and any("se brise" in e for e in rapport.effets)


def test_sans_arme_en_main_une_arme_lachee_ne_change_rien():
    k, g = kaito(), ganger(arme=None)
    rapport = combat(DesTruques(97, 1), k, g).attaquer(g, k)
    assert g.arme is None and g.arme_lachee is None and rapport.effets == []


def test_un_debloquage_sans_arme_enrayee_est_refuse():
    k = kaito()
    with pytest.raises(ActionImpossible, match="pas enrayée"):
        combat(DesTruques(), k, ganger()).debloquer(k)


# --- La défense et la difficulté par défaut (7.3) ---------------------------------------------

def test_la_defense_par_defaut_est_la_meilleure_des_deux():
    k = kaito()  # Esquive 50, Corps à corps 25
    assert Combat.defense_par_defaut(k) is Defense.ESQUIVE
    brute = Combattant(FichePnj("Brute", combat=60, pv_max_base=10, competences={"Esquive": 30}), "ennemis", COUTEAU)
    assert Combat.defense_par_defaut(brute) is Defense.RIPOSTE


def test_a_egalite_la_defense_par_defaut_est_l_esquive():
    assert Combat.defense_par_defaut(ganger()) is Defense.ESQUIVE  # 45 et 45


def test_la_difficulte_est_normale_contre_une_cible_qui_se_defend():
    c = combat(DesTruques(), kaito(), ganger())
    assert c.difficulte_contre(c.ordre[0]) is Difficulte.NORMALE


@pytest.mark.parametrize("etat", [Etat.INCONSCIENT, Etat.MOURANT, Etat.STABLE])
def test_la_difficulte_est_facile_contre_une_cible_hors_jeu(etat):
    k, g = kaito(), ganger()
    g.fiche.etat = etat
    assert combat(DesTruques(), k, g).difficulte_contre(g) is Difficulte.FACILE


def test_la_difficulte_est_facile_contre_une_cible_surprise_et_normale_ensuite():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g, surpris=[g])
    assert c.difficulte_contre(g) is Difficulte.FACILE
    c.fin_de_round()
    assert c.difficulte_contre(g) is Difficulte.NORMALE


def test_attaquer_applique_la_difficulte_du_code_et_une_valeur_donnee_la_remplace():
    k, g = kaito(), ganger()
    g.fiche.etat = Etat.INCONSCIENT
    assert combat(DesTruques(90), k, g).attaquer(k, g).attaque.valeur == 50 + 20
    k2 = kaito()
    assert combat(DesTruques(90), k2, g).attaquer(k2, g, difficulte=Difficulte.DIFFICILE).attaque.valeur == 50 - 20


# --- Le bonus d'une réussite majeure (7.4) ----------------------------------------------------

def test_une_reussite_majeure_au_tir_n_offre_pas_de_choix_contre_un_ennemi_desarme():
    k, g = kaito(), ganger(arme=None)
    assert Combat.options_majeure(k, g) == [BonusMajeure.DE_SUPPLEMENTAIRE]


def test_une_reussite_majeure_peut_desarmer_un_ennemi_arme():
    k, g = kaito(), ganger()
    assert Combat.options_majeure(k, g) == [BonusMajeure.DE_SUPPLEMENTAIRE, BonusMajeure.DESARMER]


def test_au_corps_a_corps_on_peut_aussi_repousser():
    k, g = kaito(COUTEAU), ganger()
    assert Combat.options_majeure(k, g) == [
        BonusMajeure.DE_SUPPLEMENTAIRE, BonusMajeure.DESARMER, BonusMajeure.REPOUSSER]


# --- La chance de toucher, pour le menu du joueur ---------------------------------------------

def test_la_chance_de_reussite_compte_les_jets_qui_passent():
    assert chance_de_reussite(50) == 50  # de 1 à 50 ; le 100 seul est une maladresse
    assert chance_de_reussite(30) == 30
    assert chance_de_reussite(0) == 1  # un 01 réussit toujours


def test_la_chance_de_toucher_suit_le_couvert_la_visee_et_la_difficulte():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g)
    assert c.chance_de_toucher(k, g) == 50
    c.se_mettre_a_couvert(g)
    assert c.chance_de_toucher(k, g) == 30
    k.vise = True
    assert c.chance_de_toucher(k, g) == 50
    g.fiche.etat = Etat.INCONSCIENT
    assert c.chance_de_toucher(k, g) == 70  # 50, couvert −20, visée +20, cible hors jeu +20


def test_estimer_la_chance_ne_change_rien_au_combat():
    k, g = kaito(), ganger()
    k.vise = True
    c = combat(DesTruques(), k, g)
    c.chance_de_toucher(k, g)
    assert k.vise and k.budget.utilise[TypeAction.SIMPLE] == 0


# --- Le moral des ennemis (7.8) ---------------------------------------------------------------

def test_un_ennemi_en_pleine_forme_n_a_rien_a_tester():
    c = combat(DesTruques(), kaito(), ganger())
    g = c.ordre[1]
    assert c.declencheurs_de_moral(g) == [] and c.tester_moral(g) is None


def test_la_moitie_des_pv_met_le_moral_a_l_epreuve_et_un_echec_fait_fuir():
    k, g = kaito(), ganger(pv=5)
    c = combat(DesTruques(90), k, g)
    rapport = c.tester_moral(g)
    assert rapport.declencheurs == ["la moitié de ses PV"]
    assert rapport.test.valeur == 45 and rapport.moral is Moral.EN_FUITE and g.moral is Moral.EN_FUITE


def test_un_test_reussi_garde_l_ennemi_au_combat():
    g = ganger(pv=5)
    rapport = combat(DesTruques(20), kaito(), g).tester_moral(g)
    assert rapport.moral is Moral.NORMAL and g.moral is Moral.NORMAL


def test_chaque_declencheur_en_plus_donne_moins_20():
    g, mort = ganger(pv=5, nom="A"), ganger(nom="B")
    mort.fiche.etat = Etat.INCONSCIENT
    c = combat(DesTruques(30), kaito(), g, mort)
    rapport = c.tester_moral(g)
    assert rapport.declencheurs == ["la moitié de ses PV", "la moitié de son camp hors de combat"]
    assert rapport.test.valeur == 45 - 20 and g.moral is Moral.EN_FUITE  # 30 > 25


def test_une_menace_forte_ou_elite_a_plus_20():
    ch = chef(pv=5)
    rapport = combat(DesTruques(90), kaito(), ch).tester_moral(ch)
    assert rapport.test.valeur == 75 + 20 and rapport.moral is Moral.NORMAL  # 90 passe sous 95 ; sans le bonus, non


def test_une_blessure_grave_fait_se_rendre_au_lieu_de_fuir():
    g = ganger(pv=4, blessure_grave=True)
    rapport = combat(DesTruques(90), kaito(), g).tester_moral(g)
    assert "une blessure grave" in rapport.declencheurs
    assert rapport.moral is Moral.RENDU and g.hors_combat


def test_un_ennemi_rendu_ne_se_defend_plus_et_ne_joue_plus():
    k, g = kaito(), ganger(pv=4, blessure_grave=True)
    c = combat(DesTruques(90), k, g)
    c.tester_moral(g)
    assert not c.peut_agir(g) and not c.peut_se_defendre(g)
    assert c.difficulte_contre(g) is Difficulte.FACILE
    assert c.actifs("ennemis") == []


def test_le_moral_d_un_personnage_joueur_n_est_pas_teste_ici():
    k = kaito()
    k.fiche.pv = 1
    assert combat(DesTruques(), k, ganger()).tester_moral(k) is None


def test_un_ennemi_deja_en_fuite_n_est_pas_reteste():
    g = ganger(pv=5)
    c = combat(DesTruques(90), kaito(), g)
    c.tester_moral(g)
    assert c.tester_moral(g) is None


def test_l_ennemi_en_fuite_part_a_la_fin_de_son_prochain_tour_et_reste_une_cible_d_ici_la():
    k, g = kaito(), ganger(pv=5)
    c = combat(DesTruques(90, 90), k, g, tour_par_tour=True)
    assert c.au_tour_de is k
    c.fin_de_tour()
    assert c.au_tour_de is g
    c.tester_moral(g)  # il craque à son tour
    c.fin_de_tour()  # fin du tour où il a craqué : il est encore là
    assert g.moral is Moral.EN_FUITE and c.actifs("ennemis") == [g]
    c.fin_de_tour()  # Kaito
    assert c.au_tour_de is g and g.moral is Moral.EN_FUITE
    c.fin_de_tour()  # fin de son prochain tour : il part
    assert g.moral is Moral.PARTI and not c.peut_agir(g) and c.actifs("ennemis") == []


def test_on_ne_peut_plus_attaquer_celui_qui_a_quitte_le_combat():
    k, g = kaito(), ganger()
    g.moral = Moral.PARTI
    with pytest.raises(ActionImpossible, match="quitté"):
        combat(DesTruques(), k, g).attaquer(k, g)


def test_le_seuil_de_menace_forte_suit_la_table_des_menaces():
    moyenne = next(m for m in gains.MENACES if m[0] == "moyenne")
    assert SEUIL_MENACE_FORTE == moyenne[1]
    assert gains.menace(SEUIL_MENACE_FORTE)[0] == "moyenne" and gains.menace(SEUIL_MENACE_FORTE + 1)[0] == "forte"
