"""Le MJ : son prompt système, rempli avec l'univers, le personnage et la scène."""

from aria import chemins
from aria.personnage import Personnage
from aria.univers import Univers

PROMPT = chemins.PROMPTS / "mj.md"


def presenter(personnage: Personnage) -> str:
    p = personnage
    return (f"{p.nom}, {p.parcours}. Motivation : {p.motivation}. Lien : {p.lien}. "
            f"Défaut : {p.defaut}.")


def prompt_systeme(univers: Univers, personnage: Personnage, scene: str = "", memoire: str = "",
                   fil: str = "") -> str:
    """Le prompt du MJ. `scene` : ce que le MJ sait de la situation en cours (lieu, PNJ présents…) ;
    `memoire` : le bloc Mémoire de la campagne ; `fil` : ce que le moteur a gardé des échanges
    de la session sortis de la conversation."""
    gabarit = PROMPT.read_text(encoding="utf-8")
    return gabarit.format(univers=univers.nom, genre=univers.genre, cadre=univers.cadre,
                          personnage=presenter(personnage),
                          memoire=f"\n## Ce dont tu te souviens\n\n{memoire}\n" if memoire else "",
                          scene=f"\n## La scène\n\n{scene}\n" if scene else "",
                          fil=f"\n## Plus tôt dans cette session\n\nLes premiers échanges de la session sont sortis "
                              f"de la conversation. Le moteur en a gardé les actions du joueur et les "
                              f"résultats :\n\n{fil}\n" if fil else "").strip() + "\n"
