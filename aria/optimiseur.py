"""Les réglages du MJ selon le matériel : quel modèle, quel contexte, quel cache, MTP ou non.

Contrairement à Aria-Pilote, qui cherche le plus de contexte possible, le MJ prend le
contexte juste suffisant (CONTEXTE_CIBLE) : les outils, le prompt, la mémoire de campagne
et l'historique récent. Le reste de la VRAM est laissé libre, pour ComfyUI notamment.
Un modèle qui ne tient pas entier sur la carte graphique est écarté : à moitié en RAM, il
serait trop lent pour jouer, et un modèle plus petit du catalogue fera mieux.

Ce sont des estimations : l'essai réel (llm.py) les confirme, et descend d'un cran si besoin.
"""

from dataclasses import dataclass, replace
from pathlib import Path

from aria import gguf

GIO = 1024 ** 3
# Le prompt du MJ avec ses outils pèse environ 14 000 jetons (mesuré le 2026-11-13 sur Qwen3.8 et Gemma 4) :
# en dessous de ce contexte, le serveur refuse la première requête. Il n'y a donc pas de palier plus petit.
CONTEXTE_CIBLE = 16384
OCTETS_PAR_VALEUR = {"f16": 2.0, "q8_0": 34 / 32}  # le cache de contexte, par valeur stockée
SURCOUT = int(0.6 * GIO)  # tampons de calcul et contexte CUDA (mesuré par Aria-Pilote : 0,2 à 1,1 Gio)
SURCOUT_MTP = int(1.5 * GIO)  # le contexte de la couche MTP (mesuré ici : 1,9 Gio à 32k)
MARGE = int(0.5 * GIO)  # VRAM toujours laissée libre pour Windows
LOT = 2048  # jetons traités d'un coup par le serveur : une couche à fenêtre garde sa fenêtre plus un lot, au plus


@dataclass(frozen=True)
class ModeleConnu:
    nom: str
    fichier: str
    depot: str  # sur Hugging Face


# Du meilleur au plus léger : le premier qui tient en VRAM et passe le banc devient le MJ.
CATALOGUE = (
    ModeleConnu("Qwen3.8 27B", "Qwen3.8-27B-UD-Q3_K_XL.gguf", "unsloth/Qwen3.8-27B-GGUF"),
    ModeleConnu("Gemma 4 26B", "gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf", "unsloth/gemma-4-26B-A4B-it-GGUF"),
    ModeleConnu("Bonsai 2 27B", "Ternary-Bonsai-2-27B-PQ2_0.gguf", "prism-ml/Ternary-Bonsai-2-27B-gguf"),
    ModeleConnu("Bonsai 2 9B", "Ternary-Bonsai-2-9B-PQ2_0.gguf", "prism-ml/Ternary-Bonsai-2-9B-gguf"),
    ModeleConnu("Bonsai 2 4B", "Ternary-Bonsai-2-4B-PQ2_0.gguf", "prism-ml/Ternary-Bonsai-2-4B-gguf"),
    ModeleConnu("Bonsai 2 2B", "Ternary-Bonsai-2-2B-PQ2_0.gguf", "prism-ml/Ternary-Bonsai-2-2B-gguf"),
)


@dataclass(frozen=True)
class Reglages:
    contexte: int
    cache: str = "f16"
    mtp: bool = False

    def arguments(self) -> list[str]:
        """Les options de llama-server qui correspondent."""
        args = ["-c", str(self.contexte), "-ngl", "99", "-np", "1"]  # un seul joueur : un seul emplacement
        if self.cache != "f16":
            args += ["-ctk", self.cache, "-ctv", self.cache, "-fa", "on"]  # compresser V exige la flash attention
        if self.mtp:
            args += ["--spec-type", "draft-mtp"]
        return args

    def __str__(self) -> str:
        return f"{self.contexte // 1024}k, cache {self.cache}" + (", MTP" if self.mtp else "")


@dataclass(frozen=True)
class Modele:
    """Un modèle présent sur le disque, avec ce qu'en dit son en-tête."""
    nom: str
    chemin: Path
    taille: int  # octets
    valeurs_kv: int  # valeurs du cache de contexte par jeton
    a_mtp: bool
    contexte_max: int
    valeurs_fenetre: int = 0  # valeurs par jeton des couches à fenêtre glissante
    fenetre: int = 0  # jetons que ces couches gardent, quel que soit le contexte


def valeurs_kv_par_jeton(meta: dict) -> int | None:
    """Valeurs du cache (K + V) par jeton de contexte, ou None si l'en-tête ne le dit pas."""
    cache = cache_du_modele(meta)
    return cache[0] if cache else None


def cache_du_modele(meta: dict) -> tuple[int, int, int] | None:
    """Le cache de contexte : (valeurs par jeton, valeurs par jeton des couches à fenêtre, jetons de la fenêtre),
    ou None si l'en-tête ne le dit pas.

    Les architectures hybrides (Qwen3.8, Bonsai 2…) n'ont une attention classique qu'une couche
    sur N (full_attention_interval) ; les autres couches ont un état de taille fixe, négligeable.

    Gemma 4 donne ses têtes couche par couche, et dit lesquelles ont une fenêtre glissante
    (sliding_window_pattern), avec des clés et des valeurs plus courtes (key_length_swa). Ces couches ne
    gardent que leur fenêtre (sliding_window), plus un lot de jetons : on les compte à part, avec ce majorant.
    Si l'en-tête ne donne pas la taille de la fenêtre, elles sont comptées comme des couches ordinaires."""
    couches = gguf.cle(meta, "block_count")
    tetes = gguf.cle(meta, "attention.head_count")
    if not couches or not tetes or not isinstance(tetes, (int, list)):
        return None
    tetes = max(tetes) if isinstance(tetes, list) else tetes
    tetes_kv = gguf.cle(meta, "attention.head_count_kv") or tetes
    dimension = (gguf.cle(meta, "embedding_length") or 0) // tetes
    k = gguf.cle(meta, "attention.key_length") or dimension
    v = gguf.cle(meta, "attention.value_length") or dimension
    if not k or not v or not isinstance(tetes_kv, (int, list)):
        return None
    glissantes = gguf.cle(meta, "attention.sliding_window_pattern")
    if isinstance(tetes_kv, list) or isinstance(glissantes, list):
        courtes = ((gguf.cle(meta, "attention.key_length_swa") or k) + (gguf.cle(meta, "attention.value_length_swa") or v))
        fenetre = gguf.cle(meta, "attention.sliding_window")
        fenetre = fenetre + LOT if isinstance(fenetre, int) and fenetre > 0 else 0
        entieres = sous_fenetre = 0
        for couche in range(couches):
            par_couche = tetes_kv[couche] if isinstance(tetes_kv, list) and couche < len(tetes_kv) else (
                max(tetes_kv) if isinstance(tetes_kv, list) else tetes_kv)
            glissante = isinstance(glissantes, list) and couche < len(glissantes) and glissantes[couche]
            if glissante and fenetre:
                sous_fenetre += par_couche * courtes
            else:
                entieres += par_couche * (courtes if glissante else k + v)
        return (entieres, sous_fenetre, fenetre if sous_fenetre else 0) if entieres or sous_fenetre else None
    intervalle = gguf.cle(meta, "full_attention_interval")
    couches_attention = couches // intervalle if isinstance(intervalle, int) and intervalle > 1 else couches
    return couches_attention * tetes_kv * (k + v), 0, 0


def decrire(chemin: Path, nom: str | None = None) -> Modele | None:
    """Lit l'en-tête d'un modèle ; None s'il est illisible ou incomplet."""
    try:
        meta = gguf.lire_metadonnees(chemin)
    except (OSError, gguf.GgufInvalide):
        return None
    cache = cache_du_modele(meta)
    if not cache:
        return None
    return Modele(nom or chemin.stem, chemin, chemin.stat().st_size, cache[0],
                  bool(gguf.cle(meta, "nextn_predict_layers")), gguf.cle(meta, "context_length") or CONTEXTE_CIBLE,
                  cache[1], cache[2])


def vram_estimee(modele: Modele, reglages: Reglages) -> int:
    jetons = modele.valeurs_kv * reglages.contexte + modele.valeurs_fenetre * min(modele.fenetre, reglages.contexte)
    cache = jetons * OCTETS_PAR_VALEUR[reglages.cache]
    return int(modele.taille + cache + SURCOUT + (SURCOUT_MTP if reglages.mtp else 0))


def paliers(modele: Modele) -> list[Reglages]:
    """Les réglages à essayer, du plus confortable au plus économe."""
    cible = min(CONTEXTE_CIBLE, modele.contexte_max)
    sans_mtp = [Reglages(cible), Reglages(cible, "q8_0")]
    avec_mtp = [replace(r, mtp=True) for r in sans_mtp] if modele.a_mtp else []
    return avec_mtp + sans_mtp


def vram_requise(modele: Modele) -> int:
    """La VRAM libre qu'il faut pour le palier le plus économe, marge comprise."""
    return min(vram_estimee(modele, r) for r in paliers(modele)) + MARGE


def planifier(modele: Modele, vram_libre: int | None) -> list[Reglages]:
    """Les paliers qui tiennent dans la VRAM libre (marge comprise), dans l'ordre où les essayer."""
    if vram_libre is None:
        return []
    return [r for r in paliers(modele) if vram_estimee(modele, r) + MARGE <= vram_libre]


def modeles_presents(dossier: Path) -> list[Modele]:
    """Les modèles du catalogue présents dans le dossier, du meilleur au plus léger."""
    presents = []
    for connu in CATALOGUE:
        chemin = dossier / connu.fichier
        if chemin.is_file() and (modele := decrire(chemin, connu.nom)):
            presents.append(modele)
    return presents
