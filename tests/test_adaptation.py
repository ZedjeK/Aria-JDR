"""Le générateur, lots 2 et 3 : le LLM adapte l'univers au cadre, le code valide (REGLES.md 1.3 et 5).

Ordre des appels au LLM : nommer l'univers (si besoin), retirer (véhicules, armes, armures), renommer
(armes, armures, implants, véhicules), trier les parcours, puis ajouter des parcours par paquets.
"""

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
    choix_par_defaut,
    generer,
    proposer_cadre,
    valider_parcours,
    valider_renommages,
    valider_retraits,
    valider_tri,
)
from aria.univers import univers_depuis_dict
from test_table import ServeurScripte


@pytest.fixture(scope="module")
def bibliotheque():
    return charger()


@pytest.fixture(scope="module")
def cyberpunk(bibliotheque):
    return generer(bibliotheque, choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie."))


@pytest.fixture(scope="module")
def horreur(bibliotheque):
    return generer(bibliotheque, choix_par_defaut(bibliotheque, "Horreur", "Arkham 1925", "Arkham, 1925."))


# --- Le faux LLM ---------------------------------------------------------------------------------

def outil(_nom, **arguments):
    return [{"name": _nom, "arguments": arguments}]


def nommer(nom, cadre, annee=2088):
    return outil("nommer_univers", nom=nom, cadre=cadre, annee=annee)


def retirer(*noms):
    return outil("retirer", retirer=list(noms))


def renommer(*paires):
    return outil("renommer", renommages=[{"de": a, "vers": b} for a, b in paires])


def trier(retires=(), renommes=()):
    return outil("trier_parcours", retirer=list(retires), renommer=[{"de": a, "vers": b} for a, b in renommes])


def ajouter(*parcours):
    return outil("ajouter_parcours", parcours=list(parcours))


def rien(implants=True):
    """Un univers qui colle déjà au cadre : aucun retrait, aucun renommage, aucun parcours ajouté."""
    return [retirer(), retirer(), retirer(), renommer(), renommer(), *([renommer()] if implants else []), renommer(),
            trier(), ajouter()]


def avec_equipement(parcours, **cases):
    return dict(parcours, equipement=dict(parcours["equipement"], **cases))


DATA_COURSIER = {
    "nom": "Passeur de données", "description": "Il transporte des données trop sensibles pour le Net. Les corpos "
    "le paient bien et l'oublient vite. Il est rapide et discret, mais il ne survit pas à une vraie fusillade.",
    "competences": ["Conduite", "Esquive", "Vigilance", "Athlétisme", "Infiltration", "Réseau", "Arnaque", "Piratage"],
    "equipement": {"armes": ["Pistolet léger", "rien"], "armures": ["Veste renforcée"], "implants": ["Neuroport"],
                   "objets": ["une puce chiffrée", "un téléphone jetable", "un contact chez un fixer"]},
}


# --- Appliquer : tout se rejoue, et rien ne change dans les règles ---------------------------------

def test_appliquer_rejoue_toute_l_adaptation(cyberpunk):
    a = Adaptation(
        "Osaka 2091", "Osaka sous la pluie.",
        retraits={"vehicules": ["Drone de combat"], "armes": ["Pistolet-mitrailleur"]},
        renommages={"armes": {"Pistolet silencieux": "Pistolet à silencieux"},
                    "armures": {"Veste renforcée": "Veston doublé"}, "implants": {"Neuroport": "Port neural"}},
        parcours_retires=["Idol"], parcours_renommes={"Netrunner": "Coureur de réseau"},
    )
    # Un parcours ajouté se valide sur l'univers déjà renommé, comme dans le vrai déroulé
    avant = appliquer(cyberpunk, a)
    ajoute = avec_equipement(DATA_COURSIER, armures=["Veston doublé"], implants=["Port neural"])
    a.parcours_ajoutes = [valider_parcours(ajoute, avant, set(avant["parcours"]))[0]]
    u = univers_depuis_dict(appliquer(cyberpunk, a))  # toujours valide pour le moteur
    assert "Pistolet-mitrailleur" not in {x.nom for x in u.armes} and "Drone de combat" not in {v.nom for v in u.vehicules}
    coureur = u.equipements["Coureur de réseau"]
    assert "Port neural" in coureur["implants"] and "Pistolet à silencieux" in coureur["armes"]
    assert "Idol" not in u.parcours and "Netrunner" not in u.parcours
    assert u.nom_local("Netrunner") == "Coureur de réseau" and u.nom_local("Neuroport") == "Port neural"
    assert u.parcours["Passeur de données"][0] == "Pilotage"  # « Conduite » ramenée au socle
    assert u.equipements["Passeur de données"]["armes"] == ["Pistolet léger", None]
    assert next(s for s in u.systemes if s.nom == "Cortex frontal").requiert == "Port neural"
    assert "Pistolet-mitrailleur" in {x["nom"] for x in cyberpunk["armes"]}  # l'original n'a pas bougé


def test_les_retraits_purgent_les_listes_de_depart(cyberpunk):
    assert "Pistolet silencieux" in cyberpunk["equipements"]["Netrunner"]["armes"]
    d = appliquer(cyberpunk, Adaptation("A", "B", retraits={"armes": ["Pistolet silencieux"]}))
    assert all("Pistolet silencieux" not in listes.get("armes", []) for listes in d["equipements"].values())
    univers_depuis_dict(d)


def test_un_renommage_ne_change_pas_les_regles(horreur):
    pistolet = next(a for a in horreur["armes"] if a["nom"] == "Pistolet lourd")
    d = appliquer(horreur, Adaptation("Arkham", "1925", renommages={"armes": {"Pistolet lourd": "Colt .45"}}))
    colt = next(a for a in d["armes"] if a["nom"] == "Colt .45")
    assert {k: v for k, v in colt.items() if k != "nom"} == {k: v for k, v in pistolet.items() if k != "nom"}


# --- Les validations ---------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "proposes, accepte, erreur",
    [
        ([{"de": "Couteau", "vers": "Tantō"}], {"Couteau": "Tantō"}, None),
        ([{"de": "Couteau", "vers": "Couteau"}], {}, None),
        ([{"de": "Sabre laser", "vers": "X"}], {}, "n'existe pas"),
        ([{"de": "Couteau", "vers": "A"}, {"de": "Couteau", "vers": "B"}], {"Couteau": "A"}, "deux fois"),
        ([{"de": "Couteau", "vers": "x" * 41}], {}, "de 1 à 40"),
        ([{"de": "Couteau", "vers": "Katana"}], {}, "déjà pris"),
        ("pas une liste", {}, "doit être une liste"),
    ],
)
def test_valider_les_renommages(proposes, accepte, erreur):
    acceptes, refus = valider_renommages(proposes, ["Couteau", "Katana"], {"Couteau", "Katana"})
    assert acceptes == accepte
    assert refus == [] if erreur is None else any(erreur in r for r in refus), refus


def test_valider_les_retraits(cyberpunk):
    acceptes, refus = valider_retraits(["Minigun", "Lance-flammes", "Sabre laser"], "armes", cyberpunk)
    assert acceptes == ["Lance-flammes"]  # le minigun est monté sur un AV de l'univers
    assert any("Minigun" in r and "véhicule" in r for r in refus) and any("Sabre laser" in r for r in refus)
    toutes = [a["nom"] for a in cyberpunk["armures"]]
    acceptes, refus = valider_retraits(toutes, "armures", cyberpunk)
    assert acceptes == [] and any("au moins 2" in r for r in refus)
    assert valider_retraits("non", "armes", cyberpunk) == ([], ["« retirer » doit être une liste."])
    peu = dict(cyberpunk, armures=cyberpunk["armures"][:1])  # l'époque n'a laissé qu'une armure
    assert valider_retraits([], "armures", peu) == ([], [])


def test_valider_le_tri_des_parcours(cyberpunk):
    (retires, renommes), refus = valider_tri({"retirer": ["Netrunner", "Idol", "Pirate"],
                                              "renommer": [{"de": "Solo", "vers": "Ronin"}]}, cyberpunk, {"Netrunner"})
    assert retires == ["Idol"] and renommes == {"Solo": "Ronin"}
    assert any("doit rester" in r for r in refus) and any("Pirate" in r for r in refus)
    (retires, _), refus = valider_tri({"retirer": list(cyberpunk["parcours"])[:12], "renommer": []}, cyberpunk, set())
    assert retires == [] and any("au moins 10" in r for r in refus)


@pytest.mark.parametrize(
    "changements, erreur",
    [
        ({}, None),
        ({"nom": "Netrunner"}, "existe déjà"),
        ({"description": "x" * 601}, "description"),
        ({"competences": ["Conduite"] * 8}, "compétences distinctes"),
        ({"competences": ["Conduite", "Esquive", "Vigilance", "Athlétisme", "Infiltration", "Réseau", "Arnaque", "Magie"]},
         "compétences distinctes"),  # pas de Magie en Cyberpunk
        ({"equipement": dict(DATA_COURSIER["equipement"], armures=["Armure tactique"])}, "option de départ"),
        ({"equipement": dict(DATA_COURSIER["equipement"], armes=["Pistolet lourd Arasaka"])}, "option de départ"),
        ({"equipement": dict(DATA_COURSIER["equipement"], armes=[])}, "de 1 à 3 options"),
        ({"equipement": dict(DATA_COURSIER["equipement"], objets=["un seul"])}, "objets racontés"),
    ],
)
def test_valider_un_parcours_ajoute(cyberpunk, changements, erreur):
    parcours, refus = valider_parcours(dict(DATA_COURSIER, **changements), cyberpunk, set(cyberpunk["parcours"]))
    if erreur is None:
        assert refus == [] and parcours["nom"] == "Passeur de données"
    else:
        assert parcours is None and any(erreur in r for r in refus), refus


# --- L'adaptation complète, avec un faux LLM ---------------------------------------------------------

def test_adapter_avec_relances(bibliotheque, cyberpunk):
    choix = choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie.", 2091)
    passeur = avec_equipement(DATA_COURSIER, implants=[])  # le neuroport est renommé dans ce scénario
    faux = dict(passeur, nom="Netrunner")
    serveur = ServeurScripte(
        retirer(),  # véhicules
        retirer("Minigun"), retirer("Lance-flammes"),  # armes : le minigun est monté, relance
        retirer(),  # armures
        renommer(("Pistolet lourd", "Nambu lourd"), ("Sabre laser", "X")), renommer(("Pistolet lourd", "Nambu lourd")),
        renommer(), renommer(("Neuroport", "Port neural")),
        "Je ne vois rien à changer.", "Toujours rien.",  # véhicules : pas d'outil, deux fois
        trier(["Netrunner"]), trier(["Idol"]),  # le Netrunner est gardé : relance
        ajouter(passeur, faux), ajouter(passeur),  # un parcours fautif : relance
    )
    a = adapter(serveur, cyberpunk, choix, budget=128, gardes={"Netrunner"})
    assert a.retraits == {"armes": ["Lance-flammes"]}
    assert a.renommages == {"armes": {"Pistolet lourd": "Nambu lourd"}, "implants": {"Neuroport": "Port neural"}}
    assert a.parcours_retires == ["Idol"] and [p["nom"] for p in a.parcours_ajoutes] == ["Passeur de données"]
    assert any("véhicules" in r and "renommer" in r for r in a.refus)
    assert "Minigun" in serveur.recus[2][0][-1]["content"]  # la relance cite l'erreur
    assert not serveur.script  # tout le scénario a été joué
    univers_depuis_dict(appliquer(cyberpunk, a))


def test_arkham_retire_puis_comble_les_parcours(bibliotheque, horreur):
    choix = choix_par_defaut(bibliotheque, "Horreur", "Arkham 1925", "Arkham, 1925.", 1925)
    retires = list(horreur["parcours"])[:8]  # 20 - 8 = 12 : il en manque 3 pour atteindre 15
    medium = {"nom": "Spirite", "description": "Elle fait tourner les tables dans les salons. La bonne société "
              "s'en amuse et s'en méfie. Elle entend parfois de vraies voix, et ne s'en remet jamais tout à fait.",
              "competences": ["Occultisme", "Psychologie", "Persuasion", "Mensonge", "Perception", "Arts", "Mythe",
                              "Culture générale"],
              "equipement": {"armes": ["rien"], "armures": ["rien"], "objets": ["un guéridon", "un jeu de tarot",
                                                                               "une clientèle fortunée"]}}
    bootlegger = dict(medium, nom="Bootlegger", competences=["Conduite", "Armes à distance", "Intimidation",
                                                            "Persuasion", "Perception", "Esquive", "Mécanique", "Survie"])
    garde = dict(medium, nom="Garde du campus", competences=["Combat rapproché", "Perception", "Intimidation",
                                                            "Athlétisme", "Esquive", "Investigation", "Survie", "Meneur"])
    serveur = ServeurScripte(
        retirer(), retirer("Shuriken"), retirer(),  # l'époque a déjà fait le gros du travail
        renommer(("Pistolet lourd", "Colt .45")), renommer(), renommer(),
        trier(retires),
        ajouter(medium, bootlegger),  # 14 : il en manque encore un
        ajouter(garde),  # 15 : c'est assez
    )
    a = adapter(serveur, horreur, choix)
    assert a.annee == 1925 and a.retraits == {"armes": ["Shuriken"]} and not a.refus
    epoque = a.retraits_epoque
    assert {"Lance-roquettes", "Minigun", "Fusil d'assaut", "Grenade flash"} <= set(epoque["armes"])
    assert "Jet-ski" in epoque["vehicules"] and "Blindé de reconnaissance" not in epoque["vehicules"]
    d = appliquer(horreur, a)
    assert len(d["parcours"]) == 15 and "Spirite" in d["parcours"]
    assert "Colt .45" in {x["nom"] for x in d["armes"]}
    assert not serveur.script
    assert "de 3 à 5" in serveur.recus[7][0][-1]["content"] and "de 1 à 5" in serveur.recus[8][0][-1]["content"]


def test_le_llm_nomme_un_univers_sans_nom(bibliotheque, cyberpunk):
    choix = choix_par_defaut(bibliotheque, "Cyberpunk")  # nom = le genre, pas de cadre
    serveur = ServeurScripte(nommer("Neo-Kobe", "Kobe en 2088, sous la coupe des zaibatsus."), *rien())
    a = adapter(serveur, cyberpunk, choix)
    assert (a.nom, a.cadre, a.annee) == ("Neo-Kobe", "Kobe en 2088, sous la coupe des zaibatsus.", 2088)
    assert not a.refus and not a.retraits_epoque  # en 2088, tout existe déjà


def test_surprends_moi_garder_ou_relancer(bibliotheque):
    choix = choix_par_defaut(bibliotheque, "Horreur")
    serveur = ServeurScripte(nommer("Arkham", "Arkham, 1925. Le brouillard ne se lève plus."),
                             nommer("Salem", "Salem, 1692. Les procès commencent."))
    reponses = iter(["n", "o"])
    garde = jeu.surprendre(serveur, choix, 128, entree=lambda _: next(reponses), sortie=lambda _: None)
    assert (garde.nom, garde.cadre) == ("Salem", "Salem, 1692. Les procès commencent.")
    assert "Arkham, 1925" in serveur.recus[1][0][-1]["content"]
    with pytest.raises(ChoixInvalide, match="écris-en un"):
        proposer_cadre(ServeurScripte("Hmm.", "Hmm."), choix)


def test_une_campagne_generee_et_adaptee(tmp_path, bibliotheque):
    campagne = Campagne(tmp_path)
    choix = choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie acide.", 2091)
    serveur = ServeurScripte(
        retirer(), retirer(), retirer(),
        renommer(("Pistolet silencieux", "Pistolet à silencieux")), renommer(("Veste renforcée", "Veston doublé")),
        renommer(("Neuroport", "Port neural")), renommer(),
        trier(renommes=[("Netrunner", "Coureur de réseau")]),
        ajouter(avec_equipement(DATA_COURSIER, armures=["Veston doublé"], implants=["Port neural"])),
        "La pluie acide ronge les néons d'Osaka.",  # la première scène
    )
    sortie, entrees = [], iter(["quitter"])
    partie = jeu.Jeu(serveur, budget=128, entree=lambda _: next(entrees), sortie=sortie.append,
                     campagne=campagne, choix=choix)
    s = partie.session
    assert s.personnage.parcours == "Coureur de réseau"  # Kaito suit son parcours renommé
    assert s.joueur.armure.nom == "Veston doublé" and s.personnage.implants[0]["nom"] == "Port neural"
    texte = "\n".join(sortie)
    assert "Les armures : Veste renforcée → Veston doublé" in texte and "Nouveau parcours : Passeur de données" in texte
    ecrit = json.loads(campagne.univers.read_text(encoding="utf-8"))
    assert ecrit["origines"]["Coureur de réseau"] == "Netrunner"
    partie.jouer()
    reprise = jeu.Jeu(ServeurScripte("Tu reprends."), budget=128, entree=lambda _: "quitter", sortie=lambda _: None,
                      campagne=campagne)
    assert reprise.session.univers.nom_local("Neuroport") == "Port neural"


def test_l_epoque_retire_avant_le_llm(bibliotheque, horreur):
    from aria.generateur import retraits_par_epoque
    r = retraits_par_epoque(horreur, 1925)
    assert "Grenade flash" in r["armes"] and "Pistolet lourd" not in r["armes"]
    assert "Blindé de transport" in r["vehicules"] and "Char" not in r.get("vehicules", [])
    assert retraits_par_epoque(horreur, 2100) == {}
    d = appliquer(horreur, Adaptation("Arkham", "1925", 1925, retraits_epoque=r))
    univers_depuis_dict(d)  # rien d'orphelin : les armes montées partent avec leur véhicule


def test_sans_annee_le_llm_la_donne(bibliotheque, horreur):
    choix = choix_par_defaut(bibliotheque, "Horreur", "Arkham", "Arkham, au temps de la Prohibition.")
    serveur = ServeurScripte(nommer("Arkham", "Arkham, au temps de la Prohibition.", 1926), *rien(implants=False))
    a = adapter(serveur, horreur, choix)
    assert a.annee == 1926 and "Minigun" in a.retraits_epoque["armes"]
    sans = adapter(ServeurScripte(nommer("Arkham", "Arkham.", "vers 1920"), *rien(implants=False)), horreur, choix)
    assert sans.annee is None and not sans.retraits_epoque and any("pas d'année" in r for r in sans.refus)
