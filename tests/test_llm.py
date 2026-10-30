"""Ce qu'on envoie à llama-server : la ligne de commande et le corps des requêtes."""

from pathlib import Path

from aria.llm import MESSAGE_FIN_REFLEXION, PLAFOND_JETONS, arguments_serveur, requete
from aria.optimiseur import Modele, Reglages

MESSAGES = [{"role": "user", "content": "Bonjour"}]


def test_ligne_de_commande():
    modele = Modele("Bonsai", Path("m.gguf"), 0, 1, False, 262144)
    args = arguments_serveur(modele, Reglages(16384), port=9000)
    assert args[:2] == ["-m", "m.gguf"]
    assert "--jinja" in args
    assert args[args.index("--reasoning-budget-message") + 1] == MESSAGE_FIN_REFLEXION
    assert args[-2:] == ["--port", "9000"]


def test_budget_de_reflexion():
    assert "thinking_budget_tokens" not in requete(MESSAGES) and "chat_template_kwargs" not in requete(MESSAGES)
    assert requete(MESSAGES, budget=0)["chat_template_kwargs"] == {"enable_thinking": False}
    assert requete(MESSAGES, budget=256)["thinking_budget_tokens"] == 256


def test_toujours_un_plafond_de_jetons():
    corps = requete(MESSAGES, outils=[{"type": "function"}])
    assert corps["max_tokens"] == PLAFOND_JETONS
    assert corps["tools"] == [{"type": "function"}]
    assert "tools" not in requete(MESSAGES)
