"""Le générateur d'univers (REGLES.md 1.3) : une campagne ne crée rien de zéro.

1. Le joueur choisit le genre, le cadre et les réglages ; ils sont préremplis par genre.
2. Le filtre de la bibliothèque ne garde que ce qui a droit au genre et à la magie.
3. Le générateur pioche dedans ; plus tard, le LLM adaptera les noms au cadre, et le code
   vérifiera ses propositions.
4. L'univers est écrit dans le dossier de la campagne : une copie figée, que l'évolution de
   la bibliothèque ne touche plus.

Lot 1 : sans LLM. L'univers garde les noms de la bibliothèque.
"""

import json
from dataclasses import dataclass, replace

from aria.bibliotheque import GENRES, Bibliotheque, charger
from aria.campagne import Campagne
from aria.reglages import Curseur
from aria.sante_mentale import Choc
from aria.univers import Univers, charger_univers, univers_depuis_dict

ACTIVEE, DESACTIVEE, OPTION = "activée", "désactivée", "option"
NOM_MAX = 60
CADRE_MAX = 400


class ChoixInvalide(ValueError):
    """Les choix du joueur ne respectent pas les règles du genre. `erreurs` les liste tous."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("Choix invalides :\n- " + "\n- ".join(erreurs))


@dataclass(frozen=True)
class Choix:
    """Ce que le joueur choisit pour sa campagne."""

    genre: str
    nom: str
    cadre: str = ""
    magie: bool = False
    curseur: str = Curseur.STANDARD.value
    monde_impitoyable: bool = False
    chocs_banals: tuple[str, ...] = ()


def choix_par_defaut(bibliotheque: Bibliotheque, genre: str, nom: str = "", cadre: str = "") -> Choix:
    """Les réglages préremplis du genre (REGLES.md 1.2) : le joueur peut ensuite tout changer,
    sauf la magie là où le genre l'impose."""
    if genre not in bibliotheque.genres:
        raise ChoixInvalide([f"Genre inconnu : « {genre} ». Genres : {', '.join(GENRES)}."])
    fiche = bibliotheque.genres[genre]
    reglages = fiche["reglages"]
    return Choix(genre, nom or genre, cadre, fiche["magie"]["statut"] == ACTIVEE, reglages["curseur"],
                 reglages["monde_impitoyable"], tuple(reglages["chocs_banals"]))


def verifier_choix(bibliotheque: Bibliotheque, choix: Choix) -> list[str]:
    if choix.genre not in bibliotheque.genres:
        return [f"Genre inconnu : « {choix.genre} »."]
    erreurs = []
    if not choix.nom.strip() or len(choix.nom) > NOM_MAX:
        erreurs.append(f"Le nom de l'univers : de 1 à {NOM_MAX} caractères.")
    if len(choix.cadre) > CADRE_MAX:
        erreurs.append(f"Le cadre : {CADRE_MAX} caractères au plus.")
    statut = bibliotheque.genres[choix.genre]["magie"]["statut"]
    if statut == DESACTIVEE and choix.magie:
        erreurs.append(f"Pas de magie en {choix.genre}.")
    if statut == ACTIVEE and not choix.magie:
        erreurs.append(f"La magie fait partie du genre {choix.genre} : elle reste activée.")
    if choix.curseur not in {c.value for c in Curseur}:
        erreurs.append(f"Curseur inconnu « {choix.curseur} ».")
    erreurs += [f"Choc inconnu « {c} »." for c in choix.chocs_banals if c not in Choc.__members__]
    return erreurs


def generer(bibliotheque: Bibliotheque, choix: Choix) -> dict:
    """Le JSON de l'univers, composé depuis la bibliothèque et vérifié par le moteur.
    Lève ChoixInvalide, ou UniversInvalide si l'univers composé enfreint les règles."""
    erreurs = verifier_choix(bibliotheque, choix)
    if erreurs:
        raise ChoixInvalide(erreurs)
    donnees = bibliotheque.composer(choix.genre, choix.magie, choix.nom.strip(), choix.cadre.strip(), choix.curseur,
                                    choix.monde_impitoyable, list(choix.chocs_banals))
    univers_depuis_dict(donnees)  # le moteur vérifie tout avant qu'on l'écrive
    return donnees


def creer_campagne(campagne: Campagne, choix: Choix, bibliotheque: Bibliotheque | None = None) -> Univers:
    """Génère l'univers et l'écrit dans le dossier de la campagne. C'est une copie figée : on ne
    l'écrase jamais (lève FileExistsError si la campagne a déjà son univers)."""
    if campagne.univers.exists():
        raise FileExistsError(f"La campagne a déjà son univers : {campagne.univers}")
    donnees = generer(bibliotheque or charger(), choix)
    campagne.dossier.mkdir(parents=True, exist_ok=True)
    temporaire = campagne.univers.with_suffix(".tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporaire.replace(campagne.univers)
    return charger_univers(campagne.univers)


def avec(choix: Choix, **changements) -> Choix:
    """Le joueur change un réglage prérempli."""
    return replace(choix, **changements)
