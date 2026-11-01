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


def test_la_magie_seulement_dans_un_univers_qui_en_a():
    session = nouvelle_session(1)
    assert "## Magie" not in mj.prompt_systeme(session.univers, session.personnage)
    elara = nouvelle_session(1, "fantasy")
    prompt = mj.prompt_systeme(elara.univers, elara.personnage)
    assert "## Magie" in prompt and "Trait de feu : attaque, modéré, 3 PM" in prompt
    assert "Lance de glace" not in prompt  # le Givre n'est pas un de ses domaines
    assert "Ce que la magie ne fait pas" in prompt and "{" not in prompt
