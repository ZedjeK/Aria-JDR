"""Le combat avec des véhicules, l'armement monté, les systèmes défensifs et les drones (REGLES.md 12.4 et 12.7)."""

from dataclasses import replace

import pytest

from aria.combat import ActionImpossible, blesser, combattant_drone, iem_sur_engin, subir_iem
from aria.des import DesTruques
from aria.equipement import ARMES_A_DISTANCE, Arme, Munitions, Portee, Propriete, Recharge
from aria.reglages import Curseur
from aria.vehicules import Engin, ModVehicule, Vehicule, verifier_armement
from tests.test_combat import FUSIL, PISTOLET, combat, ganger, kaito
from tests.test_vehicules import MOTO, VOITURE, session_motarde
from tests.test_zone import GRENADE, LANCE_ROQUETTES

MITRAILLEUSE_LOURDE = Arme("Mitrailleuse lourde", ARMES_A_DISTANCE, "3d6", Portee.LONGUE,
                           munitions=Munitions(100, Recharge.SIMPLE), proprietes=frozenset({Propriete.PERFORANTE}),
                           montee=True)
ARMES = {a.nom: a for a in (PISTOLET, FUSIL, MITRAILLEUSE_LOURDE, LANCE_ROQUETTES, GRENADE)}
BLINDE = Vehicule("Blindé", "terrestre", "lourd", "moyenne", -10, 50, 6, places=8, electronique=True,
                  armes_montees=({"tourelle": "lourde", "arme": "Mitrailleuse lourde"},
                                 {"tourelle": "légère", "arme": "Fusil"}),
                  systemes=("Lance-fumigènes",))
AV = Vehicule("AV", "aérien", "lourd", "très rapide", 0, 50, 6, electronique=True, systemes=("Leurres",))
DRONE = Vehicule("Drone de combat", "aérien", "drone", "rapide", 10, 10, 1, places=0, electronique=True,
                 armes_montees=({"tourelle": "légère", "arme": "Pistolet"},))


# --- Les points d'emport et les tourelles ----------------------------------------------------

@pytest.mark.parametrize(
    "vehicule, erreur",
    [
        (BLINDE, None),
        (DRONE, None),
        (replace(VOITURE, armes_montees=({"tourelle": "lourde", "arme": "Mitrailleuse lourde"},)), "Pas de tourelle lourde"),
        (replace(VOITURE, armes_montees=({"tourelle": "légère", "arme": "Mitrailleuse lourde"},)), "tourelle lourde"),
        (replace(VOITURE, armes_montees=({"tourelle": "légère", "arme": "Fusil"},) * 2), "points d'emport"),
        (replace(VOITURE, modifications=(ModVehicule("Tourelle télécommandée", "support d'arme", 1),),
                 armes_montees=({"tourelle": "légère", "arme": "Fusil"},) * 2), None),
        (replace(MOTO, armes_montees=({"tourelle": "légère", "arme": "Pistolet"},)), "points d'emport"),
        (replace(BLINDE, systemes=("Bouclier d'énergie",)), "Système défensif inconnu"),
        (replace(BLINDE, drones={"nombre": 2, "modele": "Drone de combat"}), "baie à drones"),
        (replace(VOITURE, arme_integree="Grenade à fragmentation"), "Seul un drone"),
    ],
)
def test_l_armement_d_un_vehicule(vehicule, erreur):
    erreurs = verifier_armement(vehicule, ARMES)
    assert erreurs == [] if erreur is None else any(erreur in e for e in erreurs), erreurs


# --- Tirer depuis un véhicule, et sur un véhicule ---------------------------------------------

def test_tirer_depuis_un_vehicule():
    k, g = kaito(PISTOLET), ganger()
    r = combat(DesTruques(99), k, g).attaquer(k, g, tireur="conducteur")
    assert r.attaque.valeur == 50 - 20
    k2 = kaito(PISTOLET)
    assert combat(DesTruques(99), k2, g).attaquer(k2, g, tireur="passager").attaque.valeur == 50 - 10
    k3 = kaito(replace(FUSIL, proprietes=frozenset({Propriete.DEUX_MAINS})))
    with pytest.raises(ActionImpossible, match="une main"):
        combat(DesTruques(), k3, g).attaquer(k3, g, tireur="conducteur")
    k4 = kaito(MITRAILLEUSE_LOURDE)
    with pytest.raises(ActionImpossible, match="tourelle"):
        combat(DesTruques(), k4, g).attaquer(k4, g)


def test_tirer_sur_la_carrosserie():
    k, voiture = kaito(PISTOLET), Engin(VOITURE)
    r = combat(DesTruques(20, 7), k).tirer_sur_vehicule(k, voiture)
    assert (r.degats_bruts, r.blindage, r.structure_perdue, voiture.structure) == (7, 2, 5, 25)
    perforant = Arme("Fusil perforant", ARMES_A_DISTANCE, "2d6", Portee.LONGUE, munitions=Munitions(5, Recharge.SIMPLE),
                     proprietes=frozenset({Propriete.DEUX_MAINS, Propriete.PERFORANTE}))
    k2, blinde = kaito(perforant), Engin(BLINDE)
    r = combat(DesTruques(20, 4, 4), k2).tirer_sur_vehicule(k2, blinde)
    assert (r.blindage, r.structure_perdue) == (3, 5)


def test_viser_les_pneus():
    k, voiture = kaito(PISTOLET), Engin(VOITURE)
    r = combat(DesTruques(25), k).tirer_sur_vehicule(k, voiture, "pneus")
    assert r.attaque.valeur == 30 and r.touche  # difficile
    assert voiture.vitesse == "moyenne" and voiture.structure == 30
    with pytest.raises(ActionImpossible, match="blindé"):
        combat(DesTruques(), k).tirer_sur_vehicule(k, Engin(BLINDE), "pneus")


def test_les_leurres_detournent_une_roquette():
    k, av = kaito(LANCE_ROQUETTES), Engin(AV)
    r = combat(DesTruques(), k).tirer_sur_vehicule(k, av)
    assert r.attaque is None and "leurres" in r.effets[0] and av.structure == 50
    assert "Leurres" in av.systemes_utilises


def test_eperonner_un_pieton_puis_une_moto():
    k, g, voiture = kaito(), ganger(), Engin(VOITURE)
    # Pilotage 40 : 10 réussit, l'Esquive du ganger rate (90). 2d6 + 1d6 (rapide) = 9 ; Constitution 20.
    r = combat(DesTruques(10, 90, 3, 3, 3, 20), k, g).eperonner(k, voiture, g)
    assert r.touche and r.degats == 9 and g.fiche.pv == 1
    assert r.recul == 2 and voiture.structure == 28  # la moitié (4), moins son blindage (2)
    k2, g2, moto = kaito(), ganger(nom="Motard"), Engin(MOTO)
    r = combat(DesTruques(10, 90, 3, 3, 3), k2, g2).eperonner(k2, Engin(VOITURE), g2, moto)
    assert r.defense.valeur == 25 + 10  # Pilotage du PNJ, plus la maniabilité de la moto
    assert moto.structure == 15 - (9 - 1)


def test_la_cible_evite_le_choc():
    k, g = kaito(), ganger()
    r = combat(DesTruques(30, 10), k, g).eperonner(k, Engin(VOITURE), g)
    assert not r.touche and g.fiche.pv == 10


# --- L'IEM et les véhicules ------------------------------------------------------------------------

def test_iem_sur_les_vehicules():
    assert "mécanique" in iem_sur_engin(Engin(VOITURE))[0]
    electrique = Engin(replace(VOITURE, electronique=True))
    iem_sur_engin(electrique)
    assert electrique.coupe == 1 and electrique.vitesse == "moyenne"
    blinde = Engin(replace(VOITURE, electronique=True, systemes=("Blindage IEM de véhicule",)))
    assert "aucun effet" in iem_sur_engin(blinde)[0] and blinde.coupe == 0
    assert len(iem_sur_engin(Engin(AV))) == 2  # un véhicule aérien : le test de Pilotage en plus


def test_une_grenade_touche_aussi_le_vehicule():
    k, g, voiture = kaito(GRENADE), ganger(), Engin(VOITURE)
    r = combat(DesTruques(15, 4, 4, 4, 90), k, g).attaquer_zone(k, [g], vehicules=[voiture])
    assert r.vehicules == [("Voiture", 10, "intact", [])] and voiture.structure == 20


# --- Les drones --------------------------------------------------------------------------------------

def test_un_drone_autonome():
    d = combattant_drone(Engin(DRONE), "ennemis", PISTOLET)
    assert d.valeur("Armes à distance") == 40 and d.protection == 1 and d.fiche.pv == 10
    r = blesser(DesTruques(), Curseur.STANDARD, d, 12)
    assert r.etat.value == "mort" and d.drone.structure == 0


def test_un_drone_telepilote_agit_avec_l_action_de_son_operateur():
    k, g = kaito(PISTOLET), ganger(dexterite=40)
    d = combattant_drone(Engin(DRONE), "joueur", PISTOLET, operateur=k)
    assert d.valeur("Armes à distance") == 40  # le Pilotage de Kaito
    c = combat(DesTruques(99), k, g, d, tour_par_tour=True)
    assert [x.nom for x in c.ordre if c.peut_agir(x)] == ["Kaito", "Ganger"]  # pas de tour à lui
    c.attaquer(d, g)
    with pytest.raises(ActionImpossible, match="budget"):
        c.attaquer(k, g)  # Kaito a dépensé son action simple à piloter
    k.fiche.implants = [{"nom": "Neuroport", "qualite": "d'origine", "sm": 2}]
    assert d.valeur("Armes à distance") == 75  # son Piratage, par le neuroport


def test_l_iem_grille_un_drone_sauf_blindage():
    d = combattant_drone(Engin(DRONE), "ennemis", PISTOLET)
    assert "grillé" in subir_iem(d, "Grenade IEM")[0] and d.fiche.etat.value == "mort"
    blinde = combattant_drone(Engin(DRONE), "ennemis", PISTOLET, blindage_iem=True)
    assert "coupé" in subir_iem(blinde, "Grenade IEM")[0]
    assert not combat(DesTruques(), blinde).peut_agir(blinde)


# --- Par les outils du MJ ----------------------------------------------------------------------------

def session_armee(*des):
    s = session_motarde(*des)
    u = s.univers
    pickup = Vehicule("Pick-up armé", "terrestre", "moyen", "moyenne", 0, 30, 3, places=3,
                      armes_montees=({"tourelle": "légère", "arme": "Fusil d'assaut"},))
    drone = replace(DRONE, armes_montees=({"tourelle": "légère", "arme": "Pistolet lourd"},))
    s.univers = replace(u, vehicules=u.vehicules + (pickup, drone))
    assert s.univers.verifier() == []
    return s


def test_les_outils_de_l_armement():
    # Le drone autonome tire (99 : raté) ; le flic, depuis la tourelle du pick-up, tire sur Kaito (99).
    s = session_armee(99, 99)
    s.appeler("creer_pnj", {"identifiant": "flic", "nom": "Flic", "camp": "ennemis", "combat": 45, "pv": 10,
                            "vehicule": "Pick-up armé"})
    assert "erreur" not in s.appeler("debut_combat", {"pnj": ["flic"]})
    noms = {x["function"]["name"] for x in s.schemas()}
    assert {"tirer_sur_vehicule", "eperonner", "tirer_arme_montee", "lancer_drone"} <= noms
    r = s.appeler("lancer_drone", {"identifiant": "drone", "modele": "Drone de combat", "camp": "allies",
                                   "operateur": "joueur"})
    assert r["mode"] == "télépiloté par Kaito"
    assert "un seul" in s.appeler("lancer_drone", {"identifiant": "drone2", "modele": "Drone de combat",
                                                   "camp": "allies", "operateur": "joueur"})["erreur"]
    r = s.appeler("attaquer", {"attaquant": "drone", "cible": "flic"})
    assert r["attaque"]["valeur"] == 40  # le Pilotage de Kaito
    s.appeler("fin_de_tour")
    r = s.appeler("tirer_arme_montee", {"attaquant": "flic", "vehicule_de": "flic", "arme": "Fusil d'assaut",
                                        "cible": "joueur"})
    assert r["attaque"]["valeur"] == 45 and s.pnj["flic"].arme is None  # l'arme montée ne reste pas en main
    assert "ne porte pas" in s.appeler("tirer_arme_montee", {"attaquant": "flic", "vehicule_de": "joueur",
                                                              "arme": "Fusil d'assaut", "cible": "joueur"})["erreur"]


def test_en_poursuite_la_distance_dit_ce_qui_porte():
    s = session_armee()
    s.appeler("creer_pnj", {"identifiant": "flic", "nom": "Flic", "camp": "ennemis", "combat": 45, "pv": 10,
                            "arme": "Couteau", "vehicule": "Berline"})
    s.appeler("debut_poursuite", {"fuyard": "joueur", "poursuivants": ["flic"], "zone": "Autoroute",
                                  "distance": "loin"})
    s.appeler("debut_combat", {"pnj": ["flic"]})
    r = s.appeler("attaquer", {"attaquant": "joueur", "cible": "flic", "tireur": "conducteur"})
    assert "portée longue" in r["erreur"]
    assert "au contact" in s.appeler("eperonner", {"attaquant": "joueur", "cible": "flic"})["erreur"]
