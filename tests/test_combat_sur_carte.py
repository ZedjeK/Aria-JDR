"""Le combat à pied sur la carte (REGLES.md 7.11) : l'ouverture par le MJ, l'IA qui se déplace, le menu du joueur
(se déplacer, cibles hors de portée, fuir), les sorts, l'écran et le journal."""

import pytest

from aria import carte_combat
from aria.combat import Combat, Moral, TypeAction
from aria.combat_auto import CombatAuto, Choix, Fin, Geste, Intention, Registre, prochaine_action
from aria.combat_joueur import TourDuJoueur, ecran_du_combat, lignes_du_tour, ouvrir_le_combat
from aria.des import Des, DesTruques
from aria.grille import Carte, Terrain, case, distance
from tests.test_combat import PISTOLET, ganger, kaito
from tests.test_combat_joueur import Script
from tests.test_outils import ganger as creer_ganger
from tests.test_outils import session


def sur_carte(*places, terrain=None, des=None, largeur=40, hauteur=20):
    """Un combat sur une carte nue : places = (combattant, colonne, ligne)."""
    carte = Carte(largeur, hauteur, dict(terrain or {}), bords={"joueurs": 0, "ennemis": largeur - 1})
    for combattant, colonne, rang in places:
        carte.placer(combattant, case(colonne, rang))
    return Combat(des or DesTruques(), [p[0] for p in places], tour_par_tour=False, carte=carte)


# --- L'ouverture du combat par le MJ


def session_a_pied(*des, **options):
    s = session(*des)
    s.combat_par_le_code = True
    s.des_des_cartes = Des(7)
    creer_ganger(s)
    return s


def test_un_combat_a_pied_mene_par_le_code_se_joue_sur_une_carte():
    s = session_a_pied()
    r = s.appeler("debut_combat", {"pnj": ["ganger"], "lieu": "entrepôt", "decor": "fortifié"})
    assert "erreur" not in r and r["lieu"] == "entrepôt (fortifié)"
    carte = s.combat.carte
    assert carte.lieu == "entrepôt" and s.combat.decor.value == "fortifié"
    assert carte.ecart(s.joueur, s.pnj["ganger"]) == 12


def test_par_defaut_une_ruelle_encombree():
    s = session_a_pied()
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert s.combat.carte.lieu == "ruelle" and s.combat.decor.value == "encombré"


def test_en_embuscade_les_camps_commencent_a_six_cases():
    s = session_a_pied()
    s.appeler("debut_combat", {"pnj": ["ganger"], "surpris": "joueur"})
    assert s.combat.carte.ecart(s.joueur, s.pnj["ganger"]) == 6


def test_dessiner_la_carte_ne_consomme_pas_les_des_du_jeu():
    s = session_a_pied()  # DesTruques sans aucune valeur : le moindre jet ferait échouer le test
    assert "erreur" not in s.appeler("debut_combat", {"pnj": ["ganger"]})


def test_sans_menu_ni_mode_a_pied_pas_de_carte():
    s = session()
    creer_ganger(s)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    assert s.combat.carte is None


@pytest.mark.parametrize("arguments, mot", [({"lieu": "cathédrale"}, "cathédrale"), ({"decor": "baroque"}, "baroque")])
def test_un_lieu_ou_un_decor_inconnu_est_refuse(arguments, mot):
    s = session_a_pied()
    r = s.appeler("debut_combat", {"pnj": ["ganger"]} | arguments)
    assert mot in r["erreur"] and s.combat is None


def test_un_renfort_entre_par_le_bord_de_son_cote():
    s = session_a_pied()
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    creer_ganger(s, identifiant="renfort")
    s.appeler("rejoindre_combat", {"pnj": ["renfort"]})
    carte = s.combat.carte
    assert s.pnj["renfort"] in carte.positions
    assert carte.position(s.pnj["renfort"])[0] + carte.position(s.pnj["renfort"])[1] // 2 >= carte.largeur - 3


# --- L'IA sur la carte


def action(c, qui, choix=None):
    return prochaine_action(c, qui, Registre(), choix=choix)


def test_un_bretteur_loin_avance_jusqu_au_contact_s_il_le_peut():
    k, g = kaito(), ganger()
    c = sur_carte((k, 2, 5), (g, 8, 5))
    a = action(c, g)
    assert a.geste is Geste.SE_DEPLACER and distance(a.vers, case(2, 5)) == 1


def test_un_bretteur_trop_loin_se_rapproche_puis_repart_d_un_second_deplacement():
    k, g = kaito(), ganger()
    c = sur_carte((k, 2, 5), (g, 20, 5))
    premier = action(c, g)
    assert premier.geste is Geste.SE_DEPLACER and distance(premier.vers, case(2, 5)) == 12
    c.deplacer(g, premier.vers)
    second = action(c, g)
    assert second.geste is Geste.SE_DEPLACER and distance(second.vers, case(2, 5)) == 6


def test_un_bretteur_au_contact_frappe():
    k, g = kaito(), ganger()
    c = sur_carte((k, 2, 5), (g, 3, 5))
    a = action(c, g)
    assert a.geste is Geste.ATTAQUER and a.cible is k


def test_un_tireur_a_portee_se_poste_derriere_un_obstacle_qui_garde_sa_cible_en_vue():
    k, g = kaito(), ganger(PISTOLET)
    c = sur_carte((k, 2, 5), (g, 9, 5), terrain={case(8, 4): Terrain.BAS})
    assert c.carte.abri(k, g).value == 0  # à découvert là où il est
    a = action(c, g)
    assert a.geste is Geste.SE_DEPLACER
    assert c.carte.abri_entre(case(2, 5), a.vers).value >= 1 and distance(a.vers, case(2, 5)) <= 8


def test_un_tireur_a_couvert_qui_n_a_pas_bouge_vise_puis_tire():
    k, g = kaito(), ganger(PISTOLET)
    c = sur_carte((k, 2, 5), (g, 8, 5), terrain={case(7, 5): Terrain.BAS})
    assert action(c, g).geste is Geste.VISER
    c.viser(g)
    assert action(c, g).geste is Geste.ATTAQUER


def test_un_tireur_hors_de_portee_va_a_une_position_de_tir():
    k, g = kaito(), ganger(PISTOLET)
    c = sur_carte((k, 2, 5), (g, 14, 5))
    a = action(c, g)
    assert a.geste is Geste.SE_DEPLACER and distance(a.vers, case(2, 5)) <= 8


def test_un_fuyard_gagne_le_bord():
    k, g = kaito(), ganger()
    c = sur_carte((k, 2, 5), (g, 30, 5))
    g.moral = Moral.EN_FUITE
    a = action(c, g)
    assert a.geste is Geste.FUIR and a.vers is not None
    bord = c.carte.cases_du_bord()
    assert min(distance(a.vers, b) for b in bord) < min(distance(case(30, 5), b) for b in bord)


def test_le_plan_s_abriter_mene_derriere_un_obstacle():
    k, g = kaito(), ganger(PISTOLET)
    c = sur_carte((k, 2, 5), (g, 9, 5), terrain={case(8, 4): Terrain.BAS})
    a = action(c, g, Choix(Intention.S_ABRITER))
    assert a.geste is Geste.SE_DEPLACER and c.carte.abri_entre(case(2, 5), a.vers).value >= 1


def test_le_plan_attaquer_une_cible_hors_de_portee_laisse_l_ia_decider():
    k, g = kaito(), ganger(PISTOLET)
    c = sur_carte((k, 2, 5), (g, 14, 5))
    a = action(c, g, Choix(Intention.ATTAQUER, k))
    assert a.geste is Geste.SE_DEPLACER  # l'IA s'approche au lieu d'un tir impossible


@pytest.mark.parametrize("lieu", carte_combat.LIEUX)
def test_un_combat_entier_sur_chaque_lieu_se_termine(lieu):
    for graine in range(5):
        des = Des(graine)
        k, g1, g2 = kaito(), ganger(), ganger(PISTOLET, nom="Tireur")
        carte = carte_combat.ouvrir(lieu, carte_combat.Decor.ENCOMBRE, des, [k], [g1, g2])
        combat = Combat(des, [k, g1, g2], tour_par_tour=True, carte=carte)
        auto = CombatAuto(combat, mene=lambda _: True)
        while auto.fin() is Fin.EN_COURS:
            if not auto.avancer():
                break
        assert auto.fin() is not Fin.EN_COURS


# --- Le joueur sur la carte


def partie_sur_carte(*des):
    """Kaito contre un ganger sur une carte nue, Kaito joue le premier : Kaito en (2, 5), le ganger en (9, 5)."""
    s = session_a_pied(*des)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    carte = s.combat.carte
    carte.terrain.clear()
    carte.positions[s.joueur], carte.positions[s.pnj["ganger"]] = case(2, 5), case(9, 5)
    return s


def tour_de(s, script):
    return TourDuJoueur(s, ouvrir_le_combat(s, script.ecran()), script.ecran())


def test_sur_la_carte_le_menu_propose_se_deplacer_et_plus_se_mettre_a_couvert():
    s = partie_sur_carte()
    libelles = [e.option.libelle for e in tour_de(s, Script()).entrees()]
    assert "Se déplacer…" in libelles and not any(l.startswith("Se mettre à couvert") for l in libelles)


def test_se_deplacer_au_contact_du_ganger():
    s = partie_sur_carte()
    script = Script("Se déplacer", "Aller au contact de Ganger", "Terminer")
    tour_de(s, script).jouer()
    assert s.combat.carte.ecart(s.joueur, s.pnj["ganger"]) == 1
    assert s.joueur.budget.utilise[TypeAction.DEPLACEMENT] == 1
    assert "Tu te déplaces : Ganger au contact" in script.texte


def test_une_cible_hors_de_portee_est_grisee_avec_sa_raison():
    s = partie_sur_carte()
    s.combat.carte.positions[s.pnj["ganger"]] = case(20, 5)
    script = Script("Attaquer", "Retour", "Terminer")
    tour_de(s, script).jouer()
    titre, options = next(v for v in script.vues if v[0] == "Qui attaques-tu ?")
    ganger_ = next(o for o in options if o.libelle.startswith("Ganger"))
    assert not ganger_.active and "hors de portée" in ganger_.raison and "à 18 cases" in ganger_.libelle


def test_l_ecran_donne_le_lieu_et_les_positions():
    s = partie_sur_carte()
    lignes = ecran_du_combat(s.combat, s.joueur, Script().ecran())
    assert lignes[0] == "— Round 1 — ruelle (encombré) —"
    assert "Positions : Ganger à 7 cases" in "\n".join(lignes)


def test_fuir_sur_la_carte_mene_vers_le_bord():
    s = partie_sur_carte()
    bord = s.combat.carte.cases_du_bord()
    avant = min(distance(case(2, 5), b) for b in bord)
    sortie = tour_de(s, Script("Fuir", "Oui")).jouer()
    apres = min(distance(s.combat.carte.position(s.joueur), b) for b in bord)
    assert sortie.nature.name == "FUITE" and apres < avant


def test_le_journal_dit_ou_mene_le_deplacement_d_un_ennemi():
    s = partie_sur_carte(90, 50)  # arrivé au contact, le ganger frappe et rate
    g = s.pnj["ganger"]
    auto = ouvrir_le_combat(s, Script().ecran())
    s.combat.actif = s.combat.ordre.index(g)
    rapport = auto.jouer_le_tour()
    lignes = lignes_du_tour(rapport, s.combat, Script().ecran())
    assert any("Ganger se déplace : le voilà au contact" in l for l in lignes)


# --- Les sorts sur la carte


def test_un_sort_porte_vingt_cases_avec_la_ligne_de_tir():
    k, g = kaito(), ganger()
    c = sur_carte((k, 0, 5), (g, 20, 5))
    assert c.raison_de_ne_pas_lancer(k, g) is None
    c.carte.positions[g] = case(21, 5)
    assert "hors de portée d'un sort" in c.raison_de_ne_pas_lancer(k, g)
    c.carte.positions[g] = case(6, 5)
    c.carte.terrain[case(3, 5)] = Terrain.PLEIN
    assert "coupe la ligne" in c.raison_de_ne_pas_lancer(k, g)
    assert c.raison_de_ne_pas_lancer(k, k) is None  # sur soi-même


def test_le_couvert_d_un_sort_vient_de_la_carte():
    k, g = kaito(), ganger()
    c = sur_carte((k, 0, 5), (g, 6, 5), terrain={case(5, 5): Terrain.BAS})
    assert c.couvert_du_sort(k, g).name == "PARTIEL"
    assert Combat(DesTruques(), [k, g]).couvert_du_sort(k, g) is g.couvert  # sans carte : son couvert à lui


# --- Non-régression : ce que l'essai de combats complets a trouvé


def test_un_bretteur_qui_a_deja_frappe_garde_sa_place():
    k, g = kaito(), ganger()
    c = sur_carte((k, 2, 5), (g, 3, 5), des=DesTruques(90, 90))
    c.attaquer(g, k)
    assert action(c, g) is None  # il lui reste un déplacement, mais quelqu'un est à sa portée


def test_le_journal_donne_la_position_de_chaque_pas_et_pas_seulement_la_derniere():
    s = partie_sur_carte(90, 50)
    g = s.pnj["ganger"]
    s.combat.carte.positions[g] = case(20, 5)  # à 18 cases : deux déplacements le mènent à 12, puis à 6
    auto = ouvrir_le_combat(s, Script().ecran())
    s.combat.actif = s.combat.ordre.index(g)
    lignes = lignes_du_tour(auto.jouer_le_tour(), s.combat, Script().ecran())
    pas = [l for l in lignes if "se déplace" in l]
    assert len(pas) == 2 and "à 12 cases" in pas[0] and "à 6 cases" in pas[1]
