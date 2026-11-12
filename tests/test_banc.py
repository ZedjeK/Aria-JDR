"""Le banc d'essai du MJ, joué avec un faux serveur qui répond des appels d'outils écrits à l'avance."""

import json

import pytest

from aria import banc
from aria.banc import SITUATIONS, Situation, exige, interdit, au_plus, egal, essayer_budget, jouer, nouvelle_session


class FauxServeur:
    """Répond, pour chaque situation, la liste d'appels donnée, puis une narration."""

    def __init__(self, scenarios: dict[str, list[tuple[str, dict]]], defaut=()):
        self.scenarios, self.defaut = scenarios, list(defaut)
        self.budgets = []

    def discuter(self, messages, outils=None, budget=None):
        self.budgets.append(budget)
        joueur = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        situation = next(s.nom for s in SITUATIONS if s.joueur == joueur)
        dernier_joueur = max(i for i, m in enumerate(messages) if m["role"] == "user")
        deja = sum(m["role"] == "tool" for m in messages[dernier_joueur:])  # les appels de ce tour-ci
        appels = self.scenarios.get(situation, self.defaut)
        if deja < len(appels):
            nom, arguments = appels[deja]
            message = {"role": "assistant", "content": None, "tool_calls": [
                {"id": str(deja), "type": "function", "function": {"name": nom, "arguments": json.dumps(arguments)}}]}
        else:
            message = {"role": "assistant", "content": "Que fais-tu ?"}
        return {"choices": [{"message": message}], "usage": {"completion_tokens": 10}}


def situation(nom):
    return next(s for s in SITUATIONS if s.nom == nom)


def test_soixante_neuf_situations_dont_dix_huit_pieges():
    assert len(SITUATIONS) == 69
    assert sum(s.piege for s in SITUATIONS) == 18
    assert len({s.nom for s in SITUATIONS}) == 69
    assert len({s.joueur for s in SITUATIONS}) == 69  # le faux serveur les reconnaît à la phrase du joueur
    assert sum(s.univers == banc.FANTASY for s in SITUATIONS) == 6


@pytest.mark.parametrize("s", SITUATIONS, ids=lambda s: s.nom)
def test_chaque_scene_se_prepare(s):
    session = nouvelle_session(1, s.univers)
    if s.preparer:
        s.preparer(session)
    assert session.personnage.nom == ("Elara" if s.univers == banc.FANTASY else "Kaito")


def test_verifications():
    appels = [("test_competence", {"competence": "Piratage"}), ("choc", {"choc": "TORTURE"}),
              ("choc", {"choc": "TORTURE"})]
    assert exige("test_competence", egal("competence", "Piratage"))(appels) is None
    assert "attendu" in exige("test_competence", egal("competence", "Athlétisme"))(appels)
    assert "interdit" in interdit("choc")(appels)
    assert "trop d'appels" in au_plus("choc", 1)(appels)


def test_une_situation_reussie():
    serveur = FauxServeur({"porte": [("test_competence", {"competence": "Piratage", "difficulte": "normale"})]})
    partie = jouer(serveur, situation("porte"), budget=0, graine=1)
    assert partie.reussie and partie.narration == "Que fais-tu ?"
    assert serveur.budgets == [0, 0]


def test_une_erreur_corrigee_est_acceptee():
    serveur = FauxServeur({"porte": [("test_competence", {"competence": "Pirater", "difficulte": "normale"}),
                                     ("test_competence", {"competence": "Piratage", "difficulte": "normale"})]})
    partie = jouer(serveur, situation("porte"), budget=0, graine=1)
    assert partie.reussie
    assert "erreur" in partie.appels[0]


def test_le_piege_du_ramen():
    serveur = FauxServeur({"ramen": [("test_competence", {"competence": "Vigilance", "difficulte": "facile"})]})
    partie = jouer(serveur, situation("ramen"), budget=0, graine=1)
    assert not partie.reussie and partie.raisons == ["interdit : test_competence"]
    assert jouer(FauxServeur({}), situation("ramen"), budget=0, graine=1).reussie


def test_raconter_sans_les_des_est_rate():
    partie = jouer(FauxServeur({}), situation("videur"), budget=0, graine=1)
    assert not partie.reussie


def test_le_mj_qui_tourne_en_rond_est_arrete():
    boucle = [("etat", {})] * 20
    partie = jouer(FauxServeur({"porte": boucle}), situation("porte"), budget=0, graine=1)
    assert len(partie.appels) == banc.TOURS_MAX + 1
    assert not partie.reussie


def test_un_piege_rate_arrete_le_budget():
    essai = essayer_budget(FauxServeur({}), budget=0, afficher=lambda *_: None)
    assert not essai.reussi and essai.pieges == "raté"
    assert len(essai.parties) == 1  # pas la peine de jouer la suite


def test_un_budget_qualifie(monkeypatch):
    # Un banc réduit : un piège et deux situations normales, dont une ratée (permis : 1 sur 2 à 50 %)
    reduites = [situation("ramen"), situation("porte"), situation("mur")]
    monkeypatch.setattr(banc, "SITUATIONS", reduites)
    monkeypatch.setattr(banc, "SEUIL_NORMALES", 0.5)
    serveur = FauxServeur({"porte": [("test_competence", {"competence": "Piratage", "difficulte": "normale"})]})
    essai = essayer_budget(serveur, budget=128, afficher=lambda *_: None)
    assert essai.reussi and (essai.normales, essai.pieges) == ("1/2", "1/1")
    assert [p.situation for p in essai.parties] == ["ramen", "ramen", "porte", "porte", "mur"]


def test_le_piege_de_l_enchainement():
    tir = ("attaquer", {"attaquant": "joueur", "cible": "tireur"})
    riposte = ("attaquer", {"attaquant": "tireur", "cible": "joueur"})
    bon = [tir, ("fin_de_tour", {}), riposte, ("fin_de_tour", {})]
    assert jouer(FauxServeur({"enchainer": bon}), situation("enchainer"), budget=0, graine=1).reussie
    saute = [tir, ("fin_de_tour", {}), ("fin_de_tour", {}), ("fin_de_tour", {"passe": True})]
    partie = jouer(FauxServeur({"enchainer": saute}), situation("enchainer"), budget=0, graine=1)
    assert partie.raisons == ["interdit : fin_de_tour (tour du joueur sauté)"]
    # Tirer encore sans fin_de_tour : le moteur refuse (budget), l'appel raté ne compte pas
    double = [tir, tir]
    partie = jouer(FauxServeur({"enchainer": double}), situation("enchainer"), budget=0, graine=1)
    assert partie.reussie and "erreur" in partie.appels[1]


def test_le_piege_encore_montre_le_vrai_test_au_mj():
    session = nouvelle_session(1)
    historique = situation("encore").preparer(session)
    assert [m["role"] for m in historique] == ["user", "assistant", "tool", "assistant"]
    resultat = json.loads(historique[2]["content"])
    assert resultat["reussi"] and "ne se relance pas" in resultat["consigne"]
    assert session.dernier_test["nom"] == "Piratage"  # le moteur a bien joué ce test


def test_hana_juge_l_effet_du_choc():
    for choc, attendu in ((("PERTE_DU_LIEN", False), True), (("MORT_D_UN_ALLIE", True), True),
                          (("MORT_D_UN_ALLIE", False), False), (("VIOLENCE_BRUTALE", True), False)):
        appels = [{"choc": choc[0], "concerne_lien": choc[1]}]
        serveur = FauxServeur({"hana": [("choc", appels[0])]})
        assert jouer(serveur, situation("hana"), budget=0, graine=1).reussie is attendu, choc


def test_la_memoire_fidele():
    fidele = {"titre": "Chez Mori", "moments_forts": "Mori accorde une semaine de soins gratuits à Kaito."}
    infidele = {"titre": "Chez Mori", "moments_forts": "Mori accorde un mois de soins gratuits à Kaito."}
    assert jouer(FauxServeur({"fidele": [("fin_scene", fidele)]}), situation("fidele"), 0, 1).reussie
    partie = jouer(FauxServeur({"fidele": [("fin_scene", infidele)]}), situation("fidele"), 0, 1)
    assert partie.raisons == ["interdit : fin_scene (le mois que le joueur espérait)"]


def test_le_piege_du_faux_souvenir():
    promesse = {"identifiant": "promesse_mori", "fil": "Mori doit 1000 eddies à Kaito."}
    assert jouer(FauxServeur({}), situation("souvenir"), 0, 1).reussie
    assert not jouer(FauxServeur({"souvenir": [("ouvrir_fil", promesse)]}), situation("souvenir"), 0, 1).reussie
    # Hors jeu, pas de dés : le joueur n'a rien à bluffer
    negociation = ("test_competence", {"competence": "Négociation", "difficulte": "difficile"})
    assert not jouer(FauxServeur({"souvenir": [negociation]}), situation("souvenir"), 0, 1).reussie


def test_le_bluff_de_kaito():
    """En jeu, Mori peut refuser ou laisser trancher les dés, sans que la dette devienne un fait."""
    tentative = {"identifiant": "doc_mori", "nom": "Doc Mori", "role": "charcudoc",
                 "attitude": "vexé : Kaito a tenté de lui soutirer 1000 eddies sur une promesse inventée"}
    assert jouer(FauxServeur({}), situation("bluff"), 0, 1).reussie
    difficile = ("test_competence", {"competence": "Arnaque", "difficulte": "difficile"})
    assert jouer(FauxServeur({"bluff": [difficile, ("noter_pnj", tentative)]}), situation("bluff"), 0, 1).reussie
    normale = ("test_competence", {"competence": "Négociation", "difficulte": "normale"})
    partie = jouer(FauxServeur({"bluff": [normale]}), situation("bluff"), 0, 1)
    assert partie.raisons == ["interdit : test_competence (bluff trop facile)"]
    dette = ("ouvrir_fil", {"identifiant": "dette_mori", "fil": "Mori doit 1000 eddies à Kaito."})
    assert not jouer(FauxServeur({"bluff": [dette]}), situation("bluff"), 0, 1).reussie


def test_le_colis_est_dans_la_memoire():
    session = nouvelle_session(1)
    situation("colis").preparer(session)
    assert "colis_lotus" in session.memoire.bloc() and "Le fixeur" in session.memoire.bloc()


def test_les_pieges_de_la_magie():
    trait = ("lancer_sort", {"lanceur": "joueur", "sort": "Trait de feu", "cible": "brigand"})
    assert jouer(FauxServeur({"trait": [trait]}), situation("trait"), 0, 1).reussie
    assert jouer(FauxServeur({}), situation("boule"), 0, 1).reussie  # refuser sans rien lancer
    flamme = ("lancer_sort", {"lanceur": "joueur", "sort": "Allumer ou souffler une flamme"})
    assert not jouer(FauxServeur({"boule": [flamme]}), situation("boule"), 0, 1).reussie
    squelette = ("creer_pnj", {"identifiant": "squelette", "nom": "Squelette", "camp": "allies", "combat": 40,
                               "pv": 8})
    assert not jouer(FauxServeur({"squelette": [squelette]}), situation("squelette"), 0, 1).reussie


def test_la_boule_de_feu_vise_la_destruction():
    etrange = ("choc", {"choc": "PHENOMENE_ETRANGE"})
    assert jouer(FauxServeur({"boule": [etrange]}), situation("boule"), 0, 1).reussie  # le prompt s'en charge
    massacre = ("choc", {"choc": "MASSACRE"})
    partie = jouer(FauxServeur({"boule": [massacre]}), situation("boule"), 0, 1)
    assert partie.raisons == ["interdit : choc (le marché rasé)"]
