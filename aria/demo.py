"""Démo jouable en ligne de commande : une ruelle de Néo-Tokyo.

Tu joues Kaito, le Netrunner ; un MJ scripté joue les deux gangers. Lancer avec :
    .venv\\Scripts\\python.exe -m aria.demo
"""

import sys
from pathlib import Path

from aria import progression, sante_mentale, soins
from aria.combat import (
    BudgetRound,
    Combat,
    Combattant,
    Couvert,
    Defense,
    FichePnj,
    RapportAttaque,
    TypeAction,
    laisser_pour_mort,
    tester_embuscade,
)
from aria.des import Des
from aria.personnage import Caracteristique as C, Etat
from aria.resolution import Degre, Issue, Resultat
from aria.sauvegarde import Partie, sauvegarder
from aria.temps import Moment, Periode
from aria.univers import charger_univers

RACINE = Path(__file__).resolve().parent.parent
UNIVERS = RACINE / "univers" / "cyberpunk.json"
SAUVEGARDE = RACINE / "parties" / "demo_kaito.json"
ROUNDS_MAX = 30
KAITO = dict(
    nom="Kaito",
    caracteristiques={C.FORCE: 35, C.CONSTITUTION: 45, C.DEXTERITE: 60, C.INTELLIGENCE: 75, C.VOLONTE: 50, C.PRESENCE: 35},
    points_parcours={"Technologie": 70, "Investigation": 45, "Sécurité": 50, "Perception": 25,
                     "Discrétion": 30, "Artisanat": 40, "Tromperie": 25, "Sciences": 15},
    points_personnels={"Armes à distance": 30, "Esquive": 20, "Pilotage": 20, "Perspicacité": 30},
    motivation="Effacer sa dette envers une corpo",
    lien="Sa petite sœur Yuna, sa seule famille",
    defaut="Fait trop confiance aux machines",
)


def jet(resultat: Resultat) -> str:
    return f"{resultat.jet:02d} pour {resultat.valeur} : {resultat.degre.libelle}"


class Demo:
    def __init__(self, des: Des | None = None, entree=input, sortie=print, chemin_sauvegarde: Path = SAUVEGARDE):
        self.des = des or Des()
        self.entree = entree
        self.dire = sortie
        self.chemin_sauvegarde = chemin_sauvegarde
        self.univers = charger_univers(UNIVERS)
        self.kaito = self.univers.creer_personnage("Netrunner", **KAITO)
        self.moment = Moment(1, Periode.APRES_MIDI)
        self.a_frole_la_mort = False

    # --- Outils ---------------------------------------------------------------------------

    def choisir(self, question: str, options: list[str]) -> int:
        self.dire(question)
        for numero, option in enumerate(options, 1):
            self.dire(f"  {numero}. {option}")
        return self.lire_choix(len(options))

    def lire_choix(self, nombre: int) -> int:
        """Lit un numéro entre 1 et `nombre` et renvoie son indice (à partir de 0)."""
        while True:
            reponse = self.entree("> ").strip()
            if reponse.isdigit() and 1 <= int(reponse) <= nombre:
                return int(reponse) - 1
            self.dire(f"Tape un nombre entre 1 et {nombre}.")

    def nom(self, competence: str) -> str:
        return self.univers.nom_affiche(competence)

    def raconter(self, rapport: RapportAttaque):
        self.dire(f"  {rapport.attaquant} attaque : {jet(rapport.attaque)}.")
        if rapport.defense:
            self.dire(f"  {rapport.cible} se défend : {jet(rapport.defense)}.")
        if rapport.touche:
            b = rapport.blessure
            armure = f", l'armure en arrête {rapport.protection}" if rapport.protection else ""
            self.dire(f"  → {rapport.touche} est touché : {rapport.degats_bruts} dégâts{armure}. PV {b.pv_avant} → {b.pv_apres}.")
            if b.blessure_grave:
                self.dire("  → BLESSURE GRAVE !")
            if b.test_constitution:
                self.dire(f"  → Test de Constitution : {jet(b.test_constitution)}.")
            if b.etat is not Etat.ACTIF:
                self.dire(f"  → {rapport.touche} est {b.etat.value}.")
        elif rapport.issue is Issue.DEFENSEUR:
            self.dire("  → Le coup est évité.")
        else:
            self.dire("  → Raté.")
        for effet in rapport.effets:
            self.dire(f"  → {effet}")

    # --- La partie --------------------------------------------------------------------------

    def jouer(self):
        k = self.kaito
        self.dire(f"=== {self.univers.nom} ===")
        self.dire(self.univers.cadre)
        self.dire(f"\nTu es {k.nom}, netrunner. {k.pv} PV, {k.sm} en Santé mentale, {k.points_destin} points de destin.")
        self.dire(f"Motivation : {k.motivation}. Lien : {k.lien}. Défaut : {k.defaut}.")
        self.dire("\nFin d'après-midi. La pluie fait grésiller les néons. Tu coupes par une ruelle pour rentrer "
                  "à ta planque, ton pistolet Arasaka sous la veste…")
        self.combattre()
        if k.etat is Etat.MORT:
            self.dire("\nKaito est mort dans une ruelle de Néo-Tokyo. Fin de la partie.")
            return
        self.apres_combat()
        self.nuit()
        self.fin_de_session()

    # --- Le combat --------------------------------------------------------------------------

    def combattre(self):
        u = self.univers
        self.k = Combattant(self.kaito, "joueur", u.arme("Pistolet lourd Arasaka"), u.armure("Veste renforcée"))
        self.couteau = Combattant(FichePnj("Le ganger au couteau", combat=45, pv_max_base=10, dexterite=55),
                                  "ennemis", u.arme("Couteau"))
        self.tireur = Combattant(FichePnj("Le tireur", combat=40, pv_max_base=9, dexterite=50),
                                 "ennemis", u.arme("Pistolet lourd"))
        self.a_couvert = self.au_contact = self.enraye = False

        embuscade = tester_embuscade(self.des, self.kaito.competence("Perception"), 45)
        self.dire(f"\nDeux silhouettes t'attendaient. Leur discrétion : {jet(embuscade.discretion)}. "
                  f"Ta {self.nom('Perception')} : {jet(embuscade.perception)}.")
        self.dire("Ils te tombent dessus par surprise ! Tu perds ton premier round." if embuscade.surpris
                  else "Tu les as repérés à temps : un type avec un couteau, et un tireur derrière une voiture.")
        self.combat = Combat(self.des, [self.k, self.couteau, self.tireur], u.curseur,
                             surpris=[self.k] if embuscade.surpris else [])

        while self.combat.round <= ROUNDS_MAX:
            self.dire(f"\n— Round {self.combat.round} — Kaito : {self.kaito.pv}/{self.kaito.pv_max} PV, "
                      f"{self.k.munitions_restantes() if self.k.arme else 0} balles"
                      + (", à couvert" if self.a_couvert else ""))
            for combattant in self.combat.ordre:
                if self.combat_fini():
                    break
                if combattant is self.k:
                    self.tour_kaito()
                elif combattant is self.couteau:
                    self.tour_couteau()
                else:
                    self.tour_tireur()
            for nom, test in self.combat.fin_de_round():
                self.dire(f"  {nom} agonise. Constitution : {jet(test)}.")
            if self.kaito.pv == 0:
                self.a_frole_la_mort = True
            if self.proposer_destin():
                return
            if self.combat_fini():
                break
        self.fin_du_combat()

    def combat_fini(self) -> bool:
        ennemis_debout = any(self.combat.peut_agir(g) for g in (self.couteau, self.tireur))
        return not ennemis_debout or not self.k.conscient

    def tour_kaito(self):
        c, k = self.combat, self.k
        if not c.peut_agir(k):
            if k.surpris:
                self.dire("\nTu es pris par surprise et ne peux rien faire ce round.")
            return
        self.dire("\nC'est ton tour. Rappel : 1 déplacement + 1 action simple + 1 action mineure, "
                  "ou 2 déplacements + 1 action mineure.")
        while not self.combat_fini():
            budget = k.budget
            restants = [(budget.restants(TypeAction.DEPLACEMENT), "déplacement"),
                        (budget.restants(TypeAction.MINEURE), "action mineure"),
                        (budget.restants(TypeAction.SIMPLE), "action simple")]
            self.dire("\nIl te reste : " + ", ".join(f"{n} {nom}{'s' if n > 1 else ''}" for n, nom in restants))
            options = []
            for titre, actions, raison in self.actions_possibles():
                self.dire(f"  [{titre}]")
                if not actions:
                    self.dire(f"     ({raison})")
                for libelle, action in actions:
                    options.append(action)
                    self.dire(f"  {len(options)}. {libelle}")
            if not options:
                self.dire("  Plus rien à faire : ton tour se termine.")
                return
            options.append(None)
            self.dire(f"  {len(options)}. Finir ton tour")
            action = options[self.lire_choix(len(options))]
            if action is None:
                return
            action()

    def actions_possibles(self) -> list[tuple[str, list, str]]:
        """Les actions du tour, rangées par type : (titre, [(libellé, action)], raison s'il n'y en a aucune)."""
        c, k = self.combat, self.k
        budget = k.budget
        restantes = k.munitions_restantes() or 0
        recharge_mineure = k.arme is not None and k.arme.munitions.recharge.value == "mineure"
        peut_recharger = k.arme is not None and restantes < k.arme.munitions.capacite

        deplacements, raison_deplacement = [], ""
        if k.vise:
            raison_deplacement = "tu as visé : tu ne peux plus bouger ce round"
        elif not budget.peut(TypeAction.DEPLACEMENT):
            raison_deplacement = "plus de déplacement possible ce round"
        elif self.a_couvert:
            raison_deplacement = "tu es déjà à couvert derrière la benne"
        else:
            deplacements.append(("Plonger à couvert derrière une benne (le tireur aura −20)", self.se_couvrir))

        mineures, raison_mineure = [], "rien d'utile pour l'instant"
        if not budget.peut(TypeAction.MINEURE):
            raison_mineure = "action mineure déjà utilisée"
        else:
            if k.arme and restantes and not k.vise:
                if budget.utilise[TypeAction.DEPLACEMENT]:
                    raison_mineure = "viser est impossible : tu t'es déplacé ce round"
                else:
                    mineures.append(("Viser (+20 au tir de ce round, mais tu ne pourras plus bouger)", lambda: c.viser(k)))
            if peut_recharger and recharge_mineure:
                mineures.append((f"Recharger ({restantes} balles restantes)", self.recharger))

        simples, raison_simple = [], ""
        if not budget.peut(TypeAction.SIMPLE):
            raison_simple = ("tu t'es déplacé deux fois" if budget.utilise[TypeAction.DEPLACEMENT] == 2
                             else "action simple déjà utilisée")
        elif k.arme and restantes:
            bonus = " (+20, tu as visé)" if k.vise else ""
            for cible in (self.couteau, self.tireur):
                if c.peut_agir(cible):
                    couvert = ", il est à couvert : −20" if cible is self.tireur else ""
                    simples.append((f"Tirer sur {cible.nom.lower()}{bonus}{couvert}",
                                    lambda cible=cible: self.tirer(cible)))
        elif k.arme:
            raison_simple = "chargeur vide : recharge d'abord"
        elif self.au_contact and c.peut_agir(self.couteau):
            simples.append(("Frapper le ganger au couteau à mains nues",
                            lambda: self.raconter(c.attaquer(k, self.couteau))))
        else:
            raison_simple = "tu n'as plus d'arme et personne à portée de poing"
        if budget.peut(TypeAction.SIMPLE) and peut_recharger and not recharge_mineure:
            simples.append(("Recharger", self.recharger))

        return [("Déplacement", deplacements, raison_deplacement),
                ("Action mineure", mineures, raison_mineure),
                ("Action simple", simples, raison_simple)]

    def se_couvrir(self):
        self.combat.deplacer(self.k)
        self.a_couvert = True
        self.dire("  Tu plonges derrière une benne. Le tireur aura du mal à t'atteindre.")

    def recharger(self):
        self.combat.recharger(self.k)
        self.dire(f"  Tu enclenches un chargeur neuf ({self.k.munitions_restantes()} balles).")

    def tirer(self, cible: Combattant):
        couvert = Couvert.PARTIEL if cible is self.tireur else Couvert.AUCUN
        self.raconter(self.combat.attaquer(self.k, cible, couvert=couvert))

    def tour_couteau(self):
        c, g = self.combat, self.couteau
        if not c.peut_agir(g):
            return
        if not self.au_contact:
            c.deplacer(g)
            self.au_contact = True
            self.dire("\nLe ganger au couteau fonce sur toi, lame en avant !")
        else:
            self.dire("\nLe ganger au couteau frappe encore !")
        defense = None
        if self.k.conscient and not (self.k.surpris and c.round == 1):
            choix = self.choisir("Comment réagis-tu ?", [f"Esquiver ({self.k.valeur('Esquive')} %)",
                                                         f"Riposter ({self.k.valeur('Corps à corps')} %)"])
            defense = Defense.ESQUIVE if choix == 0 else Defense.RIPOSTE
        self.raconter(c.attaquer(g, self.k, defense))

    def tour_tireur(self):
        c, g = self.combat, self.tireur
        if not c.peut_agir(g):
            return
        if self.enraye:
            self.enraye = False
            self.dire("\nLe tireur jure en désenrayant son arme.")
            return
        if g.munitions_restantes() == 0:
            c.recharger(g)
            self.dire("\nLe tireur recharge.")
        self.dire("\nLe tireur fait feu" + (" sur ta benne !" if self.a_couvert else " !"))
        rapport = c.attaquer(g, self.k, couvert=Couvert.PARTIEL if self.a_couvert else Couvert.AUCUN)
        self.raconter(rapport)
        if rapport.attaque.degre is Degre.MALADRESSE:
            self.enraye = True
            self.dire("  → Son pistolet s'enraye !")

    def proposer_destin(self) -> bool:
        """Si Kaito vient de mourir, propose un point de destin. Renvoie vrai si la partie s'arrête."""
        if self.kaito.etat is not Etat.MORT:
            return False
        if self.kaito.points_destin <= 0:
            return True
        choix = self.choisir(f"\nKaito est mort… Dépenser un point de destin ({self.kaito.points_destin} restants) ?",
                             ["Oui : il est laissé pour mort", "Non : c'est la fin"])
        if choix == 1:
            return True
        laisser_pour_mort(self.k)
        self.dire("  Le destin s'en mêle : Kaito respire encore, à peine. Il est laissé pour mort.")
        return False

    def fin_du_combat(self):
        k = self.kaito
        if not self.k.conscient and k.etat is not Etat.MORT:
            self.dire("\nTu t'effondres. Les gangers te fouillent, prennent ton pistolet et filent.")
            self.k.arme = None
            vendeuse = Combattant(FichePnj("La vendeuse de ramen", combat=20, pv_max_base=8,
                                           competences={"Médecine": 40}), "passants")
            while k.etat is Etat.MOURANT:
                self.dire("Une vendeuse de ramen accourt et tente d'arrêter l'hémorragie…")
                resultat = self.combat.stabiliser(vendeuse, self.k)
                self.dire(f"  Médecine : {jet(resultat)}.")
                for nom, test in self.combat.fin_de_round():
                    self.dire(f"  {nom} agonise. Constitution : {jet(test)}.")
                vendeuse.budget = BudgetRound()
                if self.proposer_destin():
                    return
            if k.etat is not Etat.ACTIF:
                repos = soins.reposer(k, soins.Repos.COURT, self.moment, self.univers.curseur)
                self.dire(f"Tu reprends connaissance une demi-heure plus tard, sous la pluie (+{repos.gain} PV).")
        elif self.combat.round > ROUNDS_MAX:
            self.dire("\nDes sirènes au loin : les gangers décrochent et disparaissent.")
        else:
            self.dire("\nLe silence retombe sur la ruelle. Il ne reste que la pluie et l'odeur de la poudre.")

    # --- Après le combat ---------------------------------------------------------------------

    def apres_combat(self):
        k, u = self.kaito, self.univers
        for ganger in (self.couteau, self.tireur):
            if ganger.fiche.etat is Etat.MOURANT and k.etat is Etat.ACTIF:
                choix = self.choisir(f"\n{ganger.nom} agonise dans une flaque.",
                                     [f"Tenter de le stabiliser ({self.nom('Médecine')} {k.valeur('Médecine')} %)",
                                      "Le laisser"])
                if choix == 0:
                    self.k.budget = BudgetRound()  # hors combat, chaque blessé a droit à son temps
                    resultat = self.combat.stabiliser(self.k, ganger)
                    self.dire(f"  {jet(resultat)}.")
                if ganger.fiche.etat is Etat.MOURANT:
                    ganger.fiche.etat = Etat.MORT
                    self.dire("  Il cesse de respirer.")
                else:
                    self.dire("  Il respire encore. Les secours le trouveront peut-être.")

        reglages = u.reglages_mentaux()
        chocs = []
        if any(g.fiche.etat is Etat.MORT for g in (self.couteau, self.tireur)):
            chocs.append(sante_mentale.Choc.PREMIER_MEURTRE)
        if self.a_frole_la_mort:
            chocs.append(sante_mentale.Choc.FROLER_LA_MORT)
        for choc in chocs:
            r = sante_mentale.subir_choc(self.des, k, choc, self.moment, reglages)
            if r.gravite is None:
                continue
            self.dire(f"\n{choc.description}… Santé mentale : {jet(r.test)}. Tu perds {r.perte} (SM {r.sm_apres}).")
            if r.crise:
                self.dire(f"  Crise : {r.crise.value} pendant {r.duree_crise} rounds.")
            if r.trouble:
                self.dire(f"  Un trouble s'installe : {r.trouble.type.value}.")

        if k.blessure_grave:
            charcudoc = FichePnj("Doc Mori, charcudoc", combat=20, pv_max_base=10, competences={"Médecine": 70})
            choix = self.choisir("\nTa blessure est grave. Que fais-tu ?",
                                 ["Aller voir Doc Mori, le charcudoc du quartier (Médecine 70)",
                                  f"Te recoudre toi-même ({k.valeur('Médecine')} %)"])
            soigneur = charcudoc if choix == 0 else k
            r = soins.soigner(self.des, soigneur, k, self.moment)
            self.dire(f"  Médecine : {jet(r.test)}. +{r.gain} PV ({r.pv_apres}/{k.pv_max})."
                      + (" La blessure est soignée : elle guérira cette nuit." if r.blessure_grave_soignee else ""))

    def nuit(self):
        k = self.kaito
        self.moment = Moment(1, Periode.NUIT)
        self.dire("\nLa nuit tombe sur Néo-Tokyo. Tu rentres à ta planque.")
        choix = self.choisir("Avant de dormir :", ["Appeler Yuna, ta petite sœur", "Dormir directement"])
        if choix == 0:
            r = sante_mentale.discussion(self.des, k, self.moment)
            self.dire(f"  Sa voix te fait du bien : +{r.gain} SM ({r.sm_apres}).")
        r = soins.reposer(k, soins.Repos.LONG, self.moment, self.univers.curseur)
        self.dire(f"  Une nuit de sommeil : PV {r.pv_apres}/{k.pv_max}."
                  + (" Ta blessure grave est guérie." if r.blessure_grave_guerie else ""))

    def fin_de_session(self):
        k = self.kaito
        self.dire("\n=== Fin de session ===")
        ameliorations = progression.fin_de_session(self.des, k)
        if not ameliorations:
            self.dire("Aucune compétence réussie à faire progresser.")
        for a in ameliorations:
            self.dire(f"  {self.nom(a.competence)} {a.avant} : jet {a.jet:02d} → "
                      + (f"+{a.gain}, passe à {a.apres} !" if a.gain else "pas de progrès."))
        arme = [self.k.arme.nom] if self.k.arme else []
        partie = Partie(k, self.univers, Moment(2, Periode.MATIN), armes=arme,
                        arme_en_main=arme[0] if arme else None, armure="Veste renforcée")
        sauvegarder(partie, self.chemin_sauvegarde)
        self.dire(f"\nPartie sauvegardée : {self.chemin_sauvegarde}")
        self.dire(f"Kaito : {k.pv}/{k.pv_max} PV, {k.sm} en Santé mentale, {k.points_destin} points de destin.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        Demo().jouer()
    except (KeyboardInterrupt, EOFError):
        print("\nPartie interrompue.")


if __name__ == "__main__":
    main()
