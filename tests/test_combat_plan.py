"""Le plan du round par le LLM (REGLES.md 7.8, étage 2) : sa traduction en actions, sa lecture, ses replis.

Le serveur du MJ est un faux qui renvoie des réponses scriptées ; les dés sont truqués.
"""

import json

import pytest

from aria import llm
from aria.combat import Combat, Combattant, Couvert, Decor, FichePnj, Moral, TypeAction
from aria.combat_auto import (
    Action,
    Choix,
    CombatAuto,
    Fin,
    Geste,
    Intention,
    Registre,
    prochaine_action,
)
from aria.combat_plan import (
    BUDGET_PLAN,
    DELAI_PLAN,
    NOM_OUTIL,
    PANNES_MAX,
    PlanificateurLLM,
)
from aria.des import DesTruques
from aria.personnage import Etat
from tests.test_combat import COUTEAU, PISTOLET, combat, ganger, kaito
from tests.test_outils import ganger as creer_ganger
from tests.test_outils import session


def decider(c, combattant, choix, registre=None, **kwargs):
    return prochaine_action(c, combattant, registre or Registre(), choix=choix, **kwargs)


# --- Les intentions deviennent des actions ----------------------------------------------------------------

def test_attaquer_une_cible_choisie_sans_passer_par_le_couvert():
    k, g = kaito(), ganger(arme=PISTOLET)
    c = combat(DesTruques(), k, g)  # décor encombré : l'IA seule irait d'abord à couvert
    assert decider(c, g, None) == Action(Geste.COUVERT)
    assert decider(c, g, Choix(Intention.ATTAQUER, k)) == Action(Geste.ATTAQUER, k)


def test_l_etat_de_l_arme_passe_avant_l_intention():
    k, g = kaito(), ganger(arme=PISTOLET)
    g.munitions[PISTOLET] = 0
    assert decider(combat(DesTruques(), k, g), g, Choix(Intention.ATTAQUER, k)) == Action(Geste.RECHARGER)


def test_viser_puis_attaquer_pour_un_tireur():
    k, g = kaito(), ganger(arme=PISTOLET)
    c = combat(DesTruques(), k, g)
    choix = Choix(Intention.VISER, k)
    assert decider(c, g, choix) == Action(Geste.VISER)
    c.viser(g)
    assert decider(c, g, choix) == Action(Geste.ATTAQUER, k)


def test_viser_ne_se_joue_pas_au_corps_a_corps_l_ia_decide():
    k, g = kaito(), ganger()
    assert decider(combat(DesTruques(), k, g), g, Choix(Intention.VISER, k)) == Action(Geste.ATTAQUER, k)


def test_s_abriter_pour_un_tireur_puis_le_tour_est_fini():
    k, g = kaito(), ganger(arme=PISTOLET)
    c = combat(DesTruques(), k, g)
    choix = Choix(Intention.S_ABRITER)
    assert decider(c, g, choix) == Action(Geste.COUVERT)
    c.se_mettre_a_couvert(g)
    assert decider(c, g, choix) is None  # à l'abri : il n'attaque pas ce round


def test_s_abriter_sans_abri_ou_au_corps_a_corps_l_ia_decide():
    k, g = kaito(), ganger(arme=PISTOLET)
    assert decider(combat(DesTruques(), k, g, decor=Decor.DEGAGE), g, Choix(Intention.S_ABRITER)) == \
        Action(Geste.ATTAQUER, k)
    k, g = kaito(), ganger()
    assert decider(combat(DesTruques(), k, g), g, Choix(Intention.S_ABRITER)) == Action(Geste.ATTAQUER, k)


def test_une_cible_tombee_ou_hors_du_camp_retombe_sur_l_ia():
    k, g = kaito(), ganger()
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10), "ennemis", COUTEAU)
    c = combat(DesTruques(), k, g, allie)
    k.fiche.etat = Etat.INCONSCIENT
    autre = Combattant(FichePnj("Passant", combat=20, pv_max_base=8), "joueur", COUTEAU)
    c.rejoindre(autre)
    assert decider(c, g, Choix(Intention.ATTAQUER, k)).cible is autre  # Kaito est à terre : l'IA prend l'autre
    assert decider(c, g, Choix(Intention.ATTAQUER, allie)).cible is autre  # un allié de g n'est pas une cible


def test_le_plafond_de_deux_attaquants_vaut_aussi_pour_le_plan():
    k = kaito()
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10), "allies", COUTEAU)
    a, b, troisieme = ganger(nom="Alpha"), ganger(nom="Bravo"), ganger(nom="Charlie")
    c = combat(DesTruques(), k, allie, a, b, troisieme)
    registre = Registre()
    registre.attaquants[k] = {a, b}
    assert decider(c, troisieme, Choix(Intention.ATTAQUER, k), registre) == Action(Geste.ATTAQUER, allie)


def test_fuir_et_se_rendre_se_jouent_par_le_moral_pas_par_une_action():
    k, g = kaito(), ganger()
    c = combat(DesTruques(), k, g)
    for intention in (Intention.FUIR, Intention.SE_RENDRE):
        assert decider(c, g, Choix(intention)) == Action(Geste.ATTAQUER, k)


# --- La boucle suit le plan ----------------------------------------------------------------------------

def auto_planifie(c, plan_par_round):
    """Une boucle dont le plan est écrit à l'avance : un par round (l'appel est compté)."""
    appels = []

    def planificateur(combat_, registre):
        appels.append(combat_.round)
        return plan_par_round.pop(0) if plan_par_round else None

    return CombatAuto(c, planificateur=planificateur), appels


def test_le_plan_se_demande_une_fois_par_round_au_premier_tour_d_un_pnj():
    k, g, h = kaito(), ganger(nom="Alpha", dexterite=70), ganger(nom="Bravo", dexterite=65)
    c = combat(DesTruques(*([90, 50] * 2)), k, g, h, tour_par_tour=True)
    auto, appels = auto_planifie(c, [{}, {}])
    auto.jouer_le_tour()
    auto.jouer_le_tour()
    assert appels == [1]  # Alpha et Bravo jouent le round 1 : un seul plan


def test_un_pnj_absent_du_plan_suit_l_ia_et_un_planificateur_muet_aussi():
    k, g = kaito(), ganger(dexterite=70)
    c = combat(DesTruques(90, 50), k, g, tour_par_tour=True)
    auto, _ = auto_planifie(c, [None])
    rapport = auto.jouer_le_tour()
    assert [e.action.geste for e in rapport.evenements] == [Geste.ATTAQUER]


def test_le_plan_dirige_les_actions_du_tour():
    k, g = kaito(), ganger(arme=PISTOLET, dexterite=70)
    c = combat(DesTruques(90), k, g, tour_par_tour=True)
    auto, _ = auto_planifie(c, [{g: Choix(Intention.S_ABRITER)}])
    rapport = auto.jouer_le_tour()
    assert [e.action.geste for e in rapport.evenements] == [Geste.COUVERT] and g.couvert is Couvert.PARTIEL


def test_fuir_de_son_plein_gre_demande_un_declencheur_et_ne_demande_pas_de_test():
    k, g = kaito(), ganger(dexterite=70, pv=4)  # sous la moitié de ses PV
    c = combat(DesTruques(10), k, g, tour_par_tour=True)  # son test de moral réussit : il tenait bon
    auto, _ = auto_planifie(c, [{g: Choix(Intention.FUIR)}])
    rapport = auto.jouer_le_tour()
    assert g.moral is Moral.EN_FUITE and rapport.moral.test is None and rapport.moral.moral is Moral.EN_FUITE
    assert [e.action.geste for e in rapport.evenements] == [Geste.FUIR, Geste.FUIR]


def test_se_rendre_de_son_plein_gre_ne_joue_plus_de_tour():
    k, g = kaito(), ganger(dexterite=70, pv=4)
    c = combat(DesTruques(10), k, g, tour_par_tour=True)
    auto, _ = auto_planifie(c, [{g: Choix(Intention.SE_RENDRE)}])
    rapport = auto.jouer_le_tour()
    assert g.moral is Moral.RENDU and rapport.passe


def test_sans_declencheur_fuir_ou_se_rendre_est_ignore_et_le_pnj_se_bat():
    k, g = kaito(), ganger(dexterite=70)  # indemne, seul de son camp
    c = combat(DesTruques(90, 50), k, g, tour_par_tour=True)
    auto, _ = auto_planifie(c, [{g: Choix(Intention.FUIR)}])
    rapport = auto.jouer_le_tour()
    assert g.moral is Moral.NORMAL and rapport.moral is None
    assert [e.action.geste for e in rapport.evenements] == [Geste.ATTAQUER]


def test_le_plan_ne_retient_jamais_un_pnj_que_le_moral_fait_craquer():
    k, g = kaito(), ganger(dexterite=70, pv=4)
    c = combat(DesTruques(99), k, g, tour_par_tour=True)  # le test de moral est raté
    auto, _ = auto_planifie(c, [{g: Choix(Intention.ATTAQUER, k)}])
    rapport = auto.jouer_le_tour()
    assert g.moral is Moral.EN_FUITE and rapport.moral.test is not None
    assert [e.action.geste for e in rapport.evenements] == [Geste.FUIR, Geste.FUIR]


# --- Le planificateur du LLM ----------------------------------------------------------------------------

class Serveur:
    """Un faux serveur : renvoie les réponses scriptées (un plan, ou une erreur), et note ce qu'on lui demande."""

    def __init__(self, *reponses):
        self.reponses, self.demandes = list(reponses), []

    def discuter(self, messages, outils=None, budget=None, **options):
        self.demandes.append({"messages": messages, "outils": outils, "budget": budget, **options})
        suivante = self.reponses.pop(0)
        if isinstance(suivante, Exception):
            raise suivante
        return suivante


def plan_de(*entrees, nom=NOM_OUTIL, brut=None):
    arguments = brut if brut is not None else json.dumps({"plan": list(entrees)})
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "0", "type": "function", "function": {"name": nom, "arguments": arguments}}]}}]}


def combat_planifie(*reponses, **profil):
    """Deux ennemis (un colérique au couteau, un tireur peureux) contre Kaito, dans une session des outils."""
    s = session()
    creer_ganger(s, "voyou", nom="Voyou", dexterite=70)
    creer_ganger(s, "tireur", nom="Tireur", arme="Pistolet lourd", dexterite=50)
    s.appeler("debut_combat", {"pnj": ["voyou", "tireur"]})
    s.pnj["voyou"].caractere, s.pnj["tireur"].caractere = "colérique", "peureux"
    serveur = Serveur(*reponses)
    return s, serveur, PlanificateurLLM(serveur, s)


def appeler(planificateur, s):
    return planificateur(s.combat, Registre())


def test_un_plan_valide_donne_une_intention_par_pnj():
    s, serveur, p = combat_planifie(plan_de({"pnj": "voyou", "intention": "attaquer", "cible": "joueur"},
                                            {"pnj": "tireur", "intention": "s'abriter"}))
    plan = appeler(p, s)
    assert plan == {s.pnj["voyou"]: Choix(Intention.ATTAQUER, s.joueur), s.pnj["tireur"]: Choix(Intention.S_ABRITER)}
    assert (p.stats.appels, p.stats.plans_valides, p.stats.plans_partiels, p.stats.echecs) == (1, 1, 0, 0)


def test_la_demande_impose_l_outil_borne_le_delai_et_decrit_chacun():
    s, serveur, p = combat_planifie(plan_de({"pnj": "voyou", "intention": "attaquer", "cible": "joueur"}))
    appeler(p, s)
    demande = serveur.demandes[0]
    assert demande["outil_impose"] == NOM_OUTIL and demande["delai"] == DELAI_PLAN == 25 and demande["budget"] == BUDGET_PLAN
    schema = demande["outils"][0]["function"]
    entree = schema["parameters"]["properties"]["plan"]["items"]["properties"]
    assert entree["pnj"]["enum"] == ["tireur", "voyou"] and entree["cible"]["enum"] == ["joueur"]
    assert entree["intention"]["enum"] == ["attaquer", "s'abriter", "viser", "fuir", "se rendre"]
    texte = demande["messages"][1]["content"]
    assert "voyou (Voyou), caractère : colérique ; Couteau ; indemne" in texte
    assert "tireur (Tireur), caractère : peureux ; Pistolet lourd (8 balles) ; indemne" in texte
    assert "Décor : encombré" in texte and "joueur (Kaito, indemne)" in texte and "personne n'a été blessé" in texte


def test_un_pnj_sans_caractere_le_dit():
    s, serveur, p = combat_planifie(plan_de())
    s.pnj["voyou"].caractere = ""
    appeler(p, s)
    assert "caractère : aucun en particulier" in serveur.demandes[0]["messages"][1]["content"]


def test_un_pnj_eprouve_peut_fuir_et_le_plan_le_sait():
    s, serveur, p = combat_planifie(plan_de({"pnj": "voyou", "intention": "fuir"}))
    s.pnj["voyou"].fiche.pv = 3
    plan = appeler(p, s)
    assert "éprouvé (la moitié de ses PV) : il peut fuir ou se rendre" in serveur.demandes[0]["messages"][1]["content"]
    assert plan == {s.pnj["voyou"]: Choix(Intention.FUIR)}


@pytest.mark.parametrize("entree", [
    {"pnj": "inconnu", "intention": "attaquer", "cible": "joueur"},      # un PNJ qui n'existe pas
    {"pnj": "voyou", "intention": "danser"},                              # hors de la liste fermée
    {"pnj": "voyou", "intention": "attaquer"},                            # une attaque sans cible
    {"pnj": "voyou", "intention": "attaquer", "cible": "tireur"},        # une cible de son propre camp
    {"pnj": "voyou", "intention": "fuir"},                                # fuir sans être éprouvé
    {"pnj": "voyou", "intention": "se rendre"},
    "n'importe quoi",
])
def test_une_entree_illisible_ou_illegale_est_ecartee_et_le_plan_devient_partiel(entree):
    s, _, p = combat_planifie(plan_de(entree, {"pnj": "tireur", "intention": "s'abriter"}))
    plan = appeler(p, s)
    assert plan == {s.pnj["tireur"]: Choix(Intention.S_ABRITER)}  # le voyou retombe sur l'IA
    assert p.stats.plans_valides == 0 and p.stats.plans_partiels == 1


def test_un_pnj_en_double_garde_sa_premiere_entree():
    s, _, p = combat_planifie(plan_de({"pnj": "voyou", "intention": "attaquer", "cible": "joueur"},
                                      {"pnj": "voyou", "intention": "s'abriter"},
                                      {"pnj": "tireur", "intention": "s'abriter"}))
    assert appeler(p, s)[s.pnj["voyou"]] == Choix(Intention.ATTAQUER, s.joueur)
    assert p.stats.plans_partiels == 1


def test_un_pnj_qui_a_craque_ou_qui_est_tombe_n_est_pas_planifie():
    s, serveur, p = combat_planifie(plan_de({"pnj": "voyou", "intention": "attaquer", "cible": "joueur"}))
    s.pnj["tireur"].moral = Moral.EN_FUITE
    appeler(p, s)
    assert "tireur (" not in serveur.demandes[0]["messages"][1]["content"].split("PNJ à jouer :")[1]


def test_rien_a_planifier_ne_demande_rien():
    s, serveur, p = combat_planifie()
    for c in s.pnj.values():
        c.fiche.etat = Etat.INCONSCIENT
    assert appeler(p, s) is None and serveur.demandes == []


@pytest.mark.parametrize("reponse", [
    {"choices": [{"message": {"role": "assistant", "content": "Je pense qu'ils attaquent."}}]},  # pas d'appel d'outil
    plan_de(brut="{pas du json"),
    plan_de(nom="autre_outil"),
    plan_de(brut='{"plan": "attaquer"}'),
    {"choices": []},
])
def test_une_reponse_illisible_donne_la_main_a_l_ia(reponse):
    s, _, p = combat_planifie(reponse)
    assert appeler(p, s) is None
    assert p.stats.echecs == 1 and p.pannes == 1


def test_un_serveur_muet_ou_trop_lent_donne_la_main_a_l_ia():
    s, _, p = combat_planifie(llm.ErreurLLM("Le serveur n'a pas répondu : délai dépassé"))
    assert appeler(p, s) is None and p.stats.echecs == 1 and len(p.stats.durees) == 1


def test_apres_deux_rounds_sans_plan_on_cesse_de_demander_pour_ce_combat():
    s, serveur, p = combat_planifie(*[llm.ErreurLLM("muet")] * PANNES_MAX)
    for _ in range(PANNES_MAX + 2):
        assert appeler(p, s) is None
    assert len(serveur.demandes) == PANNES_MAX == 2


def test_un_plan_utilisable_remet_les_pannes_a_zero():
    s, _, p = combat_planifie(llm.ErreurLLM("muet"), plan_de({"pnj": "voyou", "intention": "s'abriter"}),
                              llm.ErreurLLM("muet"))
    appeler(p, s)
    appeler(p, s)
    assert p.pannes == 0
    appeler(p, s)
    assert p.pannes == 1


def test_les_durees_et_la_mediane_se_gardent():
    s, _, p = combat_planifie(plan_de({"pnj": "voyou", "intention": "s'abriter"}),
                              plan_de({"pnj": "voyou", "intention": "s'abriter"}))
    appeler(p, s)
    appeler(p, s)
    assert len(p.stats.durees) == 2 and p.stats.mediane >= 0


def test_un_plan_complet_se_joue_dans_la_boucle_et_le_repli_se_joue_pour_les_autres():
    s, serveur, p = combat_planifie(plan_de({"pnj": "tireur", "intention": "s'abriter"}))
    s.combat.des = DesTruques(90, 50)  # le voyou (70) joue avant Kaito : il attaque et rate
    auto = CombatAuto(s.combat, planificateur=p)
    rapports = auto.avancer()
    gestes = {r.qui.nom: [e.action.geste for e in r.evenements] for r in rapports}
    assert gestes.get("Voyou") == [Geste.ATTAQUER]  # absent du plan : l'IA
    assert auto.fin() is Fin.EN_COURS


# --- Le client LLM ---------------------------------------------------------------------------------------

def test_la_requete_impose_l_outil_seulement_quand_on_le_demande():
    outils = [{"type": "function", "function": {"name": "plan_du_round"}}]
    assert "tool_choice" not in llm.requete([], outils)
    assert llm.requete([], outils, outil_impose="plan_du_round")["tool_choice"] == {
        "type": "function", "function": {"name": "plan_du_round"}}
    assert "tool_choice" not in llm.requete([], None, outil_impose="plan_du_round")  # sans outils, rien à imposer


def test_discuter_attend_la_reponse_le_delai_demande(monkeypatch):
    vus = {}

    class Reponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, *_):
            return b"{}"

    def faux_urlopen(demande, timeout):
        vus["timeout"], vus["corps"] = timeout, json.loads(demande.data)
        return Reponse()

    monkeypatch.setattr(llm.urllib.request, "urlopen", faux_urlopen)
    monkeypatch.setattr(llm.json, "load", lambda r: {})
    serveur = llm.Serveur.__new__(llm.Serveur)
    serveur.port = 8080
    serveur.discuter([], [{"type": "function", "function": {"name": "x"}}], 128, delai=25, outil_impose="x")
    assert vus["timeout"] == 25 and vus["corps"]["tool_choice"]["function"]["name"] == "x"
