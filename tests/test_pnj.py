"""Les PNJ tirés par le moteur (REGLES.md 15.2) : un rôle, une menace, et le code tire le reste."""

import pytest

from aria import noms, pnj
from aria.pnj import ELITE, FAIBLE, FORTE, MOYENNE, PnjImpossible
from aria.personnage import COMPETENCES_SOCLE
from aria.univers import charger_univers
from tests.test_monde import Imposes, petit
from tests.test_outils import session
from tests.test_univers import CYBERPUNK


def monde(genre: str = "Cyberpunk") -> dict:
    etat = petit()
    noms.installer(etat, genre, "Osaka")
    pnj.installer(etat, genre)
    return etat


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def test_la_bibliotheque_est_complete(u):
    assert pnj.verifier_tables() == []
    kaito = session().personnage
    assert pnj.verifier_tables(set(kaito.competences)) == []  # les rôles du Cyberpunk n'inventent aucune compétence
    generiques = {c for r in pnj.roles("Western").values() for c in r["competences"]}
    assert generiques <= set(COMPETENCES_SOCLE)  # les rôles génériques valent dans tous les genres


def test_les_roles_viennent_du_genre_sinon_du_generique():
    assert list(pnj.roles("Cyberpunk"))[:3] == ["passant", "commerçant", "voyou"]
    assert "homme de loi" in pnj.roles("Fantasy") and "policier" not in pnj.roles("Fantasy")
    assert pnj.actifs(monde()) and not pnj.actifs(petit()) and not pnj.actifs(None)


@pytest.mark.parametrize("menace, des, combat, pv", [
    (FAIBLE, (1, 1, 1), 22, 7), (FAIBLE, (10, 10, 6), 40, 12),
    (MOYENNE, (1, 1, 1), 42, 11), (MOYENNE, (10, 10, 6), 60, 16),
    (FORTE, (1, 1, 1), 57, 15), (FORTE, (10, 10, 8), 75, 22),
])
def test_la_menace_donne_les_chiffres(u, menace, des, combat, pv):
    p = pnj.tirer(monde(), Imposes(*des), u, "voyou", menace, ["exceptionnelle"])
    assert (p["combat"], p["pv"]) == (combat, pv)


def test_l_elite_ne_lance_qu_un_de_de_combat(u):
    etat = monde()
    assert pnj.tirer(etat, Imposes(1, 1), u, "tueur", ELITE, ["dangereuse"])["combat"] == 76
    haut = pnj.tirer(etat, Imposes(10, 10), u, "tueur", ELITE, ["dangereuse"])
    assert (haut["combat"], haut["pv"]) == (85, 30)


def test_le_role_donne_trois_competences_au_niveau_de_la_menace(u):
    p = pnj.tirer(monde(), Imposes(), u, "technicien", MOYENNE)
    assert p["competences"] == {"Technologie": 55, "Artisanat": 55, "Sécurité": 55}
    assert p["dexterite"] == 42 and (p["arme"], p["armure"]) == (None, None)
    assert p["caractere"] == "méfiant" and p["signe"] == "un œil cybernétique qui ne cligne pas"


def test_l_equipement_vient_de_l_armurerie(u):
    # combat ×2, pv, dextérité ×2, puis la classe d'arme, l'arme, l'armure
    soldat = pnj.tirer(monde(), Imposes(1, 1, 1, 1, 1, 1, 2, 1), u, "soldat de corpo", MOYENNE, ["risquée"])
    assert soldat["arme"] == pnj.armes_de_classe(u, pnj.LONGUE)[1].nom
    assert u.armure(soldat["armure"]).protection == 3
    voyou = pnj.tirer(monde(), Imposes(1, 1, 1, 1, 1, 2, 1), u, "voyou", FAIBLE)
    assert voyou["arme"] == pnj.armes_de_classe(u, pnj.POING)[0].nom and voyou["armure"] is None


def test_les_armes_tirees_sont_ordinaires(u):
    for classe in pnj.CLASSES_D_ARMES:
        armes = pnj.armes_de_classe(u, classe)
        assert armes and not any(a.fabricant or a.zone or a.montee or a.usage_unique for a in armes)
    assert {a.nom for a in pnj.armes_de_classe(u, pnj.POING)} >= {"Pistolet léger", "Pistolet lourd"}
    assert "Fusil d'assaut" in {a.nom for a in pnj.armes_de_classe(u, pnj.LONGUE)}
    assert "Mitrailleuse légère" not in {a.nom for a in pnj.armes_de_classe(u, pnj.LONGUE)}
    assert "Katana" in {a.nom for a in pnj.armes_de_classe(u, pnj.MELEE)}


@pytest.mark.parametrize("role, menace, dangers, morceau", [
    ("passant", MOYENNE, [], "faible au plus"),
    ("chef", MOYENNE, [], "forte au moins"),
    ("voyou", ELITE, [], "hors mission"),
    ("voyou", FORTE, ["simple"], "pour une mission de ce danger"),
    ("voyou", ELITE, ["risquée"], "forte au plus"),
    ("sorcier", FAIBLE, [], "n'existe pas"),
])
def test_ce_que_les_regles_refusent(u, role, menace, dangers, morceau):
    with pytest.raises(PnjImpossible, match=morceau):
        pnj.tirer(monde(), Imposes(), u, role, menace, dangers)


def test_le_plafond_suit_la_mission_la_plus_dangereuse():
    assert pnj.plafond([]) == FORTE
    assert pnj.plafond(["un service"]) == MOYENNE and pnj.plafond(["simple"]) == MOYENNE
    assert pnj.plafond(["risquée"]) == FORTE
    assert pnj.plafond(["simple", "dangereuse"]) == ELITE


# --- L'outil du MJ ----------------------------------------------------------------------------

def creer(s, identifiant="g", role="voyou", menace=MOYENNE, **plus):
    return s.appeler("creer_pnj", {"identifiant": identifiant, "sexe": "homme", "camp": "ennemis", "role": role,
                                   "menace": menace} | plus)


def des_libres(*valeurs):
    """Une session dont les dés donnent les valeurs imposées, puis des 1."""
    s = session(monde=monde())
    s.des = Imposes(*valeurs)
    return s


def test_creer_pnj_ne_prend_plus_de_chiffres():
    s = des_libres()
    schema = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert set(schema["properties"]) == {"identifiant", "sexe", "origine", "faction", "camp", "role", "menace", "vehicule"}
    assert schema["required"] == ["identifiant", "camp", "role", "menace"]
    assert "Paramètre inconnu" in creer(s, combat=85)["erreur"]
    r = creer(s)
    assert (r["combat"], r["pv"], r["role"], r["menace"]) == (42, 11, "voyou", MOYENNE)
    assert r["competences"] == {"Intimidation": 55, "Infiltration": 55, "Doigts agiles": 55}  # les noms de l'univers
    assert r["nom"] == "Haruto Sato" and r["caractere"] and r["signe"] and r["arme"]
    fiche = s.pnj["g"].fiche
    assert (fiche.combat, fiche.pv_max, fiche.competences["Discrétion"]) == (42, 11, 55)


def test_la_mission_en_cours_plafonne_la_menace():
    s = des_libres()
    assert "hors mission" in creer(s, menace=ELITE, role="tueur")["erreur"]
    s.personnage.missions["vol"] = {"recompense": 500, "avance": 0, "danger": "simple"}
    assert "pour une mission de ce danger" in creer(s, menace=FORTE)["erreur"]
    s.personnage.missions["raid"] = {"recompense": 0, "avance": 0, "offre": {"danger": "dangereuse"}}  # une offre du moteur
    assert creer(s, menace=ELITE, role="tueur")["menace"] == ELITE


def test_un_seul_pnj_d_elite_par_scene():
    s = des_libres()
    s.personnage.missions["raid"] = {"recompense": 5000, "avance": 0, "danger": "dangereuse"}
    assert "erreur" not in creer(s, "a", "tueur", ELITE)
    assert "Un seul PNJ d'élite par scène" in creer(s, "b", "tueur", ELITE)["erreur"]
    assert "erreur" not in s.appeler("fin_scene", {"titre": "Le raid", "moments_forts": "Le tueur a fui par les toits."})
    assert "erreur" not in creer(s, "b", "tueur", ELITE)


def test_une_campagne_d_avant_garde_les_chiffres_libres():
    s = session()
    schema = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert "combat" in schema["required"] and "role" not in schema["properties"]
    r = s.appeler("creer_pnj", {"identifiant": "g", "nom": "Ganger", "camp": "ennemis", "combat": 45, "pv": 10})
    assert r["pv"] == 10 and "role" not in r
    assert "combat" in s.appeler("creer_pnj", {"identifiant": "h", "nom": "X", "camp": "ennemis"})["erreur"]
