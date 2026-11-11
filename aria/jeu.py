"""Démo v2 : la ruelle de Néo-Tokyo, en texte libre, avec le MJ LLM.

Tu écris ce que fait Kaito ; le MJ (le modèle qualifié par le banc) appelle le moteur et
raconte. Chaque jet s'affiche avant la narration : tu vois toujours ce que disent les dés.
Commandes : « etat » pour ta fiche, « quitter » pour finir la session.

Tout ce qui concerne la campagne (sauvegarde, mémoire, fiche du combat en cours) est
rangé dans son dossier : ~/.Aria-JDR/neo-tokyo-kaito/. Au lancement suivant, la campagne reprend
là où on l'a laissée.

Lancement (après le banc, qui choisit le modèle) :
    .venv\\Scripts\\python.exe -m aria.jeu
Une autre campagne, dans un univers généré depuis la bibliothèque :
    .venv\\Scripts\\python.exe -m aria.jeu --campagne ma-campagne --genre Cyberpunk --cadre "Osaka, 2091"
"""

import argparse
import sys

from aria import banc, banc_generateur, chemins, generateur, llm, optimiseur, outils, progression
from aria.campagne import Campagne
from aria.compte_rendu import decrire
from aria.des import Des
from aria.outils import Session
from aria.personnage import Etat
from aria.sauvegarde import Partie, charger, sauvegarder
from aria.table import Table
from aria.temps import Moment, Periode
from aria.univers import charger_univers

CAMPAGNE = "neo-tokyo-kaito"
JOURNAL_SERVEUR = chemins.DONNEES / "serveur_jeu.log"
QUITTER = ("quitter", "/quitter")
ETAT = ("etat", "état", "/etat")
# Ce que le MJ sait de la scène. Le joueur, lui, ne voit que la narration.
# La ruelle de la démo v1 ouvre la campagne ; le quartier reste, d'une session à l'autre.
EMBUSCADE = (
    "Jour 1, fin d'après-midi. La pluie fait grésiller les néons. Kaito coupe par une ruelle pour rentrer "
    "à sa planque, son pistolet lourd Arasaka sous sa veste renforcée.\n\n"
    "Deux gangers l'attendent, cachés, pour le dépouiller (leur Discrétion : 45) :\n"
    "- un ganger au couteau, nerveux (combat 45, 10 PV, Couteau, dextérité 55) ;\n"
    "- un tireur, planqué derrière une voiture (combat 40, 9 PV, Pistolet lourd, dextérité 50).\n"
    "Ils ne se battent pas jusqu'à la mort : blessés ou en mauvaise posture, ils fuient ou se rendent.\n\n"
)
QUARTIER = (
    "Dans le quartier : une vendeuse de ramen au coin de la rue (Médecine 40), Doc Mori, le charcudoc "
    "(Médecine 70), et la planque de Kaito, où il peut appeler Hana."
)
SCENE = EMBUSCADE + QUARTIER
# À « quitter », le MJ range la scène en cours dans la mémoire avant la sauvegarde
FIN_DE_SESSION = ("[Fin de session] Le joueur s'arrête là. Si un combat est en cours, termine-le avec fin_combat. "
                  "Sinon, si la scène en cours a compté, appelle fin_scene. Mets à jour les PNJ et les fils "
                  "si besoin. Ne raconte rien.")


NETRUNNER = "Netrunner"  # le parcours de Kaito, gardé dans tout univers généré tant que la création de perso n'existe pas


class SansPersonnage(Exception):
    """Pas encore de création de personnage : seul Kaito, le Netrunner, peut jouer."""


class Jeu:
    def __init__(self, serveur: llm.Serveur, budget: int | None, contexte: int = optimiseur.CONTEXTE_CIBLE,
                 des: Des | None = None, entree=input, sortie=print, campagne: Campagne | None = None,
                 choix: "generateur.Choix | None" = None, budget_generation: int | None = None):
        """`choix` : pour une nouvelle campagne, l'univers à générer. Sans choix, une campagne qui n'a pas
        encore d'univers prend Néo-Tokyo, l'univers étalon du banc."""
        self.entree, self.dire = entree, sortie
        self.campagne = campagne or Campagne.nommee(CAMPAGNE)
        self.campagne.ouvrir()
        self.reprise = self.campagne.sauvegarde.is_file()
        if self.reprise:
            # La campagne continue : Kaito tel qu'on l'a laissé, et le quartier sans l'embuscade
            partie = charger(self.campagne.sauvegarde)
            self.session = Session(partie.univers, partie.personnage, des or Des(), partie.moment,
                                   arme=partie.arme_en_main, armure=partie.armure, vehicule=partie.vehicule,
                                   campagne=self.campagne)
        else:
            if self.campagne.univers.is_file():
                univers = charger_univers(self.campagne.univers)
            elif choix:
                generation = budget if budget_generation is None else budget_generation
                univers, adaptation = generateur.creer_campagne(self.campagne, choix, serveur=serveur, budget=generation,
                                                                gardes={NETRUNNER})
                self.montrer_adaptation(univers, adaptation)
            else:
                univers = charger_univers(banc.UNIVERS)
            local = univers.nom_local  # le parcours et l'équipement de Kaito, sous les noms de cet univers
            if local(NETRUNNER) not in univers.parcours:
                raise SansPersonnage(f"{univers.nom} n'a pas de Netrunner pour Kaito : la création de personnage "
                                     "arrive à l'étape suivante.")
            kaito = univers.creer_personnage(local(NETRUNNER), **banc.FICHE_KAITO)
            depart = {cle: local(v) if isinstance(v, str) else v for cle, v in banc.EQUIPEMENT_KAITO.items()}
            univers.equiper(kaito, **depart)
            self.session = Session(univers, kaito, des or Des(), Moment(1, Periode.APRES_MIDI),
                                   arme=local("Pistolet lourd Arasaka"), armure=local("Veste renforcée"),
                                   campagne=self.campagne)
        self.table = Table(serveur, self.session, budget, QUARTIER if self.reprise else SCENE, contexte=contexte)

    def montrer_adaptation(self, univers, adaptation: "generateur.Adaptation | None"):
        """Ce que le MJ a adapté au cadre, avant la première scène."""
        self.dire(f"\nUnivers créé : {univers.nom}" + (f" — {univers.cadre}" if univers.cadre else ""))
        if adaptation is None:
            return
        a = adaptation
        for categorie, retires in a.retraits_epoque.items():
            self.dire(f"  Apparus après {a.annee}, {generateur.CATEGORIES[categorie]} : {', '.join(retires)}")
        for categorie, retires in a.retraits.items():
            self.dire(f"  Retirés, {generateur.CATEGORIES[categorie]} : {', '.join(retires)}")
        for categorie, renommages in a.renommages.items():
            self.dire(f"  {generateur.CATEGORIES[categorie].capitalize()} : "
                      + ", ".join(f"{x} → {n}" for x, n in renommages.items()))
        if a.parcours_retires:
            self.dire(f"  Parcours retirés : {', '.join(a.parcours_retires)}")
        if a.parcours_renommes:
            self.dire("  Parcours renommés : " + ", ".join(f"{x} → {n}" for x, n in a.parcours_renommes.items()))
        for p in a.parcours_ajoutes:
            self.dire(f"  Nouveau parcours : {p['nom']} — {p['description']}")
        if not (a.retraits_epoque or a.retraits or a.renommages or a.parcours_retires or a.parcours_renommes
                or a.parcours_ajoutes):
            self.dire("  La bibliothèque colle au cadre : rien n'a changé.")
        for refus in adaptation.refus:
            self.dire(f"  (écarté : {refus})")

    def mort(self) -> bool:
        k = self.session.personnage
        return k.etat is Etat.MORT and k.points_destin == 0

    def jouer(self):
        k, u = self.session.personnage, self.session.univers
        if self.mort():
            self.dire(f"Kaito est mort. Pour une nouvelle campagne, supprime le dossier {self.campagne.dossier}.")
            return
        self.dire(f"=== {u.nom} ===\n{u.cadre}")
        if self.reprise:
            self.dire(f"\nReprise de la campagne : {self.session.moment}.")
        self.dire(f"\nTu es {k.nom}, netrunner. {k.pv}/{k.pv_max} PV, {k.sm} en Santé mentale, "
                  f"{k.points_destin} points de destin.")
        self.dire(f"Motivation : {k.motivation}. Lien : {k.lien}. Défaut : {k.defaut}.")
        self.dire("Écris ce que fait Kaito. « etat » : ta fiche ; « quitter » : fin de la session.")
        self.raconter(lambda: self.table.ouvrir(reprise=self.reprise))
        while True:
            phrase = self.entree("\n> ").strip()
            if not phrase:
                continue
            if phrase.lower() in QUITTER:
                break
            if phrase.lower() in ETAT:
                self.afficher_etat()
                continue
            self.raconter(lambda: self.table.tour(phrase))
            self.sauvegarder()  # à chaque action : une coupure ne fait jamais perdre la partie
            if self.mort():
                self.dire("\nKaito est mort dans les rues de Néo-Tokyo. Fin de la partie.")
                return
        self.fin_de_session()

    def raconter(self, jouer_tour, attente="… le MJ réfléchit", narrer=True):
        self.dire("\n" + attente)
        try:
            tour = jouer_tour()
        except llm.ErreurLLM as erreur:
            self.dire(f"Le MJ n'a pas répondu ({erreur}). Réessaie.")
            return
        for appel in tour.appels:
            for ligne in decrire(appel.outil, appel.arguments, appel.resultat, self.session):
                self.dire(ligne)
        if narrer:
            self.dire("\n" + (tour.narration.strip() or "(Le MJ reste muet… Reformule ton action.)"))

    def sauvegarder(self):
        s = self.session
        arme = [s.joueur.arme.nom] if s.joueur.arme else []
        armure = s.joueur.armure.nom if s.joueur.armure else None
        sauvegarder(Partie(s.personnage, s.univers, s.moment, armes=arme, arme_en_main=arme[0] if arme else None,
                           armure=armure, vehicule=s.vehicule.vers_dict() if s.vehicule else None),
                    self.campagne.sauvegarde)

    def afficher_etat(self):
        e = outils.etat(self.session)  # appelé en direct : ni le MJ ni le journal ne le voient
        j = e["joueur"]
        self.dire(f"\n{j['nom']} — {e['moment']}")
        self.dire(f"  {j['pv']}/{j['pv_max']} PV ({j['etat']}" + (", blessure grave" if j["blessure_grave"] else "")
                  + f"), Santé mentale {j['sante_mentale']}/{j['sm_max']}, {j['points_destin']} points de destin, "
                  f"{j['xp']} XP")
        arme = j["arme"] or "aucune arme"
        self.dire(f"  {arme}" + (f" ({j['munitions']} balles)" if "munitions" in j else "")
                  + f", {j['armure'] or 'sans armure'}")
        if j["troubles"]:
            self.dire(f"  Troubles : {', '.join(j['troubles'])}")
        if "combat" in e:
            self.dire(f"  En combat, round {e['combat']['round']}")

    def fin_de_session(self):
        k, s = self.session.personnage, self.session
        self.raconter(lambda: self.table.tour(FIN_DE_SESSION), "… le MJ range ses souvenirs", narrer=False)
        self.dire("\n=== Fin de session ===")
        ameliorations = progression.fin_de_session(s.des, k)
        if not ameliorations:
            self.dire("Aucune compétence réussie à faire progresser.")
        for a in ameliorations:
            self.dire(f"  {s.univers.nom_affiche(a.competence)} {a.avant} : jet {a.jet:02d} → "
                      + (f"+{a.gain}, passe à {a.apres} !" if a.gain else "pas de progrès."))
        self.sauvegarder()
        self.dire(f"\nPartie sauvegardée : {self.campagne.sauvegarde}")
        self.dire(f"Kaito : {k.pv}/{k.pv_max} PV, {k.sm} en Santé mentale, {k.points_destin} points de destin.")


def lire_arguments(arguments: list[str] | None = None):
    parser = argparse.ArgumentParser(prog="aria.jeu", description="Jouer une campagne avec le MJ.")
    parser.add_argument("--campagne", default=CAMPAGNE, help=f"son dossier dans .Aria-JDR (par défaut {CAMPAGNE})")
    parser.add_argument("--genre", help="pour une nouvelle campagne : son genre (l'univers est généré)")
    parser.add_argument("--nom", default="", help="le nom de l'univers (par défaut, celui du genre)")
    parser.add_argument("--cadre", default="", help="le cadre, en une phrase")
    parser.add_argument("--annee", type=int, help="l'année du cadre (sinon, le MJ la déduit du cadre)")
    parser.add_argument("--surprends-moi", action="store_true", help="le MJ propose le nom et le cadre")
    return parser.parse_args(arguments)


def choix_de(arguments) -> "generateur.Choix | None":
    """Les choix d'une nouvelle campagne, préremplis par genre ; None pour reprendre une campagne."""
    if not arguments.genre:
        return None
    return generateur.choix_par_defaut(generateur.charger(), arguments.genre, arguments.nom, arguments.cadre,
                                       arguments.annee)


def surprendre(serveur, choix, budget, entree=input, sortie=print):
    """Le MJ propose un cadre ; le joueur le garde, ou en demande un autre. None s'il abandonne."""
    refuses = []
    while True:
        propose = generateur.proposer_cadre(serveur, choix, budget, refuses)
        sortie(f"\n{propose.nom} — {propose.cadre}")
        reponse = entree("On garde ? (o : oui, n : un autre, q : abandonner) ").strip().lower()
        if reponse in ("o", "oui", ""):
            return propose
        if reponse in ("q", "quitter"):
            return None
        refuses.append(propose.cadre)


def main(arguments: list[str] | None = None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = lire_arguments(arguments)
    campagne = Campagne.nommee(arguments.campagne)
    try:
        choix = choix_de(arguments)
    except generateur.ChoixInvalide as erreur:
        print(erreur)
        return
    if choix and campagne.univers.is_file():
        print(f"La campagne « {arguments.campagne} » a déjà son univers : elle reprend telle quelle (sans --genre).")
        return
    profil = banc.profil_valide()
    if profil is None:
        print("Pas de MJ qualifié sur ce PC. Lance d'abord le banc : .venv\\Scripts\\python.exe -m aria.banc")
        return
    modele = optimiseur.decrire(llm.DOSSIER_MODELES / profil["fichier"], profil["modele"])
    if modele is None:
        print(f"Le modèle {profil['fichier']} est illisible. Relance le banc.")
        return
    reglages = optimiseur.Reglages(**profil["reglages"])
    print(f"Chargement du MJ : {modele.nom} ({reglages}), réflexion {profil['budget_reflexion']} jetons…")
    serveur = llm.Serveur(modele, reglages, journal=JOURNAL_SERVEUR)
    try:
        if not serveur.demarrer():
            print(f"Le serveur du MJ ne démarre pas (détails : {JOURNAL_SERVEUR}). "
                  "La carte graphique est peut-être occupée : ferme ce qui l'utilise, ou relance le banc.")
            return
        if choix and arguments.surprends_moi:
            choix = surprendre(serveur, choix, banc_generateur.budget_generateur(profil))
            if choix is None:
                return
        Jeu(serveur, profil["budget_reflexion"], reglages.contexte, campagne=campagne, choix=choix,
            budget_generation=banc_generateur.budget_generateur(profil)).jouer()
    except SansPersonnage as erreur:
        print(erreur)
    except (KeyboardInterrupt, EOFError):
        print("\nPartie interrompue.")
    finally:
        serveur.arreter()


if __name__ == "__main__":
    main()
