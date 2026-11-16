"""Le MJ : son prompt système, rempli avec l'univers, le personnage et la scène."""

from aria import chemins
from aria.personnage import Personnage
from aria.univers import Univers

PROMPT = chemins.PROMPTS / "mj.md"
MAGIE = chemins.PROMPTS / "magie.md"
INTERDITS = chemins.PROMPTS / "magie_interdite.md"
ECONOMIE = chemins.PROMPTS / "economie.md"
MONDE = chemins.PROMPTS / "monde.md"
ALEATOIRE = chemins.PROMPTS / "aleatoire.md"
OUTILS = chemins.PROMPTS / "outils.md"
COMBAT_CLASSIQUE = chemins.PROMPTS / "combat_classique.md"


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


def presenter_economie(univers: Univers, personnage: Personnage) -> str:
    """Les règles de l'argent et du matériel (REGLES.md 13). Vide pour un personnage d'avant l'économie."""
    if personnage.inventaire is None:
        return ""
    return ECONOMIE.read_text(encoding="utf-8").format(monnaie=univers.monnaie)


def presenter_familles(ouvertes: list[str], fermees: dict[str, str]) -> str:
    """La section « Tes outils » : les familles sous la main, et celles que le MJ peut ouvrir avec ce qu'elles
    contiennent (voir aria.familles)."""
    lignes = "\n".join(f"- {famille} : {contenu} ;" for famille, contenu in fermees.items())
    return OUTILS.read_text(encoding="utf-8").format(
        ouvertes=", ".join(ouvertes) if ouvertes else "aucune pour l'instant",
        fermees=f"Fermées :\n{lignes[:-2]}." if fermees else "Fermées : aucune.")


def prompt_systeme(univers: Univers, personnage: Personnage, scene: str = "", memoire: str = "",
                   fil: str = "", monde: bool = False, aleatoire: bool = False,
                   familles: tuple[list[str], dict[str, str]] | None = None, combat_classique: bool = True) -> str:
    """Le prompt du MJ. `scene` : ce que le MJ sait de la situation en cours (lieu, PNJ présents…) ;
    `memoire` : le bloc Mémoire de la campagne ; `fil` : ce que le moteur a gardé des échanges
    de la session sortis de la conversation. `combat_classique` : les lignes de pilotage d'un combat mené par le
    MJ (attaquer, fin_de_tour…) ; faux quand le code mène les combats à pied (REGLES.md 7.8)."""
    gabarit = PROMPT.read_text(encoding="utf-8")
    return gabarit.format(univers=univers.nom, genre=univers.genre, cadre=univers.cadre,
                          combat=COMBAT_CLASSIQUE.read_text(encoding="utf-8") if combat_classique else "",
                          personnage=presenter(personnage), magie=presenter_magie(univers, personnage),
                          economie=presenter_economie(univers, personnage)
                          + (MONDE.read_text(encoding="utf-8") if monde else "")
                          + (ALEATOIRE.read_text(encoding="utf-8") if aleatoire else "")
                          + (presenter_familles(*familles) if familles else ""),
                          memoire=f"\n## Ce dont tu te souviens\n\n{memoire}\n" if memoire else "",
                          scene=f"\n## La scène\n\n{scene}\n" if scene else "",
                          fil=f"\n## Plus tôt dans cette session\n\nLes premiers échanges de la session sont sortis "
                              f"de la conversation. Le moteur en a gardé les actions du joueur et les "
                              f"résultats :\n\n{fil}\n" if fil else "").strip() + "\n"
