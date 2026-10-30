import pytest

from aria.combat import (
    ActionImpossible,
    BonusMajeure,
    BudgetRound,
    Combat,
    Combattant,
    Couvert,
    Defense,
    FichePnj,
    TypeAction,
    laisser_pour_mort,
    tester_embuscade,
)
from aria.des import DesTruques
from aria.equipement import (
    ARMES_A_DISTANCE,
    CORPS_A_CORPS,
    Arme,
    Armure,
    Munitions,
    Portee,
    Propriete,
    Recharge,
)
from aria.personnage import Etat, creer_personnage
from aria.reglages import Curseur
from aria.resolution import Degre, Difficulte, Issue
from tests.test_personnage import netrunner

COUTEAU = Arme("Couteau", CORPS_A_CORPS, "1d4", Portee.CONTACT)
PISTOLET = Arme("Pistolet", ARMES_A_DISTANCE, "1d10", Portee.COURTE, munitions=Munitions(8, Recharge.MINEURE))
FUSIL = Arme("Fusil", ARMES_A_DISTANCE, "2d6+2", Portee.LONGUE, munitions=Munitions(30, Recharge.MINEURE))
GILET = Armure("Gilet pare-balles", 3)


def kaito(arme=PISTOLET, armure=None):
    """Le Netrunner : Dextérité 60, Esquive 50, Corps à corps 25, Armes à distance 50, Force 35, 8 PV."""
    return Combattant(creer_personnage(**netrunner()), "joueur", arme, armure)


def ganger(arme=COUTEAU, armure=None, nom="Ganger", **profil):
    """Un ennemi type : 45 % en combat, 10 PV, Dextérité 55."""
    profil.setdefault("dexterite", 55)
    return Combattant(FichePnj(nom, combat=45, pv_max_base=10, **profil), "ennemis", arme, armure)


def combat(des, *combattants, **options):
    return Combat(des, list(combattants), **options)


# --- Initiative et budget ------------------------------------------------------------

def test_initiative_par_dexterite_puis_perception():
    k, g = kaito(), ganger()
    lent = ganger(nom="Lent", dexterite=30)
    vigilant = ganger(nom="Vigilant", dexterite=55, perception=60)
    assert [c.nom for c in combat(DesTruques(), lent, g, k, vigilant).ordre] == ["Kaito", "Vigilant", "Ganger", "Lent"]


def test_budget_option_a_un_deplacement_une_simple_une_mineure():
    budget = BudgetRound()
    for action in (TypeAction.DEPLACEMENT, TypeAction.SIMPLE, TypeAction.MINEURE):
        budget.utiliser(action)
    for action in TypeAction:
        assert not budget.peut(action)


def test_budget_option_b_deux_deplacements_une_mineure():
    budget = BudgetRound()
    budget.utiliser(TypeAction.DEPLACEMENT)
    budget.utiliser(TypeAction.DEPLACEMENT)
    assert not budget.peut(TypeAction.SIMPLE)
    budget.utiliser(TypeAction.MINEURE)
    assert not budget.peut(TypeAction.MINEURE)


def test_budget_pas_de_second_deplacement_apres_une_action_simple():
    budget = BudgetRound()
    budget.utiliser(TypeAction.SIMPLE)
    budget.utiliser(TypeAction.DEPLACEMENT)
    with pytest.raises(ActionImpossible):
        budget.utiliser(TypeAction.DEPLACEMENT)


# --- Corps à corps -------------------------------------------------------------------

def test_attaque_touche_si_l_esquive_rate():
    k, g = kaito(), ganger()
    # Ganger 30 (réussite), esquive de Kaito 62 (échec), couteau 3
    rapport = combat(DesTruques(30, 62, 3), k, g).attaquer(g, k, Defense.ESQUIVE)
    assert rapport.issue is Issue.ATTAQUANT
    assert rapport.touche == "Kaito"
    assert k.fiche.pv == 5
    assert not rapport.blessure.blessure_grave  # 3 < 8 / 2


def test_egalite_l_esquive_gagne():
    k, g = kaito(), ganger()
    rapport = combat(DesTruques(30, 40), k, g).attaquer(g, k, Defense.ESQUIVE)  # réussite contre réussite
    assert rapport.issue is Issue.DEFENSEUR
    assert rapport.touche is None
    assert k.fiche.pv == 8


def test_egalite_la_riposte_perd():
    k, g = kaito(), ganger()
    rapport = combat(DesTruques(30, 20, 2), k, g).attaquer(g, k, Defense.RIPOSTE)
    assert rapport.issue is Issue.ATTAQUANT
    assert k.fiche.pv == 6


def test_riposte_gagnante_touche_l_attaquant():
    k, g = kaito(), ganger()
    # Riposte de Kaito à 25 : 05 = critique. Mains nues 1d3 au maximum (3), Force 35 donc −1 : 2 dégâts.
    rapport = combat(DesTruques(30, 5), k, g).attaquer(g, k, Defense.RIPOSTE)
    assert rapport.issue is Issue.DEFENSEUR
    assert rapport.touche == "Ganger"
    assert rapport.degats_bruts == 2
    assert g.fiche.pv == 8


def test_defense_supplementaire_a_moins_20():
    k, g1, g2 = kaito(), ganger(), ganger(nom="Ganger 2")
    c = combat(DesTruques(80, 40, 80, 40), k, g1, g2)
    assert c.attaquer(g1, k, Defense.ESQUIVE).defense.valeur == 50
    assert c.attaquer(g2, k, Defense.ESQUIVE).defense.valeur == 30


# --- Tir -------------------------------------------------------------------------------

def test_tir_sans_esquive_avec_couvert_et_munitions():
    k, g = kaito(), ganger()
    # Couvert partiel : 50 − 20 = 30. Jet 20 (réussite), 1d10 = 6, puis test de Constitution raté (70).
    rapport = combat(DesTruques(20, 6, 70), k, g).attaquer(k, g, Defense.ESQUIVE, couvert=Couvert.PARTIEL)
    assert rapport.attaque.valeur == 30
    assert rapport.defense is None  # on n'esquive pas une balle
    assert k.munitions_restantes() == 7
    assert rapport.blessure.blessure_grave  # 6 ≥ 10 / 2
    assert g.fiche.pv == 4
    assert g.fiche.pv_max == 5
    assert g.fiche.etat is Etat.INCONSCIENT


def test_viser_puis_tirer_dans_le_meme_round():
    k, g = kaito(), ganger()
    c = combat(DesTruques(80, 80), k, g)
    c.viser(k)  # action mineure
    assert c.attaquer(k, g).attaque.valeur == 70
    assert not k.vise  # le bonus ne sert qu'une fois
    c.fin_de_round()
    assert c.attaquer(k, g).attaque.valeur == 50


def test_viser_interdit_de_se_deplacer_ce_round():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g)
    c.deplacer(k)
    with pytest.raises(ActionImpossible):
        c.viser(k)
    c.fin_de_round()
    c.viser(k)
    with pytest.raises(ActionImpossible):
        c.deplacer(k)


def test_pas_de_deplacement_apres_un_tir_vise():
    k, g = kaito(), ganger()
    c = combat(DesTruques(80), k, g)
    c.viser(k)
    c.attaquer(k, g)  # le bonus est consommé…
    with pytest.raises(ActionImpossible):
        c.deplacer(k)  # … mais il a quand même visé ce round


def test_la_visee_se_perd_en_fin_de_round():
    k, g = kaito(), ganger()
    c = combat(DesTruques(80), k, g)
    c.viser(k)
    c.fin_de_round()
    assert c.attaquer(k, g).attaque.valeur == 50


def test_arme_vide_puis_rechargement():
    un_coup = Arme("Fusil à un coup", ARMES_A_DISTANCE, "2d6", Portee.LONGUE, munitions=Munitions(1, Recharge.SIMPLE))
    k, g = kaito(arme=un_coup), ganger()
    c = combat(DesTruques(90, 90), k, g)
    c.attaquer(k, g)
    c.fin_de_round()
    with pytest.raises(ActionImpossible):
        c.attaquer(k, g)
    c.recharger(k)  # rechargement en action simple : plus d'attaque ce round
    with pytest.raises(ActionImpossible):
        c.attaquer(k, g)
    c.fin_de_round()
    c.attaquer(k, g)


def test_arme_de_lancer_quitte_la_main():
    javelot = Arme("Javelot", ARMES_A_DISTANCE, "1d8", Portee.COURTE, proprietes=frozenset({Propriete.LANCER}))
    k, g = kaito(arme=javelot), ganger()
    rapport = combat(DesTruques(60), k, g).attaquer(k, g)
    assert k.arme is None
    assert any("lancée" in e for e in rapport.effets)


# --- Degrés de réussite ----------------------------------------------------------------

def test_critique_degats_max_et_armure_a_moitie():
    k, g = kaito(), ganger(armure=GILET)
    # 05 ≤ 50 / 5 : critique. 1d10 au maximum = 10, gilet 3 // 2 = 1, donc 9 dégâts. Constitution réussie (20).
    rapport = combat(DesTruques(5, 20), k, g).attaquer(k, g)
    assert rapport.attaque.degre is Degre.CRITIQUE
    assert (rapport.degats_bruts, rapport.protection) == (10, 1)
    assert g.fiche.pv == 1
    assert g.fiche.etat is Etat.ACTIF


def test_majeure_de_supplementaire():
    k, g = kaito(), ganger()
    # 20 ≤ 50 / 2 : majeure. 1d10 = 4, +1d10 = 3, donc 7. Constitution réussie (10).
    rapport = combat(DesTruques(20, 4, 3, 10), k, g).attaquer(k, g)
    assert rapport.degats_bruts == 7
    assert g.fiche.pv == 3


def test_majeure_desarmer():
    k, g = kaito(), ganger()
    rapport = combat(DesTruques(15, 2), k, g).attaquer(g, k, bonus_majeure=BonusMajeure.DESARMER)
    assert rapport.attaque.degre is Degre.MAJEURE
    assert k.arme is None
    assert k.fiche.pv == 6


def test_maladresse_brise_une_arme_fragile():
    batte = Arme("Batte fêlée", CORPS_A_CORPS, "1d6", Portee.CONTACT, proprietes=frozenset({Propriete.FRAGILE}))
    k, g = kaito(), ganger(arme=batte)
    rapport = combat(DesTruques(97), k, g).attaquer(g, k)  # combat 45 : maladresse de 96 à 100
    assert rapport.attaque.degre is Degre.MALADRESSE
    assert g.arme is None
    assert k.fiche.pv == 8


# --- Blessures, agonie et destin ---------------------------------------------------------

def test_mort_instantanee_seulement_en_realiste():
    def brute():
        return ganger(arme=Arme("Masse lourde", CORPS_A_CORPS, "2d6+2", Portee.CONTACT))

    k, b = kaito(), brute()
    rapport = combat(DesTruques(3), k, b, curseur=Curseur.REALISTE).attaquer(b, k)  # critique : 14
    assert rapport.blessure.mort_instantanee
    assert k.fiche.etat is Etat.MORT

    k, b = kaito(), brute()
    combat(DesTruques(3), k, b, curseur=Curseur.STANDARD).attaquer(b, k)
    assert k.fiche.pv == 0
    assert k.fiche.etat is Etat.MOURANT


def test_le_mourant_teste_sa_constitution_en_fin_de_round():
    k, g = kaito(), ganger()
    k.fiche.pv, k.fiche.etat = 0, Etat.MOURANT
    c = combat(DesTruques(30, 60), k, g)
    assert c.fin_de_round()[0][1].reussi  # Constitution 45 : 30 réussit
    assert k.fiche.etat is Etat.MOURANT
    c.fin_de_round()  # 60 échoue
    assert k.fiche.etat is Etat.MORT


def test_sursis_du_mourant():
    k, g = kaito(), ganger()
    k.fiche.pv = 2
    c = combat(DesTruques(30, 3, 60), k, g)
    c.attaquer(g, k)  # couteau : 3 dégâts, Kaito tombe à 0 et devient mourant
    assert k.fiche.etat is Etat.MOURANT
    assert c.fin_de_round() == []  # sursis : pas de test à la fin du round où il tombe
    assert c.fin_de_round()[0][1].jet == 60  # premier test à la fin du round suivant
    assert k.fiche.etat is Etat.MORT


def test_stabiliser_un_mourant():
    k, g = kaito(), ganger()
    g.fiche.pv, g.fiche.etat = 0, Etat.MOURANT
    assert combat(DesTruques(3), k, g).stabiliser(k, g).reussi  # Médecine 5
    assert g.fiche.etat is Etat.STABLE


def test_point_de_destin_laisse_pour_mort():
    k = kaito()
    k.fiche.points_destin = 1
    k.fiche.pv, k.fiche.etat = 0, Etat.MORT
    laisser_pour_mort(k)
    assert k.fiche.etat is Etat.STABLE
    assert k.fiche.points_destin == 0
    k.fiche.etat = Etat.MORT
    with pytest.raises(ActionImpossible):
        laisser_pour_mort(k)


def test_difficulte_choisie_par_le_mj():
    k, g = kaito(), ganger()
    k.fiche.etat = Etat.INCONSCIENT
    rapport = combat(DesTruques(60, 2), k, g).attaquer(g, k, difficulte=Difficulte.FACILE)
    assert rapport.attaque.valeur == 65  # 45 + 20 contre une cible sans défense
    assert rapport.issue is Issue.ATTAQUANT


def test_pnj_competences_hors_combat():
    medecin = FichePnj("Charcudoc", combat=30, pv_max_base=10, competences={"Médecine": 70})
    assert medecin.competence("Médecine") == 70
    assert medecin.competence("Esquive") == 30  # compétence de combat
    assert medecin.competence("Perception") == 25
    assert medecin.competence("Piratage") == 25  # valeur par défaut
    medecin.blessure_grave = True
    assert medecin.valeur("Médecine") == 50


def test_on_n_attaque_pas_un_mort():
    k, g = kaito(), ganger()
    g.fiche.etat = Etat.MORT
    with pytest.raises(ActionImpossible):
        combat(DesTruques(), k, g).attaquer(k, g)


# --- Malus ---------------------------------------------------------------------------------

def test_malus_de_blessure_grave_et_d_armure():
    k = kaito(armure=Armure("Exosquelette", 5, {"Esquive": -20}))
    assert k.valeur("Esquive") == 30
    k.fiche.blessure_grave = True
    assert k.valeur("Esquive") == 10
    assert k.valeur("Perception") == 30
    assert k.fiche.pv_max == 4


# --- Embuscade -----------------------------------------------------------------------------

def test_embuscade():
    # Discrétion 60 : 10 = critique ; Perception 50 : 40 = réussite. Victimes surprises.
    rapport = tester_embuscade(DesTruques(10, 40), perception_victimes=50, discretion_agresseurs=60)
    assert rapport.surpris
    assert (rapport.discretion.degre, rapport.perception.degre) == (Degre.CRITIQUE, Degre.REUSSITE)
    # Majeure contre majeure : l'égalité profite aux victimes.
    assert not tester_embuscade(DesTruques(20, 20), perception_victimes=50, discretion_agresseurs=60).surpris


def test_le_camp_surpris_perd_son_premier_round():
    k, g = kaito(), ganger()
    c = combat(DesTruques(30, 2), k, g, surpris=[k])
    assert not c.peut_agir(k)
    with pytest.raises(ActionImpossible):
        c.deplacer(k)
    rapport = c.attaquer(g, k, Defense.ESQUIVE)
    assert rapport.defense is None  # surpris : pas de défense
    c.fin_de_round()
    assert c.peut_agir(k)
