"""L'économie, lot 3 (REGLES.md 13.3, 13.6, 13.7 et 13.10) : acheter, vendre, payer, marchander, commander."""

import pytest

from aria import commerce, outils
from aria.commerce import MARCHE_NOIR, OCCASION, CommerceImpossible, Marchandage, article, marchander, stock
from aria.des import Des, DesTruques
from aria.inventaire import ARME, GARNISSEUR, OUTIL, PORTAGE
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from test_inventaire import session
from tests.test_univers import CYBERPUNK


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def riche(u, argent=10000, des=None, **options):
    s, i = session(u, des=des, **options)
    s.personnage.argent = argent
    return s, i


def test_les_articles(u):
    assert article(u, "Katana").prix == 200 and article(u, "Gilet tactique lourd").prix == 500
    boite = article(u, "Boîte de cartouches (Pistolet lourd)")
    assert (boite.famille, boite.prix, boite.arme) == ("munitions", 20, "Pistolet lourd")
    assert article(u, "Boîte de cartouches (Fusil d'assaut)").prix == 50
    assert article(u, "Chargeur (Pistolet lourd)").prix == 50 and article(u, GARNISSEUR).prix == 100
    for nom in ("Sabre laser", "Boîte de cartouches (Katana)", "Chargeur (Sabre laser)"):
        with pytest.raises(CommerceImpossible):
            article(u, nom)


def test_le_nom_d_un_objet_est_verifie_par_le_moteur_pas_par_une_liste(u):
    s, i = riche(u, 1000)
    for outil in ("acheter", "commander"):
        schema = next(o for o in s.schemas() if o["function"]["name"] == outil)["function"]["parameters"]
        assert "enum" not in schema["properties"]["objet"]  # la liste de tout l'univers n'est plus dans le schéma
    r = s.appeler("acheter", {"objet": "katana"})  # un écart de casse est pardonné
    assert r["achete"] and r["objet"] == "Katana" and i.a("Katana", ARME)
    r = s.appeler("acheter", {"objet": "Katanna"})  # une faute : refusé, avec les noms proches
    assert "n'existe pas dans cet univers" in r["erreur"] and "Katana" in r["erreur"] and s.personnage.argent == 800
    r = s.appeler("acheter", {"objet": "Sabre laser"})  # rien de proche : le moteur ne laisse pas deviner
    assert "n'existe pas dans cet univers" in r["erreur"] and s.personnage.argent == 800
    r = s.appeler("commander", {"objet": "Sabre laser", "lieu": "grande ville"})
    assert "n'existe pas dans cet univers" in r["erreur"]
    # Les boîtes et les chargeurs ne valent que pour les armes qu'il possède
    assert s.appeler("acheter", {"objet": "Boîte de cartouches (Katana)"}).get("erreur")


def test_acheter_du_materiel_courant(u):
    s, i = riche(u, 1000)
    r = s.appeler("acheter", {"objet": "Katana"})
    assert r["achete"] and r["prix"] == 200 and r["argent"] == 800 and i.a("Katana", ARME)
    assert s.appeler("acheter", {"objet": "Boîte de cartouches (Pistolet lourd)"})["argent"] == 780
    assert sum(i.vrac.values()) == 40
    assert s.appeler("acheter", {"objet": "Chargeur (Pistolet lourd)"})["argent"] == 730
    assert [c["cartouches"] for c in i.chargeurs] == [8, 0]  # un chargeur se vend vide
    s.appeler("acheter", {"objet": "Gilet tactique moyen"})
    s.appeler("acheter", {"objet": GARNISSEUR})
    assert i.a("Gilet tactique moyen", PORTAGE) and i.a(GARNISSEUR, OUTIL) and s.personnage.argent == 430
    assert "Pas assez d'argent" in s.appeler("acheter", {"objet": "Pistolet lourd"})["erreur"]
    assert s.personnage.argent == 430  # rien n'est débité quand l'achat échoue


def test_le_restreint_et_le_militaire_ne_sont_pas_en_boutique(u):
    s, i = riche(u)
    assert "restreint" in s.appeler("acheter", {"objet": "Fusil d'assaut"})["erreur"]
    assert "militaire" in s.appeler("acheter", {"objet": "Lance-roquettes"})["erreur"]
    assert "militaire" in s.appeler("commander", {"objet": "Lance-roquettes", "lieu": "grande ville"})["erreur"]
    assert s.personnage.argent == 10000 and not i.a("Fusil d'assaut")
    assert "erreur" in s.appeler("acheter", {"objet": "Sabre laser"})  # hors de la liste fermée


def test_le_stock_d_un_vendeur_est_tire_et_dure_une_semaine(u):
    occasions = stock(u, "armurier_okabe", 3)
    assert len(occasions) == 3 and stock(u, "armurier_okabe", 7) == occasions  # la même semaine
    assert stock(u, "armurier_okabe", 8) != occasions and stock(u, "autre_boutique", 3) != occasions
    assert all(ligne["etat"] in (OCCASION, "marque") for ligne in occasions)
    noir = stock(u, "contact_ryo", 3, marche_noir=True)
    assert len(noir) == 4 and all(ligne["etat"] == MARCHE_NOIR for ligne in noir)
    s, i = riche(u, 50000)
    vu = s.appeler("voir_boutique", {"vendeur": "contact_ryo", "marche_noir": True})
    assert vu["stock"] == noir and "commande" in vu["rappel"]
    choisi = noir[0]
    assert "pas dans le stock" in s.appeler("acheter", {"objet": choisi["objet"], "etat": MARCHE_NOIR,
                                                         "vendeur": "un_autre"})["erreur"] \
        or stock(u, "un_autre", 1, True)[0]["objet"] == choisi["objet"]
    r = s.appeler("acheter", {"objet": choisi["objet"], "etat": MARCHE_NOIR, "vendeur": "contact_ryo"})
    assert r["achete"] and r["prix"] == choisi["prix"] and r["prix"] == commerce.decaler(article(u, choisi["objet"]).prix, 1)
    occasion = next((ligne for ligne in occasions if ligne["etat"] == OCCASION), None)
    if occasion:
        r = s.appeler("acheter", {"objet": occasion["objet"], "etat": OCCASION, "vendeur": "armurier_okabe"})
        assert r["prix"] == commerce.decaler(article(u, occasion["objet"]).prix, -1)
        assert i.trouver(occasion["objet"])["qualite"] == "usé"


def test_vendre_a_un_receleur(u):
    s, i = riche(u, 0)
    i.ajouter("Katana", ARME)  # vaut 200 : deux paliers en dessous, 50
    assert s.appeler("vendre", {"objet": "Katana"}) | {"monnaie": ""} == {
        "objet": "Katana", "vendu": True, "prix": 50, "argent": 50, "monnaie": ""}
    i.ajouter("Katana", ARME, qualite="usé")  # usé : 100, donc 20
    assert s.appeler("vendre", {"objet": "Katana"})["prix"] == 20
    assert "pas de valeur marchande" in s.appeler("vendre", {"objet": i.noms("objet")[0]})["erreur"]
    assert "sur son dos" in s.appeler("vendre", {"objet": "Gilet balistique"})["erreur"]
    i.ajouter("Lance-roquettes", ARME)
    assert "contact" in s.appeler("vendre", {"objet": "Lance-roquettes"})["erreur"]
    assert s.appeler("vendre", {"objet": "Lance-roquettes", "par_un_contact": True})["prix"] == 5000
    # vendre l'arme qu'on a en main la retire de la main
    assert s.joueur.arme.nom == "Pistolet lourd"
    s.appeler("vendre", {"objet": "Pistolet lourd"})
    assert s.joueur.arme is None and not i.a("Pistolet lourd")


@pytest.mark.parametrize("jet, achete, prix, geste", [
    (1, True, 500, True),  # critique : un palier en dessous, et le geste
    (30, True, 1000, True),  # réussite : le geste du vendeur, une boîte offerte
    (90, True, 1000, False),  # échec : le prix affiché
    (100, False, 0, False),  # maladresse : il refuse de vendre
])
def test_marchander_un_achat(u, jet, achete, prix, geste):
    s, i = riche(u, 5000, des=DesTruques(jet))
    s.personnage.competences["Persuasion"] = 50
    i.retirer("Pistolet lourd")
    r = s.appeler("acheter", {"objet": "Revolver lourd", "marchander": "persuasion", "attitude": "neutre"})
    assert r["achete"] is achete and r.get("prix", 0) == prix and ("geste" in r) is geste
    assert s.personnage.argent == 5000 - prix and "attitude" not in r
    if geste:
        assert sum(i.vrac.values()) == 40  # la boîte de départ, et celle qu'il offre


def test_marchander_une_revente_et_par_la_menace(u):
    s, i = riche(u, 0, des=DesTruques(30, 45))
    s.personnage.competences |= {"Persuasion": 50, "Intimidation": 50}
    i.ajouter("Katana", ARME)
    assert s.appeler("vendre", {"objet": "Katana", "marchander": "persuasion"})["prix"] == 100  # un palier de mieux
    i.ajouter("Katana", ARME)
    r = s.appeler("vendre", {"objet": "Katana", "marchander": "menace", "attitude": "hostile"})
    assert r["prix"] == 50 and "lui en veut" in r["attitude"]  # hostile : difficile, le test échoue
    m = marchander(Des(1), 50, "amical")
    assert isinstance(m, Marchandage) and not m.attitude_baisse


def test_payer_un_service(u):
    s, _ = riche(u, 1000)
    assert s.appeler("payer", {"service": "un trajet en taxi"})["argent"] == 980
    assert s.appeler("payer", {"service": "soigner une blessure grave"})["argent"] == 480
    assert "palier" in s.appeler("payer", {"service": "un pot-de-vin"})["erreur"]
    assert "erreur" in s.appeler("payer", {"service": "un pot-de-vin", "palier": 300})  # pas un palier permis
    assert s.appeler("payer", {"service": "un pot-de-vin", "palier": 200})["argent"] == 280
    assert "Pas assez d'argent" in s.appeler("payer", {"service": "une information", "palier": 500})["erreur"]
    assert s.personnage.argent == 280


def test_se_detendre_une_fois_par_semaine(u):
    s, _ = riche(u, 1000, des=DesTruques(4))
    s.personnage.sm -= 10
    avant = s.personnage.sm
    r = s.appeler("payer", {"service": "une soirée de détente"})
    assert r["sm_gagnee"] == 4 and s.personnage.sm == avant + 4 and r["argent"] == 800
    assert "déjà détendu" in s.appeler("payer", {"service": "une soirée de détente"})["erreur"]
    s.moment = Moment(8, Periode.APRES_MIDI)
    s.des = DesTruques(6)
    assert s.appeler("payer", {"service": "une soirée de détente"})["argent"] == 600


def test_commander_un_objet_restreint(u):
    s, i = riche(u, 10000, des=DesTruques(30, 2))  # le test réussit ; délai : 2 jours
    s.personnage.competences["Persuasion"] = 60
    r = s.appeler("commander", {"objet": "Fusil d'assaut", "lieu": "grande ville"})
    assert r["commande"] and r["prix"] == 5000 and r["arrive"] == "jour 3" and s.personnage.argent == 5000
    assert not i.a("Fusil d'assaut") and s.personnage.commandes == [{"objet": "Fusil d'assaut", "prix": 5000, "jour": 3}]
    s.moment = Moment(2, Periode.NUIT)
    arrive = outils.avancer_temps(s)
    assert arrive["commandes_arrivees"] == ["Fusil d'assaut"] and i.a("Fusil d'assaut") and not s.personnage.commandes
    assert s.joueur.munitions[u.arme("Fusil d'assaut")] == 30  # livré chargé
    assert "vente libre" in s.appeler("commander", {"objet": "Katana", "lieu": "grande ville"})["erreur"]
    assert "il faut une ville" in s.appeler("commander", {"objet": "Fusil d'assaut", "lieu": "village ou nature"})["erreur"]
    s.des = DesTruques(95)
    rate = s.appeler("commander", {"objet": "Fusil d'assaut", "lieu": "petite ville"})
    assert not rate["commande"] and s.personnage.argent == 5000  # rien n'est payé si le contact ne trouve pas


def test_la_pose_d_un_implant_se_paie(u):
    s, _ = riche(u, 3000, des=DesTruques(20))
    outils.creer_pnj(s, "doc", "neutres", 30, 10, nom="Doc Mori", competences={"Médecine": 70})
    r = s.appeler("poser_implant", {"implant": "Neuroport", "charcudoc": "doc"})
    assert r["pose"] and r["prix"] == 2000 + 500 and s.personnage.argent == 500
    assert "Pas assez d'argent" in s.appeler("poser_implant", {"implant": "Paume d'interface", "charcudoc": "doc", "cote": "droit"})["erreur"]
    assert "militaire" in s.appeler("poser_implant", {"implant": "Sandevistan", "charcudoc": "doc"})["erreur"]
    s.des = DesTruques(20)
    offert = s.appeler("poser_implant", {"implant": "Paume d'interface", "charcudoc": "doc", "cote": "droit", "offert": True})
    assert "prix" not in offert and s.personnage.argent == 500


def test_changer_de_niveau_de_vie_par_l_outil(u):
    s, _ = riche(u, 2000)
    r = s.appeler("niveau_de_vie", {"niveau": "confortable"})
    assert r["niveau_de_vie"] == "confortable" and r["visage"].startswith("un appartement") and r["argent"] == 2000
    s.personnage.semaine_payee = False
    assert s.appeler("niveau_de_vie", {"niveau": "modeste", "payer_maintenant": True})["argent"] == 1650
    assert s.appeler("niveau_de_vie", {"niveau": "à la rue"})["niveau_de_vie"] == "à la rue"


def test_sans_inventaire_pas_d_outils_d_argent(u):
    s, _ = session(u)
    s.personnage.inventaire = None
    from aria.outils import Session
    ancienne = Session(u, s.personnage, Des(1))
    noms = {x["function"]["name"] for x in ancienne.schemas()}
    assert not noms & {"acheter", "vendre", "payer", "commander", "voir_boutique", "niveau_de_vie", "inventaire"}
    assert {"acheter", "vendre", "payer", "commander", "voir_boutique", "niveau_de_vie"} <= {
        x["function"]["name"] for x in session(u)[0].schemas()}
