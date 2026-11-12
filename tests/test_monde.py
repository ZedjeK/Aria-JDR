"""Le monde qui vit (REGLES.md 14.3 à 14.6) : la carte, les mêlées, la réputation, et leurs outils."""

import pytest

import json

from aria import jeu, monde, outils
from aria.bibliotheque import charger
from aria.campagne import Campagne
from aria.compte_rendu import decrire_monde
from aria.generateur import choix_par_defaut
from aria.des import Des
from aria.monde import AMI, ATTAQUE, DEFENSE, HOSTILE, MEMBRE, NEUTRE, RECHERCHE, MondeImpossible
from aria.personnage import Etat
from aria.sauvegarde import Partie, partie_depuis_dict, partie_vers_dict
from test_table import ServeurScripte
from tests.test_outils import session


class Imposes(Des):
    """Les valeurs données d'abord (ramenées au nombre de faces), puis des 1."""

    def __init__(self, *valeurs: int):
        super().__init__(1)
        self.valeurs = list(valeurs)

    def lancer(self, faces: int) -> int:
        return min(self.valeurs.pop(0), faces) if self.valeurs else 1


def petit() -> dict:
    """Quatre quartiers en ligne : A (Lames) — B (Rats) — C (Rats) — D (Helix). Les Rats dominent le Nord."""
    def q(district, voisins, maitre, controle):
        return {"district": district, "voisins": voisins, "maitre": maitre, "controle": controle, "attaque": None,
                "attaquant": None}
    return {"districts": {"Nord": ["A", "B", "C"], "Sud": ["D"]},
            "quartiers": {"A": q("Nord", ["B"], "Lames", 6), "B": q("Nord", ["A", "C"], "Rats", 3),
                          "C": q("Nord", ["B", "D"], "Rats", 8), "D": q("Sud", ["C"], "Helix", 7)},
            "factions": {"Lames": {"type": "gang", "chef": "Rin", "rivale": "Rats"},
                         "Rats": {"type": "gang", "chef": "Nour", "rivale": "Lames"},
                         "Helix": {"type": "corporation", "chef": "Vera", "rivale": ""}},
            "reputation": {"Lames": NEUTRE, "Rats": NEUTRE, "Helix": NEUTRE}, "ici": "D", "journal": [], "lu": 0,
            "genre": "Cyberpunk", "en_cours": [], "vus": {},
            "evenements": {"quartier": 999, "ville": 999, "monde": 999}}  # pas d'événement, sauf si le test en veut


def attaque(etat, quartier="B", jour=1):
    etat["quartiers"][quartier] |= {"attaque": jour, "attaquant": monde.attaquants(etat, quartier)[0]}
    return etat


# --- La carte -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("genre, districts, quartiers, factions", [("Cyberpunk", 6, (18, 20), 8),
                                                                    ("Fantasy", 3, (8, 10), 5)])
def test_la_carte_a_la_taille_du_cadre(genre, districts, quartiers, factions):
    for graine in range(1, 6):
        e = monde.creer(Des(graine), genre)
        assert len(e["districts"]) == districts and quartiers[0] <= len(e["quartiers"]) <= quartiers[1]
        assert len(e["factions"]) == factions and set(e["reputation"].values()) == {NEUTRE}
        assert sum(f["type"] == monde.AUTORITES for f in e["factions"].values()) == 1
        assert all(f["rivale"] in e["factions"] and f["rivale"] != nom for nom, f in e["factions"].items())
        assert all(4 <= q["controle"] <= 8 and q["maitre"] in e["factions"] for q in e["quartiers"].values())
        assert e["ici"] in e["quartiers"]
        # La carte tient d'un seul bloc, et les voisins le sont dans les deux sens
        vus, a_voir = set(), [e["ici"]]
        while a_voir:
            q = a_voir.pop()
            if q not in vus:
                vus.add(q)
                a_voir += e["quartiers"][q]["voisins"]
        assert vus == set(e["quartiers"])
        assert all(a in e["quartiers"][b]["voisins"] for a, q in e["quartiers"].items() for b in q["voisins"])
        # Un quartier disputé a sa prochaine attaque, les autres non
        for nom, q in e["quartiers"].items():
            assert (q["attaque"] is not None) == monde.dispute(e, nom)


def test_un_bourg_tient_dans_un_district():
    e = monde.creer(Des(1), "Fantasy", "bourg")
    assert len(e["districts"]) == 1 and 3 <= len(e["quartiers"]) <= 4 and len(e["factions"]) == 3


def test_qui_est_hostile_a_qui():
    e = petit()
    e["factions"] |= {"Police": {"type": "autorités", "chef": "", "rivale": ""},
                      "Guilde": {"type": "syndicat ou guilde", "chef": "", "rivale": "Helix"}}
    assert monde.hostiles(e, "Lames", "Rats") and monde.hostiles(e, "Lames", "Police")
    assert not monde.hostiles(e, "Lames", "Helix") and not monde.hostiles(e, "Helix", "Police")
    assert monde.hostiles(e, "Helix", "Guilde") and not monde.hostiles(e, "Rats", "Rats")
    assert monde.attaquants(e, "B") == ["Lames"] and not monde.dispute(e, "C") and not monde.dispute(e, "D")
    assert monde.domine(e, "Nord") == "Rats" and monde.domine(e, "Sud") == "Helix"
    e["districts"]["Nord"].append("D")
    assert monde.domine(e, "Nord") is None  # deux sur quatre : pas de majorité, la guerre est ouverte


def test_planifier():
    e = petit()
    monde.planifier(e, Imposes(2, 1, 3, 1), 1)
    q = e["quartiers"]
    assert (q["A"]["attaque"], q["A"]["attaquant"], q["B"]["attaque"], q["B"]["attaquant"]) == (3, "Rats", 4, "Lames")
    assert q["C"]["attaque"] is None and q["D"]["attaque"] is None


# --- La mêlée -------------------------------------------------------------------------------------------

def test_l_attaquant_gagne_deux_points_sur_un_ecart_de_cinq():
    e = attaque(petit())
    m = monde.resoudre(e, Imposes(1, 1, 9, 3), "B")  # 9 contre 3 + 1 (les Rats dominent le district)
    assert (m.bonus_attaque, m.bonus_defense, m.points, m.pris, m.controle) == (0, 1, -2, False, 1)
    assert m.vainqueur == "Lames" and e["quartiers"]["B"]["maitre"] == "Rats"
    assert e["quartiers"]["B"]["attaque"] == 2  # la prochaine attaque est déjà tirée : 1d3 jours plus tard
    assert "avantage à Lames" in e["journal"][-1]["texte"]


def test_a_zero_le_quartier_change_de_mains():
    e = attaque(petit())
    e["quartiers"]["B"]["controle"] = 1
    m = monde.resoudre(e, Imposes(6, 1, 1, 6, 5), "B")  # un clan préparé (+2) : 6 + 2 contre 5 + 1
    assert m.pris and m.bonus_attaque == 2 and m.raisons == ["attaque : un repérage des lieux"]
    assert (e["quartiers"]["B"]["maitre"], e["quartiers"]["B"]["controle"]) == ("Lames", 5)
    assert monde.domine(e, "Nord") == "Lames" and "change de mains, victoire de Lames" in e["journal"][-1]["texte"]
    assert not monde.dispute(e, "A") and monde.dispute(e, "C")  # le front s'est déplacé


def test_le_defenseur_reprend_du_terrain_et_l_egalite_ne_change_rien():
    e = attaque(petit())
    m = monde.resoudre(e, Imposes(1, 1, 2, 9), "B")
    assert (m.points, m.controle, m.vainqueur) == (2, 5, "Rats")
    e["quartiers"]["B"] |= {"controle": 10}
    attaque(e)
    assert monde.resoudre(e, Imposes(1, 1, 1, 5), "B").controle == 10  # jamais plus de 10
    attaque(e)
    m = monde.resoudre(e, Imposes(1, 1, 5, 4), "B")  # 5 contre 4 + 1
    assert (m.points, m.vainqueur) == (0, None) and "sans vainqueur" in e["journal"][-1]["texte"]
    with pytest.raises(MondeImpossible):
        monde.resoudre(e, Imposes(), "D")


def test_les_bonus_sont_plafonnes_a_trois():
    e = attaque(petit())
    e["quartiers"]["B"]["annoncee"] = True
    monde.preparer(e, "B", DEFENSE, 3)
    monde.se_battre(e, "B", DEFENSE, True)
    m = monde.resoudre(e, Imposes(1, 6, 1, 5, 5), "B")  # +1 (domine) +2 (clan) +3 (préparé) +2 (combat gagné)
    assert m.bonus_defense == 3 and m.points == 1


# --- Le joueur dans une mêlée ---------------------------------------------------------------------------

def test_le_joueur_est_prevenu_selon_sa_reputation():
    e = attaque(petit(), jour=5)
    assert monde.avancer(e, Imposes(), 4) == [] and monde.melees_annoncees(e) == []  # neutre, ailleurs : rien
    e["reputation"]["Rats"] = MEMBRE
    monde.avancer(e, Imposes(), 4)
    assert monde.melees_annoncees(e) == ["B"] and "pour demain" in e["journal"][-1]["texte"]
    assert monde.avancer(e, Imposes(), 5) == []  # le jour même : elle attend la fin de sa journée
    jouees = monde.avancer(e, Imposes(1, 1, 5, 5), 6)
    assert [m.quartier for m in jouees] == ["B"]
    assert "B" in monde.melees_annoncees(e)  # un membre est prévenu de la suivante aussi

    e = attaque(petit(), jour=5)
    e["reputation"]["Lames"] = AMI
    monde.avancer(e, Imposes(), 4)
    assert monde.melees_annoncees(e) == []  # un ami ne l'apprend que le jour même
    monde.avancer(e, Imposes(), 5)
    assert monde.melees_annoncees(e) == ["B"] and "aujourd'hui" in e["journal"][-1]["texte"]

    e = attaque(petit(), jour=5)
    e["ici"] = "B"
    monde.avancer(e, Imposes(), 5)
    assert monde.melees_annoncees(e) == ["B"]  # il est sur place


def test_sans_le_joueur_les_melees_se_jouent_toutes_seules():
    e = attaque(petit(), jour=2)
    jouees = monde.avancer(e, Des(4), 30)
    assert len(jouees) > 5 and all(m.quartier in ("A", "B", "C") for m in jouees)
    assert [x["jour"] for x in e["journal"]] == sorted(x["jour"] for x in e["journal"])  # dans l'ordre des jours
    assert all(q["attaque"] is None or q["attaque"] >= 30 for q in e["quartiers"].values())


def test_un_seul_preparatif_et_un_seul_camp():
    e = attaque(petit())
    with pytest.raises(MondeImpossible, match="Aucune mêlée"):
        monde.preparer(e, "B", DEFENSE, 1)
    e["quartiers"]["B"]["annoncee"] = True
    monde.preparer(e, "B", DEFENSE, 2)
    with pytest.raises(MondeImpossible, match="Un seul préparatif"):
        monde.preparer(e, "B", DEFENSE, 1)
    with pytest.raises(MondeImpossible, match="déjà choisi son camp"):
        monde.se_battre(e, "B", ATTAQUE, True)
    assert monde.camps(e, "B") == {ATTAQUE: "Lames", DEFENSE: "Rats"}


def test_se_meler_d_une_melee_change_la_reputation():
    e = attaque(petit())
    e["quartiers"]["B"]["annoncee"] = True
    monde.se_battre(e, "B", ATTAQUE, True)
    m = monde.resoudre(e, Imposes(1, 1, 8, 2), "B")  # 8 + 2 contre 2 + 1 : son camp gagne
    assert e["reputation"] == {"Lames": AMI, "Rats": HOSTILE, "Helix": NEUTRE}
    assert m.reputation == ["Lames : neutre → ami", "Rats : neutre → hostile"]
    attaque(e)
    e["quartiers"]["B"]["annoncee"] = True
    monde.se_battre(e, "B", ATTAQUE, False)
    monde.resoudre(e, Imposes(1, 1, 2, 9), "B")  # son camp perd : rien de gagné, mais l'autre s'en souvient
    assert e["reputation"] == {"Lames": AMI, "Rats": RECHERCHE, "Helix": NEUTRE}


# --- La réputation --------------------------------------------------------------------------------------

def test_la_reputation_monte_et_baisse_d_un_cran():
    e = petit()
    assert monde.bouger_reputation(e, "Lames", 1) == ["Lames : neutre → ami", "Rats : neutre → hostile"]
    assert monde.bouger_reputation(e, "Lames", 1) == ["Rats : hostile → recherché"]  # ami : on ne monte pas plus
    assert monde.bouger_reputation(e, "Rats", -1) == []  # recherché : on ne tombe pas plus bas
    assert monde.bouger_reputation(e, "Helix", -1) == ["Helix : neutre → hostile"]
    assert monde.entrer(e, "Lames") == "Lames : ami → membre" and monde.reputation(e, "Lames") == MEMBRE
    assert monde.bouger_reputation(e, "Lames", 1, rivale=False) == []  # un membre le reste
    with pytest.raises(MondeImpossible, match="ami"):
        monde.entrer(e, "Helix")


# --- Le journal et la carte -----------------------------------------------------------------------------

def test_les_trois_nouvelles_les_plus_importantes():
    e = petit()
    monde.noter(e, 1, monde.QUARTIER, "A", "Une bagarre à A.")
    monde.noter(e, 2, monde.QUARTIER, "D", "Une coupure à D.")
    monde.noter(e, 2, monde.VILLE, "Nord", "Une grève dans le Nord.")
    monde.noter(e, 3, monde.MONDE, "", "Un krach.")
    assert monde.nouvelles(e) == ["Jour 3 — Un krach.", "Jour 2 — Une grève dans le Nord.", "Jour 2 — Une coupure à D."]
    assert monde.nouvelles(e) == []  # déjà données au MJ ; le reste est dans le journal
    for jour in range(300):
        monde.noter(e, jour, monde.QUARTIER, "A", "…")
    assert len(e["journal"]) == monde.JOURNAL_MAX and e["lu"] == 0


def test_la_carte_pour_le_joueur():
    e = attaque(petit())
    e["reputation"]["Rats"] = AMI
    texte = "\n".join(monde.carte(e))
    assert "Nord — dominé par Rats" in texte and "B : Rats (contrôle 3, disputé)" in texte
    assert "D : Helix (contrôle 7)  ← tu es ici" in texte and "Rats (gang, 2 quartiers) — Nour" in texte
    assert "toi : ami" in texte
    s = monde.situation(e, "B")
    assert s["maitre"] == "Rats" and s["dispute"] and s["reputation"] == {"Rats": AMI} and "melee" not in s


# --- Les outils du MJ -----------------------------------------------------------------------------------

def test_sans_monde_pas_d_outils_du_monde():
    s = session()
    assert "inconnu" in s.appeler("monde")["erreur"]
    assert not {"monde", "melee", "reputation"} & {o["function"]["name"] for o in s.schemas()}


def test_l_outil_monde_suit_le_joueur_et_annonce_la_melee():
    s = session(monde=attaque(petit()))
    assert "melee" not in {o["function"]["name"] for o in s.schemas()}  # rien d'annoncé : pas d'outil
    r = s.appeler("monde", {"ici": "B"})
    assert r["quartier"] == "B" and r["maitre"] == "Rats" and r["melee"] == {"attaquant": "Lames", "defenseur": "Rats"}
    assert "se prépare contre B" in r["nouvelles_du_monde"][0]
    assert "melee" in {o["function"]["name"] for o in s.schemas()}
    assert "erreur" in s.appeler("monde", {"ici": "Z"})


def test_l_outil_melee_prepare_puis_fait_se_battre():
    s = session(30, monde=attaque(petit()))
    s.appeler("monde", {"ici": "B"})
    r = s.appeler("melee", {"quartier": "B", "camp": DEFENSE, "action": "preparer", "competence": "Piratage"})
    assert r["pour"] == "Rats" and r["reussi"] and r["bonus_au_de"] == s.monde["quartiers"]["B"]["joueur"]["preparatif"]
    assert "Un seul préparatif" in s.appeler("melee", {"quartier": "B", "camp": DEFENSE, "action": "preparer",
                                                       "competence": "Piratage"})["erreur"]
    assert "déjà choisi son camp" in s.appeler("melee", {"quartier": "B", "camp": ATTAQUE,
                                                         "action": "se_battre"})["erreur"]
    r = s.appeler("melee", {"quartier": "B", "camp": DEFENSE, "action": "se_battre"})
    assert r["contre"] == "Lames" and r["adversaires"] == ["melee_1", "melee_2"]
    assert s.pnj["melee_1"].fiche.combat == 50 and s.pnj["melee_1"].camp == "ennemis"
    assert "déjà dans une mêlée" in s.appeler("melee", {"quartier": "B", "camp": DEFENSE, "action": "se_battre"})["erreur"]
    # Le combat joué : ses deux adversaires sont à terre
    for i in r["adversaires"]:
        s.pnj[i].fiche.etat = Etat.MORT
    s.des = Imposes(1, 1, 5, 5)  # 5 contre 5 + 1 (domine) + son préparatif + 2 (combat gagné), plafonné à +3
    fin = outils._fin_de_melee(s)["melee"]
    assert fin["le_joueur_a_gagne_son_combat"] and fin["vainqueur"] == "Rats" and s.melee is None
    assert fin["reputation"] == ["Rats : neutre → ami", "Lames : neutre → hostile"]


def test_un_combat_de_melee_perdu():
    s = session(monde=attaque(petit()))
    s.appeler("monde", {"ici": "B"})
    s.appeler("melee", {"quartier": "B", "camp": ATTAQUE, "action": "se_battre"})
    s.des = Imposes(1, 1, 5, 5)  # ses adversaires sont debout : 5 − 2 contre 5 + 1
    fin = outils._fin_de_melee(s)["melee"]
    assert not fin["le_joueur_a_gagne_son_combat"] and fin["vainqueur"] == "Rats"
    assert s.monde["reputation"]["Rats"] == HOSTILE and s.monde["reputation"]["Lames"] == NEUTRE


def test_l_outil_reputation():
    s = session(monde=petit())
    r = s.appeler("reputation", {"faction": "Helix", "acte": "un service rendu"})
    assert r["reputation"] == AMI and r["changements"] == ["Helix : neutre → ami"]
    assert "déjà compté" in s.appeler("reputation", {"faction": "Helix", "acte": "un service rendu"})["erreur"]
    r = s.appeler("reputation", {"faction": "Helix", "acte": "un de ses hommes tué devant témoin"})
    assert r["reputation"] == NEUTRE
    assert "erreur" in s.appeler("reputation", {"faction": "Helix", "acte": "un cadeau"})


def test_le_monde_vit_quand_le_temps_passe():
    s = session(monde=attaque(petit(), jour=1))
    s.des = Imposes(1, 1, 9, 3)
    assert "nouvelles_du_monde" not in s.appeler("avancer_temps")  # encore le jour 1
    s.appeler("avancer_temps")
    r = s.appeler("avancer_temps")  # le matin du jour 2 : la mêlée d'hier a été jouée
    assert s.moment.jour == 2 and 0 < len(r["nouvelles_du_monde"]) <= 3
    assert "Mêlée à B : avantage à Lames" in s.monde["journal"][0]["texte"] and s.jour_du_monde == 2
    assert all(q["attaque"] is None or q["attaque"] > 2 for q in s.monde["quartiers"].values())


def test_le_monde_est_sauvegarde():
    s = session(monde=attaque(petit()))
    donnees = partie_vers_dict(Partie(s.personnage, s.univers, monde=s.monde))
    assert partie_depuis_dict(donnees).monde == s.monde
    del donnees["monde"]
    assert partie_depuis_dict(donnees).monde is None  # une sauvegarde d'avant : pas de monde


def test_le_compte_rendu_des_melees():
    assert decrire_monde("reputation", {}, {"changements": ["Helix : neutre → ami"]}) == ["🏳 Réputation — Helix : neutre → ami"]
    assert decrire_monde("reputation", {}, {"erreur": "non"}) == [] and decrire_monde("etat", {}, {}) == []
    fin = {"melee": {"quartier": "B", "attaquant": "Lames", "defenseur": "Rats", "vainqueur": "Lames",
                     "quartier_pris": True, "controle": 5, "reputation": ["Rats : neutre → hostile"]}}
    assert decrire_monde("fin_combat", {}, fin) == ["⚔ Mêlée de B : Lames contre Rats — Lames prend le quartier.",
                                                    "   Réputation — Rats : neutre → hostile"]


def test_une_nouvelle_campagne_a_sa_carte(tmp_path):
    choix = choix_par_defaut(charger(), "Cyberpunk", "Osaka 2091", "Osaka sous la pluie.", 2091)
    serveur = ServeurScripte(
        *[[{"name": "retirer", "arguments": {"retirer": []}}]] * 3,
        *[[{"name": "renommer", "arguments": {"renommages": []}}]] * 4,
        [{"name": "trier_parcours", "arguments": {"retirer": [], "renommer": []}}],
        [{"name": "ajouter_parcours", "arguments": {"parcours": []}}],
        [{"name": "proposer_personnage", "arguments": {"nom": "Yuki Sato", "motivation": "m", "lien": "l",
                                                       "defaut": "d", "allure": "a"}}],
        "La pluie tombe sur Osaka.",
    )
    reponses, lignes = iter(["tout", "", "", "carte", "quitter"]), []
    partie = jeu.Jeu(serveur, budget=128, entree=lambda _: next(reponses), sortie=lignes.append,
                     campagne=Campagne(tmp_path), choix=choix, creer=True)
    partie.jouer()
    texte = "\n".join(lignes)
    assert "← tu es ici" in texte and "Les factions :" in texte and "« carte » : qui tient quoi" in texte
    sauvegarde = json.loads((tmp_path / "sauvegarde.json").read_text(encoding="utf-8"))
    assert len(sauvegarde["monde"]["districts"]) == 6 and len(sauvegarde["monde"]["factions"]) == 8
    reprise = jeu.Jeu(ServeurScripte("On reprend."), budget=128, entree=lambda _: "quitter", sortie=lambda _: None,
                      campagne=Campagne(tmp_path))
    assert reprise.session.monde == sauvegarde["monde"]
