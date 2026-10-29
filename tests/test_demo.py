"""La démo jouée de bout en bout par des « joueurs » automatiques, pour vérifier qu'elle ne plante jamais."""

import random

import pytest

from aria.demo import Demo
from aria.des import Des
from aria.sauvegarde import charger


def joueur(strategie: str, graine: int):
    """Un joueur automatique : toujours la 1re option, ou au hasard (y compris des réponses invalides)."""
    hasard = random.Random(graine)

    def repondre(_invite: str) -> str:
        if strategie == "premier":
            return "1"
        return hasard.choice(["1", "2", "3", "4", "5", "abc", "", "0", "9"])
    return repondre


@pytest.mark.parametrize("strategie", ["premier", "hasard"])
@pytest.mark.parametrize("graine", range(25))
def test_la_demo_se_joue_jusqu_au_bout(tmp_path, strategie, graine):
    lignes = []
    chemin = tmp_path / "partie.json"
    demo = Demo(Des(graine), joueur(strategie, graine), lignes.append, chemin)
    demo.jouer()
    texte = "\n".join(lignes)
    assert "Néo-Tokyo 2087" in texte
    if "Fin de la partie" in texte:
        assert not chemin.exists()
    else:
        assert charger(chemin).personnage.nom == "Kaito"
