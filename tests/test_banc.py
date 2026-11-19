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


def test_quatre_vingt_six_situations_dont_vingt_trois_pieges():
    assert len(SITUATIONS) == 86
    assert sum(s.piege for s in SITUATIONS) == 23
    assert len({s.nom for s in SITUATIONS}) == 86
    assert len({s.joueur for s in SITUATIONS}) == 86  # le faux serveur les reconnaît à la phrase du joueur
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


def test_pas_assez_de_vram_le_banc_dit_combien_il_en_faut():
    from pathlib import Path

    from aria import banc, optimiseur
    modele = optimiseur.Modele("Test", Path("test.gguf"), 12 * optimiseur.GIO, 32768, False, 262144)
    compte_rendu = banc.qualifier_modele(modele, 13 * optimiseur.GIO)  # aucun palier ne tient : aucun serveur lancé
    assert not compte_rendu["reussi"]
    assert compte_rendu["raison"] == "pas assez de VRAM libre : il en faut 13.6 Gio, 13.0 Gio libres"
    assert "aucune carte NVIDIA" in banc.qualifier_modele(modele, None)["raison"]


# --- Le combat à pied que le code mène ---------------------------------------------------------------------

class FauxRecit(FauxServeur):
    """Un faux serveur qui raconte ce qu'on lui donne : la narration écrite pour chaque situation de récit."""

    def __init__(self, narrations: dict[str, str], scenarios=None):
        super().__init__(scenarios or {})
        self.narrations, self.outils_recus = narrations, []

    def discuter(self, messages, outils=None, budget=None, **options):
        self.outils_recus.append(outils)
        reponse = super().discuter(messages, outils, budget)
        joueur = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        nom = next(s.nom for s in SITUATIONS if s.joueur == joueur)
        if nom in self.narrations and not reponse["choices"][0]["message"].get("tool_calls"):
            reponse["choices"][0]["message"]["content"] = self.narrations[nom]
        return reponse


BIEN = {
    "recit_rien": "Le ganger fonce, mais Kaito s'écarte d'un pas. Un deuxième ganger se plante derrière un abri et tire à côté.",
    "recit_chute": "Le tir de Kaito part, sec et net. Le ganger lâche un râle et s'effondre sur le bitume.",
    "recit_fuite": "Le ganger blêmit, regarde ses compagnons, puis détale vers la sortie sans demander son reste. Ses pas claquent un instant, puis le silence revient.",
    "recit_blessure": "La lame file et entaille Kaito au flanc. La douleur monte, vive, mais il tient debout.",
    "recit_joueur": "Kaito plonge derrière un abri. Le ganger tire, et la balle claque contre le métal.",
    "recit_arme": "Le ganger s'élance trop vite, son pied glisse. Le couteau lui échappe des doigts et tinte au sol.",
}


@pytest.mark.parametrize("nom", list(BIEN))
def test_un_bon_recit_passe_ses_pieges(nom):
    partie = jouer(FauxRecit(BIEN), situation(nom), budget=0, graine=1)
    assert partie.reussie, partie.raisons
    assert partie.appels == [] and partie.narration == BIEN[nom]


def test_le_recit_se_joue_sans_outils_et_avec_une_reflexion_courte():
    serveur = FauxRecit(BIEN)
    jouer(serveur, situation("recit_rien"), budget=512, graine=1)
    assert serveur.outils_recus == [None] and serveur.budgets == [128]


@pytest.mark.parametrize("nom, narration, raison", [
    ("recit_rien", "Le ganger frappe, il perd 4 PV.", "des chiffres dans le récit"),
    ("recit_rien", "Le ganger s'effondre, mort sur le coup. Kaito soupire.", "interdit dans le récit"),
    ("recit_rien", "Un ganger sort un fusil d'assaut. Kaito recule. Il tire.", "interdit dans le récit"),
    ("recit_chute", "Le ganger vacille. Il serre son couteau. Kaito le tient en joue.", "le récit oublie un fait"),
    ("recit_fuite", "Le ganger hésite. Il regarde Kaito. Il serre les dents.", "le récit oublie un fait"),
    ("recit_blessure", "Kaito est touché, 4 dégâts. Il serre les dents.", "des chiffres dans le récit"),
    ("recit_joueur", "Kaito se met à couvert. Puis Kaito tire sur le ganger. Le ganger tombe.", "interdit dans le récit"),
    ("recit_arme", "Le ganger rate. Il sort alors un pistolet. Kaito esquive.", "interdit dans le récit"),
    ("recit_rien", "Un seul mot.", "phrases au lieu de 2 à 7"),
])
def test_un_mauvais_recit_echoue_au_piege_qu_il_rate(nom, narration, raison):
    partie = jouer(FauxRecit({nom: narration}), situation(nom), budget=0, graine=1)
    assert not partie.reussie and any(raison in r for r in partie.raisons), partie.raisons


def test_un_serveur_muet_donne_un_recit_raté():
    class Muet(FauxServeur):
        def discuter(self, messages, outils=None, budget=None, **options):
            from aria import llm
            raise llm.ErreurLLM("muet")

    partie = jouer(Muet({}), situation("recit_fuite"), budget=0, graine=1)
    assert not partie.reussie and partie.raisons == ["aucun récit"]


def test_les_verifications_de_narration():
    assert banc.sans_chiffre("Rien à signaler.") is None and "chiffres" in banc.sans_chiffre("4 dégâts")
    assert banc.sans("mort")("Il vit.") is None and "mort" in banc.sans("mort")("Il est MORT.")
    assert banc.avec_un_de("tombe")("Il tombe.") is None and banc.avec_un_de("tombe")("Il rit.")
    assert banc.avec_un_de("s'éloigne")("Il s’éloigne.") is None  # l'apostrophe typographique du modèle
    assert banc.sans("s'enfuit")("Il s’enfuit.")
    assert banc.phrases(2, 3)("Un. Deux.") is None and "1 phrases" in banc.phrases(2, 3)("Un.")
    assert banc.phrases(2, 3)("Un ! Deux ? Trois… Quatre. Cinq.")


def test_le_declenchement_d_un_combat_se_joue_avec_les_outils_d_un_combat_a_pied():
    serveur = FauxServeur({"ganger": [("creer_pnj", {"identifiant": "ganger", "nom": "Ganger", "camp": "ennemis",
                                                      "combat": 45, "pv": 10, "arme": "Couteau", "dexterite": 50}),
                                      ("debut_combat", {"pnj": ["ganger"]})]})
    partie = jouer(serveur, situation("ganger"), budget=0, graine=1)
    assert partie.reussie, partie.raisons
    assert not any("erreur" in trace for trace in partie.appels)


def _combat_au(nom, **arguments):
    """Le MJ crée le ganger puis ouvre le combat avec ces arguments, dans la situation `nom`."""
    pnj = ("creer_pnj", {"identifiant": "ganger", "nom": "Ganger", "camp": "ennemis", "combat": 45, "pv": 10,
                         "arme": "Couteau", "dexterite": 50})
    return jouer(FauxServeur({nom: [pnj, ("debut_combat", {"pnj": ["ganger"]} | arguments)]}), situation(nom),
                 budget=0, graine=1)


@pytest.mark.parametrize("nom, bons, mauvais", [
    ("lieu_bar", {"lieu": "bar"}, {}),
    ("lieu_toit", {"lieu": "toit", "decor": "dégagé"}, {"lieu": "toit"}),
    ("lieu_parking", {"lieu": "parking", "decor": "fortifié"}, {"lieu": "parking", "decor": "encombré"}),
])
def test_le_mj_donne_le_lieu_et_le_decor_de_la_scene(nom, bons, mauvais):
    reussie = _combat_au(nom, **bons)
    assert reussie.reussie, reussie.raisons
    assert not any("erreur" in trace for trace in reussie.appels)
    ratee = _combat_au(nom, **mauvais)  # sans argument : une ruelle encombrée, le défaut
    assert not ratee.reussie and any("lieu" in r for r in ratee.raisons)


def test_le_prompt_dit_au_mj_de_donner_le_lieu_et_le_decor():
    from tests.test_combat_partie import systeme
    from tests.test_outils import session
    texte = systeme(session())
    assert "`lieu`" in texte and "`decor`" in texte and "« fortifié »" in texte and "« dégagé »" in texte


def test_parler_et_autre_action_veulent_un_jet_de_base():
    jet = ("test_competence", {"competence": "Arnaque", "difficulte": "normale"})
    assert jouer(FauxServeur({"parler": [jet]}), situation("parler"), budget=0, graine=1).reussie
    sans_jet = jouer(FauxServeur({}), situation("benne"), budget=0, graine=1)
    assert not sans_jet.reussie and "attendu" in sans_jet.raisons[0]


def test_aucun_outil_d_attaque_pendant_parler():
    jouee = jouer(FauxServeur({"parler": [("attaquer", {"attaquant": "joueur", "cible": "ganger"})]}),
                  situation("parler"), budget=0, graine=1)
    assert not jouee.reussie and any("Le code mène ce combat" in trace for trace in jouee.appels)


def test_la_fuite_demande_fin_combat_puis_la_poursuite_du_joueur_par_le_ganger():
    fin = ("fin_combat", {"moments_forts": "Kaito s'enfuit."})
    poursuite = ("debut_poursuite", {"fuyard": "joueur", "poursuivants": ["ganger"], "zone": "Centre-ville"})
    assert jouer(FauxServeur({"fuite": [fin, poursuite]}), situation("fuite"), budget=0, graine=1).reussie
    sans_fin = jouer(FauxServeur({"fuite": [poursuite]}), situation("fuite"), budget=0, graine=1)
    assert not sans_fin.reussie and any("avant fin_combat" in r or "attendu" in r for r in sans_fin.raisons)
    mal = ("debut_poursuite", {"fuyard": "joueur", "poursuivants": ["autre"], "zone": "Centre-ville"})
    assert not jouer(FauxServeur({"fuite": [fin, mal]}), situation("fuite"), budget=0, graine=1).reussie


def test_les_situations_de_combat_a_pied_sont_jouees_dans_le_mode_du_jeu_reel():
    a_pied = {s.nom for s in SITUATIONS if s.par_le_code}
    assert {"ganger", "embuscade", "racket", "patronne", "croisee", "tirs", "parler", "benne", "fuite"} <= a_pied
    assert {s.nom for s in SITUATIONS if s.recit} == {n for n in BIEN}
    assert "grenade" not in a_pied and "drone" not in a_pied  # zones et drones : combat classique
