"""Le MJ : son prompt système, rempli avec l'univers, le personnage et la scène."""

from pathlib import Path

from aria.personnage import Personnage
from aria.univers import Univers

PROMPT = Path(__file__).parent / "prompts" / "mj.md"


def presenter(personnage: Personnage) -> str:
    p = personnage
    return (f"{p.nom}, {p.parcours}. Motivation : {p.motivation}. Lien : {p.lien}. "
            f"Défaut : {p.defaut}.")


def prompt_systeme(univers: Univers, personnage: Personnage, scene: str = "") -> str:
    """Le prompt du MJ. `scene` : ce que le MJ sait de la situation en cours (lieu, PNJ présents…)."""
    gabarit = PROMPT.read_text(encoding="utf-8")
    return gabarit.format(univers=univers.nom, genre=univers.genre, cadre=univers.cadre,
                          personnage=presenter(personnage),
                          scene=f"\n## La scène\n\n{scene}\n" if scene else "").strip() + "\n"
