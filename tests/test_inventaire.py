"""L'économie, lot 2 (REGLES.md 13.5 et 13.9) : les emplacements, le portage, les sacs, les munitions comptées."""

import random

import pytest

from aria import inventaire as inv_
from aria import outils
from aria.combat import ActionImpossible, TypeAction
from aria.creation import Brouillon, proposer_chiffres
from aria.des import Des
from aria.inventaire import (
    ARME,
    GARNISSEUR,
    LAME,
    OBJET,
    OUTIL,
    PORTAGE,
    SAC,
    Inventaire,
    InventaireImpossible,
    a_chargeur,
    cadence,
)
from aria.outils import Session
from aria.personnage import Caracteristique
from aria.sauvegarde import personnage_depuis_dict, personnage_vers_dict
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from tests.test_univers import CYBERPUNK


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def perso(u, parcours="Solo", force=60, arme="Pistolet lourd", armure="Gilet balistique", adistance=None):
    """Un personnage créé comme dans le jeu, avec l'arme et l'armure voulues parmi les listes de son métier."""
    b = proposer_chiffres(Brouillon(u), random.Random(1), parcours)
    b.fixer("equipement", dict(b.equipement, arme=arme, armure=armure))
    b.fixer("roleplay", {"nom": "Yuki", "motivation": "m", "lien": "l", "defaut": "d"})
    p, depart = b.finaliser()
    p.caracteristiques[Caracteristique.FORCE] = force
    if adistance is not None:
        p.competences["Armes à distance"] = adistance
    return p, depart


def session(u, des=None, **options):
    p, depart = perso(u, **options)
    s = Session(u, p, des or Des(1), Moment(1, Periode.APRES_MIDI), arme=depart.arme, armure=depart.armure)
    return s, s.inventaire


def combat(s, combat_pnj=40):
    outils.creer_pnj(s, "ganger", "Ganger", "ennemis", combat_pnj, 10, arme="Pistolet léger")
    outils.debut_combat(s, ["ganger"])
    s.combat.ordre.sort(key=lambda c: c is not s.joueur)  # le joueur d'abord
    return s.combat


# --- L'équipement de départ -----------------------------------------------------------------------------

def test_l_equipement_de_depart_entre_dans_l_inventaire(u):
    s, i = session(u)
    assert i.noms(ARME) == ["Pistolet lourd"] and i.est_pret("Pistolet lourd")
    assert [(c["cartouches"], c["capacite"], c["rapide"]) for c in i.chargeurs] == [(8, 8, False)]  # le second : le premier est dans l'arme
    assert sum(i.vrac.values()) == 20 and s.joueur.munitions_restantes() == 8
    assert i.trouver("Gilet balistique")["portee"] and len(i.noms(OBJET)) == 2
    assert i.capacite() == 10  # 4 + Force 60 ÷ 10
    # l'arme 1, un chargeur 0,5, une boîte 0,5, deux objets 2 ; l'armure portée ne compte pas
    assert i.utilises() == 4 and not i.surcharge()
    assert personnage_depuis_dict(personnage_vers_dict(s.personnage)).inventaire == s.personnage.inventaire


def test_un_revolver_part_avec_deux_chargeurs_rapides(u):
    p, _ = perso(u)
    p.inventaire = None
    i = inv_.equipement_de_depart(p, u, "Revolver lourd", None, [])
    assert sum(i.vrac.values()) == 20
    assert [c["rapide"] for c in i.chargeurs] == [True, True] and not a_chargeur(u.arme("Revolver lourd"))


def test_un_personnage_sans_inventaire_joue_comme_avant(u):
    p, _ = perso(u)
    p.inventaire = None
    s = Session(u, p, Des(1), arme="Fusil d'assaut")  # toute l'armurerie se dégaine
    assert s.inventaire is None and s.joueur.reserve is None and "inventaire" not in outils.etat(s)["joueur"]
    c = combat(s)
    s.joueur.munitions[s.joueur.arme] = 0
    c.recharger(s.joueur)
    assert s.joueur.munitions_restantes() == 30  # sans compter


# --- Les emplacements, le portage, les sacs -------------------------------------------------------------

def test_les_emplacements_et_la_surcharge(u):
    _, i = session(u, force=35)
    assert i.capacite() == 7
    i.ajouter("Fusil d'assaut", ARME)  # 2 emplacements
    i.ajouter("Carabine", ARME)  # 2 de plus : 8 pour 7
    assert i.utilises() == 8 and i.surcharge()
    assert i.malus("Esquive") == -20 and i.malus("Discrétion") == -20 and i.malus("Persuasion") == 0
    i.ajouter("Sac à dos de ville", SAC)
    assert i.capacite() == 11 and not i.surcharge() and i.malus("Esquive") == 0
    with pytest.raises(InventaireImpossible, match="le double au plus"):
        for _ in range(12):
            i.ajouter("Fusil à pompe", ARME)


def test_trois_objets_sous_la_main_sans_equipement(u):
    _, i = session(u)
    # prêts : le pistolet (1), le chargeur (0,5) ; les deux objets du métier prennent les deux places restantes… ou pas
    prets = [o["nom"] for o in i.objets if o.get("pret")]
    assert prets[0] == "Pistolet lourd" and i._libre()["objet"] >= 0
    i.ajouter("Katana", ARME)
    assert not i.est_pret("Katana")  # plus de place : il va dans le sac
    with pytest.raises(InventaireImpossible, match="Plus de place sous la main"):
        i.preparer("Katana")
    i.ajouter("Holster", PORTAGE)  # une place réservée à une arme à une main
    i.preparer("Katana")
    assert i.est_pret("Katana")
    with pytest.raises(InventaireImpossible, match="déjà un équipement de ce genre"):
        i.ajouter("Holster", PORTAGE)


def test_le_gilet_tactique_tient_les_chargeurs(u):
    s, i = session(u)
    arme = u.arme("Pistolet lourd")
    for _ in range(6):
        i.ajouter_chargeur(arme)
    assert sum(bool(c.get("pret")) for c in i.chargeurs) < 7  # sans gilet, tous ne tiennent pas sous la main
    i.ajouter("Gilet tactique moyen", PORTAGE)  # + 4 emplacements de petits objets : huit chargeurs
    for c in i.chargeurs:
        c["pret"] = True
    assert not i.prets_en_trop()
    i.retirer("Gilet tactique moyen")
    assert not i.prets_en_trop() and sum(bool(c.get("pret")) for c in i.chargeurs) < 7  # le surplus est retourné au sac
    with pytest.raises(InventaireImpossible):
        i.preparer("Gilet balistique")  # l'armure se porte


def test_les_sacs(u):
    _, i = session(u, force=50)
    i.ajouter("Sac de randonnée", SAC)
    assert i.capacite() == 9 + 10 and i.prets()["objet"] == 3 + 2  # deux poches latérales
    assert i.malus("Esquive") == -10 and i.malus("Athlétisme") == -10 and i.malus("Discrétion") == 0
    with pytest.raises(InventaireImpossible, match="déjà un sac"):
        i.ajouter("Sac à dos tactique", SAC)
    i.ajouter("Sacoche", SAC)  # en plus du sac à dos
    assert i.capacite() == 9 + 10 + 2
    i.ajouter("Gilet tactique lourd", PORTAGE)
    assert i.malus("Discrétion") == -10
    assert set(i.resume()["portage"]) == {"Gilet tactique lourd", "Sac de randonnée", "Sacoche"}


# --- Les munitions comptées -----------------------------------------------------------------------------

def test_la_cadence_de_garnissage():
    assert [cadence(v) for v in (20, 49, 50, 74, 75, 99)] == [3, 3, 5, 5, 7, 7]
    assert [cadence(v, GARNISSEUR) for v in (40, 60, 80)] == [6, 10, 14]
    assert [cadence(v, LAME) for v in (40, 60, 80)] == [10, 10, 15]


def test_changer_de_chargeur_puis_garnir_a_la_main(u):
    s, i = session(u, adistance=40)
    c, k, arme = combat(s), s.joueur, s.joueur.arme
    k.munitions[arme] = 3
    c.recharger(k)  # une action mineure : le chargeur de rechange
    assert k.munitions_restantes() == 8 and k.budget.restants(TypeAction.MINEURE) == 0
    assert [ch["cartouches"] for ch in i.chargeurs] == [3]  # celui qu'on a retiré est gardé, entamé
    k.munitions[arme] = 0
    k.budget = type(k.budget)()
    c.recharger(k)  # le chargeur entamé : 3 cartouches
    assert k.munitions_restantes() == 3 and [ch["cartouches"] for ch in i.chargeurs] == [0]
    k.budget = type(k.budget)()
    k.munitions[arme] = 0
    with pytest.raises(ActionImpossible, match="Plus de chargeur garni sous la main"):
        c.recharger(k)
    assert k.budget.restants(TypeAction.MINEURE) == 1  # l'action n'est pas perdue
    # Garnir à la main : 3 cartouches par action simple à moins de 50, + 2 avec l'action mineure
    assert c.garnir(k, avec_la_mineure=True) == 5
    assert [ch["cartouches"] for ch in i.chargeurs] == [5] and sum(i.vrac.values()) == 15
    assert k.budget.restants(TypeAction.SIMPLE) == 0 and k.budget.restants(TypeAction.MINEURE) == 0


def test_un_tireur_expert_et_un_garnisseur(u):
    s, i = session(u, adistance=80)
    c, k = combat(s), s.joueur
    i.chargeurs[0]["cartouches"] = 0
    assert c.garnir(k) == 7  # 75 et plus : 7 à la main
    i.ajouter(GARNISSEUR, OUTIL)
    i.chargeurs[0]["cartouches"] = 0
    k.budget = type(k.budget)()
    assert c.garnir(k) == 8  # 14 avec le garnisseur, mais le chargeur n'en tient que 8


def test_une_arme_sans_chargeur_se_garnit_directement(u):
    s, i = session(u, "Solo", arme="Fusil à pompe", adistance=60)
    c, k, arme = combat(s), s.joueur, s.joueur.arme
    assert not a_chargeur(arme) and i.chargeurs == []
    k.munitions[arme] = 0
    c.recharger(k)  # pas de chargeur : on garnit, 5 cartouches à 60
    assert k.munitions_restantes() == 5 and k.budget.restants(TypeAction.SIMPLE) == 0
    k.budget = type(k.budget)()
    assert c.garnir(k) == 1 and k.munitions_restantes() == 6  # l'arme est pleine
    i.vrac.clear()
    k.munitions[arme] = 0
    k.budget = type(k.budget)()
    with pytest.raises(ActionImpossible, match="Plus de cartouches en vrac"):
        c.recharger(k)


def test_la_lame_chargeur_se_consomme(u):
    s, i = session(u, "Solo", arme="Fusil à pompe", adistance=40)
    i.ajouter("Fusil d'assaut", ARME, charge=0)
    fusil = u.arme("Fusil d'assaut")
    i.ajouter_chargeur(fusil, cartouches=0)
    i.ajouter_cartouches(fusil, 40)
    i.ajouter(LAME, OUTIL)
    assert i.moyen_de_garnir(fusil) == LAME and i.garnir(fusil, cadence(40, LAME)) == (10, None)
    assert not i.a(LAME) and i.moyen_de_garnir(fusil) == "main"
    assert i.regarnir_tout() == {"Fusil d'assaut": 20} and i.vrac[inv_.calibre(fusil)] == 10


def test_les_pnj_comptent_aussi_leurs_chargeurs(u):
    s, _ = session(u)
    c = combat(s)
    ganger = s.pnj["ganger"]
    assert ganger.reserve.chargeurs_restants == [12, 12]
    for attendu in (2, 1):
        ganger.munitions[ganger.arme] = 0
        ganger.budget = type(ganger.budget)()
        assert len(ganger.reserve.chargeurs_restants) == attendu
        ganger.reserve.changer_chargeur(ganger.arme, 0)
    with pytest.raises(InventaireImpossible):
        ganger.reserve.changer_chargeur(ganger.arme, 0)


# --- La session et les outils du MJ ---------------------------------------------------------------------

def test_seules_les_armes_possedees_se_degainent(u):
    s, i = session(u)
    assert [a.nom for a in s.armes_du_joueur() if not a.nom.startswith("Lames")][:1] == ["Pistolet lourd"]
    c = combat(s)
    assert "erreur" in s.appeler("action_combat", {"qui": "joueur", "action": "degainer", "arme": "Fusil d'assaut"})
    i.ajouter("Katana", ARME, pret=False)
    r = s.appeler("action_combat", {"qui": "joueur", "action": "degainer", "arme": "Katana"})
    assert "erreur" not in r and s.joueur.arme.nom == "Katana"
    assert s.joueur.budget.restants(TypeAction.SIMPLE) == 0  # il était au fond du sac : une action simple
    assert c is s.combat


def test_l_outil_inventaire(u):
    s, i = session(u)
    assert "inventaire" in {x["function"]["name"] for x in s.schemas()}
    i.ajouter("Katana", ARME, pret=False)
    for objet in i.objets:
        if objet["famille"] == OBJET:
            objet["pret"] = False  # de la place sous la main
    r = s.appeler("inventaire", {"action": "preparer", "objet": "Katana"})
    assert "Katana" in r["prets"] and "erreur" in s.appeler("inventaire", {"action": "preparer", "objet": "Katana"})
    assert "Katana" in s.appeler("inventaire", {"action": "ranger", "objet": "Katana"})["ranges"]
    r = s.appeler("inventaire", {"action": "poser", "objet": "Katana"})
    assert not i.a("Katana") and r["portes"] == ["Gilet balistique"] and "Gilet balistique" not in r["ranges"]
    i.chargeurs[0]["cartouches"] = 2
    r = s.appeler("inventaire", {"action": "regarnir"})
    assert r["cartouches_garnies"] == {"Pistolet lourd": 6} and sum(i.vrac.values()) == 14
    combat(s)
    assert "erreur" in s.appeler("inventaire", {"action": "regarnir"})  # en combat, on garnit à la main
    r = s.appeler("action_combat", {"qui": "joueur", "action": "recharger"})
    assert r["munitions"] == 8 and r["chargeurs"] and "cartouches_en_vrac" in r
    assert outils.etat(s)["joueur"]["inventaire"]["emplacements"].endswith("/ 10")


def test_le_contenu_de_l_arme_survit_a_la_sauvegarde(u):
    s, _ = session(u)
    s.joueur.munitions[s.joueur.arme] = 2
    s.noter_les_charges()
    relu = personnage_depuis_dict(personnage_vers_dict(s.personnage))
    reprise = Session(u, relu, Des(1), arme="Pistolet lourd", armure="Gilet balistique")
    assert reprise.joueur.munitions_restantes() == 2 and len(reprise.inventaire.chargeurs) == 1


def test_une_grenade_lancee_quitte_l_inventaire(u):
    s, i = session(u, des=Des(3))
    i.ajouter("Grenade à fragmentation", ARME)
    combat(s)
    r = s.appeler("attaquer_zone", {"attaquant": "joueur", "cibles": ["ganger"], "arme": "Grenade à fragmentation"})
    assert "erreur" not in r and not i.a("Grenade à fragmentation")
