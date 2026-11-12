"""La fin d'une campagne (REGLES.md 14.11) : les atouts, les fins, l'épilogue, et ce qui vient après."""

import random

import pytest

from aria import jeu, missions, monde, personnages, trame
from aria.campagne import Campagne
from aria.compte_rendu import decrire_monde
from aria.monde import AMI, MEMBRE, RECHERCHE
from aria.personnage import AGUERRI, DEBUTANT, Etat, VETERAN
from aria.univers import charger_univers
from test_amorce import appel, generation, nouvelle_partie
from test_commerce import riche
from test_creation import personnalite
from test_table import ServeurScripte
from tests.test_monde import Imposes
from tests.test_trame_campagne import SECRET, avec_trame, joue
from tests.test_univers import CYBERPUNK


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def finie(type_="standard", reussies=8, ratees=0, finale=True) -> dict:
    """Une trame dont la finale vient d'être jouée."""
    e = avec_trame(type_)
    e["trame"] |= {"acte": trame.nombre_d_actes(e["trame"]), "reussies": reussies, "ratees": ratees,
                   "fin": {"finale_reussie": finale, "jour": 30}}
    return e


# --- Les fins -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("reussies, finale, fin", [
    (8, True, "triomphe"), (6, True, "triomphe"), (5, True, "victoire amère"), (1, True, "victoire amère"),
    (4, False, "défaite honorable"), (7, False, "défaite honorable"), (3, False, "chute"), (0, False, "chute")])
def test_les_quatre_fins(reussies, finale, fin):
    assert trame.nom_de_la_fin(finie(reussies=reussies, ratees=8 - reussies, finale=finale)["trame"]) == fin


def test_un_contrat_est_reussi_ou_rate_et_la_mort_est_une_fin():
    assert trame.nom_de_la_fin(finie("contrat", 1, 0, True)["trame"]) == "contrat réussi"
    assert trame.nom_de_la_fin(finie("contrat", 0, 1, False)["trame"]) == "contrat raté"
    e = avec_trame()
    faits = trame.mourir(e, 12)
    assert faits["fin"] == "mort" and e["trame"]["fin"] == {"finale_reussie": False, "jour": 12, "mort": True,
                                                            "nom": "mort"}
    assert trame.finie(e["trame"]) and faits["secret_entier"] == SECRET


# --- Les atouts -----------------------------------------------------------------------------------------

def test_les_trois_atouts():
    e = avec_trame("contrat")  # un indice par couche : le quatrième est en trop
    assert trame.atouts(e, "D") == []  # sans rien : il y va à la dure
    for n in range(4):
        trame.noter_un_indice(e["trame"], 1, f"Indice {n}.")
    e["reputation"] |= {"Rats": AMI}
    gagnes = trame.atouts(e, "B")  # B est aux Rats, ses amis
    assert [a["atout"] for a in gagnes] == [trame.FAIBLESSE, trame.RENFORTS, trame.ENTREE_SURE]
    assert gagnes[1]["faction"] == "Rats" and "surpris" in gagnes[2]["effet"]
    assert [a["atout"] for a in trame.atouts(e, "D")] == [trame.FAIBLESSE, trame.RENFORTS]  # D est à l'antagoniste
    e["reputation"] |= {"Helix": MEMBRE, "Rats": "neutre"}
    assert [a["atout"] for a in trame.atouts(e, "D")] == [trame.FAIBLESSE]  # l'antagoniste n'est pas un ami qui compte


def test_la_menace_de_la_finale_suit_l_experience_de_depart():
    def menace(cran, affaiblie=False):
        return trame.menace_finale({"cran": cran}, affaiblie)
    assert [menace(c) for c in (DEBUTANT, AGUERRI, VETERAN)] == [("moyenne", 55), ("forte", 70), ("élite", 80)]
    assert menace(VETERAN, affaiblie=True) == ("forte", 70) and menace(DEBUTANT, affaiblie=True) == ("faible", 40)


# --- Ce que la fin change -------------------------------------------------------------------------------

def test_une_victoire_fait_ceder_l_antagoniste():
    e = finie()
    e["quartiers"]["C"] |= {"maitre": "Helix", "controle": 2}  # Helix tient C (2 points) et D (7 points)
    e["factions"]["Helix"]["rivale"] = "Rats"  # C touche B, aux Rats : il peut tomber de leur côté
    faits = trame.finir(e, Imposes(), 30)
    assert faits["fin"] == "triomphe" and faits["carte"] == ["C passe à Rats"]
    assert (e["quartiers"]["C"]["maitre"], e["quartiers"]["C"]["controle"]) == ("Rats", 5)
    assert (e["quartiers"]["D"]["maitre"], e["quartiers"]["D"]["controle"]) == ("Helix", 4)
    assert "Coup dur pour Helix" in e["journal"][-1]["texte"] and e["trame"]["fin"]["nom"] == "triomphe"
    e = finie()
    e["quartiers"]["D"]["controle"] = 2  # sans voisin hostile, un quartier ne tombe pas : il reste à 1
    trame.finir(e, Imposes(), 30)
    assert (e["quartiers"]["D"]["maitre"], e["quartiers"]["D"]["controle"]) == ("Helix", 1)


def test_une_defaite_renforce_l_antagoniste():
    e = finie(reussies=2, ratees=6, finale=False)
    e["quartiers"]["D"]["controle"] = 9
    faits = trame.finir(e, Imposes(), 30)
    assert faits["fin"] == "chute" and faits["carte"] == ["Helix : il y est maintenant recherché"]
    assert e["quartiers"]["D"]["controle"] == 10 and e["reputation"]["Helix"] == RECHERCHE
    assert "Victoire de Helix" in e["journal"][-1]["texte"]


def test_les_faits_de_l_epilogue_disent_tout():
    e = finie(reussies=5, ratees=3)
    e["trame"]["cicatrices"] = [{"jour": 9, "nature": "une dette"}]
    e["reputation"] |= {"Rats": AMI}
    faits = trame.faits_de_fin(e)
    assert faits["fin"] == "victoire amère" and faits["missions_principales"] == "5 réussies sur 8"
    assert faits["secret_entier"] == SECRET and faits["cicatrices"] == ["une dette"]
    assert faits["reputation"] == {"Rats": AMI} and faits["districts"] == {"Nord": "Rats", "Sud": "Helix"}
    assert "sans en changer aucun" in faits["consigne"] and "Helix ; derrière, le chef en personne" in faits["antagoniste"]
    assert "quelques lignes" in trame.faits_de_fin(finie("contrat", 1, 0))["consigne"]


# --- Et après -------------------------------------------------------------------------------------------

def test_arreter_ou_continuer():
    e = finie()
    assert not trame.suite_decidee(e["trame"]) and not trame.arretee(e)
    assert trame.decider_la_suite(e, Imposes(), 30, continuer=False) == trame.ARRET
    assert trame.arretee(e) and trame.suite_decidee(e["trame"]) and not trame.arretee(None)
    e = finie()
    ancienne = e["trame"]
    assert trame.decider_la_suite(e, Imposes(1, 1, 1, 1, 2, 7), 30, continuer=True) == trame.SUITE
    nouvelle = e["trame"]
    assert nouvelle is not ancienne and e["trames_passees"] == [ancienne] and ancienne["apres"] == trame.SUITE
    assert nouvelle["antagoniste"] == "Rats" and nouvelle["antagoniste"] != ancienne["antagoniste"]
    assert nouvelle["prochaine"] == 30 + 7 + 10 and nouvelle["acte"] == 1 and not trame.finie(nouvelle)
    assert missions.tenir_la_trame(e, Imposes(), 46) is None
    assert missions.tenir_la_trame(e, Imposes(), 47)["cible"] == "Rats"  # la nouvelle trame a sa première mission


def test_garder_le_personnage_d_une_campagne_finie(u, tmp_path, monkeypatch):
    monkeypatch.setattr("aria.chemins.DONNEES", tmp_path)
    s, _ = riche(u, 0)
    p = s.personnage
    garde = personnages.garder(p, u, AGUERRI, random.Random(1))
    assert garde.cran == AGUERRI and garde.nom == p.nom and garde.parcours == p.parcours and garde.genre == "Cyberpunk"
    assert garde.fichier.is_file() and sum(garde.fiche["points_personnels"].values()) == 200
    assert garde in [x for x in personnages.lister("Cyberpunk") if x.fichier]
    p.parcours = "Veilleur d'Osaka"  # un métier qui n'existe que dans le cadre de sa campagne
    assert personnages.garder(p, u, AGUERRI) is None


# --- Par les outils du MJ -------------------------------------------------------------------------------

def test_la_mission_finale_par_les_outils(u):
    s, _ = riche(u, 0, des=Imposes())
    s.monde = avec_trame("contrat")
    s.monde["reputation"] |= {"Rats": AMI}
    offre = next(o for o in s.appeler("monde")["offres_de_mission"] if "mission_principale" in o)
    r = s.appeler("accepter_mission", {"offre": offre["id"]})
    assert r["mission_principale"] == "la mission finale de la campagne"
    assert [a["atout"] for a in r["atouts"]] == [trame.RENFORTS] and r["atouts"][0]["pnj"] == "allie_finale"
    assert s.pnj["allie_finale"].camp == "allies" and s.pnj["allie_finale"].nom == "Un allié de Rats"
    assert r["hommes_de_l_antagoniste"] == "menace moyenne : combat 55 (creer_pnj)"
    assert decrire_monde("accepter_mission", {}, r)[0] == "🃏 Atout : des renforts."
    assert s.personnage.missions[offre["id"]]["offre"]["atouts"] == [trame.RENFORTS]
    r = s.appeler("clore_fil", {"identifiant": offre["id"], "issue": "Helix cède.", "reussie": True})
    fin = r["trame"]["fin_de_la_campagne"]
    assert fin["fin"] == "contrat réussi" and fin["secret_entier"] == SECRET and trame.finie(s.monde["trame"])
    assert decrire_monde("clore_fil", {}, r)[-1] == "🏁 Fin de la campagne : contrat réussi."
    assert "indice" not in {o["function"]["name"] for o in s.schemas()}  # la trame est finie


def test_sans_atout_il_y_va_sans_rien(u):
    s, _ = riche(u, 0, des=Imposes())
    s.monde = avec_trame("contrat", cran=VETERAN)
    offre = next(o for o in s.appeler("monde")["offres_de_mission"] if "mission_principale" in o)
    r = s.appeler("accepter_mission", {"offre": offre["id"]})
    assert r["atouts"] == "aucun : il y va sans rien" and "menace élite : combat 80" in r["hommes_de_l_antagoniste"]
    assert "allie_finale" not in s.pnj and decrire_monde("accepter_mission", {}, r)[0].startswith("📜")


# --- Dans le jeu ----------------------------------------------------------------------------------------

def partie_finie(tmp_path, monkeypatch, reponses, sortie, type_="standard", script=()):
    monkeypatch.setattr("aria.chemins.DONNEES", tmp_path / "donnees")
    serveur = ServeurScripte(*generation(), personnalite(), appel(), *script)
    partie = nouvelle_partie(tmp_path / "campagne", serveur, ["tout", "", "", "", *reponses], sortie)
    t = partie.session.monde["trame"]
    t |= {"type": type_, "acte": trame.nombre_d_actes(t | {"type": type_}), "reussies": 8,
          "fin": {"finale_reussie": True, "jour": 30, "nom": "triomphe"}}
    return partie


def test_arreter_garde_le_personnage_et_ferme_la_campagne(tmp_path, monkeypatch):
    sortie = []
    partie = partie_finie(tmp_path, monkeypatch, ["n"], sortie)
    assert partie.apres_la_fin() is True
    texte = "\n".join(sortie)
    assert "=== Fin de la campagne : triomphe ===" in texte and "il repartira aguerri (200 points personnels" in texte
    garde, = [p for p in personnages.lister("Cyberpunk") if p.fichier]
    assert garde.nom == "Yuki Sato" and garde.cran == AGUERRI
    lignes = []
    reprise = jeu.Jeu(ServeurScripte(), budget=128, entree=lambda _: "quitter", sortie=lignes.append,
                      campagne=Campagne(tmp_path / "campagne"))
    reprise.jouer()
    assert lignes == ["Cette campagne est terminée (triomphe). Yuki Sato attend dans le menu Personnages."]


def test_continuer_ouvre_une_nouvelle_trame(tmp_path, monkeypatch):
    sortie = []
    partie = partie_finie(tmp_path, monkeypatch, ["o"], sortie)
    ancien = partie.session.monde["trame"]["antagoniste"]
    assert partie.apres_la_fin() is False and "un nouvel adversaire se prépare" in sortie[-1]
    t = partie.session.monde["trame"]
    assert not trame.finie(t) and t["prochaine"] >= 1 + 11 and len(partie.session.monde["trames_passees"]) == 1
    assert t["antagoniste"] != ancien or len({q["maitre"] for q in partie.session.monde["quartiers"].values()}) == 1
    assert partie.apres_la_fin() is False  # la question ne revient pas
    assert [p for p in personnages.lister("Cyberpunk") if p.fichier] == []


def test_une_campagne_sans_fin_continue_d_office(tmp_path, monkeypatch):
    sortie = []
    partie = partie_finie(tmp_path, monkeypatch, [], sortie, type_="sans fin")
    assert partie.apres_la_fin() is False and not trame.finie(partie.session.monde["trame"])
    assert not any("Continuer dans ce monde" in ligne for ligne in sortie)


def test_la_mort_a_son_epilogue(tmp_path, monkeypatch):
    sortie = []
    partie = partie_finie(tmp_path, monkeypatch, [], sortie, script=["Yuki tombe sous la pluie d'Osaka."])
    del partie.session.monde["trame"]["fin"]  # la trame n'était pas finie
    partie.session.personnage.etat, partie.session.personnage.points_destin = Etat.MORT, 0
    partie.epilogue_de_mort()
    assert partie.session.monde["trame"]["fin"]["nom"] == "mort"
    assert any("Yuki tombe sous la pluie" in ligne for ligne in sortie)
    demande = partie.table.serveur.recus[-1][0][-1]["content"]
    assert "[Épilogue]" in demande and "'fin': 'mort'" in demande
    partie.epilogue_de_mort()  # la fin est déjà dite : rien de plus
    assert len([ligne for ligne in sortie if "Yuki tombe" in ligne]) == 1
