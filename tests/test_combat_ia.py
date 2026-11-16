"""L'IA des ennemis, la boucle des tours, la fin du combat et le choix du mode (REGLES.md 7.8).

Les dés sont truqués. L'IA ne lance qu'un dé : le tirage de la cible quand il y en a plusieurs ; le reste de l'ordre
est celui du moteur (attaque, d6 d'une maladresse, défense, dégâts).
"""

import pytest

from aria.combat import Combat, Combattant, Couvert, Decor, FichePnj, Moral, TypeAction
from aria.combat_auto import (
    ROUNDS_MAX,
    Action,
    CombatAuto,
    Fin,
    Geste,
    ModeCombat,
    Registre,
    choisir_mode,
    poids_des_cibles,
    prochaine_action,
    tirer_la_cible,
)
from aria.des import DesTruques
from aria.equipement import ARMES_A_DISTANCE, Arme, Portee
from aria.inventaire import ReservePnj
from aria.personnage import Etat
from tests.test_combat import COUTEAU, PISTOLET, combat, ganger, kaito

GRENADE = Arme("Grenade", ARMES_A_DISTANCE, "2d6", Portee.COURTE, zone="petite", usage_unique=True)


def decider(c, combattant, registre=None, **kwargs):
    return prochaine_action(c, combattant, registre or Registre(), **kwargs)


def deux_ennemis_et_kaito(des=None, **options):
    k, a, b = kaito(), ganger(nom="Alpha"), ganger(nom="Bravo")
    return k, a, b, combat(des or DesTruques(), k, a, b, **options)


# --- Le mode du combat -------------------------------------------------------------------------

def test_un_combat_a_pied_ordinaire_est_mene_par_le_code():
    assert choisir_mode([kaito(), ganger(), ganger(arme=PISTOLET)]) is ModeCombat.A_PIED


def test_une_arme_de_zone_laisse_le_combat_au_mj():
    assert choisir_mode([kaito(), ganger(arme=GRENADE)]) is ModeCombat.CLASSIQUE


def test_un_pnj_lanceur_de_sorts_laisse_le_combat_au_mj():
    mage = Combattant(FichePnj("Mage", combat=30, pv_max_base=8, sorts=("Boule de feu",)), "ennemis")
    assert choisir_mode([kaito(), mage]) is ModeCombat.CLASSIQUE


def test_un_vehicule_laisse_le_combat_au_mj():
    assert choisir_mode([kaito(), ganger()], avec_vehicule=True) is ModeCombat.CLASSIQUE


def test_un_drone_laisse_le_combat_au_mj():
    drone = ganger(nom="Drone")
    drone.drone = object()  # seul compte qu'il y en ait un : choisir_mode ne regarde pas son modèle
    assert choisir_mode([kaito(), drone]) is ModeCombat.CLASSIQUE


# --- L'ordre des décisions (7.8) ---------------------------------------------------------------

def test_un_bretteur_attaque_sans_se_deplacer():
    k, g = kaito(), ganger()
    assert decider(combat(DesTruques(), k, g), g) == Action(Geste.ATTAQUER, k)


def test_un_tireur_se_met_a_couvert_avant_de_tirer_dans_un_decor_encombre():
    k, g = kaito(), ganger(arme=PISTOLET)
    c = combat(DesTruques(), k, g)
    assert decider(c, g) == Action(Geste.COUVERT)
    c.se_mettre_a_couvert(g)
    assert decider(c, g) == Action(Geste.ATTAQUER, k)  # il vient de bouger : pas de visée ce round


def test_un_tireur_tire_directement_dans_un_decor_degage():
    k, g = kaito(), ganger(arme=PISTOLET)
    assert decider(combat(DesTruques(), k, g, decor=Decor.DEGAGE), g) == Action(Geste.ATTAQUER, k)


def test_un_tireur_deja_a_couvert_vise_puis_tire():
    k, g = kaito(), ganger(arme=PISTOLET)
    c = combat(DesTruques(), k, g)
    g.couvert = Couvert.PARTIEL
    assert decider(c, g) == Action(Geste.VISER)
    c.viser(g)
    assert decider(c, g) == Action(Geste.ATTAQUER, k)


def test_un_tireur_a_couvert_ne_se_deplace_pas_de_nouveau():
    k, g = kaito(), ganger(arme=PISTOLET)
    g.couvert = Couvert.LOURD
    assert decider(combat(DesTruques(), k, g, decor=Decor.FORTIFIE), g).geste is not Geste.COUVERT


def test_un_chargeur_vide_se_recharge_avant_tout():
    k, g = kaito(), ganger(arme=PISTOLET)
    g.munitions[PISTOLET] = 0
    assert decider(combat(DesTruques(), k, g), g) == Action(Geste.RECHARGER)


def test_une_arme_lachee_se_ramasse_d_abord():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g)
    g.arme, g.arme_lachee = None, COUTEAU
    assert decider(c, g) == Action(Geste.RAMASSER)
    c.degainer(g, g.arme_lachee)
    assert decider(c, g) == Action(Geste.ATTAQUER, k)


def test_une_arme_enrayee_se_debloque_d_abord():
    k, g = kaito(), ganger(arme=PISTOLET)
    g.arme_enrayee = PISTOLET
    assert decider(combat(DesTruques(), k, g), g) == Action(Geste.DEBLOQUER)


def test_un_fuyard_court_sans_attaquer_et_n_a_que_deux_deplacements():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g)
    g.moral = Moral.EN_FUITE
    assert decider(c, g) == Action(Geste.FUIR)
    c.deplacer(g)
    assert decider(c, g) == Action(Geste.FUIR)
    c.deplacer(g)
    assert decider(c, g) is None


@pytest.mark.parametrize("moral", [Moral.RENDU, Moral.PARTI])
def test_un_ennemi_rendu_ou_parti_ne_fait_rien(moral):
    k, g = kaito(), ganger()
    g.moral = moral
    assert decider(combat(DesTruques(), k, g), g) is None


def test_une_fois_l_action_simple_depensee_le_tour_est_fini():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g)
    c.action_simple(g)
    assert decider(c, g) is None


def test_un_geste_interdit_par_le_moteur_n_est_pas_retente():
    k, g = kaito(), ganger(arme=PISTOLET)
    g.munitions[PISTOLET] = 0
    assert decider(combat(DesTruques(), k, g), g, interdits=frozenset({Geste.RECHARGER})) is None


def test_sans_adversaire_en_lice_on_ne_fait_rien():
    k, g = kaito(), ganger()
    k.fiche.etat = Etat.INCONSCIENT
    assert decider(combat(DesTruques(), k, g), g) is None


# --- Le choix de la cible (7.8) -------------------------------------------------------------------

def test_une_cible_pese_1_et_3_sous_la_moitie_de_ses_pv():
    k, g = kaito(), ganger()
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10, pv=4), "allies", COUTEAU)
    c = combat(DesTruques(), k, allie, g)
    assert dict(poids_des_cibles(c, g, Registre())) == {k: 1, allie: 3}


def test_la_moitie_exacte_des_pv_n_est_pas_sous_la_moitie():
    k, g = kaito(), ganger()
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10, pv=5), "allies", COUTEAU)
    assert dict(poids_des_cibles(combat(DesTruques(), k, allie, g), g, Registre()))[allie] == 1


def test_qui_m_a_blesse_au_round_precedent_pese_un_de_plus():
    k, a, b, c = deux_ennemis_et_kaito()
    registre = Registre()
    registre.blessures.add((k, a))
    registre.ouvrir(2)  # le round suivant : ce qui s'est passé devient la revanche
    assert dict(poids_des_cibles(c, a, registre))[k] == 2
    assert dict(poids_des_cibles(c, b, registre))[k] == 1  # Bravo n'a pas été blessé
    registre.ouvrir(3)  # et une revanche n'a qu'un round
    assert dict(poids_des_cibles(c, a, registre))[k] == 1


def test_un_inconscient_n_est_pas_une_cible_tant_qu_un_actif_reste():
    k, g = kaito(), ganger()
    allie_a_terre = Combattant(FichePnj("Allié", combat=40, pv_max_base=10), "allies", COUTEAU)
    allie_a_terre.fiche.etat = Etat.INCONSCIENT
    assert [c for c, _ in poids_des_cibles(combat(DesTruques(), k, allie_a_terre, g), g, Registre())] == [k]


def test_un_fuyard_reste_une_cible_mais_pas_un_ennemi_parti_ou_rendu():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g)
    g.moral = Moral.EN_FUITE
    assert [x for x, _ in poids_des_cibles(c, k, Registre())] == [g]
    g.moral = Moral.PARTI
    assert poids_des_cibles(c, k, Registre()) == []


def test_pas_plus_de_deux_attaquants_par_cible_sauf_cible_unique():
    k = kaito()
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10), "allies", COUTEAU)
    a, b, troisieme = ganger(nom="Alpha"), ganger(nom="Bravo"), ganger(nom="Charlie")
    c = combat(DesTruques(), k, allie, a, b, troisieme)
    registre = Registre()
    registre.attaquants[k] = {a, b}
    assert [x for x, _ in poids_des_cibles(c, troisieme, registre)] == [allie]  # Kaito est pris à deux
    registre.attaquants[allie] = {a, b}
    assert {x for x, _ in poids_des_cibles(c, troisieme, registre)} == {k, allie}  # tous pris : on revient au choix libre
    seul = combat(DesTruques(), kaito(), ganger())
    solo_k, solo_g = seul.ordre
    registre.attaquants = {solo_k: {a, b}}
    assert [x for x, _ in poids_des_cibles(seul, solo_g, registre)] == [solo_k]  # cible unique : le plafond saute


def test_le_tirage_pondere_suit_les_poids():
    k, g = kaito(), ganger()
    c = combat(DesTruques(1, 2, 3, 4), k, g)
    poids = [(k, 1), (g, 3)]
    assert [tirer_la_cible(c, poids) for _ in range(4)] == [k, g, g, g]


def test_une_cible_unique_se_choisit_sans_lancer_de_de():
    k, g = kaito(), ganger()
    des = DesTruques()
    assert tirer_la_cible(combat(des, k, g), [(k, 3)]) is k


# --- La boucle des tours ------------------------------------------------------------------------

def test_un_tour_de_bretteur_une_attaque_puis_la_main_passe():
    k, g = kaito(), ganger(dexterite=70)  # le ganger joue avant Kaito
    c = combat(DesTruques(90, 50), k, g, tour_par_tour=True)  # attaque ratée (45 %), puis la défense de Kaito
    rapport = CombatAuto(c).jouer_le_tour()
    assert [e.action.geste for e in rapport.evenements] == [Geste.ATTAQUER]
    assert rapport.evenements[0].attaque.cible == "Kaito"
    assert c.au_tour_de is k


def test_un_tireur_a_couvert_enchaine_couvert_et_tir():
    k, g = kaito(), ganger(arme=PISTOLET, dexterite=70)
    c = combat(DesTruques(90), k, g, tour_par_tour=True)  # un tir de loin : pas de défense
    rapport = CombatAuto(c).jouer_le_tour()
    assert [e.action.geste for e in rapport.evenements] == [Geste.COUVERT, Geste.ATTAQUER]
    assert g.couvert is Couvert.PARTIEL


def test_un_tireur_a_sec_recharge_et_tire_dans_le_meme_tour():
    k, g = kaito(), ganger(arme=PISTOLET, dexterite=70)
    g.munitions[PISTOLET] = 0
    g.couvert = Couvert.PARTIEL
    c = combat(DesTruques(90), k, g, tour_par_tour=True)
    gestes = [e.action.geste for e in CombatAuto(c).jouer_le_tour().evenements]
    assert gestes == [Geste.RECHARGER, Geste.ATTAQUER]  # recharge mineure : elle prend la place de la visée
    assert g.munitions_restantes() == 7


def test_un_ennemi_eprouve_teste_son_moral_et_s_enfuit_sans_attaquer():
    k, g = kaito(), ganger(dexterite=70, pv=4)  # 4 PV sur 10 : sous la moitié
    c = combat(DesTruques(99), k, g, tour_par_tour=True)  # le test de moral est raté
    rapport = CombatAuto(c).jouer_le_tour()
    assert rapport.moral.moral is Moral.EN_FUITE
    assert [e.action.geste for e in rapport.evenements] == [Geste.FUIR, Geste.FUIR]
    assert g.moral is Moral.EN_FUITE


def test_un_fuyard_quitte_le_combat_a_la_fin_de_son_prochain_tour():
    k, g = kaito(), ganger(dexterite=70, pv=4)
    c = combat(DesTruques(99), k, g, tour_par_tour=True)
    auto = CombatAuto(c)
    auto.jouer_le_tour()
    c.fin_de_tour()  # le tour de Kaito
    assert g.moral is Moral.EN_FUITE and auto.fin() is Fin.EN_COURS  # on peut encore le frapper
    auto.jouer_le_tour()
    assert g.moral is Moral.PARTI and auto.fin() is Fin.VICTOIRE


def test_un_blesse_grave_qui_craque_se_rend_et_ne_fait_rien():
    k, g = kaito(), ganger(dexterite=70, pv=4, blessure_grave=True)
    c = combat(DesTruques(99), k, g, tour_par_tour=True)
    rapport = CombatAuto(c).jouer_le_tour()
    assert g.moral is Moral.RENDU and rapport.passe and rapport.moral.moral is Moral.RENDU


def test_un_ennemi_qui_tient_son_moral_se_bat():
    k, g = kaito(), ganger(dexterite=70, pv=4)
    c = combat(DesTruques(10, 90, 50), k, g, tour_par_tour=True)  # moral réussi, attaque ratée, défense
    rapport = CombatAuto(c).jouer_le_tour()
    assert rapport.moral.moral is Moral.NORMAL
    assert [e.action.geste for e in rapport.evenements] == [Geste.ATTAQUER]


def test_une_arme_que_le_moteur_refuse_ne_bloque_pas_le_tour():
    k, g = kaito(), ganger(arme=PISTOLET, dexterite=70)
    g.reserve = ReservePnj(PISTOLET, chargeurs=0)
    g.reserve.cartouches = 0
    g.munitions[PISTOLET] = 0
    rapport = CombatAuto(combat(DesTruques(), k, g, tour_par_tour=True)).jouer_le_tour()
    assert rapport.passe  # plus rien à recharger : il passe, sans erreur


def test_la_boucle_s_arrete_au_tour_du_joueur():
    k, g = kaito(), ganger(dexterite=70)
    c = combat(DesTruques(90, 50), k, g, tour_par_tour=True)
    rapports = CombatAuto(c).avancer()
    assert [r.qui for r in rapports] == [g] and c.au_tour_de is k


def test_la_boucle_n_a_rien_a_jouer_quand_le_joueur_ouvre_le_round():
    k, g = kaito(), ganger()
    assert CombatAuto(combat(DesTruques(), k, g, tour_par_tour=True)).avancer() == []


def test_la_boucle_peut_mener_tout_le_monde_jusqu_a_la_fin():
    k, g = kaito(COUTEAU), ganger()  # au corps à corps, chaque attaque lance l'attaque puis la défense
    c = combat(DesTruques(*([90, 50] * 70)), k, g, tour_par_tour=True)
    auto = CombatAuto(c, mene=lambda _: True)
    auto.avancer()  # tout le monde rate : le combat s'essouffle
    assert auto.fin() is Fin.ESSOUFFLE and c.round > ROUNDS_MAX


def test_le_registre_se_souvient_de_qui_a_attaque_qui_et_l_oublie_au_round_suivant():
    k, g = kaito(), ganger(dexterite=70)
    c = combat(DesTruques(90, 50), k, g, tour_par_tour=True)
    auto = CombatAuto(c)
    auto.jouer_le_tour()
    assert auto.registre.attaquants[k] == {g}
    auto.registre.ouvrir(2)
    assert auto.registre.attaquants == {}


def test_le_registre_note_un_coup_qui_blesse():
    k, g = kaito(), ganger(dexterite=70)
    c = combat(DesTruques(40, 90, 3), k, g, tour_par_tour=True)  # le ganger touche (40), Kaito rate sa défense (90), 1d4
    auto = CombatAuto(c)
    auto.jouer_le_tour()
    assert (g, k) in auto.registre.blessures


def test_le_registre_note_une_riposte_qui_blesse_l_attaquant():
    k, r = kaito(COUTEAU), ganger(nom="Rapide", competences={"Corps à corps": 70})
    c = combat(DesTruques(10, 5, 10), k, r)  # Kaito touche (10), la riposte est un critique (5), et un test de Constitution
    assert Combat.defense_par_defaut(r).value == "riposte"
    registre = Registre()
    registre.noter(k, r, c.attaquer(k, r, defense=Combat.defense_par_defaut(r)))
    assert registre.blessures == {(r, k)}  # c'est le défenseur qui a blessé


# --- La fin du combat ------------------------------------------------------------------------------

def test_le_combat_continue_tant_que_les_deux_camps_tiennent():
    k, g = kaito(), ganger()
    assert CombatAuto(combat(DesTruques(), k, g)).fin() is Fin.EN_COURS


@pytest.mark.parametrize("etat", [Etat.INCONSCIENT, Etat.MOURANT, Etat.MORT])
def test_victoire_quand_plus_aucun_ennemi_n_est_debout(etat):
    k, g = kaito(), ganger()
    g.fiche.etat = etat
    assert CombatAuto(combat(DesTruques(), k, g)).fin() is Fin.VICTOIRE


@pytest.mark.parametrize("moral", [Moral.PARTI, Moral.RENDU])
def test_victoire_quand_les_ennemis_sont_partis_ou_rendus(moral):
    k, g = kaito(), ganger()
    g.moral = moral
    assert CombatAuto(combat(DesTruques(), k, g)).fin() is Fin.VICTOIRE


def test_defaite_quand_plus_personne_ne_tient_du_cote_du_joueur():
    k, g = kaito(), ganger()
    k.fiche.etat = Etat.INCONSCIENT
    assert CombatAuto(combat(DesTruques(), k, g)).fin() is Fin.DEFAITE


def test_un_allie_debout_garde_le_combat_ouvert():
    k, g = kaito(), ganger()
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10), "allies", COUTEAU)
    k.fiche.etat = Etat.INCONSCIENT
    assert CombatAuto(combat(DesTruques(), k, allie, g)).fin() is Fin.EN_COURS


def test_un_neutre_ne_compte_pour_personne():
    k, g = kaito(), ganger()
    passant = Combattant(FichePnj("Passant", combat=20, pv_max_base=8), "neutres")
    g.fiche.etat = Etat.INCONSCIENT
    assert CombatAuto(combat(DesTruques(), k, g, passant)).fin() is Fin.VICTOIRE
    assert poids_des_cibles(combat(DesTruques(), k, g, passant), passant, Registre()) == []


def test_un_ennemi_en_fuite_garde_le_combat_ouvert_jusqu_a_son_depart():
    k, g = kaito(), ganger()
    g.moral = Moral.EN_FUITE
    assert CombatAuto(combat(DesTruques(), k, g)).fin() is Fin.EN_COURS


# --- Le mode, à l'ouverture d'un combat, par les outils du MJ ---------------------------------------

def test_debut_combat_choisit_le_mode_et_fin_combat_l_efface():
    from tests.test_outils import ganger as pnj_ganger
    from tests.test_outils import session

    s = session()
    pnj_ganger(s)
    assert s.mode_combat is None
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert s.mode_combat is ModeCombat.A_PIED
    s.appeler("fin_combat", {"moments_forts": "Un coup d'essai."})
    assert s.mode_combat is None


def test_debut_combat_laisse_au_mj_un_combat_avec_une_grenade():
    from tests.test_outils import ganger as pnj_ganger
    from tests.test_outils import session

    s = session()
    pnj_ganger(s, arme="Grenade à fragmentation")
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert s.mode_combat is ModeCombat.CLASSIQUE
