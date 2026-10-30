"""Le LLM du MJ : lancer llama-server (le fork PrismML) et lui parler.

Le serveur se lance avec les réglages de l'optimiseur. S'il ne démarre pas, ou laisse trop
peu de VRAM libre, on descend d'un palier et on réessaie (l'essai réel). On lui parle
ensuite au format OpenAI, avec la bibliothèque standard de Python.

La réflexion du modèle se règle à chaque requête : None la laisse libre, 0 la coupe,
N la limite à N jetons. Au bout du budget, le serveur glisse MESSAGE_FIN_REFLEXION pour
que le modèle conclue au lieu de continuer à réfléchir dans sa réponse.
"""

import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from aria import chemins, materiel
from aria.optimiseur import MARGE, Modele, Reglages

DOSSIER_LLM = chemins.dossier_llm()
MOTEUR = DOSSIER_LLM / "llama-prism" / "llama-server.exe"
DOSSIER_MODELES = DOSSIER_LLM / "modeles"
PORT = 8080
PLAFOND_JETONS = 3000  # jamais de réponse sans fin, même si le modèle part en boucle
DELAI_CHARGEMENT = 300  # secondes
DELAI_REPONSE = 600
MESSAGE_FIN_REFLEXION = "Okay, time is up. I must give my final answer now."
_SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ErreurLLM(Exception):
    pass


def arguments_serveur(modele: Modele, reglages: Reglages, port: int = PORT) -> list[str]:
    return ["-m", str(modele.chemin), *reglages.arguments(), "--jinja",
            "--reasoning-budget-message", MESSAGE_FIN_REFLEXION, "--host", "127.0.0.1", "--port", str(port)]


def requete(messages: list[dict], outils: list[dict] | None = None, budget: int | None = None,
            temperature: float = 0.6, plafond: int = PLAFOND_JETONS) -> dict:
    """Le corps d'une requête de chat, avec le budget de réflexion voulu."""
    corps = {"messages": messages, "temperature": temperature, "max_tokens": plafond}
    if outils:
        corps["tools"] = outils
    if budget == 0:
        corps["chat_template_kwargs"] = {"enable_thinking": False}
    elif budget is not None:
        corps["thinking_budget_tokens"] = budget
    return corps


@dataclass
class Serveur:
    modele: Modele
    reglages: Reglages
    moteur: Path = MOTEUR
    port: int = PORT
    journal: Path | None = None  # où écrire la sortie du serveur (rien si None)
    _processus: subprocess.Popen | None = field(default=None, repr=False)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def demarrer(self) -> bool:
        """Lance le serveur et attend qu'il soit prêt ; False s'il s'arrête ou met trop longtemps."""
        if not self.moteur.is_file():
            raise ErreurLLM(f"llama-server introuvable : {self.moteur}")
        sortie = open(self.journal, "w", encoding="utf-8") if self.journal else subprocess.DEVNULL
        self._processus = subprocess.Popen([str(self.moteur), *arguments_serveur(self.modele, self.reglages, self.port)],
                                           stdout=sortie, stderr=subprocess.STDOUT, creationflags=_SANS_FENETRE)
        limite = time.time() + DELAI_CHARGEMENT
        while time.time() < limite:
            if self._processus.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=2) as r:
                    if r.status == 200:
                        return True
            except (urllib.error.URLError, OSError):
                pass  # 503 pendant le chargement, ou pas encore à l'écoute
            time.sleep(1)
        self.arreter()
        return False

    def arreter(self):
        if self._processus and self._processus.poll() is None:
            self._processus.terminate()
            try:
                self._processus.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self._processus.kill()
        self._processus = None

    def discuter(self, messages: list[dict], outils: list[dict] | None = None, budget: int | None = None,
                 temperature: float = 0.6) -> dict:
        """Envoie la conversation ; renvoie la réponse complète de llama-server (message, usage, timings)."""
        corps = json.dumps(requete(messages, outils, budget, temperature)).encode()
        demande = urllib.request.Request(f"{self.url}/v1/chat/completions", data=corps,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(demande, timeout=DELAI_REPONSE) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as erreur:
            raise ErreurLLM(f"Le serveur n'a pas répondu : {erreur}") from erreur

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.arreter()


def demarrer_au_mieux(modele: Modele, paliers: list[Reglages], moteur: Path = MOTEUR,
                      journal: Path | None = None) -> Serveur | None:
    """Essai réel : le premier palier qui démarre et laisse assez de VRAM libre ; None si aucun."""
    for reglages in paliers:
        serveur = Serveur(modele, reglages, moteur, journal=journal)
        if serveur.demarrer():
            libre = materiel.scanner().vram_libre
            if libre is None or libre >= MARGE:
                return serveur
            serveur.arreter()
        time.sleep(2)  # le temps que la VRAM soit rendue
    return None
