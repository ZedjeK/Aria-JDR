"""Matériel, en-têtes GGUF et réglages du MJ selon la VRAM."""

import struct

import pytest

from aria import gguf
from aria.materiel import MIO, CarteGraphique, Materiel, lire_nvidia_smi
from aria.optimiseur import (GIO, LOT, MARGE, Modele, Reglages, cache_du_modele, decrire, paliers, planifier,
                             valeurs_kv_par_jeton, vram_estimee, vram_requise)

# L'en-tête de Bonsai 2 27B / Qwen3.8 27B : 64 couches, une attention classique toutes les 4
META_QWEN = {"general.architecture": "qwen35", "qwen35.block_count": 64, "qwen35.embedding_length": 5120,
             "qwen35.attention.head_count": 24, "qwen35.attention.head_count_kv": 4,
             "qwen35.attention.key_length": 256, "qwen35.attention.value_length": 256,
             "qwen35.full_attention_interval": 4, "qwen35.context_length": 262144}


def ecrire_gguf(chemin, meta: dict):
    """Un faux GGUF : l'en-tête seulement, avec des entiers (type 4), des chaînes (8) et un tableau (9)."""
    def chaine(s):
        donnees = s.encode()
        return struct.pack("<Q", len(donnees)) + donnees

    corps = b""
    for cle, valeur in meta.items():
        if isinstance(valeur, str):
            corps += chaine(cle) + struct.pack("<I", 8) + chaine(valeur)
        elif isinstance(valeur, list):
            corps += chaine(cle) + struct.pack("<IIQ", 9, 4, len(valeur)) + struct.pack(f"<{len(valeur)}I", *valeur)
        else:
            corps += chaine(cle) + struct.pack("<II", 4, valeur)
    chemin.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 0, len(meta)) + corps)


def modele(taille_gio: float, mtp=False) -> Modele:
    return Modele("Test", None, int(taille_gio * GIO), valeurs_kv_par_jeton(META_QWEN), mtp, 262144)


# --- Matériel ---------------------------------------------------------------------------------

def test_lecture_de_nvidia_smi():
    cartes = lire_nvidia_smi("NVIDIA GeForce RTX 4080 SUPER, 16376, 15061\nligne cassée\n")
    assert cartes == (CarteGraphique("NVIDIA GeForce RTX 4080 SUPER", 16376 * MIO, 15061 * MIO),)


def test_empreinte_et_vram():
    pc = Materiel((CarteGraphique("RTX 3060", 12288 * MIO, 11000 * MIO),
                   CarteGraphique("RTX 4080 SUPER", 16376 * MIO, 15061 * MIO)), None, 20)
    assert pc.empreinte == "RTX 4080 SUPER (16376 Mio)"
    assert pc.vram_libre == 15061 * MIO
    assert Materiel((), None, 4).empreinte == "sans carte NVIDIA"
    assert Materiel((), None, 4).vram_libre is None


# --- GGUF -------------------------------------------------------------------------------------

def test_lecture_d_un_en_tete(tmp_path):
    chemin = tmp_path / "test.gguf"
    ecrire_gguf(chemin, META_QWEN | {"tokenizer.ggml.tokens": list(range(600)), "qwen35.par_couche": [1, 2, 3]})
    meta = gguf.lire_metadonnees(chemin)
    assert meta["general.architecture"] == "qwen35"
    assert gguf.cle(meta, "block_count") == 64
    assert meta["tokenizer.ggml.tokens"] == {"longueur": 600}  # un long tableau est sauté
    assert meta["qwen35.par_couche"] == [1, 2, 3]  # un court tableau de nombres est lu


@pytest.mark.parametrize("contenu", [b"PASGGUF", b"GGUF\x03\x00"])
def test_fichier_invalide(tmp_path, contenu):
    chemin = tmp_path / "faux.gguf"
    chemin.write_bytes(contenu)
    with pytest.raises(gguf.GgufInvalide):
        gguf.lire_metadonnees(chemin)
    assert decrire(chemin) is None


def test_description_d_un_modele(tmp_path):
    chemin = tmp_path / "qwen.gguf"
    ecrire_gguf(chemin, META_QWEN | {"qwen35.nextn_predict_layers": 1})
    m = decrire(chemin, "Qwen")
    assert (m.nom, m.a_mtp, m.contexte_max, m.valeurs_kv) == ("Qwen", True, 262144, 16 * 4 * 512)


# --- Réglages ---------------------------------------------------------------------------------

def test_cache_d_un_modele_hybride():
    # 16 couches d'attention × 4 têtes K/V × (256 + 256) : 1 Gio de cache en f16 pour 16k jetons
    m = modele(0)
    assert m.valeurs_kv * 2 * 16384 == GIO
    assert vram_estimee(m, Reglages(16384)) == int(GIO + 0.6 * GIO)


def test_cache_d_un_modele_a_fenetres_glissantes():
    # Gemma 4 : des têtes et un motif de fenêtres donnés couche par couche, des clés plus courtes sous fenêtre
    meta = {"general.architecture": "gemma4", "gemma4.block_count": 6, "gemma4.embedding_length": 2816,
            "gemma4.attention.head_count": 16, "gemma4.attention.head_count_kv": [8, 8, 8, 8, 8, 2],
            "gemma4.attention.key_length": 512, "gemma4.attention.value_length": 512,
            "gemma4.attention.key_length_swa": 256, "gemma4.attention.value_length_swa": 256,
            "gemma4.attention.sliding_window_pattern": [1, 1, 1, 1, 1, 0], "gemma4.attention.sliding_window": 1024}
    # Une couche sur six garde tout le contexte ; les cinq autres, leur fenêtre et un lot
    assert cache_du_modele(meta) == (2 * (512 + 512), 5 * 8 * (256 + 256), 1024 + LOT)
    assert valeurs_kv_par_jeton(meta) == 2 * (512 + 512)
    m = Modele("Gemma", None, 0, *cache_du_modele(meta)[:1], False, 262144, *cache_du_modele(meta)[1:])
    ecart = vram_estimee(m, Reglages(32768)) - vram_estimee(m, Reglages(16384))
    assert ecart == 2 * (512 + 512) * 2 * 16384  # doubler le contexte ne coûte que la couche entière
    assert vram_estimee(m, Reglages(1024)) < vram_estimee(m, Reglages(4096))  # la fenêtre ne dépasse pas le contexte
    # Sans taille de fenêtre, les couches glissantes comptent comme des couches ordinaires (majorant)
    sans = {c: v for c, v in meta.items() if c != "gemma4.attention.sliding_window"}
    assert cache_du_modele(sans) == (5 * 8 * (256 + 256) + 2 * (512 + 512), 0, 0)
    # Un tableau trop long pour être lu : on ne sait pas, et on le dit
    assert cache_du_modele(meta | {"gemma4.attention.head_count_kv": {"longueur": 9000}}) is None


def test_paliers_avec_et_sans_mtp():
    # Pas de palier sous 16k : le prompt du MJ et ses outils n'y tiendraient pas
    assert [str(r) for r in paliers(modele(7))] == ["16k, cache f16", "16k, cache q8_0"]
    assert vram_requise(modele(7)) == vram_estimee(modele(7), Reglages(16384, "q8_0")) + MARGE
    assert [str(r) for r in paliers(modele(7, mtp=True))][:2] == ["16k, cache f16, MTP", "16k, cache q8_0, MTP"]


def test_planifier_selon_la_vram():
    bonsai, qwen = modele(6.7), modele(12.25, mtp=True)
    vram = int(14.7 * GIO)  # une 4080 SUPER avec Windows dessus
    assert planifier(bonsai, vram)[0] == Reglages(16384)
    assert all(not r.mtp for r in planifier(qwen, vram))  # la MTP ne tient pas en plus
    assert planifier(qwen, int(8 * GIO)) == []  # trop gros : écarté
    assert planifier(bonsai, None) == []  # pas de carte NVIDIA


def test_arguments_du_serveur():
    assert Reglages(12288, "q8_0", mtp=True).arguments() == [
        "-c", "12288", "-ngl", "99", "-np", "1", "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on", "--spec-type", "draft-mtp"]
