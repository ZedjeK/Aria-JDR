"""Les mises à jour intégrées : chercher une nouvelle version, la télécharger et la vérifier, garder la version en cours,
mettre la nouvelle à sa place, puis la relancer. Rien ne se télécharge ni ne s'installe sans l'accord de l'utilisateur :
c'est l'interface qui appelle ces fonctions, après son clic.

Une seule adresse est interrogée : releases/latest du dépôt de l'appli, sur l'API GitHub, sans identifiant ni télémétrie.
Seul le zip de la version est retenu, sur github.com en HTTPS, avec l'empreinte SHA-256 que GitHub calcule à l'envoi
(champ « digest »). L'empreinte prouve que le téléchargement est intact, pas d'où il vient : la provenance repose sur le
compte de l'auteur, les releases immuables et l'attestation jointe (voir « Limites à connaître » du README).

L'appli est portable : la mise à jour remplace, là où l'exe tourne, exactement ce que liste le fichiers.txt du zip
(posé par tools\\empaqueter.ps1). La version en cours est d'abord copiée dans sauvegardes\\versions\\.
"""

import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from appli import donnees, identite

PROPRIETAIRE = "ZedjeK"
FICHIERS = "fichiers.txt"
DOSSIER_TRAVAIL = "mise-a-jour"  # dans cache\ : le zip téléchargé et son extraction, retirés après chaque essai
DOSSIER_VERSIONS = "versions"  # dans sauvegardes\ : la version précédente de l'appli
ARGUMENT_APRES = "--apres-mise-a-jour"
SUFFIXE_ANCIEN = ".ancien"  # le fichier remplacé : un exe qui tourne se renomme, il ne s'écrase pas
SUFFIXE_NOUVEAU = ".nouveau"
DELAI_RECHERCHE = 30  # secondes
DELAI_TELECHARGEMENT = 600
TAILLE_REPONSE_MAX = 1_000_000  # la réponse de l'API : quelques Ko d'ordinaire

# Ouvre une requête HTTP et renvoie la réponse (urllib.request.urlopen ; les tests en passent une fausse)
Ouvreur = Callable[..., object]

_VERSION = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")


class ErreurMiseAJour(Exception):
    """La mise à jour n'a pas eu lieu ; le message dit pourquoi, en clair, pour l'utilisateur."""


@dataclass(frozen=True)
class Fichier:
    """Le zip d'une version : son nom, son adresse, sa taille, et l'empreinte SHA-256 annoncée par GitHub."""

    nom: str
    url: str
    taille: int
    sha256: str


@dataclass(frozen=True)
class MiseAJour:
    """Une version plus récente que celle en cours."""

    version: str
    page: str
    zip: Fichier


@dataclass(frozen=True)
class Resultat:
    """`fait` : les fichiers sont en place, `exe` est à relancer. Sinon rien n'a changé, et `erreur` dit pourquoi."""

    fait: bool
    erreur: str | None = None
    exe: Path | None = None


def depot() -> str:
    return f"https://github.com/{PROPRIETAIRE}/{identite.EXE}"


def prefixe_telechargement() -> str:
    """Début obligatoire de l'adresse du zip : une release de ce dépôt, en HTTPS, sur github.com."""
    return depot() + "/releases/download/"


def api_derniere_version() -> str:
    return f"https://api.github.com/repos/{PROPRIETAIRE}/{identite.EXE}/releases/latest"


def nom_exe() -> str:
    return identite.EXE + ".exe"


def dossier_travail(racine: Path | None = None) -> Path:
    return (Path(racine) if racine is not None else identite.dossier_donnees()) / donnees.DOSSIER_CACHE / DOSSIER_TRAVAIL


def dossier_versions(racine: Path | None = None) -> Path:
    return (Path(racine) if racine is not None else identite.dossier_donnees()) / donnees.DOSSIER_SAUVEGARDES / DOSSIER_VERSIONS


# ------------------------------------------------------------------ Chercher


def version_du_tag(tag) -> tuple[int, int, int] | None:
    """« v1.2.3 » → (1, 2, 3) ; rien d'autre n'est accepté."""
    if not isinstance(tag, str) or not tag.startswith("v"):
        return None
    return _numeros(tag[1:])


def _numeros(texte: str) -> tuple[int, int, int] | None:
    trouve = _VERSION.fullmatch(texte)
    return tuple(int(n) for n in trouve.groups()) if trouve else None


def empreinte(digest) -> str | None:
    """« sha256:ABC… » → les 64 chiffres en minuscules ; None pour tout autre format."""
    if not isinstance(digest, str) or not digest.lower().startswith("sha256:"):
        return None
    hexa = digest[len("sha256:"):].strip().lower()
    return hexa if len(hexa) == 64 and all(c in "0123456789abcdef" for c in hexa) else None


def lire_reponse(brut, actuelle: str) -> MiseAJour | None:
    """Lit la réponse de l'API ; None si la version n'est pas plus récente ou si la réponse est inutilisable."""
    try:
        racine = json.loads(brut)
    except (ValueError, TypeError):
        return None
    if not isinstance(racine, dict) or racine.get("draft") is True or racine.get("prerelease") is True:
        return None
    derniere = version_du_tag(racine.get("tag_name"))
    if derniere is None or derniere <= (_numeros(actuelle) or (0, 0, 0)):
        return None

    texte = ".".join(str(n) for n in derniere)
    attendu = f"{identite.EXE}-{texte}.zip"
    fichiers = racine.get("assets")
    if not isinstance(fichiers, list):
        return None
    for fichier in fichiers:
        if not isinstance(fichier, dict) or fichier.get("name") != attendu:
            continue
        url, taille = fichier.get("browser_download_url"), fichier.get("size")
        if not isinstance(url, str) or not url.startswith(prefixe_telechargement()):
            return None
        if not isinstance(taille, int) or isinstance(taille, bool) or taille <= 0:
            return None
        sha = empreinte(fichier.get("digest"))
        if sha is None:
            return None
        # Seule une page de ce dépôt est proposée à l'ouverture
        page = racine.get("html_url")
        if not isinstance(page, str) or not page.lower().startswith(depot().lower() + "/"):
            page = depot() + "/releases/latest"
        return MiseAJour(texte, page, Fichier(attendu, url, taille, sha))
    return None


def _requete(url: str, accepte: str) -> urllib.request.Request:
    """HTTPS, et un nom d'appli sans rien qui identifie l'utilisateur."""
    return urllib.request.Request(url, headers={"User-Agent": f"{identite.EXE}/{identite.version()}", "Accept": accepte})


def chercher(actuelle: str | None = None, ouvrir: Ouvreur | None = None) -> MiseAJour | None:
    """La version plus récente ; None si celle-ci est la dernière, ou si GitHub ne répond pas utilement. Ne lève jamais."""
    ouvrir = ouvrir or urllib.request.urlopen
    try:
        with ouvrir(_requete(api_derniere_version(), "application/vnd.github+json"), timeout=DELAI_RECHERCHE) as reponse:
            brut = reponse.read(TAILLE_REPONSE_MAX + 1)
    except (OSError, ValueError):
        return None  # pas de réseau, proxy, délai dépassé, réponse HTTP en erreur
    if len(brut) > TAILLE_REPONSE_MAX:
        return None
    return lire_reponse(brut, actuelle or identite.version())


# ------------------------------------------------------------------ Télécharger


def telecharger(mise_a_jour: MiseAJour, dossier: Path | None = None, ouvrir: Ouvreur | None = None) -> Path:
    """Télécharge et vérifie le zip ; renvoie son chemin. Lève ErreurMiseAJour si ce n'est pas le bon fichier."""
    fichier = mise_a_jour.zip
    if not fichier.url.startswith(prefixe_telechargement()):
        raise ErreurMiseAJour("Adresse de téléchargement refusée : elle n'est pas une release de ce dépôt sur github.com.")
    ouvrir = ouvrir or urllib.request.urlopen
    dossier = Path(dossier) if dossier is not None else dossier_travail()
    cible = dossier / fichier.nom
    partiel = cible.with_name(cible.name + ".part")
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        with ouvrir(_requete(fichier.url, "application/octet-stream"), timeout=DELAI_TELECHARGEMENT) as reponse:
            # GitHub redirige vers son hôte de téléchargement : toujours en HTTPS
            if not str(reponse.geturl()).startswith("https://"):
                raise ErreurMiseAJour("Le téléchargement a été redirigé hors de HTTPS : rien n'est installé.")
            calcul, total = hashlib.sha256(), 0
            with open(partiel, "wb") as sortie:
                while bloc := reponse.read(65536):
                    total += len(bloc)
                    if total > fichier.taille:
                        raise ErreurMiseAJour("Le fichier téléchargé est plus gros qu'annoncé : rien n'est installé.")
                    calcul.update(bloc)
                    sortie.write(bloc)
        if total != fichier.taille or calcul.hexdigest() != fichier.sha256:
            raise ErreurMiseAJour("Le fichier téléchargé ne correspond pas à l'empreinte annoncée par GitHub : rien n'est installé.")
        os.replace(partiel, cible)
        return cible
    except OSError as erreur:
        raise ErreurMiseAJour(f"Le téléchargement a échoué : {erreur}") from erreur
    finally:
        try:
            partiel.unlink(missing_ok=True)
        except OSError:
            pass  # retiré au prochain lancement (nettoyer)


# ------------------------------------------------------------------ Installer


def lire_liste(dossier: Path) -> list[str] | None:
    """Fichiers livrés avec l'exe de ce dossier, d'après son fichiers.txt ; None si la liste manque ou est incohérente
    (nom avec un chemin, exe absent de la liste). Lève seulement si le dossier est illisible."""
    liste = Path(dossier) / FICHIERS
    if not liste.is_file():
        return None
    noms = [ligne.strip() for ligne in liste.read_text(encoding="utf-8-sig").splitlines() if ligne.strip()]
    # Un nom de la liste devient un chemin : rien qui puisse sortir du dossier
    for nom in noms:
        if nom != PureWindowsPath(nom).name or nom != Path(nom).name or nom in (".", "..") or nom.lower() == FICHIERS:
            return None
    if not noms or nom_exe().lower() not in (n.lower() for n in noms):
        return None
    return noms


def _extraire(archive: Path, destination: Path) -> Path:
    """Extrait le zip et renvoie le dossier qui contient ses fichiers (son unique sous-dossier s'il en a un seul)."""
    base = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for entree in zf.infolist():
            chemin = (destination / entree.filename).resolve()
            if chemin != base and base not in chemin.parents:
                raise ErreurMiseAJour(f"Le zip contient un chemin qui sort de son dossier ({entree.filename}) : rien n'est installé.")
        zf.extractall(destination)
    contenu = list(destination.iterdir())
    if len(contenu) == 1 and contenu[0].is_dir():
        return contenu[0]
    return destination


def garder(dossier_exe: Path, version: str, versions: Path) -> Path | None:
    """Copie la version en cours dans `versions`, sous son numéro, et retire celles gardées avant elle. La copie se fait
    à côté, puis prend sa place : une copie interrompue ne remplace jamais une version déjà gardée. Lève une OSError."""
    noms = lire_liste(dossier_exe) or [nom_exe()]
    presents = [n for n in noms + [FICHIERS] if (dossier_exe / n).is_file()]
    if not presents:
        return None
    versions.mkdir(parents=True, exist_ok=True)
    cible = versions / version
    copie = versions / (version + ".copie")
    if copie.exists():
        shutil.rmtree(copie)
    copie.mkdir()
    for nom in presents:
        shutil.copyfile(dossier_exe / nom, copie / nom)
    if cible.exists():
        shutil.rmtree(cible)
    os.replace(copie, cible)
    for autre in versions.iterdir():  # une seule version gardée : la précédente
        if autre != cible and autre.is_dir() and _numeros(autre.name):
            shutil.rmtree(autre, ignore_errors=True)
    return cible


def echanger(source: Path, dossier: Path, noms: list[str]) -> Resultat:
    """Remplace dans `dossier` chaque fichier de la liste par celui de `source`. Le fichier en place est renommé en
    « .ancien » (un exe qui tourne se renomme, il ne s'écrase pas). À la première erreur, tout ce qui a été fait est défait."""
    faits: list[tuple[str, bool]] = []
    try:
        for nom in noms:
            cible, ancien = dossier / nom, dossier / (nom + SUFFIXE_ANCIEN)
            nouveau = dossier / (nom + SUFFIXE_NOUVEAU)
            shutil.copyfile(source / nom, nouveau)  # le contenu seul : la marque « téléchargé depuis Internet » ne suit pas
            ancien.unlink(missing_ok=True)  # reste d'une mise à jour précédente
            avait = cible.exists()
            if avait:
                os.replace(cible, ancien)
            try:
                os.replace(nouveau, cible)
            except OSError:
                if avait:
                    os.replace(ancien, cible)
                raise
            faits.append((nom, avait))
    except OSError as erreur:
        for nom, avait in reversed(faits):
            try:
                (dossier / nom).unlink(missing_ok=True)
                if avait:
                    os.replace(dossier / (nom + SUFFIXE_ANCIEN), dossier / nom)
            except OSError:
                pass  # on défait tout ce qui peut l'être
        for nom in noms:
            try:
                (dossier / (nom + SUFFIXE_NOUVEAU)).unlink(missing_ok=True)
            except OSError:
                pass
        return Resultat(False, f"La mise à jour n'a pas pu remplacer les fichiers : {erreur}. Rien n'a changé.")
    return Resultat(True, exe=dossier / nom_exe())


def installer(archive: Path, exe: Path, versions: Path | None = None, travail: Path | None = None) -> Resultat:
    """Installe le zip vérifié dans le dossier de l'exe en cours, en gardant la version actuelle. Ne lève jamais : à la
    moindre erreur, rien n'a changé et le résultat dit pourquoi."""
    exe = Path(exe)
    dossier = exe.parent
    versions = Path(versions) if versions is not None else dossier_versions()
    travail = Path(travail) if travail is not None else dossier_travail()
    extrait = travail / "extrait"
    try:
        if exe.name.lower() != nom_exe().lower():
            return Resultat(False, f"L'exe s'appelle « {exe.name} » : renomme-le « {nom_exe()} » pour le mettre à jour.")
        if extrait.exists():
            shutil.rmtree(extrait)
        extrait.mkdir(parents=True)
        racine = _extraire(Path(archive), extrait)
        noms = lire_liste(racine)
        if noms is None:
            return Resultat(False, f"Le zip ne contient pas de {FICHIERS} lisible : rien n'est installé.")
        manquants = [n for n in noms if not (racine / n).is_file()]
        if manquants:
            return Resultat(False, f"Il manque dans le zip : {', '.join(manquants)}. Rien n'est installé.")
        try:
            garder(dossier, identite.version(), versions)
        except OSError as erreur:
            return Resultat(False, f"La version en cours n'a pas pu être mise de côté : {erreur}. Rien n'est installé.")
        return echanger(racine, dossier, noms + [FICHIERS])
    except (OSError, ErreurMiseAJour, zipfile.BadZipFile) as erreur:
        return Resultat(False, f"La mise à jour n'a pas pu être installée : {erreur}")
    finally:
        try:
            shutil.rmtree(extrait, ignore_errors=True)
            # Le zip ne sert plus, que l'installation ait réussi ou non : un nouvel essai le retélécharge
            if travail.resolve() in Path(archive).resolve().parents:
                Path(archive).unlink(missing_ok=True)
        except OSError:
            pass  # retiré au prochain lancement (nettoyer)


def nettoyer(dossier_exe: Path | None = None, travail: Path | None = None) -> None:
    """Retire ce que laisse une mise à jour : le dossier de travail, et les « .ancien » et « .nouveau » des seuls fichiers
    de l'appli (un exe portable peut être rangé dans un dossier qui contient autre chose). À appeler au lancement ; ne
    lève jamais."""
    travail = Path(travail) if travail is not None else dossier_travail()
    try:
        shutil.rmtree(travail, ignore_errors=True)
    except OSError:
        pass
    if dossier_exe is None:
        return
    try:
        noms = (lire_liste(Path(dossier_exe)) or [nom_exe()]) + [FICHIERS]
    except OSError:
        return
    for nom in noms:
        for suffixe in (SUFFIXE_ANCIEN, SUFFIXE_NOUVEAU):
            try:
                (Path(dossier_exe) / (nom + suffixe)).unlink(missing_ok=True)
            except OSError:
                pass  # encore utilisé : retiré au prochain lancement


# ------------------------------------------------------------------ Relancer


def exe_en_cours() -> Path | None:
    """L'exe qui tourne ; None depuis les sources (python -m appli), qui ne se mettent pas à jour."""
    return Path(sys.executable) if getattr(sys, "frozen", False) else None


def processus_a_attendre() -> int:
    """Le processus que la nouvelle version doit voir finir avant de démarrer. Dans un exe PyInstaller en un seul
    fichier, Python tourne dans un processus enfant du chargeur, et c'est le chargeur qui tient l'exe et son dossier
    décompressé jusqu'au bout : on attend donc le parent."""
    return os.getppid() if getattr(sys, "frozen", False) else os.getpid()


def relancer(exe: Path, pid: int | None = None) -> None:
    """Lance la nouvelle version, qui attendra la fin de celle-ci. Lève une OSError si le lancement échoue.

    PYINSTALLER_RESET_ENVIRONMENT : sans elle, le nouvel exe se croirait l'enfant du chargeur en cours et s'y rattacherait."""
    environnement = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    drapeaux = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(exe), ARGUMENT_APRES, str(pid if pid is not None else processus_a_attendre())],
                     env=environnement, close_fds=True, creationflags=drapeaux)


def pid_a_attendre(arguments: list[str]) -> int | None:
    """Le processus de l'ancienne version, si l'appli est lancée par une mise à jour ; None sinon."""
    if ARGUMENT_APRES not in arguments:
        return None
    i = arguments.index(ARGUMENT_APRES)
    try:
        pid = int(arguments[i + 1])
    except (IndexError, ValueError):
        return None
    return pid if pid > 0 else None


def attendre_la_fin(pid: int, delai: float = 60) -> bool:
    """Attend que le processus `pid` soit fini, `delai` secondes au plus. Vrai s'il l'est (ou s'il n'existe pas)."""
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    poignee = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not poignee:
        return True  # déjà fini
    try:
        return kernel32.WaitForSingleObject(poignee, int(delai * 1000)) == 0  # WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(poignee)
