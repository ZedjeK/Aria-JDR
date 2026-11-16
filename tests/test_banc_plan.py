"""Le mini-banc du plan du round : sa mécanique, avec un faux serveur (le vrai MJ ne tourne que sur ordre)."""

import json

from aria import llm
from aria.banc_plan import SCENES, SEUIL_VALIDES, Bilan, Essai, jouer, lancer
from aria.combat_plan import NOM_OUTIL


class Obeissant:
    """Un faux serveur qui fait attaquer tout le monde, la première cible venue."""

    def __init__(self, panne=False):
        self.panne, self.appels = panne, 0

    def discuter(self, messages, outils=None, budget=None, **options):
        self.appels += 1
        if self.panne:
            raise llm.ErreurLLM("Le serveur n'a pas répondu : essai")
        propres = outils[0]["function"]["parameters"]["properties"]["plan"]["items"]["properties"]
        cible = propres["cible"]["enum"][0]
        plan = [{"pnj": i, "intention": "attaquer", "cible": cible} for i in propres["pnj"]["enum"]]
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "0", "type": "function", "function": {"name": NOM_OUTIL, "arguments": json.dumps({"plan": plan})}}]}}]}


def scene(nom):
    return next(s for s in SCENES if s.nom == nom)


def test_il_y_a_une_dizaine_de_situations_dont_quatre_pieges_de_caractere():
    assert len(SCENES) == 10
    assert len([s for s in SCENES if s.piege]) == 4  # fuir interdit, prudent, téméraire, loyal


def test_chaque_situation_se_joue_et_donne_un_plan_avec_un_serveur_obeissant():
    for s in SCENES:
        essai = jouer(Obeissant(), s, 1)
        assert essai.utilisable and essai.intentions, s.nom


def test_un_serveur_qui_fait_toujours_attaquer_rate_le_piege_du_prudent_et_reussit_celui_du_temeraire():
    assert jouer(Obeissant(), scene("prudent éprouvé"), 1).piege is False
    assert jouer(Obeissant(), scene("téméraire éprouvé"), 1).piege is True
    assert jouer(Obeissant(), scene("loyal, son camp à terre"), 1).piege is True
    assert jouer(Obeissant(), scene("indemne et prudent : fuir est interdit"), 1).piege is True
    assert jouer(Obeissant(), scene("deux couteaux"), 1).piege is None


def test_le_prudent_eprouve_est_bien_eprouve_et_le_loyal_a_bien_son_camp_a_terre():
    serveur = Obeissant()
    jouer(serveur, scene("prudent éprouvé"), 1)
    jouer(serveur, scene("loyal, son camp à terre"), 1)
    assert serveur.appels == 2


def test_le_bilan_compte_les_plans_valides_la_mediane_et_les_pieges_rates():
    sorties = []
    bilan = lancer(Obeissant(), sorties.append, repetitions=1)
    assert len(bilan.essais) == 10 and bilan.taux_valides == 1.0
    assert len(bilan.pieges_rates) == 1 and not bilan.concluant
    assert any("Pièges de caractère ratés : 1" in ligne for ligne in sorties)
    assert any("on s'arrête à l'étage 1" in ligne for ligne in sorties)


def test_un_bilan_sans_defaut_est_concluant_seulement_si_tout_tient():
    bon = Essai("x", True, True, 3.0, True, [])
    assert Bilan([bon, bon]).concluant
    assert not Bilan([bon, Essai("y", True, True, 40.0, None, [])]).concluant  # la médiane (40 s) dépasse 15 s
    assert not Bilan([bon, Essai("y", False, True, 3.0, None, [])]).concluant  # 50 % de plans valides
    assert SEUIL_VALIDES == 0.95


def test_sans_serveur_le_mini_banc_le_dit_et_ne_plante_pas():
    sorties = []
    bilan = lancer(Obeissant(panne=True), sorties.append, repetitions=1, scenes=SCENES[:2])
    assert bilan.taux_valides == 0 and any("aucun plan" in ligne for ligne in sorties)
