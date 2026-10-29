import pytest

from aria.des import DesTruques
from aria.personnage import Etat, creer_personnage
from aria.reglages import Curseur
from aria.soins import Repos, SoinImpossible, reposer, soigner
from aria.temps import Moment, Periode
from tests.test_personnage import netrunner

MATIN = Moment(1, Periode.MATIN)
APRES_MIDI = Moment(1, Periode.APRES_MIDI)
NUIT = Moment(1, Periode.NUIT)


def kaito(pv=None):
    """Kaito : 8 PV max. On lui donne 60 en Médecine pour les tests de soin."""
    perso = creer_personnage(**netrunner())
    perso.competences["Médecine"] = 60
    if pv is not None:
        perso.pv = pv
    return perso


# --- Médecine -------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "des, gain",
    [
        ((10, 4, 5), 9),  # 10 ≤ 60 / 5 : critique, 2d6
        ((20, 3), 3),  # majeure, 1d6
        ((45, 2), 2),  # réussite, 1d3
        ((55, 2), 2),  # réussite avec complication : reste une réussite, 1d3
        ((80,), 0),  # échec
        ((100,), -1),  # maladresse : la plaie est aggravée
    ],
)
def test_table_de_medecine(des, gain):
    patient = kaito(pv=3)
    rapport = soigner(DesTruques(*des), kaito(), patient, MATIN)
    assert rapport.gain == gain
    assert patient.pv == min(8, 3 + gain)


def test_un_jet_par_patient_et_par_demi_journee():
    patient = kaito(pv=3)
    soigner(DesTruques(80), kaito(), patient, MATIN)
    with pytest.raises(SoinImpossible):
        soigner(DesTruques(10), kaito(), patient, MATIN)  # même un autre soigneur
    soigner(DesTruques(80), kaito(), patient, APRES_MIDI)
    with pytest.raises(SoinImpossible):
        soigner(DesTruques(80), kaito(), patient, NUIT)


def test_soigner_une_blessure_grave():
    patient = kaito(pv=2)
    patient.blessure_grave = True
    assert soigner(DesTruques(45, 1), kaito(), patient, MATIN).blessure_grave_soignee
    assert patient.pv == 3


def test_le_soin_reveille_un_mourant():
    patient = kaito(pv=0)
    patient.etat = Etat.MOURANT
    soigner(DesTruques(45, 2), kaito(), patient, MATIN)
    assert patient.pv == 2
    assert patient.etat is Etat.ACTIF


def test_maladresse_a_1_pv():
    patient = kaito(pv=1)
    soigner(DesTruques(100), kaito(), patient, MATIN)
    assert patient.pv == 0
    assert patient.etat is Etat.MOURANT


def test_on_ne_soigne_pas_un_mort():
    patient = kaito(pv=0)
    patient.etat = Etat.MORT
    with pytest.raises(SoinImpossible):
        soigner(DesTruques(10), kaito(), patient, MATIN)


# --- Repos ---------------------------------------------------------------------------------

def test_repos_standard_court_puis_moyen():
    perso = kaito(pv=1)
    assert reposer(perso, Repos.COURT, MATIN).gain == 2  # 1/4 de 8
    with pytest.raises(SoinImpossible):
        reposer(perso, Repos.MOYEN, MATIN)  # un repos par demi-journée
    assert reposer(perso, Repos.MOYEN, APRES_MIDI).gain == 4  # 1/2 de 8
    assert perso.pv == 7


def test_repos_long_la_nuit_seulement():
    perso = kaito(pv=1)
    with pytest.raises(SoinImpossible):
        reposer(perso, Repos.LONG, MATIN)
    with pytest.raises(SoinImpossible):
        reposer(perso, Repos.COURT, NUIT)
    reposer(perso, Repos.LONG, NUIT)
    assert perso.pv == 8


def test_repos_long_standard_et_blessure_grave():
    perso = kaito(pv=1)
    perso.blessure_grave = True
    rapport = reposer(perso, Repos.LONG, NUIT)
    assert not rapport.blessure_grave_guerie  # pas soignée : elle reste
    assert perso.pv == 4  # PV max divisés par deux

    perso.blessure_grave_soignee = True
    rapport = reposer(perso, Repos.LONG, Moment(2, Periode.NUIT))
    assert rapport.blessure_grave_guerie
    assert not perso.blessure_grave
    assert perso.pv == 8


def test_repos_long_heroique_guerit_sans_soins():
    perso = kaito(pv=1)
    perso.blessure_grave = True
    assert reposer(perso, Repos.LONG, NUIT, Curseur.HEROIQUE).blessure_grave_guerie
    assert perso.pv == 8


def test_repos_realiste():
    perso = kaito(pv=1)
    assert reposer(perso, Repos.COURT, MATIN, Curseur.REALISTE).gain == 0
    assert reposer(perso, Repos.MOYEN, APRES_MIDI, Curseur.REALISTE).gain == 2  # 1/4 de 8
    assert reposer(perso, Repos.LONG, NUIT, Curseur.REALISTE).gain == 4  # 1/2 de 8


def test_realiste_la_blessure_grave_soignee_guerit_en_trois_nuits():
    perso = kaito(pv=1)
    perso.blessure_grave = True
    perso.blessure_grave_soignee = True
    for jour in (1, 2):
        assert not reposer(perso, Repos.LONG, Moment(jour, Periode.NUIT), Curseur.REALISTE).blessure_grave_guerie
    assert reposer(perso, Repos.LONG, Moment(3, Periode.NUIT), Curseur.REALISTE).blessure_grave_guerie


def test_repos_interrompu():
    perso = kaito(pv=1)
    assert reposer(perso, Repos.MOYEN, MATIN, interrompu=True).gain == 0
    assert perso.pv == 1
    with pytest.raises(SoinImpossible):
        reposer(perso, Repos.COURT, MATIN)  # le temps est passé


def test_un_mourant_ne_se_repose_pas():
    perso = kaito(pv=0)
    perso.etat = Etat.MOURANT
    with pytest.raises(SoinImpossible):
        reposer(perso, Repos.LONG, NUIT)


def test_le_temps_passe():
    assert MATIN.suivant() == APRES_MIDI
    assert APRES_MIDI.suivant() == NUIT
    assert NUIT.suivant() == Moment(2, Periode.MATIN)
