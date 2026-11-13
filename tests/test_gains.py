"""L'économie, lot 4 (REGLES.md 13.6 à 13.8) : les missions, le métier, les dettes, le lien à charge, le butin."""

import pytest

from aria import economie, gains, outils
from aria.campagne import Campagne
from aria.des import Des, DesTruques
from aria.economie import PALIERS, passer_les_echeances
from aria.gains import CACHES, fouiller_un_corps, fouiller_une_cache, menace
from aria.inventaire import ARME, ARMURE
from aria.personnage import Etat
from aria.temps import Moment, Periode
from aria.univers import charger_univers
from test_inventaire import combat, session
from tests.test_univers import CYBERPUNK


@pytest.fixture(scope="module")
def u():
    return charger_univers(CYBERPUNK)


def partie(u, argent=1000, des=None, **options):
    s, i = session(u, des=des, **options)
    s.personnage.argent = argent
    return s, i


# --- Les missions ---------------------------------------------------------------------------------------

def test_une_mission_est_payee_a_la_cloture(u):
    s, _ = partie(u)
    r = s.appeler("ouvrir_mission", {"identifiant": "extraction", "fil": "Sortir Tanaka de sa tour.", "danger": "risquée"})
    assert r["recompense"] == 2000 and r["avance"] == 0 and s.memoire.fils["extraction"].ouvert
    assert outils.etat(s)["joueur"]["missions"] == {"extraction": 2000}
    assert "reussie" in s.appeler("clore_fil", {"identifiant": "extraction", "issue": "Tanaka est sorti."})["erreur"]
    assert s.memoire.fils["extraction"].ouvert and s.personnage.argent == 1000  # rien n'est clos ni versé
    r = s.appeler("clore_fil", {"identifiant": "extraction", "issue": "Tanaka est sorti.", "reussie": True})
    assert r["recompense_versee"] == 2000 and s.personnage.argent == 3000 and not s.personnage.missions
    # une mission ratée ne paie pas ; un fil ordinaire se clôt comme avant
    s.appeler("ouvrir_mission", {"identifiant": "livraison", "fil": "Livrer un colis.", "danger": "simple"})
    assert s.appeler("clore_fil", {"identifiant": "livraison", "issue": "Le colis est perdu.", "reussie": False})[
        "recompense_versee"] == 0
    s.appeler("ouvrir_fil", {"identifiant": "dette_mori", "fil": "Une dette envers Mori."})
    assert "mission_reussie" not in s.appeler("clore_fil", {"identifiant": "dette_mori", "issue": "Réglée."})
    assert s.personnage.argent == 3000
    assert "erreur" in s.appeler("ouvrir_mission", {"identifiant": "x", "fil": "y", "danger": "suicidaire"})


@pytest.mark.parametrize("jet, recompense, avance", [(1, 5000, 0), (30, 2000, 500), (90, 2000, 0), (100, 1000, 0)])
def test_marchander_une_mission(u, jet, recompense, avance):
    s, _ = partie(u, 0, des=DesTruques(jet))
    s.personnage.competences["Persuasion"] = 50
    r = s.appeler("ouvrir_mission", {"identifiant": "m", "fil": "Une escorte.", "danger": "risquée",
                                     "marchander": "persuasion"})
    assert (r["recompense"], r["avance"]) == (recompense, avance) and s.personnage.argent == avance
    verse = s.appeler("clore_fil", {"identifiant": "m", "issue": "Faite.", "reussie": True})["recompense_versee"]
    assert verse == recompense - avance and s.personnage.argent == recompense  # l'avance est déduite à la fin


# --- Exercer son métier ---------------------------------------------------------------------------------

@pytest.mark.parametrize("jet, revenu, ennui", [(1, 1400, False), (20, 1050, False), (45, 700, False), (95, 0, False), (100, 0, True)])
def test_une_semaine_de_travail(u, jet, revenu, ennui):
    s, _ = partie(u, 1000, des=DesTruques(jet))
    p = s.personnage
    p.competences[u.parcours["Solo"][0]] = 60
    p.pv = 3
    r = s.appeler("semaine_de_travail", {})
    assert r["revenu"] == revenu and ("ennui" in r) is ennui
    assert s.moment.jour == 8 and r["echeances"][0]["cout"] == 350  # la semaine passe : le loyer tombe
    assert p.argent == 1000 + revenu - 350 and p.pv == p.pv_max and p.echeance == 15


def test_un_precaire_paie_tout_juste_sa_semaine(u):
    s, _ = partie(u, 0, des=DesTruques(45), parcours="Ganger", arme="Pistolet léger", armure="Veste renforcée")
    s.personnage.competences[u.parcours["Ganger"][0]] = 60
    r = s.appeler("semaine_de_travail", {})
    assert r["revenu"] == 350 and s.personnage.argent == 0 and not economie.a_la_rue(s.personnage)


# --- Les dettes et le lien à charge ---------------------------------------------------------------------

def test_emprunter_et_rembourser(u):
    s, _ = partie(u, 0)
    r = s.appeler("emprunter", {"creancier": "usurier_tanaka", "somme": 2000})
    assert r["echeance_par_semaine"] == 200 and r["total_a_rembourser"] == 2400 and s.personnage.argent == 2000
    assert "erreur" in s.appeler("emprunter", {"creancier": "usurier_tanaka", "somme": 300})  # pas un palier
    assert "déjà trop" in s.appeler("emprunter", {"creancier": "autre", "somme": 5000})["erreur"]
    (e,) = passer_les_echeances(s.personnage, 8)  # la dette d'abord (200), puis le loyer (350)
    assert e.dettes_payees == [("usurier_tanaka", 200, 2200)] and e.payee and s.personnage.argent == 1450
    assert outils.etat(s)["joueur"]["dettes"] == [{"creancier": "usurier_tanaka", "reste_du": 2200, "par_semaine": 200}]
    s.personnage.argent = 100  # plus de quoi payer : l'échéance est manquée, et le loyer aussi
    s.moment = Moment(14, Periode.NUIT)
    ligne = outils.avancer_temps(s)["echeances"][0]
    assert ligne["dettes_manquees"][0]["echeances_manquees"] == 1 and "menace" in ligne["dettes_manquees"][0]["consequence"]
    assert ligne["impayee"] and s.personnage.argent == 100 and s.personnage.dettes[0]["reste"] == 2200
    s.personnage.argent = 50000
    for jour in range(22, 22 + 7 * 11, 7):
        passer_les_echeances(s.personnage, jour)
    assert s.personnage.dettes == []  # onze échéances de plus : la dette est éteinte


def test_le_lien_a_charge(u):
    s, _ = partie(u, 1000, des=DesTruques(5, 2))
    p = s.personnage
    p.sm -= 10
    assert s.appeler("niveau_de_vie", {"niveau": "modeste", "lien_a_charge": True})["lien_a_charge"]
    gain = s.appeler("recuperer_sante_mentale", {"source": "discussion", "avec_son_lien": True})["sm_gagnee"]
    assert gain == 5  # 1d6 au lieu de 1d3
    (e,) = passer_les_echeances(p, 8)
    assert e.lien is True and p.argent == 1000 - 200 - 350
    p.argent = 100
    s.moment = Moment(14, Periode.NUIT)
    ligne = outils.avancer_temps(s)["echeances"][0]
    assert "impayé" in ligne["lien_a_charge"] and not p.charge_payee
    s.moment = Moment(16, Periode.APRES_MIDI)
    assert "ne le réconforte pas" in s.appeler("recuperer_sante_mentale",
                                                {"source": "discussion", "avec_son_lien": True})["erreur"]
    assert s.appeler("recuperer_sante_mentale", {"source": "discussion"})["sm_gagnee"] == 2  # avec quelqu'un d'autre : 1d3


# --- Le butin -------------------------------------------------------------------------------------------

def test_la_menace_d_un_pnj():
    assert [menace(c)[0] for c in (20, 40, 41, 60, 61, 75, 76, 95)] == [
        "faible", "faible", "moyenne", "moyenne", "forte", "forte", "élite", "élite"]


def test_fouiller_un_corps_donne_ce_qu_il_avait(u):
    arme, armure = u.arme("Pistolet léger"), u.armure("Veste renforcée")
    # 1d6 = 3 (argent : 3 × 20), 1d10 = 4 (usée), 1d6 = 6 (pas d'objet en plus : 2 chances sur 6 en menace moyenne)
    butin = fouiller_un_corps(DesTruques(3, 4, 6), u, 50, arme, armure, dans_l_arme=7, chargeurs=1)
    assert butin.argent == 60 and butin.menace == "moyenne"
    assert butin.objets == [
        {"nom": "Pistolet léger", "famille": ARME, "qualite": "usé", "charge": 7, "chargeurs": 1},
        {"nom": "Veste renforcée", "famille": ARMURE, "qualite": "usé"}]
    # un tueur d'élite, arme d'origine (1d10 = 9), un objet en plus (1d6 = 2 sur 4 chances), matériel marqué
    butin = fouiller_un_corps(DesTruques(6, 9, 2, 1), u, 85, u.arme("Fusil d'assaut"), None, marque=True, chargeurs=2)
    assert butin.argent == 600 and "qualite" not in butin.objets[0] and butin.objets[0]["marque"]
    assert len(butin.objets) == 2 and butin.objets[1]["nom"] in gains.table_du_genre(u)
    sans_arme = fouiller_un_corps(DesTruques(1, 6), u, 30, None, None)
    assert sans_arme.argent == 10 and sans_arme.objets == []


def test_les_caches(u):
    for taille, (mini, maxi) in CACHES.items():
        for graine in range(30):
            butin = fouiller_une_cache(Des(graine), u, taille)
            valeur = butin.argent + sum(economie.prix(u.arme(o["nom"]) if o["famille"] == ARME else u.armure(o["nom"]), u)
                                        for o in butin.objets)
            assert mini <= valeur <= maxi and valeur in PALIERS and butin.argent > 0, (taille, graine)
            assert all(economie.disponibilite(u.arme(o["nom"]), u) != "militaire" for o in butin.objets if o["famille"] == ARME)
    petites = [fouiller_une_cache(Des(g), u, "petite") for g in range(200)]
    valeurs = [b.argent + sum(economie.prix(u.arme(o["nom"]) if o["famille"] == ARME else u.armure(o["nom"]), u)
                              for o in b.objets) for b in petites]
    assert valeurs.count(500) < valeurs.count(50)  # deux tirages, on garde le plus bas : le maximum est rare


def test_fouiller_et_prendre_par_les_outils(u):
    s, i = partie(u, 0, des=Des(4))
    combat(s, combat_pnj=50)
    ganger = s.pnj["ganger"]
    assert "debout" in s.appeler("fouiller", {"cible": "ganger"})["erreur"]
    ganger.fiche.etat, ganger.fiche.pv = Etat.MORT, 0
    ganger.munitions[ganger.arme] = 5
    # sous le feu : seulement son arme, pour une action mineure
    r = s.appeler("fouiller", {"cible": "ganger"})
    assert r["argent_trouve"] == 0 and len(r["objets"]) == 1 and "Pistolet léger" in r["objets"][0]
    assert "5 cartouches" in r["objets"][0] and "prendre" in {x["function"]["name"] for x in s.schemas()}
    pris = s.appeler("prendre", {"origine": "ganger", "objet": "Pistolet léger"})
    assert i.a("Pistolet léger", ARME) and "Pistolet léger" in str(pris["prets"] + pris["ranges"])
    assert s.joueur.munitions[u.arme("Pistolet léger")] == 5  # ramassé tel quel
    s.combat = None
    r = s.appeler("fouiller", {"cible": "ganger"})  # le combat fini, on fouille pour de bon
    assert r["argent_trouve"] > 0 and s.personnage.argent == r["argent_trouve"] and r["menace"] == "moyenne"
    assert "déjà été fouillé" in s.appeler("fouiller", {"cible": "ganger"})["erreur"]
    assert "erreur" in s.appeler("prendre", {"origine": "ganger", "objet": "Katana"})
    assert "Pistolet léger" not in [o["nom"] for o in s.trouvailles["ganger"]]  # son arme a déjà été ramassée


def test_une_cache_par_les_outils_et_un_objet_de_valeur(u):
    s, i = partie(u, 0, des=Des(2), force=80)
    assert "taille" in s.appeler("fouiller", {"cible": "cache"})["erreur"]
    r = s.appeler("fouiller", {"cible": "cache", "taille": "moyenne"})
    assert r["argent_trouve"] > 0 and r["origine"] == "cache_1" and s.personnage.argent == r["argent_trouve"]
    for nom in [o["nom"] for o in s.trouvailles["cache_1"]]:
        assert "erreur" not in s.appeler("prendre", {"origine": "cache_1", "objet": nom})
    assert s.trouvailles["cache_1"] == []
    gains.prendre(i, u, {"nom": gains.OBJET_DE_VALEUR, "famille": "objet", "valeur": 100})
    avant = s.personnage.argent
    assert s.appeler("vendre", {"objet": gains.OBJET_DE_VALEUR})["prix"] == 100 and s.personnage.argent == avant + 100


def test_tout_survit_a_la_sauvegarde(u, tmp_path):
    from aria.sauvegarde import personnage_depuis_dict, personnage_vers_dict
    s, _ = partie(u)
    s.appeler("emprunter", {"creancier": "tanaka", "somme": 1000})
    s.appeler("ouvrir_mission", {"identifiant": "m", "fil": "Une escorte.", "danger": "simple"})
    s.appeler("niveau_de_vie", {"niveau": "modeste", "lien_a_charge": True})
    relu = personnage_depuis_dict(personnage_vers_dict(s.personnage))
    assert relu.dettes == s.personnage.dettes and relu.missions == {"m": {"recompense": 500, "avance": 0, "danger": "simple"}}
    assert relu.lien_a_charge and relu.argent == 2000 and Campagne(tmp_path)
