"""Le simulateur de combats : il tourne, il est reproductible, et il tient ce que les règles de 7.8 visent.

Les bornes sont larges (la simulation est à graine fixe, donc stable) : elles protègent la cible des règles,
pas un chiffre précis. Si une règle change et fait sortir un scénario de sa borne, il faut le dire et la revoir.
"""

from aria import pnj
from aria.combat_auto import Fin
from aria.simulateur_combat import BRETTEUR, SCENARIOS, TIREUR, Scenario, simuler

DEUX_VOYOUS = next(s for s in SCENARIOS if s.nom.startswith("deux voyous moyens, un couteau"))


def test_chaque_scenario_se_termine_et_compte_tous_ses_combats():
    for scenario in SCENARIOS:
        bilan = simuler(scenario, combats=20)
        assert bilan.combats == 20 == sum(bilan.issues.values())
        assert Fin.EN_COURS not in bilan.issues
        assert all(1 <= r <= 31 for r in bilan.rounds)


def test_la_simulation_est_reproductible():
    assert simuler(DEUX_VOYOUS, 30).rounds == simuler(DEUX_VOYOUS, 30).rounds
    assert simuler(DEUX_VOYOUS, 30, graine=1).rounds != simuler(DEUX_VOYOUS, 30, graine=2).rounds


def test_le_joueur_debutant_gagne_le_plus_souvent_contre_deux_voyous_mais_pas_toujours():
    bilan = simuler(DEUX_VOYOUS, 300)
    assert 0.5 <= bilan.taux(Fin.VICTOIRE) <= 0.9
    assert bilan.taux(Fin.DEFAITE) >= 0.1


def test_un_combat_contre_deux_voyous_dure_de_trois_a_cinq_rounds():
    assert 3 <= simuler(DEUX_VOYOUS, 300).rounds_moyens <= 5


def test_un_voyou_faible_ne_tient_pas_tete_a_un_debutant():
    assert simuler(Scenario("faible", ((pnj.FAIBLE, BRETTEUR),)), 200).taux(Fin.VICTOIRE) >= 0.9


def test_une_elite_est_plus_dangereuse_qu_un_voyou_moyen():
    moyen = simuler(Scenario("moyen", ((pnj.MOYENNE, TIREUR),)), 200)
    elite = simuler(Scenario("élite", ((pnj.ELITE, TIREUR),)), 200)
    assert elite.taux(Fin.VICTOIRE) < moyen.taux(Fin.VICTOIRE)


def test_le_moral_fait_partir_ou_rendre_des_ennemis():
    bilan = simuler(DEUX_VOYOUS, 300)
    assert bilan.ennemis["parti"] + bilan.ennemis["rendu"] > 0


def test_la_ligne_du_tableau_se_lit():
    ligne = simuler(DEUX_VOYOUS, 10).ligne()
    assert "victoire" in ligne and "rounds" in ligne
