"""Les lieux d'un quartier (REGLES.md 15.4) : tirés avec la carte, et le commerce passe par eux."""

import pytest

from aria import lieux, missions, monde, noms, pnj
from aria.des import Des, DesTruques
from aria.lieux import ARMES, IMPLANTS, MATERIEL, SOINS, LieuImpossible
from aria.monde import AMI
from aria.univers import charger_univers
from test_inventaire import session
from tests.test_monde import Imposes, petit
from tests.test_univers import CYBERPUNK


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def carte(*des, ici: str = "D") -> dict:
    """Le petit monde avec ses lieux. Sans dés imposés, tout sort sur 1 : chaque quartier a un bar, un club et
    un marché, plus une planque cachée ; le code ajoute ce qui manque à chaque district."""
    etat = petit()
    etat["ici"] = ici
    noms.installer(etat, "Cyberpunk", "Osaka")
    pnj.installer(etat, "Cyberpunk")
    lieux.installer(etat, Imposes(*des), "Cyberpunk")
    return etat


def partie(u, etat, argent=10000, des=None):
    s, i = session(u, des=des)
    s.monde, s.personnage.argent = etat, argent
    return s, i


def noms_des_lieux(etat, quartier, caches=False):
    return [l["nom"] for l in lieux.du_quartier(etat, quartier, caches)]


def test_la_bibliotheque_est_complete():
    assert lieux.verifier_tables() == []


def test_chaque_quartier_recoit_ses_lieux():
    etat = carte()
    assert noms_des_lieux(etat, "C") == ["bar Pluie d'or", "club Silicium", "marché Kabuki"]
    assert noms_des_lieux(etat, "C", caches=True)[-1] == "planque Dernière Dose"
    assert lieux.actifs(etat) and not lieux.actifs(petit()) and not lieux.actifs(None)
    assert etat["lieux"]["connus"] == ["D"]


def test_le_nombre_de_lieux_va_de_trois_a_cinq():
    etat = carte(3)  # le premier quartier tire 3 : cinq lieux
    assert len(noms_des_lieux(etat, "A")) >= 5 and len(noms_des_lieux(etat, "C")) == 3


def test_le_code_complete_le_minimum_de_chaque_district():
    etat = carte()
    assert "clinique Minuit Cobalt" in noms_des_lieux(etat, "A")  # le Nord n'avait ni soins…
    assert "armurerie Orchidée noire" in noms_des_lieux(etat, "B")  # … ni armurerie
    assert {"clinique Sept Lunes", "armurerie Cuivre et Verre"} <= set(noms_des_lieux(etat, "D"))
    for membres in etat["districts"].values():
        vendu = {b for q in membres for l in lieux.du_quartier(etat, q) for b in l["vend"]}
        assert set(lieux.MINIMUM_PAR_DISTRICT) <= vendu


def test_un_district_domine_a_son_quartier_general():
    etat = carte()
    qg = next(l for l in lieux.du_quartier(etat, "B") if l["type"] == lieux.QG)
    assert qg["nom"] == "quartier général de Rats" and qg["tenancier"]["nom"] == "Nour"
    assert (qg["tenancier"]["role"], qg["tenancier"]["menace"]) == ("chef", pnj.FORTE)
    assert not any(l["type"] == lieux.QG for l in lieux.du_quartier(etat, "A"))


def test_un_tenancier_a_un_nom_un_role_une_menace_et_deux_traits():
    etat = carte()
    t = lieux.du_quartier(etat, "A")[0]["tenancier"]
    assert t == {"nom": "Haruto Sato", "sexe": "homme", "role": "commerçant", "menace": "faible",
                 "caractere": "méfiant", "signe": "un œil cybernétique qui ne cligne pas"}
    tous = [l["tenancier"]["nom"] for q in etat["quartiers"] for l in lieux.du_quartier(etat, q, caches=True)]
    assert len(set(tous)) == len(tous)  # jamais deux fois le même nom


def test_la_menace_d_un_tenancier_reste_dans_les_bornes_de_son_role():
    assert lieux._menace(Imposes(6), "Cyberpunk", "commerçant") == pnj.FAIBLE  # un commerçant reste faible
    assert lieux._menace(Imposes(6), "Cyberpunk", "fixer") == pnj.FORTE
    assert lieux._menace(Imposes(4), "Cyberpunk", "technicien") == pnj.MOYENNE
    assert lieux._menace(Imposes(1), "Cyberpunk", "chef") == pnj.FORTE  # un chef est au moins fort


def test_une_megapole_entiere():
    des = Des(7)
    etat = monde.creer(des, "Cyberpunk")
    noms.installer(etat, "Cyberpunk", "Osaka")
    pnj.installer(etat, "Cyberpunk")
    lieux.installer(etat, des, "Cyberpunk")
    tous = [l for q in etat["quartiers"] for l in lieux.du_quartier(etat, q, caches=True)]
    assert all(len(lieux.du_quartier(etat, q)) >= 3 for q in etat["quartiers"])
    assert len({l["nom"] for l in tous}) == len(tous)  # plus de lieux que d'enseignes, et aucun nom en double
    assert all(l["cache"] != l["trouve"] for l in tous)
    for membres in etat["districts"].values():
        vendu = {b for q in membres for l in lieux.du_quartier(etat, q) for b in l["vend"]}
        assert set(lieux.MINIMUM_PAR_DISTRICT) <= vendu


def test_l_attitude_suit_la_reputation_chez_le_maitre_du_quartier():
    etat = carte()
    assert lieux.attitude(etat) == "neutre"
    etat["reputation"]["Helix"] = AMI
    assert lieux.attitude(etat) == "amical" and lieux.attitude(etat, "A") == "neutre"
    etat["reputation"]["Helix"] = monde.HOSTILE
    assert lieux.decrire(etat)[0]["attitude"] == "hostile"


def test_le_lieu_le_plus_proche():
    etat = carte(ici="C")
    assert lieux.exiger(etat, MATERIEL) == "marché Kabuki"
    assert lieux.plus_proche(etat, ARMES) == ("armurerie Orchidée noire", "B")
    assert lieux.plus_proche(etat, SOINS) == ("clinique Sept Lunes", "D")
    with pytest.raises(LieuImpossible, match="une armurerie. Le plus proche : armurerie Orchidée noire, à B"):
        lieux.exiger(etat, ARMES)
    assert lieux.exiger(etat, IMPLANTS) is None  # aucun poseur d'implants connu sur la carte : rien n'est exigé


def test_un_lieu_cache_ne_sert_que_trouve():
    etat = carte(ici="C")
    for l in lieux.du_quartier(etat, "C", caches=True):
        if l["cache"]:
            l["vend"] = [SOINS]
    assert lieux.plus_proche(etat, SOINS) == ("clinique Sept Lunes", "D")
    trouve = lieux.reveler(etat)
    assert trouve["nom"] == "planque Dernière Dose" and lieux.reveler(etat) is None
    assert lieux.exiger(etat, SOINS) == "planque Dernière Dose"


def test_la_carte_montre_les_lieux_connus():
    etat = carte()
    lignes = lieux.carte(etat)
    assert lignes[0] == "Les lieux que tu connais :" and len(lignes) == 2 and lignes[1].startswith("  D : bar Dragon pâle")
    lieux.visiter(etat, "A")
    lieux.visiter(etat, "A")
    assert len(lieux.carte(etat)) == 3 and etat["lieux"]["connus"] == ["D", "A"]


def test_une_offre_de_mission_designe_un_lieu():
    etat = carte()
    offre = missions.tirer_offre(etat, Imposes(), 1)
    assert offre["endroit"] in noms_des_lieux(etat, offre["lieu"])
    assert offre["texte"].endswith(f"Sur place : {offre['endroit']}.")
    assert "endroit" not in missions.tirer_offre(petit(), Imposes(), 1)


# --- Les outils du MJ -------------------------------------------------------------------------

def test_on_achete_une_arme_la_ou_on_en_vend(u):
    s, i = partie(u, carte(ici="C"))
    refus = s.appeler("acheter", {"objet": "Katana"})["erreur"]
    assert "une armurerie" in refus and "armurerie Orchidée noire" in refus and s.personnage.argent == 10000
    assert s.appeler("acheter", {"objet": "Gilet tactique moyen"})["achete"]  # du matériel : le marché du quartier
    s.monde["ici"] = "B"
    assert s.appeler("acheter", {"objet": "Katana"})["achete"]


def test_le_marche_noir_passe_par_un_contact_pas_par_un_lieu(u):
    s, _ = partie(u, carte(ici="C"))
    stock = s.appeler("voir_boutique", {"vendeur": "fixer_jin", "marche_noir": True})["stock"]
    if stock:
        r = s.appeler("acheter", {"objet": stock[0]["objet"], "etat": "marché noir", "vendeur": "fixer_jin"})
        assert "armurerie" not in r.get("erreur", "")


def test_on_se_fait_soigner_dans_une_clinique(u):
    s, _ = partie(u, carte(ici="C"))
    assert "un lieu où se faire soigner" in s.appeler("payer", {"service": "une consultation ou un soin"})["erreur"]
    assert s.appeler("payer", {"service": "un repas correct"})["prix"] > 0  # un service ordinaire reste libre
    s.monde["ici"] = "D"
    assert s.appeler("payer", {"service": "une consultation ou un soin"})["prix"] > 0


def test_une_campagne_sans_lieux_garde_son_commerce(u):
    s, _ = partie(u, petit())
    assert s.appeler("acheter", {"objet": "Katana"})["achete"]


def test_l_outil_monde_donne_les_lieux_et_les_fait_connaitre(u):
    s, _ = partie(u, carte(), des=Imposes())
    r = s.appeler("monde", {"ici": "A"})
    assert [l["lieu"] for l in r["lieux"]][:3] == ["bar Lotus blanc", "club Dernier Signal", "marché Zéro Absolu"]
    assert r["lieux"][0]["tenancier"] == "Haruto Sato" and r["lieux"][2]["on_y_trouve"] == ["materiel"]
    assert "n'en invente aucun" in r["consigne_lieux"] and "lieu_indique" not in r
    assert s.monde["lieux"]["connus"] == ["D", "A"]


def test_une_faction_amie_indique_le_lieu_cache(u):
    etat = carte()
    etat["reputation"]["Lames"] = AMI
    s, _ = partie(u, etat, des=Imposes())
    r = s.appeler("monde", {"ici": "A"})
    assert r["lieu_indique"] == "Lames lui indique un lieu caché du quartier : planque Écran mort."
    assert r["lieux"][-1]["lieu"] == "planque Écran mort" and r["lieux"][-1]["cache"]
    assert "lieu_indique" not in s.appeler("monde", {})


def test_une_enquete_reussie_revele_le_lieu_cache(u):
    s, _ = partie(u, carte(), des=DesTruques(1, 99, 1))
    nom = next(affiche for affiche, socle in s.noms_competences.items() if socle == "Investigation")
    r = s.appeler("test_competence", {"competence": nom, "difficulte": "normale"})
    assert r["reussi"] and "planque Vapeur" in r["lieu_trouve"]
    rate = s.appeler("test_competence", {"competence": nom, "difficulte": "normale"})
    assert not rate["reussi"] and "lieu_trouve" not in rate
    encore = s.appeler("test_competence", {"competence": nom, "difficulte": "normale"})
    assert encore["reussi"] and "lieu_trouve" not in encore  # il n'y en a qu'un par quartier


def test_creer_le_tenancier_d_un_lieu(u):
    s, _ = partie(u, carte(), des=Imposes())
    schema = next(o for o in s.schemas() if o["function"]["name"] == "creer_pnj")["function"]["parameters"]
    assert schema["properties"]["tenancier"]["enum"][0] == "bar Dragon pâle"
    assert schema["required"] == ["identifiant", "camp"]
    patron = lieux.lieu(s.monde, "bar Dragon pâle")["tenancier"]
    r = s.appeler("creer_pnj", {"identifiant": "patron", "camp": "neutres", "tenancier": "bar Dragon pâle"})
    assert (r["nom"], r["role"], r["menace"]) == (patron["nom"], "commerçant", "faible")
    assert (r["caractere"], r["signe"]) == (patron["caractere"], patron["signe"])
    assert "doit être l'une de ces valeurs" in s.appeler("creer_pnj", {"identifiant": "x", "camp": "neutres",
                                                   "tenancier": "bar Lotus blanc"})["erreur"]
    assert "role" in s.appeler("creer_pnj", {"identifiant": "y", "camp": "neutres", "sexe": "homme"})["erreur"]
