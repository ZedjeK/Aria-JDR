"""`jeu.lancer` et `personnages.creer` passent l'entrée et la sortie qu'on leur donne : la console par défaut, l'interface web."""

import io
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


def test_le_moteur_dit_qu_il_cree_l_univers_avant_la_longue_attente(tmp_path, monkeypatch):
    """La génération de l'univers dure des minutes : le joueur doit le lire avant qu'elle commence, pas après."""
    from aria import generateur

    class Arrete(Exception):
        pass

    def creer_campagne(*args, **kwargs):
        raise Arrete

    monkeypatch.setattr(chemins, "DONNEES", tmp_path / ".Aria-JDR")
    monkeypatch.setattr(generateur, "creer_campagne", creer_campagne)
    choix = generateur.choix_par_defaut(generateur.charger(), "Cyberpunk")
    dits = []
    try:
        jeu.Jeu(None, 512, entree=lambda invite="": "", sortie=dits.append, campagne=campagne.Campagne.nommee("essai"), choix=choix)
    except Arrete:
        pass
    assert len(dits) == 1 and "crée l'univers" in dits[0] and "minutes" in dits[0]


def _lancer_avec_un_faux_jeu(tmp_path, monkeypatch, **options) -> dict:
    monkeypatch.setattr(chemins, "DONNEES", tmp_path / ".Aria-JDR")
    recus = {}

    @contextmanager
    def faux_mj(sortie=print):
        yield "serveur", {"budget_reflexion": 512}, SimpleNamespace(contexte=16384)

    class FauxJeu:
        def __init__(self, serveur, budget, contexte, **kwargs):
            recus.update(kwargs)

        def jouer(self):
            pass

    monkeypatch.setattr(jeu, "mj_charge", faux_mj)
    monkeypatch.setattr(jeu, "Jeu", FauxJeu)
    jeu.lancer(campagne.Campagne.nommee("essai"), **options)
    return recus


def test_lancer_donne_le_choix_du_joueur_qu_on_lui_passe(tmp_path, monkeypatch):
    choisir = lambda titre, options: 0  # noqa: E731
    recus = _lancer_avec_un_faux_jeu(tmp_path, monkeypatch, entree=lambda invite="": "", sortie=print, choisir=choisir)
    assert recus["choisir"] is choisir


def test_lancer_sans_entree_donnee_choisit_en_console(tmp_path, monkeypatch):
    dits = []
    monkeypatch.setattr("sys.stdin", io.StringIO("2\n"))  # la console réelle : `input` lit l'entrée standard
    recus = _lancer_avec_un_faux_jeu(tmp_path, monkeypatch, sortie=dits.append)
    from aria.choix import Option
    assert recus["choisir"]("Que fais-tu ?", [Option("Tirer"), Option("Fuir")]) == 1


def test_lancer_avec_une_autre_entree_laisse_le_mj_mener_le_combat(tmp_path, monkeypatch):
    recus = _lancer_avec_un_faux_jeu(tmp_path, monkeypatch, entree=lambda invite="": "", sortie=print)
    assert recus["choisir"] is None
