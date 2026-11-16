"""Le tour du joueur dans un combat à pied : l'écran, le menu d'actions légales, ses réactions et la boucle.

Référence : REGLES.md 7.8. Le moteur construit le menu : chaque entrée est légale, ou grisée avec sa raison. Les
ennemis ne montrent que leur état (indemne, blessé, gravement blessé, à terre, en fuite, rendu), jamais leurs PV,
sauf si le joueur le demande. « Parler » et « Autre action » rendent la main au MJ pour cette action seulement ;
« Fuir » ouvre une poursuite.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum

from aria import magie
from aria.choix import Choisir, Option
from aria.combat import (
    ActionImpossible,
    BonusMajeure,
    Combat,
    Combattant,
    Couvert,
    Decor,
    Defense,
    Moral,
    RapportAttaque,
    TypeAction,
)
from aria.combat_auto import (
    Action,
    CombatAuto,
    Fin,
    Geste,
    Reactions,
    RapportTour,
    _cote,
    _en_lice,
    executer,
)
from aria.equipement import Arme, Recharge
from aria.personnage import Etat, Personnage
from aria.resolution import Resultat, chance_de_reussite

PAUSE_ENTRE_LES_ACTIONS = 0.6  # secondes, entre deux actions de PNJ : le temps de lire


# --- Ce que le joueur voit --------------------------------------------------------------------

@dataclass
class Ecran:
    """Tout ce par quoi le combat parle au joueur et l'interroge, et ses réglages."""

    dire: Callable[[str], None]
    choisir: Choisir
    entree: Callable[[str], str]
    pv_exacts: bool = False  # les PV exacts des ennemis, au lieu de leur seul état
    choisir_sa_defense: bool = False  # « Je choisis ma défense » : esquiver ou riposter, au lieu du code
    pause: Callable[[float], None] = time.sleep
    delai: float = PAUSE_ENTRE_LES_ACTIONS
    faits: list[str] = field(default_factory=list)  # ce qui s'est passé depuis le dernier récit du MJ

    def fait(self, produire: Callable[["Ecran"], list[str]], titre: str = "") -> None:
        """Montre ce qui vient de se passer, et le garde pour le récit. Le MJ ne reçoit jamais les PV exacts des
        ennemis, même si le joueur les voit."""
        lignes = produire(self)
        if lignes:
            self.dire("\n".join(([titre] if titre else []) + lignes))
        self.faits.extend(produire(replace(self, pv_exacts=False)) if self.pv_exacts else lignes)


def jet(resultat: Resultat) -> str:
    return f"{resultat.jet:02d} pour {resultat.valeur} : {resultat.degre.libelle}"


def etat_visible(combattant: Combattant) -> str:
    """L'état d'un combattant, tel qu'on le voit : sans chiffres."""
    fiche = combattant.fiche
    if combattant.moral is Moral.RENDU:
        return "rendu"
    if combattant.moral is Moral.PARTI:
        return "parti"
    if not combattant.conscient:
        return "à terre"
    if combattant.moral is Moral.EN_FUITE:
        return "en fuite"
    if fiche.blessure_grave:
        return "gravement blessé"
    return "blessé" if fiche.pv < fiche.pv_max_base else "indemne"


def _du_cote_du_joueur(combattant: Combattant) -> bool:
    return _cote(combattant) == "joueurs"


def _etat_chiffre(combattant: Combattant, ecran: Ecran) -> str:
    fiche = combattant.fiche
    if _du_cote_du_joueur(combattant) or ecran.pv_exacts:
        grave = ", blessure grave" if fiche.blessure_grave else ""
        etat = "" if fiche.etat is Etat.ACTIF else f", {fiche.etat.value}"
        return f"{fiche.pv}/{fiche.pv_max} PV{grave}{etat}"
    return etat_visible(combattant)


def budget_restant(combattant: Combattant) -> str:
    restants = [(combattant.budget.restants(TypeAction.DEPLACEMENT), "déplacement"),
                (combattant.budget.restants(TypeAction.SIMPLE), "action simple"),
                (combattant.budget.restants(TypeAction.MINEURE), "action mineure")]
    return ", ".join(f"{n} {nom}{'s' if n > 1 else ''}" for n, nom in restants)


def _arme_et_munitions(combattant: Combattant) -> str:
    arme = combattant.arme
    if arme is None:
        return "à mains nues" + (f" ({combattant.arme_lachee.nom} à tes pieds)" if combattant.arme_lachee else "")
    texte = arme.nom
    if arme.munitions:
        texte += f" ({combattant.munitions_restantes()}/{arme.chargeur.capacite})"
    if combattant.arme_enrayee is arme:
        texte += ", enrayée"
    return texte


def ecran_du_combat(combat: Combat, joueur: Combattant, ecran: Ecran) -> list[str]:
    """L'écran du joueur : le round, le décor, l'initiative, chacun avec son état, et ce qu'il a en main."""
    ordre = [f"{'→ ' if c is combat.au_tour_de else ''}{c.nom} ({_etat_chiffre(c, ecran)})" for c in combat.ordre
             if _cote(c) is not None]
    lignes = [f"— Round {combat.round} — décor {combat.decor.value} —", "Initiative : " + " ; ".join(ordre)]
    couvert = ", à couvert" if joueur.couvert is not Couvert.AUCUN else ""
    lignes.append(f"Toi : {_etat_chiffre(joueur, ecran)}{couvert} ; {_arme_et_munitions(joueur)}")
    if isinstance(joueur.fiche, Personnage) and joueur.fiche.pm_max:
        lignes[-1] += f" ; {joueur.fiche.pm}/{joueur.fiche.pm_max} PM"
    return lignes


# --- Le journal des jets ---------------------------------------------------------------------

def _blessure(rapport: RapportAttaque, victime: Combattant, ecran: Ecran) -> list[str]:
    b = rapport.blessure
    armure = f", l'armure en arrête {rapport.protection}" if rapport.protection else ""
    if _du_cote_du_joueur(victime) or ecran.pv_exacts:
        lignes = [f"  → {rapport.touche} est touché : {rapport.degats_bruts} dégâts{armure}. PV {b.pv_avant} → {b.pv_apres}."]
    else:
        lignes = [f"  → {rapport.touche} est touché ({rapport.degats_bruts} dégâts{armure})."]
    if b.blessure_grave:
        lignes.append("  → BLESSURE GRAVE !")
    if b.test_constitution:
        lignes.append(f"  → Test de Constitution : {jet(b.test_constitution)}.")
    if b.etat is not Etat.ACTIF:
        lignes.append(f"  → {rapport.touche} est {'à terre' if not _du_cote_du_joueur(victime) else b.etat.value}.")
    return lignes


def lignes_de_l_attaque(rapport: RapportAttaque, combat: Combat, ecran: Ecran) -> list[str]:
    """Les mêmes lignes de jets que le MJ recevra pour raconter (lot suivant)."""
    par_nom = {c.nom: c for c in combat.ordre}
    lignes = [f"  {rapport.attaquant} attaque {rapport.cible} : {jet(rapport.attaque)}."]
    if rapport.defense:
        lignes.append(f"  {rapport.cible} se défend : {jet(rapport.defense)}.")
    if rapport.touche and rapport.blessure:
        lignes += _blessure(rapport, par_nom[rapport.touche], ecran)
    elif rapport.touche:
        lignes.append(f"  → {rapport.touche} est touché, sans effet.")
    elif rapport.issue.value == "défenseur":
        lignes.append("  → Le coup est évité.")
    else:
        lignes.append("  → Raté.")
    return lignes + [f"  → {effet}" for effet in rapport.effets]


_TEXTE_DU_GESTE = {
    Geste.FUIR: "{qui} court vers la sortie.",
    Geste.RAMASSER: "{qui} ramasse son arme.",
    Geste.DEBLOQUER: "{qui} débloque son arme.",
    Geste.RECHARGER: "{qui} recharge.",
    Geste.COUVERT: "{qui} se met à couvert.",
    Geste.VISER: "{qui} prend le temps de viser.",
}


def lignes_du_tour(rapport: RapportTour, combat: Combat, ecran: Ecran) -> list[str]:
    """Ce qui s'est passé pendant un tour, en lignes."""
    qui = rapport.qui.nom
    lignes = []
    if rapport.moral:
        m = rapport.moral
        verbe = {Moral.NORMAL: "tient bon", Moral.EN_FUITE: "craque et s'enfuit", Moral.RENDU: "craque et se rend"}[m.moral]
        lignes.append(f"  {qui} est éprouvé ({' ; '.join(m.declencheurs)}). Moral : {jet(m.test)} → {verbe}.")
    for evenement in rapport.evenements:
        if evenement.attaque:
            lignes += lignes_de_l_attaque(evenement.attaque, combat, ecran)
        elif evenement.action.geste in _TEXTE_DU_GESTE:
            lignes.append("  " + _TEXTE_DU_GESTE[evenement.action.geste].format(qui=qui))
    if rapport.passe and not rapport.moral:
        lignes.append(f"  {qui} ne fait rien.")
    return lignes + lignes_de_fin_de_tour(rapport)


def lignes_de_fin_de_tour(rapport: RapportTour) -> list[str]:
    """Ce que la fin d'un tour déclenche : les mourants qui testent, les effets persistants qui mordent."""
    lignes = [f"  {nom} agonise. Constitution : {jet(test)}." for nom, test in rapport.mourants]
    for s in rapport.sauvegardes:
        lignes.append(f"  {s.qui} : {s.sort}, sauvegarde {jet(s.test)}" + (f", {s.degats} dégâts" if s.degats else "")
                      + (" : l'effet s'arrête." if s.fini else "."))
    return lignes


def lignes_du_sort(rapport: magie.RapportSort, combat: Combat, ecran: Ecran) -> list[str]:
    lignes = [f"  {rapport.lanceur} lance {rapport.sort.nom} : {jet(rapport.test)} ({rapport.pm_depenses} PM)."]
    if rapport.pv_puises:
        lignes.append(f"  → À court de PM, il y laisse {rapport.pv_puises} PV.")
    for cible in rapport.cibles:
        if cible.attaque:
            lignes += lignes_de_l_attaque(cible.attaque, combat, ecran)[1:]
        elif cible.gain:
            lignes.append(f"  → {cible.nom} récupère {cible.gain} PV.")
        elif cible.effet:
            lignes.append(f"  → {cible.nom} : {cible.effet}.")
    if rapport.retour:
        lignes.append(f"  → {rapport.retour}")
    return lignes


# --- Les réactions du joueur -----------------------------------------------------------------

class ReactionsDuJoueur(Reactions):
    """Les choix du joueur pendant les actions : sa défense (s'il l'a demandé) et le bonus de ses réussites majeures."""

    def __init__(self, joueur: Combattant, ecran: Ecran):
        self.joueur, self.ecran = joueur, ecran

    def defense(self, attaquant: Combattant, cible: Combattant) -> Defense | None:
        if cible is not self.joueur or not self.ecran.choisir_sa_defense:
            return None
        valeurs = {d: Combat.valeur_de_defense(cible, d) for d in Defense}
        options = [Option(f"Esquiver ({chance_de_reussite(valeurs[Defense.ESQUIVE])} % de réussir)"),
                   Option(f"Riposter ({chance_de_reussite(valeurs[Defense.RIPOSTE])} % de réussir)")]
        choix = self.ecran.choisir(f"{attaquant.nom} t'attaque. Comment réagis-tu ?", options)
        return (Defense.ESQUIVE, Defense.RIPOSTE)[choix]

    def bonus_majeure(self, source: Combattant, victime: Combattant, options: list[BonusMajeure]) -> BonusMajeure:
        if source is not self.joueur:
            return BonusMajeure.DE_SUPPLEMENTAIRE
        choix = self.ecran.choisir("Réussite majeure ! Quel bonus ?", [Option(o.value) for o in options])
        return options[choix]


# --- Le menu ---------------------------------------------------------------------------------

class Nature(Enum):
    FIN_DU_TOUR = "fin du tour"
    PARLER = "parler"
    AUTRE_ACTION = "autre action"
    FUITE = "fuite"


@dataclass(frozen=True)
class Sortie:
    """Pourquoi la boucle du joueur s'arrête : il finit son tour, rend la main au MJ pour une action (avec ce qu'il
    a écrit), ou fuit (avec ceux qui le poursuivent)."""

    nature: Nature
    texte: str = ""
    poursuivants: tuple[Combattant, ...] = ()


@dataclass
class Entree:
    option: Option
    faire: Callable[[], Sortie | None] | None = None


def _raison_du_budget(combattant: Combattant, action: TypeAction) -> str:
    """Pourquoi le budget du round ne permet plus cette action, ou rien s'il la permet."""
    if combattant.budget.peut(action):
        return ""
    if action is TypeAction.DEPLACEMENT:
        return "plus de déplacement possible ce round"
    if action is TypeAction.SIMPLE:
        deux = combattant.budget.utilise[TypeAction.DEPLACEMENT] == 2
        return "tu t'es déplacé deux fois" if deux else "action simple déjà utilisée"
    return "action mineure déjà utilisée"


class TourDuJoueur:
    """Le tour du joueur : construit le menu, exécute ce qu'il choisit, rend ses résultats par l'écran."""

    def __init__(self, session, auto: CombatAuto, ecran: Ecran):
        self.session, self.auto, self.ecran = session, auto, ecran
        self.combat, self.joueur = auto.combat, session.joueur

    # -- La boucle

    def jouer(self) -> Sortie:
        """Joue le tour du joueur jusqu'à ce qu'il le finisse, rende la main au MJ ou fuie."""
        self.ecran.dire("\n" + "\n".join(ecran_du_combat(self.combat, self.joueur, self.ecran)))
        while True:
            entrees = self.entrees()
            if not any(e.option.active for e in entrees[:-1]):
                self.ecran.dire("  Plus rien à faire : ton tour se termine.")
                return Sortie(Nature.FIN_DU_TOUR)
            self.ecran.dire(f"\nIl te reste : {budget_restant(self.joueur)}")
            choix = self.ecran.choisir("C'est ton tour. Que fais-tu ?", [e.option for e in entrees])
            entree = entrees[choix]
            sortie = entree.faire()
            if sortie is not None:
                return sortie
            if self.auto.fin() is not Fin.EN_COURS:
                return Sortie(Nature.FIN_DU_TOUR)

    def entrees(self) -> list[Entree]:
        entrees = [self._attaquer(), self._viser(), self._recharger()]
        if self.joueur.arme_enrayee is not None and self.joueur.arme_enrayee is self.joueur.arme:
            entrees.append(self._debloquer())
        entrees += [self._changer_d_arme(), self._se_mettre_a_couvert()]
        if self.session.a_la_magie and self.session.sorts_connus(self.joueur):
            entrees.append(self._lancer_un_sort())
        if any(a is not self.joueur for a in self.combat.ordre if _du_cote_du_joueur(a)):
            entrees.append(self._stabiliser())
        entrees += [self._parler(), self._autre_action(), self._fuir(),
                    Entree(Option("Terminer le tour"), lambda: Sortie(Nature.FIN_DU_TOUR))]
        return entrees

    # -- Ce qui se passe quand il choisit

    def _essayer(self, action: Callable[[], object]) -> bool:
        """Fait faire l'action par le moteur, qui peut la refuser : le joueur lit pourquoi, et son tour continue."""
        try:
            action()
        except ActionImpossible as erreur:
            self.ecran.dire(f"  Impossible : {erreur}")
            return False
        return True

    def _sous_menu(self, titre: str, options: list[Option]) -> int | None:
        """Un sous-menu avec « Retour » en dernier ; None si le joueur revient."""
        choix = self.ecran.choisir(titre, options + [Option("Retour")])
        return None if choix == len(options) else choix

    def _adversaires(self) -> list[Combattant]:
        return _en_lice(self.combat, "ennemis")

    # -- Attaquer, viser, recharger

    def _attaquer(self) -> Entree:
        j, arme = self.joueur, self.joueur.arme_en_main
        raison = _raison_du_budget(j, TypeAction.SIMPLE)
        if not raison and arme.zone:
            raison = f"{arme.nom} est une arme de zone : passe par « Autre action »"
        if not raison and j.arme_enrayee is arme:
            raison = "ton arme est enrayée : débloque-la d'abord"
        if not raison and not arme.corps_a_corps and arme.munitions and j.munitions_restantes() == 0:
            raison = "chargeur vide : recharge d'abord"
        if not raison and not self._adversaires():
            raison = "plus personne à frapper"
        return Entree(Option("Attaquer…", raison), None if raison else self._choisir_une_cible)

    def _choisir_une_cible(self) -> Sortie | None:
        j, adversaires = self.joueur, self._adversaires()
        options = []
        for cible in adversaires:
            chance = self.combat.chance_de_toucher(j, cible)
            couvert = ", à couvert" if cible.couvert is not Couvert.AUCUN and not j.arme_en_main.corps_a_corps else ""
            options.append(Option(f"{cible.nom} ({etat_visible(cible)}{couvert}) — {chance} % de toucher"))
        choix = self._sous_menu("Qui attaques-tu ?", options)
        if choix is not None:
            self._essayer(lambda: self._attaque_de(j, adversaires[choix]))
        return None

    def _attaque_de(self, attaquant: Combattant, cible: Combattant):
        rapport = executer(self.combat, attaquant, Action(Geste.ATTAQUER, cible), self.auto.reactions)
        self.auto.registre.noter(attaquant, cible, rapport)
        self.ecran.fait(lambda ecran: lignes_de_l_attaque(rapport, self.combat, ecran))

    def _viser(self) -> Entree:
        j, arme = self.joueur, self.joueur.arme_en_main
        raison = _raison_du_budget(j, TypeAction.MINEURE)
        if not raison and arme.corps_a_corps:
            raison = "viser ne sert qu'avec une arme de tir"
        if not raison and j.arme_enrayee is arme:
            raison = "ton arme est enrayée"
        if not raison and arme.munitions and j.munitions_restantes() == 0:
            raison = "chargeur vide"
        if not raison and j.a_vise:
            raison = "tu as déjà visé ce round"
        if not raison and j.budget.utilise[TypeAction.DEPLACEMENT]:
            raison = "tu t'es déplacé ce round"
        return Entree(Option("Viser (+20 au tir de ce round, mais tu ne pourras plus bouger)", raison),
                      None if raison else lambda: self._action(lambda: self.combat.viser(j), "  Tu prends le temps de viser."))

    def _recharger(self) -> Entree:
        j, arme = self.joueur, self.joueur.arme
        if not arme or not arme.munitions:
            return Entree(Option("Recharger", "ton arme n'a pas de chargeur"))
        restantes = j.munitions_restantes()
        mineure = arme.chargeur.recharge is Recharge.MINEURE
        raison = _raison_du_budget(j, TypeAction.MINEURE if mineure else TypeAction.SIMPLE)
        if not raison and restantes >= arme.chargeur.capacite:
            raison = "le chargeur est plein"
        return Entree(Option(f"Recharger ({restantes}/{arme.chargeur.capacite})", raison),
                      None if raison else lambda: self._action(lambda: self.combat.recharger(j), "  Tu recharges."))

    def _debloquer(self) -> Entree:
        j = self.joueur
        raison = _raison_du_budget(j, TypeAction.MINEURE)
        return Entree(Option("Débloquer ton arme enrayée", raison),
                      None if raison else lambda: self._action(lambda: self.combat.debloquer(j), "  Tu débloques ton arme."))

    def _action(self, faire: Callable[[], object], texte: str) -> None:
        if self._essayer(faire):
            self.ecran.fait(lambda _: [texte])

    # -- Changer d'arme, se mettre à couvert

    def _armes_en_reserve(self) -> list[tuple[str, Arme, bool]]:
        """(libellé, arme, rangée) : l'arme à ses pieds, puis celles qu'il possède. Une arme rangée au fond du sac
        coûte une action simple à sortir (REGLES.md 13.9)."""
        j, s = self.joueur, self.session
        armes = []
        if j.arme_lachee:
            armes.append((f"Ramasser {j.arme_lachee.nom}", j.arme_lachee, False))
        for arme in s.armes_du_joueur():
            if arme is j.arme or arme is j.arme_lachee:
                continue
            rangee = bool(s.inventaire and s.inventaire.a(arme.nom, "arme") and not s.inventaire.est_pret(arme.nom))
            armes.append((f"Prendre {arme.nom}" + (" (rangée dans ton sac : action simple)" if rangee else ""), arme, rangee))
        return armes

    def _changer_d_arme(self) -> Entree:
        j = self.joueur
        armes = self._armes_en_reserve()
        if not armes:
            return Entree(Option("Changer d'arme…", "tu n'as pas d'autre arme"))
        if not any(j.budget.peut(TypeAction.SIMPLE if rangee else TypeAction.MINEURE) for _, _, rangee in armes):
            return Entree(Option("Changer d'arme…", _raison_du_budget(j, TypeAction.MINEURE)))

        def choisir() -> Sortie | None:
            options = [Option(libelle, _raison_du_budget(j, TypeAction.SIMPLE if rangee else TypeAction.MINEURE))
                       for libelle, _, rangee in armes]
            choix = self._sous_menu("Quelle arme ?", options)
            if choix is not None:
                _, arme, rangee = armes[choix]
                self._action(lambda: self.combat.degainer(j, arme, rangee=rangee), f"  Tu prends {arme.nom} en main.")
            return None

        return Entree(Option("Changer d'arme…"), choisir)

    def _se_mettre_a_couvert(self) -> Entree:
        j, c = self.joueur, self.combat
        raison = ""
        if c.decor is Decor.DEGAGE:
            raison = "le décor est dégagé : il n'y a rien pour s'abriter"
        elif j.couvert is not Couvert.AUCUN:
            raison = "tu es déjà à couvert"
        elif j.a_vise:
            raison = "tu as visé : tu ne peux plus bouger ce round"
        else:
            raison = _raison_du_budget(j, TypeAction.DEPLACEMENT)
        gain = {Decor.ENCOMBRE: "−20", Decor.FORTIFIE: "−40"}.get(c.decor, "")
        return Entree(Option(f"Se mettre à couvert (les tireurs auront {gain})", raison),
                      None if raison else lambda: self._action(lambda: c.se_mettre_a_couvert(j), "  Tu te mets à couvert."))

    # -- Lancer un sort, stabiliser

    def _sorts_a_une_cible(self) -> list[magie.Sort]:
        """Les sorts du joueur qui visent une cible : ni zone, ni utilitaire (ceux-là, c'est « Autre action »)."""
        return [s for s in self.session.sorts_connus(self.joueur).values()
                if not s.a(magie.ProprieteSort.ZONE) and s.effet is not magie.Effet.UTILITAIRE]

    def _lancer_un_sort(self) -> Entree:
        j, sorts = self.joueur, self._sorts_a_une_cible()
        raison = _raison_du_budget(j, TypeAction.SIMPLE) or ("" if sorts else "aucun de tes sorts ne vise une cible")
        return Entree(Option("Lancer un sort…", raison), None if raison else self._choisir_un_sort)

    def _choisir_un_sort(self) -> Sortie | None:
        sorts = self._sorts_a_une_cible()
        pm = self.joueur.fiche.pm
        options = [Option(f"{s.nom} ({s.effet.value}, {s.puissance.value}, coût {s.cout}, tu as {pm} PM)") for s in sorts]
        choix = self._sous_menu("Quel sort ?", options)
        if choix is None:
            return None
        sort = sorts[choix]
        cibles = self._adversaires() if sort.effet.nocif else [c for c in self.combat.ordre
                                                               if _du_cote_du_joueur(c) and c.conscient]
        options = [Option("Toi" if c is self.joueur else f"{c.nom} ({_etat_chiffre(c, self.ecran)})") for c in cibles]
        choix = self._sous_menu(f"{sort.nom} : sur qui ?", options)
        if choix is not None:
            self._essayer(lambda: self._sort_sur(sort, cibles[choix]))
        return None

    def _sort_sur(self, sort: magie.Sort, cible: Combattant):
        s = self.session
        rapport = magie.lancer(s.des, self.joueur, sort, [cible], self.combat,
                               cible.couvert if sort.effet is magie.Effet.ATTAQUE else Couvert.AUCUN, s.moment,
                               coute_sm=s.univers.genre == "Horreur")
        for sur in rapport.cibles:
            if sur.attaque:
                self.auto.registre.noter(self.joueur, cible, sur.attaque)
        self.ecran.fait(lambda ecran: lignes_du_sort(rapport, self.combat, ecran))

    def _stabiliser(self) -> Entree:
        j = self.joueur
        raison = _raison_du_budget(j, TypeAction.SIMPLE)
        mourants = [c for c in self.combat.ordre if _du_cote_du_joueur(c) and c.fiche.etat is Etat.MOURANT]
        if not raison and not mourants:
            raison = "aucun allié n'est mourant"

        def choisir() -> Sortie | None:
            chance = chance_de_reussite(j.valeur("Médecine"), combat=False)
            options = [Option(f"{c.nom} (mourant) — {chance} % de réussir") for c in mourants]
            choix = self._sous_menu("Qui stabilises-tu ?", options)
            if choix is not None:
                self._essayer(lambda: self._stabilisation_de(mourants[choix]))
            return None

        return Entree(Option("Stabiliser…", raison), None if raison else choisir)

    def _stabilisation_de(self, mourant: Combattant):
        test = self.combat.stabiliser(self.joueur, mourant)
        self.ecran.fait(lambda _: [f"  Tu tentes de stabiliser {mourant.nom} : {jet(test)}."
                                   + (" Il est stabilisé." if test.reussi else "")])

    # -- Rendre la main au MJ, fuir

    def _parler(self) -> Entree:
        raison = _raison_du_budget(self.joueur, TypeAction.MINEURE)
        return Entree(Option("Parler (action mineure)", raison),
                      None if raison else lambda: self._rendre_la_main(Nature.PARLER, TypeAction.MINEURE, "Ce que tu dis : "))

    def _autre_action(self) -> Entree:
        raison = _raison_du_budget(self.joueur, TypeAction.SIMPLE)
        return Entree(Option("Autre action… (action simple)", raison),
                      None if raison else lambda: self._rendre_la_main(Nature.AUTRE_ACTION, TypeAction.SIMPLE,
                                                                       "Ce que tu fais : "))

    def _rendre_la_main(self, nature: Nature, cout: TypeAction, invite: str) -> Sortie | None:
        """Le joueur écrit ce qu'il fait : le MJ le joue, pour cette action seulement. Le moteur en déduit le coût."""
        texte = self.ecran.entree(invite).strip()
        if not texte:
            return None
        if not self._essayer(lambda: self.combat._agir(self.joueur, cout)):
            return None
        return Sortie(nature, texte)

    def _fuir(self) -> Entree:
        j = self.joueur
        raison = ""
        if j.a_vise:
            raison = "tu as visé : tu ne peux plus bouger ce round"
        elif j.budget.restants(TypeAction.DEPLACEMENT) < 2:
            raison = "il te faut deux déplacements : tu as déjà agi ce round"
        elif not self._adversaires():
            raison = "plus personne ne te poursuit"
        return Entree(Option("Fuir (deux déplacements, les ennemis te poursuivent)", raison),
                      None if raison else self._confirmer_la_fuite)

    def _confirmer_la_fuite(self) -> Sortie | None:
        poursuivants = tuple(self._adversaires())
        choix = self.ecran.choisir(f"Tu fuis : {', '.join(c.nom for c in poursuivants)} te poursuivront. Tu es sûr ?",
                                   [Option("Oui, je fuis"), Option("Non")])
        if choix == 1:
            return None
        for _ in range(2):
            self.combat.deplacer(self.joueur)
        return Sortie(Nature.FUITE, poursuivants=poursuivants)


# --- La boucle du combat -----------------------------------------------------------------------

def ouvrir_le_combat(session, ecran: Ecran) -> CombatAuto:
    """La boucle d'un combat à pied de cette session : les PNJ jouent seuls, le joueur par son menu."""
    return CombatAuto(session.combat, reactions=ReactionsDuJoueur(session.joueur, ecran))


def jouer_les_pnj(auto: CombatAuto, ecran: Ecran) -> list[RapportTour]:
    """Les tours des PNJ jusqu'à celui du joueur, montrés un à un, avec une courte pause entre eux."""
    def montrer(rapport: RapportTour):
        ecran.fait(lambda e: lignes_du_tour(rapport, auto.combat, e), titre=f"\n{rapport.qui.nom} :")
        if rapport.evenements or rapport.moral:
            ecran.pause(ecran.delai)

    return auto.avancer(montrer)


def mener_le_combat(session, auto: CombatAuto, ecran: Ecran,
                    recit: Callable[[Fin], None] | None = None) -> "Sortie | Fin":
    """Mène le combat jusqu'à sa fin (une `Fin`) ou jusqu'à ce que le MJ doive reprendre la main (une `Sortie` :
    parler, autre action, fuite). Rappelée après le MJ, elle reprend le tour du joueur là où il en était.
    `recit(fin)` : appelée juste avant chaque menu du joueur (avec `Fin.EN_COURS`) et à la fin du combat, pour que le
    MJ raconte ce qu'`ecran.faits` a gardé depuis le dernier récit."""
    combat = auto.combat
    while True:
        jouer_les_pnj(auto, ecran)
        fin = auto.fin()
        if fin is not Fin.EN_COURS:
            if recit:
                recit(fin)
            return fin
        if combat.au_tour_de is not session.joueur:
            raise ActionImpossible("Plus personne ne peut agir.")
        if recit:
            recit(Fin.EN_COURS)
        sortie = TourDuJoueur(session, auto, ecran).jouer()
        if sortie.nature in (Nature.PARLER, Nature.AUTRE_ACTION, Nature.FUITE):
            return sortie
        fin = auto.fin()
        if fin is not Fin.EN_COURS:  # son action a fini le combat : le round ne se clôt pas
            if recit:
                recit(fin)
            return fin
        mourants, sauvegardes = auto.finir_le_tour()
        ecran.fait(lambda _: lignes_de_fin_de_tour(RapportTour(session.joueur, combat.round, mourants=mourants,
                                                               sauvegardes=sauvegardes)))
        fin = auto.fin()
        if fin is not Fin.EN_COURS:
            if recit:
                recit(fin)
            return fin


def lignes_de_fin(fin: Fin) -> list[str]:
    """La fin du combat, en une phrase de faits (le MJ en raconte les suites)."""
    return {Fin.VICTOIRE: ["\nPlus aucun ennemi ne tient : le combat est fini."],
            Fin.DEFAITE: ["\nTu ne tiens plus debout : le combat est perdu."],
            Fin.ESSOUFFLE: ["\nPlus personne n'arrive à finir l'autre : le combat s'essouffle."]}.get(fin, [])


def ouvrir_la_poursuite(session, poursuivants: tuple[Combattant, ...], zone: str) -> dict:
    """Une fuite à pied : une poursuite (REGLES.md 12.3) avec les ennemis encore en lice pour poursuivants."""
    return session.appeler("debut_poursuite", {"fuyard": "joueur",
                                               "poursuivants": [session.identifiant(c) for c in poursuivants],
                                               "zone": zone})
