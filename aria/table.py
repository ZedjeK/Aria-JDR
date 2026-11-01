"""La table de jeu : le joueur parle, le MJ (le LLM) appelle le moteur, puis raconte.

Un tour : la phrase du joueur part au LLM avec les outils du moteur. Tant que le LLM
appelle des outils, la session les exécute et lui renvoie les résultats ; quand il
répond en texte, c'est sa narration, et le tour est fini. C'est la même boucle que celle
du banc d'essai : le MJ qui joue est exactement celui qui a été qualifié.

La conversation garde tout l'historique tant qu'elle tient dans le contexte du modèle.
Quand elle déborde, les plus vieux échanges sont oubliés (une fenêtre glissante) ; le
prompt système, lui, reste toujours, avec le bloc Mémoire de la campagne (memoire.py),
remis à jour avant chaque requête. Des échanges oubliés, le moteur garde le fil : les
phrases du joueur et les lignes de ses jets, qui rejoignent le prompt système.
"""

import json
import time
from dataclasses import dataclass, field

from aria import llm, mj, optimiseur
from aria.compte_rendu import decrire
from aria.outils import Session

TOURS_MAX = 8  # allers-retours avec le modèle pour une seule action du joueur
RESERVE_TOUR = 2500  # jetons laissés libres pour les appels d'outils et les résultats d'un tour
FIL_MAX = 2000  # caractères du fil des échanges oubliés, environ 600 jetons
PHRASE_MAX = 120  # caractères gardés d'une phrase du joueur
OUVERTURE = "[Début de la partie] Présente la scène d'ouverture au joueur, puis rends-lui la main."
REPRISE = ("[Reprise de la partie] Rappelle au joueur en deux phrases où on en était, d'après ta mémoire, "
           "puis rends-lui la main.")


@dataclass
class AppelOutil:
    outil: str
    arguments: dict | str  # str si le LLM a envoyé un JSON illisible
    resultat: dict

    @property
    def reussi(self) -> bool:
        return "erreur" not in self.resultat


@dataclass
class Tour:
    narration: str
    appels: list[AppelOutil] = field(default_factory=list)  # dans l'ordre, erreurs comprises
    interrompu: bool = False  # le MJ tournait en rond : arrêté au bout de TOURS_MAX
    jetons: int = 0  # jetons générés par le modèle pendant le tour
    duree: float = 0.0


def _caracteres(messages: list[dict]) -> int:
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)


def _fil(oublies: list[dict], session: Session) -> list[str]:
    """Le fil des échanges oubliés : les phrases du joueur et les lignes du moteur (jets, dégâts…),
    qui sont des faits. La narration du MJ, elle, part : la mémoire en garde l'essentiel."""
    lignes, appels = [], {}
    for message in oublies:
        if message["role"] == "user" and not message["content"].startswith("["):
            phrase = message["content"]
            if len(phrase) > PHRASE_MAX:
                phrase = phrase[:PHRASE_MAX - 1] + "…"
            lignes.append(f"- Le joueur : « {phrase} »")
        for appel in message.get("tool_calls") or []:
            appels[appel.get("id", "")] = appel["function"]
        if message["role"] == "tool" and (fonction := appels.get(message.get("tool_call_id", ""))):
            try:
                arguments = fonction["arguments"]
                arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
                lignes += [f"  - {ligne.strip()}"
                           for ligne in decrire(fonction["name"], arguments, json.loads(message["content"]), session)]
            except (ValueError, KeyError, TypeError, AttributeError):
                pass  # un appel illisible ne laisse pas de trace
    return lignes


class Table:
    def __init__(self, serveur: llm.Serveur, session: Session, budget: int | None, scene: str = "",
                 historique: list[dict] = (), contexte: int = optimiseur.CONTEXTE_CIBLE):
        self.serveur, self.session, self.budget, self.scene = serveur, session, budget, scene
        self.fil: list[str] = []  # ce que le moteur garde des échanges oubliés
        self._fil_coupe = False  # le début du fil a lui-même été oublié
        self.messages = [{"role": "system", "content": self._systeme()}, *historique]
        # La taille du prompt à ne pas dépasser, pour que la réponse tienne encore dans le contexte
        self.limite = contexte - llm.PLAFOND_JETONS - RESERVE_TOUR
        self._mesure = (0, 0)  # (jetons du dernier prompt envoyé, nombre de messages à ce moment-là)

    def ouvrir(self, reprise: bool = False) -> Tour:
        """Le MJ présente la scène d'ouverture, ou rappelle où on en était quand la campagne reprend."""
        return self.tour(REPRISE if reprise else OUVERTURE)

    def tour(self, joueur: str) -> Tour:
        """Joue une action du joueur. Peut lever llm.ErreurLLM si le serveur ne répond pas."""
        self._elaguer()
        self.messages.append({"role": "user", "content": joueur})
        tour, debut = Tour(""), time.time()
        for _ in range(TOURS_MAX):
            message = self._demander(tour, avec_outils=True)
            if not message.get("tool_calls"):
                tour.narration = message.get("content") or ""
                break
            for appel in message["tool_calls"]:
                tour.appels.append(self._executer(appel))
        else:
            # Il tourne en rond : une dernière demande, sans outils, pour qu'il raconte ce qui s'est passé
            tour.interrompu = True
            tour.narration = self._demander(tour, avec_outils=False).get("content") or ""
        tour.duree = round(time.time() - debut, 1)
        return tour

    def _systeme(self) -> str:
        s = self.session
        fil = "\n".join((["- (…)"] if self._fil_coupe else []) + self.fil)
        return mj.prompt_systeme(s.univers, s.personnage, self.scene, s.memoire.bloc(), fil)

    def _rafraichir_systeme(self):
        """Le MJ a pu écrire dans la mémoire pendant le tour : il voit toujours sa dernière version."""
        ancien, nouveau = self.messages[0]["content"], self._systeme()
        if nouveau != ancien:
            self.messages[0]["content"] = nouveau
            jetons, nombre = self._mesure
            if nombre:
                self._mesure = (jetons + (len(nouveau) - len(ancien)) // 3, nombre)

    def _demander(self, tour: Tour, avec_outils: bool) -> dict:
        self._rafraichir_systeme()
        reponse = self.serveur.discuter(self.messages, self.session.schemas() if avec_outils else None, self.budget)
        message = reponse["choices"][0]["message"]
        usage = reponse.get("usage", {})
        tour.jetons += usage.get("completion_tokens", 0)
        if usage.get("prompt_tokens"):
            self._mesure = (usage["prompt_tokens"], len(self.messages))
        # La réflexion du modèle n'est pas renvoyée : elle prendrait de la place pour rien
        self.messages.append({k: v for k, v in message.items() if k in ("role", "content", "tool_calls")})
        return message

    def _executer(self, appel: dict) -> AppelOutil:
        nom, brut = appel["function"]["name"], appel["function"]["arguments"]
        resultat = self.session.appeler(nom, brut)
        self.messages.append({"role": "tool", "tool_call_id": appel.get("id", ""),
                              "content": json.dumps(resultat, ensure_ascii=False)})
        return AppelOutil(nom, self.session.journal[-1]["arguments"], resultat)

    def taille_estimee(self) -> int:
        """Les jetons du prompt : la dernière mesure du serveur, plus ce qui s'est ajouté depuis."""
        jetons, nombre = self._mesure
        return jetons + _caracteres(self.messages[nombre:]) // 3  # ~3 caractères par jeton : on surestime

    def _elaguer(self):
        """Oublie les plus vieux échanges tant que le prompt dépasse la limite. Garde le dernier échange."""
        taille = self.taille_estimee()
        while taille > self.limite:
            debuts = [i for i, m in enumerate(self.messages) if m["role"] == "user"]
            if len(debuts) < 2:
                return
            # Un échange va d'un message du joueur au suivant : outils et réponses partent avec lui
            oublies = self.messages[1:debuts[1]]
            del self.messages[1:debuts[1]]
            jetons, nombre = self._mesure
            # ~4 caractères par jeton : on sous-estime ce qu'on enlève
            self._mesure = (jetons - _caracteres(oublies) // 4, max(1, nombre - len(oublies)))
            self._garder_le_fil(oublies)
            self._rafraichir_systeme()
            taille = self.taille_estimee()

    def _garder_le_fil(self, oublies: list[dict]):
        """Garde des échanges oubliés la phrase du joueur et les lignes du moteur, dans une taille bornée."""
        self.fil += _fil(oublies, self.session)
        while sum(len(ligne) + 1 for ligne in self.fil) > FIL_MAX:
            self.fil.pop(0)
            self._fil_coupe = True
