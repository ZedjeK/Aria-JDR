"""La table de jeu, jouée avec un faux serveur qui suit un script."""

import json

from aria import table
from aria.banc import nouvelle_session
from aria.table import Table


def appel(nom, **arguments):
    return {"name": nom, "arguments": arguments}


class ServeurScripte:
    """Répond les messages du script dans l'ordre : une liste d'appels d'outils, ou une narration."""

    def __init__(self, *script, prompt_tokens=1000):
        self.script, self.prompt_tokens = list(script), prompt_tokens
        self.recus = []  # (messages, outils) de chaque requête

    def discuter(self, messages, outils=None, budget=None):
        self.recus.append(([dict(m) for m in messages], outils))
        suivant = self.script.pop(0) if self.script else "Que fais-tu ?"
        if isinstance(suivant, str):
            message = {"role": "assistant", "content": suivant, "reasoning_content": "hmm"}
        else:
            message = {"role": "assistant", "content": None, "tool_calls": [
                {"id": str(i), "type": "function", "function": {"name": a["name"], "arguments": json.dumps(a["arguments"])}}
                for i, a in enumerate(suivant)]}
        return {"choices": [{"message": message}],
                "usage": {"completion_tokens": 5, "prompt_tokens": self.prompt_tokens}}


def nouvelle_table(serveur, **options):
    return Table(serveur, nouvelle_session(1), budget=128, **options)


def test_un_tour_avec_un_jet():
    serveur = ServeurScripte([appel("test_competence", competence="Piratage", difficulte="normale")],
                             "La serrure cède.")
    tour = nouvelle_table(serveur).tour("Je pirate la porte.")
    assert tour.narration == "La serrure cède."
    assert [a.outil for a in tour.appels] == ["test_competence"] and tour.appels[0].reussi
    assert tour.jetons == 10 and not tour.interrompu
    messages, outils = serveur.recus[1]
    assert outils and messages[-1]["role"] == "tool" and '"jet"' in messages[-1]["content"]


def test_la_reflexion_n_est_pas_gardee():
    t = nouvelle_table(ServeurScripte("Bonsoir."))
    t.tour("Salut.")
    assert t.messages[-1] == {"role": "assistant", "content": "Bonsoir."}


def test_une_erreur_revient_au_mj():
    serveur = ServeurScripte([appel("test_competence", competence="Pirater", difficulte="normale")], "Oups.")
    tour = nouvelle_table(serveur).tour("Je pirate la porte.")
    assert not tour.appels[0].reussi
    assert "erreur" in serveur.recus[1][0][-1]["content"]


def test_l_historique_reste_d_un_tour_a_l_autre():
    serveur = ServeurScripte("Une ruelle sous la pluie.", "Tu avances.")
    t = nouvelle_table(serveur, scene="Une ruelle.")
    t.ouvrir()
    t.tour("J'avance.")
    messages = serveur.recus[1][0]
    assert messages[0]["role"] == "system" and "Une ruelle." in messages[0]["content"]
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]
    assert messages[1]["content"] == table.OUVERTURE


def test_le_mj_qui_tourne_en_rond_doit_raconter():
    serveur = ServeurScripte(*[[appel("etat")]] * table.TOURS_MAX, "Bon, je raconte.")
    tour = nouvelle_table(serveur).tour("Je regarde autour.")
    assert tour.interrompu and tour.narration == "Bon, je raconte."
    assert len(tour.appels) == table.TOURS_MAX
    assert serveur.recus[-1][1] is None  # la dernière demande est faite sans outils


def test_les_vieux_echanges_sont_oublies():
    serveur = ServeurScripte(*[[appel("etat")], "Réponse."] * 6, prompt_tokens=1000)
    t = nouvelle_table(serveur)
    for i in range(6):
        t.tour(f"Action {i}")
    assert len(t.messages) == 1 + 6 * 4  # rien n'est oublié tant que ça tient
    serveur.prompt_tokens = t.limite + 500  # le serveur annonce un prompt trop gros
    serveur.script = ["Encore."]
    t.tour("Action 6")
    t.tour("Action 7")
    roles = [m["role"] for m in t.messages]
    assert roles[0] == "system" and roles[1] == "user"  # jamais un résultat d'outil orphelin
    assert t.messages[1]["content"] != "Action 0"
    assert t.messages[-2]["content"] == "Action 7"


def test_le_dernier_echange_n_est_jamais_oublie():
    # « Tu esquives ou tu ripostes ? » doit rester visible quand le joueur répond « J'esquive »
    serveur = ServeurScripte("Un.", "Deux.", "Trois.", prompt_tokens=10 ** 6)
    t = nouvelle_table(serveur)
    for phrase in ("Premier", "Second", "Troisième"):
        t.tour(phrase)
    assert [m["content"] for m in t.messages[1:]] == ["Second", "Deux.", "Troisième", "Trois."]
