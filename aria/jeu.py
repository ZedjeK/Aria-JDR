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
import random
from contextlib import contextmanager
import sys

from aria import (amorce, banc, banc_generateur, chemins, creation_texte, generateur, llm, optimiseur, outils,
                  personnages, progression)
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
PLANS_VUS = "plans_vus.json"  # les plans d'amorce déjà piochés
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
                 choix: "generateur.Choix | None" = None, budget_generation: int | None = None,
                 creer: bool = False, predefini: "personnages.Predefini | None" = None):
        """`choix` : pour une nouvelle campagne, l'univers à générer. Sans choix, une campagne qui n'a pas
        encore d'univers prend Néo-Tokyo, l'univers étalon du banc. `creer` : le joueur crée son personnage
        (sinon, c'est Kaito, le Netrunner de la démo) ; avec `predefini`, il prend ce personnage préparé à
        l'avance, dont le métier est gardé dans l'univers."""
        self.entree, self.dire, self.hasard = entree, sortie, random.Random()
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
                                                                gardes={predefini.parcours} if predefini else set() if creer else {NETRUNNER})
                self.montrer_adaptation(univers, adaptation)
            else:
                univers = charger_univers(banc.UNIVERS)
            if creer:
                generation = budget if budget_generation is None else budget_generation
                perso, depart = self.personnage_du_joueur(univers, predefini, serveur, generation)
                self.session = Session(univers, perso, des or Des(), Moment(1, Periode.APRES_MIDI),
                                       arme=depart.arme if depart else None, armure=depart.armure if depart else None,
                                       vehicule=depart.vehicule if depart else None, campagne=self.campagne)
                self.table = Table(serveur, self.session, budget, self.amorcer(serveur, generation), contexte=contexte)
                self.sauvegarder()  # le personnage et son amorce existent : une coupure ne les fait pas perdre
                return
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
        # Le quartier de Kaito ne vaut que pour Néo-Tokyo ; ailleurs, la mémoire de la campagne dit où on en est
        quartier = "" if self.campagne.univers.is_file() else QUARTIER
        self.table = Table(serveur, self.session, budget, quartier if self.reprise else SCENE, contexte=contexte)

    def personnage_du_joueur(self, univers, predefini, serveur, budget: int | None):
        """Le personnage prédéfini s'il peut vivre dans cet univers ; sinon, la création guidée."""
        if predefini is not None:
            try:
                brouillon, notes = personnages.brouillon_dans(univers, predefini, self.hasard)
                self.dire("\n=== Ton personnage ===\n" + "\n".join(creation_texte.resume(brouillon)))
                for note in notes:
                    self.dire(f"  ({note})")
                return brouillon.finaliser()
            except creation_texte.EtapeInvalide as erreur:
                self.dire(f"\n{predefini.nom} ne peut pas vivre dans cet univers ({' '.join(erreur.erreurs)}) : "
                          "on crée un personnage sur place.")
        return creation_texte.Guide(univers, self.entree, self.dire, serveur, budget).creer()

    def amorcer(self, serveur, budget: int | None) -> str:
        """L'amorce de la campagne, d'après l'idée du joueur ou un plan tiré dans la bibliothèque. Gardée, elle
        est rangée dans la mémoire. Renvoie la scène d'ouverture pour le MJ (vide s'il doit l'inventer seul)."""
        s = self.session
        vus = self.campagne.dossier.parent / PLANS_VUS  # à côté des campagnes : il vaut pour toutes
        self.dire("\n=== Le début de ta campagne ===")
        idee = self.entree("Ton idée de départ en une phrase, ou Entrée pour que je pioche un plan : ").strip()
        while True:
            plan = idee[:amorce.PLAN_MAX] or (f"{amorce.tirer_plan(s.univers.genre, self.hasard, vus)} "
                                              f"Complication : {amorce.tirer_complication(self.hasard)}")
            self.dire(f"\nPlan : {plan}\n… le MJ prépare le début de la campagne")
            try:
                proposee = amorce.proposer_amorce(serveur, s.univers, s.personnage, plan, budget)
            except llm.ErreurLLM:
                proposee = None
            if proposee is None:
                self.dire("Le MJ n'a rien proposé de valide : il ouvrira la campagne lui-même.")
                return ""
            self.dire("\n" + "\n".join(proposee.lignes()))
            reponse = self.entree("Entrée pour garder, « r » pour une autre, ou écris une autre idée : ").strip()
            if reponse == "":
                proposee.ranger(s.memoire, s.moment)
                return proposee.scene
            if reponse.lower() != "r":
                idee = reponse

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
        mort = "morte" if k.sexe == "femme" else "mort"
        if self.mort():
            self.dire(f"{k.nom} est {mort}. Pour une nouvelle campagne, supprime le dossier {self.campagne.dossier}.")
            return
        self.dire(f"=== {u.nom} ===\n{u.cadre}")
        if self.reprise:
            self.dire(f"\nReprise de la campagne : {self.session.moment}.")
        self.dire(f"\nTu es {k.nom}, {k.parcours.lower()}. {k.pv}/{k.pv_max} PV, {k.sm} en Santé mentale, "
                  f"{k.points_destin} points de destin.")
        self.dire(f"Motivation : {k.motivation}. Lien : {k.lien}. Défaut : {k.defaut}.")
        self.dire(f"Écris ce que fait {k.nom}. « etat » : ta fiche ; « quitter » : fin de la session.")
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
                self.dire(f"\n{k.nom} est {mort}. Fin de la partie.")
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
        self.dire(f"{k.nom} : {k.pv}/{k.pv_max} PV, {k.sm} en Santé mentale, {k.points_destin} points de destin.")


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
    lancer(campagne, choix, arguments.surprends_moi)


@contextmanager
def mj_charge():
    """Le serveur du MJ, démarré puis arrêté : donne (serveur, profil, réglages), ou None s'il ne peut pas
    tourner (la raison est affichée)."""
    profil = banc.profil_valide()
    if profil is None:
        print("Pas de MJ qualifié sur ce PC. Lance d'abord le banc : .venv\\Scripts\\python.exe -m aria.banc")
        yield None
        return
    modele = optimiseur.decrire(llm.DOSSIER_MODELES / profil["fichier"], profil["modele"])
    if modele is None:
        print(f"Le modèle {profil['fichier']} est illisible. Relance le banc.")
        yield None
        return
    reglages = optimiseur.Reglages(**profil["reglages"])
    print(f"Chargement du MJ : {modele.nom} ({reglages}), réflexion {profil['budget_reflexion']} jetons…")
    serveur = llm.Serveur(modele, reglages, journal=JOURNAL_SERVEUR)
    try:
        if serveur.demarrer():
            yield serveur, profil, reglages
        else:
            print(f"Le serveur du MJ ne démarre pas (détails : {JOURNAL_SERVEUR}). "
                  "La carte graphique est peut-être occupée : ferme ce qui l'utilise, ou relance le banc.")
            yield None
    finally:
        serveur.arreter()


def lancer(campagne: Campagne, choix: "generateur.Choix | None" = None, surprends_moi: bool = False,
           predefini: "personnages.Predefini | None" = None):
    """Charge le MJ et joue la campagne : nouvelle si `choix` est donné, reprise sinon. Le menu et la ligne
    de commande passent tous les deux par ici."""
    # Un univers généré mais pas encore de sauvegarde : la création du personnage n'a pas été finie
    a_creer = campagne.univers.is_file() and not campagne.sauvegarde.is_file()
    with mj_charge() as mj:
        if mj is None:
            return
        serveur, profil, reglages = mj
        try:
            if choix and surprends_moi:
                choix = surprendre(serveur, choix, banc_generateur.budget_generateur(profil))
                if choix is None:
                    return
            Jeu(serveur, profil["budget_reflexion"], reglages.contexte, campagne=campagne, choix=choix,
                budget_generation=banc_generateur.budget_generateur(profil), creer=choix is not None or a_creer,
                predefini=predefini if choix is not None else None).jouer()
        except SansPersonnage as erreur:
            print(erreur)
        except creation_texte.Abandon:
            print("\nCréation abandonnée. Reprends cette campagne pour créer ton personnage.")
        except (KeyboardInterrupt, EOFError):
            print("\nPartie interrompue.")


if __name__ == "__main__":
    main()
