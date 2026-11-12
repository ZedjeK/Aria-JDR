"""L'amorce d'une campagne : les plans de la bibliothèque, la proposition du LLM vérifiée, la mémoire remplie."""

import random

import pytest

from aria import amorce, jeu
from aria.amorce import NB_PNJ, charger_plans, proposer_amorce, tirer_plan, verifier
from aria.bibliotheque import charger
from aria.campagne import Campagne
from aria.creation import Brouillon, proposer_chiffres
from aria.generateur import choix_par_defaut
from aria.memoire import Memoire
from aria.mj import presenter
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from tests.test_univers import CYBERPUNK
from test_creation import ROLEPLAY, personnalite
from test_table import ServeurScripte

AMORCE = {
    "passe": "Yuki a grandi dans les étages bas d'Osaka. Elle pirate pour payer les soins de sa mère.",
    "lieu": "Un comptoir à nouilles sous la voie rapide, à la tombée de la nuit.",
    "situation": "Un homme en costume pose une enveloppe devant elle : la dette est due ce soir.",
    "secret": "Tanaka travaille en réalité pour la corpo qui a rendu sa mère malade.",
    "soupcon": "La dette de sa mère a été rachetée trois fois en un an.",  # les deux premières couches du secret,
    "coupable": "Tanaka ne travaille pas pour l'usurier qu'il dit servir.",  # lues seulement s'il y a une trame
    "pnj": [{"identifiant": "mere_sato", "nom": "Emi Sato", "role": "Sa mère, malade", "attitude": "L'aime, s'inquiète."},
            {"identifiant": "tanaka", "nom": "Tanaka", "role": "Recouvreur de dettes", "attitude": "Poli, sans pitié."}],
    "fils": [{"identifiant": "dette_mere", "texte": "Racheter la dette de sa mère avant la fin du mois."}],
}
PLAN = "Une dette arrive à échéance aujourd'hui, et le créancier envoie quelqu'un la réclamer."


def appel(**changements):
    return [{"name": "amorcer_campagne", "arguments": dict(AMORCE, **changements)}]


@pytest.fixture(scope="module")
def neo_tokyo():
    return charger_univers(CYBERPUNK)


@pytest.fixture
def yuki(neo_tokyo):
    b = proposer_chiffres(Brouillon(neo_tokyo), random.Random(2), "Netrunner")
    b.fixer("roleplay", ROLEPLAY | {"sexe": "femme"})
    return b.finaliser()[0]


def test_les_plans_de_la_bibliotheque(tmp_path):
    assert len(charger_plans()) == 50 and len(charger_plans("Fantasy")) == 50  # pas encore de plans de Fantasy
    plans = charger_plans("Cyberpunk")
    assert len(plans) == 65 and len(set(plans)) == 65 and len(amorce.charger_complications()) == 20
    hasard, vus = random.Random(1), tmp_path / "plans_vus.json"
    tires = [tirer_plan("Cyberpunk", hasard, vus) for _ in range(65)]
    assert sorted(tires) == sorted(plans)  # jamais deux fois le même tant qu'il en reste, d'une campagne à l'autre
    assert tirer_plan("Cyberpunk", hasard, vus) in plans  # tout a été vu : on repart de zéro
    assert len(amorce._lire_vus(vus)) == 1
    vus.write_text("pas du json", encoding="utf-8")
    assert tirer_plan("Fantasy", hasard, vus) in charger_plans()  # un fichier abîmé n'empêche pas de jouer
    assert amorce.tirer_complication(hasard) in amorce.charger_complications()


def test_l_amorce_est_verifiee():
    propre, erreurs = verifier(AMORCE, PLAN)
    assert not erreurs and propre.plan == PLAN and len(propre.pnj) == 2
    assert propre.scene.startswith("Un comptoir") and "enveloppe" in propre.scene
    for changement, attendu in (
            ({"passe": ""}, "« passe »"),
            ({"lieu": "x" * 401}, "« lieu »"),
            ({"pnj": AMORCE["pnj"][:1]}, f"de {NB_PNJ[0]} à {NB_PNJ[1]}"),
            ({"fils": []}, "« fils »"),
            ({"pnj": [dict(AMORCE["pnj"][0], identifiant="Mère Sato"), AMORCE["pnj"][1]]}, "Identifiant invalide"),
            ({"pnj": [AMORCE["pnj"][0], dict(AMORCE["pnj"][1], identifiant="mere_sato")]}, "en double"),
            ({"pnj": [AMORCE["pnj"][0], dict(AMORCE["pnj"][1], nom="x" * 41)]}, "nom"),
            ({"secret": ""}, "« secret »"),
            ({"fils": [dict(AMORCE["fils"][0], identifiant=amorce.FIL_SECRET)]}, "en double"),
            ({"fils": "une dette"}, "« fils »")):
        propre, erreurs = verifier(dict(AMORCE, **changement))
        assert propre is None and any(attendu in e for e in erreurs), changement


def test_le_llm_propose_l_amorce(neo_tokyo, yuki):
    serveur = ServeurScripte(appel(fils=[]), appel())  # une relance : il manquait un fil
    proposee = proposer_amorce(serveur, neo_tokyo, yuki, PLAN)
    assert proposee.fils[0]["identifiant"] == "dette_mere"
    demande = serveur.recus[0][0][-1]["content"]
    assert PLAN in demande and "une femme" in demande and yuki.lien in demande and "Netrunner" in demande
    assert "« fils »" in serveur.recus[1][0][-1]["content"]
    assert proposer_amorce(ServeurScripte("Hmm.", "Hmm."), neo_tokyo, yuki, PLAN) is None


def test_l_amorce_remplit_la_memoire(tmp_path):
    campagne = Campagne(tmp_path)
    campagne.ouvrir()
    proposee, _ = verifier(AMORCE, PLAN)
    proposee.ranger(Memoire(campagne), Moment(1, Periode.APRES_MIDI))
    relue = Memoire(campagne)  # relue depuis les fichiers
    assert relue.pnj["tanaka"].role == "Recouvreur de dettes" and relue.fils["dette_mere"].ouvert
    assert relue.souvenirs[0].startswith("## Avant la campagne") and "comptoir à nouilles" in relue.souvenirs[0]
    assert "Tanaka" in relue.bloc() and "Avant la campagne" in relue.bloc()
    assert any("Tanaka" in ligne for ligne in proposee.lignes())
    # Le secret : jamais montré au joueur, mais gardé pour le MJ, dans la scène et dans un fil qu'il pourra clore
    assert not any("corpo qui a rendu" in ligne for ligne in proposee.lignes())
    assert "corpo qui a rendu" in proposee.scene and "corpo qui a rendu" in relue.fils[amorce.FIL_SECRET].texte


def test_la_fiche_du_mj_dit_le_sexe_et_l_allure(yuki):
    assert "Yuki Sato, femme, Netrunner." in presenter(yuki) and "Allure : Cheveux argentés" in presenter(yuki)
    yuki.sexe = yuki.allure = ""
    assert presenter(yuki).startswith("Yuki Sato, Netrunner.") and "Allure" not in presenter(yuki)


def generation():
    return [*[[{"name": "retirer", "arguments": {"retirer": []}}]] * 3,
            *[[{"name": "renommer", "arguments": {"renommages": []}}]] * 4,
            [{"name": "trier_parcours", "arguments": {"retirer": [], "renommer": []}}],
            [{"name": "ajouter_parcours", "arguments": {"parcours": []}}]]


def nouvelle_partie(tmp_path, serveur, reponses, sortie):
    choix = choix_par_defaut(charger(), "Cyberpunk", "Osaka 2091", "Osaka sous la pluie.", 2091)
    reponses = iter(reponses)
    return jeu.Jeu(serveur, budget=128, entree=lambda _: next(reponses), sortie=sortie.append,
                   campagne=Campagne(tmp_path), choix=choix, creer=True)


def test_une_nouvelle_campagne_a_son_amorce(tmp_path):
    serveur = ServeurScripte(*generation(), personnalite(), appel(lieu="Un parking désert."), appel(),
                             "La pluie tombe sur Osaka.")
    sortie = []
    # tout proposer, valider le personnage, laisser piocher un plan, en demander un autre, le garder
    partie = nouvelle_partie(tmp_path, serveur, ["tout", "", "", "r", "", "quitter"], sortie)
    plans = [ligne.split("\n")[1] for ligne in sortie if ligne.startswith("\nPlan : ")]
    assert len(plans) == 2 and plans[0] != plans[1] and all("Complication : " in plan for plan in plans)
    assert (tmp_path.parent / jeu.PLANS_VUS).is_file()  # les plans piochés sont retenus, à côté des campagnes
    assert "comptoir à nouilles" in partie.table.scene and "parking" not in partie.table.scene
    assert "comptoir à nouilles" in partie.table.messages[0]["content"]  # le MJ connaît la scène d'ouverture
    assert "Tanaka" in partie.session.memoire.pnj["tanaka"].nom
    assert Campagne(tmp_path).sauvegarde.is_file()  # sauvegardée dès la création
    partie.jouer()
    # À la reprise : plus de scène écrite, la mémoire dit d'où on vient
    reprise = jeu.Jeu(ServeurScripte(), budget=128, entree=lambda _: "quitter", sortie=lambda _: None,
                      campagne=Campagne(tmp_path))
    assert reprise.reprise and reprise.session.personnage.nom == "Yuki Sato" and reprise.table.scene == ""
    assert "Avant la campagne" in reprise.table.messages[0]["content"]


def test_l_idee_du_joueur_sert_de_plan(tmp_path):
    serveur = ServeurScripte(*generation(), personnalite(), appel(), "La pluie tombe.")
    sortie = []
    nouvelle_partie(tmp_path, serveur, ["tout", "", "Yuki se réveille dans une clinique inconnue.", ""], sortie)
    assert "clinique inconnue" in serveur.recus[-1][0][-1]["content"]
    assert any("Plan : Yuki se réveille" in ligne and "Complication" not in ligne for ligne in sortie)


def test_sans_amorce_valide_le_mj_ouvre_seul(tmp_path):
    serveur = ServeurScripte(*generation(), personnalite(), "Hmm.", "Hmm.")
    sortie = []
    partie = nouvelle_partie(tmp_path, serveur, ["tout", "", ""], sortie)
    assert partie.table.scene == "" and partie.session.memoire.pnj == {}
    assert any("ouvrira la campagne lui-même" in ligne for ligne in sortie)


def test_la_mort_s_accorde(tmp_path):
    serveur = ServeurScripte(*generation(), personnalite(), appel())
    sortie = []
    partie = nouvelle_partie(tmp_path, serveur, ["tout", "", "", ""], sortie)
    assert partie.session.personnage.sexe in ("femme", "homme")
    partie.session.personnage.sexe = "femme"
    partie.mort = lambda: True
    partie.jouer()
    assert any("Yuki Sato est morte." in ligne for ligne in sortie)
    assert amorce.TITRE in partie.session.memoire.souvenirs[0]
