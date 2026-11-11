"""Le banc du générateur : ce que le code sait juger d'une adaptation, et le choix du budget."""

import json

import pytest

from aria import banc, banc_generateur
from aria.banc_generateur import CADRES, Cadre, budget_generateur, jouer, qualifier, verifier
from aria.bibliotheque import charger
from aria.generateur import Adaptation, choix_par_defaut, generer

ARKHAM = next(c for c in CADRES if c.nom_court == "arkham")
OSAKA = next(c for c in CADRES if c.nom_court == "osaka")
SPIRITE = {"nom": "Spirite", "description": "Elle fait tourner les tables.", "competences": [
    "Occultisme", "Psychologie", "Persuasion", "Mensonge", "Perception", "Arts", "Mythe", "Culture générale"],
    "equipement": {"armes": ["rien"], "armures": ["rien"], "objets": ["un guéridon", "un tarot", "des clients"]}}


@pytest.fixture(scope="module")
def bibliotheque():
    return charger()


def donnees_de(bibliotheque, cadre):
    return generer(bibliotheque, choix_par_defaut(bibliotheque, cadre.genre, cadre.nom, cadre.cadre))


def ajoute(donnees):
    from aria.generateur import valider_parcours
    return valider_parcours(SPIRITE, donnees, set(donnees["parcours"]))[0]


def test_les_cadres_de_reference():
    assert len(CADRES) * banc_generateur.REPETITIONS == 10  # le seuil de 90 % : 9 essais sur 10
    for cadre in CADRES:
        assert cadre.genre in charger().genres


def test_un_objet_interdit_reste_meme_renomme(bibliotheque):
    d = donnees_de(bibliotheque, ARKHAM)
    a = Adaptation("Arkham", "1925", renommages={"armes": {"Fusil d'assaut": "Fusil barrette"}})
    a.parcours_ajoutes = [ajoute(d)]
    raisons = verifier(ARKHAM, d, a)
    assert "« Fusil d'assaut » est resté" in raisons and "« Minigun » est resté" in raisons


def test_arkham_reussi(bibliotheque):
    d = donnees_de(bibliotheque, ARKHAM)
    vehicules = [v for v in ARKHAM.interdits if v in {x["nom"] for x in d["vehicules"]}]
    armes = [x for x in ARKHAM.interdits if x in {a["nom"] for a in d["armes"]}]
    armures = [x for x in ARKHAM.interdits if x in {a["nom"] for a in d["armures"]}]
    a = Adaptation("Arkham", "1925", retraits={"vehicules": vehicules, "armes": armes, "armures": armures},
                   renommages={"armes": {"Pistolet lourd": "Colt .45"}})
    a.parcours_ajoutes = [ajoute(d)]
    assert verifier(ARKHAM, d, a) == []


@pytest.mark.parametrize(
    "nom, raison",
    [
        ("Saw de chantier", "nom anglais"),
        ("Flamethrower de chantier", "nom anglais"),
        ("Camionnettte", "faute"),
        ("Sten de poche", "nom anachronique"),
        ("Veste de chasse", None),  # « veste » n'est pas « vest »
        ("M3 Grease Gun", None),  # un vrai nom d'arme, pas un anglicisme
        ("Smuggleur du port", "nom anglais"),
    ],
)
def test_les_noms_juges(bibliotheque, nom, raison):
    d = donnees_de(bibliotheque, ARKHAM)
    a = Adaptation("Arkham", "1925", renommages={"armes": {"Pistolet lourd": nom}})
    a.parcours_ajoutes = [ajoute(d)]
    raisons = [r for r in verifier(ARKHAM, d, a) if "est resté" not in r]
    assert raisons == [] if raison is None else any(raison in r for r in raisons), raisons


def test_un_cadre_proche_ne_bouge_presque_pas(bibliotheque):
    d = donnees_de(bibliotheque, OSAKA)
    noms = [x["nom"] for x in d["armes"]][:7]
    a = Adaptation("Osaka", "2091", renommages={"armes": {n: f"{n} bis" for n in noms}})
    raisons = verifier(OSAKA, d, a)
    assert any("7 objets retirés ou renommés" in r for r in raisons)
    assert "aucun parcours propre au cadre" in raisons


def test_le_parcours_garde_et_le_nombre_de_parcours(bibliotheque):
    d = donnees_de(bibliotheque, OSAKA)
    retires = [n for n in d["parcours"] if n != "Netrunner"][:9]
    a = Adaptation("Osaka", "2091", parcours_retires=retires + ["Netrunner"])
    raisons = verifier(OSAKA, d, a)
    assert "parcours gardé perdu : Netrunner" in raisons and any("parcours, au lieu de 15 à 30" in r for r in raisons)


class LlmSage:
    """Un faux LLM qui répond juste : il retire les interdits du cadre, ne renomme rien, ne trie rien,
    et ajoute un parcours construit avec les options que l'outil lui propose."""

    def __init__(self, cadre: Cadre):
        self.cadre, self.appels = cadre, 0

    def discuter(self, messages, outils=None, budget=None):
        self.appels += 1
        outil = outils[0]["function"]
        nom, proprietes = outil["name"], outil["parameters"]["properties"]
        if nom == "retirer":
            arguments = {"retirer": [x for x in proprietes["retirer"]["items"]["enum"] if x in self.cadre.interdits]}
        elif nom == "renommer":
            arguments = {"renommages": []}
        elif nom == "trier_parcours":
            arguments = {"retirer": [], "renommer": []}
        else:
            p = proprietes["parcours"]["items"]["properties"]
            arguments = {"parcours": [{
                "nom": "Métier du cadre", "description": "Un métier propre au cadre.",
                "competences": p["competences"]["items"]["enum"][:8],
                "equipement": {"armes": ["rien"], "armures": ["rien"], "objets": ["un", "deux", "trois"]}}]}
        appel = {"id": "0", "type": "function", "function": {"name": nom, "arguments": json.dumps(arguments)}}
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [appel]}}]}


def test_un_essai_reussi_avec_un_llm_sage(bibliotheque):
    essai = jouer(LlmSage(ARKHAM), bibliotheque, ARKHAM, 128)
    assert essai.reussi, essai.raisons
    assert essai.resume["parcours_ajoutes"] == ["Métier du cadre"]


def test_qualifier_garde_le_plus_petit_budget_qui_passe(bibliotheque):
    class Muet:
        def discuter(self, messages, outils=None, budget=None):
            return {"choices": [{"message": {"role": "assistant", "content": "Je ne sais pas."}}]}

    sortie = []
    budget, essais = qualifier(Muet(), budgets=(128,), cadres=(ARKHAM,), repetitions=1, afficher=sortie.append,
                               bibliotheque=bibliotheque)
    assert budget is None and not essais[0].reussi and "raté : 0/1" in sortie[-1]

    class Sage:
        def discuter(self, messages, outils=None, budget=None):
            return LlmSage(ARKHAM).discuter(messages, outils, budget)

    budget, essais = qualifier(Sage(), budgets=(128, 256), cadres=(ARKHAM,), repetitions=2, afficher=sortie.append,
                               bibliotheque=bibliotheque)
    assert budget == 128 and len(essais) == 2  # le budget 256 n'a pas eu besoin de tourner


def test_enregistrer_dans_le_profil(tmp_path, monkeypatch):
    profil = tmp_path / "profil_mj.json"
    profil.write_text(json.dumps({"modele": "Qwen", "budget_reflexion": 512}), encoding="utf-8")
    monkeypatch.setattr(banc, "PROFIL", profil)
    monkeypatch.setattr(banc_generateur, "DETAIL", tmp_path / "banc_generateur.json")
    banc_generateur.enregistrer(256, [banc_generateur.Essai("arkham", 256, True)])
    lu = json.loads(profil.read_text(encoding="utf-8"))
    assert lu["budget_generateur"] == 256 and lu["budget_reflexion"] == 512
    assert budget_generateur(lu) == 256 and budget_generateur({"budget_reflexion": 512}) == 512
    assert json.loads((tmp_path / "banc_generateur.json").read_text(encoding="utf-8"))[0]["cadre"] == "arkham"
