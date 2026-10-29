import pytest

from aria.combat import FichePnj
from aria.des import DesTruques
from aria.personnage import creer_personnage
from aria.reglages import Curseur, Jalon
from aria.sante_mentale import (
    Choc,
    Crise,
    Gravite,
    ReglagesMentaux,
    Trouble,
    TypeTrouble,
    discussion,
    gravite_finale,
    jalon_atteint,
    sauver_de_la_folie,
    subir_choc,
    therapie,
)
from aria.soins import SoinImpossible
from aria.temps import Moment, Periode
from tests.test_personnage import netrunner

JOUR_1 = Moment(1, Periode.MATIN)
NUIT_1 = Moment(1, Periode.NUIT)


def kaito(sm=None):
    """Kaito : Volonté 50, donc 50 en SM ; Perspicacité 40."""
    perso = creer_personnage(**netrunner())
    if sm is not None:
        perso.sm = sm
    return perso


# --- Gravité finale ---------------------------------------------------------------------------

def test_gravite_de_base():
    assert gravite_finale(kaito(), Choc.CADAVRE_INCONNU, ReglagesMentaux()) is Gravite.LEGER
    assert gravite_finale(kaito(), Choc.MASSACRE, ReglagesMentaux()) is Gravite.GRAVE


def test_le_lien_amplifie():
    assert gravite_finale(kaito(), Choc.MORT_D_UN_ALLIE, ReglagesMentaux(), concerne_lien=True) is Gravite.GRAVE
    assert gravite_finale(kaito(), Choc.DOUBLE, ReglagesMentaux(), concerne_lien=True) is Gravite.ABSOLUE


def test_accoutumance_apres_trois_chocs():
    perso = kaito()
    perso.chocs_vecus[Choc.CHARNIER.name] = 3
    assert gravite_finale(perso, Choc.CHARNIER, ReglagesMentaux()) is Gravite.LEGER
    perso.chocs_vecus[Choc.CADAVRE_INCONNU.name] = 3
    assert gravite_finale(perso, Choc.CADAVRE_INCONNU, ReglagesMentaux()) is None


def test_normalite_de_l_univers():
    reglages = ReglagesMentaux(chocs_banals=frozenset({Choc.SURNATUREL_INDENIABLE}),
                               chocs_normaux=frozenset({Choc.MASSACRE}))
    assert gravite_finale(kaito(), Choc.SURNATUREL_INDENIABLE, reglages) is Gravite.LEGER
    assert gravite_finale(kaito(), Choc.MASSACRE, reglages) is None


def test_monde_impitoyable():
    reglages = ReglagesMentaux(monde_impitoyable=True)
    assert gravite_finale(kaito(), Choc.CADAVRE_INCONNU, reglages) is None
    assert gravite_finale(kaito(), Choc.CHARNIER, reglages) is Gravite.SERIEUX


def test_heroique_seulement_grave_et_absolue():
    reglages = ReglagesMentaux(curseur=Curseur.HEROIQUE)
    assert gravite_finale(kaito(), Choc.TORTURE, reglages) is None
    assert gravite_finale(kaito(), Choc.MASSACRE, reglages) is Gravite.GRAVE


def test_chocs_de_combat_seulement_en_realiste():
    assert gravite_finale(kaito(), Choc.MORT_D_UN_ALLIE, ReglagesMentaux(), en_combat=True) is None
    realiste = ReglagesMentaux(curseur=Curseur.REALISTE)
    assert gravite_finale(kaito(), Choc.MORT_D_UN_ALLIE, realiste, en_combat=True) is Gravite.SERIEUX
    assert gravite_finale(kaito(), Choc.MORT_D_UN_ALLIE, ReglagesMentaux()) is Gravite.SERIEUX  # après le combat


def test_premier_meurtre_une_seule_fois():
    perso = kaito()
    subir_choc(DesTruques(30, 1), perso, Choc.PREMIER_MEURTRE, JOUR_1)
    assert gravite_finale(perso, Choc.PREMIER_MEURTRE, ReglagesMentaux()) is None


# --- Subir un choc ----------------------------------------------------------------------------

def test_choc_leger_reussi_ne_coute_rien():
    perso = kaito()
    rapport = subir_choc(DesTruques(30), perso, Choc.CADAVRE_INCONNU, JOUR_1)
    assert rapport.test.reussi
    assert rapport.perte == 0
    assert perso.sm == 50


def test_choc_sans_test_compte_quand_meme_pour_l_accoutumance():
    perso = kaito()
    rapport = subir_choc(DesTruques(), perso, Choc.CADAVRE_INCONNU, JOUR_1, ReglagesMentaux(monde_impitoyable=True))
    assert rapport.gravite is None and rapport.test is None
    assert perso.chocs_vecus[Choc.CADAVRE_INCONNU.name] == 1


def test_perte_de_5_declenche_une_crise():
    perso = kaito()
    # Test raté (70), 1d6 = 6, crise n° 2 (paralysie) pendant 4 rounds
    rapport = subir_choc(DesTruques(70, 6, 2, 4), perso, Choc.TORTURE, JOUR_1)
    assert (rapport.perte, perso.sm) == (6, 44)
    assert (rapport.crise, rapport.duree_crise) == (Crise.PARALYSIE, 4)
    assert rapport.trouble is None  # 6 < 50 / 5


def test_un_cinquieme_de_la_sm_en_un_jour_donne_un_trouble():
    perso = kaito()
    # Test raté, 1d10 = 10 : crise (1 = panique, 3 rounds), puis trouble n° 3 (paranoïa)
    rapport = subir_choc(DesTruques(70, 10, 1, 3, 3), perso, Choc.MASSACRE, JOUR_1)
    assert rapport.crise is Crise.PANIQUE
    # Le seuil de guérison est la SM du début de la journée, avant les pertes
    assert rapport.trouble == Trouble(TypeTrouble.PARANOIA, 50, Choc.MASSACRE.description)
    assert perso.troubles == [rapport.trouble]


def test_le_trouble_guerit_quand_la_sm_retrouve_son_niveau_du_matin():
    perso = kaito()
    subir_choc(DesTruques(70, 10, 1, 3, 3), perso, Choc.MASSACRE, JOUR_1)  # 50 → 40, trouble
    assert jalon_atteint(DesTruques(6), perso, Jalon.OBJECTIF).troubles_gueris == []  # 46 : pas encore
    assert perso.troubles
    rapport = jalon_atteint(DesTruques(4), perso, Jalon.OBJECTIF)  # 50 : niveau du matin retrouvé
    assert [t.type for t in rapport.troubles_gueris] == [TypeTrouble.PARANOIA]
    assert perso.troubles == []


def test_seuil_plafonne_par_la_sm_max():
    perso = kaito(sm=40)
    perso.troubles = [Trouble(TypeTrouble.PHOBIE, 50, "test")]
    perso.competences["Mythe"] = 55  # SM max : min(50, 99 − 55) = 44
    assert jalon_atteint(DesTruques(4), perso, Jalon.OBJECTIF).troubles_gueris


def test_les_pertes_s_additionnent_sur_la_journee():
    perso = kaito()
    subir_choc(DesTruques(70, 4), perso, Choc.TORTURE, JOUR_1)  # −4
    rapport = subir_choc(DesTruques(70, 4, 1), perso, Choc.CHARNIER, Moment(1, Periode.APRES_MIDI))  # −4 : 8 < 10
    assert rapport.trouble is None
    rapport = subir_choc(DesTruques(70, 2, 4), perso, Choc.CHARNIER, Moment(1, Periode.NUIT))  # 10 ≥ 50 / 5
    assert rapport.trouble.type is TypeTrouble.TREMBLEMENTS


def test_un_seul_trouble_par_jour_puis_remise_a_zero():
    perso = kaito()
    subir_choc(DesTruques(70, 10, 1, 1, 1), perso, Choc.MASSACRE, JOUR_1)
    rapport = subir_choc(DesTruques(70, 4), perso, Choc.TORTURE, JOUR_1)
    assert rapport.trouble is None
    rapport = subir_choc(DesTruques(70, 10, 1, 1, 2), perso, Choc.MASSACRE, Moment(2, Periode.MATIN))
    assert rapport.trouble is not None  # nouveau jour : 10 ≥ 36 / 5


def test_folie_puis_point_de_destin():
    perso = kaito(sm=3)
    perso.points_destin = 1
    rapport = subir_choc(DesTruques(70, 15), perso, Choc.ENTITE_COSMIQUE, JOUR_1)
    assert rapport.folie and perso.folie
    assert perso.sm == 0
    sauver_de_la_folie(perso)
    assert (perso.folie, perso.sm, perso.points_destin) == (False, 1, 0)
    perso.folie = True
    with pytest.raises(ValueError):
        sauver_de_la_folie(perso)


# --- Récupération -----------------------------------------------------------------------------

def test_therapie_la_nuit_et_guerison_du_trouble():
    patient = kaito(sm=40)
    patient.troubles = [Trouble(TypeTrouble.PHOBIE, 40, "test")]
    # Perspicacité 40 : 05 = critique, 2d6 = 3 + 3
    rapport = therapie(DesTruques(5, 3, 3), kaito(), patient, NUIT_1)
    assert rapport.gain == 6
    assert patient.sm == 46
    assert [t.type for t in rapport.troubles_gueris] == [TypeTrouble.PHOBIE]
    assert patient.troubles == []


def test_therapie_par_un_pnj_et_malus_du_soignant_blesse():
    psy = FichePnj("Psy", combat=20, pv_max_base=10, competences={"Perspicacité": 60})
    assert therapie(DesTruques(80), psy, kaito(sm=30), NUIT_1).test.valeur == 60
    blesse = kaito()
    blesse.blessure_grave = True
    assert therapie(DesTruques(80), blesse, kaito(sm=30), NUIT_1).test.valeur == 20  # 40 − 20


def test_therapie_une_fois_par_nuit():
    patient = kaito(sm=30)
    with pytest.raises(SoinImpossible):
        therapie(DesTruques(5), kaito(), patient, JOUR_1)
    therapie(DesTruques(80), kaito(), patient, NUIT_1)
    with pytest.raises(SoinImpossible):
        therapie(DesTruques(5), kaito(), patient, NUIT_1)
    with pytest.raises(SoinImpossible):
        therapie(DesTruques(5), kaito(), patient, Moment(2, Periode.NUIT), competence="Persuasion")


def test_discussion_une_fois_par_jour():
    perso = kaito(sm=30)
    assert discussion(DesTruques(2), perso, JOUR_1).gain == 2
    with pytest.raises(SoinImpossible):
        discussion(DesTruques(2), perso, Moment(1, Periode.NUIT))
    discussion(DesTruques(2), perso, Moment(2, Periode.MATIN))
    assert perso.sm == 34


def test_jalons():
    perso = kaito(sm=30)
    assert jalon_atteint(DesTruques(4), perso, Jalon.OBJECTIF).gain == 4
    assert jalon_atteint(DesTruques(9), perso, Jalon.ARC).gain == 9
    assert jalon_atteint(DesTruques(), perso, Jalon.SESSION).gain == 0


def test_plafond_de_la_sm():
    perso = kaito(sm=49)
    jalon_atteint(DesTruques(10), perso, Jalon.ARC)
    assert perso.sm == 50  # jamais au-dessus de la Volonté


def test_pas_de_recuperation_pour_un_fou():
    perso = kaito(sm=0)
    perso.folie = True
    with pytest.raises(SoinImpossible):
        discussion(DesTruques(2), perso, JOUR_1)
