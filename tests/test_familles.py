"""Les familles d'outils du MJ (aria.familles) : le socle, ce que le moteur ouvre seul, ce que le MJ ouvre."""

from aria import familles
from aria.banc import SITUATIONS, nouvelle_session
from aria.outils import OUTILS

CYBERPUNK = next(s.univers for s in SITUATIONS if s.nom == "racket")
SOCLE = {"etat", "monde", "inventaire", "test_competence", "test_caracteristique", "forcer_jet", "attaquer",
         "creer_pnj", "noter_pnj", "debut_combat", "embuscade", "avancer_temps", "fin_scene", "ouvrir_fil",
         "clore_fil", "jalon", "point_de_destin", "fouiller", "prendre"}


def session(allumees: bool = True):
    s = nouvelle_session(1, CYBERPUNK)
    s.familles = allumees
    return s


def noms(s) -> set[str]:
    return {o["function"]["name"] for o in s.schemas()}


def ganger(s):
    assert "erreur" not in s.appeler("creer_pnj", {"identifiant": "ganger", "nom": "Ganger", "camp": "ennemis",
                                                  "combat": 40, "pv": 10})


def test_chaque_outil_a_sa_place():
    ranges = [nom for outils, _ in familles.FAMILLES.values() for nom in outils]
    assert len(ranges) == len(set(ranges)) == 35 and set(ranges) <= set(OUTILS)
    assert set(OUTILS) - set(ranges) == SOCLE | {"outils"}  # le socle : 19 outils, plus celui qui ouvre les familles
    assert familles.famille_de("acheter") == familles.COMMERCE and familles.famille_de("etat") is None


def test_eteintes_rien_ne_change():
    s = session(allumees=False)
    assert noms(s) == {nom for nom, o in OUTILS.items() if o.disponible(s)} and "outils" not in noms(s)
    assert s.familles_fermees() == [] and "voir_boutique" in noms(s)
    r = s.appeler("voir_boutique", {"vendeur": "armurier"})
    assert "erreur" not in r and "famille_ouverte" not in r and s.ouvertes == []


def test_allumees_le_mj_n_a_que_le_socle():
    s = session()
    assert noms(s) <= SOCLE | {"outils"} and {"etat", "test_competence", "creer_pnj", "fin_scene", "outils"} <= noms(s)
    schema = next(o for o in s.schemas() if o["function"]["name"] == "outils")["function"]["parameters"]
    assert schema["properties"]["famille"]["enum"] == s.familles_fermees()
    assert familles.COMMERCE in s.familles_fermees() and familles.SOINS in s.familles_fermees()
    assert familles.MAGIE not in s.familles_fermees()  # Kaito n'a pas la magie : rien à ouvrir
    assert s.familles_ouvertes() == []


def test_le_mj_ouvre_une_famille():
    s = session()
    r = s.appeler("outils", {"famille": familles.COMMERCE})
    assert r["famille_ouverte"] == familles.COMMERCE and "acheter" in r["outils"] and "famille_refermee" not in r
    assert {"acheter", "vendre", "payer", "voir_boutique"} <= noms(s) and "soigner" not in noms(s)
    assert familles.COMMERCE not in s.familles_fermees() and s.familles_ouvertes() == [familles.COMMERCE]
    # Une famille déjà ouverte n'est plus proposée
    assert "erreur" in s.appeler("outils", {"famille": familles.COMMERCE})


def test_deux_familles_au_plus_la_troisieme_referme_la_plus_ancienne():
    s = session()
    s.appeler("outils", {"famille": familles.COMMERCE})
    s.appeler("outils", {"famille": familles.SOINS})
    r = s.appeler("outils", {"famille": familles.POURSUITE})
    assert r["famille_refermee"] == familles.COMMERCE
    assert s.ouvertes == [familles.SOINS, familles.POURSUITE] and "acheter" not in noms(s) and "soigner" in noms(s)


def test_le_moteur_est_indulgent_un_outil_d_une_famille_fermee_l_ouvre():
    s = session()
    r = s.appeler("voir_boutique", {"vendeur": "armurier"})  # le MJ s'en souvient et l'appelle directement
    assert "stock" in r and r["famille_ouverte"] == familles.COMMERCE and s.ouvertes == [familles.COMMERCE]
    # Des arguments faux : l'erreur habituelle, et la famille reste ouverte pour qu'il recommence
    r = s.appeler("soigner", {"n_importe_quoi": 1})
    assert "erreur" in r and r["famille_ouverte"] == familles.SOINS and "soigner" in noms(s)
    # Un outil qui n'existe pas reste inconnu, et la liste ne montre que ce qu'il a sous la main
    r = s.appeler("teleporter", {})
    assert "Outil inconnu" in r["erreur"] and "famille_ouverte" not in r and "'niveau_de_vie'" in r["erreur"]


def test_le_moteur_ouvre_seul_ce_que_l_etat_impose():
    s = session()
    assert s.familles_imposees() == set()
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert familles.COMBAT in s.familles_imposees() and {"action_combat", "fin_de_tour", "fin_combat"} <= noms(s)
    assert s.ouvertes == [] and s.familles_ouvertes() == [familles.COMBAT]
    # En plein combat, le commerce ne sert pas : le MJ ne peut pas l'ouvrir, et l'appeler reste refusé
    assert familles.COMMERCE not in s.familles_fermees()
    for outil, arguments in (("acheter", {"objet": "Katana"}), ("poser_implant", {"implant": "Neuroport",
                                                                               "charcudoc": "ganger"})):
        r = s.appeler(outil, arguments)
        assert "erreur" in r and "famille_ouverte" not in r and s.ouvertes == [] and outil not in noms(s)
    s.combat = None
    assert familles.COMBAT not in s.familles_imposees() and "fin_de_tour" not in noms(s)


def test_blesse_en_mission_ou_fou_les_familles_s_ouvrent_seules():
    s = session()
    s.personnage.pv -= 3
    assert s.familles_imposees() == {familles.SOINS} and "soigner" in noms(s)
    s.personnage.pv = s.personnage.pv_max
    assert s.familles_imposees() == set()
    s.personnage.folie = True
    assert familles.SOINS in s.familles_imposees()
    s.personnage.folie = False
    s.personnage.missions["extraction"] = {"recompense": 500, "avance": 0, "danger": "simple"}
    assert s.familles_imposees() == {familles.MISSIONS} and "ouvrir_mission" in noms(s)
    # Une famille imposée ne compte pas dans les deux du MJ, et l'ouvrir ne change rien
    assert s.ouvrir_famille(familles.MISSIONS) is None and s.ouvertes == []


def test_un_allie_blesse_ouvre_les_soins_pas_un_ennemi():
    s = session()
    ganger(s)
    s.pnj["ganger"].fiche.pv -= 2
    assert familles.SOINS not in s.familles_imposees()
    s.appeler("creer_pnj", {"identifiant": "hana", "nom": "Hana", "camp": "allies", "combat": 30, "pv": 8})
    s.pnj["hana"].fiche.pv -= 2
    assert familles.SOINS in s.familles_imposees()


def test_la_fin_de_scene_referme_ce_que_le_mj_a_ouvert():
    s = session()
    s.appeler("outils", {"famille": familles.COMMERCE})
    r = s.appeler("fin_scene", {"titre": "Au marché", "moments_forts": "Kaito a regardé les étals."})
    assert "erreur" not in r and s.ouvertes == [] and "acheter" not in noms(s)
