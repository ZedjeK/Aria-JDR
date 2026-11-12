"""Le générateur de missions (REGLES.md 14.8) : les offres, leur acceptation et ce qu'elles changent à la fin."""

import pytest

from aria import gains, missions, monde
from aria.compte_rendu import decrire_monde
from aria.des import Des
from aria.monde import AMI, HOSTILE, MEMBRE, NEUTRE, RECHERCHE
from aria.personnage import AGUERRI, DEBUTANT, VETERAN
from aria.univers import charger_univers
from test_commerce import riche
from tests.test_monde import Imposes, attaque, petit
from tests.test_univers import CYBERPUNK

VOLER, ELIMINER, DEFENDRE = 1, 5, 12  # le rang de quelques objectifs dans la liste


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def une_offre(etat, **champs) -> dict:
    """Une offre posée à la main : voler à B, pour Helix, contre les Rats."""
    offre = {"id": "mission_1", "commanditaire": "Helix", "cible": "Rats", "lieu": "B", "objectif": "voler",
             "danger": "simple", "prime": 0, "recompense": 500, "retournement": None, "expire": 9, "source": "faction",
             "texte": "Voler, pour Helix, à B, contre Rats."} | champs
    etat["offres"].append(offre)
    return offre


def test_les_douze_objectifs_et_les_trente_retournements():
    assert len(missions.OBJECTIFS) == 12 and len(set(missions.OBJECTIFS)) == 12
    assert len(missions.retournements()) == 30 and len(set(missions.retournements())) == 30
    assert missions.DANGERS == ("un service", "simple", "risquée", "dangereuse", "très dangereuse", "exceptionnelle")


def test_le_danger_suit_l_experience_de_depart():
    assert [missions.danger_tire(Imposes(5), cran) for cran in (DEBUTANT, AGUERRI, VETERAN)] == [
        "simple", "risquée", "dangereuse"]
    assert missions.danger_tire(Imposes(3), DEBUTANT) == "un service"  # parfois un cran en dessous
    assert missions.danger_tire(Imposes(10), DEBUTANT) == "risquée"  # rarement un cran au-dessus
    assert missions.danger_tire(Imposes(10), VETERAN, decalage=3) == "exceptionnelle"  # jamais au-delà
    tires = [missions.danger_tire(Des(g), DEBUTANT) for g in range(200)]
    assert tires.count("simple") > tires.count("un service") > tires.count("risquée") > 0


def test_tirer_une_offre():
    e = petit()  # le joueur est à D, que Helix (corporation) domine
    o = missions.tirer_offre(e, Imposes(1, 2, VOLER, 1, 5, 2), 6)  # Helix, contre les Rats, voler, à B, simple
    assert (o["commanditaire"], o["cible"], o["objectif"], o["lieu"], o["danger"]) == ("Helix", "Rats", "voler", "B",
                                                                                      "simple")
    assert (o["prime"], o["recompense"]) == (1, 1000)  # la faction qui domine paie un palier de plus
    assert o["texte"] == "Voler, pour Helix, à B, contre Rats." and o["id"] == "mission_1" and o["expire"] == 6
    assert o["retournement"] is None and "controle" not in o and o["source"] == "faction"
    o = missions.tirer_offre(e, Imposes(1, 2, ELIMINER, 2, 5, 1, 4), 6)  # éliminer à C, avec un retournement
    assert o["controle"] == -2 and o["lieu"] == "C" and o["retournement"] == missions.retournements()[3]
    assert o["id"] == "mission_2"
    o = missions.tirer_offre(e, Imposes(1, 1, DEFENDRE, 1, 5, 2), 6)  # défendre : chez le commanditaire
    assert (o["lieu"], o["controle"], o["cible"]) == ("D", 2, "Lames")


def test_une_offre_par_un_contact_ou_par_un_evenement():
    e = petit()
    o = missions.tirer_offre(e, Imposes(1, 2, VOLER, 1, 5, 2, 1, 1), 6, contacts=["Mori", "Ishikawa"])
    assert o["source"] == "contact" and o["contact"] == "Ishikawa"
    assert "contact" not in missions.tirer_offre(e, Imposes(1, 2, VOLER, 1, 5, 2, 2), 6, contacts=["Mori"])
    monde.tirer_evenement(e, Imposes(1, 1), monde.QUARTIER, 2)  # une coupure de courant à D
    o = missions.tirer_offre(e, Imposes(1, 2, VOLER, 1, 5, 2), 6)
    assert o["source"] == "événement" and "Coupure de courant" in o["occasion"]
    e["offres"].append(o)
    assert "occasion" not in missions.tirer_offre(e, Imposes(1, 2, VOLER, 1, 5, 2), 6)  # une seule à la fois


def test_personne_ne_propose_rien_a_un_ennemi():
    e = petit()
    e["reputation"]["Helix"] = HOSTILE
    assert missions._commanditaires(e) == ["Lames", "Rats"]  # ceux d'ailleurs, faute de mieux ici
    e["reputation"] |= {"Lames": RECHERCHE, "Rats": HOSTILE}
    assert missions.tirer_offre(e, Imposes(), 6) is None


def test_la_mission_d_entree_d_une_faction_amie():
    e = petit()
    e["reputation"]["Helix"] = AMI
    assert missions.tirer_offre(e, Imposes(1, 2, VOLER, 1, 5, 2, 1), 6)["entree"]
    assert "entree" not in missions.tirer_offre(e, Imposes(1, 2, VOLER, 1, 5, 2, 2), 6)
    assert "le fait entrer chez Helix" in missions.resume({"id": "m", "commanditaire": "Helix", "entree": True})["mission_d_entree"]


def test_les_offres_se_renouvellent():
    e = petit()
    del e["prochaines_offres"]
    offres = missions.renouveler(e, Imposes(2, 4), 1)  # 2 offres, pour 4 jours
    assert len(offres) == 2 and e["prochaines_offres"] == 5 and all(o["expire"] == 5 for o in offres)
    assert missions.renouveler(e, Imposes(), 4) is offres and len(offres) == 2  # rien ne bouge avant la date
    anciennes = [o["id"] for o in offres]
    missions.renouveler(e, Imposes(3, 1), 5)
    assert len(e["offres"]) == 3 and not set(anciennes) & {o["id"] for o in e["offres"]}  # les autres ont disparu
    assert e["prochaines_offres"] == 6


def test_une_melee_annoncee_fait_recruter_les_deux_camps():
    e = attaque(petit(), jour=5)
    e["ici"] = "B"
    monde.avancer(e, Imposes(), 5)
    offres = missions.renouveler(e, Imposes(), 5)
    assert [(o["commanditaire"], o["camp"], o["source"]) for o in offres] == [("Rats", "défense", "mêlée"),
                                                                             ("Lames", "attaque", "mêlée")]
    assert offres[0]["texte"] == "Se battre pour Rats dans la mêlée de B, côté défense, contre Lames."
    assert len(missions.renouveler(e, Imposes(), 5)) == 2  # pas deux fois
    e["reputation"]["Lames"] = HOSTILE
    e["offres"].clear()
    assert [o["commanditaire"] for o in missions.renouveler(e, Imposes(), 5)] == ["Rats"]
    e["ici"] = "D"  # il s'en va ; le lendemain, la mêlée a été jouée sans lui
    monde.avancer(e, Imposes(), 6)
    assert missions.renouveler(e, Imposes(), 6) == []


def test_prendre_une_offre_et_ce_que_le_mj_en_montre():
    e = petit()
    o = une_offre(e, retournement="C'est un piège.", controle=-2)
    assert missions.resume(o) == {"id": "mission_1", "texte": "Voler, pour Helix, à B, contre Rats.",
                                  "danger": "simple", "recompense": 500}
    assert missions.prendre(e, "mission_1") == {"commanditaire": "Helix", "cible": "Rats", "lieu": "B",
                                                "objectif": "voler", "controle": -2}
    assert e["offres"] == []
    with pytest.raises(monde.MondeImpossible, match="Pas d'offre"):
        missions.prendre(e, "mission_1")


# --- La fin d'une mission -------------------------------------------------------------------------------

def test_une_mission_reussie_change_la_reputation():
    e = petit()
    mission = {"commanditaire": "Helix", "cible": "Rats", "lieu": "B", "objectif": "voler"}
    assert missions.conclure(e, Imposes(), mission, True, 3) == ["Helix : neutre → ami", "Rats : neutre → hostile"]
    e = petit()
    mission = {"commanditaire": "Lames", "cible": "Rats", "lieu": "B", "objectif": "voler"}  # la cible est la rivale
    assert missions.conclure(e, Imposes(), mission, True, 3) == ["Lames : neutre → ami", "Rats : neutre → hostile"]
    mission = {"commanditaire": "Lames", "cible": "Helix", "lieu": "D", "objectif": "voler"}  # la rivale et la cible
    assert missions.conclure(e, Imposes(), mission, True, 3) == ["Rats : hostile → recherché", "Helix : neutre → hostile"]
    assert e["reputation"] == {"Lames": AMI, "Rats": RECHERCHE, "Helix": HOSTILE}


def test_une_mission_ratee_deçoit_le_commanditaire():
    e = petit()
    mission = {"commanditaire": "Helix", "cible": "Rats", "lieu": "B", "objectif": "voler", "controle": -2}
    assert missions.conclure(e, Imposes(), mission, False, 3) == ["Helix : neutre → hostile"]
    assert e["reputation"]["Rats"] == NEUTRE and e["quartiers"]["B"]["controle"] == 3


def test_une_mission_contre_un_quartier_lui_coute_deux_points():
    e = petit()
    mission = {"commanditaire": "Lames", "cible": "Rats", "lieu": "C", "objectif": "saboter", "controle": -2}
    assert "C : contrôle 6 pour Rats" in missions.conclure(e, Imposes(), mission, True, 3)
    mission["lieu"] = "B"  # B n'a que 3 points : il tombe à 1, puis change de mains
    missions.conclure(e, Imposes(), mission, True, 3)
    assert e["quartiers"]["B"]["controle"] == 1
    changements = missions.conclure(e, Imposes(), mission, True, 4)
    assert "B change de mains : Lames le prend à Rats" in changements
    assert (e["quartiers"]["B"]["maitre"], e["quartiers"]["B"]["controle"]) == ("Lames", 5)
    assert "victoire de Lames sur Rats" in e["journal"][-1]["texte"]
    defense = {"commanditaire": "Helix", "cible": "Rats", "lieu": "D", "objectif": "défendre un lieu", "controle": 2}
    assert "D : contrôle 9 pour Helix" in missions.conclure(e, Imposes(), defense, True, 4)


def test_la_mission_d_entree_reussie_fait_un_membre():
    e = petit()
    e["reputation"]["Helix"] = AMI
    mission = {"commanditaire": "Helix", "cible": "Rats", "lieu": "B", "objectif": "voler", "entree": True}
    assert "Helix : ami → membre" in missions.conclure(e, Imposes(), mission, True, 3)
    assert monde.reputation(e, "Helix") == MEMBRE and monde.loge(e)


# --- Les outils du MJ -----------------------------------------------------------------------------------

def test_l_outil_monde_montre_les_offres_sans_leur_retournement(u):
    s, _ = riche(u, 0)
    s.monde = petit()
    assert "accepter_mission" not in {o["function"]["name"] for o in s.schemas()}  # pas d'offre : pas d'outil
    une_offre(s.monde, retournement="C'est un piège.")
    r = s.appeler("monde")
    assert r["offres_de_mission"] == [{"id": "mission_1", "texte": "Voler, pour Helix, à B, contre Rats.",
                                       "danger": "simple", "recompense": 500}]
    assert "piège" not in str(r) and "accepter_mission" in {o["function"]["name"] for o in s.schemas()}


def test_accepter_puis_reussir_une_mission(u):
    s, _ = riche(u, 0)
    s.monde = petit()
    une_offre(s.monde, retournement="C'est un piège.", prime=1, recompense=1000, controle=-2)
    r = s.appeler("accepter_mission", {"offre": "mission_1"})
    assert r["recompense"] == 1000 and r["retournement_pour_toi_seul"] == "C'est un piège." and r["avance"] == 0
    assert s.monde["offres"] == [] and s.memoire.fils["mission_1"].ouvert
    assert s.personnage.missions["mission_1"]["offre"]["controle"] == -2
    assert decrire_monde("accepter_mission", {}, r) == [
        "📜 Mission acceptée : Voler, pour Helix, à B, contre Rats. Récompense : 1000 crédits."]
    assert "erreur" in s.appeler("accepter_mission", {"offre": "mission_1"})  # elle n'est plus à prendre
    assert "reussie" in s.appeler("clore_fil", {"identifiant": "mission_1", "issue": "Le coffre est vidé."})["erreur"]
    r = s.appeler("clore_fil", {"identifiant": "mission_1", "issue": "Le coffre est vidé.", "reussie": True})
    assert r["recompense_versee"] == 1000 and s.personnage.argent == 1000
    assert r["monde"] == ["Helix : neutre → ami", "Rats : neutre → hostile", "B : contrôle 1 pour Rats"]
    assert decrire_monde("clore_fil", {}, r)[0] == "🏳 Helix : neutre → ami"
    assert s.monde["quartiers"]["B"]["controle"] == 1 and "mission_1" not in s.personnage.missions


def test_une_mission_ratee_ne_paie_pas(u):
    s, _ = riche(u, 0)
    s.monde = petit()
    une_offre(s.monde)
    s.appeler("accepter_mission", {"offre": "mission_1"})
    r = s.appeler("clore_fil", {"identifiant": "mission_1", "issue": "Kaito s'est fait prendre.", "reussie": False})
    assert r["recompense_versee"] == 0 and r["monde"] == ["Helix : neutre → hostile"] and s.personnage.argent == 0


def test_une_mission_du_mj_ne_change_pas_le_monde(u):
    s, _ = riche(u, 0)
    s.monde = petit()
    s.appeler("ouvrir_mission", {"identifiant": "colis", "fil": "Livrer un colis.", "danger": "simple"})
    r = s.appeler("clore_fil", {"identifiant": "colis", "issue": "Livré.", "reussie": True})
    assert r["recompense_versee"] == 500 and "monde" not in r and set(s.monde["reputation"].values()) == {NEUTRE}


def test_la_prime_et_le_marchandage(u):
    s, _ = riche(u, 0)
    assert gains.ouvrir_mission(s.personnage, "a", "simple", paliers=1).recompense == 1000
    assert gains.ouvrir_mission(s.personnage, "b", "simple").recompense == 500


def test_une_offre_de_melee_rappelle_l_outil_melee(u):
    s, _ = riche(u, 0, des=Imposes())
    s.monde = attaque(petit())
    s.appeler("monde", {"ici": "B"})
    offre = next(o for o in s.monde["offres"] if o["camp"] == "défense")
    r = s.appeler("accepter_mission", {"offre": offre["id"]})
    assert "melee" in r["rappel"] and "défense" in r["rappel"] and s.personnage.missions[offre["id"]]["offre"]["camp"] == "défense"


def test_les_offres_arrivent_quand_le_temps_passe(u):
    s, _ = riche(u, 0, des=Des(2))
    s.monde = monde.creer(Des(2), "Cyberpunk")
    for _ in range(3):
        s.appeler("avancer_temps")
    assert s.moment.jour == 2 and 1 <= len([o for o in s.monde["offres"] if o["source"] != "mêlée"]) <= 3
    assert s.monde["prochaines_offres"] > 2
