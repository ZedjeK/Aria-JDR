"""Le plan du round par le LLM : l'étage 2 du combat à pied (REGLES.md 7.8).

Une requête par round demande au LLM l'intention de chaque PNJ à jouer, dans une liste fermée, d'après son caractère,
son arme et son état. Le code reste patron : le moral se teste d'abord, une intention illisible ou illégale (cible
morte, déjà prise à deux attaquants…) retombe sur l'IA par défaut pour ce PNJ, et si le serveur ne répond pas, ou
trop lentement, le round se joue entièrement par l'IA. Éteint par défaut.
"""

import json
import time
from dataclasses import dataclass, field

from aria import llm
from aria.combat import Combat, Combattant, Couvert, FichePnj, Moral
from aria.combat_auto import Choix, Intention, Plan, Registre, _adversaires
from aria.combat_joueur import etat_visible

NOM_OUTIL = "plan_du_round"
DELAI_PLAN = 25  # secondes : au-delà, le round se joue par l'IA du code
BUDGET_PLAN = 256  # réflexion : un choix à faire, pas un récit
PANNES_MAX = 2  # deux rounds de suite sans plan : on cesse de demander pour ce combat

SYSTEME = """Tu joues les ennemis d'un combat de jeu de rôle. Pour chaque PNJ à jouer, choisis ce qu'il veut faire ce round, dans la liste fermée de l'outil, d'après son caractère, son arme et son état. La cible est un identifiant de la liste. Fuir ou se rendre n'est permis qu'à un PNJ éprouvé. Réponds en appelant l'outil `plan_du_round` une seule fois, sans rien écrire d'autre."""

DESCRIPTION = ("Le plan du round : une entrée par PNJ à jouer. Intentions : attaquer (une cible), viser (une cible, "
               "tireur), s'abriter (tireur, se met à couvert), fuir ou se rendre (seulement un PNJ éprouvé).")


@dataclass
class Statistiques:
    """Ce que le plan a donné, pour juger l'étage 2 (le mini-banc, aria.banc_plan)."""

    appels: int = 0
    plans_valides: int = 0  # tous les PNJ présents, toutes les entrées lisibles et légales
    plans_partiels: int = 0  # utilisables, mais des PNJ ou des entrées retombent sur l'IA
    echecs: int = 0  # pas de plan : serveur muet, trop lent, réponse illisible
    durees: list[float] = field(default_factory=list)

    @property
    def mediane(self) -> float:
        ordonnees = sorted(self.durees)
        return ordonnees[len(ordonnees) // 2] if ordonnees else 0.0


class PlanificateurLLM:
    """À donner à `CombatAuto(planificateur=...)` : un plan par round, ou rien (l'IA joue)."""

    def __init__(self, serveur, session, budget: int = BUDGET_PLAN, delai: int = DELAI_PLAN):
        self.serveur, self.session, self.budget, self.delai = serveur, session, budget, delai
        self.pannes = 0
        self.derniere_erreur = ""  # ce que le serveur a répondu de travers, pour comprendre un plan raté
        self.stats = Statistiques()

    def __call__(self, combat: Combat, registre: Registre) -> Plan | None:
        if self.pannes >= PANNES_MAX:
            return None
        joues = [c for c in combat.ordre if self._a_planifier(combat, c)]
        adversaires = {}  # identifiant → combattant, pour chaque PNJ, et pour chaque cible possible
        for c in joues:
            for x in _adversaires(combat, c):
                adversaires[self._id(x)] = x
        if not joues:
            return None
        par_id = {self._id(c): c for c in joues}
        messages = [{"role": "system", "content": SYSTEME},
                    {"role": "user", "content": self.situation(combat, registre, joues, adversaires)}]
        self.stats.appels += 1
        debut = time.time()
        try:
            reponse = self.serveur.discuter(messages, [self.schema(par_id, adversaires)], self.budget,
                                            delai=self.delai, outil_impose=NOM_OUTIL)
        except llm.ErreurLLM as erreur:
            self.derniere_erreur = str(erreur)
            return self._echec(debut)
        entrees = self._entrees(reponse)
        self.stats.durees.append(round(time.time() - debut, 1))
        if entrees is None:
            self.pannes += 1
            self.stats.echecs += 1
            return None
        plan, complet = self.lire(entrees, combat, par_id, adversaires)
        if not plan:
            self.pannes += 1
            self.stats.echecs += 1
            return None
        self.pannes = 0
        if complet:
            self.stats.plans_valides += 1
        else:
            self.stats.plans_partiels += 1
        return plan

    # -- Ce qu'on demande

    def _id(self, combattant: Combattant) -> str:
        return self.session.identifiant(combattant)

    def _a_planifier(self, combat: Combat, c: Combattant) -> bool:
        """Un PNJ qui peut agir, que le MJ a nommé, et qui n'a pas déjà craqué (un fuyard court, un rendu ne joue plus)."""
        return (isinstance(c.fiche, FichePnj) and not c.drone and combat.peut_agir(c) and c.moral is Moral.NORMAL
                and c in self.session.pnj.values())

    def situation(self, combat: Combat, registre: Registre, joues: list[Combattant],
                  adversaires: dict[str, Combattant]) -> str:
        lignes = [f"Round {combat.round}. Décor : {combat.decor.value}.",
                  "Cibles possibles : " + ", ".join(f"{i} ({x.nom}, {etat_visible(x)}"
                                                    + (", à couvert" if x.couvert is not Couvert.AUCUN else "") + ")"
                                                    for i, x in adversaires.items()) + ".",
                  "PNJ à jouer :"]
        for c in joues:
            arme = c.arme.nom if c.arme else "sans arme"
            if c.arme and c.arme.munitions:
                arme += f" ({c.munitions_restantes()} balles)"
            raisons = combat.declencheurs_de_moral(c)
            etat = f"{etat_visible(c)}" + (", à couvert" if c.couvert is not Couvert.AUCUN else "")
            eprouve = f" ; éprouvé ({' ; '.join(raisons)}) : il peut fuir ou se rendre" if raisons else ""
            lignes.append(f"- {self._id(c)} ({c.nom}), caractère : {c.caractere or 'aucun en particulier'} ; "
                          f"{arme} ; {etat}{eprouve}")
        blesses = sorted(f"{a.nom} a blessé {b.nom}" for a, b in registre.blessures_precedentes)
        lignes.append("Au round précédent : " + (" ; ".join(blesses) if blesses else "personne n'a été blessé") + ".")
        return "\n".join(lignes)

    @staticmethod
    def schema(par_id: dict[str, Combattant], adversaires: dict[str, Combattant]) -> dict:
        entree = {"type": "object", "properties": {
            "pnj": {"type": "string", "enum": sorted(par_id)},
            "intention": {"type": "string", "enum": [i.value for i in Intention]},
            "cible": {"type": "string", "enum": sorted(adversaires)},
        }, "required": ["pnj", "intention"]}
        return {"type": "function", "function": {"name": NOM_OUTIL, "description": DESCRIPTION, "parameters": {
            "type": "object", "properties": {"plan": {"type": "array", "items": entree}}, "required": ["plan"]}}}

    # -- Ce qu'on en tire

    @staticmethod
    def _entrees(reponse: dict) -> list | None:
        """Les entrées du plan dans la réponse du serveur, ou None si elle n'a pas la forme attendue."""
        try:
            appel = reponse["choices"][0]["message"]["tool_calls"][0]["function"]
            if appel["name"] != NOM_OUTIL:
                return None
            arguments = appel["arguments"]
            arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            entrees = arguments["plan"]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        return entrees if isinstance(entrees, list) else None

    def lire(self, entrees: list, combat: Combat, par_id: dict[str, Combattant],
             adversaires: dict[str, Combattant]) -> tuple[Plan, bool]:
        """Le plan légal, et s'il est complet : tous les PNJ y sont, toutes les entrées valides. Une entrée illisible,
        illégale ou en double est écartée : ce PNJ suit l'IA par défaut."""
        plan, complet = {}, True
        for entree in entrees:
            choix = self._choix(entree, combat, par_id, adversaires)
            pnj = par_id.get(entree.get("pnj")) if isinstance(entree, dict) else None
            if choix is None or pnj in plan:
                complet = False
                continue
            plan[pnj] = choix
        return plan, complet and len(plan) == len(par_id)

    @staticmethod
    def _choix(entree, combat: Combat, par_id: dict[str, Combattant], adversaires: dict[str, Combattant]) -> Choix | None:
        if not isinstance(entree, dict) or entree.get("pnj") not in par_id:
            return None
        intention = next((i for i in Intention if i.value == entree.get("intention")), None)
        if intention is None:
            return None
        pnj = par_id[entree["pnj"]]
        if intention in (Intention.FUIR, Intention.SE_RENDRE):
            return Choix(intention) if combat.declencheurs_de_moral(pnj) else None
        if intention.veut_une_cible:
            cible = adversaires.get(entree.get("cible"))
            return Choix(intention, cible) if cible is not None and cible in _adversaires(combat, pnj) else None
        return Choix(intention)

    def _echec(self, debut: float) -> None:
        self.stats.durees.append(round(time.time() - debut, 1))
        self.stats.echecs += 1
        self.pannes += 1
        return None
