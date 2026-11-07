"""Les armes de zone et l'IEM (REGLES.md 7.9 et 7.10)."""

import pytest

from aria.combat import ActionImpossible, Combattant, IssueZone, subir_iem
from aria.compte_rendu import decrire
from aria.des import DesTruques
from aria.equipement import (
    ARMES_A_DISTANCE,
    CORPS_A_CORPS,
    Arme,
    Armure,
    Modification,
    Munitions,
    Portee,
    Propriete,
    Qualite,
    Recharge,
    verifier_arme,
)
from aria.personnage import Etat
from tests.test_combat import GILET, combat, ganger, kaito
from tests.test_outils import ganger as ganger_de_session
from tests.test_outils import session

LANCER = frozenset({Propriete.LANCER})
GRENADE = Arme("Grenade à fragmentation", ARMES_A_DISTANCE, "3d6", Portee.COURTE, proprietes=LANCER,
               zone="petite", usage_unique=True)
INCENDIAIRE = Arme("Grenade incendiaire", ARMES_A_DISTANCE, "2d6", Portee.COURTE, proprietes=LANCER,
                   zone="petite", effets=frozenset({"brûlure"}), usage_unique=True)
FLASH = Arme("Grenade flash", ARMES_A_DISTANCE, None, Portee.COURTE, proprietes=LANCER, zone="petite",
             effets=frozenset({"aveuglant"}), usage_unique=True)
FUMIGENE = Arme("Grenade fumigène", ARMES_A_DISTANCE, None, Portee.COURTE, proprietes=LANCER, zone="petite",
                effets=frozenset({"fumée"}), usage_unique=True)
GRENADE_IEM = Arme("Grenade IEM", ARMES_A_DISTANCE, None, Portee.COURTE, proprietes=LANCER, zone="petite",
                   effets=frozenset({"IEM"}), usage_unique=True, electronique=True)
LANCE_ROQUETTES = Arme("Lance-roquettes", ARMES_A_DISTANCE, "4d6", Portee.LONGUE, munitions=Munitions(1, Recharge.SIMPLE),
                       proprietes=frozenset({Propriete.DEUX_MAINS, Propriete.PERFORANTE, Propriete.ENCOMBRANTE}),
                       zone="moyenne")
CHARGE = Arme("Charge d'explosif", ARMES_A_DISTANCE, "4d6", Portee.CONTACT, zone="grande", usage_unique=True, posee=True)


def test_les_armes_de_zone_respectent_leurs_bornes():
    for arme in (GRENADE, INCENDIAIRE, FLASH, FUMIGENE, GRENADE_IEM, LANCE_ROQUETTES, CHARGE):
        assert verifier_arme(arme) == [], arme.nom
    petard = Arme("Pétard", ARMES_A_DISTANCE, "1d6", Portee.COURTE, proprietes=LANCER, zone="petite", usage_unique=True)
    assert any("hors des bornes" in e for e in verifier_arme(petard))
    assert any("Zone inconnue" in e for e in verifier_arme(Arme("Bombe", ARMES_A_DISTANCE, "3d6", Portee.COURTE,
                                                                 proprietes=LANCER, zone="immense")))
    assert any("Ni dégâts" in e for e in verifier_arme(Arme("Rien", ARMES_A_DISTANCE, None, Portee.COURTE,
                                                             proprietes=LANCER, zone="petite")))
    canon = Arme("Canon", ARMES_A_DISTANCE, "4d6", Portee.LONGUE, montee=True)
    assert any("arme montée" in e for e in verifier_arme(canon))  # une arme montée s'arrête à 3d6


def test_une_grenade_touche_toute_la_zone():
    k, g1, g2 = kaito(GRENADE), ganger(nom="Ganger 1"), ganger(nom="Ganger 2")
    # Athlétisme 20 : 15 réussit. 3d6 = 12. Ganger 1 rate son esquive (80) : 12, il tombe.
    # Ganger 2 esquive (30) : la moitié, 6, blessure grave, et il tient (Constitution 20).
    c = combat(DesTruques(15, 4, 4, 4, 80, 30, 20), k, g1, g2)
    r = c.attaquer_zone(k, [g1, g2])
    assert (r.competence, r.issue, r.jet_degats) == ("Athlétisme", IssueZone.REUSSITE, 12)
    assert g1.fiche.etat is Etat.MOURANT
    assert r.cibles[1].degats_bruts == 6 and g2.fiche.pv == 4 and g2.fiche.etat is Etat.ACTIF
    assert k.arme is None  # une grenade ne sert qu'une fois


def test_ratee_elle_devie():
    k, g = kaito(GRENADE), ganger(armure=GILET)
    # 50 rate : la moitié des dégâts (6), et +20 pour esquiver (45 + 20 = 65 ; 70 rate). Le gilet en arrête 3.
    r = combat(DesTruques(50, 4, 4, 4, 70), k, g).attaquer_zone(k, [g])
    assert r.issue is IssueZone.DEVIATION
    assert r.cibles[0].esquive.valeur == 65
    assert (r.cibles[0].degats_bruts, r.cibles[0].protection, g.fiche.pv) == (6, 3, 7)


def test_maladresse_aux_pieds_du_lanceur():
    k, g = kaito(GRENADE), ganger()
    allie = Combattant(ganger().fiche, "joueur")
    # 96 : maladresse. Les cibles prévues sont épargnées ; Kaito et son voisin prennent 3 chacun.
    r = combat(DesTruques(96, 1, 1, 1, 99, 90), k, g, allie).attaquer_zone(k, [g], voisins=[allie])
    assert r.issue is IssueZone.MALADRESSE
    assert [c.qui for c in r.cibles] == ["Kaito", "Ganger"]
    assert g.fiche.pv == 10 and k.fiche.pv == k.fiche.pv_max_base - 3 and allie.fiche.pv == 7


def test_esquive_majeure_couvert_lourd_et_sans_esquive():
    k, g1, g2 = kaito(LANCE_ROQUETTES), ganger(nom="A"), ganger(nom="B")
    g3 = ganger(nom="C")
    # Armes à distance 50 : 20 réussit. 4d6 = 12. A rate son esquive mais il est à couvert : 6.
    # (blessure grave, il tient sa Constitution : 20). B esquive en majeure (10) : rien. C n'esquive pas : 12.
    c = combat(DesTruques(20, 3, 3, 3, 3, 90, 20, 10), k, g1, g2, g3)
    r = c.attaquer_zone(k, [g1, g2, g3], couverts_lourds=[g1], sans_esquive=[g3])
    assert [x.degats_bruts for x in r.cibles] == [6, 0, 12]
    assert r.cibles[2].esquive is None and g2.fiche.pv == 10
    assert k.munitions_restantes() == 0
    with pytest.raises(ActionImpossible, match="vide"):
        c.attaquer_zone(k, [g1])


def test_une_roquette_perforante_ne_laisse_que_la_moitie_de_l_armure():
    k, g = kaito(LANCE_ROQUETTES), ganger(armure=GILET)
    r = combat(DesTruques(20, 1, 1, 1, 1, 90), k, g).attaquer_zone(k, [g])
    assert r.cibles[0].protection == 1


def test_les_limites_de_la_zone():
    k = kaito(GRENADE)
    gangers = [ganger(nom=f"G{i}") for i in range(3)]
    c = combat(DesTruques(), k, *gangers)
    with pytest.raises(ActionImpossible, match="2 cibles au plus"):
        c.attaquer_zone(k, gangers)
    with pytest.raises(ActionImpossible, match="deux fois"):
        c.attaquer_zone(k, [gangers[0], gangers[0]])
    with pytest.raises(ActionImpossible, match="attaque de zone"):
        c.attaquer(k, gangers[0])
    k.arme = None
    with pytest.raises(ActionImpossible, match="pas d'arme de zone"):
        c.attaquer_zone(k, gangers[:1])


def test_un_pnj_lance_avec_son_pourcentage_de_combat():
    g, k = ganger(GRENADE), kaito()
    r = combat(DesTruques(30, 1, 1, 1, 90), k, g).attaquer_zone(g, [k])
    assert (r.competence, r.attaque.valeur) == ("Armes à distance", 45)


def test_une_charge_posee_se_joue_en_artisanat_sans_explosifs():
    k, g = kaito(CHARGE), ganger()
    r = combat(DesTruques(20, 1, 1, 1, 1, 90), k, g).attaquer_zone(k, [g])
    assert r.competence == "Artisanat"


def test_brulure_persistante():
    k, g1, g2 = kaito(INCENDIAIRE), ganger(nom="A"), ganger(nom="B")
    # 2d6 = 4. A rate son esquive : il brûle. B esquive en majeure (10) : ni dégâts ni brûlure.
    r = combat(DesTruques(15, 2, 2, 90, 10), k, g1, g2).attaquer_zone(k, [g1, g2])
    assert [e.nature for e in g1.effets] == ["attaque"] and g1.effets[0].persistant
    assert g2.effets == [] and r.cibles[1].effets == []


def test_flash_aveuglant():
    k, g1, g2 = kaito(FLASH), ganger(nom="A"), ganger(nom="B")
    # Pas d'esquive ni de dégâts : chacun teste sa Constitution (50). A rate (80), B tient (20).
    r = combat(DesTruques(15, 80, 20), k, g1, g2).attaquer_zone(k, [g1, g2])
    assert r.jet_degats == 0 and r.cibles[0].blessure is None
    assert g1.valeur("Esquive") == 25 and g2.valeur("Esquive") == 45


def test_fumee():
    k, g = kaito(FUMIGENE), ganger()
    c = combat(DesTruques(15), k, g)
    r = c.attaquer_zone(k, [])
    assert c.fumee == 3 and "couvert lourd" in r.effets[-1]
    c.fin_de_round()
    assert c.fumee == 2


VISEUR = Modification("Viseur holographique", "précision", 5, electronique=True)
PISTOLET_VISEUR = Arme("Pistolet", ARMES_A_DISTANCE, "1d8", Portee.COURTE, munitions=Munitions(10, Recharge.SIMPLE),
                       qualite=Qualite.ORIGINE, modifications=(VISEUR,))
MANTIS = Arme("Lames-mantis", CORPS_A_CORPS, "2d6", Portee.CONTACT, proprietes=frozenset({Propriete.DEUX_MAINS}))


def kaito_augmente():
    k = kaito(PISTOLET_VISEUR)
    k.fiche.implants = [{"nom": "Yeux cybernétiques", "qualite": "d'origine", "sm": 2},
                        {"nom": "Kerenzikov", "qualite": "d'origine", "sm": 4, "competence": "Esquive", "bonus": 5}]
    k.armure_implantee = Armure("Peau dermique", 2)
    k.armes_implantees = frozenset({"Lames-mantis"})
    return k


def test_l_iem_coupe_les_implants():
    k, g = kaito_augmente(), ganger(GRENADE_IEM)
    assert (k.valeur("Esquive"), k.protection, PISTOLET_VISEUR.bonus.jet) == (55, 2, 5)
    c = combat(DesTruques(15), k, g)
    r = c.attaquer_zone(g, [k])
    assert any("yeux cybernétiques" in e for e in r.cibles[0].effets)
    assert k.iem
    assert k.valeur("Esquive") == 50 - 20  # plus de Kerenzikov, et aveuglé
    assert k.protection == 0
    assert PISTOLET_VISEUR.bonus_sans(electronique=True).jet == 0
    k.arme = MANTIS
    with pytest.raises(ActionImpossible, match="coupée par l'IEM"):
        c.attaquer(k, g)
    c.fin_de_round()
    assert not k.iem and k.valeur("Esquive") == 55 and k.protection == 2


def test_le_tir_perd_son_viseur_sous_l_iem():
    k, g = kaito_augmente(), ganger()
    subir_iem(k, "Grenade IEM")
    r = combat(DesTruques(99), k, g).attaquer(k, g)
    assert r.attaque.valeur == 50 - 20  # Armes à distance 50, sans le viseur, et aveuglé


def test_le_blindage_iem_protege():
    k = kaito_augmente()
    k.blindage_iem = True
    assert subir_iem(k, "Grenade IEM") == ["blindage IEM : aucun effet"] and not k.iem


# --- Par l'outil du MJ -----------------------------------------------------------------------

def test_l_outil_n_apparait_qu_avec_une_arme_de_zone_en_main():
    # 1 : critique, 3d6 = 6, le ganger rate son esquive (90) puis tient sa Constitution (10).
    s = session(1, 2, 2, 2, 90, 10)
    ganger_de_session(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    noms = lambda: {x["function"]["name"] for x in s.schemas()}  # noqa: E731
    assert "attaquer_zone" not in noms()
    s.joueur.arme = GRENADE
    assert "attaquer_zone" in noms()
    r = s.appeler("attaquer_zone", {"attaquant": "joueur", "cibles": ["ganger"]})
    assert r["issue"] == "réussite" and r["cibles"][0]["degats"] == 6 and r["cibles"][0]["pv"] == 4
    lignes = decrire("attaquer_zone", {}, r, s)
    assert lignes[0].startswith("💥 Kaito, Grenade à fragmentation") and "6 dégâts" in lignes[0]
    assert "attaquer_zone" not in noms()  # la grenade est partie
