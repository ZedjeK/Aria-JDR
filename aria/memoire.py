"""La mémoire de la campagne : ce que le MJ doit retenir, d'un échange et d'une session à l'autre.

Trois fichiers Markdown dans le dossier de la campagne, lisibles et modifiables à la main :
- souvenirs.md : le journal, dans l'ordre (combats et scènes terminés) ;
- pnj.md : les PNJ rencontrés, leur rôle, leur attitude envers le personnage, leur état ;
- fils.md : les fils de l'histoire (quêtes, promesses, dettes, menaces), ouverts puis clos.

Le MJ écrit par ses outils ; le moteur valide, puis réécrit les fichiers. L'état d'un PNJ
(vivant ou mort), lui, ne vient que du moteur. À chaque requête, le MJ reçoit le bloc
Mémoire : les fils ouverts, les PNJ connus, les souvenirs récents en entier et les plus
vieux réduits à leur titre, dans une taille bornée.
"""

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

from aria.campagne import Campagne

BLOC_MAX = 5000  # caractères du bloc Mémoire, environ 1 500 jetons
LONGUEURS = {"nom": 40, "rôle": 120, "attitude": 160, "fil": 200, "issue": 200, "titre": 60}
VIVANT, MORT = "vivant", "mort"
_IDENTIFIANT = re.compile(r"^[a-z0-9_]{1,40}$")
_TITRE_PNJ = re.compile(r"^(.+) \(([a-z0-9_]+)\)$")
_CHAMP = re.compile(r"^- ([^:]+?) : (.*)$")


class MemoireRefusee(ValueError):
    """Une écriture refusée par le moteur. Le message est renvoyé tel quel au MJ."""


@dataclass
class PnjConnu:
    nom: str
    role: str
    attitude: str
    etat: str = VIVANT


@dataclass
class Fil:
    texte: str
    issue: str | None = None  # None tant que le fil est ouvert

    @property
    def ouvert(self) -> bool:
        return self.issue is None


def _sections(texte: str) -> list[tuple[str, dict[str, str]]]:
    """Les sections « ## titre » d'un fichier, avec leurs champs « - Clé : valeur »."""
    sections = []
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            sections.append((ligne[3:].strip(), {}))
        elif sections and (champ := _CHAMP.match(ligne.strip())):
            sections[-1][1][champ.group(1).strip().lower()] = champ.group(2).strip()
    return sections


def _souvenirs(texte: str) -> list[str]:
    """Les souvenirs d'un journal : chacun commence par son titre « ## … »."""
    morceaux = re.split(r"^(?=## )", texte, flags=re.MULTILINE)
    return [m.strip() for m in morceaux if m.startswith("## ")]


def _verifier(champ: str, valeur: str) -> str:
    valeur = " ".join(valeur.split())
    if not valeur:
        raise MemoireRefusee(f"« {champ} » ne peut pas être vide.")
    if len(valeur) > LONGUEURS[champ]:
        raise MemoireRefusee(f"« {champ} » est trop long ({len(valeur)} caractères, {LONGUEURS[champ]} au plus).")
    return valeur


def verifier_identifiant(identifiant: str) -> str:
    if not _IDENTIFIANT.match(identifiant):
        raise MemoireRefusee(f"Identifiant invalide : « {identifiant} ». Minuscules, chiffres et _ seulement, "
                             "par exemple doc_mori.")
    return identifiant


def _ecrire(chemin: Path, texte: str):
    """Écrit un fichier entier sans jamais laisser une version à moitié écrite."""
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire.write_text(texte, encoding="utf-8")
        os.replace(temporaire, chemin)
    except OSError as erreur:
        raise MemoireRefusee(f"La mémoire n'a pas pu être écrite ({erreur}) : rien n'a changé.") from erreur


class Memoire:
    def __init__(self, campagne: Campagne | None = None):
        """Relit la mémoire de la campagne. Sans campagne (le banc d'essai), elle ne vit qu'en mémoire vive."""
        self.campagne = campagne
        self.pnj: dict[str, PnjConnu] = {}
        self.fils: dict[str, Fil] = {}
        self.souvenirs: list[str] = []
        if campagne is None:
            return
        if campagne.pnj.is_file():
            for titre, champs in _sections(campagne.pnj.read_text(encoding="utf-8")):
                if (t := _TITRE_PNJ.match(titre)) and "rôle" in champs and "attitude" in champs:
                    self.pnj[t.group(2)] = PnjConnu(t.group(1), champs["rôle"], champs["attitude"],
                                                    champs.get("état", VIVANT))
        if campagne.fils.is_file():
            for titre, champs in _sections(campagne.fils.read_text(encoding="utf-8")):
                if _IDENTIFIANT.match(titre) and "fil" in champs:
                    self.fils[titre] = Fil(champs["fil"], champs.get("issue"))
        if campagne.souvenirs.is_file():
            self.souvenirs = _souvenirs(campagne.souvenirs.read_text(encoding="utf-8"))

    # --- Écritures (le MJ par ses outils, le moteur pour les états) ---

    def noter_pnj(self, identifiant: str, nom: str, role: str, attitude: str) -> PnjConnu:
        """Un PNJ rencontré, ou son attitude qui change. Son état reste celui que le moteur connaît."""
        verifier_identifiant(identifiant)
        ancien = self.pnj.get(identifiant)
        pnj = PnjConnu(_verifier("nom", nom), _verifier("rôle", role), _verifier("attitude", attitude),
                       ancien.etat if ancien else VIVANT)
        self._ecrire_pnj(self.pnj | {identifiant: pnj})
        return pnj

    def marquer_etat(self, identifiant: str, etat: str):
        if identifiant in self.pnj and self.pnj[identifiant].etat != etat:
            self._ecrire_pnj(self.pnj | {identifiant: replace(self.pnj[identifiant], etat=etat)})

    def est_mort(self, identifiant: str) -> bool:
        return identifiant in self.pnj and self.pnj[identifiant].etat == MORT

    def ouvrir_fil(self, identifiant: str, texte: str) -> Fil:
        verifier_identifiant(identifiant)
        if identifiant in self.fils:
            etat = "ouvert" if self.fils[identifiant].ouvert else "clos"
            raise MemoireRefusee(f"Le fil « {identifiant} » existe déjà ({etat}) : prends un autre identifiant.")
        fil = Fil(_verifier("fil", texte))
        self._ecrire_fils(self.fils | {identifiant: fil})
        return fil

    def clore_fil(self, identifiant: str, issue: str) -> Fil:
        ouverts = sorted(i for i, f in self.fils.items() if f.ouvert)
        if identifiant not in self.fils:
            raise MemoireRefusee(f"Fil inconnu : « {identifiant} ». Fils ouverts : {ouverts or 'aucun'}.")
        if not self.fils[identifiant].ouvert:
            raise MemoireRefusee(f"Le fil « {identifiant} » est déjà clos.")
        fil = replace(self.fils[identifiant], issue=_verifier("issue", issue))
        self._ecrire_fils(self.fils | {identifiant: fil})
        return fil

    def ajouter_souvenir(self, souvenir: str):
        """Ajoute un souvenir au journal. Lève OSError si l'écriture échoue."""
        if self.campagne:
            self.campagne.ajouter_souvenir(souvenir)
        self.souvenirs.append(souvenir.strip())

    def _ecrire_pnj(self, pnj: dict[str, PnjConnu]):
        if self.campagne:
            sections = [f"## {p.nom} ({i})\n- Rôle : {p.role}\n- Attitude : {p.attitude}\n- État : {p.etat}\n"
                        for i, p in pnj.items()]
            _ecrire(self.campagne.pnj, "# PNJ de la campagne\n\n" + "\n".join(sections))
        self.pnj = pnj

    def _ecrire_fils(self, fils: dict[str, Fil]):
        if self.campagne:
            sections = [f"## {i}\n- Fil : {f.texte}\n" + (f"- Issue : {f.issue}\n" if f.issue else "")
                        for i, f in fils.items()]
            _ecrire(self.campagne.fils, "# Fils de la campagne\n\n" + "\n".join(sections))
        self.fils = fils

    # --- Ce que le MJ lit ---

    def bloc(self, limite: int = BLOC_MAX) -> str:
        """Le résumé de la mémoire que reçoit le MJ ; vide tant que la campagne n'a rien retenu.
        Les fils ouverts et les PNJ passent toujours ; les souvenirs remplissent la place qui reste,
        les plus récents en entier, les autres par leur titre."""
        parties = []
        ouverts = [f"- {i} : {f.texte}" for i, f in self.fils.items() if f.ouvert]
        if ouverts:
            parties.append("### Fils ouverts\n" + "\n".join(ouverts))
        if self.pnj:
            parties.append("### PNJ connus\n" + "\n".join(
                f"- {p.nom} ({i}) — {p.role} — attitude : {p.attitude}" + (f" [{p.etat}]" if p.etat != VIVANT else "")
                for i, p in self.pnj.items()))
        if self.souvenirs:
            parties.append(self._bloc_souvenirs(limite - sum(len(p) + 2 for p in parties)))
        return "\n\n".join(parties)

    def _bloc_souvenirs(self, place: int) -> str:
        entete = "### Souvenirs (du plus ancien au plus récent)\n"
        place -= len(entete)
        entiers, titres = [], []
        for souvenir in reversed(self.souvenirs):
            texte = "##" + souvenir  # « ## » devient « #### » : un niveau sous la section
            if not titres and len(texte) + 2 <= place:
                entiers.insert(0, texte)
                place -= len(texte) + 2
            else:
                titres.insert(0, "- " + souvenir.splitlines()[0][3:])
        def note(n: int) -> list[str]:
            return [f"- ({n} souvenirs plus anciens, dans souvenirs.md)"] if n else []

        oublies = 0
        while titres and sum(len(t) + 1 for t in note(oublies) + titres) + 1 > place:
            titres.pop(0)
            oublies += 1
        titres = note(oublies) + titres
        return entete + "\n".join(titres + ([""] if titres and entiers else []) + ["\n\n".join(entiers)]).strip()
