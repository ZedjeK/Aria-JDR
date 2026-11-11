"""Le générateur d'univers, lot 1 : réglages par genre, composition et copie figée (REGLES.md 1.2 et 1.3)."""

import json

import pytest

from aria import generateur, jeu
from aria.bibliotheque import GENRES, charger
from aria.campagne import Campagne
from aria.generateur import Choix, ChoixInvalide, avec, choix_par_defaut, creer_campagne, generer
from aria.univers import univers_depuis_dict
from test_table import ServeurScripte


@pytest.fixture(scope="module")
def bibliotheque():
    return charger()


@pytest.mark.parametrize(
    "genre, magie, curseur, impitoyable",
    [
        ("Fantasy", True, "héroïque", False),
        ("Horreur", True, "réaliste", False),
        ("Contemporain", False, "standard", False),
        ("Cyberpunk", False, "standard", True),
        ("Post-apo", False, "réaliste", True),
    ],
)
def test_les_reglages_sont_preremplis_par_genre(bibliotheque, genre, magie, curseur, impitoyable):
    choix = choix_par_defaut(bibliotheque, genre)
    assert (choix.magie, choix.curseur, choix.monde_impitoyable, choix.nom) == (magie, curseur, impitoyable, genre)


@pytest.mark.parametrize("genre", GENRES)
def test_chaque_genre_donne_un_univers_valide(bibliotheque, genre):
    choix = choix_par_defaut(bibliotheque, genre, "Test", "Un cadre.")
    u = univers_depuis_dict(generer(bibliotheque, choix))
    assert u.genre == genre and 15 <= len(u.parcours) <= 30
    assert u.magie_active == choix.magie
    if genre in ("Fantasy", "Dark fantasy"):  # les seuls domaines de la bibliothèque, pour l'instant
        assert u.domaines


def test_le_joueur_change_les_reglages(bibliotheque):
    choix = avec(choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091"), curseur="réaliste",
                 monde_impitoyable=False, chocs_banals=())
    u = univers_depuis_dict(generer(bibliotheque, choix))
    assert (u.nom, u.curseur.value, u.monde_impitoyable, u.chocs_banals) == ("Osaka 2091", "réaliste", False, frozenset())


def test_la_magie_option_du_post_apo(bibliotheque):
    sans = univers_depuis_dict(generer(bibliotheque, choix_par_defaut(bibliotheque, "Post-apo")))
    avec_psi = univers_depuis_dict(generer(bibliotheque, avec(choix_par_defaut(bibliotheque, "Post-apo"), magie=True)))
    assert not sans.domaines and len(avec_psi.parcours) >= len(sans.parcours)


@pytest.mark.parametrize(
    "changements, erreur",
    [
        (dict(genre="Cyberpunk", magie=True), "Pas de magie en Cyberpunk"),
        (dict(genre="Fantasy", magie=False), "reste activée"),
        (dict(curseur="épique"), "Curseur inconnu"),
        (dict(nom=" "), "nom de l'univers"),
        (dict(chocs_banals=("PANIQUE",)), "Choc inconnu"),
    ],
)
def test_les_choix_impossibles_sont_refuses(bibliotheque, changements, erreur):
    base = choix_par_defaut(bibliotheque, changements.get("genre", "Contemporain"))
    with pytest.raises(ChoixInvalide) as e:
        generer(bibliotheque, avec(base, **changements))
    assert any(erreur in x for x in e.value.erreurs), e.value.erreurs


def test_genre_inconnu(bibliotheque):
    with pytest.raises(ChoixInvalide, match="Genre inconnu"):
        choix_par_defaut(bibliotheque, "Space opera")


def test_l_univers_de_la_campagne_est_une_copie_figee(tmp_path, bibliotheque):
    campagne = Campagne(tmp_path / "osaka")
    choix = choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091", "Osaka sous la pluie acide.")
    u, adaptation = creer_campagne(campagne, choix, bibliotheque)
    assert adaptation is None  # sans serveur, pas de LLM
    assert u.nom == "Osaka 2091" and u.cadre == "Osaka sous la pluie acide."
    ecrit = json.loads(campagne.univers.read_text(encoding="utf-8"))
    assert ecrit["nom"] == "Osaka 2091" and not campagne.univers.with_suffix(".tmp").exists()
    with pytest.raises(FileExistsError):
        creer_campagne(campagne, choix, bibliotheque)


def test_une_partie_dans_un_univers_genere(tmp_path, bibliotheque):
    campagne = Campagne(tmp_path)
    choix = choix_par_defaut(bibliotheque, "Cyberpunk", "Osaka 2091")
    entrees = iter(["quitter"])
    partie = jeu.Jeu(ServeurScripte("La pluie acide."), budget=128, entree=lambda _: next(entrees),
                     sortie=lambda _: None, campagne=campagne, choix=choix)
    assert partie.session.univers.nom == "Osaka 2091" and campagne.univers.is_file()
    partie.jouer()
    # Au lancement suivant, sans choix : la campagne reprend dans son propre univers
    reprise = jeu.Jeu(ServeurScripte("Tu reprends."), budget=128, entree=lambda _: "quitter", sortie=lambda _: None,
                      campagne=campagne)
    assert reprise.session.univers.nom == "Osaka 2091"


def test_sans_netrunner_pas_encore_de_personnage(tmp_path, bibliotheque):
    with pytest.raises(jeu.SansPersonnage, match="étape suivante"):
        jeu.Jeu(ServeurScripte(), budget=128, campagne=Campagne(tmp_path),
                choix=choix_par_defaut(bibliotheque, "Fantasy"))


def test_les_arguments_du_jeu(bibliotheque):
    assert jeu.choix_de(jeu.lire_arguments([])) is None
    choix = jeu.choix_de(jeu.lire_arguments(["--campagne", "osaka", "--genre", "Cyberpunk", "--cadre", "Osaka, 2091"]))
    assert isinstance(choix, Choix) and choix.cadre == "Osaka, 2091" and choix.nom == "Cyberpunk"
    with pytest.raises(ChoixInvalide):
        jeu.choix_de(jeu.lire_arguments(["--genre", "Western"]))


def test_la_bibliotheque_verifie_les_reglages(bibliotheque):
    from dataclasses import replace
    import copy
    genres = copy.deepcopy(bibliotheque.genres)
    genres["Cyberpunk"]["reglages"]["curseur"] = "épique"
    genres["Horreur"]["reglages"]["chocs_banals"] = ["PANIQUE"]
    erreurs = replace(bibliotheque, genres=genres).verifier()
    assert any("curseur inconnu" in e for e in erreurs) and any("choc inconnu" in e for e in erreurs)
    assert generateur.ACTIVEE == "activée"
