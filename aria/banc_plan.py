"""Le mini-banc du plan du round : juge si le LLM qui choisit pour les PNJ (REGLES.md 7.8, étage 2) vaut d'être allumé.

Une dizaine de situations de combat, jouées deux fois, soit une vingtaine d'appels au vrai MJ (quelques minutes).
Critères pour allumer l'interrupteur, avec le jugement de l'auteur sur quelques combats :
  - des plans valides du premier coup : 95 % au moins ;
  - une durée médiane de 15 secondes au plus ;
  - tous les pièges de caractère réussis (un prudent éprouvé ne fonce pas ; un téméraire éprouvé ne fuit pas).

Lancer, GPU libre (il charge le MJ qualifié) :
    .venv\\Scripts\\python.exe -m aria.banc_plan
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass

from aria import banc
from aria.combat import Combat
from aria.combat_auto import Intention, Plan, Registre
from aria.combat_plan import DELAI_PLAN, PlanificateurLLM
from aria.outils import Session
from aria.personnage import Etat

REPETITIONS = 2
SEUIL_VALIDES = 0.95
SEUIL_DUREE = 15.0

FONCER = {Intention.ATTAQUER, Intention.VISER}
PARTIR = {Intention.FUIR, Intention.SE_RENDRE}
PAS_FONCER = PARTIR | {Intention.S_ABRITER}


@dataclass(frozen=True)
class Scene:
    nom: str
    preparer: Callable[[Session], None]
    piege: str | None = None  # ce que le caractère interdit ou impose, en une phrase
    attendu: Callable[[Plan, Session], bool] | None = None  # vrai si le plan respecte le piège


def _combat(*pnj: tuple[str, str, str, dict]):
    """Un combat contre ces PNJ (identifiant, nom, arme, particularités), avant le tour de personne."""
    def preparer(session: Session):
        for identifiant, nom, arme, plus in pnj:
            banc._pnj(session, identifiant, nom, arme)
            c = session.pnj[identifiant]
            c.caractere = plus.get("caractere", "")
            c.fiche.pv = plus.get("pv", c.fiche.pv)
            if plus.get("a_terre"):
                c.fiche.etat = Etat.INCONSCIENT
            if plus.get("a_sec"):
                c.munitions[c.arme] = 0
        session.appeler("debut_combat", {"pnj": [p[0] for p in pnj]})
        session.journal.clear()
    return preparer


def _intention(session: Session, plan: Plan, identifiant: str) -> Intention | None:
    choix = plan.get(session.pnj[identifiant])
    return choix.intention if choix else None


def _parmi(identifiant: str, intentions: set[Intention]) -> Callable[[Plan, Session], bool]:
    return lambda plan, session: _intention(session, plan, identifiant) in intentions


SCENES = (
    Scene("deux couteaux", _combat(("a", "Voyou", "Couteau", {"caractere": "colérique"}),
                                   ("b", "Brute", "Couteau", {"caractere": "froid"}))),
    Scene("couteau et tireur", _combat(("a", "Voyou", "Couteau", {"caractere": "impatient"}),
                                       ("b", "Tireur", "Pistolet lourd", {"caractere": "prudent"}))),
    Scene("trois contre un", _combat(("a", "Voyou", "Couteau", {"caractere": "rancunier"}),
                                     ("b", "Brute", "Couteau", {"caractere": "fier"}),
                                     ("c", "Tireur", "Pistolet lourd", {"caractere": "cynique"}))),
    Scene("tireur seul", _combat(("a", "Tireur", "Pistolet lourd", {"caractere": "méfiant"}))),
    Scene("un blessé, un indemne", _combat(("a", "Voyou", "Couteau", {"caractere": "nerveux", "pv": 4}),
                                           ("b", "Tireur", "Pistolet lourd", {"caractere": "susceptible"}))),
    Scene("indemne et prudent : fuir est interdit", _combat(("a", "Tireur", "Pistolet lourd", {"caractere": "prudent"})),
          "un PNJ indemne n'a pas le droit de fuir ni de se rendre",
          lambda plan, s: _intention(s, plan, "a") not in PARTIR),
    Scene("prudent éprouvé", _combat(("a", "Tireur", "Pistolet lourd", {"caractere": "prudent", "pv": 3})),
          "un prudent à moitié mort ne fonce pas", _parmi("a", PAS_FONCER)),
    Scene("téméraire éprouvé", _combat(("a", "Voyou", "Couteau", {"caractere": "téméraire", "pv": 3})),
          "un téméraire à moitié mort ne fuit pas et ne se rend pas", _parmi("a", FONCER)),
    Scene("loyal, son camp à terre", _combat(("a", "Voyou", "Couteau", {"caractere": "loyal jusqu'à l'entêtement"}),
                                             ("b", "Brute", "Couteau", {"a_terre": True}),
                                             ("c", "Tireur", "Pistolet lourd", {"a_terre": True})),
          "un loyal obstiné reste au combat", _parmi("a", FONCER)),
    Scene("tireur à sec", _combat(("a", "Tireur", "Pistolet lourd", {"caractere": "impatient", "a_sec": True}))),
)


@dataclass
class Essai:
    scene: str
    complet: bool  # plan valide du premier coup : tous les PNJ, toutes les entrées légales
    utilisable: bool
    duree: float
    piege: bool | None  # None : pas de piège ; vrai : respecté
    intentions: list[str]
    erreur: str = ""


def jouer(serveur, scene: Scene, graine: int) -> Essai:
    session = banc.nouvelle_session(graine)
    scene.preparer(session)
    planificateur = PlanificateurLLM(serveur, session)
    combat: Combat = session.combat
    plan = planificateur(combat, Registre())
    s = planificateur.stats
    piege = None if scene.attendu is None else bool(plan) and scene.attendu(plan, session)
    intentions = [f"{c.nom} : {choix.intention.value}" + (f" → {choix.cible.nom}" if choix.cible else "")
                  for c, choix in (plan or {}).items()]
    return Essai(scene.nom, s.plans_valides == 1, bool(plan), s.durees[0] if s.durees else 0.0, piege, intentions,
                 planificateur.derniere_erreur)


@dataclass
class Bilan:
    essais: list[Essai]

    @property
    def taux_valides(self) -> float:
        return sum(e.complet for e in self.essais) / len(self.essais)

    @property
    def mediane(self) -> float:
        durees = sorted(e.duree for e in self.essais)
        return durees[len(durees) // 2]

    @property
    def pieges_rates(self) -> list[Essai]:
        return [e for e in self.essais if e.piege is False]

    @property
    def concluant(self) -> bool:
        return self.taux_valides >= SEUIL_VALIDES and self.mediane <= SEUIL_DUREE and not self.pieges_rates


def lancer(serveur, afficher=print, repetitions: int = REPETITIONS, scenes=SCENES) -> Bilan:
    essais = []
    for scene in scenes:
        for repetition in range(repetitions):
            essai = jouer(serveur, scene, repetition + 1)
            essais.append(essai)
            marque = "✓" if essai.complet else "·" if essai.utilisable else "✗"
            piege = "" if essai.piege is None else "  piège " + ("respecté" if essai.piege else "RATÉ")
            afficher(f"  {marque} {scene.nom:<42} {essai.duree:>5.1f} s{piege}")
            for ligne in essai.intentions:
                afficher(f"      {ligne}")
            if not essai.utilisable and essai.erreur:
                afficher(f"      (aucun plan : {essai.erreur})")
    bilan = Bilan(essais)
    afficher(f"\nPlans valides du premier coup : {bilan.taux_valides:.0%} (seuil {SEUIL_VALIDES:.0%})")
    afficher(f"Durée médiane : {bilan.mediane:.1f} s (seuil {SEUIL_DUREE:.0f} s, délai {DELAI_PLAN} s)")
    afficher(f"Pièges de caractère ratés : {len(bilan.pieges_rates)}")
    afficher("Verdict des chiffres : " + ("concluant, à toi de juger sur quelques combats."
                                          if bilan.concluant else "pas concluant : on s'arrête à l'étage 1."))
    return bilan


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from aria import jeu
    with jeu.mj_charge(print) as mj:
        if mj is None:
            return
        lancer(mj[0])


if __name__ == "__main__":
    main()
