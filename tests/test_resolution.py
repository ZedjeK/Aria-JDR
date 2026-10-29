import pytest

from aria.des import DesTruques
from aria.resolution import Degre, Difficulte, Issue, Resultat, calculer_degre, forcer, opposer, tester


# Exemple de REGLES.md 2.2, compétence à 50 :
# critique 01-10, majeure 11-25, réussite 26-40, complication 41-50, échec 51-99, maladresse 100.
@pytest.mark.parametrize(
    "jet, attendu",
    [
        (1, Degre.CRITIQUE),
        (10, Degre.CRITIQUE),
        (11, Degre.MAJEURE),
        (25, Degre.MAJEURE),
        (26, Degre.REUSSITE),
        (40, Degre.REUSSITE),
        (41, Degre.COMPLICATION),
        (50, Degre.COMPLICATION),
        (51, Degre.ECHEC),
        (99, Degre.ECHEC),
        (100, Degre.MALADRESSE),
    ],
)
def test_exemple_competence_50(jet, attendu):
    assert calculer_degre(jet, 50) == attendu


def test_pas_de_complication_en_combat():
    assert calculer_degre(45, 50, combat=True) == Degre.REUSSITE
    assert calculer_degre(50, 50, combat=True) == Degre.REUSSITE
    assert calculer_degre(51, 50, combat=True) == Degre.ECHEC


@pytest.mark.parametrize(
    "valeur, jet, attendu",
    [
        (49, 96, Degre.MALADRESSE),  # sous 50, maladresse de 96 à 100
        (49, 95, Degre.ECHEC),
        (50, 96, Degre.ECHEC),  # à partir de 50, maladresse sur 100 seulement
        (50, 100, Degre.MALADRESSE),
        (115, 99, Degre.REUSSITE),  # une compétence au-delà de 100 peut réussir un 99
        (115, 100, Degre.MALADRESSE),  # mais 100 reste une maladresse
    ],
)
def test_maladresse(valeur, jet, attendu):
    assert calculer_degre(jet, valeur) == attendu


@pytest.mark.parametrize("valeur", [-25, 0, 1])
def test_01_toujours_au_moins_une_reussite_simple(valeur):
    assert calculer_degre(1, valeur) == Degre.REUSSITE


def test_01_garde_un_meilleur_degre():
    assert calculer_degre(1, 4) == Degre.MAJEURE  # 01 ≤ 4 / 2
    assert calculer_degre(1, 5) == Degre.CRITIQUE  # 01 ≤ 5 / 5


def test_valeur_negative_echoue_sauf_01():
    assert calculer_degre(2, -25) == Degre.ECHEC


def test_jet_impossible():
    with pytest.raises(ValueError):
        calculer_degre(0, 50)
    with pytest.raises(ValueError):
        calculer_degre(101, 50)


def test_difficulte_appliquee_avant_les_degres():
    # Exemple de REGLES.md 2.2 : 60 en Difficile = 40, critique jusqu'à 08, majeure jusqu'à 20.
    assert tester(DesTruques(8), 60, Difficulte.DIFFICILE).degre == Degre.CRITIQUE
    assert tester(DesTruques(9), 60, Difficulte.DIFFICILE).degre == Degre.MAJEURE
    assert tester(DesTruques(20), 60, Difficulte.DIFFICILE).degre == Degre.MAJEURE
    resultat = tester(DesTruques(41), 60, Difficulte.DIFFICILE)
    assert resultat.valeur == 40
    assert resultat.degre == Degre.ECHEC


@pytest.mark.parametrize(
    "difficulte, modificateur",
    [(Difficulte.FACILE, 20), (Difficulte.NORMALE, 0), (Difficulte.DIFFICILE, -20), (Difficulte.EXTREME, -40)],
)
def test_liste_des_difficultes(difficulte, modificateur):
    assert difficulte.modificateur == modificateur
    assert tester(DesTruques(50), 50, difficulte).valeur == 50 + modificateur


def test_forcer_un_jet_rate():
    premier = tester(DesTruques(80), 50)
    assert not premier.reussi
    second = forcer(DesTruques(30), 50, premier)
    assert second.force
    assert second.reussi
    assert not second.consequence_grave


def test_forcer_et_rater_donne_une_consequence_grave():
    premier = tester(DesTruques(80), 50)
    second = forcer(DesTruques(90), 50, premier)
    assert not second.reussi
    assert second.consequence_grave


def test_on_ne_force_pas_un_jet_reussi():
    with pytest.raises(ValueError):
        forcer(DesTruques(30), 50, tester(DesTruques(20), 50))


def test_on_ne_force_qu_une_fois():
    premier = tester(DesTruques(80), 50)
    second = forcer(DesTruques(90), 50, premier)
    with pytest.raises(ValueError):
        forcer(DesTruques(10), 50, second)


def _resultat(degre: Degre) -> Resultat:
    return Resultat(jet=50, valeur=50, degre=degre)


@pytest.mark.parametrize(
    "attaque, defense, esquive, attendu",
    [
        # Le meilleur degré gagne
        (Degre.MAJEURE, Degre.REUSSITE, True, Issue.ATTAQUANT),
        (Degre.REUSSITE, Degre.CRITIQUE, True, Issue.DEFENSEUR),
        (Degre.REUSSITE, Degre.MAJEURE, False, Issue.DEFENSEUR),
        # Égalité : l'esquive gagne, la riposte perd
        (Degre.REUSSITE, Degre.REUSSITE, True, Issue.DEFENSEUR),
        (Degre.REUSSITE, Degre.REUSSITE, False, Issue.ATTAQUANT),
        (Degre.CRITIQUE, Degre.CRITIQUE, False, Issue.ATTAQUANT),
        # Un seul camp réussit
        (Degre.REUSSITE, Degre.ECHEC, True, Issue.ATTAQUANT),
        (Degre.ECHEC, Degre.REUSSITE, True, Issue.DEFENSEUR),
        (Degre.MALADRESSE, Degre.REUSSITE, False, Issue.DEFENSEUR),
        # Personne ne réussit
        (Degre.ECHEC, Degre.ECHEC, True, Issue.PERSONNE),
        (Degre.ECHEC, Degre.MALADRESSE, False, Issue.PERSONNE),
    ],
)
def test_opposition(attaque, defense, esquive, attendu):
    assert opposer(_resultat(attaque), _resultat(defense), esquive) == attendu


def test_degres_comparables_et_libelles():
    assert Degre.CRITIQUE > Degre.MAJEURE > Degre.REUSSITE > Degre.COMPLICATION > Degre.ECHEC > Degre.MALADRESSE
    assert Degre.COMPLICATION.est_reussite
    assert not Degre.ECHEC.est_reussite
    assert Degre.MAJEURE.libelle == "réussite majeure"
