"""Le dossier d'une campagne : sa sauvegarde, ses souvenirs et la fiche du combat en cours.

Chaque campagne a son propre dossier dans parties/ : deux campagnes ne partagent jamais
leurs souvenirs. Le moteur écrit tout ; le MJ lit.

- souvenirs.md : le journal de la campagne. Chaque combat terminé y ajoute ses moments forts
  (racontés par le MJ) et son résultat (écrit par le moteur) ; chaque scène terminée, les siens.
- pnj.md et fils.md : les PNJ rencontrés et les fils de l'histoire (voir memoire.py).
- combat.md : la fiche du combat en cours, réécrite à chaque fin de round, puis supprimée
  quand le combat est versé dans les souvenirs.
"""

from dataclasses import dataclass
from pathlib import Path

from aria import chemins

RACINE = chemins.PARTIES


@dataclass
class Campagne:
    dossier: Path

    @classmethod
    def nommee(cls, nom: str) -> "Campagne":
        return cls(RACINE / nom)

    @property
    def sauvegarde(self) -> Path:
        return self.dossier / "sauvegarde.json"

    @property
    def souvenirs(self) -> Path:
        return self.dossier / "souvenirs.md"

    @property
    def pnj(self) -> Path:
        return self.dossier / "pnj.md"

    @property
    def fils(self) -> Path:
        return self.dossier / "fils.md"

    @property
    def combat(self) -> Path:
        return self.dossier / "combat.md"

    def ouvrir(self):
        """Au lancement d'une partie : crée le dossier, et supprime la fiche d'un combat interrompu
        (la sauvegarde ne garde pas l'état d'un combat, cette fiche ne correspondrait plus à rien)."""
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.combat.unlink(missing_ok=True)

    def ecrire_combat(self, fiche: str):
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.combat.write_text(fiche, encoding="utf-8")

    def ajouter_souvenir(self, souvenir: str):
        """Ajoute un souvenir à la fin du fichier. Lève OSError si l'écriture échoue."""
        self.dossier.mkdir(parents=True, exist_ok=True)
        nouveau = not self.souvenirs.exists()
        with open(self.souvenirs, "a", encoding="utf-8") as fichier:
            fichier.write(("# Souvenirs de la campagne\n" if nouveau else "") + "\n" + souvenir.strip() + "\n")

    def effacer_combat(self):
        self.combat.unlink(missing_ok=True)
