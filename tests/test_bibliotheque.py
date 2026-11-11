"""La bibliothèque : ses données, ses vérifications et son filtre (REGLES.md 1.3)."""

import copy

import pytest

from aria import bibliotheque as b

BIBLIOTHEQUE = b.charger()


def erreurs_avec(modifier) -> list[str]:
    copie = copy.deepcopy(BIBLIOTHEQUE)
    modifier(copie)
    return copie.verifier()


def test_la_bibliotheque_est_valide():
    assert BIBLIOTHEQUE.verifier() == []
    assert len(BIBLIOTHEQUE.parcours) == 159
    assert set(BIBLIOTHEQUE.genres) == set(b.GENRES)


def test_les_raccourcis_de_genre():
    assert b.genres_de(["moderne"]) == {"Contemporain", "Horreur", "Militaire", "Cyberpunk", "Post-apo"}
    assert b.genres_de(["futuriste", "Militaire"]) == {"Cyberpunk", "Science-fiction", "Militaire"}
    assert b.genres_de(["tous"]) == set(b.GENRES)


def test_le_filtre_du_cyberpunk():
    cyber = BIBLIOTHEQUE.filtrer("Cyberpunk", magie=False)
    noms = {a["nom"] for a in cyber.armes}
    assert {"Pistolet lourd", "Pistolet intelligent", "Katana"} <= noms
    assert "Épée longue" not in noms  # médiéval
    assert len(cyber.parcours) == 19 and cyber.implants and cyber.domaines == []
    assert {v["nom"] for v in cyber.vehicules} >= {"Char", "AV de corpo", "Drone de combat"}


def test_le_filtre_et_la_magie():
    sans = BIBLIOTHEQUE.filtrer("Fantasy", magie=False)
    avec = BIBLIOTHEQUE.filtrer("Fantasy", magie=True)
    assert "Mage" not in {p["nom"] for p in sans.parcours} and "Mage" in {p["nom"] for p in avec.parcours}
    assert sans.domaines == [] and len(avec.domaines) == 6
    assert sans.implants == []  # pas d'implants hors du Cyberpunk
    assert [v["nom"] for v in avec.vehicules] == ["Cheval"]


def test_un_genre_inconnu():
    with pytest.raises(KeyError):
        BIBLIOTHEQUE.filtrer("Western", magie=False)


def test_les_parcours_sont_verifies():
    def sept_competences(bi):
        bi.parcours[0]["competences"] = bi.parcours[0]["competences"][:7]
    assert any("8 compétences" in e for e in erreurs_avec(sept_competences))

    def magie_dans_le_cyberpunk(bi):
        p = next(x for x in bi.parcours if x["genre"] == "Cyberpunk")
        p["magie"] = True
    assert any("genre sans magie" in e for e in erreurs_avec(magie_dans_le_cyberpunk))


def test_l_equipement_de_depart_est_verifie():
    def armure_lourde(bi):
        solo = next(x for x in bi.parcours if x["nom"] == "Solo")
        solo["equipement"]["armures"] = ["Armure tactique"]
    assert any("plus de 3" in e for e in erreurs_avec(armure_lourde))

    def implant_militaire(bi):
        solo = next(x for x in bi.parcours if x["nom"] == "Solo")
        solo["equipement"]["implants"] = ["Sandevistan"]
    assert any("gamme standard" in e for e in erreurs_avec(implant_militaire))

    def epee_a_neo_tokyo(bi):
        solo = next(x for x in bi.parcours if x["nom"] == "Solo")
        solo["equipement"]["armes"] = ["Épée longue"]
    assert any("n'existe pas dans ce genre" in e for e in erreurs_avec(epee_a_neo_tokyo))


def test_les_armes_sont_verifiees():
    def pistolet_monstrueux(bi):
        bi.arme("Pistolet lourd")["degats"] = "4d10"
    assert any("Pistolet lourd" in e for e in erreurs_avec(pistolet_monstrueux))

    def grenade_trop_forte(bi):
        bi.arme("Grenade à fragmentation")["degats"] = "6d6"
    assert any("hors des bornes" in e for e in erreurs_avec(grenade_trop_forte))


def test_les_vehicules_sont_verifies():
    def moto_blindee(bi):
        bi.vehicule("Moto sportive")["blindage"] = 6
    assert any("le blindage va de 0 à 2" in e for e in erreurs_avec(moto_blindee))

    def canon_sur_une_citadine(bi):
        bi.vehicule("Citadine")["armes_montees"] = [{"tourelle": "légère", "arme": "Canon de char"}]
    assert any("tourelle lourde" in e for e in erreurs_avec(canon_sur_une_citadine))

    def trop_d_armes(bi):
        bi.vehicule("Berline")["armes_montees"] = [{"tourelle": "légère", "arme": "Fusil d'assaut"}] * 2
    assert any("points d'emport" in e for e in erreurs_avec(trop_d_armes))


def test_les_fabricants_et_leurs_categories():
    def kiroshi_fait_des_gilets(bi):
        bi.modeles.append({"nom": "Gilet Kiroshi", "type": "armure", "base": "Gilet balistique", "fabricant": "Kiroshi",
                           "qualite": "personnalisé", "modifications": [], "genres": ["Cyberpunk"]})
    assert any("ne fabrique pas" in e for e in erreurs_avec(kiroshi_fait_des_gilets))

    def sans_modification_d_usine(bi):
        modele = next(m for m in bi.modeles if m["nom"] == "Pistolet lourd Arasaka")
        modele["modifications"] = ["Nouveau calibre"]
    assert any("modification d'usine" in e for e in erreurs_avec(sans_modification_d_usine))


def test_le_plafond_des_modifications():
    def trois_viseurs(bi):
        bi.modifications.append(dict(bi.modification("Viseur holographique"), nom="Viseur bis"))
        modele = next(m for m in bi.modeles if m["nom"] == "Fusil de précision Tsunami « Nekomata »")
        modele["modifications"] = ["Pointeur laser", "Viseur holographique", "Viseur bis"]
    assert any("plafond" in e for e in erreurs_avec(trois_viseurs))


def test_les_implants_sont_verifies():
    def gamme_fausse(bi):
        bi.implant("Optiques Kiroshi")["gamme"] = "avancée"
    assert any("bonus vaut +5" in e for e in erreurs_avec(gamme_fausse))

    def systeme_inconnu(bi):
        bi.implant("Neuroport")["systeme"] = "Rate"
    assert any("système inconnu" in e for e in erreurs_avec(systeme_inconnu))
