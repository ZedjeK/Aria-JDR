"""Un combat à pied dans la partie : le MJ qui raconte, ses outils réduits, le passage de main, la fin (REGLES.md 7.8).

Le serveur du MJ est un faux qui suit un script ; les dés sont truqués ; les choix du joueur sont scriptés.
"""

import json
from types import SimpleNamespace

import pytest

from aria import llm
from aria.combat_auto import ModeCombat
from aria.combat_partie import (
    MESSAGE_FIN,
    CombatDePartie,
    Recit,
    ReglagesDeCombat,
)
from aria.jeu import Jeu
from aria.outils import OUTILS_A_PIED
from aria.table import BUDGET_RECIT, Table
from tests.test_combat_joueur import Script
from tests.test_outils import ganger as creer_ganger
from tests.test_outils import session
from tests.test_table import ServeurScripte, appel


class Serveur(ServeurScripte):
    """Le faux serveur, qui note aussi le budget de réflexion de chaque requête, et peut tomber en panne."""

    def __init__(self, *script, panne=False):
        super().__init__(*script)
        self.budgets, self.panne = [], panne

    def discuter(self, messages, outils=None, budget=None, **options):
        if self.panne:
            raise llm.ErreurLLM("Le serveur n'a pas répondu : essai")
        self.budgets.append(budget)
        return super().discuter(messages, outils, budget, **options)

    def outils_de(self, requete: int) -> set[str]:
        return {o["function"]["name"] for o in (self.recus[requete][1] or [])}


def combat_a_pied(*des, rapide=False, **profil):
    """Kaito contre un ganger, dans une session où le code mène les combats à pied."""
    s = session(*des)
    s.combat_par_le_code = True
    creer_ganger(s, **({"dexterite": 70} if rapide else {}) | profil)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    return s


def partie(s, serveur, script, reglages=ReglagesDeCombat()):
    """Le combat de la partie, avec ce que le jeu lui donne : un écran, une table, de quoi faire parler le MJ."""
    table = Table(serveur, s, budget=512)
    dits, narrations = [], []

    def raconter(jouer_tour):
        try:
            tour = jouer_tour()
        except llm.ErreurLLM:
            dits.append("Le MJ n'a pas répondu.")
            return
        narrations.append(tour.narration)
        dits.append(tour.narration)

    ecran = script.ecran()
    combat = CombatDePartie(s, table, dits.append, script.choisir, script.entree, raconter, reglages)
    combat.ecran.pause = lambda _: None
    combat.dits, combat.narrations, combat.table = dits, narrations, table
    return combat


# --- Ce que le MJ a sous la main ---------------------------------------------------------------------

def test_en_combat_a_pied_le_mj_n_a_ni_attaque_ni_tour_de_parole():
    s = combat_a_pied()
    noms = {o["function"]["name"] for o in s.schemas()}
    assert noms == OUTILS_A_PIED & noms and {"fin_combat", "test_competence", "rejoindre_combat"} <= noms
    assert not noms & {"attaquer", "action_combat", "fin_de_tour", "stabiliser", "attaquer_zone", "lancer_sort",
                       "lancer_drone", "debut_combat", "outils"}


def test_appeler_un_outil_retire_dit_que_le_code_mene_le_combat():
    s = combat_a_pied()
    r = s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    assert "Le code mène ce combat" in r["erreur"] and "fin_combat" in r["erreur"]
    assert s.joueur.budget.utilise[next(iter(s.joueur.budget.utilise))] == 0


def test_sans_menu_a_poser_le_mj_garde_tous_ses_outils_comme_avant():
    s = session()
    creer_ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert s.mode_combat is ModeCombat.A_PIED and not s.a_pied  # la partie ne mène pas : c'est le banc, ou l'ancien jeu
    assert {"attaquer", "fin_de_tour"} <= {o["function"]["name"] for o in s.schemas()}


def test_un_combat_classique_laisse_au_mj_ses_outils_meme_dans_une_partie_menee_par_le_code():
    s = session()
    s.combat_par_le_code = True
    creer_ganger(s, arme="Grenade à fragmentation")
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert s.mode_combat is ModeCombat.CLASSIQUE and not s.a_pied
    assert "attaquer" in {o["function"]["name"] for o in s.schemas()}


def test_la_main_du_mj_peut_etre_reduite_ou_elargie_le_temps_d_une_action():
    s = combat_a_pied()
    s.main_du_mj = frozenset({"fin_combat"})
    assert {o["function"]["name"] for o in s.schemas()} == {"fin_combat"}
    s.main_du_mj = OUTILS_A_PIED | {"debut_poursuite"}
    assert "debut_poursuite" in {o["function"]["name"] for o in s.schemas()}


def test_debut_combat_a_pied_dit_au_mj_de_raconter_l_ouverture_sans_fiche():
    s = session()
    s.combat_par_le_code = True
    creer_ganger(s)
    r = s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert "Le code mène ce combat" in r["consigne"] and "fiche" not in r and "au_tour_de" not in r


# --- Le prompt ----------------------------------------------------------------------------------------

def systeme(s) -> str:
    return Table(Serveur(), s, budget=512)._systeme()


def test_le_prompt_n_a_plus_les_lignes_de_pilotage_quand_le_code_mene_les_combats():
    s = session()
    s.combat_par_le_code = True
    prompt = systeme(s)
    assert "`fin_de_tour`" not in prompt and "`action_combat`" not in prompt and "c'est le code" in prompt


def test_le_prompt_garde_les_lignes_de_pilotage_pour_un_combat_classique_et_pour_l_ancien_jeu():
    assert "`fin_de_tour`" in systeme(session())  # le banc : le MJ mène
    s = session()
    s.combat_par_le_code = True
    creer_ganger(s, arme="Grenade à fragmentation")
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert "`fin_de_tour`" in systeme(s)


# --- Le récit ------------------------------------------------------------------------------------------

def test_le_mj_raconte_sans_outils_avec_une_reflexion_courte_et_le_message_de_faits_se_resume():
    s = combat_a_pied()
    serveur = Serveur("Le ganger fonce, la lame au clair.")
    table = Table(serveur, s, budget=512)
    narration = table.raconter_le_combat("[Combat : récit] Le ganger attaque Kaito.", "[Combat : le round 1 a été raconté.]")
    assert narration == "Le ganger fonce, la lame au clair."
    assert serveur.recus[0][1] is None and serveur.budgets == [BUDGET_RECIT] == [128]
    assert table.messages[-2:] == [{"role": "user", "content": "[Combat : le round 1 a été raconté.]"},
                                   {"role": "assistant", "content": "Le ganger fonce, la lame au clair."}]


def test_un_serveur_muet_ne_laisse_aucune_trace_dans_la_conversation():
    s = combat_a_pied()
    table = Table(Serveur(panne=True), s, budget=512)
    avant = list(table.messages)
    assert table.raconter_le_combat("[Combat : récit] faits", "[résumé]") == ""
    assert table.messages == avant


def test_un_recit_vide_ne_laisse_aucune_trace_non_plus():
    s = combat_a_pied()
    table = Table(Serveur("  "), s, budget=512)
    avant = list(table.messages)
    assert table.raconter_le_combat("[Combat : récit] faits", "[résumé]") == ""
    assert table.messages == avant


# --- Le combat de la partie ---------------------------------------------------------------------------

def test_le_mj_raconte_juste_avant_le_menu_du_joueur_avec_les_faits_les_etats_et_le_decor():
    s = combat_a_pied(90, 90, 50, 70)  # Kaito rate son tir ; le ganger rate, et Kaito esquive ; round 2 : un tir
    serveur = Serveur("La lame passe à un souffle de Kaito.", [appel("fin_combat", moments_forts="Kaito fuit.")], "Fin.")
    script = Script("Attaquer", "Ganger", "Terminer", "Fuir", "Oui")
    c = partie(s, serveur, script)
    c.jouer()
    message = serveur.recus[0][0][-1]["content"]
    assert message.startswith("[Combat : récit]")
    assert "Kaito attaque Ganger" in message and "Ganger attaque Kaito" in message
    assert "États : Kaito : indemne ; Ganger : indemne." in message and "Décor : encombré" in message
    assert "23/23" not in message and "PV" not in message.split("États")[0]  # pas de PV dans les faits
    assert "La lame passe à un souffle de Kaito." in "\n".join(c.dits)


def test_parler_rend_la_main_au_mj_pour_cette_action_seulement():
    s = combat_a_pied(1)  # le jet de base du MJ
    serveur = Serveur([appel("test_competence", competence="Tromperie", difficulte="normale")],
                      [appel("fin_combat", moments_forts="Ils s'arrangent.")], "Le ganger hésite.")
    script = Script("Parler", saisies=("On peut s'arranger.",))
    c = partie(s, serveur, script)
    c.jouer()
    message = serveur.recus[0][0][-1]["content"]
    assert message.startswith("[Combat : action du joueur]") and "« On peut s'arranger. »" in message
    assert "(rien de nouveau)" in message  # aucun récit avant : il n'y avait rien à raconter
    assert "son action mineure" in message and "sans attaque ni dégâts" in message
    assert "attaquer" not in serveur.outils_de(0) and "test_competence" in serveur.outils_de(0)
    assert s.main_du_mj is None and s.combat is None


def test_la_fuite_donne_au_mj_la_poursuite_et_de_quoi_l_ouvrir():
    s = combat_a_pied()
    serveur = Serveur([appel("fin_combat", moments_forts="Kaito s'enfuit.")], "Kaito détale.")
    c = partie(s, serveur, Script("Fuir", "Oui"))
    c.jouer()
    message = serveur.recus[0][0][-1]["content"]
    assert message.startswith("[Combat : fuite]") and "Ganger" in message and "ganger" in message
    assert "debut_poursuite" in message and "debut_poursuite" in serveur.outils_de(0)
    assert s.combat is None


def test_une_victoire_se_raconte_puis_le_mj_appelle_fin_combat_seul_outil():
    s = combat_a_pied(1)  # Kaito sort un 01 : critique, dégâts maximum
    serveur = Serveur([appel("fin_combat", moments_forts="Kaito abat le ganger.")], "Le ganger s'effondre.")
    c = partie(s, serveur, Script("Attaquer", "Ganger"))
    c.jouer()
    message = serveur.recus[0][0][-1]["content"]
    assert message.startswith("[Combat : fin]") and "Les ennemis ne tiennent plus" in message
    assert "Kaito attaque Ganger" in message and "Ganger : à terre" in message
    assert serveur.outils_de(0) == {"fin_combat"}
    assert s.combat is None and s.mode_combat is None and s.main_du_mj is None
    assert "Le ganger s'effondre." in c.dits and "\nPlus aucun ennemi ne tient : le combat est fini." in c.dits


def test_une_defaite_dit_au_mj_de_ne_pas_tuer_le_joueur_et_de_ne_pas_frapper_de_nouveau():
    s = combat_a_pied(rapide=True)
    s.joueur.fiche.etat = type(s.joueur.fiche.etat).INCONSCIENT
    serveur = Serveur([appel("fin_combat", moments_forts="Kaito est à terre.")], "Les gangers repartent.")
    c = partie(s, serveur, Script())
    c.jouer()
    message = serveur.recus[0][0][-1]["content"]
    assert "hors de combat" in message and "Ne dis pas qu'il meurt" in message and "sans nouveau coup" in message
    assert s.combat is None


def test_si_le_mj_ne_ferme_pas_le_combat_le_code_le_ferme_avec_ses_propres_moments_forts():
    s = combat_a_pied(1)
    serveur = Serveur("Le ganger s'effondre.")  # raconte, mais n'appelle pas fin_combat
    c = partie(s, serveur, Script("Attaquer", "Ganger"))
    c.jouer()
    assert s.combat is None
    assert "Combat contre Ganger, 1 round. Les ennemis ne tenaient plus." in s.journal[-1]["resultat"]["souvenir"]


def test_si_le_serveur_du_mj_tombe_le_combat_se_termine_quand_meme():
    s = combat_a_pied(1)
    c = partie(s, Serveur(panne=True), Script("Attaquer", "Ganger"))
    c.jouer()
    assert s.combat is None and "Le MJ n'a pas répondu." in c.dits


# --- Les réglages ---------------------------------------------------------------------------------------

def test_recit_a_la_fin_ne_parle_pas_avant_les_menus():
    s = combat_a_pied(90, 90, 50)
    serveur = Serveur([appel("fin_combat", moments_forts="Kaito fuit.")], "Fin.")
    c = partie(s, serveur, Script("Attaquer", "Ganger", "Terminer", "Fuir", "Oui"), ReglagesDeCombat(Recit.A_LA_FIN))
    c.jouer()
    assert len(serveur.recus) == 2  # la fuite : appel et réponse ; aucun récit de round avant
    assert serveur.recus[0][0][-1]["content"].startswith("[Combat : fuite]")
    assert "Kaito attaque Ganger" in serveur.recus[0][0][-1]["content"]  # les faits attendent le prochain appel


def test_sans_recit_le_mj_ne_dit_rien_et_le_code_ecrit_les_moments_forts():
    s = combat_a_pied(1)
    serveur = Serveur()
    c = partie(s, serveur, Script("Attaquer", "Ganger"), ReglagesDeCombat(Recit.AUCUN))
    c.jouer()
    assert serveur.recus == [] and s.combat is None


def test_le_mj_ne_recoit_jamais_les_pv_des_ennemis_meme_si_le_joueur_les_voit():
    s = combat_a_pied(30, 3)  # Kaito touche, 1d10 = 3 (+1) : 4 dégâts sur 10 PV, sans blessure grave
    serveur = Serveur("Le ganger encaisse.", [appel("fin_combat", moments_forts="Kaito fuit.")], "Fin.")
    # le joueur voit les PV exacts ; le ganger joue ensuite et rate (90, défense 50), puis Kaito fuit au round 2
    s.combat.des._valeurs += [90, 50]
    script = Script("Attaquer", "Ganger", "Terminer", "Fuir", "Oui")
    c = partie(s, serveur, script, ReglagesDeCombat(pv_exacts=True))
    c.jouer()
    montre = "\n".join(c.dits + script.lignes)
    assert "PV 10 → 6" in montre
    recus = serveur.recus[0][0][-1]["content"] + (serveur.recus[1][0][-1]["content"] if len(serveur.recus) > 1 else "")
    assert "PV 10" not in recus and "10 → 6" not in recus


def test_les_reglages_de_combat_se_lisent_avec_tolerance():
    assert ReglagesDeCombat.depuis_dict(None) == ReglagesDeCombat()
    assert ReglagesDeCombat.depuis_dict({"recit": "fin", "pv_exacts": True, "choisir_sa_defense": True}) == \
        ReglagesDeCombat(Recit.A_LA_FIN, True, True)
    assert ReglagesDeCombat.depuis_dict({"recit": "n'importe quoi", "pv_exacts": "oui"}) == ReglagesDeCombat()


# --- Le jeu --------------------------------------------------------------------------------------------

def jeu_minimal(s, serveur, script, reglages=ReglagesDeCombat()):
    """Un Jeu sans campagne ni MJ réel : juste de quoi mener un combat à pied."""
    jeu = object.__new__(Jeu)
    jeu.session, jeu.table, jeu.choisir, jeu.entree = s, Table(serveur, s, budget=512), script.choisir, script.entree
    jeu.dire, jeu.reglages_combat = script.lignes.append, reglages
    return jeu


def test_le_jeu_mene_un_combat_a_pied_quand_le_mj_vient_de_l_ouvrir():
    s = combat_a_pied(1)
    serveur = Serveur([appel("fin_combat", moments_forts="Kaito abat le ganger.")], "Le ganger s'effondre.")
    jeu = jeu_minimal(s, serveur, Script("Attaquer", "Ganger"))
    jeu.combattre_a_pied()
    assert s.combat is None and "Le ganger s'effondre." in "\n".join(jeu.dire.__self__)


def test_le_jeu_ne_fait_rien_quand_le_combat_est_classique_ou_absent():
    s = session()
    serveur = Serveur()
    jeu_minimal(s, serveur, Script()).combattre_a_pied()
    assert serveur.recus == []


def test_l_interrupteur_du_plan_ne_branche_le_planificateur_que_s_il_est_allume(monkeypatch):
    import aria.combat_partie as combat_partie
    from aria.combat_plan import PlanificateurLLM

    vus, vrai = [], combat_partie.ouvrir_le_combat
    monkeypatch.setattr(combat_partie, "ouvrir_le_combat",
                        lambda s, ecran, planificateur=None: (vus.append(planificateur), vrai(s, ecran, planificateur))[1])
    for reglages, attendu in ((ReglagesDeCombat(), type(None)), (ReglagesDeCombat(pnj_par_le_llm=True), PlanificateurLLM)):
        vus.clear()
        s = combat_a_pied(1)  # Kaito joue le premier et abat le ganger : le plan n'est jamais demandé
        serveur = Serveur([appel("fin_combat", moments_forts="Fin.")], "Le ganger s'effondre.")
        partie(s, serveur, Script("Attaquer", "Ganger"), reglages).jouer()
        assert isinstance(vus[0], attendu) and s.combat is None


def test_le_plan_du_llm_est_eteint_par_defaut_et_se_lit_dans_les_reglages():
    assert ReglagesDeCombat().pnj_par_le_llm is False
    assert ReglagesDeCombat.depuis_dict({"pnj_par_le_llm": True}).pnj_par_le_llm is True
    assert ReglagesDeCombat.depuis_dict({"pnj_par_le_llm": "oui"}).pnj_par_le_llm is False
