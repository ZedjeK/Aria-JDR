"""Un combat à pied dans la partie : le code le mène, le MJ le raconte (REGLES.md 7.8).

Le MJ parle à l'ouverture (`debut_combat`, inchangé), juste avant chaque menu du joueur (ce qui s'est passé depuis son
dernier tour, sans outils), puis à la fin (le récit, puis `fin_combat`). Quand le joueur choisit « Parler » ou « Autre
action », ou fuit, la main revient au MJ pour cette action seulement, avec des outils sans attaque ni dégâts.
Si un appel au MJ échoue, le combat continue avec les seules lignes du moteur.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from aria.choix import Choisir
from aria.combat import Combat, Decor
from aria.combat_auto import Fin, _cote
from aria.combat_plan import PlanificateurLLM
from aria.combat_joueur import (
    Ecran,
    Nature,
    Sortie,
    etat_visible,
    lignes_de_fin,
    mener_le_combat,
    ouvrir_le_combat,
)
from aria.outils import OUTILS_A_PIED, Session
from aria.table import Table


class Recit(Enum):
    """Quand le MJ raconte (le réglage « Récit en combat »)."""

    PAR_ROUND = "round"  # avant chaque menu du joueur : le défaut
    A_LA_FIN = "fin"  # une seule fois, à la fin du combat
    AUCUN = "aucun"  # jamais : le code écrit lui-même les moments forts


@dataclass(frozen=True)
class ReglagesDeCombat:
    recit: Recit = Recit.PAR_ROUND
    pv_exacts: bool = False  # voir les PV exacts des ennemis, au lieu de leur état
    choisir_sa_defense: bool = False  # « Je choisis ma défense »
    pnj_par_le_llm: bool = False  # le LLM planifie le round des PNJ (étage 2) : éteint par défaut

    @staticmethod
    def depuis_dict(brut) -> "ReglagesDeCombat":
        """Tolérant : une valeur inconnue ou mal typée prend sa valeur par défaut."""
        if not isinstance(brut, dict):
            return ReglagesDeCombat()
        recit = next((r for r in Recit if r.value == brut.get("recit")), Recit.PAR_ROUND)
        return ReglagesDeCombat(recit, brut.get("pv_exacts") is True, brut.get("choisir_sa_defense") is True,
                                brut.get("pnj_par_le_llm") is True)


MESSAGE_RECIT = """[Combat : récit] Voici ce qui s'est passé, dans l'ordre. Ces faits sont exacts : ne change rien, n'ajoute rien.
{faits}
États : {etats}.
Décor : {decor}.
Raconte-le en trois à cinq phrases, dans l'ordre. Aucun chiffre : ni PV, ni dégâts, ni jets. N'invente aucun ennemi, aucune arme, aucun effet. Ne décide rien à la place du joueur. N'appelle aucun outil et ne lui demande pas ce qu'il fait : son menu s'affiche après ton récit."""

MESSAGE_FIN = """[Combat : fin] {issue}
Faits depuis le dernier récit :
{faits}
États : {etats}.
Raconte la fin du combat en trois à cinq phrases, d'après ces faits seulement et sans chiffre. {suite}
Puis appelle `fin_combat` avec les moments forts du combat, en trois phrases au plus."""

ISSUES = {
    Fin.VICTOIRE: ("Les ennemis ne tiennent plus : tombés, rendus ou partis.", ""),
    Fin.DEFAITE: ("Le joueur est hors de combat : le moteur a fixé son état (voir États).",
                  "Ne dis pas qu'il meurt si son état ne le dit pas. Raconte ce que font ensuite les ennemis, sans "
                  "nouveau coup."),
    Fin.ESSOUFFLE: ("Plus personne n'arrive à finir l'autre.", "Les combattants se séparent."),
}

MESSAGE_ACTION = """[Combat : action du joueur] Faits depuis le dernier récit :
{faits}
Pendant son tour, le joueur fait : « {texte} ». Le moteur a déjà déduit {cout}. Joue-le : un jet de base si l'issue est incertaine, sans attaque ni dégâts de son fait. Raconte en quelques phrases, puis rends-lui la main. N'appelle `fin_combat` que si le combat s'arrête vraiment (reddition, accord, ennemis qui partent)."""

MESSAGE_FUITE = """[Combat : fuite] Faits depuis le dernier récit :
{faits}
Le joueur fuit à pied (deux déplacements dépensés). Ceux qui le poursuivent : {poursuivants}. Raconte son départ en deux ou trois phrases. Puis appelle `fin_combat` (moments forts en trois phrases au plus), puis `debut_poursuite` avec le fuyard « joueur », ces poursuivants (leurs identifiants : {identifiants}) et une zone qui convient au lieu."""

COUTS = {Nature.PARLER: "son action mineure", Nature.AUTRE_ACTION: "son action simple"}
AUCUN_FAIT = "(rien de nouveau)"


class CombatDePartie:
    """Un combat à pied d'une partie : l'écran du joueur, le MJ qui raconte, et la boucle du code."""

    def __init__(self, session: Session, table: Table, dire: Callable[[str], None], choisir: Choisir,
                 entree: Callable[[str], str], raconter: Callable[[Callable], None],
                 reglages: ReglagesDeCombat = ReglagesDeCombat()):
        """`raconter(jouer_tour)` : le jeu joue un tour du MJ (avec ses outils), en montre les lignes et la narration."""
        self.session, self.table, self.dire, self.raconter, self.reglages = session, table, dire, raconter, reglages
        self.ecran = Ecran(dire, choisir, entree, pv_exacts=reglages.pv_exacts,
                           choisir_sa_defense=reglages.choisir_sa_defense)

    def jouer(self) -> None:
        """Mène le combat jusqu'à son terme : sa fin, ou une action que le MJ a close avec `fin_combat`."""
        s = self.session
        planificateur = PlanificateurLLM(self.table.serveur, s) if self.reglages.pnj_par_le_llm else None
        auto = ouvrir_le_combat(s, self.ecran, planificateur)
        while s.a_pied:
            resultat = mener_le_combat(s, auto, self.ecran, self._avant_le_menu)
            if isinstance(resultat, Fin):
                self._finir(resultat)
                return
            self._rendre_la_main(resultat)

    # -- Ce que le MJ reçoit

    def _faits(self) -> str:
        """Les faits gardés depuis le dernier récit, que le MJ va recevoir : ils sont ensuite oubliés."""
        faits = "\n".join(self.ecran.faits) or AUCUN_FAIT
        self.ecran.faits.clear()
        return faits

    def _etats(self) -> str:
        c: Combat = self.session.combat
        return " ; ".join(f"{x.nom} : {etat_visible(x)}" for x in c.ordre if _cote(x) is not None)

    def _decor(self) -> str:
        return {Decor.DEGAGE: "dégagé, rien pour s'abriter", Decor.ENCOMBRE: "encombré, on peut s'y mettre à couvert",
                Decor.FORTIFIE: "fortifié, de bons abris"}[self.session.combat.decor]

    def _avant_le_menu(self, fin: Fin) -> None:
        """Juste avant le menu du joueur : le MJ raconte ce qui s'est passé depuis son dernier tour."""
        if fin is not Fin.EN_COURS or self.reglages.recit is not Recit.PAR_ROUND or not self.ecran.faits:
            return
        c = self.session.combat
        message = MESSAGE_RECIT.format(faits=self._faits(), etats=self._etats(), decor=self._decor())
        narration = self.table.raconter_le_combat(message, f"[Combat : le round {c.round} a été raconté.]")
        if narration:
            self.dire("\n" + narration)

    def _rendre_la_main(self, sortie: Sortie) -> None:
        """Parler, Autre action ou Fuir : le MJ joue cette action seulement, avec les outils d'un combat à pied."""
        s = self.session
        if sortie.nature is Nature.FUITE:
            noms = ", ".join(c.nom for c in sortie.poursuivants)
            identifiants = ", ".join(s.identifiant(c) for c in sortie.poursuivants)
            message = MESSAGE_FUITE.format(faits=self._faits(), poursuivants=noms, identifiants=identifiants)
            outils = OUTILS_A_PIED | {"debut_poursuite"}
        else:
            message = MESSAGE_ACTION.format(faits=self._faits(), texte=sortie.texte, cout=COUTS[sortie.nature])
            outils = None
        self._jouer_le_mj(message, outils)

    def _jouer_le_mj(self, message: str, outils: frozenset[str] | None) -> None:
        self.session.main_du_mj = outils
        try:
            self.raconter(lambda: self.table.tour(message))
        finally:
            self.session.main_du_mj = None

    # -- La fin

    def _finir(self, fin: Fin) -> None:
        s = self.session
        for ligne in lignes_de_fin(fin):
            self.dire(ligne)
        if self.reglages.recit is not Recit.AUCUN:
            issue, suite = ISSUES[fin]
            message = MESSAGE_FIN.format(issue=issue, faits=self._faits(), etats=self._etats(), suite=suite)
            self._jouer_le_mj(message, frozenset({"fin_combat"}))
        if s.combat is not None:  # le MJ n'a pas répondu, ou n'a pas appelé fin_combat : le code la ferme
            s.appeler("fin_combat", {"moments_forts": self._moments_forts(fin)})

    def _moments_forts(self, fin: Fin) -> str:
        c = self.session.combat
        adversaires = ", ".join(x.nom for x in c.ordre if _cote(x) == "ennemis") or "personne"
        issue = {Fin.VICTOIRE: "Les ennemis ne tenaient plus.", Fin.DEFAITE: "Le personnage est resté à terre.",
                 Fin.ESSOUFFLE: "Le combat s'est essoufflé."}[fin]
        return f"Combat contre {adversaires}, {c.round} round{'s' if c.round > 1 else ''}. {issue}"
