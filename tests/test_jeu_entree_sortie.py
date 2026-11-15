"""`jeu.lancer` et `personnages.creer` passent l'entrée et la sortie qu'on leur donne : la console par défaut, l'interface web."""

from contextlib import contextmanager
from types import SimpleNamespace

from aria import campagne, chemins, creation_texte, jeu, personnages


def test_lancer_donne_l_entree_et_la_sortie_au_jeu(tmp_path, monkeypatch):
    monkeypatch.setattr(chemins, "DONNEES", tmp_path / ".Aria-JDR")
    recus = {}

    @contextmanager
    def faux_mj(sortie=print):
        sortie("Chargement du MJ.")
        yield "serveur", {"budget_reflexion": 512}, SimpleNamespace(contexte=16384)

    class FauxJeu:
        def __init__(self, serveur, budget, contexte, **kwargs):
            recus.update(kwargs, budget=budget)

        def jouer(self):
            recus["sortie"]("La partie se joue.")

    monkeypatch.setattr(jeu, "mj_charge", faux_mj)
    monkeypatch.setattr(jeu, "Jeu", FauxJeu)
    dits = []
    entree = lambda invite="": "oui"  # noqa: E731
    jeu.lancer(campagne.Campagne.nommee("essai"), entree=entree, sortie=dits.append)
    assert recus["entree"] is entree and recus["sortie"] == dits.append
    assert dits == ["Chargement du MJ.", "La partie se joue."]


def test_lancer_dit_par_la_sortie_donnee_quand_le_moteur_leve_une_interruption(tmp_path, monkeypatch):
    monkeypatch.setattr(chemins, "DONNEES", tmp_path / ".Aria-JDR")

    @contextmanager
    def faux_mj(sortie=print):
        yield "serveur", {"budget_reflexion": 512}, SimpleNamespace(contexte=16384)

    class JeuInterrompu:
        def __init__(self, *args, **kwargs):
            pass

        def jouer(self):
            raise EOFError

    monkeypatch.setattr(jeu, "mj_charge", faux_mj)
    monkeypatch.setattr(jeu, "Jeu", JeuInterrompu)
    dits = []
    jeu.lancer(campagne.Campagne.nommee("essai"), sortie=dits.append)
    assert dits == ["\nPartie interrompue."]


def test_mj_charge_dit_par_la_sortie_donnee_qu_aucun_mj_n_est_qualifie(monkeypatch):
    monkeypatch.setattr(jeu.banc, "profil_valide", lambda: None)
    dits = []
    with jeu.mj_charge(dits.append) as mj:
        assert mj is None
    assert dits and "Pas de MJ qualifié" in dits[0]


def test_creer_un_personnage_abandonne_le_dit_par_la_sortie_donnee(monkeypatch):
    class Abandonne:
        def __init__(self, *args, **kwargs):
            pass

        def composer(self):
            raise creation_texte.Abandon

    monkeypatch.setattr(creation_texte, "Guide", Abandonne)
    dits = []
    assert personnages.creer("Cyberpunk", "débutant", False, lambda invite="": "", dits.append) is None
    assert dits == ["Création abandonnée."]


def test_le_banc_du_generateur_dit_par_la_sortie_donnee_qu_aucun_mj_n_est_qualifie(monkeypatch):
    from aria import banc, banc_generateur
    monkeypatch.setattr(banc, "profil_valide", lambda: None)
    dits = []
    banc_generateur.lancer(sortie=dits.append)
    assert len(dits) == 1 and "Pas de MJ qualifié" in dits[0]


def test_la_ligne_de_commande_du_banc_du_generateur_passe_par_la_meme_fonction(monkeypatch):
    from aria import banc_generateur
    recus = []
    monkeypatch.setattr(banc_generateur, "lancer", lambda budgets, sortie: recus.append(budgets))
    banc_generateur.main(["--budgets", "128", "256"])
    assert recus == [[128, 256]]
