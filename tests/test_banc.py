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
        deja = sum(m["role"] == "tool" for m in messages)
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


def test_vingt_quatre_situations_dont_six_pieges():
    assert len(SITUATIONS) == 24
    assert sum(s.piege for s in SITUATIONS) == 6
    assert len({s.nom for s in SITUATIONS}) == 24
    assert len({s.joueur for s in SITUATIONS}) == 24  # le faux serveur les reconnaît à la phrase du joueur


@pytest.mark.parametrize("s", SITUATIONS, ids=lambda s: s.nom)
def test_chaque_scene_se_prepare(s):
    session = nouvelle_session(1)
    if s.preparer:
        s.preparer(session)
    assert session.personnage.nom == "Kaito"


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
