"""L'économie, lot 1 (REGLES.md 13.1 à 13.4) : les paliers, les prix, le niveau de vie, l'argent de départ."""

import random
from dataclasses import replace

import pytest

from aria import economie, outils
from aria.bibliotheque import charger
from aria.creation import Brouillon, proposer_chiffres
from aria.des import Des, DesTruques
from aria.economie import (
    COURANT,
    MILITAIRE,
    PALIERS,
    RESTREINT,
    NiveauDeVie,
    decaler,
    disponibilite,
    palier,
    passer_les_echeances,
    prix,
)
from aria.equipement import Qualite
from aria.outils import ErreurOutil, Session
from aria.personnages import KAITO, brouillon_dans
from aria.sauvegarde import personnage_depuis_dict, personnage_vers_dict
from aria.temps import Moment, Periode
from aria.univers import charger_univers, univers_depuis_dict, univers_vers_dict
from tests.test_univers import CYBERPUNK


@pytest.fixture(scope="module")
def neo_tokyo():
    return charger_univers(CYBERPUNK)


def personnage(univers, parcours):
    b = proposer_chiffres(Brouillon(univers), random.Random(1), parcours)
    b.fixer("roleplay", {"nom": "Yuki", "motivation": "m", "lien": "l", "defaut": "d"})
    return b.finaliser()[0]


def session(univers, parcours="Solo", periode=Periode.APRES_MIDI):
    return Session(univers, personnage(univers, parcours), Des(2), Moment(1, periode))


# --- Les paliers ----------------------------------------------------------------------------------------

def test_les_paliers():
    assert PALIERS[:10] == (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)
    assert palier(1) == 10 and palier(400) == 500 and palier(300) == 200 and palier(1900) == 2000
    assert all(palier(p) == p for p in PALIERS)
    assert decaler(1000, -2) == 200 and decaler(1000, 1) == 2000 and decaler(10, -3) == 10


# --- Les prix et la disponibilité -----------------------------------------------------------------------

def test_tout_objet_a_un_prix_qui_est_un_palier(neo_tokyo):
    lignes = economie.catalogue(neo_tokyo)
    assert len(lignes) == len(neo_tokyo.armes) + len(neo_tokyo.armures) + len(neo_tokyo.implants) + len(neo_tokyo.vehicules)
    assert all(cout in PALIERS and dispo in economie.DISPONIBILITES for _, _, cout, dispo in lignes)
    for genre in ("Fantasy", "Militaire", "Science-fiction", "Post-apo"):  # les autres genres aussi
        b = charger()
        from aria.generateur import choix_par_defaut, generer
        monde = univers_depuis_dict(generer(b, choix_par_defaut(b, genre)))
        assert all(cout in PALIERS for _, _, cout, _ in economie.catalogue(monde)), genre


@pytest.mark.parametrize("nom, attendu, dispo", [
    ("Couteau", 50, COURANT), ("Katana", 200, COURANT), ("Pistolet léger", 500, COURANT),
    ("Pistolet silencieux", 500, RESTREINT), ("Pistolet lourd", 1000, COURANT), ("Fusil d'assaut", 2000, RESTREINT),
    ("Fusil de précision", 5000, RESTREINT), ("Grenade à fragmentation", 200, RESTREINT),
    ("Lance-roquettes", 20000, MILITAIRE),
    ("Fusil à rail", 5000, RESTREINT),  # prix et disponibilité imposés par la bibliothèque
])
def test_le_prix_des_armes(neo_tokyo, nom, attendu, dispo):
    arme = neo_tokyo.arme(nom)
    assert prix(arme, neo_tokyo) == attendu and disponibilite(arme, neo_tokyo) == dispo


def test_le_prix_du_reste(neo_tokyo):
    u = neo_tokyo
    assert prix(u.armure("Veste renforcée")) == 200 and disponibilite(u.armure("Veste renforcée")) == COURANT
    assert prix(u.armure("Gilet balistique")) == 2000 and disponibilite(u.armure("Gilet balistique")) == RESTREINT
    assert prix(u.implant("Neuroport")) == 2000 and disponibilite(u.implant("Neuroport")) == COURANT
    assert prix(u.implant("Sandevistan")) == 50000 and disponibilite(u.implant("Sandevistan")) == MILITAIRE
    assert prix(u.vehicule("Citadine"), u) == 20000 and prix(u.vehicule("Voiture de sport"), u) == 100000
    assert prix(u.vehicule("Moto sportive"), u) == 10000
    av = u.vehicule("AV de corpo")  # ses armes montées comptent, et le rendent introuvable en boutique
    assert prix(av, u) >= 200000 and disponibilite(av, u) == MILITAIRE


def test_la_qualite_et_la_marque_se_comptent_en_paliers(neo_tokyo):
    lourd = neo_tokyo.arme("Pistolet lourd")
    assert prix(replace(lourd, qualite=Qualite.USE)) == 500  # un palier en dessous
    assert prix(replace(lourd, qualite=Qualite.UNIQUE)) == 5000  # deux au-dessus
    assert disponibilite(replace(lourd, qualite=Qualite.UNIQUE)) == MILITAIRE  # jamais en boutique
    arasaka = neo_tokyo.arme("Pistolet lourd Arasaka")  # de marque, et une modification posée en plus de celle d'usine
    assert arasaka.fabricant and prix(arasaka, neo_tokyo) > prix(lourd, neo_tokyo)


def test_un_objet_renomme_par_le_cadre_garde_son_prix_impose(neo_tokyo):
    rail = replace(neo_tokyo.arme("Fusil à rail"), nom="Lance-éclair")
    monde = replace(neo_tokyo, origines={"Lance-éclair": "Fusil à rail"})
    assert prix(rail, monde) == 5000 and disponibilite(rail, monde) == RESTREINT
    assert prix(rail) == 2000 and disponibilite(rail) == COURANT  # sans son origine, le calcul seul


def test_les_exceptions_de_la_bibliotheque_sont_verifiees(monkeypatch):
    assert charger().verifier() == []
    monkeypatch.setattr(economie, "_exceptions", lambda: {"prix": {"Sabre laser": 300, "Katana": 250},
                                                          "disponibilites": {"Couteau": "interdit"}})
    erreurs = economie.verifier_exceptions({"Katana", "Couteau"})
    assert len(erreurs) == 4 and any("Sabre laser" in e and "n'existe pas" in e for e in erreurs)
    assert any("250" in e and "palier" in e for e in erreurs) and any("interdit" in e for e in erreurs)


# --- L'argent de départ ---------------------------------------------------------------------------------

@pytest.mark.parametrize("parcours, argent, niveau", [("Ganger", 500, "modeste"), ("Solo", 2000, "modeste"),
                                                      ("Fixer", 5000, "confortable")])
def test_l_argent_de_depart_suit_le_rang_du_metier(neo_tokyo, parcours, argent, niveau):
    p = personnage(neo_tokyo, parcours)
    assert (p.argent, p.niveau_de_vie, p.semaine_payee, p.echeance) == (argent, niveau, True, 8)
    assert personnage_depuis_dict(personnage_vers_dict(p)).argent == argent  # la sauvegarde le garde


def test_les_rangs_et_la_monnaie_suivent_l_univers(neo_tokyo):
    assert len(neo_tokyo.rangs) == 19 and neo_tokyo.rangs["Idol"] == "aisé" and neo_tokyo.monnaie == "crédits"
    assert neo_tokyo.niveaux_de_vie["modeste"].startswith("une capsule")
    relu = univers_depuis_dict(univers_vers_dict(neo_tokyo))
    assert relu.rangs == neo_tokyo.rangs and relu.monnaie == "crédits" and relu.niveaux_de_vie == neo_tokyo.niveaux_de_vie
    fantasy = charger().composer("Fantasy", True, "Valombre")
    assert fantasy["monnaie"] == "couronnes" and fantasy["rangs"] == {}  # pas encore de rangs : « établi » par défaut
    assert brouillon_dans(neo_tokyo, KAITO)[0].finaliser()[0].argent == 2000  # un Netrunner est établi


def test_un_parcours_renomme_ou_retire_garde_ses_rangs_en_ordre():
    from aria.generateur import _renommer_parcours, _retirer_parcours
    d = charger().composer("Cyberpunk", False, "Osaka")
    _renommer_parcours(d, {"Idol": "Étoile"})
    _retirer_parcours(d, ["Ganger"])
    assert d["rangs"]["Étoile"] == "aisé" and "Idol" not in d["rangs"] and "Ganger" not in d["rangs"]
    assert univers_depuis_dict(d).creer_personnage  # l'univers reste valide


# --- Le niveau de vie -----------------------------------------------------------------------------------

def test_le_cout_de_la_vie_tombe_tous_les_sept_jours(neo_tokyo):
    p = personnage(neo_tokyo, "Ganger")  # 500, modeste : de quoi payer une semaine, pas deux
    assert passer_les_echeances(p, 7) == []
    (premiere,) = passer_les_echeances(p, 8)
    assert premiere.payee and premiere.cout == 350 and p.argent == 150 and p.echeance == 15
    (deuxieme,) = passer_les_echeances(p, 15)
    assert not deuxieme.payee and p.argent == 150 and economie.a_la_rue(p) and p.niveau_de_vie == "modeste"
    p.argent = 1000
    assert economie.payer_la_semaine(p) and p.argent == 650 and not economie.a_la_rue(p)
    payee, impayee = passer_les_echeances(p, 29)  # deux échéances d'un coup : la seconde ne passe plus
    assert payee.payee and not impayee.payee and p.argent == 300 and p.echeance == 36


def test_changer_de_niveau_de_vie(neo_tokyo):
    p = personnage(neo_tokyo, "Fixer")
    economie.changer_niveau_de_vie(p, NiveauDeVie.MODESTE)
    assert economie.niveau_effectif(p) is NiveauDeVie.MODESTE and passer_les_echeances(p, 8)[0].cout == 350
    economie.changer_niveau_de_vie(p, NiveauDeVie.A_LA_RUE)
    assert economie.a_la_rue(p) and passer_les_echeances(p, 15)[0].cout == 0 and p.argent == 4650


def test_avancer_le_temps_debite_et_previent_le_mj(neo_tokyo):
    s = session(neo_tokyo, "Ganger")
    s.moment = Moment(7, Periode.NUIT)
    resultat = outils.avancer_temps(s)
    assert resultat["echeances"] == [{"jour": 8, "niveau_de_vie": "modeste", "cout": 350, "argent": 150}]
    s.moment = Moment(14, Periode.NUIT)
    impayee = outils.avancer_temps(s)["echeances"][0]
    assert impayee["impayee"] and "à la rue" in impayee["consequence"]
    etat = outils.etat(s)["joueur"]
    assert (etat["argent"], etat["monnaie"], etat["niveau_de_vie"], etat["prochaine_echeance"]) == (
        150, "crédits", "à la rue", "jour 22")
    assert "echeances" not in outils.avancer_temps(s)


def test_a_la_rue_le_repos_long_ne_vaut_qu_un_repos_moyen(neo_tokyo):
    loge, dehors = session(neo_tokyo, periode=Periode.NUIT), session(neo_tokyo, periode=Periode.NUIT)
    dehors.personnage.semaine_payee = False
    for s in (loge, dehors):
        s.personnage.pv = 1
    assert outils.repos(loge, "long")["pv"] == loge.personnage.pv_max
    assert outils.repos(dehors, "long")["pv"] == 1 + max(1, dehors.personnage.pv_max // 2)
    with pytest.raises(ErreurOutil, match="vit à la rue"):
        outils.recuperer_sante_mentale(dehors, "thérapie")


def test_un_niveau_confortable_aide_la_therapie(neo_tokyo):
    reussites = {}
    for niveau in (NiveauDeVie.MODESTE, NiveauDeVie.CONFORTABLE):
        s = session(neo_tokyo, periode=Periode.NUIT)
        s.des = DesTruques(55, 2)  # 55 au d100 : un échec à 50, une réussite à 60 ; puis le dé du gain
        s.personnage.competences["Perspicacité"] = 50
        s.personnage.sm -= 10
        s.personnage.niveau_de_vie = niveau.value
        reussites[niveau] = outils.recuperer_sante_mentale(s, "thérapie")["sm_gagnee"] > 0
    assert reussites == {NiveauDeVie.MODESTE: False, NiveauDeVie.CONFORTABLE: True}
