"""Ce que la page dessine d'un combat sur la carte (aria/vue_combat.py) : les cases, les combattants, ce que le joueur
peut faire, et quand le combat le publie."""

from aria import vue_combat
from aria.combat_joueur import TourDuJoueur, jouer_les_pnj, montrer_la_carte, ouvrir_le_combat
from aria.grille import Terrain, case
from tests.test_combat_joueur import Script
from tests.test_combat_sur_carte import partie_sur_carte


def publiees(s, script, **options):
    """Un tour du joueur dont l'écran garde chaque carte publiée."""
    vues = []
    ecran = script.ecran(publier=vues.append, **options)
    return TourDuJoueur(s, ouvrir_le_combat(s, ecran), ecran), vues


def test_sans_carte_pas_de_vue():
    assert vue_combat.vue(None, None) is None
    s = partie_sur_carte()
    s.combat.carte = None
    assert vue_combat.vue(s.combat, s.joueur) is None


def test_la_vue_place_chaque_combattant_par_colonne_et_ligne():
    s = partie_sur_carte()
    v = vue_combat.vue(s.combat, s.joueur)
    assert (v["lieu"], v["decor"], v["round"]) == ("ruelle", "encombré", 1)
    assert (v["largeur"], v["hauteur"]) == (s.combat.carte.largeur, s.combat.carte.hauteur)
    par_nom = {c["nom"]: c for c in v["combattants"]}
    kaito, ganger = par_nom[s.joueur.nom], par_nom["Ganger"]
    assert (kaito["camp"], kaito["colonne"], kaito["ligne"]) == ("joueur", 2, 5)
    assert (ganger["camp"], ganger["colonne"], ganger["ligne"]) == ("ennemi", 9, 5)
    assert kaito["debout"] and ganger["etat"] == "indemne"


def test_les_pv_des_ennemis_seulement_si_le_joueur_les_demande():
    s = partie_sur_carte()
    cache = {c["nom"]: c for c in vue_combat.vue(s.combat, s.joueur)["combattants"]}
    vus = {c["nom"]: c for c in vue_combat.vue(s.combat, s.joueur, pv_exacts=True)["combattants"]}
    fiche = s.pnj["ganger"].fiche
    assert cache["Ganger"]["pv"] is None and vus["Ganger"]["pv"] == f"{fiche.pv}/{fiche.pv_max}"
    assert cache[s.joueur.nom]["pv"] == f"{s.joueur.fiche.pv}/{s.joueur.fiche.pv_max}"


def test_le_terrain_donne_le_type_de_chaque_obstacle():
    s = partie_sur_carte()
    s.combat.carte.terrain.update({case(5, 5): Terrain.BAS, case(5, 6): Terrain.PLEIN, case(6, 2): Terrain.DIFFICILE})
    terrain = vue_combat.vue(s.combat, s.joueur)["terrain"]
    assert sorted(terrain) == [[5, 5, "bas"], [5, 6, "plein"], [6, 2, "difficile"]]


def test_a_son_tour_le_joueur_voit_ou_il_peut_aller():
    s = partie_sur_carte()
    assert s.combat.au_tour_de is s.joueur
    atteignables = vue_combat.vue(s.combat, s.joueur)["atteignables"]
    assert [3, 5] in atteignables and [8, 5] in atteignables and [2, 5] not in atteignables
    assert [9, 5] not in atteignables  # la case de l'ennemi


def test_apres_avoir_vise_plus_de_cases_atteignables():
    s = partie_sur_carte()
    s.joueur.a_vise = True
    assert vue_combat.vue(s.combat, s.joueur)["atteignables"] == []


def test_hors_de_son_tour_pas_de_cases_atteignables():
    s = partie_sur_carte()
    s.combat.actif = s.combat.ordre.index(s.pnj["ganger"])
    assert vue_combat.vue(s.combat, s.joueur)["atteignables"] == []


def test_le_tour_du_joueur_publie_la_carte_avant_le_menu():
    s = partie_sur_carte()
    tour, vues = publiees(s, Script("Terminer"))
    tour.jouer()
    assert vues and vues[-1]["destinations"] == [] and vues[-1]["menu"] is None
    assert any(c["actif"] and c["camp"] == "joueur" for c in vues[-1]["combattants"])


def test_le_menu_ou_vas_tu_numerote_ses_destinations_sur_la_carte():
    s = partie_sur_carte()
    script = Script("Se déplacer", "Retour", "Terminer")
    tour, vues = publiees(s, script)
    tour.jouer()
    avec = next(v for v in vues if v["destinations"])
    titre, options = next(v for v in script.vues if v[0] == vue_combat.MENU_DES_DESTINATIONS)
    assert avec["menu"] == titre
    assert [d["numero"] for d in avec["destinations"]] == list(range(1, len(options)))  # « Retour » en dernier
    for d, option in zip(avec["destinations"], options):
        assert option.libelle.startswith(d["libelle"])
    contact = next(d for d in avec["destinations"] if d["libelle"] == "Aller au contact de Ganger")
    assert (contact["colonne"], contact["ligne"]) in {(8, 5), (8, 4), (8, 6), (9, 4), (9, 6)}
    assert vues[-1]["destinations"] == []  # revenu au menu principal : plus de destinations


def test_chaque_action_d_un_pnj_republie_la_carte():
    s = partie_sur_carte(*[90] * 20)  # assez de dés pour ce que le ganger tente une fois arrivé
    vues = []
    ecran = Script().ecran(publier=vues.append)
    auto = ouvrir_le_combat(s, ecran)
    s.combat.actif = s.combat.ordre.index(s.pnj["ganger"])
    jouer_les_pnj(auto, ecran)
    assert len(vues) >= 2
    ganger = next(c for c in vues[-1]["combattants"] if c["nom"] == "Ganger")
    assert (ganger["colonne"], ganger["ligne"]) != (9, 5)  # il s'est approché


def test_sans_page_rien_n_est_publie():
    s = partie_sur_carte()
    montrer_la_carte(s.combat, Script().ecran())  # pas de `publier` : ne fait rien, ne casse rien


def test_un_combat_sans_carte_publie_none():
    s = partie_sur_carte()
    s.combat.carte = None
    vues = []
    montrer_la_carte(s.combat, Script().ecran(publier=vues.append))
    assert vues == [None]
