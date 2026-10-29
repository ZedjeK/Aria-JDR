import pytest

from aria.combat import Combat, Defense
from aria.des import DesTruques
from aria.personnage import Caracteristique, DefCompetence, creer_personnage
from aria.progression import (
    ProgressionImpossible,
    ameliorer_caracteristique,
    ameliorer_competence,
    apprendre_competence,
    cocher,
    fin_de_session,
    gagner_xp,
)
from aria.reglages import Jalon
from aria.resolution import Degre, Resultat
from aria.soins import soigner
from aria.temps import Moment, Periode
from tests.test_combat import ganger
from tests.test_combat import kaito as kaito_combattant
from tests.test_personnage import netrunner

REUSSITE = Resultat(30, 50, Degre.REUSSITE)
ECHEC = Resultat(80, 50, Degre.ECHEC)


def kaito(xp=0):
    """Kaito : Esquive 50, Technologie 75, Volonté 50, Constitution 45, 8 PV."""
    perso = creer_personnage(**netrunner())
    perso.xp = xp
    return perso


# --- À l'usage ----------------------------------------------------------------------------------

def test_seules_les_reussites_sont_cochees():
    perso = kaito()
    cocher(perso, "Esquive", REUSSITE)
    cocher(perso, "Perception", ECHEC)
    cocher(perso, "Inconnue", REUSSITE)
    assert perso.competences_cochees == {"Esquive"}


def test_fin_de_session():
    perso = kaito()
    perso.competences_cochees = {"Esquive", "Technologie"}
    # Esquive 50 : 80 > 50, donc +1d10 (7). Technologie 75 : 40 ≤ 75, pas de progrès.
    ameliorations = fin_de_session(DesTruques(80, 7, 40), perso)
    assert [(a.competence, a.gain, a.apres) for a in ameliorations] == [("Esquive", 7, 57), ("Technologie", 0, 75)]
    assert perso.competence("Esquive") == 57
    assert perso.competences_cochees == set()


def test_plafond_de_95_a_l_usage():
    perso = kaito()
    perso.competences["Technologie"] = 92
    perso.competences["Esquive"] = 95
    perso.competences_cochees = {"Technologie", "Esquive"}
    ameliorations = fin_de_session(DesTruques(99, 8), perso)  # Esquive, déjà à 95, n'est pas lancée
    assert [a.competence for a in ameliorations] == ["Technologie"]
    assert perso.competence("Technologie") == 95


# --- Avec l'XP ------------------------------------------------------------------------------------

def test_gains_d_xp_a_definir():
    perso = kaito()
    assert gagner_xp(perso, Jalon.ARC) == 0  # montants à définir (REGLES.md 10)


def test_ameliorer_une_competence():
    perso = kaito()
    with pytest.raises(ProgressionImpossible):
        ameliorer_competence(perso, "Esquive")  # pas d'XP
    perso.xp = 2
    ameliorer_competence(perso, "Esquive")
    assert (perso.competence("Esquive"), perso.xp) == (55, 1)
    perso.competences["Esquive"] = 93
    ameliorer_competence(perso, "Esquive")
    assert perso.competence("Esquive") == 95
    with pytest.raises(ProgressionImpossible):
        ameliorer_competence(perso, "Inconnue")


def test_apprendre_une_competence_thematique():
    perso = kaito(xp=3)
    cybernetique = DefCompetence("Cybernétique", "Thématique", 5)
    apprendre_competence(perso, cybernetique)
    assert (perso.competence("Cybernétique"), perso.xp) == (5, 0)
    perso.xp = 3
    with pytest.raises(ProgressionImpossible):
        apprendre_competence(perso, cybernetique)


def test_ameliorer_une_caracteristique_recalcule_les_maximums():
    perso = kaito(xp=15)
    perso.pv = 5
    ameliorer_caracteristique(perso, Caracteristique.VOLONTE)
    assert (perso.sm_max, perso.sm) == (55, 55)
    ameliorer_caracteristique(perso, Caracteristique.CONSTITUTION)  # 35 + 50 = 85 : toujours 8 PV
    assert (perso.pv_max, perso.pv) == (8, 5)
    ameliorer_caracteristique(perso, Caracteristique.CONSTITUTION)  # 35 + 55 = 90 : 9 PV
    assert (perso.pv_max, perso.pv) == (9, 6)
    assert perso.xp == 0


def test_plafond_de_90_pour_une_caracteristique():
    perso = kaito(xp=5)
    perso.caracteristiques[Caracteristique.INTELLIGENCE] = 90
    with pytest.raises(ProgressionImpossible):
        ameliorer_caracteristique(perso, Caracteristique.INTELLIGENCE)
    assert perso.xp == 5  # rien n'a été dépensé


# --- Le moteur coche tout seul --------------------------------------------------------------------

def test_le_combat_coche_les_competences_reussies():
    k, g = kaito_combattant(), ganger()
    c = Combat(DesTruques(30, 6, 10, 30, 40), [k, g])
    c.attaquer(k, g)  # tir réussi (30), 6 dégâts, le ganger réussit sa Constitution (10)
    c.attaquer(g, k, Defense.ESQUIVE)  # esquive réussie à égalité
    assert k.fiche.competences_cochees == {"Armes à distance", "Esquive"}


def test_le_soin_coche_la_medecine_du_soigneur():
    soigneur, patient = kaito(), kaito()
    patient.pv = 3
    soigner(DesTruques(3, 1), soigneur, patient, Moment(1, Periode.MATIN))  # Médecine 5 : 03 réussit
    assert soigneur.competences_cochees == {"Médecine"}
