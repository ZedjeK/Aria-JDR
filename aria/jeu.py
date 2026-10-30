"""Démo v2 : la ruelle de Néo-Tokyo, en texte libre, avec le MJ LLM.

Tu écris ce que fait Kaito ; le MJ (le modèle qualifié par le banc) appelle le moteur et
raconte. Chaque jet s'affiche avant la narration : tu vois toujours ce que disent les dés.
Commandes : « etat » pour ta fiche, « quitter » pour finir la session.

Tout ce qui concerne la campagne (sauvegarde, souvenirs, fiche du combat en cours) est
rangé dans son dossier : parties/neo-tokyo-kaito/.

Lancement (après le banc, qui choisit le modèle) :
    .venv\\Scripts\\python.exe -m aria.jeu
"""

import sys
from pathlib import Path

from aria import banc, llm, optimiseur, outils, progression
from aria.campagne import Campagne
from aria.compte_rendu import decrire
from aria.des import Des
from aria.outils import Session
from aria.personnage import Etat
from aria.sauvegarde import Partie, sauvegarder
from aria.table import Table
from aria.temps import Moment, Periode
from aria.univers import charger_univers

RACINE = Path(__file__).resolve().parent.parent
CAMPAGNE = "neo-tokyo-kaito"
JOURNAL_SERVEUR = RACINE / "parties" / "serveur_jeu.log"
QUITTER = ("quitter", "/quitter")
ETAT = ("etat", "état", "/etat")
# Ce que le MJ sait de la scène : la ruelle de la démo v1. Le joueur, lui, ne voit que la narration.
SCENE = (
    "Jour 1, fin d'après-midi. La pluie fait grésiller les néons. Kaito coupe par une ruelle pour rentrer "
    "à sa planque, son pistolet lourd Arasaka sous sa veste renforcée.\n\n"
    "Deux gangers l'attendent, cachés, pour le dépouiller (leur Discrétion : 45) :\n"
    "- un ganger au couteau, nerveux (combat 45, 10 PV, Couteau, dextérité 55) ;\n"
    "- un tireur, planqué derrière une voiture (combat 40, 9 PV, Pistolet lourd, dextérité 50).\n"
    "Ils ne se battent pas jusqu'à la mort : blessés ou en mauvaise posture, ils fuient ou se rendent.\n\n"
    "Dans le quartier : une vendeuse de ramen au coin de la rue (Médecine 40), Doc Mori, le charcudoc "
    "(Médecine 70), et la planque de Kaito, où il peut appeler Hana."
)


class Jeu:
    def __init__(self, serveur: llm.Serveur, budget: int | None, contexte: int = optimiseur.CONTEXTE_CIBLE,
                 des: Des | None = None, entree=input, sortie=print, campagne: Campagne | None = None):
        self.entree, self.dire = entree, sortie
        self.campagne = campagne or Campagne.nommee(CAMPAGNE)
        self.campagne.ouvrir()
        univers = charger_univers(banc.UNIVERS)
        kaito = univers.creer_personnage("Netrunner", **banc.FICHE_KAITO)
        self.session = Session(univers, kaito, des or Des(), Moment(1, Periode.APRES_MIDI),
                               arme="Pistolet lourd Arasaka", armure="Veste renforcée", campagne=self.campagne)
        self.table = Table(serveur, self.session, budget, SCENE, contexte=contexte)

    def jouer(self):
        k, u = self.session.personnage, self.session.univers
        self.dire(f"=== {u.nom} ===\n{u.cadre}")
        self.dire(f"\nTu es {k.nom}, netrunner. {k.pv} PV, {k.sm} en Santé mentale, {k.points_destin} points de destin.")
        self.dire(f"Motivation : {k.motivation}. Lien : {k.lien}. Défaut : {k.defaut}.")
        self.dire("Écris ce que fait Kaito. « etat » : ta fiche ; « quitter » : fin de la session.")
        self.raconter(self.table.ouvrir)
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
            if k.etat is Etat.MORT and k.points_destin == 0:
                self.dire("\nKaito est mort dans les rues de Néo-Tokyo. Fin de la partie.")
                return
        self.fin_de_session()

    def raconter(self, jouer_tour):
        self.dire("\n… le MJ réfléchit")
        try:
            tour = jouer_tour()
        except llm.ErreurLLM as erreur:
            self.dire(f"Le MJ n'a pas répondu ({erreur}). Réessaie.")
            return
        for appel in tour.appels:
            for ligne in decrire(appel.outil, appel.arguments, appel.resultat, self.session):
                self.dire(ligne)
        self.dire("\n" + (tour.narration.strip() or "(Le MJ reste muet… Reformule ton action.)"))

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
        self.dire("\n=== Fin de session ===")
        ameliorations = progression.fin_de_session(s.des, k)
        if not ameliorations:
            self.dire("Aucune compétence réussie à faire progresser.")
        for a in ameliorations:
            self.dire(f"  {s.univers.nom_affiche(a.competence)} {a.avant} : jet {a.jet:02d} → "
                      + (f"+{a.gain}, passe à {a.apres} !" if a.gain else "pas de progrès."))
        arme = [s.joueur.arme.nom] if s.joueur.arme else []
        armure = s.joueur.armure.nom if s.joueur.armure else None
        sauvegarder(Partie(k, s.univers, s.moment, armes=arme, arme_en_main=arme[0] if arme else None,
                           armure=armure), self.campagne.sauvegarde)
        self.dire(f"\nPartie sauvegardée : {self.campagne.sauvegarde}")
        self.dire(f"Kaito : {k.pv}/{k.pv_max} PV, {k.sm} en Santé mentale, {k.points_destin} points de destin.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
        Jeu(serveur, profil["budget_reflexion"], reglages.contexte).jouer()
    except (KeyboardInterrupt, EOFError):
        print("\nPartie interrompue.")
    finally:
        serveur.arreter()


if __name__ == "__main__":
    main()
