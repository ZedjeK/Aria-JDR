"""Le générateur, lot 2 : le LLM adapte les noms au cadre, le code valide (REGLES.md 1.3)."""

import json

import pytest

from aria import jeu
from aria.bibliotheque import charger
from aria.campagne import Campagne
from aria.generateur import (
    Adaptation,
    ChoixInvalide,
    adapter,
    appliquer,
    avec,
    choix_par_defaut,
    creer_campagne,
    generer,
    proposer_cadre,
    valider_renommages,
)
from aria.univers import univers_depuis_dict
from test_table import ServeurScripte, appel


@pytest.fixture(scope="module")
def bibliotheque():
    return charger()


@pytest.fixture(scope="module")
def cyberpunk(bibliotheque):
    return generer(bibliotheque, choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie."))


def nommer(nom, cadre):
    return {"name": "nommer_univers", "arguments": {"nom": nom, "cadre": cadre}}


def renommer(*paires):
    return [appel("renommer", renommages=[{"de": a, "vers": b} for a, b in paires])]


def test_appliquer_renomme_partout(cyberpunk):
    adaptation = Adaptation("Osaka 2091", "Osaka sous la pluie.", {
        "armes": {"Pistolet-mitrailleur": "Thompson", "Pistolet silencieux": "Pistolet à silencieux"},
        "armures": {"Veste renforcée": "Veston doublé"},
        "implants": {"Neuroport": "Port neural"},
        "vehicules": {"Drone de combat": "Guêpe de combat"},
    })
    u = univers_depuis_dict(appliquer(cyberpunk, adaptation))  # toujours valide pour le moteur
    drone = u.vehicule("Guêpe de combat")
    assert drone.armes_montees[0]["arme"] == "Thompson"  # l'arme montée suit son nouveau nom
    netrunner = u.equipements["Netrunner"]
    assert "Port neural" in netrunner["implants"] and "Pistolet à silencieux" in netrunner["armes"]
    assert "Veston doublé" in netrunner["armures"]
    assert next(s for s in u.systemes if s.nom == "Cortex frontal").requiert == "Port neural"
    assert u.nom_local("Neuroport") == "Port neural" and u.nom_local("Couteau") == "Couteau"
    assert u.origines["Thompson"] == "Pistolet-mitrailleur"
    assert u.arme("Thompson").degats == next(a for a in cyberpunk["armes"] if a["nom"] == "Pistolet-mitrailleur")["degats"]
    assert "Pistolet-mitrailleur" in {a["nom"] for a in cyberpunk["armes"]}  # l'original n'a pas bougé


def test_sans_renommage_rien_ne_change(cyberpunk):
    d = appliquer(cyberpunk, Adaptation("Osaka", "La pluie."))
    assert d["armes"] == cyberpunk["armes"] and "origines" not in d and d["nom"] == "Osaka"


@pytest.mark.parametrize(
    "proposes, accepte, erreur",
    [
        ([{"de": "Couteau", "vers": "Tantō"}], {"Couteau": "Tantō"}, None),
        ([{"de": "Couteau", "vers": "Couteau"}], {}, None),  # rien ne change : ce n'est pas une erreur
        ([{"de": "Sabre laser", "vers": "X"}], {}, "n'existe pas"),
        ([{"de": "Couteau", "vers": "A"}, {"de": "Couteau", "vers": "B"}], {"Couteau": "A"}, "deux fois"),
        ([{"de": "Couteau", "vers": "x" * 41}], {}, "de 1 à 40"),
        ([{"de": "Couteau", "vers": "  "}], {}, "de 1 à 40"),
        ([{"de": "Couteau", "vers": "Katana"}], {}, "déjà pris"),
        ([{"de": "Couteau", "vers": "Lame"}, {"de": "Katana", "vers": "Lame"}], {"Couteau": "Lame"}, "déjà pris"),
        ("pas une liste", {}, "doit être une liste"),
    ],
)
def test_valider_les_renommages(proposes, accepte, erreur):
    acceptes, refus = valider_renommages(proposes, ["Couteau", "Katana"], {"Couteau", "Katana"})
    assert acceptes == accepte
    assert refus == [] if erreur is None else any(erreur in r for r in refus), refus


def test_adapter_relance_puis_garde_la_bibliotheque(bibliotheque, cyberpunk):
    choix = choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie.")
    serveur = ServeurScripte(
        renommer(("Pistolet lourd", "Nambu lourd"), ("Sabre laser", "X")),  # armes : une erreur
        renommer(("Pistolet lourd", "Nambu lourd")),  # armes, relance corrigée
        renommer(),  # armures : rien
        renommer(("Neuroport", "Port neural")),  # implants
        "Je ne vois rien à changer.",  # véhicules : pas d'outil
        "Toujours rien.",  # véhicules, relance : on garde la bibliothèque
    )
    a = adapter(serveur, cyberpunk, choix, budget=128)
    assert (a.nom, a.cadre) == ("Osaka 2091", "Osaka sous la pluie.")
    assert a.renommages == {"armes": {"Pistolet lourd": "Nambu lourd"}, "implants": {"Neuroport": "Port neural"}}
    assert any("véhicules" in r and "renommer" in r for r in a.refus)
    relance = serveur.recus[1][0][-1]["content"]
    assert "Sabre laser" in relance and "recommence" in relance
    outil = serveur.recus[0][1][0]["function"]
    assert outil["name"] == "renommer" and "Pistolet lourd" in outil["parameters"]["properties"]["renommages"][
        "items"]["properties"]["de"]["enum"]


def test_le_llm_nomme_un_univers_sans_nom(bibliotheque, cyberpunk):
    choix = choix_par_defaut(bibliotheque, "Cyberpunk")  # nom = le genre, pas de cadre
    serveur = ServeurScripte([nommer("Neo-Kobe", cadre="Kobe en 2088, sous la coupe des zaibatsus.")],
                             renommer(), renommer(), renommer(), renommer())
    a = adapter(serveur, cyberpunk, choix)
    assert (a.nom, a.cadre) == ("Neo-Kobe", "Kobe en 2088, sous la coupe des zaibatsus.") and not a.refus


def test_surprends_moi_garder_ou_relancer(bibliotheque):
    choix = choix_par_defaut(bibliotheque, "Horreur")
    serveur = ServeurScripte([nommer("Arkham", cadre="Arkham, 1925. Le brouillard ne se lève plus.")],
                             [nommer("Salem", cadre="Salem, 1692. Les procès commencent.")])
    reponses = iter(["n", "o"])
    garde = jeu.surprendre(serveur, choix, 128, entree=lambda _: next(reponses), sortie=lambda _: None)
    assert (garde.nom, garde.cadre) == ("Salem", "Salem, 1692. Les procès commencent.")
    assert "Arkham, 1925" in serveur.recus[1][0][-1]["content"]  # le cadre refusé n'est plus proposé
    with pytest.raises(ChoixInvalide, match="écris-en un"):
        proposer_cadre(ServeurScripte("Hmm.", "Hmm."), choix)


def test_une_campagne_generee_et_adaptee(tmp_path, bibliotheque):
    campagne = Campagne(tmp_path)
    choix = choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie acide.")
    serveur = ServeurScripte(
        renommer(("Pistolet silencieux", "Pistolet à silencieux")),
        renommer(("Veste renforcée", "Veston doublé")),
        renommer(("Neuroport", "Port neural")),
        renommer(),
        "La pluie acide ronge les néons d'Osaka.",  # la première scène
    )
    sortie, entrees = [], iter(["quitter"])
    partie = jeu.Jeu(serveur, budget=128, entree=lambda _: next(entrees), sortie=sortie.append,
                     campagne=campagne, choix=choix)
    s = partie.session
    assert s.joueur.armure.nom == "Veston doublé"  # Kaito retrouve son équipement sous les noms d'Osaka
    assert s.personnage.implants[0]["nom"] == "Port neural"
    assert "Les armures : Veste renforcée → Veston doublé" in "\n".join(sortie)
    ecrit = json.loads(campagne.univers.read_text(encoding="utf-8"))
    assert ecrit["origines"]["Port neural"] == "Neuroport"
    partie.jouer()
    reprise = jeu.Jeu(ServeurScripte("Tu reprends."), budget=128, entree=lambda _: "quitter", sortie=lambda _: None,
                      campagne=campagne)
    assert reprise.session.univers.nom_local("Neuroport") == "Port neural"


def test_le_magicien_ne_change_pas_les_regles(bibliotheque):
    choix = avec(choix_par_defaut(bibliotheque, "Horreur", "Arkham", "Arkham, 1925."))
    donnees = generer(bibliotheque, choix)
    pistolet = next(a for a in donnees["armes"] if a["nom"] == "Pistolet lourd")
    d = appliquer(donnees, Adaptation("Arkham", "Arkham, 1925.", {"armes": {"Pistolet lourd": "Colt .45"}}))
    colt = next(a for a in d["armes"] if a["nom"] == "Colt .45")
    assert {k: v for k, v in colt.items() if k != "nom"} == {k: v for k, v in pistolet.items() if k != "nom"}
