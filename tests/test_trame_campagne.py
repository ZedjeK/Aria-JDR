"""La trame d'une campagne (REGLES.md 14.9 et 14.10) : l'antagoniste, les actes, les missions principales, le
secret en couches et les indices."""

import json

import pytest

from aria import amorce, jeu, missions, monde, trame
from aria.campagne import Campagne
from aria.compte_rendu import decrire_monde
from aria.monde import HOSTILE
from aria.personnage import AGUERRI, DEBUTANT, VETERAN
from aria.univers import charger_univers
from test_amorce import AMORCE, PLAN, appel, generation, nouvelle_partie
from test_commerce import riche
from test_creation import personnalite
from test_table import ServeurScripte
from tests.test_monde import Imposes, petit
from tests.test_univers import CYBERPUNK

SECRET = ["Les comptes de la clinique sont faux.", "Helix paie le docteur Mori.", "Helix teste un implant sur les pauvres."]


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def avec_trame(type_="standard", cran=DEBUTANT, secret=True) -> dict:
    """Le petit monde, avec Helix pour antagoniste et une mission principale prête à s'ouvrir."""
    e = petit()
    t = trame.creer(e, Imposes(1, 1, 1, 1), type_, cran)  # Helix, le chef en personne, le premier but
    t["prochaine"] = 1
    if secret:
        trame.poser_le_secret(t, SECRET)
    return e


def joue(e, perso, reussie=True, jour=2, des=None) -> dict:
    """Ouvre la mission principale, la prend, et la conclut."""
    offre = missions.tenir_la_trame(e, Imposes(), jour)
    mission = missions.prendre(e, offre["id"])
    return trame.apres_mission(e, des or Imposes(), mission, reussie, jour, perso)


# --- L'antagoniste et les actes -------------------------------------------------------------------------

def test_la_trame_tire_son_antagoniste():
    e = petit()
    t = trame.creer(e, Imposes(2, 3, 4, 2), "standard", AGUERRI)
    assert t["antagoniste"] == "Lames" and t["visage"].startswith("un bailleur de fonds")
    assert t["but"] == "prendre un territoire qui lui résiste" and t["prochaine"] == 3  # le plan : 1d3 jours
    assert (t["acte"], t["faites"], t["couches"], t["indices"], t["secret"]) == (1, 0, 0, [], [])
    assert trame.creer(petit(), Imposes(1, 1, 1), "courte")["prochaine"] == 1  # au cœur du problème : tout de suite
    assert trame.creer(petit(), Imposes(1, 1, 1, 5), "longue")["prochaine"] == 6  # le quotidien : 1d5 jours
    assert trame.trame_de(petit()) is None and trame.trame_de(None) is None and trame.bloc(None) == ""


def test_le_danger_monte_d_un_cran_par_acte():
    def dangers(type_, cran=DEBUTANT):
        t = {"type": type_, "cran": cran, "acte": 0}
        return [trame.danger_principal(t | {"acte": acte}) for acte in range(1, trame.nombre_d_actes(t) + 1)]
    assert dangers("standard") == ["risquée", "dangereuse", "très dangereuse"] == dangers("courte")
    assert dangers("longue") == ["simple", "risquée", "dangereuse", "très dangereuse", "exceptionnelle"]
    assert dangers("standard", AGUERRI) == ["dangereuse", "très dangereuse", "exceptionnelle"]
    assert dangers("standard", VETERAN) == ["très dangereuse", "exceptionnelle", "exceptionnelle"]  # jamais au-delà
    assert dangers("contrat") == ["risquée"]


def test_une_seule_mission_principale_qui_attend():
    e = avec_trame()
    e["trame"]["prochaine"] = 3
    assert missions.tenir_la_trame(e, Imposes(), 2) is None and e["offres"] == []  # pas avant sa date
    o = missions.tenir_la_trame(e, Imposes(1, 1, 1, 2), 3)
    assert o["principale"] and o["cible"] == "Helix" and o["danger"] == "risquée" and o["recompense"] == 2000
    assert o["commanditaire"] in ("Lames", "Rats") and o["source"] == "trame" and "finale" not in o
    assert missions.resume(o)["mission_principale"] == "acte 1 : elle attend le joueur"
    assert missions.tenir_la_trame(e, Imposes(), 9) is o and len(e["offres"]) == 1  # une seule à la fois
    e["prochaines_offres"] = 0
    missions.renouveler(e, Imposes(1, 1), 40)  # les offres secondaires se renouvellent ; elle, non
    assert o in e["offres"] and sum(x.get("principale", False) for x in e["offres"]) == 1


def test_le_commanditaire_d_une_principale_veut_bien_du_joueur():
    e = avec_trame()
    e["reputation"] |= {"Lames": HOSTILE}
    assert missions.tirer_principale(e, Imposes())["commanditaire"] == "Rats"
    e["reputation"] |= {"Rats": HOSTILE}  # tout le monde lui est hostile : il faut bien que quelqu'un l'emploie
    assert missions.tirer_principale(e, Imposes())["commanditaire"] in ("Lames", "Rats")


def test_un_contrat_n_a_qu_une_mission_la_finale(u):
    e = avec_trame("contrat")
    o = missions.tenir_la_trame(e, Imposes(), 1)
    assert o["finale"] and missions.resume(o)["mission_principale"] == "la mission finale"
    s, _ = riche(u, 0)
    suite = trame.apres_mission(e, Imposes(), missions.prendre(e, o["id"]), True, 1, s.personnage)
    assert suite["finale"] == "réussie" and trame.finie(e["trame"]) and suite["xp_gagnee"] == 0
    assert missions.tenir_la_trame(e, Imposes(), 5) is None  # la trame est finie : plus de mission principale


def test_une_secondaire_sur_quatre_touche_la_trame():
    e = avec_trame()
    assert missions.tirer_offre(e, Imposes(1, 2, 1, 1, 5, 2, 1), 6)["touche_la_trame"]
    assert "touche_la_trame" not in missions.tirer_offre(e, Imposes(1, 2, 1, 1, 5, 2, 2), 6)
    assert "touche_la_trame" not in missions.tirer_offre(petit(), Imposes(1, 2, 1, 1, 5, 2), 6)  # sans trame


# --- Après une mission ----------------------------------------------------------------------------------

def test_une_principale_reussie_donne_de_l_xp_et_un_indice(u):
    s, _ = riche(u, 0)
    e = avec_trame()
    suite = joue(e, s.personnage)
    t = e["trame"]
    assert suite["xp_gagnee"] == 2 and s.personnage.xp == 2 and "indice_a_decrire" in suite
    assert (t["faites"], t["reussies"], t["dus"], t["acte"], t["principale"]) == (1, 1, 1, 1, None)
    assert t["prochaine"] == 2 and "tournant" not in suite  # la suivante arrive tout de suite : même acte


def test_le_tournant_d_acte(u):
    s, _ = riche(u, 0)
    e = avec_trame()
    joue(e, s.personnage)
    suite = joue(e, s.personnage, jour=4, des=Imposes(3))  # la deuxième : l'acte 1 est fini, 1d5 jours de pause
    t = e["trame"]
    assert (t["acte"], t["faites"], t["prochaine"]) == (2, 0, 7) and "L'acte 2 sur 3 commence" in suite["tournant"]
    assert "il riposte" in suite["tournant"]
    assert missions.tenir_la_trame(e, Imposes(), 6) is None  # le joueur souffle
    assert missions.tenir_la_trame(e, Imposes(), 7)["danger"] == "dangereuse"  # un cran de plus


def test_une_principale_ratee_laisse_une_cicatrice(u):
    s, _ = riche(u, 0)
    e = avec_trame("courte")
    suite = joue(e, s.personnage, reussie=False, des=Imposes(3))  # une dette
    t = e["trame"]
    assert suite["xp_gagnee"] == 1 and "indice_a_decrire" not in suite and t["ratees"] == 1  # la moitié de 3
    assert suite["cicatrice"].startswith("une dette : il doit maintenant 1000 à Helix")
    assert s.personnage.dettes == [{"creancier": "Helix", "echeance": 100, "reste": 1200, "manquees": 0}]
    assert t["acte"] == 2 and t["cicatrices"] == [{"jour": 2, "nature": "une dette"}]  # elle ne bloque rien
    suite = joue(e, s.personnage, reussie=False, jour=9, des=Imposes(2, 1))  # un quartier qui bascule : C
    assert suite["cicatrice"] == "un quartier qui bascule : C passe à Helix."
    assert (e["quartiers"]["C"]["maitre"], e["quartiers"]["C"]["controle"]) == ("Helix", 5)
    assert "victoire de Helix sur Rats" in e["journal"][-1]["texte"]
    assert "choisis lequel" in joue(e, s.personnage, reussie=False, jour=10, des=Imposes(1, 3))["cicatrice"]
    assert trame.dernier_acte(e["trame"])
    suite = joue(e, s.personnage, reussie=False, jour=20, des=Imposes(4))
    assert "Son lien paie pour lui" in suite["cicatrice"] and suite["finale"] == "ratée"
    assert e["trame"]["fin"] == {"finale_reussie": False, "jour": 20}


def test_une_secondaire_qui_touche_la_trame_donne_un_indice(u):
    s, _ = riche(u, 0)
    e = avec_trame()
    mission = {"commanditaire": "Lames", "cible": "Rats", "touche_la_trame": True}
    assert "indice_a_decrire" in trame.apres_mission(e, Imposes(), mission, True, 3, s.personnage)
    assert e["trame"]["dus"] == 1 and s.personnage.xp == 0  # pas d'XP de trame pour une secondaire
    assert trame.apres_mission(e, Imposes(), mission, False, 3, s.personnage) == {
        "indice_a_decrire": trame.apres_mission(e, Imposes(), {}, True, 3, s.personnage)["indice_a_decrire"]}
    assert e["trame"]["dus"] == 1  # ratée, ou sans rapport : rien de plus
    assert trame.apres_mission(petit(), Imposes(), mission, True, 3, s.personnage) == {}  # sans trame


# --- Le secret en couches -------------------------------------------------------------------------------

def test_les_couches_s_ouvrent_avec_les_indices():
    t = avec_trame()["trame"]  # standard : 3 indices par couche
    assert trame.noter_un_indice(t, 2, "Un reçu au nom de Mori.") == [] and trame.noter_un_indice(t, 2, "Un badge.") == []
    r, = trame.noter_un_indice(t, 3, "  Une vidéo   de la clinique. ")
    assert r["couche"] == "Ce qui cloche" and r["ce_qu_il_comprend"] == SECRET[0] and "révélation" in r["consigne"]
    assert t["indices"][-1] == {"jour": 3, "texte": "Une vidéo de la clinique."} and t["couches"] == 1
    for n in range(3):
        revelations = trame.noter_un_indice(t, 4, f"Indice {n}.")
    assert revelations[0]["couche"] == "Qui est derrière" and t["couches"] == 2
    for n in range(4):  # tous les indices sont là, mais la dernière couche attend le dernier acte
        assert trame.noter_un_indice(t, 5, f"Autre {n}.") == []
    assert t["couches"] == 2 and trame.indices_en_trop(t) == 1
    with pytest.raises(trame.TrameImpossible, match="200 caractères"):
        trame.noter_un_indice(t, 5, "x" * 201)
    with pytest.raises(trame.TrameImpossible):
        trame.noter_un_indice(t, 5, "  ")


def test_la_derniere_couche_s_ouvre_au_dernier_acte(u):
    s, _ = riche(u, 0)
    e = avec_trame("courte")  # 2 indices par couche ; actes de 1, 2 et 1 missions
    t = e["trame"]
    for n in range(6):
        trame.noter_un_indice(t, 1, f"Indice {n}.")
    assert t["couches"] == 2
    joue(e, s.personnage)  # fin de l'acte 1
    assert t["couches"] == 2
    joue(e, s.personnage, jour=5)
    suite = joue(e, s.personnage, jour=6)  # fin de l'acte 2 : le dernier acte commence
    assert suite["revelation"][0]["couche"] == "Toute la vérité" and suite["revelation"][0]["ce_qu_il_comprend"] == SECRET[2]
    assert t["couches"] == 3


def test_sans_secret_ecrit_les_couches_s_ouvrent_quand_meme():
    t = avec_trame("contrat", secret=False)["trame"]
    trame.poser_le_secret(t, ["une seule", "", ""])  # il en faut trois, ou aucune
    assert t["secret"] == []
    r, = trame.noter_un_indice(t, 1, "Un reçu.")
    assert r["ce_qu_il_comprend"] == "" and t["couches"] == 1


def test_ce_que_le_mj_lit_de_la_trame():
    e = avec_trame()
    t = e["trame"]
    texte = trame.bloc(e)
    assert "L'antagoniste : Helix ; derrière, le chef en personne. Il veut s'emparer" in texte
    assert "Acte 1 sur 3. L'antagoniste reste dans l'ombre" in texte and SECRET[0] in texte
    assert SECRET[1] not in texte and SECRET[2] not in texte  # il ne peut pas lâcher ce qu'il n'a pas sous les yeux
    assert "Tu ne relances jamais la trame" in texte and "Un indice est dû" not in texte
    t["couches"], t["dus"] = 1, 1
    texte = trame.bloc(e)
    assert f"Le personnage a compris — ce qui cloche : {SECRET[0]}" in texte and "Un indice est dû" in texte
    assert f"que tu sèmes sans jamais le dire : {SECRET[1]}" in texte and SECRET[2] not in texte
    t["fin"] = {"finale_reussie": True, "jour": 9}
    assert "La trame est terminée." in trame.bloc(e)


def test_les_pistes_du_joueur():
    e = avec_trame()
    assert trame.pistes(e) == ["Aucune piste pour l'instant."]
    assert "avant" in trame.pistes(petit())[0]
    for n in range(4):
        trame.noter_un_indice(e["trame"], 2 + n, f"Indice {n}.")
    lignes = trame.pistes(e)
    assert lignes[:2] == ["Ce que tu as compris :", f"  Ce qui cloche — {SECRET[0]}"]
    assert lignes[2] == "Tes indices :" and lignes[-1] == "  Jour 5 — Indice 3." and len(lignes) == 7
    assert not any(SECRET[1] in ligne or "manque" in ligne for ligne in lignes)


# --- L'outil indice -------------------------------------------------------------------------------------

def test_l_outil_indice_decrit_l_indice_du(u):
    s, _ = riche(u, 0)
    s.monde = petit()
    assert "indice" not in {o["function"]["name"] for o in s.schemas()}  # pas de trame : pas d'outil
    s.monde = avec_trame("contrat")
    assert "Aucun indice n'est dû" in s.appeler("indice", {"description": "Un reçu."})["erreur"]
    trame.accorder_un_indice(s.monde["trame"])
    r = s.appeler("indice", {"description": "Un reçu au nom de Mori."})
    assert r["indice"] == "Un reçu au nom de Mori." and r["indices_trouves"] == 1 and "jet" not in r
    assert r["revelation"][0]["ce_qu_il_comprend"] == SECRET[0] and s.monde["trame"]["dus"] == 0
    assert decrire_monde("indice", {}, r) == ["🧩 Indice : Un reçu au nom de Mori."]
    assert "200 caractères" in s.appeler("indice", {"description": "x" * 250, "competence": "Piratage"})["erreur"]
    assert not s.monde["trame"]["enquete"]  # refusé avant le test : l'enquête de la scène n'est pas perdue


def test_une_enquete_par_scene(u):
    s, _ = riche(u, 0, des=Imposes(20, 99, 20))
    s.monde = avec_trame()
    s.personnage.competences["Technologie"] = 75  # son Piratage
    r = s.appeler("indice", {"description": "Un badge d'accès Helix.", "competence": "Piratage"})
    assert r["reussi"] and r["indice"] == "Un badge d'accès Helix." and s.monde["trame"]["enquete"]
    assert "Une seule enquête par scène" in s.appeler("indice", {"description": "Un autre.", "competence": "Piratage"})["erreur"]
    s.appeler("fin_scene", {"titre": "La clinique", "moments_forts": "Kaito fouille le bureau de Mori."})
    r = s.appeler("indice", {"description": "Raté.", "competence": "Piratage"})
    assert r["indice"] is None and not r["reussi"] and len(s.monde["trame"]["indices"]) == 1
    assert decrire_monde("indice", {"competence": "Piratage"}, r)[0].startswith("🎲 Enquête (Piratage)")


def test_une_mission_principale_par_les_outils(u):
    s, _ = riche(u, 0, des=Imposes())
    s.monde = avec_trame()
    r = s.appeler("monde")
    offre = next(o for o in r["offres_de_mission"] if "mission_principale" in o)
    r = s.appeler("accepter_mission", {"offre": offre["id"]})
    assert r["mission_principale"] == "acte 1" and r["recompense"] == 2000
    r = s.appeler("clore_fil", {"identifiant": offre["id"], "issue": "Le dossier est sorti.", "reussie": True})
    assert r["trame"]["xp_gagnee"] == 2 and "indice_a_decrire" in r["trame"] and s.personnage.argent == 2000
    assert decrire_monde("clore_fil", {}, r)[-1] == "⭐ Mission principale : +2 XP"
    assert "indice" in {o["function"]["name"] for o in s.schemas()}


# --- L'amorce ---------------------------------------------------------------------------------------------

def test_l_amorce_ecrit_le_secret_en_trois_couches():
    assert amorce.outil_amorce() is amorce.OUTIL_AMORCE
    parametres = amorce.outil_amorce(couches=True)["function"]["parameters"]
    assert {"soupcon", "coupable", "secret"} <= set(parametres["required"])
    assert all("160 caractères au plus" in parametres["properties"][c]["description"] for c in ("soupcon", "coupable"))
    assert "soupcon" not in amorce.OUTIL_AMORCE["function"]["parameters"]["properties"]  # l'outil d'origine est intact
    sans = {k: v for k, v in AMORCE.items() if k not in ("soupcon", "coupable")}
    assert amorce.verifier(sans, PLAN)[0].couches == []
    assert "« soupcon »" in " ".join(amorce.verifier(sans, PLAN, couches=True)[1])
    proposee, erreurs = amorce.verifier(AMORCE, PLAN, couches=True)
    assert not erreurs and proposee.couches == [AMORCE["soupcon"], AMORCE["coupable"], AMORCE["secret"]]
    assert AMORCE["secret"] not in proposee.scene and "ignore encore" not in proposee.scene
    demande = amorce._demande(charger_univers(CYBERPUNK), _perso(), PLAN, [], "", "L'antagoniste de la campagne : Helix.")
    assert "L'antagoniste de la campagne : Helix. Le secret le concerne" in demande[1]["content"]


def _perso():
    from test_amorce import Brouillon, ROLEPLAY, proposer_chiffres, random
    b = proposer_chiffres(Brouillon(charger_univers(CYBERPUNK)), random.Random(2), "Netrunner")
    b.fixer("roleplay", ROLEPLAY)
    return b.finaliser()[0]


def test_une_nouvelle_campagne_a_sa_trame(tmp_path):
    serveur = ServeurScripte(*generation(), personnalite(), appel(), "La pluie tombe sur Osaka.")
    sortie = []
    partie = nouvelle_partie(tmp_path, serveur, ["tout", "", "", "", "pistes", "quitter"], sortie)
    t = partie.session.monde["trame"]
    assert t["type"] == "standard" and t["antagoniste"] in partie.session.monde["factions"]
    assert t["secret"] == [AMORCE["soupcon"], AMORCE["coupable"], AMORCE["secret"]]
    demande = serveur.recus[-1][0][-1]["content"]  # la demande d'amorce nomme l'antagoniste
    assert f"L'antagoniste de la campagne : {t['antagoniste']}" in demande
    systeme = partie.table.messages[0]["content"]
    assert "### La trame (pour toi seul)" in systeme and AMORCE["soupcon"] in systeme
    assert AMORCE["secret"] not in systeme and AMORCE["coupable"] not in systeme  # ni dans la scène, ni dans la mémoire
    partie.jouer()
    assert "Aucune piste pour l'instant." in "\n".join(sortie) and "« pistes » : tes indices" in "\n".join(sortie)
    sauvegarde = json.loads((tmp_path / "sauvegarde.json").read_text(encoding="utf-8"))
    assert sauvegarde["monde"]["trame"]["secret"][2] == AMORCE["secret"]
    reprise = jeu.Jeu(ServeurScripte(), budget=128, entree=lambda _: "quitter", sortie=lambda _: None,
                      campagne=Campagne(tmp_path))
    assert "### La trame (pour toi seul)" in reprise.table.messages[0]["content"]
