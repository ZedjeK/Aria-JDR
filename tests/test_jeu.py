"""La démo v2 : l'affichage des jets et une petite partie avec un faux MJ."""

from aria import jeu
from aria.banc import nouvelle_session
from aria.campagne import Campagne
from aria.compte_rendu import decrire
from aria.des import DesTruques
from test_table import ServeurScripte, appel


def lignes(outil, arguments, session=None):
    session = session or nouvelle_session(1)
    return decrire(outil, arguments, session.appeler(outil, arguments), session)


def test_un_test_de_competence_se_voit():
    assert lignes("test_competence", {"competence": "Piratage", "difficulte": "difficile"}) == \
        ["🎲 Piratage (difficile) : 18 / 55 → réussite majeure"]  # Piratage 75, −20 ; la graine 1 fait 18


def test_une_attaque_se_voit():
    session = nouvelle_session(1)
    session.appeler("creer_pnj", {"identifiant": "ganger", "nom": "Ganger", "camp": "ennemis", "combat": 45,
                                  "pv": 10, "arme": "Couteau"})
    session.appeler("debut_combat", {"pnj": ["ganger"]})
    texte = lignes("attaquer", {"attaquant": "joueur", "cible": "ganger"}, session)
    assert texte[0].startswith("⚔️ Kaito attaque Ganger : ")
    assert len(texte) >= 2


def test_une_erreur_ne_se_voit_pas():
    assert lignes("test_competence", {"competence": "Pirater", "difficulte": "normale"}) == []
    assert lignes("etat", {}) == []


def test_une_partie(tmp_path):
    serveur = ServeurScripte("La pluie tombe sur la ruelle.",
                             [appel("test_competence", competence="Piratage", difficulte="normale")],
                             "La porte s'ouvre.")
    entrees = iter(["", "etat", "Je pirate la porte.", "quitter"])
    sortie = []
    partie = jeu.Jeu(serveur, budget=128, des=DesTruques(30, 50), entree=lambda _: next(entrees),
                     sortie=sortie.append, campagne=Campagne(tmp_path))
    partie.jouer()
    texte = "\n".join(sortie)
    assert "La pluie tombe sur la ruelle." in texte
    assert "🎲 Piratage : 30 / 75 → réussite majeure" in texte and "La porte s'ouvre." in texte
    assert "Kaito — jour 1" in texte  # la commande etat, sans passer par le MJ
    assert len(serveur.recus) == 3
    assert (tmp_path / "sauvegarde.json").is_file()
    assert "Piratage 75 : jet 50" in texte  # la fin de session tente de faire progresser la compétence réussie
