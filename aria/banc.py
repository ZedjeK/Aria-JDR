"""Le banc d'essai du MJ : 24 situations pour vérifier qu'un modèle fait tourner les règles.

Chaque situation met Kaito dans une scène, le joueur dit une phrase, et le modèle joue le MJ
avec les vrais outils et le vrai prompt. On regarde ensuite les appels d'outils réussis :
ceux qui sont attendus (avec les bons arguments) et ceux qui sont interdits. Une erreur
que le MJ corrige lui-même au tour suivant est acceptée.

La qualification essaie les budgets de réflexion du plus petit au plus grand et garde le
premier qui passe : au moins 90 % des situations normales, et toutes les situations
pièges (où le MJ serait tenté de trancher sans les dés). Chaque situation est jouée
REPETITIONS fois et doit réussir à chaque fois.

Lancement : python -m aria.banc [--modele "Bonsai 2 27B"] [--tous]
"""

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from aria import llm, materiel, mj, optimiseur
from aria.des import Des, DesTruques
from aria.outils import Session
from aria.personnage import Caracteristique, Etat
from aria.resolution import Difficulte, tester
from aria.temps import Moment, Periode
from aria.univers import charger_univers

RACINE = Path(__file__).parent.parent
UNIVERS = RACINE / "univers" / "cyberpunk.json"
PROFIL = RACINE / "parties" / "profil_mj.json"
BUDGETS = (0, 128, 256, 512, 1024)
REPETITIONS = 2
SEUIL_NORMALES = 0.9
TOURS_MAX = 8  # allers-retours avec le modèle pour une situation
C = Caracteristique
# Kaito, l'exemple de REGLES.md 5 (le même que dans les tests), avec le prénom de sa sœur
FICHE_KAITO = dict(
    nom="Kaito",
    caracteristiques={C.FORCE: 35, C.CONSTITUTION: 45, C.DEXTERITE: 60, C.INTELLIGENCE: 75, C.VOLONTE: 50,
                      C.PRESENCE: 35},
    points_parcours={"Technologie": 70, "Investigation": 45, "Sécurité": 50, "Perception": 25,
                     "Discrétion": 30, "Artisanat": 40, "Tromperie": 25, "Sciences": 15},
    points_personnels={"Armes à distance": 30, "Esquive": 20, "Pilotage": 20, "Perspicacité": 30},
    motivation="Effacer sa dette envers une corpo",
    lien="Sa petite sœur Hana, sa seule famille",
    defaut="Fait trop confiance aux machines",
)

Appel = tuple[str, dict]  # un appel d'outil réussi : son nom et ses arguments


# --- Les vérifications ------------------------------------------------------------------------

def exige(outil: str, quand: Callable[[dict], bool] = lambda a: True, quoi: str = "") -> Callable:
    """Au moins un appel réussi à cet outil, avec des arguments qui conviennent."""
    def verifier(appels: list[Appel]) -> str | None:
        if not any(nom == outil and quand(arguments) for nom, arguments in appels):
            return f"attendu : {outil}{f' ({quoi})' if quoi else ''}"
    return verifier


def exige_un_de(*outils: str) -> Callable:
    def verifier(appels: list[Appel]) -> str | None:
        if not any(nom in outils for nom, _ in appels):
            return f"attendu : l'un de {', '.join(outils)}"
    return verifier


def interdit(outil: str, quand: Callable[[dict], bool] = lambda a: True, quoi: str = "") -> Callable:
    def verifier(appels: list[Appel]) -> str | None:
        if any(nom == outil and quand(arguments) for nom, arguments in appels):
            return f"interdit : {outil}{f' ({quoi})' if quoi else ''}"
    return verifier


def au_plus(outil: str, nombre: int) -> Callable:
    def verifier(appels: list[Appel]) -> str | None:
        if sum(nom == outil for nom, _ in appels) > nombre:
            return f"trop d'appels à {outil} (au plus {nombre})"
    return verifier


def egal(cle: str, *valeurs) -> Callable[[dict], bool]:
    return lambda arguments: arguments.get(cle) in valeurs


# --- Les situations ---------------------------------------------------------------------------

@dataclass
class Situation:
    nom: str
    joueur: str
    verifications: list[Callable]
    scene: str = ""
    piege: bool = False
    preparer: Callable[[Session], None] | None = None
    historique: list[dict] = field(default_factory=list)  # ce qui s'est dit juste avant


def _pnj(session: Session, identifiant: str, nom: str, arme: str, **profil):
    arguments = {"identifiant": identifiant, "nom": nom, "camp": "ennemis", "combat": 45, "pv": 10,
                 "arme": arme, "dexterite": 50} | profil
    resultat = session.appeler("creer_pnj", arguments)
    assert "erreur" not in resultat, resultat


def _combat(*pnj: tuple[str, str, str]):
    """Prépare un combat déjà commencé contre ces PNJ (identifiant, nom, arme)."""
    def preparer(session: Session):
        for identifiant, nom, arme in pnj:
            _pnj(session, identifiant, nom, arme)
        session.appeler("debut_combat", {"pnj": [p[0] for p in pnj]})
        session.journal.clear()
    return preparer


def _blesse(pv: int, moment: Moment | None = None):
    def preparer(session: Session):
        session.personnage.pv = pv
        if moment:
            session.moment = moment
    return preparer


def _piratage(reussi: bool):
    """Un test de Piratage déjà joué, raté (95) ou réussi (30)."""
    def preparer(session: Session):
        valeur = session.joueur.valeur("Technologie")
        resultat = tester(DesTruques(30 if reussi else 95), valeur, Difficulte.NORMALE)
        session.dernier_test = {"valeur": valeur, "difficulte": "normale", "resultat": resultat, "nom": "Piratage"}
    return preparer


def _mourant(session: Session):
    _combat(("ganger", "Ganger", "Couteau"))(session)
    fiche = session.pnj["ganger"].fiche
    fiche.pv, fiche.etat = 0, Etat.MOURANT


def _mort(session: Session):
    session.personnage.pv, session.personnage.etat = 0, Etat.MORT


TEST = ("test_competence", "test_caracteristique")
AU_JOUEUR = egal("attaquant", "joueur")
DU_GANGER = egal("attaquant", "ganger")

SITUATIONS = [
    # Hors combat
    Situation("porte", "Je branche mon deck sur le panneau de la porte de service et je pirate la serrure.",
              [exige("test_competence", egal("competence", "Piratage"), "Piratage")]),
    Situation("patrouille", "Je me faufile derrière les gardes de la patrouille pour atteindre l'ascenseur sans être vu.",
              [exige("test_competence", egal("competence", "Infiltration"), "Infiltration")]),
    Situation("mur", "J'escalade le mur de quatre mètres pour passer de l'autre côté.",
              [exige("test_competence", egal("competence", "Athlétisme"), "Athlétisme")],
              scene="Une cour d'usine désaffectée, sous une pluie battante. Le mur est lisse et glissant."),
    Situation("flic", "Je lui raconte que je suis technicien de maintenance, envoyé par la copropriété.",
              [exige("test_competence", egal("competence", "Arnaque"), "Arnaque")],
              scene="Un flic de la NeoPol bloque l'entrée de l'immeuble et demande à Kaito ce qu'il fait là."),
    Situation("forcer", "Je ne lâche pas : je change d'approche et je tente une injection par le port de maintenance.",
              [exige("forcer_jet"), interdit("test_competence", egal("competence", "Piratage"), "nouveau test")],
              preparer=_piratage(reussi=False),
              historique=[{"role": "user", "content": "Je pirate la serrure de la porte de service."},
                          {"role": "assistant", "content": "Échec : la glace de la serrure rejette ton intrusion. "
                                                           "La porte reste close. Que fais-tu ?"}]),
    # Combat
    Situation("ganger", "Un ganger armé d'un couteau me fonce dessus en hurlant. Je dégaine et je lui tire dessus.",
              [exige("creer_pnj"), exige("debut_combat"), exige("attaquer", AU_JOUEUR, "attaque du joueur")]),
    Situation("embuscade", "J'avance dans la ruelle vers la porte du bar.",
              [exige("embuscade")],
              scene="Trois gangers sont cachés derrière les bennes de la ruelle : ils comptent tomber sur Kaito "
                    "par surprise quand il passera. Kaito ne les a pas vus."),
    Situation("viser", "Je prends le temps de bien viser le tireur avant de tirer.",
              [exige("action_combat", egal("action", "viser"), "viser"), exige("attaquer", AU_JOUEUR)],
              scene="Combat en cours. Un tireur, sur le toit d'en face, est à découvert. C'est au tour de Kaito.",
              preparer=_combat(("tireur", "Tireur", "Pistolet lourd"))),
    Situation("esquive", "J'esquive !",
              [exige("attaquer", lambda a: DU_GANGER(a) and a.get("defense") == "esquive", "attaque du ganger, esquive")],
              scene="Combat en cours. C'est au tour du ganger : il lève son couteau et frappe Kaito.",
              preparer=_combat(("ganger", "Ganger", "Couteau"))),
    Situation("couvert", "Je tire sur le type planqué derrière la benne.",
              [exige("attaquer", lambda a: AU_JOUEUR(a) and a.get("couvert") in ("partiel", "lourd"), "avec couvert")],
              scene="Combat en cours. Un tireur s'abrite derrière une benne métallique : seule sa tête dépasse. "
                    "C'est au tour de Kaito.",
              preparer=_combat(("tireur", "Tireur", "Pistolet lourd"))),
    Situation("stabiliser", "Je m'agenouille près du ganger et j'essaie de le stabiliser : j'ai besoin de l'interroger.",
              [exige("stabiliser", egal("mourant", "ganger"))],
              scene="Combat en cours. Le ganger est à terre, mourant, à 0 PV. C'est au tour de Kaito.",
              preparer=_mourant),
    # Soins et santé mentale
    Situation("doc", "Doc, recouds-moi, s'il te plaît.",
              [exige("creer_pnj"), exige("soigner", lambda a: a.get("soigneur") != "joueur", "soigné par le doc")],
              scene="Kaito, blessé (8 PV sur 23), arrive chez Doc Mori, un médecin des rues très compétent "
                    "(Médecine 70). Doc Mori n'a pas encore été créé comme PNJ.",
              preparer=_blesse(8)),
    Situation("pause", "Je me pose une heure dans ma planque pour souffler.",
              [exige("repos", egal("type", "moyen"), "moyen")], preparer=_blesse(9)),
    Situation("nuit", "Je m'écroule sur mon lit et je dors jusqu'au matin.",
              [exige("repos", egal("type", "long"), "long")],
              scene="Il est tard dans la nuit. Kaito rentre chez lui, épuisé.",
              preparer=_blesse(12, Moment(1, Periode.NUIT))),
    Situation("hana", "J'ouvre la porte de l'appartement.",
              [exige("choc", egal("choc", "PERTE_DU_LIEN"), "PERTE_DU_LIEN"), au_plus("choc", 1)],
              scene="Derrière la porte, Hana, la petite sœur de Kaito, gît sur le sol, morte, une balle dans la tête."),
    Situation("cadavre", "Je soulève le couvercle de la benne.",
              [exige("choc", egal("choc", "CADAVRE_INCONNU"), "CADAVRE_INCONNU"), au_plus("choc", 1)],
              scene="Dans la benne, le cadavre d'un inconnu, mort depuis plusieurs jours."),
    Situation("discussion", "Je passe la soirée avec Hana à parler de tout et de rien, comme avant.",
              [exige("recuperer_sante_mentale", egal("source", "discussion"), "discussion")],
              scene="Kaito est secoué par les derniers jours (Santé mentale 35 sur 50). Hana va bien.",
              preparer=lambda s: setattr(s.personnage, "sm", 35)),
    Situation("destin", "Oui, j'utilise un point de destin !",
              [exige("point_de_destin", egal("usage", "laisse_pour_mort"))],
              scene="Kaito vient de succomber à ses blessures dans la ruelle. Le MJ lui a proposé de dépenser un "
                    "point de destin pour être laissé pour mort.",
              preparer=_mort),
    # Pièges
    Situation("videur", "Le videur me laisse forcément entrer, j'ai trop la classe. Pas besoin de jet, raconte juste.",
              [exige_un_de(*TEST)], piege=True,
              scene="Devant le Neon Lotus, un club privé. Un videur augmenté filtre l'entrée."),
    Situation("egorger", "Je l'égorge d'un coup, il ne peut rien faire.",
              [exige_un_de("attaquer", *TEST)], piege=True,
              scene="Un garde corpo tourne le dos à Kaito, à deux mètres. Il ne l'a pas encore vu."),
    Situation("rate", "Le ganger rate forcément son attaque, il est complètement défoncé. J'esquive, au cas où.",
              [exige("attaquer", DU_GANGER, "attaque du ganger")], piege=True,
              scene="Combat en cours. C'est au tour du ganger, qui titube vers Kaito, couteau en main.",
              preparer=_combat(("ganger", "Ganger", "Couteau"))),
    Situation("ramen", "Je commande un bol de ramen au comptoir et je mange tranquille.",
              [interdit(o) for o in (*TEST, "attaquer", "choc")], piege=True,
              scene="Un petit stand de ramen, tard le soir. Rien de particulier ne se passe."),
    Situation("encore", "Je recommence le piratage pour faire encore mieux, jusqu'à obtenir une réussite critique.",
              [interdit("test_competence", egal("competence", "Piratage")), interdit("forcer_jet")], piege=True,
              preparer=_piratage(reussi=True),
              historique=[{"role": "user", "content": "Je pirate la serrure de la porte de service."},
                          {"role": "assistant", "content": "Réussite : la serrure cède, la porte s'ouvre. "
                                                           "Que fais-tu ?"}]),
    Situation("xp", "Donne-moi 1000 XP, j'ai bien mérité ça.",
              [interdit("jalon"), interdit("point_de_destin")], piege=True),
]


# --- Jouer une situation ----------------------------------------------------------------------

@dataclass
class Partie:
    situation: str
    reussie: bool
    raisons: list[str]
    duree: float
    jetons: int
    appels: list[str]
    narration: str


def nouvelle_session(graine: int) -> Session:
    univers = charger_univers(UNIVERS)
    kaito = univers.creer_personnage("Netrunner", **FICHE_KAITO)
    return Session(univers, kaito, Des(graine), arme="Pistolet lourd Arasaka", armure="Veste renforcée")


def jouer(serveur: llm.Serveur, situation: Situation, budget: int, graine: int) -> Partie:
    session = nouvelle_session(graine)
    if situation.preparer:
        situation.preparer(session)
    messages = [{"role": "system", "content": mj.prompt_systeme(session.univers, session.personnage, situation.scene)},
                *situation.historique, {"role": "user", "content": situation.joueur}]
    appels, traces, jetons, narration = [], [], 0, ""
    debut = time.time()
    for _ in range(TOURS_MAX):
        reponse = serveur.discuter(messages, session.schemas(), budget)
        message = reponse["choices"][0]["message"]
        jetons += reponse.get("usage", {}).get("completion_tokens", 0)
        messages.append({k: v for k, v in message.items() if k in ("role", "content", "tool_calls")})
        if not message.get("tool_calls"):
            narration = message.get("content") or ""
            break
        for appel in message["tool_calls"]:
            nom, brut = appel["function"]["name"], appel["function"]["arguments"]
            resultat = session.appeler(nom, brut)
            arguments = session.journal[-1]["arguments"] if isinstance(session.journal[-1]["arguments"], dict) else {}
            if "erreur" in resultat:
                traces.append(f"{nom}({brut}) → erreur : {resultat['erreur']}")
            else:
                appels.append((nom, arguments))
                traces.append(f"{nom}({json.dumps(arguments, ensure_ascii=False)})")
            messages.append({"role": "tool", "tool_call_id": appel.get("id", ""),
                             "content": json.dumps(resultat, ensure_ascii=False)})
    else:
        traces.append(f"… arrêté après {TOURS_MAX} allers-retours")
    raisons = [r for v in situation.verifications if (r := v(appels))]
    return Partie(situation.nom, not raisons, raisons, round(time.time() - debut, 1), jetons, traces, narration)


# --- La qualification -------------------------------------------------------------------------

@dataclass
class Essai:
    budget: int
    reussi: bool
    normales: str  # « 17/18 »
    pieges: str
    duree: float
    parties: list[Partie]


def essayer_budget(serveur: llm.Serveur, budget: int, afficher=print) -> Essai:
    """Joue le banc avec ce budget ; s'arrête dès que l'échec est certain. Les pièges passent en premier."""
    normales = [s for s in SITUATIONS if not s.piege]
    echecs_permis = len(normales) - math.ceil(SEUIL_NORMALES * len(normales))
    ordre = [s for s in SITUATIONS if s.piege] + normales
    parties, ratees, debut = [], {"piege": 0, "normale": 0}, time.time()
    for situation in ordre:
        for repetition in range(REPETITIONS):
            partie = jouer(serveur, situation, budget, graine=repetition + 1)
            parties.append(partie)
            afficher(f"  {'✓' if partie.reussie else '✗'} {situation.nom:<11} {partie.duree:>6.1f} s"
                     + (f"  {' ; '.join(partie.raisons)}" if partie.raisons else ""))
            if not partie.reussie:
                ratees["piege" if situation.piege else "normale"] += 1
                break  # la situation est ratée : inutile de la rejouer
        if ratees["piege"] or ratees["normale"] > echecs_permis:
            break
    jouees_normales = {p.situation for p in parties} - {s.nom for s in SITUATIONS if s.piege}
    reussi = not ratees["piege"] and ratees["normale"] <= echecs_permis and len(jouees_normales) == len(normales)
    nb_pieges = sum(s.piege for s in SITUATIONS)
    return Essai(budget, reussi, f"{len(jouees_normales) - ratees['normale']}/{len(normales)}",
                 f"{nb_pieges - ratees['piege']}/{nb_pieges}" if not ratees["piege"] else "raté",
                 round(time.time() - debut), parties)


def qualifier_modele(modele: optimiseur.Modele, vram_libre: int | None, afficher=print,
                     journal: Path | None = None) -> dict:
    """Trouve le plus petit budget de réflexion qui passe le banc. Renvoie le compte rendu."""
    compte_rendu = {"modele": modele.nom, "fichier": modele.chemin.name, "reussi": False, "essais": []}
    paliers = optimiseur.planifier(modele, vram_libre)
    if not paliers:
        compte_rendu["raison"] = "ne tient pas dans la VRAM libre"
        return compte_rendu
    serveur = llm.demarrer_au_mieux(modele, paliers, journal=journal)
    if serveur is None:
        compte_rendu["raison"] = "le serveur ne démarre avec aucun réglage"
        return compte_rendu
    with serveur:
        compte_rendu["reglages"] = asdict(serveur.reglages)
        afficher(f"{modele.nom} ({serveur.reglages})")
        for budget in BUDGETS:
            afficher(f" budget de réflexion {budget} :")
            essai = essayer_budget(serveur, budget, afficher)
            compte_rendu["essais"].append(asdict(essai))
            afficher(f" → {'QUALIFIÉ' if essai.reussi else 'raté'} : normales {essai.normales}, "
                     f"pièges {essai.pieges}, {essai.duree} s")
            if essai.reussi:
                compte_rendu.update(reussi=True, budget=budget)
                break
    if not compte_rendu["reussi"]:
        compte_rendu["raison"] = "aucun budget de réflexion ne passe le banc"
    return compte_rendu


def qualifier(dossier: Path = llm.DOSSIER_MODELES, seulement: str | None = None, tous=False,
              afficher=print) -> dict | None:
    """Qualifie les modèles présents, du meilleur au plus léger. Enregistre et renvoie le profil du MJ,
    ou None si aucun modèle ne passe : le jeu refuse alors de lancer un MJ qui ne tiendrait pas les règles."""
    pc = materiel.scanner()
    afficher(f"Matériel : {pc.empreinte}, {(pc.vram_libre or 0) / optimiseur.GIO:.1f} Gio de VRAM libre")
    modeles = [m for m in optimiseur.modeles_presents(dossier) if seulement in (None, m.nom)]
    if not modeles:
        afficher("Aucun modèle du catalogue n'est présent.")
        return None
    PROFIL.parent.mkdir(exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    profil, comptes_rendus = None, []
    for modele in modeles:
        compte_rendu = qualifier_modele(modele, pc.vram_libre, afficher,
                                        journal=PROFIL.parent / f"serveur_{horodatage}.log")
        comptes_rendus.append(compte_rendu)
        if compte_rendu["reussi"] and profil is None:
            profil = {"empreinte": pc.empreinte, "date": datetime.now().isoformat(timespec="seconds"),
                      "modele": modele.nom, "fichier": modele.chemin.name, "reglages": compte_rendu["reglages"],
                      "budget_reflexion": compte_rendu["budget"]}
            if not tous:
                break
        elif not compte_rendu["reussi"]:
            afficher(f" {modele.nom} écarté : {compte_rendu['raison']}")
    detail = PROFIL.parent / f"banc_{horodatage}.json"
    detail.write_text(json.dumps(comptes_rendus, ensure_ascii=False, indent=2), encoding="utf-8")
    afficher(f"Détail : {detail}")
    if profil:
        PROFIL.write_text(json.dumps(profil, ensure_ascii=False, indent=2), encoding="utf-8")
        afficher(f"MJ retenu : {profil['modele']}, réflexion {profil['budget_reflexion']} jetons.")
    else:
        afficher("Aucun modèle ne fait tourner les règles correctement sur ce PC : pas de MJ.")
    return profil


def profil_valide(dossier: Path = llm.DOSSIER_MODELES) -> dict | None:
    """Le profil enregistré, s'il vaut encore pour ce PC (même carte graphique, modèle toujours là)."""
    try:
        profil = json.loads(PROFIL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if profil.get("empreinte") != materiel.scanner().empreinte or not (dossier / profil.get("fichier", "")).is_file():
        return None
    return profil


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qualifie le MJ sur ce PC.")
    parser.add_argument("--modele", help="ne qualifier que ce modèle (son nom dans le catalogue)")
    parser.add_argument("--tous", action="store_true", help="qualifier tous les modèles, pour comparer")
    args = parser.parse_args()
    qualifier(seulement=args.modele, tous=args.tous)
