import pytest

from aria.equipement import (
    ARMES_A_DISTANCE,
    CORPS_A_CORPS,
    Arme,
    Armure,
    BonusArme,
    BonusArmure,
    Munitions,
    Portee,
    Propriete,
    Rarete,
    Recharge,
    bonus_force,
    formule_degats,
    verifier_arme,
    verifier_armure,
)

EPEE = Arme("Épée longue", CORPS_A_CORPS, "1d8", Portee.CONTACT)
ARC_ELFIQUE = Arme(
    "Arc long elfique", ARMES_A_DISTANCE, "1d8", Portee.LONGUE,
    munitions=Munitions(20, Recharge.MINEURE),
    proprietes=frozenset({Propriete.DEUX_MAINS, Propriete.SILENCIEUSE}),
    rarete=Rarete.RARE, bonus=BonusArme(jet=10),
)
PISTOLET_ARASAKA = Arme(
    "Pistolet lourd Arasaka", ARMES_A_DISTANCE, "1d10", Portee.COURTE,
    munitions=Munitions(8, Recharge.MINEURE),
    proprietes=frozenset({Propriete.DISSIMULABLE}),
    rarete=Rarete.PEU_COMMUNE, bonus=BonusArme(degats=1),
)
HARNOIS = Armure("Harnois de plates", 5, {"Discrétion": -20, "Athlétisme": -20, "Esquive": -20})


def test_exemples_de_regles_valides():
    assert verifier_arme(EPEE) == []
    assert verifier_arme(ARC_ELFIQUE) == []
    assert verifier_arme(PISTOLET_ARASAKA) == []
    assert verifier_armure(HARNOIS) == []


@pytest.mark.parametrize(
    "force, attendu",
    [(20, "-1"), (40, "-1"), (41, None), (60, None), (61, "1d4"), (75, "1d4"), (76, "1d6"), (90, "1d6")],
)
def test_bonus_de_force(force, attendu):
    assert bonus_force(force) == attendu


def test_formule_de_degats_au_corps_a_corps():
    assert str(formule_degats(EPEE, force=70)) == "1d8+1d4"
    assert str(formule_degats(EPEE, force=30)) == "1d8-1"
    assert str(formule_degats(EPEE, force=50)) == "1d8"
    assert str(formule_degats(EPEE)) == "1d8"


def test_pas_de_bonus_de_force_a_distance():
    assert str(formule_degats(PISTOLET_ARASAKA, force=90)) == "1d10+1"  # seulement le bonus de rareté


def test_proprietes_de_bonus_comptent_comme_proprietes():
    arme = Arme("Dague runique", CORPS_A_CORPS, "1d4", Portee.CONTACT,
                rarete=Rarete.RARE, bonus=BonusArme(proprietes=frozenset({Propriete.PERFORANTE})))
    assert verifier_arme(arme) == []
    assert arme.a(Propriete.PERFORANTE)
    assert not arme.a(Propriete.FRAGILE)


def test_coherence_corps_a_corps():
    arme = Arme("Épée à munitions", CORPS_A_CORPS, "1d8", Portee.LONGUE, munitions=Munitions(6, Recharge.SIMPLE))
    erreurs = verifier_arme(arme)
    assert any("portée « contact »" in e for e in erreurs)
    assert any("n'a pas de munitions" in e for e in erreurs)


def test_arme_a_distance_sans_munitions():
    sans = Arme("Fusil vide", ARMES_A_DISTANCE, "2d6+2", Portee.LONGUE)
    assert any("a des munitions" in e for e in verifier_arme(sans))
    javelot = Arme("Javelot", ARMES_A_DISTANCE, "1d8", Portee.COURTE, proprietes=frozenset({Propriete.LANCER}))
    assert verifier_arme(javelot) == []


def test_formule_et_competence_invalides():
    erreurs = verifier_arme(Arme("Bâton", "Magie", "4d", Portee.CONTACT))
    assert any("Compétence d'arme inconnue" in e for e in erreurs)
    assert any("Formule de dés invalide" in e for e in erreurs)


@pytest.mark.parametrize(
    "rarete, bonus, valide",
    [
        (Rarete.COMMUNE, BonusArme(), True),
        (Rarete.COMMUNE, BonusArme(jet=5), False),
        (Rarete.PEU_COMMUNE, BonusArme(jet=5), True),
        (Rarete.PEU_COMMUNE, BonusArme(degats=1), True),
        (Rarete.PEU_COMMUNE, BonusArme(jet=10), False),
        (Rarete.PEU_COMMUNE, BonusArme(jet=5, degats=1), False),  # « ou », pas « et »
        (Rarete.PEU_COMMUNE, BonusArme(proprietes=frozenset({Propriete.SILENCIEUSE})), False),
        (Rarete.RARE, BonusArme(jet=10), True),
        (Rarete.RARE, BonusArme(degats=2), True),
        (Rarete.RARE, BonusArme(degats=3), False),
        (Rarete.RARE, BonusArme(jet=10, degats=2), False),
        (Rarete.EXCEPTIONNELLE, BonusArme(jet=10, degats=2), True),
        (Rarete.EXCEPTIONNELLE, BonusArme(jet=10, proprietes=frozenset({Propriete.PERFORANTE})), True),
        (Rarete.EXCEPTIONNELLE, BonusArme(jet=20), False),  # deux bonus de « Rare », pas un bonus doublé
        (Rarete.EXCEPTIONNELLE, BonusArme(jet=10, degats=2, proprietes=frozenset({Propriete.PERFORANTE})), False),
        (Rarete.LEGENDAIRE, BonusArme(jet=40, degats=10), True),  # écrite à la main : pas de plafond
    ],
)
def test_echelle_de_rarete_des_armes(rarete, bonus, valide):
    arme = Arme("Arme test", CORPS_A_CORPS, "1d8", Portee.CONTACT, rarete=rarete, bonus=bonus)
    assert (verifier_arme(arme) == []) == valide


def test_legendaire_jamais_generee():
    arme = Arme("Épée du destin", CORPS_A_CORPS, "4d20", Portee.CONTACT, rarete=Rarete.LEGENDAIRE)
    assert verifier_arme(arme, generee=False) == []
    assert any("légendaire" in e for e in verifier_arme(arme, generee=True))


def test_armure_et_ses_malus():
    assert HARNOIS.protection_totale == 5
    assert HARNOIS.malus_pour("Discrétion") == -20
    assert HARNOIS.malus_pour("Perception") == 0


def test_bonus_d_armure():
    maille_naine = Armure(
        "Cotte de mailles naine", 3, {"Discrétion": -10},
        rarete=Rarete.RARE, bonus=BonusArmure(malus_en_moins=10),
    )
    assert verifier_armure(maille_naine) == []
    assert maille_naine.malus_pour("Discrétion") == 0  # le malus ne devient jamais un bonus
    renforcee = Armure("Gilet renforcé", 3, rarete=Rarete.PEU_COMMUNE, bonus=BonusArmure(protection=1))
    assert verifier_armure(renforcee) == []
    assert renforcee.protection_totale == 4


def test_armure_invalide():
    armure = Armure("Armure absurde", -1, {"Discrétion": 20}, rarete=Rarete.PEU_COMMUNE, bonus=BonusArmure(protection=2))
    erreurs = verifier_armure(armure)
    assert any("protection ne peut pas être négative" in e for e in erreurs)
    assert any("malus d'armure est négatif" in e for e in erreurs)
    assert any("+1 de protection" in e for e in erreurs)
