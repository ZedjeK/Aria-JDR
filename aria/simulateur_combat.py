"""Le simulateur de combats : des centaines de combats à pied joués par l'IA des deux côtés, pour régler le moral, le
couvert et la maladresse (REGLES.md 7.2, 7.4 et 7.8) et vérifier qu'ils tiennent ce que les règles promettent.

Lancer un scénario, ou tous :
    .venv\\Scripts\\python.exe -m aria.simulateur_combat [nombre de combats]
"""

import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field

from aria import chemins, pnj
from aria.combat import Combat, Combattant, Decor, FichePnj, Moral
from aria.combat_auto import CombatAuto, Fin
from aria.demo import KAITO
from aria.des import Des
from aria.equipement import Armure
from aria.inventaire import ReservePnj
from aria.univers import Univers, charger_univers

UNIVERS = chemins.UNIVERS / "cyberpunk.json"
BRETTEUR, TIREUR = "bretteur", "tireur"
ARME_DU_JOUEUR, ARMURE_DU_JOUEUR = "Pistolet lourd Arasaka", "Veste renforcée"
ARMES = {BRETTEUR: "Machette", TIREUR: "Pistolet lourd"}
GRAINE = 2026


def _moyenne_des(base: int, nombre: int, faces: int) -> int:
    return base + nombre * (faces + 1) // 2


@dataclass(frozen=True)
class Scenario:
    """Un combat type : le joueur débutant (Kaito) contre des ennemis, chacun une menace et un profil."""

    nom: str
    ennemis: tuple[tuple[str, str], ...]  # (menace, profil)
    decor: Decor = Decor.ENCOMBRE


SCENARIOS = (
    Scenario("un voyou faible", ((pnj.FAIBLE, BRETTEUR),)),
    Scenario("deux voyous moyens, un couteau et un tireur", ((pnj.MOYENNE, BRETTEUR), (pnj.MOYENNE, TIREUR))),
    Scenario("deux voyous moyens, à découvert", ((pnj.MOYENNE, BRETTEUR), (pnj.MOYENNE, TIREUR)), Decor.DEGAGE),
    Scenario("trois voyous faibles", ((pnj.FAIBLE, BRETTEUR), (pnj.FAIBLE, TIREUR), (pnj.FAIBLE, TIREUR))),
    Scenario("un professionnel", ((pnj.FORTE, TIREUR),)),
    Scenario("un professionnel et un voyou moyen", ((pnj.FORTE, TIREUR), (pnj.MOYENNE, BRETTEUR))),
    Scenario("une élite", ((pnj.ELITE, BRETTEUR),)),
)


def _ennemi(univers: Univers, numero: int, menace: str, profil: str) -> Combattant:
    """Un ennemi moyen de sa menace (REGLES.md 15.2) : son combat, ses PV, une armure légère et son arme."""
    (base, nombre, faces), (base_pv, faces_pv), _ = pnj.MENACES[menace]
    fiche = FichePnj(f"{menace.capitalize()} {numero}", combat=_moyenne_des(base, nombre, faces),
                     pv_max_base=base_pv + (faces_pv + 1) // 2, dexterite=_moyenne_des(*pnj.DEXTERITE))
    arme = univers.arme(ARMES[profil])
    combattant = Combattant(fiche, "ennemis", arme, Armure("Armure de voyou", pnj.ARMURES["légère"][menace]))
    combattant.reserve = ReservePnj(arme)
    return combattant


def _joueur(univers: Univers) -> Combattant:
    kaito = univers.creer_personnage("Netrunner", **KAITO)
    arme = univers.arme(ARME_DU_JOUEUR)
    joueur = Combattant(kaito, "joueur", arme, univers.armure(ARMURE_DU_JOUEUR))
    joueur.reserve = ReservePnj(arme)
    return joueur


@dataclass
class Bilan:
    """Ce que valent les combats d'un scénario."""

    scenario: Scenario
    issues: Counter = field(default_factory=Counter)
    rounds: list[int] = field(default_factory=list)
    pv_perdus: list[int] = field(default_factory=list)
    ennemis: Counter = field(default_factory=Counter)  # ce que sont devenus les ennemis, à la fin

    @property
    def combats(self) -> int:
        return len(self.rounds)

    def taux(self, issue: Fin) -> float:
        return self.issues[issue] / self.combats

    @property
    def rounds_moyens(self) -> float:
        return statistics.mean(self.rounds)

    @property
    def rounds_mediane(self) -> float:
        return statistics.median(self.rounds)

    @property
    def pv_perdus_moyens(self) -> float:
        return statistics.mean(self.pv_perdus)

    def ligne(self) -> str:
        fin = self.ennemis
        total = sum(fin.values()) or 1
        return (f"{self.scenario.nom:<46} victoire {self.taux(Fin.VICTOIRE):4.0%}  défaite {self.taux(Fin.DEFAITE):4.0%}"
                f"  rounds {self.rounds_moyens:4.1f} (méd. {self.rounds_mediane:g})  PV perdus {self.pv_perdus_moyens:4.1f}"
                f"  ennemis : à terre {fin['à terre'] / total:3.0%} partis {fin['parti'] / total:3.0%} "
                f"rendus {fin['rendu'] / total:3.0%}")


def _devenir_de(ennemi: Combattant) -> str:
    if ennemi.moral is Moral.PARTI:
        return "parti"
    if ennemi.moral is Moral.RENDU:
        return "rendu"
    return "à terre" if not ennemi.conscient else "debout"


def simuler(scenario: Scenario, combats: int = 500, graine: int = GRAINE) -> Bilan:
    """Joue `combats` combats du scénario, l'IA menant tout le monde. Chaque combat a sa propre graine."""
    univers = charger_univers(UNIVERS)
    bilan = Bilan(scenario)
    for numero in range(combats):
        des = Des(graine + numero)
        joueur = _joueur(univers)
        ennemis = [_ennemi(univers, i + 1, menace, profil) for i, (menace, profil) in enumerate(scenario.ennemis)]
        combat = Combat(des, [joueur, *ennemis], univers.curseur, tour_par_tour=True, decor=scenario.decor)
        auto = CombatAuto(combat, mene=lambda combattant: True)
        pv_depart, dernier_round = joueur.fiche.pv, 1
        while auto.fin() is Fin.EN_COURS:
            tours = auto.avancer()
            if not tours:
                break  # garde-fou : plus personne ne peut agir
            dernier_round = tours[-1].round
        bilan.issues[auto.fin()] += 1
        bilan.rounds.append(dernier_round)
        bilan.pv_perdus.append(pv_depart - joueur.fiche.pv)
        bilan.ennemis.update(_devenir_de(e) for e in ennemis)
    return bilan


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    combats = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    for scenario in SCENARIOS:
        print(simuler(scenario, combats).ligne())


if __name__ == "__main__":
    main()
