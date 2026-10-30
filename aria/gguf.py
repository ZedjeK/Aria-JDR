"""Lecture de l'en-tête d'un fichier GGUF (les métadonnées du modèle), sans charger les poids.

Inspiré d'Aria-Pilote. Les tableaux (vocabulaire du tokenizer…) sont sautés : seule leur
longueur est gardée.
"""

import struct
from pathlib import Path

MAGIE = b"GGUF"
_SCALAIRES = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
_CHAINE = 8
_TABLEAU = 9
_CHAINE_MAX = 64 * 1024 * 1024  # garde-fou contre un fichier corrompu


class GgufInvalide(Exception):
    pass


def lire_metadonnees(chemin: Path | str) -> dict:
    with open(chemin, "rb", buffering=1024 * 1024) as f:
        if f.read(4) != MAGIE:
            raise GgufInvalide("Ce n'est pas un fichier GGUF.")
        (version,) = struct.unpack("<I", _lire(f, 4))
        if version < 2:
            raise GgufInvalide(f"Version GGUF {version} non prise en charge.")
        _nb_tenseurs, nb_cles = struct.unpack("<QQ", _lire(f, 16))
        return {_lire_chaine(f): _lire_valeur(f, struct.unpack("<I", _lire(f, 4))[0]) for _ in range(nb_cles)}


def _lire(f, n: int) -> bytes:
    donnees = f.read(n)
    if len(donnees) != n:
        raise GgufInvalide("Fichier tronqué.")
    return donnees


def _lire_chaine(f) -> str:
    (n,) = struct.unpack("<Q", _lire(f, 8))
    if n > _CHAINE_MAX:
        raise GgufInvalide("Chaîne invalide (fichier corrompu ?).")
    return _lire(f, n).decode("utf-8", errors="replace")


def _lire_valeur(f, type_: int):
    if type_ in _SCALAIRES:
        format_ = _SCALAIRES[type_]
        return struct.unpack(format_, _lire(f, struct.calcsize(format_)))[0]
    if type_ == _CHAINE:
        return _lire_chaine(f)
    if type_ == _TABLEAU:
        type_elements, nombre = struct.unpack("<IQ", _lire(f, 12))
        if type_elements in _SCALAIRES:
            f.seek(nombre * struct.calcsize(_SCALAIRES[type_elements]), 1)
        elif type_elements == _CHAINE:
            for _ in range(nombre):
                (n,) = struct.unpack("<Q", _lire(f, 8))
                f.seek(n, 1)
        else:
            for _ in range(nombre):
                _lire_valeur(f, type_elements)
        return {"longueur": nombre}
    raise GgufInvalide(f"Type de valeur inconnu : {type_}.")


def cle(meta: dict, nom: str):
    """Une métadonnée propre à l'architecture : cle(meta, "block_count") lit « qwen35.block_count »."""
    return meta.get(f"{meta.get('general.architecture')}.{nom}")
