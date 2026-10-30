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
CONTEXTE_CIBLE = 16384
CONTEXTE_MINIMUM = 12288
OCTETS_PAR_VALEUR = {"f16": 2.0, "q8_0": 34 / 32}  # le cache de contexte, par valeur stockée
SURCOUT = int(0.6 * GIO)  # tampons de calcul et contexte CUDA (mesuré par Aria-Pilote : 0,2 à 1,1 Gio)
SURCOUT_MTP = int(1.5 * GIO)  # le contexte de la couche MTP (mesuré ici : 1,9 Gio à 32k)
MARGE = int(0.5 * GIO)  # VRAM toujours laissée libre pour Windows


@dataclass(frozen=True)
class ModeleConnu:
    nom: str
    fichier: str
    depot: str  # sur Hugging Face


# Du meilleur au plus léger : le premier qui tient en VRAM et passe le banc devient le MJ.
CATALOGUE = (
    ModeleConnu("Qwen3.8 27B", "Qwen3.8-27B-UD-Q3_K_XL.gguf", "unsloth/Qwen3.8-27B-GGUF"),
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


def valeurs_kv_par_jeton(meta: dict) -> int | None:
    """Valeurs du cache (K + V) par jeton, ou None si l'en-tête ne le dit pas.

    Les architectures hybrides (Qwen3.8, Bonsai 2…) n'ont une attention classique qu'une couche
    sur N (full_attention_interval) ; les autres couches ont un état de taille fixe, négligeable."""
    couches = gguf.cle(meta, "block_count")
    tetes = gguf.cle(meta, "attention.head_count")
    if not couches or not tetes:
        return None
    tetes = max(tetes) if isinstance(tetes, list) else tetes
    tetes_kv = gguf.cle(meta, "attention.head_count_kv") or tetes
    tetes_kv = max(tetes_kv) if isinstance(tetes_kv, list) else tetes_kv
    dimension = (gguf.cle(meta, "embedding_length") or 0) // tetes
    k = gguf.cle(meta, "attention.key_length") or dimension
    v = gguf.cle(meta, "attention.value_length") or dimension
    intervalle = gguf.cle(meta, "full_attention_interval")
    couches_attention = couches // intervalle if isinstance(intervalle, int) and intervalle > 1 else couches
    return couches_attention * tetes_kv * (k + v) if k and v else None


def decrire(chemin: Path, nom: str | None = None) -> Modele | None:
    """Lit l'en-tête d'un modèle ; None s'il est illisible ou incomplet."""
    try:
        meta = gguf.lire_metadonnees(chemin)
    except (OSError, gguf.GgufInvalide):
        return None
    valeurs = valeurs_kv_par_jeton(meta)
    if not valeurs:
        return None
    return Modele(nom or chemin.stem, chemin, chemin.stat().st_size, valeurs,
                  bool(gguf.cle(meta, "nextn_predict_layers")), gguf.cle(meta, "context_length") or CONTEXTE_CIBLE)


def vram_estimee(modele: Modele, reglages: Reglages) -> int:
    cache = modele.valeurs_kv * OCTETS_PAR_VALEUR[reglages.cache] * reglages.contexte
    return int(modele.taille + cache + SURCOUT + (SURCOUT_MTP if reglages.mtp else 0))


def paliers(modele: Modele) -> list[Reglages]:
    """Les réglages à essayer, du plus confortable au plus économe."""
    cible = min(CONTEXTE_CIBLE, modele.contexte_max)
    minimum = min(CONTEXTE_MINIMUM, cible)
    sans_mtp = [Reglages(cible), Reglages(cible, "q8_0"), Reglages(minimum, "q8_0")]
    avec_mtp = [replace(r, mtp=True) for r in sans_mtp[:2]] if modele.a_mtp else []
    return avec_mtp + sans_mtp


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
