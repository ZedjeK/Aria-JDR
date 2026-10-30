"""Les outils du MJ, appelés comme le ferait le LLM : par leur nom, avec des arguments JSON."""

import json

import pytest

from aria.des import DesTruques
from aria.outils import OUTILS, Session
from aria.personnage import Etat
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from tests.test_univers import CYBERPUNK, fiche_kaito


def session(*des, **options) -> Session:
    """Kaito à Néo-Tokyo (23 PV, Esquive 50, Piratage 75), avec des dés truqués."""
    univers = charger_univers(CYBERPUNK)
    kaito = univers.creer_personnage("Netrunner", **fiche_kaito())
    options.setdefault("arme", "Pistolet lourd Arasaka")
    options.setdefault("armure", "Veste renforcée")
    return Session(univers, kaito, DesTruques(*des), **options)


def ganger(s: Session, identifiant="ganger", **profil):
    arguments = {"identifiant": identifiant, "nom": "Ganger", "camp": "ennemis", "combat": 45, "pv": 10,
                 "arme": "Couteau", "dexterite": 55} | profil
    assert "erreur" not in s.appeler("creer_pnj", arguments)


# --- Catalogue et garde-fous ------------------------------------------------------------------

def test_schemas_au_format_openai():
    schemas = session().schemas()
    assert {s["function"]["name"] for s in schemas} == set(OUTILS)
    for schema in schemas:
        assert schema["type"] == "function"
        assert schema["function"]["parameters"]["type"] == "object"
        json.dumps(schema)  # sérialisable tel quel pour l'API


def test_les_competences_sont_proposees_avec_les_noms_de_l_univers():
    schema = next(s for s in session().schemas() if s["function"]["name"] == "test_competence")
    enum = schema["function"]["parameters"]["properties"]["competence"]["enum"]
    assert "Piratage" in enum and "Technologie" not in enum
    assert "Cybernétique" in enum


@pytest.mark.parametrize(
    "nom, arguments, morceau_d_erreur",
    [
        ("lancer_un_d20", {}, "Outil inconnu"),
        ("test_competence", {"competence": "Piratage"}, "obligatoire manquant : « difficulte »"),
        ("test_competence", {"competence": "Piratage", "difficulte": "-35"}, "doit être l'une de ces valeurs"),
        ("test_competence", {"competence": "Être génial", "difficulte": "normale"}, "doit être l'une"),
        ("test_competence", {"competence": "Piratage", "difficulte": "normale", "bonus": 50}, "Paramètre inconnu"),
        ("creer_pnj", {"identifiant": "x", "nom": "X", "camp": "ennemis", "combat": 200, "pv": 10}, "au plus 85"),
        ("creer_pnj", {"identifiant": "x", "nom": "X", "camp": "ennemis", "combat": "45", "pv": 10}, "integer"),
        ("attaquer", {"attaquant": "joueur", "cible": "fantome"}, "doit être l'une"),
        ("attaquer", {"attaquant": "joueur", "cible": "joueur"}, "pas soi-même"),
        ("fin_de_tour", {}, "Aucun combat en cours"),
        ("forcer_jet", {}, "Aucun test à forcer"),
    ],
)
def test_appels_refuses_sans_planter(nom, arguments, morceau_d_erreur):
    resultat = session().appeler(nom, arguments)
    assert morceau_d_erreur in resultat["erreur"]


def test_arguments_en_texte_json():
    s = session(30)
    assert s.appeler("test_competence", '{"competence": "Piratage", "difficulte": "normale"}')["reussi"]
    assert "JSON invalide" in s.appeler("test_competence", "{pas du json")["erreur"]


def test_le_journal_garde_chaque_appel():
    s = session(30)
    s.appeler("test_competence", {"competence": "Piratage", "difficulte": "normale"})
    s.appeler("lancer_un_d20")
    assert [e["outil"] for e in s.journal] == ["test_competence", "lancer_un_d20"]
    assert "erreur" in s.journal[1]["resultat"]


# --- Hors combat ------------------------------------------------------------------------------

def test_test_de_competence():
    s = session(70)
    r = s.appeler("test_competence", {"competence": "Piratage", "difficulte": "difficile", "pourquoi": "Ouvrir la porte"})
    assert (r["jet"], r["valeur"], r["degre"], r["reussi"]) == (70, 55, "échec", False)


def test_nom_de_socle_accepte_aussi():
    r = session(10).appeler("test_competence", {"competence": "Technologie", "difficulte": "normale"})
    assert r["competence"] == "Piratage" and r["reussi"]


def test_reussite_cochee_pour_la_progression():
    s = session(30)
    s.appeler("test_competence", {"competence": "Piratage", "difficulte": "normale"})
    assert s.personnage.competences_cochees == {"Technologie"}


def test_forcer_le_jet():
    s = session(90, 40)
    s.appeler("test_competence", {"competence": "Piratage", "difficulte": "normale"})
    r = s.appeler("forcer_jet")
    assert r["reussi"] and not r["consequence_grave"]
    assert "erreur" in s.appeler("forcer_jet")  # une seule fois


def test_test_de_caracteristique():
    r = session(80).appeler("test_caracteristique", {"caracteristique": "Intelligence", "difficulte": "normale"})
    assert (r["valeur"], r["reussi"]) == (75, False)


def test_choc():
    r = session(70, 6, 2, 4).appeler("choc", {"choc": "TORTURE"})
    assert (r["gravite"], r["perte"], r["sante_mentale"]) == ("serieux", 6, 44)
    assert r["crise"] == {"type": "paralysie", "rounds": 4}


def test_choc_sans_test_dans_un_monde_impitoyable():
    r = session().appeler("choc", {"choc": "CADAVRE_INCONNU"})
    assert r["test"] is False


def test_soins_par_un_pnj_puis_repos():
    s = session(40, 3, moment=Moment(1, Periode.APRES_MIDI))
    s.personnage.pv = 5
    s.appeler("creer_pnj", {"identifiant": "doc", "nom": "Doc Mori", "camp": "neutres", "combat": 20, "pv": 10,
                            "competences": {"Médecine": 70}})
    assert s.appeler("soigner", {"soigneur": "doc"})["pv"] == 8
    assert s.appeler("repos", {"type": "moyen"})["pv"] == 19  # + la moitié de 23
    assert "erreur" in s.appeler("repos", {"type": "long"})  # pas la nuit
    s.appeler("avancer_temps")
    assert s.appeler("repos", {"type": "long"})["pv"] == 23


def test_competence_de_pnj_hors_bornes():
    r = session().appeler("creer_pnj", {"identifiant": "doc", "nom": "Doc", "camp": "neutres", "combat": 20,
                                        "pv": 10, "competences": {"Médecine": 150}})
    assert "va de 0 à 90" in r["erreur"]


def test_sante_mentale_et_jalon():
    s = session(2, 5, 3, 3, 4)
    s.personnage.sm = 30
    assert s.appeler("recuperer_sante_mentale", {"source": "discussion"})["sante_mentale"] == 32
    assert "erreur" in s.appeler("recuperer_sante_mentale", {"source": "thérapie"})  # pas la nuit
    s.moment = Moment(1, Periode.NUIT)
    assert s.appeler("recuperer_sante_mentale", {"source": "thérapie"})["sm_gagnee"] == 6  # critique : 3 + 3
    r = s.appeler("jalon", {"jalon": "objectif"})
    assert (r["sm_gagnee"], r["xp_gagnee"]) == (4, 0)


def test_etat():
    r = session().appeler("etat")
    assert r["joueur"]["pv"] == 23
    assert r["joueur"]["arme"] == "Pistolet lourd Arasaka"
    assert r["joueur"]["munitions"] == 8
    assert "combat" not in r


# --- Combat -----------------------------------------------------------------------------------

def test_un_combat_complet():
    # Kaito tire (30 : réussite, 1d10 = 6, +1 de l'Arasaka), le ganger réussit sa Constitution (10),
    # puis le ganger frappe (82 : échec) et Kaito esquive (26).
    s = session(30, 6, 10, 82, 26)
    ganger(s)
    debut = s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert debut["ordre_initiative"] == ["Kaito", "Ganger"]
    tir = s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    touche = dict(tir["touche"])
    assert touche.pop("test_constitution")["reussi"]
    assert touche == {"qui": "Ganger", "degats_bruts": 7, "armure": 0, "degats": 7, "pv": 3,
                      "blessure_grave": True, "etat": "actif"}
    assert "pas le tour de Ganger" in s.appeler("attaquer", {"attaquant": "ganger", "cible": "joueur"})["erreur"]
    assert s.appeler("fin_de_tour")["au_tour_de"] == "ganger"
    coup = s.appeler("attaquer", {"attaquant": "ganger", "cible": "joueur", "defense": "esquive"})
    assert coup["issue"] == "défenseur"
    assert s.appeler("etat")["combat"]["round"] == 1
    fin = s.appeler("fin_de_tour")
    assert (fin["round"], fin["nouveau_round"], fin["au_tour_de"]) == (2, True, "joueur")
    assert "Ganger : 3/5 PV, actif, blessure grave" in fin["fiche"] and "## Round 1" in fin["fiche"]
    assert "etats" in s.appeler("fin_combat", {"moments_forts": "Kaito blesse le ganger, qui rate son coup."})
    assert "erreur" in s.appeler("fin_de_tour")


def test_budget_du_round_respecte():
    s = session(30, 6, 10)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    r = s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    assert "budget du round" in r["erreur"]


def test_viser_recharger_degainer():
    s = session(80)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    r = s.appeler("action_combat", {"qui": "joueur", "action": "viser"})
    assert r["budget_restant"]["action mineure"] == 0
    assert s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})["attaque"]["valeur"] == 70
    assert "erreur" in s.appeler("action_combat", {"qui": "joueur", "action": "deplacer"})  # a visé
    s.appeler("fin_de_tour")
    s.appeler("fin_de_tour")  # le ganger ne fait rien : retour au round 2, au tour de Kaito
    r = s.appeler("action_combat", {"qui": "joueur", "action": "degainer", "arme": "Couteau"})
    assert s.joueur.arme.nom == "Couteau" and "munitions" not in r


def test_embuscade_et_surprise():
    s = session(10, 40)
    ganger(s)
    assert s.appeler("embuscade", {"discretion_agresseurs": 60})["joueur_surpris"]
    s.appeler("debut_combat", {"pnj": ["ganger"], "surpris": "joueur"})
    assert "ne peut pas agir" in s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})["erreur"]


def test_mourant_stabilise_et_destin():
    s = session(3, 60)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    g = s.pnj["ganger"].fiche
    g.pv, g.etat = 0, Etat.MOURANT
    s.personnage.competences["Médecine"] = 40
    assert s.appeler("stabiliser", {"soigneur": "joueur", "mourant": "ganger"})["etat"] == "stable"
    s.personnage.etat, s.personnage.pv = Etat.MORT, 0
    r = s.appeler("point_de_destin", {"usage": "laisse_pour_mort"})
    assert (r["etat"], r["points_destin_restants"]) == ("stable", 1)


def test_deux_combats_d_affilee():
    s = session(30, 6, 10, 30, 3)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    s.appeler("fin_combat", {"moments_forts": "Kaito abat le ganger."})
    ganger(s, "ganger2")
    s.appeler("debut_combat", {"pnj": ["ganger2"]})
    assert "erreur" not in s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger2"})  # budget remis à neuf


# --- Le tour de parole, la fiche du combat et les souvenirs ----------------------------------

def combat_en_cours(tmp_path=None, *des):
    from aria.campagne import Campagne
    s = session(*des, campagne=Campagne(tmp_path) if tmp_path else None)
    ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    return s


def test_le_tour_du_joueur_ne_se_saute_pas():
    s = combat_en_cours()
    r = s.appeler("fin_de_tour")
    assert "rends-lui la main" in r["erreur"]
    assert s.appeler("fin_de_tour", {"passe": True})["au_tour_de"] == "ganger"


def test_la_consigne_dit_qui_joue():
    s = combat_en_cours(None, 10)  # 10 : la Constitution de Kaito, mourant, à la fin du round 1
    debut = next(e["resultat"] for e in s.journal if e["outil"] == "debut_combat")
    assert debut["au_tour_de"] == "joueur" and "Ne joue pas son tour à sa place" in debut["consigne"]
    assert s.appeler("etat")["combat"]["au_tour_de"] == "Kaito"
    r = s.appeler("fin_de_tour", {"passe": True})
    assert "C'est au tour de Ganger (ganger)" in r["consigne"] and "hors de combat" not in r["consigne"]
    s.personnage.etat = Etat.MOURANT
    r = s.appeler("fin_de_tour")  # round 2 : Kaito ne peut plus agir, on passe directement au ganger
    assert r["au_tour_de"] == "ganger" and "hors de combat" in r["consigne"]


def test_la_fiche_est_ecrite_a_chaque_round(tmp_path):
    s = combat_en_cours(tmp_path, 80)
    s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    s.appeler("fin_de_tour")
    assert not (tmp_path / "combat.md").exists()  # le round n'est pas fini
    s.appeler("fin_de_tour")
    fiche = (tmp_path / "combat.md").read_text(encoding="utf-8")
    assert fiche.startswith("# Combat — round 2")
    assert "- → Kaito : 23/23 PV" in fiche and "⚔️ Kaito attaque Ganger : 80" in fiche and "  - → Raté." in fiche


def test_fin_combat_verse_le_combat_dans_les_souvenirs(tmp_path):
    s = combat_en_cours(tmp_path, 80)
    s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    s.appeler("fin_de_tour")
    s.appeler("fin_de_tour")
    assert "erreur" in s.appeler("fin_combat", {"moments_forts": "  "})
    assert "Trop long" in s.appeler("fin_combat", {"moments_forts": "Bla. " * 200})["erreur"]
    r = s.appeler("fin_combat", {"moments_forts": "Kaito rate son tir, le ganger s'enfuit sous la pluie."})
    souvenirs = (tmp_path / "souvenirs.md").read_text(encoding="utf-8")
    assert souvenirs.startswith("# Souvenirs de la campagne")
    assert "## Jour 1, matin — Combat contre Ganger (2 rounds)" in souvenirs
    assert "le ganger s'enfuit sous la pluie." in souvenirs and "- Ganger : actif, 10/10 PV" in souvenirs
    assert r["souvenir"] in souvenirs
    assert not (tmp_path / "combat.md").exists()  # la fiche est effacée une fois le souvenir écrit
    assert s.combat is None


def test_si_le_souvenir_ne_s_ecrit_pas_le_combat_reste(tmp_path, monkeypatch):
    s = combat_en_cours(tmp_path, 80)
    s.appeler("attaquer", {"attaquant": "joueur", "cible": "ganger"})
    s.appeler("fin_de_tour")
    s.appeler("fin_de_tour")

    def disque_plein(_):
        raise OSError("disque plein")
    monkeypatch.setattr(s.campagne, "ajouter_souvenir", disque_plein)
    assert "disque plein" in s.appeler("fin_combat", {"moments_forts": "Kaito rate."})["erreur"]
    assert s.combat is not None and (tmp_path / "combat.md").exists()


def test_ouvrir_une_campagne_efface_un_combat_interrompu(tmp_path):
    from aria.campagne import Campagne
    campagne = Campagne(tmp_path / "neo-tokyo")
    campagne.ecrire_combat("# Combat — round 3\n")
    campagne.ajouter_souvenir("## Un souvenir")
    campagne.ouvrir()
    assert not campagne.combat.exists() and campagne.souvenirs.exists()


def test_un_pnj_hors_du_combat_est_refuse_puis_rejoint():
    s = combat_en_cours(None, 80)
    ganger(s, "tireur", nom="Tireur", arme="Pistolet lourd")
    r = s.appeler("attaquer", {"attaquant": "joueur", "cible": "tireur"})
    assert "ne fait pas partie du combat" in r["erreur"] and "rejoindre_combat" in r["erreur"]
    r = s.appeler("rejoindre_combat", {"pnj": ["tireur"]})
    assert r["ordre_initiative"] == ["Kaito", "Ganger", "Tireur"] and r["au_tour_de"] == "joueur"
    assert "erreur" not in s.appeler("attaquer", {"attaquant": "joueur", "cible": "tireur"})
    assert "déjà dans le combat" in s.appeler("rejoindre_combat", {"pnj": ["tireur"]})["erreur"]


def test_un_identifiant_deja_pris_propose_un_identifiant_libre():
    s = session()
    ganger(s)
    r = s.appeler("creer_pnj", {"identifiant": "ganger", "nom": "Ganger au pistolet", "camp": "ennemis",
                                "combat": 50, "pv": 10})
    assert "PNJ existants : ganger (Ganger)" in r["erreur"] and "« ganger_2 »" in r["erreur"]


def test_un_test_reussi_rappelle_qu_il_ne_se_relance_pas():
    s = session(30, 95)
    assert "ne se relance pas" in s.appeler("test_competence", {"competence": "Piratage", "difficulte": "normale"})["consigne"]
    assert "consigne" not in s.appeler("test_caracteristique", {"caracteristique": "Force", "difficulte": "normale"})


# --- Mémoire de la campagne -------------------------------------------------------------------

def test_le_mj_note_pnj_et_fils(tmp_path):
    from aria.campagne import Campagne
    s = session(campagne=Campagne(tmp_path))
    r = s.appeler("noter_pnj", {"identifiant": "doc_mori", "nom": "Doc Mori", "role": "charcudoc",
                                "attitude": "amical"})
    assert r["etat"] == "vivant" and "Doc Mori (doc_mori)" in (tmp_path / "pnj.md").read_text(encoding="utf-8")
    assert "Identifiant invalide" in s.appeler("ouvrir_fil", {"identifiant": "Dette Mori", "fil": "…"})["erreur"]
    assert "erreur" not in s.appeler("ouvrir_fil", {"identifiant": "dette_mori", "fil": "Mori doit un service."})
    schema = OUTILS["clore_fil"].parametres(s)["properties"]["identifiant"]
    assert schema["enum"] == ["dette_mori"]  # le MJ ne peut clore qu'un fil ouvert
    r = s.appeler("clore_fil", {"identifiant": "dette_mori", "issue": "Mori a recousu Kaito."})
    assert r["issue"] == "Mori a recousu Kaito." and "- Issue : Mori a recousu Kaito." in \
        (tmp_path / "fils.md").read_text(encoding="utf-8")


def test_fin_scene_va_dans_les_souvenirs(tmp_path):
    from aria.campagne import Campagne
    s = session(campagne=Campagne(tmp_path))
    assert "titre" in s.appeler("fin_scene", {"titre": "  ", "moments_forts": "Rien."})["erreur"]
    r = s.appeler("fin_scene", {"titre": "Chez Doc Mori", "moments_forts": "Mori recoud Kaito et lui doit un service."})
    assert r["souvenir"].startswith("## Jour 1, matin — Chez Doc Mori")
    assert "Mori recoud Kaito" in (tmp_path / "souvenirs.md").read_text(encoding="utf-8")
    assert s.memoire.souvenirs == [r["souvenir"].strip()]


def test_pas_de_fin_de_scene_en_plein_combat():
    s = combat_en_cours(None, 80)
    assert "fin_combat" in s.appeler("fin_scene", {"titre": "La ruelle", "moments_forts": "Kaito fuit."})["erreur"]


def test_un_pnj_mort_reste_mort():
    s = combat_en_cours(None, 80)
    s.appeler("noter_pnj", {"identifiant": "ganger", "nom": "Ganger", "role": "voyou", "attitude": "hostile"})
    s.pnj["ganger"].fiche.etat = Etat.MORT
    assert "erreur" not in s.appeler("fin_combat", {"moments_forts": "Kaito abat le ganger."})
    assert s.memoire.est_mort("ganger")
    s.pnj.clear()
    assert "est mort" in s.appeler("creer_pnj", {"identifiant": "ganger", "nom": "Ganger", "camp": "ennemis",
                                                 "combat": 45, "pv": 10})["erreur"]
