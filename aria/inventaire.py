"""L'inventaire (REGLES.md 13.5 et 13.9) : ce que le personnage porte, ce qu'il a sous la main, ses munitions.

L'inventaire est rangé dans la fiche du personnage (`Personnage.inventaire`), sous une forme que la sauvegarde
écrit telle quelle :

- `objets` : chaque objet porté, avec sa famille (arme, armure, portage, sac, outil, objet) et s'il est prêt ;
- `vrac` : les cartouches en vrac, par calibre ;
- `chargeurs` : les chargeurs, un par un, avec leur contenu (un chargeur entamé reste entamé).

Un personnage sans inventaire (`None`) est un personnage d'avant l'économie : il dégaine toute l'armurerie de
l'univers et recharge sans compter. Le banc d'essai et les vieilles sauvegardes s'en servent encore.
"""

import math
from dataclasses import dataclass

from aria.equipement import ARMES_A_DISTANCE, Arme, Propriete, Recharge
from aria.personnage import Caracteristique, Personnage

ARME, ARMURE, PORTAGE, SAC, OUTIL, OBJET = "arme", "armure", "portage", "sac", "outil", "objet"
FAMILLES = (ARME, ARMURE, PORTAGE, SAC, OUTIL, OBJET)
PRETS_DE_BASE = 3
BOITE = 20  # cartouches par boîte : une boîte entamée prend la place d'une boîte
SURCHARGE = -20
COMPETENCES_SURCHARGE = ("Athlétisme", "Esquive", "Discrétion")
GARNISSEUR, LAME, CHARGEUR_RAPIDE = "Garnisseur", "Lame-chargeur", "Chargeur rapide"
PRIX_CHARGEUR = 50
FUSILS = ("fusils", "fusils de précision")
GARNISSABLES = ("armes de poing", "armes intelligentes", *FUSILS)  # ce que le garnisseur sait garnir


class InventaireImpossible(ValueError):
    """Ce que l'inventaire ne permet pas : le message est renvoyé tel quel au MJ."""


@dataclass(frozen=True)
class Portage:
    """Un équipement de portage : il met des objets sous la main, sans rien ajouter à ce que le corps supporte."""

    nom: str
    sorte: str  # on n'en porte qu'un de chaque sorte
    prets: int
    pour: str = ""  # « une main », « dissimulable », « deux mains », « petits » ; vide : n'importe quel objet
    discret: bool = False
    malus: tuple[tuple[str, int], ...] = ()
    prix: int = 100


@dataclass(frozen=True)
class Sac:
    """Un sac : il ajoute des emplacements à ce que le corps supporte."""

    nom: str
    emplacements: int
    poches: int = 0  # des emplacements prêts, sur les côtés
    discret: bool = False
    malus: tuple[tuple[str, int], ...] = ()
    occupe_une_main: bool = False
    sacoche: bool = False  # se porte en plus d'un sac à dos
    prix: int = 100


PORTAGES = {p.nom: p for p in (
    Portage("Holster", "holster", 1, "une main", prix=50),
    Portage("Holster dissimulé", "holster dissimulé", 1, "dissimulable", discret=True, prix=100),
    Portage("Sangle d'arme", "sangle", 1, "deux mains", prix=50),
    Portage("Sangles de cuisse", "cuisse", 2, "petits", prix=100),
    Portage("Ceinture renforcée", "ceinture", 1, discret=True, prix=50),
    Portage("Ceinture tactique", "ceinture", 2, prix=100),
    Portage("Ceinture de combat", "ceinture", 3, prix=200),
    Portage("Gilet tactique léger", "gilet", 2, "petits", discret=True, prix=100),
    Portage("Gilet tactique moyen", "gilet", 4, "petits", prix=200),
    Portage("Gilet tactique lourd", "gilet", 6, "petits", malus=(("Discrétion", -10),), prix=500),
)}
SACS = {s.nom: s for s in (
    Sac("Sacoche", 2, discret=True, sacoche=True, prix=50),
    Sac("Sac à dos de ville", 4, discret=True, prix=100),
    Sac("Sac à dos tactique", 6, poches=2, prix=200),
    Sac("Sac de sport", 8, occupe_une_main=True, prix=100),
    Sac("Sac de randonnée", 10, poches=2, malus=(("Athlétisme", -10), ("Esquive", -10)), prix=200),
)}
OUTILS = {GARNISSEUR: 100, LAME: 10}  # leur prix ; la lame-chargeur se consomme
# Par action simple, selon Armes à distance (moins de 50, de 50 à 74, 75 et plus)
CADENCES = {"main": (3, 5, 7), GARNISSEUR: (6, 10, 14), LAME: (10, 10, 15)}
BONUS_ACTION_MINEURE = 2


def cadence(armes_a_distance: int, moyen: str = "main") -> int:
    """Le nombre de cartouches garnies en une action simple."""
    return CADENCES[moyen][0 if armes_a_distance < 50 else 1 if armes_a_distance < 75 else 2]


def a_chargeur(arme: Arme) -> bool:
    """Vrai pour une arme à chargeur amovible (ou à bande, à carquois) : elle se recharge en changeant de
    chargeur. Les autres (revolver, fusil à pompe, arbalète) se garnissent à la main."""
    return bool(arme.munitions) and (arme.chargeur.recharge is Recharge.MINEURE or arme.chargeur.capacite > 10)


def calibre(arme: Arme) -> str:
    """Le nom de ses munitions dans le vrac : son calibre, ou à défaut son propre nom (les flèches d'un arc)."""
    return arme.calibre or f"munitions de {arme.nom}"


def emplacements_arme(arme: Arme) -> float:
    if arme.usage_unique or arme.categorie in ("grenades", "armes de lancer"):
        return 0.5  # un petit objet
    if arme.a(Propriete.ENCOMBRANTE):
        return 3
    return 2 if arme.a(Propriete.DEUX_MAINS) else 1


def _genre_de_place(arme: Arme) -> str:
    if emplacements_arme(arme) == 0.5:
        return "petits"
    if arme.a(Propriete.DEUX_MAINS) or arme.a(Propriete.ENCOMBRANTE):
        return "deux mains"
    return "dissimulable" if arme.a(Propriete.DISSIMULABLE) else "une main"


class Inventaire:
    """L'inventaire d'un personnage, dans un univers (qui connaît ses armes)."""

    def __init__(self, perso: Personnage, univers):
        if perso.inventaire is None:
            raise InventaireImpossible(f"{perso.nom} n'a pas d'inventaire.")
        self.perso, self.univers, self.d = perso, univers, perso.inventaire

    @staticmethod
    def creer(perso: Personnage):
        """Donne un inventaire vide au personnage, s'il n'en a pas."""
        if perso.inventaire is None:
            perso.inventaire = {"objets": [], "vrac": {}, "chargeurs": []}

    # --- Lire -------------------------------------------------------------------------------------------

    @property
    def objets(self) -> list[dict]:
        return self.d["objets"]

    @property
    def chargeurs(self) -> list[dict]:
        return self.d["chargeurs"]

    @property
    def vrac(self) -> dict[str, int]:
        return self.d["vrac"]

    def trouver(self, nom: str, famille: str | None = None) -> dict:
        for o in self.objets:
            if o["nom"] == nom and famille in (None, o["famille"]):
                return o
        raise InventaireImpossible(f"{self.perso.nom} n'a pas « {nom} ». Il porte : {self.noms() or 'rien'}.")

    def a(self, nom: str, famille: str | None = None) -> bool:
        return any(o["nom"] == nom and famille in (None, o["famille"]) for o in self.objets)

    def noms(self, famille: str | None = None) -> list[str]:
        return [o["nom"] for o in self.objets if famille in (None, o["famille"])]

    def armes(self) -> list[Arme]:
        return [self.univers.arme(nom) for nom in self.noms(ARME)]

    def _portages(self) -> list[Portage]:
        return [PORTAGES[n] for n in self.noms(PORTAGE) if n in PORTAGES]

    def _sacs(self, portes_seulement: bool = True) -> list[Sac]:
        return [SACS[o["nom"]] for o in self.objets
                if o["famille"] == SAC and o["nom"] in SACS and (o.get("porte", True) or not portes_seulement)]

    # --- Les emplacements (13.9) ------------------------------------------------------------------------

    def _place(self, o: dict) -> float:
        """Ce qu'un objet prend : rien pour ce qui est porté sur soi (portage, sac, armure portée)."""
        if o["famille"] in (PORTAGE, SAC):
            return 0
        if o["famille"] == ARMURE:
            return 0 if o.get("portee") else 2
        if o["famille"] == ARME:
            return emplacements_arme(self.univers.arme(o["nom"]))
        return 0.5 if o["famille"] == OUTIL or o.get("petit") else 1

    def _genre(self, o: dict) -> str:
        if o["famille"] == ARME:
            return _genre_de_place(self.univers.arme(o["nom"]))
        return "petits" if self._place(o) == 0.5 else "objet"

    def capacite(self) -> int:
        """Ce que le corps supporte, sacs portés compris."""
        return 4 + self.perso.carac(Caracteristique.FORCE) // 10 + sum(s.emplacements for s in self._sacs())

    def _place_du_vrac(self) -> float:
        return sum(math.ceil(n / BOITE) * 0.5 for n in self.vrac.values() if n > 0)

    def utilises(self) -> float:
        return (sum(self._place(o) for o in self.objets) + 0.5 * len(self.chargeurs) + self._place_du_vrac())

    def surcharge(self) -> bool:
        return self.utilises() > self.capacite()

    def _verifier_le_poids(self, en_plus: float):
        if self.utilises() + en_plus > 2 * self.capacite():
            raise InventaireImpossible(f"{self.perso.nom} ne peut pas porter autant : {self.utilises() + en_plus:g} "
                                       f"emplacements, pour {self.capacite()} (le double au plus).")

    def prets(self) -> dict[str, float]:
        """Les emplacements prêts, par genre de place : « objet » pour n'importe quoi."""
        places = {"objet": float(PRETS_DE_BASE + sum(s.poches for s in self._sacs())),
                  "une main": 0.0, "dissimulable": 0.0, "deux mains": 0.0, "petits": 0.0}
        for p in self._portages():
            places[p.pour or "objet"] += p.prets
        return places

    def _libre(self) -> dict[str, float]:
        """Ce qui reste libre sous la main, par genre de place. Chaque objet prêt va d'abord dans sa place dédiée
        (une arme dans son holster, un chargeur dans le gilet), sinon dans une place ordinaire. Un compte
        « objet » négatif : il y a trop d'objets prêts."""
        libre = self.prets()
        demandes = [(self._genre(o), self._place(o)) for o in self.objets if o.get("pret")]
        demandes += [("petits", 0.5) for c in self.chargeurs if c.get("pret")]
        for genre, place in demandes:
            if genre in ("une main", "dissimulable", "deux mains"):
                # un holster ou une sangle tient une arme, quelle que soit sa taille ; une arme dissimulable
                # va aussi dans un holster ordinaire
                case = next((c for c in (["dissimulable", "une main"] if genre == "dissimulable" else [genre])
                             if libre[c] >= 1), None)
                if case:
                    libre[case] -= 1
                    continue
            elif genre == "petits" and libre["petits"] >= place:
                libre["petits"] -= place
                continue
            libre["objet"] -= place
        return libre

    def prets_en_trop(self) -> bool:
        return self._libre()["objet"] < -1e-9

    def _peut_etre_pret(self, objet: dict) -> bool:
        avant = objet.get("pret")
        objet["pret"] = True
        ok = not self.prets_en_trop()
        objet["pret"] = avant
        return ok

    # --- Ajouter, retirer, ranger -----------------------------------------------------------------------

    def ajouter(self, nom: str, famille: str, pret: bool | None = None, **details) -> dict:
        """Ajoute un objet. `pret` : None pour le mettre sous la main s'il y a la place, rangé sinon."""
        if famille not in FAMILLES:
            raise InventaireImpossible(f"Famille d'objet inconnue : « {famille} ».")
        objet = {"nom": nom, "famille": famille, "pret": False, **details}
        if famille == ARME:
            self.univers.arme(nom)  # elle doit exister dans l'univers
        if famille == PORTAGE:
            sorte = PORTAGES[nom].sorte
            if any(p.sorte == sorte for p in self._portages()):
                raise InventaireImpossible(f"{self.perso.nom} porte déjà un équipement de ce genre ({sorte}).")
        if famille == SAC:
            sac = SACS[nom]
            if any(s.sacoche == sac.sacoche for s in self._sacs()):
                raise InventaireImpossible(f"{self.perso.nom} porte déjà {'une sacoche' if sac.sacoche else 'un sac'}.")
            objet["porte"] = True
        self.objets.append(objet)
        try:
            self._verifier_le_poids(0)
        except InventaireImpossible:
            self.objets.remove(objet)
            raise
        if famille not in (PORTAGE, SAC, ARMURE) and pret is not False:
            if self._peut_etre_pret(objet):
                objet["pret"] = True
            elif pret:
                self.objets.remove(objet)
                raise InventaireImpossible(f"Plus de place sous la main pour « {nom} » : range autre chose d'abord.")
        return objet

    def retirer(self, nom: str, famille: str | None = None) -> dict:
        objet = self.trouver(nom, famille)
        self.objets.remove(objet)
        if objet["famille"] in (PORTAGE, SAC):
            self._ranger_ce_qui_depasse()
        return objet

    def _ranger_ce_qui_depasse(self):
        """Après avoir retiré un portage : ce qui n'a plus sa place sous la main retourne dans le sac."""
        prets = [o for o in self.chargeurs + self.objets if o.get("pret")]
        while self.prets_en_trop() and prets:
            prets.pop()["pret"] = False

    def preparer(self, nom: str):
        """Met un objet rangé sous la main."""
        objet = self.trouver(nom)
        if objet["famille"] in (PORTAGE, SAC, ARMURE):
            raise InventaireImpossible(f"« {nom} » se porte : il n'est ni prêt ni rangé.")
        if not self._peut_etre_pret(objet):
            raise InventaireImpossible(f"Plus de place sous la main pour « {nom} » : range autre chose d'abord.")
        objet["pret"] = True

    def ranger(self, nom: str):
        self.trouver(nom)["pret"] = False

    def est_pret(self, nom: str) -> bool:
        return bool(self.trouver(nom).get("pret"))

    # --- Les munitions (13.5) ---------------------------------------------------------------------------

    def ajouter_cartouches(self, arme: Arme, nombre: int):
        cle = calibre(arme)
        self.vrac[cle] = self.vrac.get(cle, 0) + nombre
        self._verifier_le_poids(0)

    def ajouter_chargeur(self, arme: Arme, cartouches: int | None = None, pret: bool | None = None) -> dict:
        """Un chargeur pour cette arme (un chargeur rapide pour une arme qui se garnit à la main), garni par défaut."""
        capacite = arme.chargeur.capacite
        chargeur = {"arme": arme.nom, "cartouches": capacite if cartouches is None else min(cartouches, capacite),
                    "capacite": capacite, "pret": False, "rapide": not a_chargeur(arme)}
        self.chargeurs.append(chargeur)
        self._verifier_le_poids(0)
        if pret is not False:
            chargeur["pret"] = True
            if self.prets_en_trop():
                chargeur["pret"] = False
        return chargeur

    def _chargeurs_de(self, arme: Arme, prets: bool | None = None) -> list[dict]:
        return [c for c in self.chargeurs if c["arme"] == arme.nom and (prets is None or bool(c.get("pret")) == prets)]

    def chargeur_garni(self, arme: Arme) -> dict | None:
        """Le chargeur prêt le plus garni pour cette arme, s'il en reste un qui n'est pas vide."""
        garnis = [c for c in self._chargeurs_de(arme, prets=True) if c["cartouches"] > 0]
        return max(garnis, key=lambda c: c["cartouches"]) if garnis else None

    def changer_chargeur(self, arme: Arme, restant: int) -> int:
        """Engage le chargeur prêt le plus garni ; celui qu'on retire est gardé, avec ce qu'il lui reste.
        Renvoie le nombre de cartouches dans l'arme."""
        nouveau = self.chargeur_garni(arme)
        if nouveau is None:
            ranges = sum(c["cartouches"] > 0 for c in self._chargeurs_de(arme, prets=False))
            raise InventaireImpossible(
                f"Plus de chargeur garni sous la main pour {arme.nom}"
                + (f" ({ranges} rangé(s) : il faut d'abord le sortir)." if ranges else
                   f" : il reste {self.vrac.get(calibre(arme), 0)} cartouche(s) en vrac à garnir à la main."))
        engage, nouveau["cartouches"] = nouveau["cartouches"], 0 if nouveau["rapide"] else restant
        if nouveau["rapide"]:
            # un chargeur rapide se vide dans le barillet : ce qui restait dans l'arme retourne au vrac
            self.vrac[calibre(arme)] = self.vrac.get(calibre(arme), 0) + restant
        return engage

    def moyen_de_garnir(self, arme: Arme) -> str:
        """Le meilleur moyen sous la main : une lame-chargeur (fusils), un garnisseur, ou la main."""
        if arme.categorie in FUSILS and self.a(LAME):
            return LAME
        return GARNISSEUR if arme.categorie in GARNISSABLES and self.a(GARNISSEUR) else "main"

    def garnir(self, arme: Arme, nombre: int, dans_l_arme: int | None = None) -> tuple[int, int | None]:
        """Garnit jusqu'à `nombre` cartouches prises dans le vrac. `dans_l_arme` : ce que contient l'arme si
        elle se garnit directement (un revolver, ou une arme à chargeur sans chargeur de rechange) ; sinon, le
        chargeur de rechange le moins vide. Renvoie (cartouches garnies, nouveau contenu de l'arme ou None).
        Une lame-chargeur utilisée est consommée."""
        cle = calibre(arme)
        dispo = self.vrac.get(cle, 0)
        if dispo <= 0:
            raise InventaireImpossible(f"Plus de cartouches en vrac pour {arme.nom} ({cle}).")
        cible = None
        if dans_l_arme is None:
            a_garnir = [c for c in self._chargeurs_de(arme) if c["cartouches"] < c["capacite"]]
            if not a_garnir:
                raise InventaireImpossible(f"Aucun chargeur à garnir pour {arme.nom} : ils sont pleins.")
            cible = max(a_garnir, key=lambda c: (bool(c.get("pret")), c["cartouches"]))
            place = cible["capacite"] - cible["cartouches"]
        else:
            place = arme.chargeur.capacite - dans_l_arme
            if place <= 0:
                raise InventaireImpossible(f"{arme.nom} est déjà pleine.")
        garnies = min(nombre, dispo, place)
        self.vrac[cle] = dispo - garnies
        if self.moyen_de_garnir(arme) == LAME:
            self.objets.remove(self.trouver(LAME))
        if cible is not None:
            cible["cartouches"] += garnies
            return garnies, None
        return garnies, dans_l_arme + garnies

    def regarnir_tout(self) -> dict[str, int]:
        """Hors combat : regarnit tous les chargeurs tant qu'il reste du vrac. Renvoie les cartouches garnies par arme."""
        garnies = {}
        for c in sorted(self.chargeurs, key=lambda c: (not c.get("pret"), -c["cartouches"])):
            arme = self.univers.arme(c["arme"])
            prises = min(c["capacite"] - c["cartouches"], self.vrac.get(calibre(arme), 0))
            if prises > 0:
                c["cartouches"] += prises
                self.vrac[calibre(arme)] -= prises
                garnies[arme.nom] = garnies.get(arme.nom, 0) + prises
        return garnies

    # --- Les malus et le résumé -------------------------------------------------------------------------

    def malus(self, competence: str) -> int:
        """La surcharge (−20 en Athlétisme, Esquive, Discrétion), plus ce que le portage et le sac font peser."""
        total = SURCHARGE if self.surcharge() and competence in COMPETENCES_SURCHARGE else 0
        for equipement in [*self._portages(), *self._sacs()]:
            total += sum(valeur for nom, valeur in equipement.malus if nom == competence)
        return total

    def resume(self) -> dict:
        """L'inventaire, pour l'état du personnage et la commande « inventaire »."""
        def ligne(o):
            return o["nom"] + (f" ({o['qualite']})" if o.get("qualite") else "")
        return {
            "emplacements": f"{self.utilises():g} / {self.capacite()}" + (" — surchargé" if self.surcharge() else ""),
            "prets": [ligne(o) for o in self.objets if o.get("pret")],
            "ranges": [ligne(o) for o in self.objets
                       if not o.get("pret") and o["famille"] not in (PORTAGE, SAC) and not o.get("portee")],
            "portes": [ligne(o) for o in self.objets if o.get("portee")],
            "portage": self.noms(PORTAGE) + self.noms(SAC),
            "chargeurs": [f"{c['arme']} : {c['cartouches']}/{c['capacite']}"
                          + (" (rapide)" if c["rapide"] else "") + ("" if c.get("pret") else ", rangé")
                          for c in self.chargeurs],
            "vrac": {cle: n for cle, n in self.vrac.items() if n > 0},
        }


class ReservePnj:
    """Les munitions d'un PNJ : quelques chargeurs garnis et une boîte, sans inventaire à tenir."""

    def __init__(self, arme: Arme | None, chargeurs: int = 2):
        self.chargeurs_restants = [arme.chargeur.capacite] * chargeurs if arme and arme.munitions else []
        self.cartouches = BOITE

    def chargeur_garni(self, arme: Arme):
        return bool(self.chargeurs_restants)

    def changer_chargeur(self, arme: Arme, restant: int) -> int:
        if not self.chargeurs_restants:
            raise InventaireImpossible(f"Plus de chargeur garni pour {arme.nom}.")
        return self.chargeurs_restants.pop()

    def moyen_de_garnir(self, arme: Arme) -> str:
        return "main"

    def garnir(self, arme: Arme, nombre: int, dans_l_arme: int | None = None) -> tuple[int, int | None]:
        contenu = dans_l_arme or 0
        garnies = min(nombre, self.cartouches, arme.chargeur.capacite - contenu)
        if garnies <= 0:
            raise InventaireImpossible(f"Plus de cartouches pour {arme.nom}.")
        self.cartouches -= garnies
        return garnies, contenu + garnies

    def malus(self, competence: str) -> int:
        return 0


def equipement_de_depart(perso: Personnage, univers, arme: str | None, armure: str | None, objets: list[str]):
    """L'inventaire de départ (REGLES.md 13.4) : l'arme avec deux chargeurs garnis et une boîte de 20 (une arme
    qui se garnit à la main : chargée, avec deux chargeurs rapides si c'est un revolver, et sa boîte), l'armure
    portée, les objets du métier."""
    Inventaire.creer(perso)
    inventaire = Inventaire(perso, univers)
    if arme:
        fiche = univers.arme(arme)
        inventaire.ajouter(arme, ARME, pret=True, charge=fiche.chargeur.capacite if fiche.munitions else 0)
        if fiche.munitions and not fiche.usage_unique:
            if a_chargeur(fiche):
                inventaire.ajouter_chargeur(fiche)  # le second : le premier est dans l'arme
            elif fiche.categorie == "armes de poing":
                inventaire.ajouter_chargeur(fiche)
                inventaire.ajouter_chargeur(fiche)
            inventaire.ajouter_cartouches(fiche, BOITE)
    if armure:
        inventaire.ajouter(armure, ARMURE, portee=True)
    for objet in objets:
        inventaire.ajouter(objet, OBJET)
    return inventaire
