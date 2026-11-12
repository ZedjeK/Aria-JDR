"""Les événements du monde (REGLES.md 14.7), et ce que le maître d'un quartier change (14.5 et 14.6)."""

import pytest

from aria import economie, monde
from aria.des import Des
from aria.inventaire import ARME
from aria.monde import AMI, DEFENSE, HOSTILE, MEMBRE, MONDE, QUARTIER, RECHERCHE, VILLE
from aria.univers import charger_univers
from test_commerce import riche
from tests.test_monde import Imposes, attaque, petit
from tests.test_univers import CYBERPUNK

# Les numéros (à partir de 1) de quelques événements de quartier du Cyberpunk
MARCHE_DE_NUIT, REGLEMENT_DE_COMPTES, PLUIE_ACIDE, PILLARDS, GUETTEURS, ARMURERIE_BRAQUEE = 3, 4, 5, 10, 20, 31


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def tombe(etat, numero, jour=1, echelle=QUARTIER):
    """Fait tomber cet événement (le matin), là où est le joueur."""
    restants = [i for i in range(len(monde.table(etat["genre"], echelle))) if i not in etat["vus"].get(echelle, [])]
    return monde.tirer_evenement(etat, Imposes(1, restants.index(numero - 1) + 1), echelle, jour)


def test_les_tables_sont_jouables():
    assert monde.verifier_tables() == []
    for genre in ("Cyberpunk", "Fantasy", "Horreur"):
        assert [len(monde.table(genre, e)) for e in (QUARTIER, VILLE, MONDE)] == [50, 25, 15]
    assert monde.table("Fantasy", QUARTIER) is monde.table("Horreur", QUARTIER)  # le jeu générique
    assert monde.table("Cyberpunk", QUARTIER) is not monde.table("Fantasy", QUARTIER)


def test_au_et_du():
    assert monde.a("le Canal noir") == "au Canal noir" and monde.a("les Docks") == "aux Docks"
    assert monde.de("les Chromés") == "des Chromés" and monde.de("le Syndicat") == "du Syndicat"
    assert monde.a("la Ruche") == "à la Ruche" and monde.de("l'Arcade") == "de l'Arcade"
    assert monde.contracter("De le pont à les quais") == "Du pont aux quais"


def test_le_delai_du_prochain_evenement():
    e = petit()
    assert monde.delai(e, Imposes(5), QUARTIER) == 5 and monde.delai(e, Imposes(20), VILLE) == 20
    assert monde.delai(e, Imposes(20, 20), MONDE) == 40
    e["districts"]["Sud"].append("C")  # le district du joueur n'a plus de majorité : la guerre y est ouverte
    e["quartiers"]["C"]["district"] = "Sud"
    assert monde.domine(e, "Sud") is None and monde.delai(e, Imposes(5), QUARTIER) == 3
    assert monde.delai(e, Imposes(1), QUARTIER) == 1


def test_un_evenement_de_prix_dure_puis_s_efface():
    e = petit()
    entree = tombe(e, MARCHE_DE_NUIT, jour=4)
    assert entree["texte"] == "Le matin, un marché de nuit s'installe à D : tout s'y vend moins cher."
    assert entree["lieu"] == "D" and e["vus"] == {QUARTIER: [MARCHE_DE_NUIT - 1]}
    assert monde.decalage(e, "armes") == -1 and monde.decalage(e, "soins") == -1  # « tout »
    e["ici"] = "A"
    assert monde.decalage(e, "armes") == 0  # ailleurs, rien
    e["ici"] = "D"
    tombe(e, ARMURERIE_BRAQUEE, jour=4)
    assert monde.decalage(e, "armes") == 0 and monde.decalage(e, "munitions") == -1  # +1 et −1 sur les armes
    e["evenements"] = {QUARTIER: 99, VILLE: 99, MONDE: 99}
    monde.vivre_les_evenements(e, Imposes(), 6)  # le marché de nuit (2 jours) est fini, pas le braquage (4 jours)
    assert [x["effet"] for x in e["en_cours"]] == [monde.PRIX_PLUS] and monde.decalage(e, "armes") == 1
    monde.vivre_les_evenements(e, Imposes(), 8)
    assert e["en_cours"] == []


def test_un_coup_porte_au_maitre_ne_lui_prend_jamais_le_quartier():
    e = petit()
    tombe(e, REGLEMENT_DE_COMPTES)
    assert e["quartiers"]["D"]["controle"] == 6 and e["en_cours"] == []
    assert "les hommes de Helix y laissent des plumes" in e["journal"][-1]["texte"]
    e["quartiers"]["D"]["controle"] = 1
    e["vus"] = {}
    tombe(e, REGLEMENT_DE_COMPTES)
    assert e["quartiers"]["D"]["controle"] == 1 and e["quartiers"]["D"]["maitre"] == "Helix"


def test_un_evenement_de_ville_touche_tout_un_district():
    e = petit()
    monde.tirer_evenement(e, Imposes(1, 1, 3), VILLE, 2)  # le Nord, le matin, la guerre des gangs
    assert [e["quartiers"][q]["controle"] for q in "ABCD"] == [5, 2, 7, 7]
    monde.tirer_evenement(e, Imposes(2, 1, 1), VILLE, 2)  # le Sud : grève des transports
    assert monde.raison(e, monde.BARRAGE) and monde.barrage(e).startswith("Grève des transports dans Sud")
    e["ici"] = "A"
    assert monde.barrage(e) is None
    monde.tirer_evenement(e, Imposes(1, 1), MONDE, 2)  # le krach : partout
    assert monde.decalage(e, "armures") == 1


def test_un_evenement_ne_revient_pas_avant_la_fin_de_la_table():
    e, des = petit(), Des(3)
    for jour in range(50):
        monde.tirer_evenement(e, des, QUARTIER, jour)
    assert sorted(e["vus"][QUARTIER]) == list(range(50))
    monde.tirer_evenement(e, des, QUARTIER, 51)
    assert len(e["vus"][QUARTIER]) == 1  # la table est reprise


def test_ils_te_cherchent():
    e = petit()
    e["reputation"]["Helix"] = RECHERCHE
    entree = monde.tirer_evenement(e, Imposes(1, 1), QUARTIER, 3)  # 1 sur 3 : ce sont ses hommes
    assert "Les hommes de Helix ont retrouvé sa trace" not in entree["texte"]  # la nouvelle commence par le moment
    assert "les hommes de Helix ont retrouvé sa trace : ils le cherchent à D" in entree["texte"]
    assert "embuscade" in monde.situation(e)["traque"] and e["vus"] == {}
    entree = monde.tirer_evenement(e, Imposes(1, 2, MARCHE_DE_NUIT), QUARTIER, 3)  # 2 sur 3 : un événement ordinaire
    assert "marché de nuit" in entree["texte"]


def test_le_monde_qui_vit_fait_tomber_les_evenements():
    e = petit()
    e["evenements"] = {QUARTIER: 3, VILLE: 99, MONDE: 99}
    assert monde.avancer(e, Imposes(), 2) == [] and e["journal"] == []
    monde.avancer(e, Imposes(1, PLUIE_ACIDE, 4), 3)  # il tombe le jour 3 ; le suivant, 4 jours plus tard
    assert "pluie acide sur D" in e["journal"][-1]["texte"] and e["evenements"][QUARTIER] == 7
    assert monde.commerce(e)["refus"].startswith("Pluie acide")
    d = Des(5)
    e = monde.creer(d, "Cyberpunk")
    for jour in range(2, 61):
        monde.avancer(e, d, jour)
    evenements = [x for x in e["journal"] if x["genre"] not in ("mêlée", "annonce")]
    assert len(evenements) > 15 and [x["jour"] for x in e["journal"]] == sorted(x["jour"] for x in e["journal"])
    assert all(x["fin"] > 60 for x in e["en_cours"])


def test_un_evenement_pese_sur_une_melee():
    e = attaque(petit())
    e["ici"] = "B"
    tombe(e, GUETTEURS)  # les hommes des Rats fortifient B
    m = monde.resoudre(e, Imposes(1, 1, 5, 4), "B")  # 5 contre 4 + 1 (domine) + 1 (guetteurs)
    assert m.bonus_defense == 2 and m.points == 1 and "guetteurs" in m.raisons[0] and m.raisons[0].startswith(DEFENSE)


# --- Ce que le quartier change au commerce --------------------------------------------------------------

def test_les_regles_du_commerce_selon_le_maitre():
    e = petit()
    assert monde.commerce(e) == {"refus": None, "sans_receleur": False, "neuf": 1, "services": 0, "amical": False}
    e["factions"]["Helix"]["type"] = monde.SYNDICAT
    e["reputation"]["Helix"] = AMI
    assert monde.commerce(e) == {"refus": None, "sans_receleur": False, "neuf": 0, "services": -1, "amical": True}
    e["factions"]["Helix"]["type"] = monde.AUTORITES
    e["reputation"]["Helix"] = HOSTILE
    regles = monde.commerce(e)
    assert regles["sans_receleur"] and "les vendeurs ne le servent pas" in regles["refus"]
    s = monde.situation(e)
    assert s["commerce"] == "pas de marché noir ni de receleur" and "un tribunal de Helix" in s["place_forte"]
    assert "n'entre pas" in s["place_forte"] and "Les barrages du district sont à Helix" in s["barrage"]


def test_acheter_chez_une_corporation_et_pendant_un_evenement(u):
    s, i = riche(u, 5000)
    s.monde = petit()  # D : une corporation
    assert s.appeler("acheter", {"objet": "Katana"})["prix"] == 500  # 200, un palier au-dessus
    tombe(s.monde, ARMURERIE_BRAQUEE)
    assert s.appeler("acheter", {"objet": "Tonfa"})["prix"] == 500  # 100, deux paliers au-dessus
    s.monde["ici"] = "A"  # chez un gang, sans événement : le prix ordinaire
    assert s.appeler("acheter", {"objet": "Couteau"})["prix"] == 50
    s.monde["ici"] = "D"
    tombe(s.monde, PLUIE_ACIDE)
    assert "Pluie acide" in s.appeler("acheter", {"objet": "Couteau"})["erreur"]
    assert "Pluie acide" in s.appeler("voir_boutique", {"vendeur": "sato"})["erreur"]
    assert s.personnage.argent == 5000 - 500 - 500 - 50


def test_les_vendeurs_d_une_faction_hostile_ne_servent_pas(u):
    s, i = riche(u, 1000)
    s.monde = petit()
    s.monde["reputation"]["Helix"] = HOSTILE
    i.ajouter("Katana", ARME)
    for outil, arguments in (("acheter", {"objet": "Couteau"}), ("vendre", {"objet": "Katana"}),
                             ("payer", {"service": "un trajet en taxi"})):
        assert "les vendeurs ne le servent pas" in s.appeler(outil, arguments)["erreur"]
    assert s.appeler("payer", {"service": "un pot-de-vin", "palier": 50})["argent"] == 950  # un pot-de-vin passe


def test_pas_de_receleur_chez_les_autorites_et_des_services_moins_chers_chez_un_syndicat(u):
    s, i = riche(u, 1000)
    s.monde = petit()
    s.monde["factions"]["Helix"]["type"] = monde.AUTORITES
    i.ajouter("Katana", ARME)
    assert "pas de receleur" in s.appeler("vendre", {"objet": "Katana"})["erreur"]
    assert "pas de marché noir" in s.appeler("voir_boutique", {"vendeur": "ombre", "marche_noir": True})["erreur"]
    assert s.appeler("vendre", {"objet": "Katana", "par_un_contact": True})["vendu"]
    s.monde["factions"]["Helix"]["type"] = monde.SYNDICAT
    assert s.appeler("payer", {"service": "un trajet en taxi"})["prix"] == 10
    assert s.appeler("payer", {"service": "soigner une blessure grave"})["prix"] == 200


def test_une_cache_videe_par_un_evenement(u):
    s, _ = riche(u, 0)
    s.monde = petit()
    assert s.appeler("fouiller", {"cible": "cache", "taille": "petite"})["argent_trouve"] > 0
    tombe(s.monde, PILLARDS)
    r = s.appeler("fouiller", {"cible": "cache", "taille": "petite"})
    assert r["vide"] and r["objets"] == [] and "pillards" in r["raison"]


def test_un_membre_est_loge_par_son_clan(u):
    s, _ = riche(u, 1000)
    p = s.personnage
    assert economie.cout_de_la_semaine(p) == 350 and economie.cout_de_la_semaine(p, loge=True) == 0
    p.niveau_de_vie = "confortable"
    assert economie.cout_de_la_semaine(p, loge=True) == 650
    p.niveau_de_vie = "modeste"
    s.monde = petit()
    assert not monde.loge(s.monde)
    s.monde["reputation"]["Helix"] = MEMBRE
    assert monde.loge(s.monde)
    echeance, = economie.passer_les_echeances(p, 8, monde.loge(s.monde))
    assert echeance.cout == 0 and p.argent == 1000 and p.semaine_payee


def test_le_journal_pour_le_joueur():
    e = petit()
    assert monde.journal(e) == ["Rien à signaler."]
    tombe(e, MARCHE_DE_NUIT, jour=2)
    lignes = monde.journal(e)
    assert lignes[0].startswith("Jour 2 — Le matin, un marché de nuit") and lignes[1] == "En ce moment à D :"
    assert monde.situation(e)["en_ce_moment"] == ["Un marché de nuit s'installe à D : tout s'y vend moins cher."]
