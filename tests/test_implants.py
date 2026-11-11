"""Les implants (REGLES.md 11) : fondations, emplacements, prix en Santé mentale, bonus et armures."""

import json

import pytest

from aria import chemins
from aria.banc import FICHE_KAITO
from aria.des import DesTruques
from aria.implants import ImplantImpossible, poser
from aria.outils import Session
from aria.univers import univers_depuis_dict


def neo_tokyo_chrome():
    """Néo-Tokyo, avec le catalogue d'implants de la bibliothèque."""
    donnees = json.loads((chemins.UNIVERS / "cyberpunk.json").read_text(encoding="utf-8"))
    catalogue = json.loads((chemins.RESSOURCES / "bibliotheque" / "implants.json").read_text(encoding="utf-8"))
    donnees["implants"] = {"systemes": catalogue["systemes"],
                           "implants": [{k: v for k, v in i.items() if k != "genres"} for i in catalogue["implants"]]}
    return univers_depuis_dict(donnees)


UNIVERS = neo_tokyo_chrome()


def session(*des: int) -> Session:
    kaito = UNIVERS.creer_personnage("Netrunner", **FICHE_KAITO)
    s = Session(UNIVERS, kaito, DesTruques(*des), arme="Pistolet lourd Arasaka", armure="Veste renforcée")
    s.appeler("creer_pnj", {"identifiant": "doc", "nom": "Doc Mori", "camp": "neutres", "combat": 30, "pv": 10,
                            "competences": {"Médecine": 70}})
    return s


def poser_direct(s: Session, nom: str, cote=None, qualite="d'origine"):
    """Une pose réussie à coup sûr (01), pour tester les règles sans les dés."""
    s.des = DesTruques(1)
    return poser(s.des, s.combattant("doc").fiche, s.personnage, s.corps(), UNIVERS.implant(nom), qualite, cote)


def test_le_catalogue_est_valide():
    assert UNIVERS.verifier() == [] and len(UNIVERS.implants) > 50


def test_une_option_demande_sa_fondation():
    s = session()
    with pytest.raises(ImplantImpossible, match="fondation"):
        poser_direct(s, "Lames-mantis", "gauche")
    poser_direct(s, "Bras cybernétique", "gauche")
    poser_direct(s, "Lames-mantis", "gauche")
    with pytest.raises(ImplantImpossible, match="fondation"):
        poser_direct(s, "Lames-mantis", "droit")  # pas de bras cybernétique à droite
    with pytest.raises(ImplantImpossible, match="côté"):
        poser_direct(s, "Bras cybernétique")


def test_une_fondation_a_un_nombre_d_options():
    s = session()
    poser_direct(s, "Bras cybernétique", "gauche")
    for option in ("Lames-mantis", "Pistolet intégré", "Lance-grappin"):
        poser_direct(s, option, "gauche")
    with pytest.raises(ImplantImpossible, match="plus d'emplacement"):
        poser_direct(s, "Servomoteurs", "gauche")


def test_un_seul_systeme_d_exploitation():
    s = session()
    poser_direct(s, "Sandevistan")
    with pytest.raises(ImplantImpossible, match="Un seul système d'exploitation"):
        poser_direct(s, "Berserk")


def test_le_cortex_demande_un_neuroport():
    s = session()
    with pytest.raises(ImplantImpossible, match="neuroport"):
        poser_direct(s, "Mémoire eidétique")
    poser_direct(s, "Neuroport")
    poser_direct(s, "Mémoire eidétique")


def test_le_prix_en_sante_mentale():
    s = session()
    assert s.personnage.sm_max == 50
    poser_direct(s, "Yeux cybernétiques")  # standard : 2
    poser_direct(s, "Optiques Kiroshi")  # militaire : 6
    poser_direct(s, "Tatouages lumineux")  # esthétique : 0
    assert s.personnage.sm_max == 42 and s.personnage.sm == 42
    poser_direct(s, "Peau dermique", qualite="usé")  # standard usé : 2 + 2
    assert s.personnage.sm_max == 38


def test_les_bonus_ne_se_cumulent_pas():
    s = session()
    base = s.personnage.valeur("Armes à distance")
    poser_direct(s, "Yeux cybernétiques")
    poser_direct(s, "Viseur balistique")
    assert s.personnage.valeur("Armes à distance") == base + 5
    poser_direct(s, "Optiques Kiroshi")
    assert s.personnage.valeur("Armes à distance") == base + 10  # le meilleur, pas +15


def test_l_armure_implantee_ne_se_cumule_pas():
    s = session()
    assert s.joueur.protection == 1  # la veste renforcée
    s.des = DesTruques(30)
    r = s.appeler("poser_implant", {"implant": "Ossature blindée", "charcudoc": "doc"})
    assert r["pose"] and s.joueur.protection == 3  # la meilleure des deux, pas 4
    assert s.joueur.valeur("Discrétion") == s.personnage.valeur("Discrétion") - 10  # son malus compte


def test_une_arme_implantee_se_degaine():
    s = session()
    poser_direct(s, "Bras cybernétique", "droit")
    poser_direct(s, "Lames-mantis", "droit")
    assert "Lames-mantis" in {a.nom for a in s.armes_du_joueur()}


def test_l_outil_et_un_echec():
    s = session(95)
    r = s.appeler("poser_implant", {"implant": "Neuroport", "charcudoc": "doc"})
    assert not r["pose"] and s.personnage.implants == [] and s.personnage.sm_max == 50
    assert "poser_implant" in {o["function"]["name"] for o in s.schemas()}


def test_pas_d_implant_en_combat():
    s = session()
    s.appeler("creer_pnj", {"identifiant": "ganger", "nom": "Ganger", "camp": "ennemis", "combat": 40, "pv": 10})
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert "erreur" in s.appeler("poser_implant", {"implant": "Neuroport", "charcudoc": "doc"})
