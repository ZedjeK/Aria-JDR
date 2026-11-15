"""La partie dans l'interface : la session (fil, événements, réponses) et ses routes (appli.partie)."""

import time
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from appli import donnees, partie, serveur
from aria import campagne, chemins, jeu, personnages

PORT, JETON = 8765, "jeton-de-test"


def attendre(condition, delai=5.0):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.01)
    return False


def jeu_scripte(entree, sortie):
    sortie("Bienvenue.")
    nom = entree("Ton nom ? ")
    sortie(f"Salut {nom}.")


# --- La session


def test_une_partie_pose_sa_question_attend_la_reponse_et_se_termine(tmp_path):
    p = partie.Partie(tmp_path)
    p.demarrer("campagne", "Essai", "essai", jeu_scripte)
    assert attendre(lambda: p.etat()["attend"] == "Ton nom ? ")
    p.repondre("Kaito")
    assert attendre(lambda: not p.etat()["actif"])
    evenements = p.evenements(0)["evenements"]
    assert [(e["type"], e["texte"]) for e in evenements] == [
        ("texte", "Bienvenue."), ("invite", "Ton nom ? "), ("joueur", "Kaito"), ("texte", "Salut Kaito."), ("fin", "")]
    assert [e["n"] for e in evenements] == [1, 2, 3, 4, 5]
    types = [e["type"] for e in donnees.lire_journal(tmp_path)]
    assert types.count("partie") == 2  # démarrée, terminée


def test_on_ne_repond_que_quand_une_question_attend(tmp_path):
    p = partie.Partie(tmp_path)
    with pytest.raises(ValueError):
        p.repondre("trop tôt")
    p.demarrer("campagne", "Essai", None, jeu_scripte)
    assert attendre(lambda: p.etat()["attend"])
    p.repondre("une fois")
    attendre(lambda: not p.etat()["actif"])
    with pytest.raises(ValueError):
        p.repondre("trop tard")


def test_une_seule_partie_a_la_fois(tmp_path):
    p = partie.Partie(tmp_path)
    p.demarrer("campagne", "Une", "une", jeu_scripte)
    attendre(lambda: p.etat()["attend"])
    with pytest.raises(partie.PartieEnCours):
        p.demarrer("campagne", "Deux", "deux", jeu_scripte)
    p.arreter()
    assert p.attendre_la_fin(5)
    p.demarrer("campagne", "Trois", "trois", jeu_scripte)  # la place est rendue, et les événements repartent de zéro
    attendre(lambda: p.etat()["attend"])
    assert p.evenements(0)["evenements"][0]["n"] == 1
    p.arreter()
    p.attendre_la_fin(5)


def test_arreter_la_partie_ferme_le_moteur_proprement(tmp_path):
    p = partie.Partie(tmp_path)
    p.demarrer("campagne", "Essai", "essai", jeu_scripte)
    attendre(lambda: p.etat()["attend"])
    p.arreter()
    assert p.attendre_la_fin(5)
    dernier = [e["texte"] for e in p.evenements(0)["evenements"]]
    assert "\nPartie interrompue." in dernier and p.etat()["erreur"] is None


def test_une_erreur_du_moteur_est_dite_a_la_page_sans_tuer_le_serveur(tmp_path, capsys):
    def casse(entree, sortie):
        raise RuntimeError("le MJ a cassé quelque chose")

    p = partie.Partie(tmp_path)
    p.demarrer("campagne", "Essai", None, casse)
    assert p.attendre_la_fin(5)
    assert p.etat()["erreur"] == "RuntimeError : le MJ a cassé quelque chose"
    assert any("erreur" in e["texte"] for e in p.evenements(0)["evenements"])
    assert any("Erreur" in e["bilan"] for e in donnees.lire_journal(tmp_path))
    capsys.readouterr()


def test_la_page_attend_les_nouveaux_evenements_au_lieu_de_tourner_en_boucle(tmp_path):
    p = partie.Partie(tmp_path)
    p.demarrer("campagne", "Essai", None, jeu_scripte)
    attendre(lambda: p.etat()["attend"])
    debut = time.time()
    assert p.evenements(p.etat()["dernier"], attente=0.3)["evenements"] == []
    assert time.time() - debut >= 0.25  # il a vraiment attendu
    p.arreter()
    p.attendre_la_fin(5)


# --- Les routes


@pytest.fixture
def donnees_jeu(tmp_path, monkeypatch):
    dossier = tmp_path / ".Aria-JDR"
    dossier.mkdir()
    monkeypatch.setattr(chemins, "DONNEES", dossier)
    return dossier


@pytest.fixture
def mj_pret(tmp_path):
    moteur = tmp_path / "llama-server.exe"
    moteur.write_bytes(b"")
    return {"profil": {"modele": "M", "budget_reflexion": 512}, "moteur": moteur}


def ouvrir(donnees_jeu, mj_pret=None, sans_mj=False):
    profil = None if sans_mj or mj_pret is None else mj_pret["profil"]
    moteur = (mj_pret["moteur"] if mj_pret else donnees_jeu / "absent.exe")
    app = serveur.creer_app(JETON, PORT, racine=donnees_jeu, arreter=lambda: None,
                            profil_valide=lambda: profil, moteur=lambda: moteur)
    client = TestClient(app, base_url=f"http://127.0.0.1:{PORT}", follow_redirects=False)
    assert client.get(f"/?j={JETON}").status_code == 303
    return client


def fausse_campagne(nom):
    c = campagne.Campagne.nommee(nom)
    c.ouvrir()
    c.sauvegarde.write_text("{}", encoding="utf-8")


def test_les_options_de_creation_donnent_de_quoi_remplir_les_formulaires(donnees_jeu):
    options = ouvrir(donnees_jeu).get("/api/creation").json()
    genres = {g["nom"]: g for g in options["genres"]}
    assert "Cyberpunk" in genres and genres["Cyberpunk"]["complet"] is True
    assert any(p["id"] == "livre" for p in genres["Cyberpunk"]["personnages"])
    assert options["type_standard"] in [t["nom"] for t in options["types"]] and options["tons"] and options["crans"]


def test_reprendre_une_campagne_inconnue_ou_sans_mj_ne_demarre_rien(donnees_jeu, mj_pret):
    fausse_campagne("neo-tokyo")
    assert ouvrir(donnees_jeu, mj_pret).post("/api/partie/reprendre", json={"nom": "inconnue"}).status_code == 404
    assert ouvrir(donnees_jeu, mj_pret).post("/api/partie/reprendre", json={"nom": "../x"}).status_code == 404
    sans_moteur = ouvrir(donnees_jeu).post("/api/partie/reprendre", json={"nom": "neo-tokyo"})
    assert sans_moteur.status_code == 409 and "introuvable" in sans_moteur.json()["detail"]
    sans_profil = ouvrir(donnees_jeu, mj_pret, sans_mj=True).post("/api/partie/reprendre", json={"nom": "neo-tokyo"})
    assert sans_profil.status_code == 409 and "qualifié" in sans_profil.json()["detail"]


def test_reprendre_une_campagne_lance_le_moteur_avec_l_entree_et_la_sortie_de_la_page(donnees_jeu, mj_pret, monkeypatch):
    appels = []

    def faux_lancer(camp, *args, entree, sortie, **kwargs):
        appels.append(camp.dossier.name)
        sortie("La partie commence.")
        sortie(f"Tu as écrit : {entree('> ')}")

    monkeypatch.setattr(jeu, "lancer", faux_lancer)
    fausse_campagne("neo-tokyo")
    client = ouvrir(donnees_jeu, mj_pret)
    assert client.post("/api/partie/reprendre", json={"nom": "neo-tokyo"}).json()["campagne"] == "neo-tokyo"
    assert attendre(lambda: client.get("/api/partie").json()["attend"] == "> ")
    assert client.post("/api/partie/saisie", json={"texte": "Je regarde autour de moi."}).status_code == 200
    assert attendre(lambda: not client.get("/api/partie").json()["actif"])
    textes = [e["texte"] for e in client.get("/api/partie/evenements").json()["evenements"]]
    assert appels == ["neo-tokyo"] and "Tu as écrit : Je regarde autour de moi." in textes


def test_on_ne_jette_pas_la_campagne_qu_on_joue_et_on_ne_quitte_pas_en_pleine_partie(donnees_jeu, mj_pret, monkeypatch):
    monkeypatch.setattr(jeu, "lancer", lambda camp, *a, entree, sortie, **k: entree("> "))
    fausse_campagne("neo-tokyo")
    fausse_campagne("autre")
    client = ouvrir(donnees_jeu, mj_pret)
    client.post("/api/partie/reprendre", json={"nom": "neo-tokyo"})
    attendre(lambda: client.get("/api/partie").json()["attend"])
    assert client.post("/api/campagnes/neo-tokyo/corbeille").status_code == 409
    assert client.post("/api/campagnes/autre/corbeille").status_code == 200
    assert client.post("/api/quitter").status_code == 409
    assert client.post("/api/partie/reprendre", json={"nom": "autre"}).status_code in (404, 409)
    assert client.post("/api/partie/arreter").status_code == 200
    assert attendre(lambda: not client.get("/api/partie").json()["actif"])
    assert client.post("/api/partie/arreter").status_code == 409
    assert client.post("/api/quitter").status_code == 200


def test_la_saisie_est_refusee_quand_rien_n_attend_ou_si_elle_est_absurde(donnees_jeu, mj_pret):
    client = ouvrir(donnees_jeu, mj_pret)
    assert client.post("/api/partie/saisie", json={"texte": "x"}).status_code == 409
    assert client.post("/api/partie/saisie", json={"texte": 12}).status_code == 400
    assert client.post("/api/partie/saisie", json={"texte": "x" * 2001}).status_code == 400
    assert client.post("/api/partie/saisie", json={}).status_code == 400


NOUVELLE = {"nom": "osaka", "genre": "Cyberpunk", "univers": "Osaka 2091", "cadre": "Osaka sous la pluie acide", "annee": 2091,
            "ton": "standard", "type": "standard", "cran": "débutant"}


@pytest.mark.parametrize("changement, code", [
    ({"nom": ""}, 400), ({"nom": "Nom Accentué é"}, 400), ({"genre": "Inconnu"}, 400), ({"annee": "abc"}, 400),
    ({"ton": "délirant"}, 400), ({"type": "inexistant"}, 400), ({"cran": "demi-dieu"}, 400), ({"personnage": "fantome.json"}, 400)])
def test_une_nouvelle_campagne_mal_remplie_est_refusee_avant_de_lancer_quoi_que_ce_soit(donnees_jeu, mj_pret, changement, code):
    client = ouvrir(donnees_jeu, mj_pret)
    assert client.post("/api/partie/nouvelle", json={**NOUVELLE, **changement}).status_code == code
    assert client.get("/api/partie").json()["actif"] is False and campagne.noms() == []


def test_une_campagne_qui_existe_deja_n_est_pas_ecrasee(donnees_jeu, mj_pret):
    fausse_campagne("osaka")
    assert ouvrir(donnees_jeu, mj_pret).post("/api/partie/nouvelle", json=NOUVELLE).status_code == 409


def test_une_nouvelle_campagne_ecrit_son_format_et_lance_le_moteur_avec_les_choix(donnees_jeu, mj_pret, monkeypatch):
    recus = {}

    def faux_lancer(camp, choix, surprends_moi, predefini=None, entree=None, sortie=None):
        recus.update(nom=camp.dossier.name, choix=choix, surprends_moi=surprends_moi, predefini=predefini)
        sortie("Univers créé.")

    monkeypatch.setattr(jeu, "lancer", faux_lancer)
    client = ouvrir(donnees_jeu, mj_pret)
    reponse = client.post("/api/partie/nouvelle", json={**NOUVELLE, "personnage": "livre"})
    assert reponse.status_code == 200 and reponse.json()["nature"] == "campagne"
    assert attendre(lambda: not client.get("/api/partie").json()["actif"])
    assert recus["nom"] == "osaka" and recus["choix"].nom == "Osaka 2091" and recus["choix"].annee == 2091
    assert recus["surprends_moi"] is False and recus["predefini"].nom == "Kaito"
    assert '"type": "standard"' in campagne.Campagne.nommee("osaka").format.read_text(encoding="utf-8")


def test_le_mj_qui_propose_le_cadre_passe_par_surprends_moi(donnees_jeu, mj_pret, monkeypatch):
    recus = {}
    monkeypatch.setattr(jeu, "lancer", lambda camp, choix, surprends_moi, predefini=None, entree=None, sortie=None:
                        recus.update(surprends_moi=surprends_moi, nom=choix.nom))
    client = ouvrir(donnees_jeu, mj_pret)
    client.post("/api/partie/nouvelle", json={**NOUVELLE, "surprends_moi": True})
    assert attendre(lambda: "surprends_moi" in recus)
    assert recus["surprends_moi"] is True and recus["nom"] != "Osaka 2091"


def test_creer_un_personnage_passe_par_la_meme_fonction_que_la_console(donnees_jeu, mj_pret, monkeypatch):
    recus = []
    monkeypatch.setattr(personnages, "creer", lambda genre, cran, avec_mj, entree, sortie: recus.append((genre, cran, avec_mj)))
    client = ouvrir(donnees_jeu, mj_pret)
    assert client.post("/api/partie/personnage", json={"genre": "Cyberpunk", "cran": "débutant"}).status_code == 200
    assert attendre(lambda: recus)
    assert recus == [("Cyberpunk", "débutant", False)]  # sans le MJ : pas besoin qu'il soit là
    assert ouvrir(donnees_jeu).post("/api/partie/personnage", json={"genre": "Cyberpunk", "avec_mj": True}).status_code == 409
    assert client.post("/api/partie/personnage", json={"genre": "Nulle part"}).status_code == 400


def test_rien_ne_demarre_par_un_get(donnees_jeu, mj_pret):
    client = ouvrir(donnees_jeu, mj_pret)
    for chemin in ("/api/partie/reprendre", "/api/partie/nouvelle", "/api/partie/personnage", "/api/partie/saisie",
                   "/api/partie/arreter"):
        assert client.get(chemin).status_code in (404, 405)


def test_sans_cookie_la_partie_est_fermee(donnees_jeu):
    app = serveur.creer_app(JETON, PORT, racine=donnees_jeu)
    client = TestClient(app, base_url=f"http://127.0.0.1:{PORT}")
    for methode, chemin in (("get", "/api/partie"), ("post", "/api/partie/saisie"), ("post", "/api/partie/reprendre")):
        assert getattr(client, methode)(chemin).status_code == 403


def test_le_vrai_moteur_joue_une_reprise_de_bout_en_bout_par_la_session(tmp_path, monkeypatch):
    """Le vrai Jeu, avec un faux MJ qui suit un script : sa sortie arrive à la page, ses questions attendent la réponse."""
    from aria.sauvegarde import sauvegarder
    from tests.test_sauvegarde import partie_en_cours
    from tests.test_table import ServeurScripte

    monkeypatch.setattr(chemins, "DONNEES", tmp_path / ".Aria-JDR")
    camp = campagne.Campagne.nommee("neo-tokyo")
    camp.ouvrir()
    sauvegarder(partie_en_cours(), camp.sauvegarde)
    faux_serveur = ServeurScripte("La pluie tombe sur Néo-Tokyo.", "Le ganger recule d'un pas.", "Souvenirs rangés.")

    @contextmanager
    def faux_mj(sortie=print):
        yield faux_serveur, {"budget_reflexion": 128}, SimpleNamespace(contexte=16384)

    monkeypatch.setattr(jeu, "mj_charge", faux_mj)
    p = partie.Partie(tmp_path)
    p.demarrer("campagne", "Reprise", "neo-tokyo", lambda entree, sortie: jeu.lancer(camp, entree=entree, sortie=sortie))

    def attend_la_commande():
        return attendre(lambda: (p.etat()["attend"] or "").strip() == ">")

    assert attend_la_commande()
    p.repondre("etat")                      # une commande du moteur, sans MJ
    assert attend_la_commande()
    p.repondre("Je regarde le ganger.")     # un tour avec le MJ
    assert attend_la_commande()
    p.repondre("quitter")                   # fin de session : le MJ range ses souvenirs, la progression est tirée
    assert p.attendre_la_fin(10) and p.etat()["erreur"] is None
    texte = "\n".join(e["texte"] for e in p.evenements(0)["evenements"] if e["type"] == "texte")
    assert "La pluie tombe sur Néo-Tokyo." in texte and "Le ganger recule d'un pas." in texte
    assert "PV" in texte and "=== Fin de session ===" in texte and "Partie sauvegardée" in texte
    assert [e["texte"] for e in p.evenements(0)["evenements"] if e["type"] == "joueur"] == ["etat", "Je regarde le ganger.", "quitter"]
