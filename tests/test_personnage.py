import pytest

from aria.personnage import (
    COMPETENCES_SOCLE,
    MAGIE,
    SOCLE,
    Caracteristique,
    CreationInvalide,
    DefCompetence,
    creer_personnage,
)
from aria.reglages import Curseur

C = Caracteristique


def netrunner(**changements):
    """L'exemple de REGLES.md 5, en noms de socle (Piratage = Technologie, etc.)."""
    parametres = dict(
        nom="Kaito",
        caracteristiques={C.FORCE: 35, C.CONSTITUTION: 45, C.DEXTERITE: 60, C.INTELLIGENCE: 75, C.VOLONTE: 50, C.PRESENCE: 35},
        parcours="Netrunner",
        competences_parcours=[
            "Technologie", "Investigation", "Sécurité", "Perception",
            "Discrétion", "Artisanat", "Tromperie", "Sciences",
        ],
        points_parcours={
            "Technologie": 70, "Investigation": 45, "Sécurité": 50, "Perception": 25,
            "Discrétion": 30, "Artisanat": 40, "Tromperie": 25, "Sciences": 15,
        },
        points_personnels={"Armes à distance": 30, "Esquive": 20, "Pilotage": 20, "Perspicacité": 30},
        motivation="Effacer sa dette envers une corpo",
        lien="Sa petite sœur, sa seule famille",
        defaut="Fait trop confiance aux machines",
        magie_active=False,
    )
    parametres.update(changements)
    return parametres


def erreurs_de(**changements) -> list[str]:
    with pytest.raises(CreationInvalide) as exc:
        creer_personnage(**netrunner(**changements))
    return exc.value.erreurs


def test_socle_de_24_competences():
    assert len(SOCLE) == 24
    assert COMPETENCES_SOCLE["Survie"].base == 10
    assert COMPETENCES_SOCLE["Esquive"].base is None


def test_exemple_du_netrunner():
    perso = creer_personnage(**netrunner())
    # Parcours (REGLES.md 5)
    assert perso.competence("Technologie") == 75  # Piratage
    assert perso.competence("Investigation") == 55  # Data-mining
    assert perso.competence("Sécurité") == 55  # Contre-mesures
    assert perso.competence("Perception") == 50  # Vigilance
    assert perso.competence("Discrétion") == 50  # Infiltration
    assert perso.competence("Artisanat") == 45  # Bricolage tech
    assert perso.competence("Tromperie") == 30  # Arnaque
    assert perso.competence("Sciences") == 20
    # Points personnels
    assert perso.competence("Armes à distance") == 50
    assert perso.competence("Esquive") == 50  # base Dextérité / 2 = 30, + 20
    assert perso.competence("Pilotage") == 40  # Conduite
    assert perso.competence("Perspicacité") == 40  # Empathie
    # Les autres compétences restent à leur base
    assert perso.competence("Corps à corps") == 25
    # Valeurs dérivées
    assert perso.pv == perso.pv_max == 8
    assert perso.sm == perso.sm_max == 50
    assert perso.pm == perso.pm_max == 0  # pas de magie en Cyberpunk


def test_pas_de_magie_si_l_univers_la_desactive():
    perso = creer_personnage(**netrunner())
    assert MAGIE not in perso.competences
    with pytest.raises(KeyError):
        perso.competence(MAGIE)


def test_points_de_magie_si_l_univers_l_active():
    perso = creer_personnage(**netrunner(magie_active=True))
    assert perso.competence(MAGIE) == 0
    assert perso.pm_max == 10  # Volonté 50 / 5


def test_bonus_de_pv_du_curseur():
    assert [c.bonus_pv for c in Curseur] == [10, 5, 0]
    perso = creer_personnage(**netrunner(bonus_pv=Curseur.HEROIQUE.bonus_pv))
    assert (perso.pv_max, perso.pv) == (18, 18)
    perso.blessure_grave = True
    assert perso.pv_max == 9


def test_pv_arrondis_a_l_inferieur():
    caracs = {C.FORCE: 37, C.CONSTITUTION: 44, C.DEXTERITE: 59, C.INTELLIGENCE: 75, C.VOLONTE: 50, C.PRESENCE: 35}
    assert creer_personnage(**netrunner(caracteristiques=caracs)).pv_max == 8  # 81 / 10


def test_caracteristiques_hors_bornes_et_total_faux():
    caracs = {C.FORCE: 85, C.CONSTITUTION: 15, C.DEXTERITE: 60, C.INTELLIGENCE: 75, C.VOLONTE: 50, C.PRESENCE: 36}
    erreurs = erreurs_de(caracteristiques=caracs)
    assert any("Force à 85" in e for e in erreurs)
    assert any("Constitution à 15" in e for e in erreurs)
    assert any("totalisent 321" in e for e in erreurs)


def test_caracteristique_manquante():
    caracs = {C.FORCE: 50, C.CONSTITUTION: 50, C.DEXTERITE: 50, C.INTELLIGENCE: 50, C.VOLONTE: 100}
    assert any("manquantes : Présence" in e for e in erreurs_de(caracteristiques=caracs))


def test_parcours_de_huit_competences_distinctes():
    erreurs = erreurs_de(competences_parcours=["Technologie"] * 8)
    assert any("en double" in e for e in erreurs)
    erreurs = erreurs_de(competences_parcours=["Technologie", "Investigation"])
    assert any("8 compétences, pas 2" in e for e in erreurs)


def test_competence_inconnue_ou_absente_de_l_univers():
    parcours = ["Piratage", "Investigation", "Sécurité", "Perception", "Discrétion", "Artisanat", "Tromperie", MAGIE]
    erreurs = erreurs_de(competences_parcours=parcours)
    assert any("« Piratage »" in e for e in erreurs)  # nom d'univers, pas de socle
    assert any(f"« {MAGIE} »" in e for e in erreurs)  # magie désactivée


def test_total_des_points_de_parcours():
    points = dict(netrunner()["points_parcours"], Sciences=16)
    assert any("totalisent 301 au lieu de 300" in e for e in erreurs_de(points_parcours=points))


def test_points_de_parcours_hors_du_parcours():
    points = dict(netrunner()["points_parcours"], Sciences=5, Médecine=10)
    assert any("« Médecine » n'est pas une compétence du parcours" in e for e in erreurs_de(points_parcours=points))


def test_total_des_points_personnels():
    assert any("totalisent 90 au lieu de 100" in e for e in erreurs_de(points_personnels={"Esquive": 90}) if "personnels" in e)


def test_points_negatifs():
    points = {"Esquive": 120, "Pilotage": -20}
    assert any("négatifs" in e for e in erreurs_de(points_personnels=points))


def test_plafond_de_creation_a_75():
    # Technologie : 5 + 70 de parcours + 1 personnel = 76
    points = {"Technologie": 1, "Armes à distance": 29, "Esquive": 20, "Pilotage": 20, "Perspicacité": 30}
    assert any("« Technologie » atteint 76" in e for e in erreurs_de(points_personnels=points))


def test_plafond_de_magie_a_50():
    points = {MAGIE: 51, "Esquive": 49}
    erreurs = erreurs_de(magie_active=True, points_personnels=points)
    assert any(f"« {MAGIE} » atteint 51" in e and "(50)" in e for e in erreurs)


def test_champs_de_roleplay_obligatoires():
    erreurs = erreurs_de(motivation="  ", lien="")
    assert any("motivation" in e for e in erreurs)
    assert any("lien" in e for e in erreurs)


def test_toutes_les_erreurs_d_un_coup():
    erreurs = erreurs_de(nom="", competences_parcours=["Technologie"], points_personnels={})
    assert len(erreurs) >= 3


def test_competence_thematique_et_sante_mentale_plafonnee_par_le_mythe():
    mythe = DefCompetence("Mythe", "Thématique", 0)
    parcours = ["Investigation", "Érudition", "Occultisme", "Perception", "Perspicacité", "Médecine", "Sciences", "Mythe"]
    points = {"Investigation": 50, "Érudition": 50, "Occultisme": 50, "Perception": 25, "Perspicacité": 40,
              "Médecine": 30, "Sciences": 25, "Mythe": 30}
    caracs = {C.FORCE: 40, C.CONSTITUTION: 45, C.DEXTERITE: 45, C.INTELLIGENCE: 75, C.VOLONTE: 75, C.PRESENCE: 20}
    perso = creer_personnage(**netrunner(
        parcours="Professeur", competences_parcours=parcours, points_parcours=points,
        points_personnels={"Esquive": 30, "Corps à corps": 20, "Persuasion": 30, "Pilotage": 20},
        caracteristiques=caracs, competences_thematiques=(mythe,), magie_active=True,
    ))
    assert perso.competence("Mythe") == 30
    assert perso.sm_max == 69  # min(Volonté 75, 99 − 30)
    assert perso.sm == 69
