import pytest

from aria import chemins, soins
from aria.banc import FICHE_ELARA
from aria.combat import Combat, Combattant, Couvert, FichePnj
from aria.compte_rendu import decrire
from aria.des import DesTruques
from aria.magie import (
    Domaine,
    Effet,
    ProprieteSort,
    Puissance,
    Sort,
    SortImpossible,
    lancer,
    verifier_domaine,
    verifier_domaines,
)
from aria.outils import Session, _fiche
from aria.personnage import Etat
from aria.resolution import Degre, Difficulte
from aria.temps import Moment, Periode
from aria.univers import UniversInvalide, charger_univers

MATIN = Moment(1, Periode.MATIN)
APRES_MIDI = Moment(1, Periode.APRES_MIDI)
NUIT = Moment(1, Periode.NUIT)
FANTASY = charger_univers(chemins.UNIVERS / "fantasy.json", genere=True)


def elara(**changements) -> Combattant:
    """Elara : Arcanes 50, 14 PM, 23 PV ; Pyromancie et Guérison."""
    perso = FANTASY.creer_personnage("Mage", **FICHE_ELARA)
    for cle, valeur in changements.items():
        setattr(perso, cle, valeur)
    return Combattant(perso, "joueur")


def brigand(pv=20, **profil) -> Combattant:
    return Combattant(FichePnj("Brigand", combat=45, pv_max_base=pv, dexterite=40, **profil), "ennemis")


def sort(nom: str) -> Sort:
    return FANTASY.sort(nom)


def combat(*combattants: Combattant, des: tuple[int, ...] = ()) -> Combat:
    """Les dés du combat servent aussi aux dégâts des sorts : ce sont ceux de la session."""
    return Combat(DesTruques(*des), list(combattants), tour_par_tour=True)


# --- Les fiches de sort -------------------------------------------------------------------------

def test_puissance_cout_et_difficulte():
    assert [(p.cout, p.difficulte) for p in Puissance] == [
        (1, Difficulte.FACILE), (3, Difficulte.NORMALE), (6, Difficulte.DIFFICILE)]
    assert sort("Brasier").cout == 7  # majeur + une propriété
    assert sort("Écran de fumée").difficulte is Difficulte.DIFFICILE  # improvisation modérée : un cran de plus
    assert sort("Allumer ou souffler une flamme").difficulte is Difficulte.NORMALE


def test_les_domaines_d_exemple_sont_valides():
    assert verifier_domaines(FANTASY.domaines) == []
    assert FANTASY.domaine("Guérison").effets.isdisjoint({Effet.ATTAQUE})


def _domaine(sorts=(), improvisations=(), effets=frozenset(Effet)) -> Domaine:
    base = [Sort(f"Sort {i}", Effet.UTILITAIRE, Puissance.MINEUR) for i in range(4)]
    impro = [Sort(f"Impro {i}", Effet.UTILITAIRE, Puissance.MINEUR, improvisation=True) for i in range(3)]
    return Domaine("Test", frozenset(effets), tuple(base + list(sorts)), tuple(impro + list(improvisations)))


@pytest.mark.parametrize("domaine, erreur", [
    (_domaine(effets={Effet.UTILITAIRE, Effet.SOIN}, sorts=[Sort("Feu", Effet.ATTAQUE, Puissance.MINEUR)]),
     "n'est pas permis"),
    (_domaine(improvisations=[Sort("Grosse impro", Effet.UTILITAIRE, Puissance.MAJEUR, improvisation=True)]),
     "modérée au plus"),
    (_domaine(improvisations=[Sort("Impro zone", Effet.SOIN, Puissance.MINEUR, ProprieteSort.ZONE,
                                   improvisation=True)]), "jamais de propriété"),
    (_domaine(sorts=[Sort("Bouclier tenace", Effet.PROTECTION, Puissance.MINEUR, ProprieteSort.PERSISTANT)]),
     "ne va pas avec"),
    (_domaine(sorts=[Sort("Lumière en zone", Effet.UTILITAIRE, Puissance.MINEUR, ProprieteSort.ZONE)]),
     "ne va pas avec"),
    (_domaine(sorts=[Sort("Effroi tenace", Effet.ENTRAVE, Puissance.MAJEUR, ProprieteSort.PERSISTANT)]),
     "tout le combat"),
    (_domaine(sorts=[Sort(f"En trop {i}", Effet.UTILITAIRE, Puissance.MINEUR) for i in range(3)]), "sorts appris"),
])
def test_verifier_un_domaine(domaine, erreur):
    assert any(erreur in e for e in verifier_domaine(domaine))


def test_verifier_les_domaines_d_un_univers():
    assert any("de 3 à 6 domaines" in e for e in verifier_domaines(FANTASY.domaines[:2]))
    double = FANTASY.domaines[:3] + (FANTASY.domaines[0],)
    assert any("existe deux fois" in e for e in verifier_domaines(double))


def test_un_perso_choisit_deux_domaines():
    perso = elara().fiche
    assert perso.domaines == ["Pyromancie", "Guérison"] and perso.pm == 14
    assert len(FANTASY.sorts_connus(perso.domaines)) == 18
    with pytest.raises(UniversInvalide, match="2 domaines"):
        FANTASY.creer_personnage("Mage", **(FICHE_ELARA | {"domaines": ["Pyromancie"]}))
    with pytest.raises(UniversInvalide, match="inconnu"):
        FANTASY.creer_personnage("Mage", **(FICHE_ELARA | {"domaines": ["Pyromancie", "Chronomancie"]}))


# --- Le lancer ----------------------------------------------------------------------------------

def test_trait_de_feu_en_combat():
    e, b = elara(), brigand()
    c = combat(e, b, des=(30, 3, 4))
    r = lancer(c.des, e, sort("Trait de feu"), [b], c)  # 30 ≤ 50 : réussite, 2d6 = 7
    assert r.test.degre is Degre.REUSSITE and r.pm_depenses == 3 and e.fiche.pm == 11
    assert r.cibles[0].attaque.blessure.degats == 7 and b.fiche.pv == 13


def test_le_couvert_gene_un_sort_d_attaque():
    e, b = elara(), brigand()
    r = lancer(DesTruques(45), e, sort("Trait de feu"), [b], combat(e, b), Couvert.PARTIEL)
    assert r.test.valeur == 30 and not r.test.reussi


def test_un_echec_coute_la_moitie():
    e, b = elara(), brigand()
    r = lancer(DesTruques(80), e, sort("Trait de feu"), [b], combat(e, b))
    assert not r.test.reussi and r.pm_depenses == 2 and b.fiche.pv == 20  # 3 / 2, arrondi au-dessus


def test_la_maladresse_se_retourne():
    e, b = elara(), brigand()
    r = lancer(DesTruques(100, 4), e, sort("Trait de feu"), [b], combat(e, b))
    assert r.test.degre is Degre.MALADRESSE and r.pm_depenses == 3
    assert e.fiche.pv == 19 and "se retourne" in r.retour and b.fiche.pv == 20


def test_a_court_de_pm_on_puise_dans_sa_vie():
    e, b = elara(pm=1), brigand()
    c = combat(e, b, des=(30, 1, 1))
    r = lancer(c.des, e, sort("Trait de feu"), [b], c)
    assert (r.pm_depenses, r.pv_puises, e.fiche.pm, e.fiche.pv) == (1, 2, 0, 21)


def test_un_sort_d_attaque_se_lance_en_combat():
    with pytest.raises(SortImpossible, match="en combat"):
        lancer(DesTruques(30), elara(), sort("Trait de feu"), [brigand()])


def test_un_sort_de_zone_touche_deux_cibles():
    e, b1, b2 = elara(), brigand(), brigand()
    c = combat(e, b1, b2, des=(30, 1, 2, 3, 4))
    r = lancer(c.des, e, sort("Gerbe de flammes"), [b1, b2], c)
    assert [x.attaque.blessure.degats for x in r.cibles] == [3, 7] and r.pm_depenses == 4
    with pytest.raises(SortImpossible, match="une cible"):
        lancer(DesTruques(30), e, sort("Trait de feu"), [b1, b2], c)


def test_protection_et_renfort():
    e, b = elara(), brigand()
    c = combat(e, b)
    lancer(DesTruques(30), e, sort("Peau de braise"), [e], c)
    assert e.protection == 2
    c.fin_de_tour(), c.fin_de_tour()  # le brigand joue, puis le round se clôt
    assert e.protection == 2  # jusqu'à la fin du combat
    lancer(DesTruques(30), e, sort("Bénédiction"), [e], c)
    assert e.valeur("Esquive") == 55 + 20
    c.fin_de_tour(), c.fin_de_tour()
    assert e.valeur("Esquive") == 55  # un round seulement


def test_hors_combat_un_renfort_vaut_pour_le_prochain_jet():
    e = elara()
    lancer(DesTruques(30), e, sort("Réchauffer un allié transi"), [e])  # improvisation mineure : Normale
    assert e.valeur("Survie") == 30 + 10
    e.consommer_effets_du_jet()
    assert e.valeur("Survie") == 30


def test_brasier_persistant_et_ses_sauvegardes():
    e, b = elara(), brigand()
    c = combat(e, b, des=(20, 2, 2, 2, 80, 2, 10))
    lancer(c.des, e, sort("Brasier"), [b], c)  # 20 ≤ 30 : réussite, 3d6 = 6
    assert b.fiche.pv == 14 and b.effets[0].persistant
    c.fin_de_tour()  # au tour du brigand : Constitution 80, raté → 1d3 = 2
    assert b.fiche.pv == 12 and c.sauvegardes[-1].degats == 2 and not c.sauvegardes[-1].fini
    c.fin_de_tour(), c.fin_de_tour()  # fin du round, Elara, puis le brigand : Constitution 10, réussie
    assert c.sauvegardes[-1].fini and b.effets == [] and b.fiche.pv == 12


def test_une_brulure_qui_assomme_saute_le_tour():
    e, b = elara(), brigand(pv=13)
    c = combat(e, b, des=(20, 2, 2, 2, 80, 2))
    lancer(c.des, e, sort("Brasier"), [b], c)  # 6 dégâts, moins de la moitié de ses PV : pas de blessure grave
    b.fiche.pv = 2
    c.fin_de_tour()  # la brûlure l'achève à 0 : il ne joue pas, le tour revient à Elara
    assert b.fiche.etat is Etat.MOURANT and c.au_tour_de is e and c.round == 2


def test_le_soin_magique_a_sa_propre_limite():
    e = elara(pv=10)
    lancer(DesTruques(30, 4), e, sort("Refermer les plaies"), [e], moment=MATIN)
    assert e.fiche.pv == 14
    with pytest.raises(SortImpossible, match="déjà reçu un soin magique"):
        lancer(DesTruques(30), e, sort("Apaiser"), [e], moment=MATIN)
    # La Médecine, elle, est encore possible : les deux limites se cumulent
    soins.soigner(DesTruques(30, 2), e.fiche, e.fiche, MATIN)
    with pytest.raises(SortImpossible, match="la nuit"):
        lancer(DesTruques(30), e, sort("Apaiser"), [e], moment=NUIT)


def test_apres_un_soin_rate_un_autre_lanceur_peut_tenter():
    e = elara(pv=10)
    soigneuse = Combattant(FichePnj("Sœur Agnès", combat=20, pv_max_base=10, competences={"Magie": 60}, pm=10),
                           "allies")
    lancer(DesTruques(80), e, sort("Apaiser"), [e], moment=MATIN)
    with pytest.raises(SortImpossible, match="un autre lanceur"):
        lancer(DesTruques(30), e, sort("Apaiser"), [e], moment=MATIN)
    r = lancer(DesTruques(50, 2), soigneuse, sort("Apaiser"), [e], moment=MATIN)  # 50 ≤ 80 − 10 : réussite
    assert r.cibles[0].gain == 2 and soigneuse.fiche.pm == 9


def test_un_soin_critique_rend_le_maximum():
    e = elara(pv=5)
    r = lancer(DesTruques(5), e, sort("Grâce de vie"), [e], moment=APRES_MIDI)  # 5 ≤ 30 / 5 : critique
    assert r.test.degre is Degre.CRITIQUE and r.cibles[0].gain == 12


def test_en_horreur_un_sort_coute_aussi_de_la_sante_mentale():
    e = elara()
    r = lancer(DesTruques(30), e, sort("Allumer ou souffler une flamme"), [], moment=MATIN, coute_sm=True)
    assert r.sm_perdue == 1 and e.fiche.sm == 69


def test_les_pm_reviennent_au_repos():
    perso = elara(pm=2).fiche
    rapport = soins.reposer(perso, soins.Repos.MOYEN, MATIN)
    assert rapport.pm_gagnes == 7 and perso.pm == 9


# --- L'outil du MJ ------------------------------------------------------------------------------

def session_fantasy(*des: int) -> Session:
    perso = FANTASY.creer_personnage("Mage", **FICHE_ELARA)
    return Session(FANTASY, perso, DesTruques(*des), arme="Dague", armure="Cuir")


def test_lancer_sort_n_existe_qu_avec_la_magie():
    noms = {s["function"]["name"] for s in session_fantasy().schemas()}
    assert "lancer_sort" in noms
    enum = next(s for s in session_fantasy().schemas()
                if s["function"]["name"] == "lancer_sort")["function"]["parameters"]["properties"]["sort"]["enum"]
    assert "Trait de feu" in enum and "Brasier" in enum and "Lance de glace" not in enum  # pas son domaine


def test_un_sort_inconnu_est_refuse():
    s = session_fantasy()
    r = s.appeler("lancer_sort", {"lanceur": "joueur", "sort": "Lance de glace", "cible": "joueur"})
    assert "erreur" in r


def test_l_outil_lance_un_sort_en_combat():
    s = session_fantasy(30, 3, 4)
    s.appeler("creer_pnj", {"identifiant": "brigand", "nom": "Brigand", "camp": "ennemis", "combat": 45, "pv": 20,
                            "dexterite": 40})
    s.appeler("debut_combat", {"pnj": ["brigand"]})
    r = s.appeler("lancer_sort", {"lanceur": "joueur", "sort": "Trait de feu", "cible": "brigand"})
    assert r["test"]["reussi"] and r["pm_restants"] == 11
    assert r["cibles"] == [{"qui": "Brigand", "degats_bruts": 7, "armure": 0, "degats": 7, "pv": 13,
                            "blessure_grave": False, "etat": "actif"}]
    assert "✨ Elara lance Trait de feu" in decrire("lancer_sort", {}, r, s)[0]
    assert "11/14 PM" not in _fiche(s) and "11 PM" in _fiche(s)


def test_une_improvisation_utilitaire_se_raconte():
    s = session_fantasy(30)
    r = s.appeler("lancer_sort", {"lanceur": "joueur", "sort": "Allumer ou souffler une flamme"})
    assert r["pm_depenses"] == 1 and "petit effet" in r["consigne"]


def test_un_pnj_lanceur_de_sorts():
    s = session_fantasy(50, 2)  # 50 ≤ 80 − 10 : réussite
    s.personnage.pv = 10
    r = s.appeler("creer_pnj", {"identifiant": "agnes", "nom": "Sœur Agnès", "camp": "allies", "combat": 20,
                                "pv": 10, "magie": 60, "pm": 10, "sorts": ["Apaiser"]})
    assert r["pm"] == 10
    r = s.appeler("lancer_sort", {"lanceur": "agnes", "sort": "Apaiser", "cible": "joueur"})
    assert r["cibles"] == [{"qui": "Elara", "pv_gagnes": 2}]
    assert "erreur" in s.appeler("creer_pnj", {"identifiant": "mage", "nom": "Mage", "camp": "ennemis", "combat": 30,
                                               "pv": 10, "sorts": ["Étincelle"]})  # sans pourcentage de Magie


def test_les_effets_s_oublient_avec_le_temps():
    s = session_fantasy(30)
    s.appeler("lancer_sort", {"lanceur": "joueur", "sort": "Bénédiction", "cible": "joueur"})
    assert s.appeler("etat")["joueur"]["effets_magiques"] == ["Bénédiction (+20 à ses jets)"]
    s.appeler("avancer_temps")
    assert s.joueur.effets == []


def test_le_repos_rend_des_pm():
    s = session_fantasy()
    s.personnage.pm = 0
    assert s.appeler("repos", {"type": "moyen"})["pm"] == 7
