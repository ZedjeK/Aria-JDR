"""Les véhicules, les montures et les poursuites (REGLES.md 12.1 à 12.3, 12.5 et 12.6)."""

from dataclasses import replace

import pytest

from aria.combat import Combattant, FichePnj
from aria.compte_rendu import decrire
from aria.des import DesTruques
from aria.equipement import Armure, Qualite
from aria.outils import Session
from aria.poursuite import (
    AU_CONTACT,
    LOIN,
    PROCHE,
    SEME,
    ZONES,
    Conducteur,
    Evenement,
    Poursuite,
    PoursuiteImpossible,
)
from aria.resolution import Difficulte
from aria.sauvegarde import Partie, partie_depuis_dict, partie_vers_dict
from aria.temps import Moment, Periode
from aria.univers import univers_depuis_dict
from aria.vehicules import (
    ENDOMMAGE,
    EPAVE,
    INTACT,
    MOURANTE,
    Engin,
    ModVehicule,
    Vehicule,
    VehiculeImpossible,
    accident,
    piloter,
    reparer,
    verifier_vehicule,
)
from tests.test_univers import donnees_cyberpunk, fiche_kaito

VOITURE = Vehicule("Voiture", "terrestre", "moyen", "rapide", 0, 30, 2, places=4)
MOTO = Vehicule("Moto", "terrestre", "léger", "très rapide", 10, 15, 1, places=2)
CHEVAL = Vehicule("Cheval", "terrestre", "léger", "rapide", 10, 15, 0, places=2, monture=True)
TURBO = ModVehicule("Turbo", "moteur", 1)
SUSPENSIONS = ModVehicule("Suspensions sport", "châssis", 5)
NITRO = ModVehicule("Kit nitro", "nitro", 10)
PNEUS = ModVehicule("Pneus tout-terrain", "propriété", propriete="tout-terrain")
MATIN = Moment(1, Periode.MATIN)


def pilote(nom="Pilote", pilotage=50, **profil) -> Combattant:
    return Combattant(FichePnj(nom, combat=45, pv_max_base=10, competences={"Pilotage": pilotage}, **profil), "pnj")


# --- La fiche et la qualité -----------------------------------------------------------------

def test_les_bornes_du_gabarit():
    assert verifier_vehicule(VOITURE) == [] and verifier_vehicule(MOTO) == [] and verifier_vehicule(CHEVAL) == []
    erreurs = verifier_vehicule(Vehicule("Char-scooter", "terrestre", "léger", "lente", 5, 80, 9))
    assert any("structure va de 10 à 20" in e for e in erreurs)
    assert any("blindage va de 0 à 2" in e for e in erreurs)
    assert any("maniabilité" in e for e in erreurs)


@pytest.mark.parametrize(
    "vehicule, erreur",
    [
        (replace(VOITURE, qualite=Qualite.PERSONNALISE, modifications=(TURBO, SUSPENSIONS)), None),
        (replace(VOITURE, modifications=(TURBO, SUSPENSIONS)), "1 emplacement"),
        (replace(VOITURE, qualite=Qualite.UNIQUE, modifications=(TURBO, ModVehicule("Reprog", "moteur", 1))), "Plafond"),
        (replace(VOITURE, qualite=Qualite.PERSONNALISE, modifications=(TURBO, TURBO)), "une fois"),
        (replace(VOITURE, qualite=Qualite.USE), "défaut"),
        (replace(VOITURE, qualite=Qualite.USE, defaut="capricieux"), None),
        (replace(VOITURE, defaut="capricieux"), "Seul un véhicule usé"),
        (replace(CHEVAL, modifications=(NITRO,)), "ne va pas sur une monture"),
        (replace(VOITURE, modifications=(ModVehicule("Turbo fou", "moteur", 2),)), "vaut 1"),
    ],
)
def test_qualite_et_modifications(vehicule, erreur):
    erreurs = verifier_vehicule(vehicule)
    assert erreurs == [] if erreur is None else any(erreur in e for e in erreurs), erreurs


def test_les_modifications_et_les_defauts_changent_la_fiche():
    turbo = replace(VOITURE, qualite=Qualite.PERSONNALISE, modifications=(TURBO, SUSPENSIONS))
    assert (turbo.cran, turbo.maniabilite_totale) == (3, 5)
    fatiguee = replace(VOITURE, qualite=Qualite.USE, defaut="moteur fatigué")
    assert fatiguee.cran == 1
    rouillee = replace(VOITURE, qualite=Qualite.USE, defaut="carrosserie rouillée")
    assert rouillee.structure_max == 25
    pneus = replace(VOITURE, modifications=(PNEUS,))
    assert "tout-terrain" in pneus.proprietes_totales


# --- L'état, l'accident, la réparation --------------------------------------------------------

def test_endommage_puis_epave():
    e = Engin(VOITURE)
    assert (e.etat, e.vitesse, e.maniabilite) == (INTACT, "rapide", 0)
    assert e.encaisser(17) == 15  # le blindage en arrête 2
    assert (e.etat, e.vitesse, e.maniabilite) == (ENDOMMAGE, "moyenne", -10)
    e.encaisser(50)
    assert e.etat == EPAVE and e.structure == 0
    assert Engin(CHEVAL, structure=0).etat == MOURANTE


def test_accident_d_une_moto():
    e = Engin(MOTO)
    occupant = pilote()
    occupant.armure = Armure("Blouson", 1, {"Discrétion": -5})
    # Très rapide : 4d6 de structure (4), 3d6 aux occupants, +1d6 sur un véhicule léger (4), moins l'armure.
    r = accident(DesTruques(1, 1, 1, 1, 1, 1, 1, 1), e, [occupant])
    assert (r.vitesse, r.structure_perdue, e.structure) == ("très rapide", 4, 11)
    assert r.occupants[0][1] == 3 and occupant.fiche.pv == 7


def test_piloter_et_la_maladresse():
    conducteur = pilote()
    r = piloter(DesTruques(40), conducteur, Engin(MOTO), Difficulte.DIFFICILE)
    assert r.test.valeur == 50 + 10 - 20 and r.accident is None
    r = piloter(DesTruques(100, 1, 1, 1, 1, 1, 1, 1, 1), conducteur, Engin(MOTO))
    assert r.accident is not None
    capricieuse = Engin(replace(VOITURE, qualite=Qualite.USE, defaut="capricieux"))
    r = piloter(DesTruques(100), conducteur, capricieuse)
    assert r.cale and r.accident is None
    with pytest.raises(VehiculeImpossible, match="épave"):
        piloter(DesTruques(), conducteur, Engin(VOITURE, structure=0))


def test_reparer():
    mecano = Combattant(FichePnj("Mécano", combat=30, pv_max_base=10, competences={"Artisanat": 50}), "pnj")
    e = Engin(VOITURE, structure=10)
    # En atelier : Facile (70). 50 : réussite, 1d6 = 4.
    r = reparer(DesTruques(50, 4), mecano, e, MATIN, atelier=True)
    assert (r.test.valeur, r.structure_rendue, e.structure) == (70, 4, 14)
    with pytest.raises(VehiculeImpossible, match="déjà"):
        reparer(DesTruques(), mecano, e, MATIN)
    epave = Engin(VOITURE, structure=0)
    with pytest.raises(VehiculeImpossible, match="atelier"):
        reparer(DesTruques(), mecano, epave, MATIN)
    # Une maladresse fait perdre 1d6
    r = reparer(DesTruques(100, 3), mecano, e, Moment(1, Periode.APRES_MIDI))
    assert r.structure_rendue == -3


def test_une_monture_se_soigne_avec_la_survie():
    palefrenier = Combattant(FichePnj("Palefrenier", combat=30, pv_max_base=10, competences={"Survie": 60}), "pnj")
    r = reparer(DesTruques(20, 2, 3), palefrenier, Engin(CHEVAL, structure=5), MATIN, atelier=True)
    assert r.test.valeur == 60  # pas d'atelier pour une monture : Normale
    assert r.structure_rendue == 5  # réussite majeure : 2d6


# --- La poursuite ------------------------------------------------------------------------------

def test_les_zones_suivent_la_table():
    assert all(len(colonne) == 10 for colonne in ZONES.values())
    assert Evenement.VIRAGE not in ZONES["Autoroute"]
    assert ZONES["Hors de la ville"].count(Evenement.ACCIDENTE) == 3
    assert Evenement.LIGNE_DROITE not in ZONES["Bas-quartiers"]


def poursuite(fuyard_engin=VOITURE, poursuivant_engin=MOTO, zone="Autoroute", **options):
    f = Conducteur("fuyard", pilote("Fuyard"), Engin(fuyard_engin) if fuyard_engin else None)
    p = Conducteur("flic", pilote("Flic"), Engin(poursuivant_engin) if poursuivant_engin else None)
    return Poursuite(f, [p], zone, **options)


def test_le_fuyard_seme_sur_une_reussite_majeure():
    p = poursuite()
    # Autoroute, 1 : voie dégagée. La moto est plus rapide d'un cran : +10. Fuyard 20 (majeure), flic 80 (raté).
    r = p.jouer_round(DesTruques(1, 20, 80))
    duel = r.duels[0]
    assert (duel.fuyard_test.valeur, duel.poursuivant_test.valeur) == (50, 70)
    assert (duel.gagnant, duel.crans) == ("Fuyard", 2)
    assert p.distances["flic"] == SEME and r.issue == "semé"
    with pytest.raises(PoursuiteImpossible, match="finie"):
        p.jouer_round(DesTruques())


def test_le_fuyard_change_de_zone_au_lieu_du_deuxieme_cran():
    p = poursuite()
    r = p.jouer_round(DesTruques(1, 20, 80), vers_zone="Banlieue")
    assert p.distances["flic"] == LOIN and p.zone == "Banlieue" and r.nouvelle_zone == "Banlieue"
    with pytest.raises(PoursuiteImpossible, match="seulement"):
        p.jouer_round(DesTruques(), vers_zone="Bas-quartiers")


def test_circulation_et_ligne_droite():
    p = poursuite()
    r = p.jouer_round(DesTruques(7, 90, 90))  # circulation : plus de vitesse, maniabilité doublée
    assert r.evenement is Evenement.CIRCULATION
    assert (r.duels[0].fuyard_test.valeur, r.duels[0].poursuivant_test.valeur) == (50, 70)
    assert p.distances["flic"] == PROCHE
    r = p.jouer_round(DesTruques(3, 90, 90))  # ligne droite : la vitesse compte double
    assert r.duels[0].poursuivant_test.valeur == 60 + 20


def test_obstacle_rate_un_cran_de_perdu():
    p = poursuite()
    r = p.jouer_round(DesTruques(8, 90, 10, 90, 90))
    assert [o.effet for o in r.obstacles] == ["perd un cran", "passe"]
    assert p.distances["flic"] == AU_CONTACT


def test_barrage_le_bloque_perd_sans_jet():
    p = poursuite()
    r = p.jouer_round(DesTruques(9, 90, 10))
    assert r.obstacles[0].test.valeur == 50 - 20  # difficile
    assert r.duels[0].fuyard_test is None and r.duels[0].gagnant == "Flic"
    assert p.distances["flic"] == AU_CONTACT


def test_maladresse_l_accident_et_le_fuyard_est_rattrape():
    p = poursuite()
    r = p.jouer_round(DesTruques(1, 100, 50, 1, 1, 1, 1, 1))
    assert r.accidents[0].vehicule == "Voiture" and r.accidents[0].structure_perdue == 3
    assert p.fuyard.pilote.fiche.pv == 8
    assert r.issue == "rattrapé" and p.distances["flic"] == AU_CONTACT


def test_un_vehicule_capricieux_cale():
    p = poursuite(fuyard_engin=replace(VOITURE, qualite=Qualite.USE, defaut="capricieux"))
    r = p.jouer_round(DesTruques(1, 100, 50))
    assert r.accidents == [] and "cale" in r.effets[0] and r.issue == "rattrapé"


def test_tous_les_quatre_rounds_la_zone_change():
    p = poursuite()
    for _ in range(3):
        assert p.jouer_round(DesTruques(1, 90, 90)).nouvelle_zone is None
    r = p.jouer_round(DesTruques(1, 90, 90, 2))
    assert r.nouvelle_zone == "Banlieue" and p.zone == "Banlieue" and p.rounds_dans_la_zone == 0


def test_la_nitro_une_fois_par_scene():
    p = poursuite(poursuivant_engin=replace(MOTO, modifications=(NITRO,)))
    r = p.jouer_round(DesTruques(1, 90, 90), nitro={"flic"})
    assert r.duels[0].poursuivant_test.valeur == 80
    with pytest.raises(PoursuiteImpossible, match="déjà brûlé"):
        p.jouer_round(DesTruques(1), nitro={"flic"})
    with pytest.raises(PoursuiteImpossible, match="pas de nitro"):
        poursuite().jouer_round(DesTruques(1), nitro={"fuyard"})


def test_a_pied_contre_une_voiture():
    p = poursuite(fuyard_engin=None, poursuivant_engin=VOITURE)
    r = p.jouer_round(DesTruques(1, 90, 90))
    assert r.duels[0].fuyard_test.valeur == 25  # l'Athlétisme du PNJ, sans rien
    assert r.duels[0].poursuivant_test.valeur == 50 + 30  # trois crans d'écart


def test_la_monture_panique():
    p = poursuite(fuyard_engin=CHEVAL)
    r = p.jouer_round(DesTruques(8, 10, 90, 10, 90, 90))
    assert [o.effet for o in r.obstacles] == ["passe", "la monture panique : perd un cran", "passe"]
    assert p.distances["flic"] == AU_CONTACT


def test_raccourci_et_coup_de_chance():
    p = poursuite(zone="Centre-ville")
    r = p.jouer_round(DesTruques(8, 10, 90, 90), raccourci=True)
    assert r.obstacles[0].effet == "raccourci : un cran de plus" and p.distances["flic"] == LOIN
    r = p.jouer_round(DesTruques(10, 90, 90))  # coup de chance : pour le flic, qui est en train de perdre
    assert r.duels[0].poursuivant_test.valeur == 70 + 10


# --- Par les outils du MJ ----------------------------------------------------------------------

def session_motarde(*des) -> Session:
    donnees = donnees_cyberpunk()
    donnees["vehicules"] = donnees.get("vehicules", []) + [
        {"nom": "Moto sportive", "type": "terrestre", "gabarit": "léger", "vitesse": "très rapide",
         "maniabilite": 10, "structure": 15, "blindage": 1, "places": 2},
        {"nom": "Berline", "type": "terrestre", "gabarit": "moyen", "vitesse": "rapide", "maniabilite": 0,
         "structure": 30, "blindage": 2, "places": 4},
    ]
    univers = univers_depuis_dict(donnees)
    assert univers.verifier() == []
    kaito = univers.creer_personnage("Netrunner", **fiche_kaito())
    return Session(univers, kaito, DesTruques(*des), vehicule="Moto sportive")


def test_une_poursuite_par_les_outils():
    s = session_motarde(1, 1, 90)
    assert "erreur" not in s.appeler("creer_pnj", {"identifiant": "flic", "nom": "Flic", "camp": "ennemis",
                                                   "combat": 45, "pv": 10, "vehicule": "Berline",
                                                   "competences": {"Conduite": 50}})
    noms = {x["function"]["name"] for x in s.schemas()}
    assert {"debut_poursuite", "piloter", "reparer"} <= noms and "round_poursuite" not in noms
    debut = s.appeler("debut_poursuite", {"fuyard": "joueur", "poursuivants": ["flic"], "zone": "Autoroute"})
    assert debut["vehicules"] == {"joueur": "Moto sportive", "flic": "Berline"}
    r = s.appeler("round_poursuite", {})
    assert r["evenement"] == "voie dégagée" and r["duels"][0]["gagnant"] == "Kaito" and r["issue"] == "semé"
    assert r["duels"][0]["jet_poursuivant"]["valeur"] == 50
    lignes = decrire("round_poursuite", {}, r, s)
    assert lignes[0] == "🏁 Round 1 de poursuite, Autoroute : voie dégagée" and "semé" in lignes[-1]
    assert s.appeler("etat")["poursuite"]["issue"] == "semé"
    s.appeler("fin_poursuite")
    assert s.poursuite is None


def test_accident_reparation_et_sauvegarde():
    s = session_motarde(100, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
    pv = s.personnage.pv
    r = s.appeler("piloter", {"difficulte": "difficile"})
    assert r["accident"]["structure_perdue"] == 4 and r["accident"]["occupants"][0]["degats"] == 4
    assert s.personnage.pv == pv - 4 and s.vehicule.structure == 11
    r = s.appeler("reparer", {"reparateur": "joueur", "atelier": True})
    assert r["structure_rendue"] == 4 and r["structure"] == 15
    assert "déjà" in s.appeler("reparer", {"reparateur": "joueur"})["erreur"]
    s.vehicule.structure = 9
    partie = partie_depuis_dict(partie_vers_dict(Partie(s.personnage, s.univers, s.moment,
                                                        vehicule=s.vehicule.vers_dict())))
    reprise = Session(partie.univers, partie.personnage, DesTruques(), partie.moment, vehicule=partie.vehicule)
    assert reprise.vehicule.structure == 9 and reprise.vehicule.derniere_reparation == s.moment
