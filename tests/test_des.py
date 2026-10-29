import pytest

from aria.des import Des, DesTruques, Formule


@pytest.mark.parametrize(
    "texte, minimum, maximum",
    [
        ("1d10", 1, 10),
        ("d6", 1, 6),
        ("2d6+2", 4, 14),
        ("1d8+1d4", 2, 12),
        ("1d3-1", 0, 2),
        ("3d6", 3, 18),
        (" 2D6 + 2 ", 4, 14),
        ("5", 5, 5),
        ("1d6-1d4", -3, 5),
    ],
)
def test_formule_minimum_et_maximum(texte, minimum, maximum):
    formule = Formule.lire(texte)
    assert formule.minimum == minimum
    assert formule.maximum == maximum


@pytest.mark.parametrize("texte", ["", "d", "2d", "1d1", "0d6", "2d6+", "deux d six", "1d6*2"])
def test_formule_invalide(texte):
    with pytest.raises(ValueError):
        Formule.lire(texte)


def test_jet_avec_des_truques():
    # 2d6+2 avec un 3 et un 5 : 3 + 5 + 2 = 10
    des = DesTruques(3, 5)
    assert des.jet("2d6+2") == 10
    assert des.restantes == 0


def test_jet_avec_terme_soustrait():
    # 1d8-1d4 avec un 6 et un 4 : 6 - 4 = 2
    assert DesTruques(6, 4).jet("1d8-1d4") == 2


def test_des_truques_refusent_une_valeur_impossible():
    with pytest.raises(ValueError):
        DesTruques(7).lancer(6)


def test_des_truques_signalent_un_lancer_en_trop():
    des = DesTruques(4)
    des.lancer(6)
    with pytest.raises(AssertionError):
        des.lancer(6)


def test_des_aleatoires_restent_dans_les_bornes():
    des = Des(graine=42)
    for _ in range(1000):
        assert 1 <= des.d100() <= 100
        assert 4 <= des.jet("2d6+2") <= 14


def test_meme_graine_memes_tirages():
    assert [Des(graine=7).d100() for _ in range(5)] == [Des(graine=7).d100() for _ in range(5)]
