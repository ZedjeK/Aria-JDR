import random

from appli import fond
from appli.donnees import Fond


def test_la_duree_d_un_passage_suit_la_vitesse():
    assert [fond.duree_passage(Fond(vitesse=v)) for v in ("lente", "normale", "rapide")] == [14.0, 7.0, 3.5]


def test_le_fond_est_coupe_si_desactive_ou_si_le_systeme_demande_moins_d_animations():
    assert fond.mode(Fond(actif=False), True, True) == fond.COUPE
    assert fond.mode(Fond(), True, False) == fond.COUPE


def test_le_fond_est_en_pause_quand_la_page_est_cachee_et_tourne_sinon():
    assert fond.mode(Fond(), False, True) == fond.EN_PAUSE
    assert fond.mode(Fond(), True, True) == fond.ACTIF


def test_le_tirage_reste_entre_les_bornes_et_les_atteint():
    hasard = random.Random(1)
    tirages = {fond.tirage(Fond(minimum=2, maximum=5), hasard) for _ in range(200)}
    assert tirages == {2, 3, 4, 5}
    assert fond.tirage(Fond(minimum=9, maximum=3), hasard) in range(3, 10)
