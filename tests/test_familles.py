"""Les familles d'outils du MJ (aria.familles) : le socle, ce que le moteur ouvre seul, ce que le MJ ouvre."""

import itertools
import json

from aria import familles, llm, table
from aria.banc import SITUATIONS, nouvelle_session
from aria.outils import OUTILS

CYBERPUNK = next(s.univers for s in SITUATIONS if s.nom == "racket")
SOCLE = {"etat", "monde", "inventaire", "test_competence", "test_caracteristique", "forcer_jet", "attaquer",
         "creer_pnj", "noter_pnj", "debut_combat", "embuscade", "avancer_temps", "fin_scene", "ouvrir_fil",
         "clore_fil", "jalon", "point_de_destin", "fouiller", "prendre", "choc"}


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
    assert len(ranges) == len(set(ranges)) == 34 and set(ranges) <= set(OUTILS)
    assert set(OUTILS) - set(ranges) == SOCLE | {"outils"}  # le socle : 20 outils, plus celui qui ouvre les familles
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


def test_la_section_du_prompt_suit_les_familles():
    from aria.table import Table
    s = session()
    prompt = Table(None, s, 512, "Une ruelle.").messages[0]["content"]
    assert "## Tes outils" in prompt and "Ouvertes : aucune pour l'instant." in prompt
    assert "- commerce : voir une boutique, acheter" in prompt and "- magie" not in prompt
    s.appeler("outils", {"famille": familles.COMMERCE})
    prompt = Table(None, s, 512, "Une ruelle.").messages[0]["content"]
    assert "Ouvertes : commerce." in prompt and "- commerce :" not in prompt and "- soins et santé mentale :" in prompt
    # Éteintes : le prompt d'avant, sans la section
    assert "## Tes outils" not in Table(None, session(allumees=False), 512, "Une ruelle.").messages[0]["content"]


def test_le_banc_joue_avec_les_familles():
    for situation in SITUATIONS:
        s = nouvelle_session(1, situation.univers)
        if situation.preparer:
            situation.preparer(s)
        assert s.familles and not [j for j in s.journal if "erreur" in j["resultat"]], situation.nom
    troisieme = next(x for x in SITUATIONS if x.nom == "troisieme")
    s = nouvelle_session(1, troisieme.univers)
    troisieme.preparer(s)
    assert s.ouvertes == [familles.COMMERCE, familles.SOINS] and familles.POURSUITE in s.familles_fermees()
    r = s.appeler("outils", {"famille": familles.POURSUITE})
    assert r["famille_refermee"] == familles.COMMERCE and "debut_poursuite" in r["outils"]


# La place : le contexte de 16 384 jetons moins la réponse (PLAFOND_JETONS) et la réserve d'un tour. Le prompt de base
# (système + schémas d'outils) en prend une part, l'historique des échanges garde le reste. Mesuré le 2026-11-15
# (3,37 caractères par jeton) : socle seul 6 800 jetons, deux familles du MJ de 7 400 à 10 000, éteint 10 700.
CARACTERES_PAR_JETON = 3.37
LIMITE = 16384 - llm.PLAFOND_JETONS - table.RESERVE_TOUR
ECHANGE = 500  # un échange moyen : phrase du joueur, deux appels d'outils avec leurs résultats, 150 jetons de narration


def base(s) -> int:
    systeme = table.Table(None, s, 512, "Une ruelle.").messages[0]["content"]
    return int((len(systeme) + len(json.dumps(s.schemas(), ensure_ascii=False))) / CARACTERES_PAR_JETON)


def test_le_socle_laisse_la_place_a_au_moins_six_echanges():
    assert (LIMITE - base(session())) // ECHANGE >= 6  # avant les familles : 195 jetons, un seul échange gardé


def test_deux_familles_du_mj_laissent_la_place_a_au_moins_un_echange():
    # La pire paire, combat et commerce (9 980 jetons), n'en laisse qu'un ; les autres en laissent de 3 à 7. Elle ne se
    # rencontre guère : dès que le combat est imposé, le commerce se ferme.
    for a, b in itertools.combinations(session().familles_fermees(), 2):
        s = session()
        s.appeler("outils", {"famille": a})
        s.appeler("outils", {"famille": b})
        assert (LIMITE - base(s)) // ECHANGE >= 1, (a, b)


def test_la_table_garde_une_dizaine_d_echanges_avec_le_socle():
    class Faux:
        def discuter(self, messages, schemas, budget):
            taille = len(json.dumps(messages, ensure_ascii=False)) + len(json.dumps(schemas or [], ensure_ascii=False))
            if messages[-1]["role"] == "user":
                appel = {"name": "test_competence", "arguments": json.dumps({
                    "competence": "Discrétion", "difficulte": "normale", "pourquoi": "Kaito se glisse entre les bennes."})}
                message = {"role": "assistant", "content": "", "tool_calls": [{"id": f"c{len(messages)}", "function": appel}]}
            else:
                message = {"role": "assistant", "content": "Le néon grésille sous la pluie acide. " * 15}
            return {"choices": [{"message": message}],
                    "usage": {"prompt_tokens": int(taille / CARACTERES_PAR_JETON), "completion_tokens": 150}}

    s = session()
    t = table.Table(Faux(), s, 512, "Une ruelle.")
    for _ in range(20):
        t.tour("Je me glisse derrière les bennes pour voir la patrouille.")
    assert sum(1 for m in t.messages if m["role"] == "user") >= 6
