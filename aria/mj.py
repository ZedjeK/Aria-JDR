"""Le MJ : son prompt système, rempli avec l'univers, le personnage et la scène."""

from aria import chemins
from aria.personnage import Personnage
from aria.univers import Univers

PROMPT = chemins.PROMPTS / "mj.md"
MAGIE = chemins.PROMPTS / "magie.md"
INTERDITS = chemins.PROMPTS / "magie_interdite.md"


def presenter(personnage: Personnage) -> str:
    p = personnage
    return (f"{p.nom}, {p.sexe + ', ' if p.sexe else ''}{p.parcours}. Motivation : {p.motivation}. "
            f"Lien : {p.lien}. Défaut : {p.defaut}." + (f" Allure : {p.allure}" if p.allure else ""))


def _sort(sort) -> str:
    propriete = f", {sort.propriete.value}" if sort.propriete else ""
    return f"- {sort.nom} : {sort.effet.value}, {sort.puissance.value}{propriete}, {sort.cout} PM"


def presenter_magie(univers: Univers, personnage: Personnage) -> str:
    """Les règles des sorts, ceux que connaît le personnage, et ce que la magie ne fait pas (REGLES.md 10).
    Vide si l'univers n'a pas de magie."""
    if not (univers.magie_active and univers.domaines):
        return ""
    sorts = univers.sorts_connus(personnage.domaines)
    interdits = INTERDITS.read_text(encoding="utf-8").replace("# ", "### ", 1).strip()
    return MAGIE.read_text(encoding="utf-8").format(
        competence=univers.nom_affiche("Magie"), nom=personnage.nom,
        domaines=", ".join(personnage.domaines) or "aucun domaine",
        sorts="\n".join(_sort(s) for s in sorts if not s.improvisation) or "- aucun",
        improvisations="\n".join(_sort(s) for s in sorts if s.improvisation) or "- aucune",
        interdits=interdits)


def prompt_systeme(univers: Univers, personnage: Personnage, scene: str = "", memoire: str = "",
                   fil: str = "") -> str:
    """Le prompt du MJ. `scene` : ce que le MJ sait de la situation en cours (lieu, PNJ présents…) ;
    `memoire` : le bloc Mémoire de la campagne ; `fil` : ce que le moteur a gardé des échanges
    de la session sortis de la conversation."""
    gabarit = PROMPT.read_text(encoding="utf-8")
    return gabarit.format(univers=univers.nom, genre=univers.genre, cadre=univers.cadre,
                          personnage=presenter(personnage), magie=presenter_magie(univers, personnage),
                          memoire=f"\n## Ce dont tu te souviens\n\n{memoire}\n" if memoire else "",
                          scene=f"\n## La scène\n\n{scene}\n" if scene else "",
                          fil=f"\n## Plus tôt dans cette session\n\nLes premiers échanges de la session sont sortis "
                              f"de la conversation. Le moteur en a gardé les actions du joueur et les "
                              f"résultats :\n\n{fil}\n" if fil else "").strip() + "\n"
