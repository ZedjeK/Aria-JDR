import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

from appli import identite, mises_a_jour as maj

EXE = maj.nom_exe()


# ------------------------------------------------------------------ Outils des tests


class FausseReponse(io.BytesIO):
    """Ce que renvoie urllib.request.urlopen : un flux lisible, avec l'adresse finale après les redirections."""

    def __init__(self, contenu: bytes, url: str):
        super().__init__(contenu)
        self._url = url

    def geturl(self):
        return self._url


class FauxGitHub:
    """Répond à la place de GitHub et garde les requêtes reçues."""

    def __init__(self, reponses: dict[str, bytes], redirection: str | None = None):
        self.reponses = reponses
        self.redirection = redirection
        self.requetes = []

    def __call__(self, requete, timeout=None):
        self.requetes.append(requete)
        if requete.full_url not in self.reponses:
            raise OSError("hôte injoignable")
        return FausseReponse(self.reponses[requete.full_url], self.redirection or requete.full_url)


def nom_zip(version: str) -> str:
    return f"{identite.EXE}-{version}.zip"


def url_zip(version: str) -> str:
    return f"{maj.prefixe_telechargement()}v{version}/{nom_zip(version)}"


def reponse_api(version="9.0.0", contenu=b"zip", **remplace) -> bytes:
    fichier = {"name": nom_zip(version), "browser_download_url": url_zip(version), "size": len(contenu),
               "digest": "sha256:" + hashlib.sha256(contenu).hexdigest()}
    fichier.update(remplace.pop("fichier", {}))
    racine = {"tag_name": f"v{version}", "draft": False, "prerelease": False,
              "html_url": f"{maj.depot()}/releases/tag/v{version}", "assets": [fichier]}
    racine.update(remplace)
    return json.dumps(racine).encode()


def faire_zip(chemin: Path, fichiers: dict[str, bytes], liste: list[str] | None = None, dossier="Aria-Essai-9.0.0") -> Path:
    """Un zip comme celui de tools\\empaqueter.ps1 : un dossier racine, les fichiers et fichiers.txt."""
    liste = sorted(fichiers) if liste is None else liste
    with zipfile.ZipFile(chemin, "w") as zf:
        for nom, contenu in fichiers.items():
            zf.writestr(f"{dossier}/{nom}", contenu)
        zf.writestr(f"{dossier}/{maj.FICHIERS}", "\n".join(liste) + "\n")
    return chemin


def poser_version(dossier: Path, fichiers: dict[str, bytes]) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, contenu in fichiers.items():
        (dossier / nom).write_bytes(contenu)
    (dossier / maj.FICHIERS).write_text("\n".join(sorted(fichiers)) + "\n", encoding="utf-8")
    return dossier / EXE


# ------------------------------------------------------------------ Chercher


@pytest.mark.parametrize("tag,attendu", [("v1.2.3", (1, 2, 3)), ("v10.0.25", (10, 0, 25)), ("1.2.3", None),
                                         ("v1.2", None), ("v1.2.3-rc1", None), ("v1.2.x", None), ("v١.2.3", None),
                                         (None, None), ("v", None)])
def test_version_du_tag(tag, attendu):
    assert maj.version_du_tag(tag) == attendu


def test_empreinte():
    hexa = "ab" * 32
    assert maj.empreinte(f"sha256:{hexa.upper()}") == hexa
    assert maj.empreinte(f"sha512:{hexa}") is None
    assert maj.empreinte("sha256:abc") is None
    assert maj.empreinte("sha256:" + "zz" * 32) is None
    assert maj.empreinte(None) is None


def test_une_version_plus_recente_est_proposee():
    trouvee = maj.lire_reponse(reponse_api("9.0.0", b"contenu"), "0.1.0")
    assert trouvee.version == "9.0.0"
    assert trouvee.zip == maj.Fichier(nom_zip("9.0.0"), url_zip("9.0.0"), 7, hashlib.sha256(b"contenu").hexdigest())
    assert trouvee.page == f"{maj.depot()}/releases/tag/v9.0.0"


@pytest.mark.parametrize("actuelle", ["9.0.0", "9.0.1", "10.0.0"])
def test_la_meme_version_ou_une_plus_ancienne_n_est_pas_proposee(actuelle):
    assert maj.lire_reponse(reponse_api("9.0.0"), actuelle) is None


def test_les_numeros_se_comparent_comme_des_nombres():
    assert maj.lire_reponse(reponse_api("0.10.0"), "0.9.0").version == "0.10.0"


@pytest.mark.parametrize("remplace", [{"draft": True}, {"prerelease": True}, {"tag_name": "dernier"},
                                      {"assets": None}, {"assets": []}])
def test_brouillon_preversion_et_reponse_incomplete_ne_proposent_rien(remplace):
    assert maj.lire_reponse(reponse_api(**remplace), "0.1.0") is None


@pytest.mark.parametrize("fichier", [
    {"browser_download_url": "https://exemple.invalid/Aria.zip"},
    {"browser_download_url": f"http://github.com/{maj.PROPRIETAIRE}/{identite.EXE}/releases/download/v9.0.0/x.zip"},
    {"browser_download_url": f"https://github.com/autre/{identite.EXE}/releases/download/v9.0.0/x.zip"},
    {"size": 0}, {"size": "12"}, {"size": True},
    {"digest": None}, {"digest": "sha256:court"},
])
def test_un_zip_douteux_n_est_pas_propose(fichier):
    assert maj.lire_reponse(reponse_api(fichier=fichier), "0.1.0") is None


def test_seul_le_zip_de_la_version_compte():
    autre = json.loads(reponse_api())
    autre["assets"][0]["name"] = nom_zip("9.0.0") + ".sha256"
    assert maj.lire_reponse(json.dumps(autre), "0.1.0") is None


def test_une_page_hors_du_depot_est_remplacee_par_celle_du_depot():
    trouvee = maj.lire_reponse(reponse_api(html_url="https://exemple.invalid/piege"), "0.1.0")
    assert trouvee.page == f"{maj.depot()}/releases/latest"


@pytest.mark.parametrize("brut", [b"", b"pas du json", b"[]", b"null", b'{"tag_name": 3}'])
def test_une_reponse_illisible_ne_propose_rien(brut):
    assert maj.lire_reponse(brut, "0.1.0") is None


def test_chercher_interroge_une_seule_adresse_sans_rien_qui_identifie_l_utilisateur():
    github = FauxGitHub({maj.api_derniere_version(): reponse_api("9.0.0")})
    assert maj.chercher("0.1.0", ouvrir=github).version == "9.0.0"
    assert [r.full_url for r in github.requetes] == [maj.api_derniere_version()]
    en_tetes = dict(github.requetes[0].header_items())
    assert set(en_tetes) == {"User-agent", "Accept"}
    assert en_tetes["User-agent"] == f"{identite.EXE}/{identite.version()}"
    assert maj.api_derniere_version().startswith("https://api.github.com/repos/")


def test_chercher_ne_leve_jamais():
    assert maj.chercher("0.1.0", ouvrir=FauxGitHub({})) is None

    def plante(requete, timeout=None):
        raise ValueError("adresse invalide")

    assert maj.chercher("0.1.0", ouvrir=plante) is None


def test_chercher_refuse_une_reponse_demesuree():
    enorme = b" " * (maj.TAILLE_REPONSE_MAX + 1)
    assert maj.chercher("0.1.0", ouvrir=FauxGitHub({maj.api_derniere_version(): enorme})) is None


# ------------------------------------------------------------------ Télécharger


def test_telecharger_garde_le_zip_seulement_s_il_a_la_bonne_empreinte(tmp_path):
    contenu = b"le zip de la 9.0.0" * 1000
    trouvee = maj.lire_reponse(reponse_api("9.0.0", contenu), "0.1.0")
    chemin = maj.telecharger(trouvee, tmp_path, ouvrir=FauxGitHub({url_zip("9.0.0"): contenu}))
    assert chemin == tmp_path / nom_zip("9.0.0") and chemin.read_bytes() == contenu
    assert list(tmp_path.iterdir()) == [chemin]


@pytest.mark.parametrize("recu", [b"un autre contenu", b"le bon contenu en plus long", b"court"])
def test_telecharger_refuse_un_fichier_qui_n_est_pas_celui_annonce(tmp_path, recu):
    trouvee = maj.lire_reponse(reponse_api("9.0.0", b"le bon contenu"), "0.1.0")
    with pytest.raises(maj.ErreurMiseAJour):
        maj.telecharger(trouvee, tmp_path, ouvrir=FauxGitHub({url_zip("9.0.0"): recu}))
    assert list(tmp_path.iterdir()) == []  # ni zip ni « .part »


def test_telecharger_refuse_une_redirection_hors_de_https(tmp_path):
    trouvee = maj.lire_reponse(reponse_api("9.0.0", b"zip"), "0.1.0")
    github = FauxGitHub({url_zip("9.0.0"): b"zip"}, redirection="http://objets.exemple.invalid/zip")
    with pytest.raises(maj.ErreurMiseAJour, match="HTTPS"):
        maj.telecharger(trouvee, tmp_path, ouvrir=github)
    assert list(tmp_path.iterdir()) == []


def test_telecharger_refuse_une_adresse_hors_du_depot(tmp_path):
    piege = maj.MiseAJour("9.0.0", "", maj.Fichier("x.zip", "https://exemple.invalid/x.zip", 3, "00" * 32))
    github = FauxGitHub({"https://exemple.invalid/x.zip": b"zip"})
    with pytest.raises(maj.ErreurMiseAJour):
        maj.telecharger(piege, tmp_path, ouvrir=github)
    assert github.requetes == []


def test_une_coupure_reseau_devient_une_erreur_lisible(tmp_path):
    trouvee = maj.lire_reponse(reponse_api("9.0.0"), "0.1.0")
    with pytest.raises(maj.ErreurMiseAJour, match="échoué"):
        maj.telecharger(trouvee, tmp_path, ouvrir=FauxGitHub({}))


# ------------------------------------------------------------------ Liste des fichiers


def test_lire_liste(tmp_path):
    (tmp_path / maj.FICHIERS).write_text(f"﻿{EXE}\r\nLICENCES-TIERS.txt\r\n\r\n", encoding="utf-8")
    assert maj.lire_liste(tmp_path) == [EXE, "LICENCES-TIERS.txt"]


@pytest.mark.parametrize("contenu", ["", "LICENCES-TIERS.txt", f"{EXE}\n..\\secrets\\x", f"{EXE}\nsous/dossier.txt",
                                     f"{EXE}\nC:\\Windows\\x.dll", f"{EXE}\n..", f"{EXE}\n{maj.FICHIERS}"])
def test_une_liste_incoherente_est_refusee(tmp_path, contenu):
    (tmp_path / maj.FICHIERS).write_text(contenu, encoding="utf-8")
    assert maj.lire_liste(tmp_path) is None


def test_sans_liste_rien(tmp_path):
    assert maj.lire_liste(tmp_path) is None


# ------------------------------------------------------------------ Installer


@pytest.fixture
def lieux(tmp_path):
    """Le dossier de l'exe portable (version 0.1.0 en place), les versions gardées et le dossier de travail."""
    exe = poser_version(tmp_path / "jeu", {EXE: b"exe 0.1.0", "LICENCES-TIERS.txt": b"licences 0.1.0",
                                           "BUILDINFO.txt": b"build 0.1.0"})
    (tmp_path / "jeu" / "partie-du-joueur.txt").write_bytes(b"a lui")  # rangé à côté de l'exe : jamais touché
    return exe, tmp_path / "versions", tmp_path / "travail"


def nouvelle_version(travail: Path, **en_plus) -> Path:
    travail.mkdir(parents=True, exist_ok=True)
    fichiers = {EXE: b"exe 9.0.0", "LICENCES-TIERS.txt": b"licences 9.0.0", "BUILDINFO.txt": b"build 9.0.0"}
    fichiers.update(en_plus)
    return faire_zip(travail / nom_zip("9.0.0"), fichiers)


def test_installer_met_la_nouvelle_version_en_place_et_garde_l_ancienne(lieux, monkeypatch):
    exe, versions, travail = lieux
    monkeypatch.setattr(identite, "version", lambda: "0.1.0")
    archive = nouvelle_version(travail, **{"nouveau.dll": b"dll 9.0.0"})
    resultat = maj.installer(archive, exe, versions, travail)
    assert resultat == maj.Resultat(True, exe=exe)
    dossier = exe.parent
    assert exe.read_bytes() == b"exe 9.0.0" and (dossier / "nouveau.dll").read_bytes() == b"dll 9.0.0"
    assert (dossier / maj.FICHIERS).read_text(encoding="utf-8").split() == sorted(
        [EXE, "LICENCES-TIERS.txt", "BUILDINFO.txt", "nouveau.dll"])
    # L'ancienne version : de côté sous son numéro, et en « .ancien » jusqu'au prochain lancement
    assert (versions / "0.1.0" / EXE).read_bytes() == b"exe 0.1.0"
    assert (versions / "0.1.0" / maj.FICHIERS).is_file()
    assert (dossier / (EXE + maj.SUFFIXE_ANCIEN)).read_bytes() == b"exe 0.1.0"
    assert (dossier / "partie-du-joueur.txt").read_bytes() == b"a lui"
    assert not archive.exists() and not (travail / "extrait").exists()


def test_une_seule_version_est_gardee(lieux, monkeypatch):
    exe, versions, travail = lieux
    (versions / "0.0.9").mkdir(parents=True)
    (versions / "autre-chose").mkdir()
    monkeypatch.setattr(identite, "version", lambda: "0.1.0")
    assert maj.installer(nouvelle_version(travail), exe, versions, travail).fait
    assert sorted(p.name for p in versions.iterdir()) == ["0.1.0", "autre-chose"]


def test_un_exe_sans_fichiers_txt_garde_au_moins_l_exe(lieux, monkeypatch):
    exe, versions, travail = lieux
    (exe.parent / maj.FICHIERS).unlink()
    monkeypatch.setattr(identite, "version", lambda: "0.1.0")
    assert maj.installer(nouvelle_version(travail), exe, versions, travail).fait
    assert sorted(p.name for p in (versions / "0.1.0").iterdir()) == [EXE]


@pytest.mark.parametrize("cas", ["sans liste", "liste incoherente", "fichier manquant"])
def test_un_zip_incomplet_n_installe_rien(lieux, cas):
    exe, versions, travail = lieux
    travail.mkdir()
    fichiers = {EXE: b"exe 9.0.0", "LICENCES-TIERS.txt": b"l"}
    archive = travail / nom_zip("9.0.0")
    if cas == "sans liste":
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(f"d/{EXE}", b"exe 9.0.0")
    elif cas == "liste incoherente":
        faire_zip(archive, fichiers, liste=[EXE, "..\\..\\piege.txt"])
    else:
        faire_zip(archive, fichiers, liste=[EXE, "LICENCES-TIERS.txt", "absent.dll"])
    resultat = maj.installer(archive, exe, versions, travail)
    assert not resultat.fait and "rien n'est installé" in resultat.erreur.lower()
    assert exe.read_bytes() == b"exe 0.1.0" and not versions.exists()


def test_un_zip_qui_sort_de_son_dossier_est_refuse(lieux):
    exe, versions, travail = lieux
    travail.mkdir()
    archive = travail / nom_zip("9.0.0")
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../../evade.txt", b"piege")
    resultat = maj.installer(archive, exe, versions, travail)
    assert not resultat.fait
    assert not (travail.parent / "evade.txt").exists() and exe.read_bytes() == b"exe 0.1.0"


def test_un_fichier_qui_n_est_pas_un_zip_est_refuse(lieux):
    exe, versions, travail = lieux
    travail.mkdir()
    archive = travail / nom_zip("9.0.0")
    archive.write_bytes(b"pas un zip")
    assert not maj.installer(archive, exe, versions, travail).fait
    assert exe.read_bytes() == b"exe 0.1.0"


def test_un_exe_renomme_n_est_pas_mis_a_jour(lieux):
    exe, versions, travail = lieux
    renomme = exe.with_name("Copie de " + EXE)
    exe.rename(renomme)
    resultat = maj.installer(nouvelle_version(travail), renomme, versions, travail)
    assert not resultat.fait and EXE in resultat.erreur


def test_une_erreur_en_plein_echange_defait_tout(lieux, monkeypatch):
    exe, versions, travail = lieux
    dossier = exe.parent
    avant = {p.name: p.read_bytes() for p in dossier.iterdir()}
    vrai_replace = os.replace
    compte = {"n": 0}

    def replace_qui_casse(a, b):
        # Le troisième fichier mis en place échoue : les deux premiers doivent revenir à l'ancienne version
        if str(a).endswith(maj.SUFFIXE_NOUVEAU):
            compte["n"] += 1
            if compte["n"] == 3:
                raise PermissionError("fichier verrouillé")
        return vrai_replace(a, b)

    monkeypatch.setattr(maj.os, "replace", replace_qui_casse)
    monkeypatch.setattr(identite, "version", lambda: "0.1.0")
    resultat = maj.installer(nouvelle_version(travail), exe, versions, travail)
    assert not resultat.fait and "Rien n'a changé" in resultat.erreur
    assert {p.name: p.read_bytes() for p in dossier.iterdir()} == avant


def test_un_reste_de_mise_a_jour_precedente_ne_gene_pas(lieux, monkeypatch):
    exe, versions, travail = lieux
    (exe.parent / (EXE + maj.SUFFIXE_ANCIEN)).write_bytes(b"exe 0.0.9")
    monkeypatch.setattr(identite, "version", lambda: "0.1.0")
    assert maj.installer(nouvelle_version(travail), exe, versions, travail).fait
    assert (exe.parent / (EXE + maj.SUFFIXE_ANCIEN)).read_bytes() == b"exe 0.1.0"


# ------------------------------------------------------------------ Nettoyer et relancer


def test_nettoyer_ne_retire_que_les_restes_de_l_appli(lieux):
    exe, versions, travail = lieux
    dossier = exe.parent
    (travail / "extrait").mkdir(parents=True)
    for nom in (EXE + maj.SUFFIXE_ANCIEN, "BUILDINFO.txt" + maj.SUFFIXE_NOUVEAU, maj.FICHIERS + maj.SUFFIXE_ANCIEN,
                "photo.jpg" + maj.SUFFIXE_ANCIEN):
        (dossier / nom).write_bytes(b"reste")
    maj.nettoyer(dossier, travail)
    assert not travail.exists()
    assert sorted(p.name for p in dossier.iterdir()) == sorted(
        [EXE, "LICENCES-TIERS.txt", "BUILDINFO.txt", maj.FICHIERS, "partie-du-joueur.txt", "photo.jpg.ancien"])


def test_nettoyer_ne_leve_jamais(tmp_path):
    maj.nettoyer(tmp_path / "absent", tmp_path / "absent-aussi")
    maj.nettoyer(None, tmp_path / "absent")


@pytest.mark.parametrize("arguments,attendu", [([], None), (["--autre"], None), ([maj.ARGUMENT_APRES], None),
                                               ([maj.ARGUMENT_APRES, "x"], None), ([maj.ARGUMENT_APRES, "-4"], None),
                                               ([maj.ARGUMENT_APRES, "1234"], 1234)])
def test_pid_a_attendre(arguments, attendu):
    assert maj.pid_a_attendre(arguments) == attendu


def test_relancer_remet_l_environnement_de_pyinstaller_a_zero(monkeypatch, tmp_path):
    lances = []
    monkeypatch.setattr(maj.subprocess, "Popen", lambda args, **options: lances.append((args, options)))
    maj.relancer(tmp_path / EXE, 4321)
    args, options = lances[0]
    assert args == [str(tmp_path / EXE), maj.ARGUMENT_APRES, "4321"]
    assert options["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_depuis_les_sources_on_attend_ce_processus_et_rien_ne_se_met_a_jour(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert maj.processus_a_attendre() == os.getpid()
    assert maj.exe_en_cours() is None


def test_dans_l_exe_on_attend_le_chargeur_de_pyinstaller(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert maj.processus_a_attendre() == os.getppid()
    assert maj.exe_en_cours() == Path(sys.executable)


@pytest.mark.skipif(sys.platform != "win32", reason="attente d'un processus Windows")
def test_attendre_la_fin(tmp_path):
    import subprocess
    court = subprocess.Popen([sys.executable, "-c", "pass"])
    court.wait()
    assert maj.attendre_la_fin(court.pid, delai=5)
    long = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert not maj.attendre_la_fin(long.pid, delai=0.2)
    finally:
        long.kill()
        long.wait()
