"""Le générateur des cartes de combat (aria.carte_combat, REGLES.md 7.11) : six lieux, le décor, le placement des camps."""

import pytest

from aria import carte_combat as cc
from aria.combat import Decor
from aria.des import Des
from aria.grille import Terrain, colonne_ligne, distance


class Pion:
    def __init__(self, nom):
        self.nom = nom


def camps(joueurs=1, ennemis=2):
    return [Pion(f"J{i}") for i in range(joueurs)], [Pion(f"E{i}") for i in range(ennemis)]


def ecart_min(carte, joueurs, ennemis):
    return min(distance(carte.positions[j], carte.positions[e]) for j in joueurs for e in ennemis)


def test_six_lieux():
    assert cc.LIEUX == ("ruelle", "entrepôt", "bar", "toit", "parking", "couloir")
    assert set(cc.GABARITS) == set(cc.LIEUX) and cc.LIEU_PAR_DEFAUT in cc.LIEUX


@pytest.mark.parametrize("lieu", cc.LIEUX)
@pytest.mark.parametrize("decor", list(Decor))
def test_chaque_lieu_et_chaque_decor_donnent_une_carte_jouable(lieu, decor):
    gabarit = cc.GABARITS[lieu]
    for graine in range(40):
        joueurs, ennemis = camps(2, 3)
        carte = cc.ouvrir(lieu, decor, Des(graine), joueurs, ennemis)
        assert gabarit.largeur[0] <= carte.largeur <= gabarit.largeur[1]
        assert gabarit.hauteur[0] <= carte.hauteur <= gabarit.hauteur[1]
        assert carte.lieu == lieu
        assert all(carte.praticable(p) for p in carte.positions.values())
        assert len(set(carte.positions.values())) == 5  # une case par combattant
        assert ecart_min(carte, joueurs, ennemis) >= cc.ecart_de_depart(lieu, False)
        assert all(carte.relie(carte.positions[joueurs[0]], carte.positions[e]) for e in ennemis)


@pytest.mark.parametrize("lieu, ecart", [("ruelle", 12), ("entrepôt", 12), ("toit", 12), ("parking", 12),
                                         ("bar", 8), ("couloir", 8)])
def test_les_camps_commencent_a_leur_distance_de_depart(lieu, ecart):
    assert cc.ecart_de_depart(lieu, False) == ecart
    joueurs, ennemis = camps()
    assert ecart_min(cc.ouvrir(lieu, Decor.ENCOMBRE, Des(3), joueurs, ennemis), joueurs, ennemis) == ecart


@pytest.mark.parametrize("lieu", cc.LIEUX)
def test_en_embuscade_le_camp_qui_surprend_commence_a_six_cases(lieu):
    assert cc.ecart_de_depart(lieu, True) == 6
    joueurs, ennemis = camps()
    assert ecart_min(cc.ouvrir(lieu, Decor.ENCOMBRE, Des(5), joueurs, ennemis, embuscade=True), joueurs, ennemis) == 6


def test_les_joueurs_commencent_du_cote_de_leur_bord_et_les_ennemis_en_face():
    joueurs, ennemis = camps()
    carte = cc.ouvrir("parking", Decor.ENCOMBRE, Des(2), joueurs, ennemis)
    assert carte.bords == {"joueurs": 0, "ennemis": carte.largeur - 1}
    colonnes = lambda qui: [colonne_ligne(carte.positions[x])[0] for x in qui]
    assert max(colonnes(joueurs)) < min(colonnes(ennemis))
    assert max(colonnes(joueurs)) <= 3


def test_la_meme_graine_donne_la_meme_carte():
    def dessin(graine):
        joueurs, ennemis = camps()
        carte = cc.ouvrir("entrepôt", Decor.FORTIFIE, Des(graine), joueurs, ennemis)
        return carte.largeur, carte.hauteur, sorted(carte.terrain.items()), sorted(carte.positions.values())
    assert dessin(11) == dessin(11)
    assert dessin(11) != dessin(12)


def _compte(decor, terrain, lieu="parking"):
    total = 0
    for graine in range(20):
        carte = cc.dessiner(lieu, decor, Des(graine))
        total += sum(t is terrain for t in carte.terrain.values())
    return total


def test_le_decor_regle_la_densite_d_obstacles():
    assert _compte(Decor.DEGAGE, Terrain.BAS) < _compte(Decor.ENCOMBRE, Terrain.BAS)
    assert _compte(Decor.DEGAGE, Terrain.BLINDE) == _compte(Decor.ENCOMBRE, Terrain.BLINDE) == 0
    assert _compte(Decor.FORTIFIE, Terrain.BLINDE) > 0


@pytest.mark.parametrize("lieu", ["ruelle", "entrepôt", "bar", "couloir"])
def test_les_lieux_fermes_ont_des_murs(lieu):
    carte = cc.dessiner(lieu, Decor.DEGAGE, Des(1))
    assert sum(t is Terrain.PLEIN for t in carte.terrain.values()) >= carte.largeur


def test_un_lieu_inconnu_est_refuse():
    with pytest.raises(ValueError, match="Lieu inconnu"):
        cc.ouvrir("cathédrale", Decor.ENCOMBRE, Des(1), *camps())


def test_un_renfort_entre_par_le_bord_de_son_cote():
    joueurs, ennemis = camps()
    carte = cc.ouvrir("ruelle", Decor.ENCOMBRE, Des(4), joueurs, ennemis)
    renfort, allie = Pion("Renfort"), Pion("Allié")
    cc.entrer(carte, renfort, "ennemis", Des(1))
    cc.entrer(carte, allie, "joueurs", Des(1))
    assert colonne_ligne(carte.positions[renfort])[0] >= carte.largeur - 3
    assert colonne_ligne(carte.positions[allie])[0] <= 2
    assert carte.praticable(carte.positions[renfort])
