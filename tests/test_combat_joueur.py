"""Le tour du joueur dans un combat à pied : le menu, l'écran, ses réactions, la boucle (REGLES.md 7.8).

Le joueur est Kaito (23 PV, Armes à distance 50, Esquive 50, Corps à corps 25, pistolet lourd Arasaka) ; le ganger a
un couteau et 45 %. Les choix du joueur sont scriptés : chaque étape est le début du libellé de l'option choisie.
"""

import pytest

from aria.choix import Option, choisir_console
from aria.combat import BonusMajeure, Combat, Combattant, Couvert, Decor, Defense, FichePnj, Moral, TypeAction
from aria.combat_auto import CombatAuto, Fin
from aria.combat_joueur import (
    Ecran,
    Nature,
    ReactionsDuJoueur,
    Sortie,
    TourDuJoueur,
    budget_restant,
    ecran_du_combat,
    etat_visible,
    jouer_les_pnj,
    lignes_de_fin,
    lignes_du_tour,
    mener_le_combat,
    ouvrir_la_poursuite,
    ouvrir_le_combat,
)
from aria.des import DesTruques
from aria.personnage import Etat
from tests.test_magie import session_fantasy
from tests.test_outils import ganger as creer_ganger
from tests.test_outils import session


class Script:
    """Les choix du joueur : une liste d'étapes, chacune le début du libellé de l'option à prendre."""

    def __init__(self, *etapes: str, saisies: tuple[str, ...] = ()):
        self.etapes, self.saisies = list(etapes), list(saisies)
        self.vues: list[tuple[str, list[Option]]] = []
        self.lignes: list[str] = []

    def choisir(self, titre: str, options: list[Option]) -> int:
        self.vues.append((titre, options))
        assert self.etapes, f"Le script n'a plus d'étape, et on demande : {titre} {[o.libelle for o in options]}"
        etape = self.etapes.pop(0)
        for indice, option in enumerate(options):
            if option.libelle.startswith(etape):
                assert option.active, f"« {option.libelle} » est grisée : {option.raison}"
                return indice
        raise AssertionError(f"Pas d'option « {etape} » dans {[o.libelle for o in options]}")

    def entree(self, invite: str) -> str:
        return self.saisies.pop(0)

    def ecran(self, **options) -> Ecran:
        return Ecran(self.lignes.append, self.choisir, self.entree, pause=lambda _: None, **options)

    @property
    def texte(self) -> str:
        return "\n".join(self.lignes)


def combat_de_session(*des, rapide=False, **profil):
    """Kaito contre un ganger. `rapide` : le ganger joue avant Kaito."""
    s = session(*des)
    creer_ganger(s, **({"dexterite": 70} if rapide else {}) | profil)
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    return s, s.pnj["ganger"]


def tour(s, script, **options):
    return TourDuJoueur(s, ouvrir_le_combat(s, script.ecran(**options)), script.ecran(**options))


def menu_de(t):
    return {e.option.libelle.split(" (")[0].rstrip("…"): e for e in t.entrees()}


def libelles(s, script=None, **options):
    return menu_de(tour(s, script or Script(), **options))


# --- Le choix en console --------------------------------------------------------------------------

def test_la_console_numerote_et_renvoie_l_indice():
    sortie, reponses = [], iter(["2"])
    choisir = choisir_console(lambda _: next(reponses), sortie.append)
    assert choisir("Que fais-tu ?", [Option("Tirer"), Option("Fuir")]) == 1
    assert sortie == ["Que fais-tu ?", "  1. Tirer", "  2. Fuir"]


def test_la_console_redemande_un_numero_invalide_ou_grise():
    sortie, reponses = [], iter(["x", "9", "1", "2"])
    choisir = choisir_console(lambda _: next(reponses), sortie.append)
    options = [Option("Recharger", "le chargeur est plein"), Option("Tirer")]
    assert choisir("Que fais-tu ?", options) == 1
    assert "  1. Recharger  (impossible : le chargeur est plein)" in sortie
    assert "Impossible : le chargeur est plein." in sortie
    assert sortie.count("Tape un nombre entre 1 et 2.") == 2


# --- Le moteur : la défense réelle et le bonus choisi après coup ----------------------------------------

def test_la_valeur_de_defense_compte_les_malus_comme_le_jet_de_defense():
    k = Combattant(FichePnj("K", combat=50, pv_max_base=10), "joueur")
    assert Combat.valeur_de_defense(k, Defense.ESQUIVE) == 50
    k.defenses_ce_round, k.desequilibre = 1, True
    assert Combat.valeur_de_defense(k, Defense.ESQUIVE) == 50 - 20 - 20


def test_la_valeur_de_defense_annoncee_est_celle_du_jet():
    s, g = combat_de_session(90, 60, rapide=True)
    s.joueur.defenses_ce_round = 1
    annoncee = Combat.valeur_de_defense(s.joueur, Defense.ESQUIVE)
    rapport = s.combat.attaquer(g, s.joueur, Defense.ESQUIVE)
    assert rapport.defense.valeur == annoncee


def test_le_bonus_de_majeure_peut_se_choisir_apres_le_jet():
    s, g = combat_de_session(20, 3)  # Kaito touche en majeure (20 ≤ 25), 1d10 = 3 : pas de blessure grave
    vus = []

    def choix(source, victime, options):
        vus.append(options)
        return BonusMajeure.DESARMER

    rapport = s.combat.attaquer(s.joueur, g, bonus_majeure=choix)
    assert vus == [[BonusMajeure.DE_SUPPLEMENTAIRE, BonusMajeure.DESARMER]] and g.arme is None
    assert any("désarmé" in e for e in rapport.effets)


def test_sans_vrai_choix_le_bonus_de_majeure_n_est_pas_demande():
    s, g = combat_de_session(20, 2, 1)  # le ganger est désarmé d'avance : seul « +1 dé » reste
    g.arme = None
    appels = []
    s.combat.attaquer(s.joueur, g, bonus_majeure=lambda *a: appels.append(a))
    assert appels == []


# --- L'écran -------------------------------------------------------------------------------------

@pytest.mark.parametrize("changement, attendu", [
    ({}, "indemne"),
    ({"pv": 5}, "blessé"),
    ({"pv": 5, "blessure_grave": True}, "gravement blessé"),
    ({"etat": Etat.INCONSCIENT}, "à terre"),
    ({"etat": Etat.MOURANT}, "à terre"),
])
def test_l_etat_visible_d_un_ennemi(changement, attendu):
    _, g = combat_de_session()
    for cle, valeur in changement.items():
        setattr(g.fiche, cle, valeur)
    assert etat_visible(g) == attendu


@pytest.mark.parametrize("moral, attendu", [(Moral.EN_FUITE, "en fuite"), (Moral.RENDU, "rendu"), (Moral.PARTI, "parti")])
def test_l_etat_visible_d_un_moral_brise(moral, attendu):
    _, g = combat_de_session()
    g.moral = moral
    assert etat_visible(g) == attendu


def test_l_ecran_montre_l_etat_des_ennemis_et_les_pv_du_joueur():
    s, g = combat_de_session()
    g.fiche.pv = 5
    texte = "\n".join(ecran_du_combat(s.combat, s.joueur, Script().ecran()))
    assert "Round 1" in texte and "décor encombré" in texte
    assert "→ Kaito (23/23 PV)" in texte and "Ganger (blessé)" in texte and "5/10" not in texte
    assert "Pistolet lourd Arasaka (8/8)" in texte


def test_les_pv_exacts_des_ennemis_sont_un_reglage():
    s, g = combat_de_session()
    g.fiche.pv = 5
    texte = "\n".join(ecran_du_combat(s.combat, s.joueur, Script().ecran(pv_exacts=True)))
    assert "Ganger (5/10 PV)" in texte


def test_l_ecran_dit_si_le_joueur_est_a_couvert():
    s, _ = combat_de_session()
    s.joueur.couvert = Couvert.PARTIEL
    assert ", à couvert" in "\n".join(ecran_du_combat(s.combat, s.joueur, Script().ecran()))


def test_le_budget_restant_se_lit():
    s, _ = combat_de_session()
    assert budget_restant(s.joueur) == "2 déplacements, 1 action simple, 1 action mineure"  # chacun, seul
    s.combat.deplacer(s.joueur)
    s.combat.deplacer(s.joueur)
    assert budget_restant(s.joueur) == "0 déplacement, 0 action simple, 1 action mineure"


# --- Le menu : légal, ou grisé avec sa raison -----------------------------------------------------------

def test_le_menu_du_debut_de_tour():
    s, _ = combat_de_session()
    menu = libelles(s)
    assert list(menu) == ["Attaquer", "Viser", "Recharger", "Changer d'arme", "Se mettre à couvert", "Parler",
                          "Autre action", "Fuir", "Terminer le tour"]
    assert menu["Attaquer"].option.active and menu["Viser"].option.active and menu["Parler"].option.active
    assert menu["Recharger"].option.raison == "le chargeur est plein"


def test_aucun_deplacement_nu_dans_le_menu():
    s, _ = combat_de_session()
    assert not any(l.startswith("Se déplacer") for l in libelles(s))


def test_attaquer_se_grise_une_fois_l_action_simple_depensee():
    s, _ = combat_de_session()
    s.combat.action_simple(s.joueur)
    assert libelles(s)["Attaquer"].option.raison == "action simple déjà utilisée"


def test_attaquer_se_grise_si_l_arme_est_vide_ou_enrayee():
    s, _ = combat_de_session()
    s.joueur.munitions[s.joueur.arme] = 0
    assert "recharge" in libelles(s)["Attaquer"].option.raison
    s.joueur.munitions[s.joueur.arme] = 8
    s.joueur.arme_enrayee = s.joueur.arme
    menu = libelles(s)
    assert "enrayée" in menu["Attaquer"].option.raison and "Débloquer ton arme enrayée" in menu


def test_se_mettre_a_couvert_depend_du_decor_et_de_l_etat():
    s, _ = combat_de_session()
    assert libelles(s)["Se mettre à couvert"].option.active
    s.joueur.couvert = Couvert.PARTIEL
    assert libelles(s)["Se mettre à couvert"].option.raison == "tu es déjà à couvert"
    s.joueur.couvert = Couvert.AUCUN
    s.combat.decor = Decor.DEGAGE
    assert "dégagé" in libelles(s)["Se mettre à couvert"].option.raison


def test_viser_se_grise_apres_un_deplacement_et_au_corps_a_corps():
    s, _ = combat_de_session()
    s.combat.deplacer(s.joueur)
    assert libelles(s)["Viser"].option.raison == "tu t'es déplacé ce round"
    s.joueur.budget = type(s.joueur.budget)()
    s.joueur.arme = None
    assert "arme de tir" in libelles(s)["Viser"].option.raison


def test_fuir_veut_deux_deplacements():
    s, _ = combat_de_session()
    s.combat.action_simple(s.joueur)
    assert "deux déplacements" in libelles(s)["Fuir"].option.raison


def test_changer_d_arme_liste_les_armes_possedees():
    s, _ = combat_de_session()
    script = Script("Retour")
    assert libelles(s, script)["Changer d'arme"].faire() is None
    assert "Prendre Couteau" in [o.libelle for o in script.vues[0][1]]
    assert s.joueur.budget.utilise[TypeAction.MINEURE] == 0


# --- Attaquer ---------------------------------------------------------------------------------------

def test_le_sous_menu_des_cibles_donne_la_chance_de_toucher():
    s, g = combat_de_session()
    script = Script("Retour")
    assert tour(s, script).entrees()[0].faire() is None
    titre, options = script.vues[0]
    chance = s.combat.chance_de_toucher(s.joueur, g)
    assert titre == "Qui attaques-tu ?" and options[0].libelle == f"Ganger (indemne) — {chance} % de toucher"
    assert options[-1].libelle == "Retour" and s.joueur.budget.utilise[TypeAction.SIMPLE] == 0


def test_attaquer_fait_tirer_le_moteur_et_raconte_sans_les_pv_de_l_ennemi():
    s, g = combat_de_session(30, 6, 10)  # touche (30 ≤ 50), 1d10 = 6 (+1 de l'Arasaka), Constitution réussie
    script = Script("Ganger")
    assert tour(s, script).entrees()[0].faire() is None
    assert g.fiche.pv == 3 and s.joueur.budget.utilise[TypeAction.SIMPLE] == 1
    assert "Kaito attaque Ganger : 30 pour 50 : réussite" in script.texte
    assert "Ganger est touché" in script.texte and "PV 10" not in script.texte


def test_les_pv_de_l_ennemi_s_affichent_si_le_joueur_les_veut():
    s, g = combat_de_session(30, 6, 10)
    script = Script("Ganger")
    tour(s, script, pv_exacts=True).entrees()[0].faire()
    assert "PV 10 → 3" in script.texte


def test_un_ennemi_touche_garde_son_rang_dans_le_registre():
    s, g = combat_de_session(90)
    t = tour(s, Script("Ganger"))
    t.entrees()[0].faire()
    assert t.auto.registre.attaquants[g] == {s.joueur}


def test_un_refus_du_moteur_se_lit_et_le_tour_continue():
    s, g = combat_de_session()
    script = Script("Ganger")
    entree = menu_de(tour(s, script))["Attaquer"]
    s.joueur.munitions[s.joueur.arme] = 0  # le menu a été construit avant : le moteur refuse
    assert entree.faire() is None
    assert "Impossible : L'arme de Kaito est vide" in script.texte
    assert s.joueur.budget.utilise[TypeAction.SIMPLE] == 0


# --- Les autres actions -------------------------------------------------------------------------------

def test_viser_puis_le_bonus_de_visee_compte_au_tir_suivant():
    s, g = combat_de_session(90)
    script = Script("Viser")
    menu_de(tour(s, script))["Viser"].faire()
    assert s.joueur.vise and "Tu prends le temps de viser." in script.texte
    assert s.combat.chance_de_toucher(s.joueur, g) > 50


def test_se_mettre_a_couvert_coute_un_deplacement():
    s, _ = combat_de_session()
    libelles(s)["Se mettre à couvert"].faire()
    assert s.joueur.couvert is Couvert.PARTIEL and s.joueur.budget.utilise[TypeAction.DEPLACEMENT] == 1


def test_recharger_remplit_le_chargeur():
    s, _ = combat_de_session()
    s.joueur.munitions[s.joueur.arme] = 2
    libelles(s)["Recharger"].faire()
    assert s.joueur.munitions_restantes() == 8


def test_changer_d_arme_prend_l_arme_choisie_pour_une_action_mineure():
    s, _ = combat_de_session()
    s.joueur.arme_lachee = s.joueur.arme
    s.joueur.arme = None
    script = Script("Ramasser")
    menu_de(tour(s, script))["Changer d'arme"].faire()
    assert s.joueur.arme.nom == "Pistolet lourd Arasaka" and s.joueur.arme_lachee is None
    assert s.joueur.budget.utilise[TypeAction.MINEURE] == 1


def test_parler_rend_la_main_au_mj_pour_une_action_mineure():
    s, _ = combat_de_session()
    script = Script(saisies=("Posez vos armes, on peut en parler.",))
    sortie = libelles(s, script)["Parler"].faire()
    assert sortie == Sortie(Nature.PARLER, "Posez vos armes, on peut en parler.")
    assert s.joueur.budget.utilise[TypeAction.MINEURE] == 1


def test_autre_action_coute_une_action_simple():
    s, _ = combat_de_session()
    script = Script(saisies=("Je renverse la benne sur eux.",))
    sortie = libelles(s, script)["Autre action"].faire()
    assert sortie == Sortie(Nature.AUTRE_ACTION, "Je renverse la benne sur eux.")
    assert s.joueur.budget.utilise[TypeAction.SIMPLE] == 1


def test_un_texte_vide_annule_l_action_sans_la_depenser():
    s, _ = combat_de_session()
    assert libelles(s, Script(saisies=("  ",)))["Parler"].faire() is None
    assert s.joueur.budget.utilise[TypeAction.MINEURE] == 0


def test_fuir_confirme_deplace_deux_fois_et_donne_les_poursuivants():
    s, g = combat_de_session()
    script = Script("Oui")
    sortie = libelles(s, script)["Fuir"].faire()
    assert sortie.nature is Nature.FUITE and sortie.poursuivants == (g,)
    assert s.joueur.budget.utilise[TypeAction.DEPLACEMENT] == 2
    assert "te poursuivront" in script.vues[0][0]


def test_fuir_refuse_ne_depense_rien():
    s, _ = combat_de_session()
    assert libelles(s, Script("Non"))["Fuir"].faire() is None
    assert s.joueur.budget.utilise[TypeAction.DEPLACEMENT] == 0


def test_la_fuite_ouvre_une_poursuite_avec_les_ennemis_pour_poursuivants():
    s, g = combat_de_session()
    r = ouvrir_la_poursuite(s, (g,), "Centre-ville")
    assert "erreur" not in r and s.poursuite is not None
    assert [c.identifiant for c in s.poursuite.poursuivants] == ["ganger"] and s.poursuite.fuyard.identifiant == "joueur"


def test_stabiliser_n_apparait_qu_avec_un_allie_et_se_grise_sans_mourant():
    s, _ = combat_de_session()
    assert "Stabiliser" not in libelles(s)
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10), "allies")
    s.combat.rejoindre(allie)
    assert libelles(s)["Stabiliser"].option.raison == "aucun allié n'est mourant"
    allie.fiche.etat = Etat.MOURANT
    assert libelles(s)["Stabiliser"].option.active


def test_stabiliser_un_allie_mourant():
    s, _ = combat_de_session(1)  # Médecine réussie (un 01 réussit toujours)
    allie = Combattant(FichePnj("Allié", combat=40, pv_max_base=10, pv=0, etat=Etat.MOURANT), "allies")
    s.combat.rejoindre(allie)
    script = Script("Allié")
    libelles(s, script)["Stabiliser"].faire()
    assert allie.fiche.etat is Etat.STABLE and "stabilisé" in script.texte


# --- Les sorts -----------------------------------------------------------------------------------------

def session_de_mage(*des):
    s = session_fantasy(*des)
    creer_ganger(s, arme="Dague", dexterite=15)  # Elara joue la première
    s.appeler("debut_combat", {"pnj": ["ganger"]})
    return s


def test_le_menu_des_sorts_ne_garde_que_les_sorts_a_une_cible():
    s = session_de_mage()
    script = Script("Trait de feu", "Retour")
    libelles(s, script)["Lancer un sort"].faire()
    noms = [o.libelle.split(" (")[0] for o in script.vues[0][1]]
    assert "Trait de feu" in noms and "Peau de braise" in noms and "Brasier" in noms
    assert "Gerbe de flammes" not in noms and "Égide" not in noms  # un sort de zone reste au MJ
    assert "Allumer ou souffler une flamme" not in noms  # un sort utilitaire passe par « Autre action »


def test_lancer_un_sort_d_attaque_sur_un_ennemi():
    s = session_de_mage(30, 3, 4, 10)
    script = Script("Trait de feu", "Ganger")
    libelles(s, script)["Lancer un sort"].faire()
    assert "lance Trait de feu" in script.texte and s.pnj["ganger"].fiche.pv < 10
    assert s.joueur.budget.utilise[TypeAction.SIMPLE] == 1


def test_sans_magie_pas_d_entree_de_sort():
    s, _ = combat_de_session()
    assert "Lancer un sort" not in libelles(s)


# --- Les réactions --------------------------------------------------------------------------------------

def test_par_defaut_le_code_choisit_la_defense_du_joueur():
    s, _ = combat_de_session(90, 50, rapide=True)
    script = Script()
    auto = ouvrir_le_combat(s, script.ecran())
    jouer_les_pnj(auto, script.ecran())
    assert script.vues == []  # aucune question
    assert "Ganger attaque Kaito" in script.texte and "Kaito se défend" in script.texte


def test_je_choisis_ma_defense_pose_la_question_avec_les_chances():
    s, g = combat_de_session(90, 40, rapide=True)  # le ganger rate ; Kaito tente sa riposte (25 %) : 40 rate
    script = Script("Riposter")
    ecran = script.ecran(choisir_sa_defense=True)
    jouer_les_pnj(ouvrir_le_combat(s, ecran), ecran)
    titre, options = script.vues[0]
    assert titre == "Ganger t'attaque. Comment réagis-tu ?"
    assert options[0].libelle == "Esquiver (50 % de réussir)" and options[1].libelle == "Riposter (25 % de réussir)"
    assert s.joueur.defenses_ce_round == 1


def test_la_reaction_ne_regarde_que_les_attaques_contre_le_joueur():
    s, g = combat_de_session()
    r = ReactionsDuJoueur(s.joueur, Script().ecran(choisir_sa_defense=True))
    assert r.defense(s.joueur, g) is None


def test_le_joueur_choisit_son_bonus_de_majeure_mais_pas_les_pnj():
    s, g = combat_de_session()
    script = Script("désarmer")
    r = ReactionsDuJoueur(s.joueur, script.ecran())
    options = [BonusMajeure.DE_SUPPLEMENTAIRE, BonusMajeure.DESARMER]
    assert r.bonus_majeure(s.joueur, g, options) is BonusMajeure.DESARMER
    assert r.bonus_majeure(g, s.joueur, options) is BonusMajeure.DE_SUPPLEMENTAIRE
    assert len(script.vues) == 1


# --- La boucle du combat ------------------------------------------------------------------------------

def test_les_pnj_jouent_avant_le_joueur_et_la_boucle_s_arrete_a_son_tour():
    s, g = combat_de_session(90, 50, rapide=True)
    script = Script()
    ecran = script.ecran()
    rapports = jouer_les_pnj(ouvrir_le_combat(s, ecran), ecran)
    assert [r.qui for r in rapports] == [g] and s.combat.au_tour_de is s.joueur
    assert script.texte.startswith("\nGanger :")


def test_la_pause_entre_les_actions_de_pnj_est_courte():
    s, _ = combat_de_session(90, 50, rapide=True)
    pauses = []
    ecran = Ecran(lambda _: None, Script().choisir, Script().entree, pause=pauses.append)
    jouer_les_pnj(ouvrir_le_combat(s, ecran), ecran)
    assert pauses == [0.6]


def test_un_combat_gagne_par_le_joueur_se_termine_par_une_victoire():
    s, g = combat_de_session(1)  # Kaito sort un 01 : critique, dégâts maximum (10 + 1) contre 10 PV
    script = Script("Attaquer", "Ganger")
    ecran = script.ecran()
    fin = mener_le_combat(s, ouvrir_le_combat(s, ecran), ecran)
    assert fin is Fin.VICTOIRE and g.fiche.etat is Etat.MOURANT
    assert lignes_de_fin(fin) == ["\nPlus aucun ennemi ne tient : le combat est fini."]


def test_un_combat_perdu_se_termine_par_une_defaite():
    s, _ = combat_de_session()
    s.joueur.fiche.etat = Etat.INCONSCIENT
    script = Script()
    ecran = script.ecran()
    assert mener_le_combat(s, ouvrir_le_combat(s, ecran), ecran) is Fin.DEFAITE
    assert "perdu" in lignes_de_fin(Fin.DEFAITE)[0]


def test_la_boucle_rend_la_main_au_mj_puis_reprend_le_tour_la_ou_il_en_etait():
    s, _ = combat_de_session()
    script = Script("Parler", "Terminer", "Parler", saisies=("On peut s'arranger.", "Et maintenant ?"))
    ecran = script.ecran()
    auto = ouvrir_le_combat(s, ecran)
    sortie = mener_le_combat(s, auto, ecran)
    assert sortie == Sortie(Nature.PARLER, "On peut s'arranger.")
    assert s.combat.au_tour_de is s.joueur and s.joueur.budget.utilise[TypeAction.MINEURE] == 1
    s.combat.des = DesTruques(90, 50)  # le ganger frappe pendant la suite, et rate
    sortie = mener_le_combat(s, auto, ecran)  # Kaito termine son tour, le ganger joue, au round 2 il reparle
    assert s.combat.round == 2 and sortie == Sortie(Nature.PARLER, "Et maintenant ?")


def test_plus_rien_a_faire_termine_le_tour_tout_seul():
    s, _ = combat_de_session()
    s.combat.deplacer(s.joueur)
    s.combat.action_simple(s.joueur)
    s.combat._agir(s.joueur, TypeAction.MINEURE)
    script = Script()
    sortie = tour(s, script).jouer()
    assert sortie == Sortie(Nature.FIN_DU_TOUR) and "Plus rien à faire" in script.texte


def test_les_lignes_du_tour_disent_le_moral_d_un_ennemi_qui_craque():
    s, g = combat_de_session(99, rapide=True)
    g.fiche.pv = 4
    script = Script()
    ecran = script.ecran()
    rapport = CombatAuto(s.combat, reactions=None).jouer_le_tour()
    texte = "\n".join(lignes_du_tour(rapport, s.combat, ecran))
    assert "est éprouvé (la moitié de ses PV)" in texte and "s'enfuit" in texte and "court vers la sortie" in texte


def test_la_fin_du_tour_du_joueur_ne_le_dit_pas_inactif():
    s, _ = combat_de_session(90, 50)  # le ganger frappe après Kaito, et rate
    script = Script("Terminer", "Parler", saisies=("On cause ?",))  # au round 2, Kaito reparle
    ecran = script.ecran()
    assert mener_le_combat(s, ouvrir_le_combat(s, ecran), ecran) == Sortie(Nature.PARLER, "On cause ?")
    assert s.combat.round == 2 and "Kaito ne fait rien" not in script.texte


def test_les_lignes_du_tour_disent_qu_un_pnj_choisit_de_fuir_sans_test():
    from aria.combat import RapportMoral
    from aria.combat_auto import RapportTour
    s, g = combat_de_session(rapide=True)
    for moral, attendu in ((Moral.EN_FUITE, "choisit de s'enfuir"), (Moral.RENDU, "choisit de se rendre")):
        rapport = RapportTour(g, 1, moral=RapportMoral("Ganger", ["la moitié de ses PV"], None, moral))
        texte = "\n".join(lignes_du_tour(rapport, s.combat, Script().ecran()))
        assert attendu in texte and "Moral :" not in texte
