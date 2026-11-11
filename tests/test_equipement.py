import pytest

from aria.equipement import (
    ARMES_A_DISTANCE,
    CORPS_A_CORPS,
    DEFAUT_FRAGILE,
    DEFAUT_JET,
    DEFAUT_MALUS,
    DEFAUT_PROTECTION,
    Arme,
    Armure,
    Modification,
    Munitions,
    Portee,
    Propriete,
    Qualite,
    Recharge,
    bonus_force,
    formule_degats,
    verifier_arme,
    verifier_armure,
)

VISEUR = Modification("Viseur holographique", "précision", 5)
LASER = Modification("Pointeur laser", "précision", 5)
CALIBRE = Modification("Nouveau calibre", "puissance", 1)
SILENCIEUX = Modification("Silencieux", "propriété", propriete=Propriete.SILENCIEUSE)
PERFORANTES = Modification("Munitions perforantes", "propriété", propriete=Propriete.PERFORANTE)
CHARGEUR = Modification("Chargeur grande capacité", "munitions", munitions="chargeur doublé")
RECHARGEUR = Modification("Rechargeur rapide", "munitions", munitions="recharge rapide")
PLAQUES = Modification("Plaques de renfort", "puissance", 1)
DOUBLURE = Modification("Doublure souple", "confort", 5)
FURTIF = Modification("Revêtement furtif", "confort", 5, competence="Discrétion")

EPEE = Arme("Épée longue", CORPS_A_CORPS, "1d8", Portee.CONTACT)
ARC_ELFIQUE = Arme(
    "Arc long elfique", ARMES_A_DISTANCE, "1d8", Portee.LONGUE,
    munitions=Munitions(20, Recharge.MINEURE),
    proprietes=frozenset({Propriete.DEUX_MAINS, Propriete.SILENCIEUSE}),
    qualite=Qualite.PERSONNALISE, modifications=(Modification("Corde de maître", "précision", 5),
                                                  Modification("Flèches équilibrées", "précision", 5)),
)
PISTOLET_ARASAKA = Arme(
    "Pistolet lourd Arasaka", ARMES_A_DISTANCE, "1d10", Portee.COURTE,
    munitions=Munitions(8, Recharge.SIMPLE),
    proprietes=frozenset({Propriete.DISSIMULABLE}),
    qualite=Qualite.PERSONNALISE, modifications=(RECHARGEUR, CALIBRE), fabricant="Arasaka",
)
HARNOIS = Armure("Harnois de plates", 4, {"Discrétion": -20, "Athlétisme": -20, "Esquive": -20})


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
    assert str(formule_degats(PISTOLET_ARASAKA, force=90)) == "1d10+1"  # seulement le nouveau calibre


def test_les_modifications_font_les_bonus():
    assert ARC_ELFIQUE.bonus.jet == 10 and PISTOLET_ARASAKA.bonus.degats == 1
    arme = Arme("Pistolet", ARMES_A_DISTANCE, "1d8", Portee.COURTE, munitions=Munitions(10, Recharge.SIMPLE),
                qualite=Qualite.ORIGINE, modifications=(SILENCIEUX,))
    assert arme.a(Propriete.SILENCIEUSE) and not arme.a(Propriete.FRAGILE)


def test_les_modifications_de_munitions():
    arme = Arme("Fusil", ARMES_A_DISTANCE, "2d6", Portee.LONGUE, munitions=Munitions(6, Recharge.SIMPLE),
                proprietes=frozenset({Propriete.DEUX_MAINS}), qualite=Qualite.PERSONNALISE,
                modifications=(CHARGEUR, RECHARGEUR))
    assert arme.chargeur == Munitions(12, Recharge.MINEURE)
    assert arme.munitions == Munitions(6, Recharge.SIMPLE)  # le chargeur d'origine ne change pas


def test_coherence_corps_a_corps():
    arme = Arme("Épée à munitions", CORPS_A_CORPS, "1d8", Portee.LONGUE, munitions=Munitions(6, Recharge.SIMPLE))
    erreurs = verifier_arme(arme)
    assert any("portée « contact »" in e for e in erreurs)
    assert any("n'a pas de munitions" in e for e in erreurs)


def test_arme_a_distance_sans_munitions():
    sans = Arme("Fusil vide", ARMES_A_DISTANCE, "2d6+2", Portee.LONGUE, proprietes=frozenset({Propriete.DEUX_MAINS}))
    assert any("a des munitions" in e for e in verifier_arme(sans))
    javelot = Arme("Javelot", ARMES_A_DISTANCE, "1d8", Portee.COURTE, proprietes=frozenset({Propriete.LANCER}))
    assert verifier_arme(javelot) == []


def test_formule_et_competence_invalides():
    erreurs = verifier_arme(Arme("Bâton", "Magie", "4d", Portee.CONTACT))
    assert any("Compétence d'arme inconnue" in e for e in erreurs)
    assert any("Formule de dés invalide" in e for e in erreurs)


def _pistolet(qualite, *modifications, defaut=None):
    return Arme("Pistolet", ARMES_A_DISTANCE, "1d8", Portee.COURTE, munitions=Munitions(10, Recharge.SIMPLE),
                qualite=qualite, modifications=modifications, defaut=defaut)


@pytest.mark.parametrize(
    "arme, erreur",
    [
        (_pistolet(Qualite.ORIGINE), None),
        (_pistolet(Qualite.ORIGINE, VISEUR), None),
        (_pistolet(Qualite.ORIGINE, VISEUR, LASER), "1 emplacement"),
        (_pistolet(Qualite.PERSONNALISE, VISEUR, LASER), None),
        (_pistolet(Qualite.PERSONNALISE, VISEUR, VISEUR), "une fois par objet"),
        (_pistolet(Qualite.UNIQUE, VISEUR, LASER, CALIBRE), None),
        (_pistolet(Qualite.UNIQUE, SILENCIEUX, PERFORANTES), "une seule propriété"),
        (_pistolet(Qualite.USE, defaut=DEFAUT_JET), None),
        (_pistolet(Qualite.USE), "défaut"),
        (_pistolet(Qualite.USE, VISEUR, defaut=DEFAUT_JET), "0 emplacement"),
        (_pistolet(Qualite.ORIGINE, defaut=DEFAUT_JET), "Seul un objet usé"),
        (_pistolet(Qualite.ORIGINE, DOUBLURE), "ne va pas"),
    ],
)
def test_qualite_et_emplacements(arme, erreur):
    erreurs = verifier_arme(arme)
    assert erreurs == [] if erreur is None else any(erreur in e for e in erreurs), erreurs


def test_le_defaut_d_une_arme_usee():
    assert _pistolet(Qualite.USE, defaut=DEFAUT_JET).bonus.jet == -5
    assert _pistolet(Qualite.USE, defaut=DEFAUT_FRAGILE).a(Propriete.FRAGILE)


def test_canon_raccourci_pas_sur_une_arme_a_deux_mains():
    raccourci = Modification("Canon raccourci", "propriété", propriete=Propriete.DISSIMULABLE)
    fusil = Arme("Fusil", ARMES_A_DISTANCE, "2d6", Portee.LONGUE, munitions=Munitions(6, Recharge.SIMPLE),
                 proprietes=frozenset({Propriete.DEUX_MAINS}), modifications=(raccourci,))
    assert any("deux mains" in e for e in verifier_arme(fusil))


def test_legendaire_jamais_generee():
    arme = Arme("Épée du destin", CORPS_A_CORPS, "4d20", Portee.CONTACT, qualite=Qualite.LEGENDAIRE)
    assert verifier_arme(arme, generee=False) == []
    assert any("légendaire" in e for e in verifier_arme(arme, generee=True))


def test_armure_et_ses_malus():
    assert HARNOIS.protection_totale == 4
    assert HARNOIS.malus_pour("Discrétion") == -20
    assert HARNOIS.malus_pour("Perception") == 0


def test_modifications_d_armure():
    gilet = Armure("Gilet balistique", 3, {"Discrétion": -10}, qualite=Qualite.PERSONNALISE,
                   modifications=(PLAQUES, DOUBLURE))
    assert verifier_armure(gilet) == []
    assert gilet.protection_totale == 4
    assert gilet.malus_pour("Discrétion") == -5
    confortable = Armure("Gilet", 3, {"Discrétion": -10}, qualite=Qualite.PERSONNALISE, modifications=(DOUBLURE, FURTIF))
    assert confortable.malus_pour("Discrétion") == 0  # le malus ne devient jamais un bonus
    tactique = Armure("Armure tactique", 4, {"Discrétion": -20, "Athlétisme": -10}, modifications=(FURTIF,))
    assert tactique.malus_pour("Discrétion") == -15 and tactique.malus_pour("Athlétisme") == -10


def test_le_defaut_d_une_armure_usee():
    veste = Armure("Veste", 1, qualite=Qualite.USE, defaut=DEFAUT_PROTECTION)
    assert veste.protection_totale == 1  # jamais en dessous de 1
    gilet = Armure("Gilet", 3, {"Discrétion": -10}, qualite=Qualite.USE, defaut=DEFAUT_MALUS)
    assert gilet.malus_pour("Discrétion") == -20


def test_armure_invalide():
    armure = Armure("Armure absurde", -1, {"Discrétion": 20}, qualite=Qualite.ORIGINE, modifications=(PLAQUES, PLAQUES))
    erreurs = verifier_armure(armure)
    assert any("protection ne peut pas être négative" in e for e in erreurs)
    assert any("malus d'armure est négatif" in e for e in erreurs)
    assert any("1 emplacement" in e for e in erreurs)


@pytest.mark.parametrize(
    "degats, proprietes, erreur",
    [
        ("1d4", (), None),
        ("1d10", (), None),
        ("1d12", (Propriete.DEUX_MAINS,), None),
        ("2d6+2", (Propriete.DEUX_MAINS,), None),
        ("1d12", (), "deux mains"),
        ("1d3", (), "de 1d4 à 2d6+2"),
        ("3d6", (Propriete.DEUX_MAINS,), "de 1d4 à 2d6+2"),  # moyenne 10,5
        ("2d8", (Propriete.DEUX_MAINS,), "de 1d4 à 2d6+2"),  # moyenne 9, mais 16 au plus
    ],
)
def test_bornes_des_degats(degats, proprietes, erreur):
    arme = Arme("Arme test", CORPS_A_CORPS, degats, Portee.CONTACT, proprietes=frozenset(proprietes))
    erreurs = verifier_arme(arme)
    assert (erreurs == []) if erreur is None else any(erreur in e for e in erreurs)


def test_bornes_de_la_protection():
    assert verifier_armure(Armure("Veste", 1)) == []
    assert any("au moins un malus" in e for e in verifier_armure(Armure("Gilet sans gêne", 3)))
    assert any("de 1 à 4" in e for e in verifier_armure(Armure("Exosquelette", 5, {"Esquive": -20})))
    assert any("de 1 à 4" in e for e in verifier_armure(Armure("Rien du tout", 0)))
    # Le légendaire s'écrit à la main : il échappe aux bornes
    assert verifier_armure(Armure("Égide divine", 8, qualite=Qualite.LEGENDAIRE)) == []
