"""La création de personnage guidée (REGLES.md 5) : le moteur, « tout proposer » et le dialogue en texte."""

import json
import random

import pytest

from aria import jeu
from aria.bibliotheque import charger
from aria.campagne import Campagne
from aria.creation import (
    Brouillon,
    EtapeInvalide,
    proposer_caracteristiques,
    proposer_chiffres,
    proposer_personnalite,
    tout_proposer,
)
from aria.creation_texte import Abandon, Guide, lire_caracteristiques, lire_points
from aria.generateur import choix_par_defaut, generer
from aria.personnage import Caracteristique as C
from aria.univers import charger_univers, univers_depuis_dict
from tests.test_univers import CYBERPUNK
from test_table import ServeurScripte

ROLEPLAY = {"nom": "Yuki Sato", "motivation": "Racheter la dette de sa mère.", "lien": "Sa mère, malade.",
            "defaut": "Ne sait pas dire non à un job.", "allure": "Cheveux argentés, imper trop grand."}


@pytest.fixture(scope="module")
def neo_tokyo():
    return charger_univers(CYBERPUNK)


@pytest.fixture(scope="module")
def fantasy():
    b = charger()
    return univers_depuis_dict(generer(b, choix_par_defaut(b, "Fantasy", "Valombre", "Un royaume.")))


def personnalite(**changements):
    return [{"name": "proposer_personnage", "arguments": dict(ROLEPLAY, **changements)}]


# --- Ce que le code propose -------------------------------------------------------------------------

@pytest.mark.parametrize("parcours", sorted(charger_univers(CYBERPUNK).parcours))
def test_tout_proposer_donne_un_personnage_valide(neo_tokyo, parcours):
    b = proposer_chiffres(Brouillon(neo_tokyo), random.Random(3), parcours)
    b.fixer("roleplay", ROLEPLAY)
    perso, depart = b.finaliser()
    assert perso.parcours == parcours and perso.nom == "Yuki Sato" and len(perso.objets) == 2
    assert sum(b.caracteristiques.values()) == 300 and sum(b.points_parcours.values()) == 300
    assert sum(b.points_personnels.values()) == 100
    assert not any("Ni Corps à corps" in a for a in b.avertissements())  # le code lui donne toujours une défense


def test_les_caracteristiques_suivent_le_parcours(neo_tokyo):
    solo = Brouillon(neo_tokyo, parcours="Solo")
    netrunner = Brouillon(neo_tokyo, parcours="Netrunner")
    c_solo, c_net = proposer_caracteristiques(solo), proposer_caracteristiques(netrunner)
    assert c_solo[C.FORCE] > c_net[C.FORCE] and c_net[C.INTELLIGENCE] > c_solo[C.INTELLIGENCE]
    for valeurs in (c_solo, c_net):
        assert sum(valeurs.values()) == 300 and all(20 <= v <= 80 for v in valeurs.values())
        assert valeurs[C.CONSTITUTION] >= 40


def test_la_magie_dans_un_univers_qui_l_a(fantasy):
    mage = next(p for p, competences in fantasy.parcours.items() if "Magie" in competences)
    b = proposer_chiffres(Brouillon(fantasy), random.Random(5), mage)
    assert len(b.domaines) == 2 and b.valeur("Magie") <= 50
    b.fixer("roleplay", ROLEPLAY)
    perso, depart = b.finaliser()
    assert perso.domaines == b.domaines and depart is None  # pas encore de listes de départ en Fantasy


# --- Les vérifications --------------------------------------------------------------------------------

def test_les_etapes_sont_verifiees(neo_tokyo):
    b = Brouillon(neo_tokyo)
    with pytest.raises(EtapeInvalide, match="Parcours inconnu"):
        b.fixer("parcours", "Astronaute")
    b.fixer("parcours", "Netrunner")
    with pytest.raises(EtapeInvalide, match="300 points"):
        b.fixer("caracteristiques", {c: 60 for c in C})
    with pytest.raises(EtapeInvalide, match="de 20 à 80"):
        b.fixer("caracteristiques", {C.FORCE: 90, C.CONSTITUTION: 10, C.DEXTERITE: 50, C.INTELLIGENCE: 50,
                                     C.VOLONTE: 50, C.PRESENCE: 50})
    b.fixer("caracteristiques", {c: 50 for c in C})
    with pytest.raises(EtapeInvalide, match="pas de points de parcours"):
        b.fixer("points_parcours", {"Médecine": 300})
    with pytest.raises(EtapeInvalide, match="dépasserait 75"):
        b.fixer("points_parcours", {"Technologie": 80, "Investigation": 220})
    with pytest.raises(EtapeInvalide, match="de 1 à 40"):
        b.fixer("roleplay", dict(ROLEPLAY, nom="x" * 41))


def test_changer_de_parcours_efface_ce_qui_en_depend(neo_tokyo):
    b = proposer_chiffres(Brouillon(neo_tokyo), random.Random(1), "Solo")
    b.fixer("parcours", "Idol")
    assert b.points_parcours == {} and b.equipement == {}


def test_l_avertissement_sans_defense(neo_tokyo):
    from dataclasses import replace
    sans_defense = [c if c != "Esquive" else "Arts" for c in neo_tokyo.parcours["Salaryman"]]
    univers = replace(neo_tokyo, parcours=dict(neo_tokyo.parcours, Salaryman=sans_defense))
    b = Brouillon(univers, parcours="Salaryman", points_personnels={"Perception": 100})  # tout mis ailleurs
    assert any("Ni Corps à corps" in a for a in b.avertissements())
    b.points_personnels = {"Esquive": 30, "Perception": 70}
    assert not any("Ni Corps à corps" in a for a in b.avertissements())


# --- La personnalité, par le LLM ----------------------------------------------------------------------

def test_le_llm_propose_la_personnalite(neo_tokyo):
    b = proposer_chiffres(Brouillon(neo_tokyo), random.Random(2), "Netrunner")
    serveur = ServeurScripte(personnalite(nom=""), personnalite())  # une relance : le nom manquait
    assert proposer_personnalite(serveur, b, sexe="femme") == ROLEPLAY | {"sexe": "femme"}
    demande = serveur.recus[0][0][-1]["content"]
    assert "Netrunner" in demande and neo_tokyo.nom in demande
    assert "nom" in serveur.recus[1][0][-1]["content"]  # la relance cite l'erreur
    assert proposer_personnalite(ServeurScripte("Hmm.", "Hmm."), b) is None


def test_le_code_tire_une_femme_ou_un_homme(neo_tokyo):
    b = proposer_chiffres(Brouillon(neo_tokyo), random.Random(2), "Netrunner")
    hasard, vus, initiales = random.Random(0), set(), set()
    for _ in range(20):
        serveur = ServeurScripte(personnalite(nom=""), personnalite())
        proposer_personnalite(serveur, b, hasard=hasard)
        premiere, relance = (recu[0][-1]["content"] for recu in serveur.recus)
        sexe = next(s for s in ("une femme", "un homme") if f"est {s}," in premiere)
        assert f"est {sexe}," in relance  # la relance garde le même tirage
        vus.add(sexe)
        lettres = premiere.split("au cadre : ")[1].split(".")[0]
        assert len(lettres.split(", ")) == 3 and f"au cadre : {lettres}." in relance
        initiales.add(lettres)
    assert vus == {"une femme", "un homme"} and len(initiales) > 10  # les initiales changent d'un tirage à l'autre


def test_tout_proposer_avec_et_sans_llm(neo_tokyo):
    avec = tout_proposer(neo_tokyo, ServeurScripte(personnalite()), hasard=random.Random(4))
    assert avec.roleplay["nom"] == "Yuki Sato"
    sans = tout_proposer(neo_tokyo, hasard=random.Random(4))
    assert sans.roleplay == {} and sans.parcours == avec.parcours


# --- Le dialogue en texte -----------------------------------------------------------------------------

def test_lire_les_saisies(neo_tokyo):
    assert lire_caracteristiques("for 50, con 45, dex 60, int 65, vol 40, pré 40")[C.PRESENCE] == 40
    assert lire_points(neo_tokyo, "Piratage 70, Technologie 5") == {"Technologie": 75}
    with pytest.raises(EtapeInvalide, match="inconnue"):
        lire_points(neo_tokyo, "Jonglage 10")
    with pytest.raises(EtapeInvalide, match="Nom valeur"):
        lire_caracteristiques("for")


def test_tout_proposer_puis_valider(neo_tokyo):
    reponses = iter(["tout", "", ""])  # tout proposer, garder la personnalité, valider
    sortie = []
    perso, depart = Guide(neo_tokyo, lambda _: next(reponses), sortie.append, ServeurScripte(personnalite()),
                          hasard=random.Random(7)).creer()
    assert perso.nom == "Yuki Sato" and perso.allure.startswith("Cheveux argentés")
    assert "\nCompétences :" in "\n".join(sortie)


def test_pas_a_pas_avec_une_saisie_fausse_puis_juste(neo_tokyo):
    reponses = iter([
        "",  # pas à pas
        "Netrunner",
        "for 90, con 10, dex 50, int 50, vol 50, pré 50",  # refusé
        "for 35, con 45, dex 60, int 75, vol 50, pré 35",
        "",  # points de parcours proposés
        "r", "",  # points personnels : relancés puis gardés
        "",  # équipement
        "f", "Yuki", "Payer sa dette", "Sa mère", "Trop curieuse", "",  # le roleplay, sans LLM
        "",  # valider
    ])
    sortie = []
    perso, _ = Guide(neo_tokyo, lambda _: next(reponses), sortie.append, hasard=random.Random(1)).creer()
    assert perso.caracteristiques[C.INTELLIGENCE] == 75 and perso.nom == "Yuki" and perso.sexe == "femme"
    assert any("de 20 à 80" in ligne for ligne in sortie)


def test_quitter_la_creation(neo_tokyo):
    with pytest.raises(Abandon):
        Guide(neo_tokyo, lambda _: "q", lambda _: None).creer()


def test_une_nouvelle_campagne_cree_son_personnage(tmp_path):
    bibliotheque = charger()
    choix = choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie.", 2091)
    serveur = ServeurScripte(
        *[[{"name": "retirer", "arguments": {"retirer": []}}]] * 3,
        *[[{"name": "renommer", "arguments": {"renommages": []}}]] * 4,
        [{"name": "trier_parcours", "arguments": {"retirer": [], "renommer": []}}],
        [{"name": "ajouter_parcours", "arguments": {"parcours": []}}],
        personnalite(),
        "La pluie tombe sur Osaka.",
    )
    reponses = iter(["tout", "", "", "quitter"])
    partie = jeu.Jeu(serveur, budget=128, entree=lambda _: next(reponses), sortie=lambda _: None,
                     campagne=Campagne(tmp_path), choix=choix, creer=True)
    assert partie.session.personnage.nom == "Yuki Sato"
    partie.jouer()
    sauvegarde = json.loads((tmp_path / "sauvegarde.json").read_text(encoding="utf-8"))
    assert sauvegarde["personnage"]["nom"] == "Yuki Sato"
