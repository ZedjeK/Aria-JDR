"""La trame (REGLES.md 14) : les types de campagne et l'expérience de départ (REGLES.md 5)."""

import random

import pytest

from aria import amorce, personnages, trame
from aria.campagne import Campagne
from aria.creation import Brouillon, EtapeInvalide, proposer_chiffres, tout_proposer
from aria.creation_texte import Guide
from aria.personnage import AGUERRI, CRANS, DEBUTANT, VETERAN
from aria.univers import PIECE_ARME, PIECE_ARMURE, PIECE_IMPLANT, charger_univers
from tests.test_univers import CYBERPUNK

ROLEPLAY = {"nom": "Yuki Sato", "motivation": "Racheter la dette de sa mère.", "lien": "Sa mère, malade.",
            "defaut": "Ne sait pas dire non à un job."}


@pytest.fixture(scope="module")
def neo_tokyo():
    return charger_univers(CYBERPUNK)


def cree(univers, cran, parcours="Netrunner", graine=3):
    b = proposer_chiffres(Brouillon(univers, cran=cran), random.Random(graine), parcours)
    b.fixer("roleplay", ROLEPLAY)
    return b, *b.finaliser()


# --- Les types de campagne ------------------------------------------------------------------------------

def test_les_cinq_types():
    t = trame.TYPES
    assert list(t) == ["contrat", "courte", "standard", "longue", "sans fin"]
    assert [x.principales for x in t.values()] == [1, 4, 8, 14, 8]
    assert [x.xp for x in t.values()] == [0, 3, 2, 1, 1]
    assert t["courte"].depart == AGUERRI and t["standard"].depart == DEBUTANT and t["sans fin"].sans_fin
    assert "cœur du problème" in t["contrat"].consigne and t["standard"].consigne == ""
    assert "quotidien" in t["longue"].consigne


def test_le_format_d_une_campagne(tmp_path):
    c = Campagne(tmp_path / "osaka")
    assert trame.lire_format(c) == trame.Format("standard", DEBUTANT)  # une campagne d'avant : le format par défaut
    trame.ecrire_format(c, trame.Format("courte", AGUERRI))
    assert trame.lire_format(c) == trame.Format("courte", AGUERRI)
    c.format.write_text('{"type": "épique", "cran": "aguerri"}', encoding="utf-8")
    assert trame.lire_format(c) == trame.Format()  # un type inconnu ne casse rien
    c.format.write_text("{", encoding="utf-8")
    assert trame.lire_format(c) == trame.Format()


def test_l_ouverture_va_dans_la_demande_d_amorce(neo_tokyo):
    _, perso, _ = cree(neo_tokyo, DEBUTANT)
    sans = amorce._demande(neo_tokyo, perso, "Un plan.", [])[1]["content"]
    avec = amorce._demande(neo_tokyo, perso, "Un plan.", [], trame.TYPES["courte"].consigne)[1]["content"]
    assert "cœur du problème" in avec and "cœur du problème" not in sans


# --- L'expérience de départ -----------------------------------------------------------------------------

@pytest.mark.parametrize("cran", [AGUERRI, VETERAN])
@pytest.mark.parametrize("parcours", sorted(charger_univers(CYBERPUNK).parcours))
def test_tout_proposer_a_chaque_cran(neo_tokyo, parcours, cran):
    b, perso, depart = cree(neo_tokyo, cran, parcours)
    regle = CRANS[cran]
    assert sum(b.points_personnels.values()) == regle.points_personnels and sum(b.points_parcours.values()) == 300
    assert perso.cran == cran and max(perso.competences.values()) <= regle.plafond
    assert len(b.equipement["pieces"]) == regle.pieces


def test_un_debutant_ne_change_pas(neo_tokyo):
    b, perso, _ = cree(neo_tokyo, DEBUTANT)
    assert perso.cran == DEBUTANT and perso.argent == 2000 and "pieces" not in b.equipement
    assert sum(b.points_personnels.values()) == 100 and max(perso.competences.values()) <= 75


def test_l_argent_monte_d_un_palier_par_cran(neo_tokyo):
    assert [cree(neo_tokyo, cran)[1].argent for cran in (DEBUTANT, AGUERRI, VETERAN)] == [2000, 5000, 10000]
    assert [cree(neo_tokyo, cran, "Ganger")[1].argent for cran in (DEBUTANT, AGUERRI, VETERAN)] == [500, 1000, 2000]


def test_les_plafonds_suivent_le_cran(neo_tokyo):
    b = Brouillon(neo_tokyo, cran=DEBUTANT)
    b.fixer("parcours", "Netrunner")
    assert (b.plafond("Technologie"), Brouillon(neo_tokyo, cran=AGUERRI).plafond("Technologie"),
            Brouillon(neo_tokyo, cran=VETERAN).plafond("Magie")) == (75, 85, 65)
    b = proposer_chiffres(Brouillon(neo_tokyo, cran=AGUERRI), random.Random(1), "Netrunner")
    with pytest.raises(EtapeInvalide, match="200 points"):
        b.fixer("points_personnels", {"Perception": 100})


def test_les_pieces_au_dessus(neo_tokyo):
    possibles = neo_tokyo.pieces_possibles()
    assert possibles["Pistolet lourd Arasaka"] == PIECE_ARME and possibles["Armure tactique"] == PIECE_ARMURE
    assert possibles["Viseur balistique"] == PIECE_IMPLANT
    assert "Fusil à rail Militech « Breakthrough »" not in possibles  # unique : jamais au départ
    assert "Gilet balistique" not in possibles and "Neuroport" not in possibles
    assert neo_tokyo.verifier_pieces([], DEBUTANT) == []
    assert "1 pièce(s)" in neo_tokyo.verifier_pieces([], AGUERRI)[0]
    assert "une seule pièce de chaque sorte" in " ".join(
        neo_tokyo.verifier_pieces(["Armure tactique", "Exosquelette léger"], VETERAN)).lower()
    assert "pas une pièce" in neo_tokyo.verifier_pieces(["Katana"], AGUERRI)[0]


def test_une_arme_ou_une_armure_au_dessus_remplace_celle_du_metier(neo_tokyo):
    b = proposer_chiffres(Brouillon(neo_tokyo, cran=VETERAN), random.Random(1), "Solo")
    b.fixer("equipement", b.equipement | {"pieces": ["Pistolet lourd Arasaka", "Armure tactique"]})
    b.fixer("roleplay", ROLEPLAY)
    perso, depart = b.finaliser()
    assert (depart.arme, depart.armure) == ("Pistolet lourd Arasaka", "Armure tactique")
    noms = [o["nom"] for o in perso.inventaire["objets"]]
    assert "Pistolet lourd Arasaka" in noms and "Armure tactique" in noms
    assert b.equipement["arme"] not in noms or b.equipement["arme"] == "Pistolet lourd Arasaka"


def test_un_implant_au_dessus_s_ajoute_et_coute_sa_sante_mentale(neo_tokyo):
    b = proposer_chiffres(Brouillon(neo_tokyo, cran=AGUERRI), random.Random(1), "Netrunner")
    sans_piece = dict(b.equipement, pieces=[])
    with pytest.raises(EtapeInvalide, match="neuroport"):  # le cortex frontal demande d'abord un neuroport
        b.fixer("equipement", b.equipement | {"implant": "Paume d'interface", "pieces": ["Mémoire eidétique"]})
    b.fixer("equipement", b.equipement | {"implant": "Neuroport", "pieces": ["Mémoire eidétique"]})
    b.fixer("roleplay", ROLEPLAY)
    perso, _ = b.finaliser()
    assert [i["nom"] for i in perso.implants][-1] == "Mémoire eidétique" and perso.sm == perso.sm_max
    with pytest.raises(EtapeInvalide, match="1 pièce"):
        b.fixer("equipement", sans_piece)


def test_le_guide_annonce_le_cran(neo_tokyo):
    reponses = iter(["tout", "h", "Kenji", "Sa dette", "Son frère", "Têtu", "", ""])
    lignes = []
    perso, _ = Guide(neo_tokyo, lambda _: next(reponses), lignes.append, hasard=random.Random(1), cran=VETERAN).creer()
    texte = "\n".join(lignes)
    assert perso.cran == VETERAN and "300 points personnels" in texte and "En plus (vétéran)" in texte


def test_un_personnage_pret_garde_son_cran(neo_tokyo, tmp_path, monkeypatch):
    monkeypatch.setattr("aria.chemins.DONNEES", tmp_path)
    base = personnages.univers_de_base("Cyberpunk")
    b = tout_proposer(base, hasard=random.Random(2), parcours="Solo", cran=AGUERRI)
    b.fixer("roleplay", ROLEPLAY)
    pret = personnages.enregistrer(b, "Cyberpunk")
    relu = next(p for p in personnages.lister("Cyberpunk") if p.fichier)
    assert relu.cran == AGUERRI and "aguerri" in relu.titre() and personnages.KAITO.cran == DEBUTANT
    brouillon, notes = personnages.brouillon_dans(neo_tokyo, relu, random.Random(1))
    perso, _ = brouillon.finaliser()
    assert perso.cran == AGUERRI and brouillon.equipement["pieces"] == pret.fiche["equipement"]["pieces"] and not notes
