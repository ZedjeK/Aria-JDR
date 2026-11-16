"""Le dossier de données et ce qu'il contient : réglages, journal des opérations, sauvegardes.

Tout ce que l'appli écrit va dans %USERPROFILE%\\.Aria-JDR : rien dans %APPDATA%, %LOCALAPPDATA% ni %TEMP%.
Chaque fonction prend en option le dossier à utiliser (les tests passent un dossier jetable).
"""

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from appli import identite

FICHIER_REGLAGES = "reglages.json"
FICHIER_JOURNAL = "journal.json"
DOSSIER_SAUVEGARDES = "sauvegardes"  # une copie datée de chaque fichier avant qu'il soit modifié
DOSSIER_CACHE = "cache"  # le cache de l'interface (et la décompression de l'exe)
DOSSIER_SECRETS = "secrets"  # chiffrés par DPAPI pour le compte de l'utilisateur
JOURNAL_MAX = 500
ELEMENTS_MIN, ELEMENTS_MAX = 1, 12
VITESSES = ("lente", "normale", "rapide")
RECITS = ("round", "fin", "aucun")  # quand le MJ raconte un combat : à chaque round, à la fin, jamais


def _racine(racine: Path | None) -> Path:
    return Path(racine) if racine is not None else identite.dossier_donnees()


def assurer(racine: Path | None = None) -> Path:
    """Crée le dossier et ses sous-dossiers s'ils manquent. Lève une OSError si c'est impossible."""
    dossier = _racine(racine)
    for sous_dossier in (DOSSIER_SAUVEGARDES, DOSSIER_CACHE, DOSSIER_SECRETS):
        (dossier / sous_dossier).mkdir(parents=True, exist_ok=True)
    return dossier


def _ecrire_json(chemin: Path, valeur) -> None:
    """Écrit à côté puis remplace : une coupure en pleine écriture ne laisse pas un fichier tronqué."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    temporaire.write_text(json.dumps(valeur, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaire, chemin)


def _entier(valeur, defaut: int) -> int:
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else defaut


@dataclass
class Fond:
    """Le fond animé, réglages obligatoires de toute appli Aria : fond.actif, fond.vitesse, fond.minimum, fond.maximum."""

    actif: bool = True
    vitesse: str = "normale"
    minimum: int = 2
    maximum: int = 5

    def assaini(self) -> "Fond":
        """Bornes ramenées entre 1 et 12 et remises dans l'ordre, vitesse inconnue ramenée à « normale »."""
        bas = min(max(_entier(self.minimum, 2), ELEMENTS_MIN), ELEMENTS_MAX)
        haut = min(max(_entier(self.maximum, 5), ELEMENTS_MIN), ELEMENTS_MAX)
        vitesse = self.vitesse.strip().lower() if isinstance(self.vitesse, str) else "normale"
        return Fond(actif=self.actif is not False, vitesse=vitesse if vitesse in VITESSES else "normale",
                    minimum=min(bas, haut), maximum=max(bas, haut))


@dataclass
class Combat:
    """Les réglages du combat à pied : le récit du MJ, les PV des ennemis, le choix de sa défense."""

    recit: str = "round"
    pv_exacts: bool = False
    choisir_sa_defense: bool = False
    pnj_par_le_llm: bool = False  # le LLM choisit les actions des PNJ, un plan par round : plus lent, éteint par défaut

    def assaini(self) -> "Combat":
        recit = self.recit if isinstance(self.recit, str) and self.recit in RECITS else "round"
        return Combat(recit, self.pv_exacts is True, self.choisir_sa_defense is True, self.pnj_par_le_llm is True)


@dataclass
class Reglages:
    """Les réglages de l'appli, enregistrés dans reglages.json. Jamais de secret ici : voir appli.coffre."""

    fond: Fond = field(default_factory=Fond)
    combat: Combat = field(default_factory=Combat)
    proposer_installation: bool = True  # sans effet tant que l'exe ne s'installe pas
    chercher_mises_a_jour: bool = True  # sans effet tant que les mises à jour ne sont pas là

    def assaini(self) -> "Reglages":
        return Reglages(fond=(self.fond if isinstance(self.fond, Fond) else Fond()).assaini(),
                        combat=(self.combat if isinstance(self.combat, Combat) else Combat()).assaini(),
                        proposer_installation=self.proposer_installation is not False,
                        chercher_mises_a_jour=self.chercher_mises_a_jour is not False)

    def en_dict(self) -> dict:
        return {"fond": asdict(self.fond),
                "combat": {"recit": self.combat.recit, "pvExacts": self.combat.pv_exacts,
                           "choisirSaDefense": self.combat.choisir_sa_defense, "pnjParLeLlm": self.combat.pnj_par_le_llm},
                "proposerInstallation": self.proposer_installation, "chercherMisesAJour": self.chercher_mises_a_jour}

    @staticmethod
    def depuis_dict(brut) -> "Reglages":
        """Un fichier modifié à la main ne casse rien : tout ce qui est illisible prend sa valeur par défaut."""
        if not isinstance(brut, dict):
            return Reglages()
        fond = brut.get("fond")
        fond = fond if isinstance(fond, dict) else {}
        combat = brut.get("combat")
        combat = combat if isinstance(combat, dict) else {}
        return Reglages(
            fond=Fond(actif=fond.get("actif", True), vitesse=fond.get("vitesse", "normale"),
                      minimum=fond.get("minimum", 2), maximum=fond.get("maximum", 5)),
            combat=Combat(recit=combat.get("recit", "round"), pv_exacts=combat.get("pvExacts", False),
                          choisir_sa_defense=combat.get("choisirSaDefense", False),
                          pnj_par_le_llm=combat.get("pnjParLeLlm", False)),
            proposer_installation=brut.get("proposerInstallation", True),
            chercher_mises_a_jour=brut.get("chercherMisesAJour", True)).assaini()


def charger_reglages(racine: Path | None = None) -> Reglages:
    """Les réglages enregistrés ; ceux par défaut si le fichier est absent, illisible ou incohérent."""
    try:
        texte = (_racine(racine) / FICHIER_REGLAGES).read_text(encoding="utf-8")
        return Reglages.depuis_dict(json.loads(texte))
    except (OSError, ValueError):
        return Reglages()


def enregistrer_reglages(reglages: Reglages, racine: Path | None = None) -> None:
    """Lève une OSError si l'écriture échoue."""
    _ecrire_json(_racine(racine) / FICHIER_REGLAGES, reglages.assaini().en_dict())


_VERROU_JOURNAL = threading.Lock()


def noter(type_: str, bilan: str, racine: Path | None = None, quand: datetime | None = None) -> None:
    """Ajoute une opération au journal (les 500 dernières). Ne lève jamais : un journal qui ne s'écrit pas ne doit pas
    faire échouer l'opération elle-même. Jamais de secret dans un bilan."""
    try:
        with _VERROU_JOURNAL:
            dossier = _racine(racine)
            entrees = lire_journal(dossier)
            entrees.append({"date": (quand or datetime.now()).isoformat(timespec="seconds"), "type": type_, "bilan": bilan})
            _ecrire_json(dossier / FICHIER_JOURNAL, entrees[-JOURNAL_MAX:])
    except (OSError, ValueError):
        pass  # dossier en lecture seule, fichier verrouillé : l'opération a eu lieu quand même


def lire_journal(racine: Path | None = None) -> list[dict]:
    """Les opérations enregistrées, de la plus ancienne à la plus récente ; aucune si le fichier est absent ou illisible."""
    try:
        contenu = json.loads((_racine(racine) / FICHIER_JOURNAL).read_text(encoding="utf-8"))
        return [e for e in contenu if isinstance(e, dict)] if isinstance(contenu, list) else []
    except (OSError, ValueError):
        return []


def sauvegarder(fichier: Path, racine: Path | None = None, quand: datetime | None = None) -> Path:
    """Copie le fichier avant sa modification dans sauvegardes\\ et renvoie le chemin de la copie. Lève une exception si la
    copie échoue : sans sauvegarde, la modification ne doit pas avoir lieu. Rien n'est jamais supprimé ni écrasé ici."""
    fichier = Path(fichier)
    if not fichier.is_file():
        raise FileNotFoundError(f"Fichier à sauvegarder introuvable : {fichier}")
    dossier = _racine(racine) / DOSSIER_SAUVEGARDES
    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"{(quand or datetime.now()):%Y-%m-%d_%H-%M-%S}_{fichier.name}"
    cible = dossier / nom
    n = 2
    while cible.exists():  # deux sauvegardes du même fichier dans la même seconde : un suffixe, jamais un écrasement
        cible = dossier / f"{Path(nom).stem}_{n}{Path(nom).suffix}"
        n += 1
    cible.write_bytes(fichier.read_bytes())
    return cible
