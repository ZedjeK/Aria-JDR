"""Les calibres : une étiquette par arme à feu, choisie selon l'époque du cadre (REGLES.md 7.5)."""

import copy
from dataclasses import replace

import pytest

from aria.bibliotheque import charger
from aria.campagne import Campagne
from aria.combat import Combattant, FichePnj
from aria.equipement import ARMES_A_DISTANCE, Arme, Munitions, Portee, Recharge
from aria.generateur import (
    Adaptation,
    adapter,
    appliquer,
    calibres_par_epoque,
    choix_par_defaut,
    creer_campagne,
    generer,
)
from aria.outils import _etat_combattant
from aria.univers import univers_depuis_dict, univers_vers_dict
from test_table import ServeurScripte


@pytest.fixture(scope="module")
def bibliotheque():
    return charger()


@pytest.fixture(scope="module")
def horreur(bibliotheque):
    return generer(bibliotheque, choix_par_defaut(bibliotheque, "Horreur", "Arkham", "Arkham."))


@pytest.mark.parametrize(
    "annee, arme, calibre",
    [
        (1925, "Pistolet lourd", ".45 ACP"),
        (1925, "Pistolet-mitrailleur", ".45 ACP"),  # la Thompson
        (1925, "Mitrailleuse lourde", ".50 BMG"),
        (1968, "Fusil d'assaut", "5,56 mm"),  # le M16
        (1968, "Pistolet lourd", ".44 Magnum"),
        (None, "Pistolet lourd", ".50 AE"),  # sans année : le plus récent
        (1925, "Fusil à pompe", "calibre 12"),
    ],
)
def test_le_calibre_de_l_epoque(horreur, annee, arme, calibre):
    assert calibres_par_epoque(horreur, annee)[arme] == calibre


def test_les_armes_sans_calibre(horreur):
    choisis = calibres_par_epoque(horreur, 2000)
    assert "Lance-roquettes" not in choisis and "Couteau" not in choisis and "Grenade à fragmentation" not in choisis


def test_appliquer_pose_le_calibre_et_suit_le_renommage(horreur):
    a = Adaptation("Arkham", "1925", 1925, calibres=calibres_par_epoque(horreur, 1925),
                   renommages={"armes": {"Pistolet lourd": "Colt .45"}})
    d = appliquer(horreur, a)
    colt = next(x for x in d["armes"] if x["nom"] == "Colt .45")
    assert colt["calibre"] == ".45 ACP" and "calibres" not in colt
    u = univers_depuis_dict(d)
    assert u.arme("Colt .45").calibre == ".45 ACP" and u.arme("Couteau").calibre is None
    assert univers_vers_dict(u)["armes"][[x.nom for x in u.armes].index("Colt .45")]["calibre"] == ".45 ACP"


def test_une_campagne_sans_llm_prend_les_calibres_de_son_annee(tmp_path, bibliotheque):
    choix = choix_par_defaut(bibliotheque, "Horreur", "Arkham 1925", "Arkham, 1925.", 1925)
    u, adaptation = creer_campagne(Campagne(tmp_path), choix, bibliotheque)
    assert adaptation is None and u.arme("Pistolet lourd").calibre == ".45 ACP"


def test_le_llm_voit_le_calibre_quand_il_renomme(bibliotheque, horreur):
    choix = choix_par_defaut(bibliotheque, "Horreur", "Arkham 1925", "Arkham, 1925.", 1925)
    serveur = ServeurScripte()  # muet : on ne regarde que ce qu'on lui demande
    adapter(serveur, horreur, choix)
    demandes = [messages[-1]["content"] for messages, _ in serveur.recus]
    armes = next(t for t in demandes if t.startswith("Voici les armes de l'univers. Appelle renommer"))
    assert "- Pistolet lourd (.45 ACP)" in armes and "- Couteau\n" in armes


def test_la_bibliotheque_verifie_les_calibres(bibliotheque):
    armes = copy.deepcopy(bibliotheque.armes)
    lourd = next(a for a in armes if a["nom"] == "Pistolet lourd")
    lourd["calibres"] = list(reversed(lourd["calibres"]))
    compact = next(a for a in armes if a["nom"] == "Pistolet compact")
    compact["calibres"] = [{"nom": ".25 ACP", "apparition": 1950}]
    revolver = next(a for a in armes if a["nom"] == "Revolver lourd")
    revolver["calibres"] = [{"nom": "", "apparition": 1850}]
    erreurs = replace(bibliotheque, armes=armes).verifier()
    assert any("Pistolet lourd : les calibres se rangent" in e for e in erreurs)
    assert any("Pistolet compact (1906) n'a aucun calibre" in e for e in erreurs)
    assert any("Revolver lourd : chaque calibre a un nom" in e for e in erreurs)


def test_l_etat_montre_le_calibre():
    colt = Arme("Colt .45", ARMES_A_DISTANCE, "1d10", Portee.COURTE, munitions=Munitions(7, Recharge.MINEURE),
                calibre=".45 ACP")
    etat = _etat_combattant(Combattant(FichePnj("Malfrat", combat=40, pv_max_base=10), "ennemis", colt))
    assert etat["calibre"] == ".45 ACP"
