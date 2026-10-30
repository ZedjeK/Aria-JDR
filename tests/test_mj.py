"""Le prompt système du MJ."""

from aria import mj
from aria.banc import nouvelle_session


def test_prompt_rempli():
    session = nouvelle_session(1)
    prompt = mj.prompt_systeme(session.univers, session.personnage, "Une ruelle sous la pluie.")
    assert "Néo-Tokyo 2087" in prompt and "Kaito, Netrunner" in prompt and "Hana" in prompt
    assert prompt.rstrip().endswith("Une ruelle sous la pluie.")
    assert "{" not in prompt  # tous les champs du gabarit sont remplis


def test_prompt_sans_scene():
    session = nouvelle_session(1)
    assert "## La scène" not in mj.prompt_systeme(session.univers, session.personnage)
