"""Le lanceur d'Aria-JDR : le menu des campagnes et des réglages.

C'est le point d'entrée de l'exe portable, et de « python -m aria ».
"""

import os
import sys
import traceback
from dataclasses import replace
from pathlib import Path

from aria import (banc, banc_generateur, campagne, chemins, creation_texte, demo, generateur, jeu, llm, personnages,
                  trame)
from aria.bibliotheque import GENRES
from aria.campagne import Campagne
from aria.personnage import Etat
from aria.reglages import Curseur
from aria.sauvegarde import charger
from aria.univers import charger_univers

MENU = """
=== Aria-JDR ===
1. Nouvelle campagne
2. Reprendre une campagne
3. Personnages
4. Réglages
5. Quitter
"""
REGLAGES = """
=== Réglages ===
1. Le MJ de ce PC
2. Requalifier le MJ (environ 15 minutes)
3. Ouvrir le dossier des données
4. Corbeille des campagnes
5. Démo sans MJ (la ruelle, avec des menus)
6. Retour
"""
GENRE_COMPLET = "Cyberpunk"  # les autres genres ont encore peu de contenu dans la bibliothèque
RETOUR = ("", "r", "retour")
OUI = ("o", "oui")


def moteur_present(sortie=print) -> bool:
    if llm.MOTEUR.is_file():
        return True
    sortie(f"Le serveur du MJ est introuvable : {llm.MOTEUR}\n"
           f"Place le dossier Aria-LLM à côté de l'exe, ou dans {Path.home()}.")
    return False


def mj_disponible(entree=input, sortie=print) -> bool:
    """Vrai si un MJ qualifié peut tourner ; sinon dit ce qui manque et propose de le qualifier."""
    if not moteur_present(sortie):
        return False
    if banc.profil_valide():
        return True
    sortie("Pas encore de MJ qualifié sur ce PC.")
    if entree("Le qualifier maintenant (environ 15 minutes) ? (o/n) ").strip().lower() not in OUI:
        return False
    return banc.qualifier(afficher=sortie) is not None


# --- Les campagnes ------------------------------------------------------------------------------------

def resumer(nom: str) -> str:
    """Une campagne en une ligne : son univers, les réglages choisis, le personnage et où il en est."""
    c = Campagne.nommee(nom)
    try:
        if c.sauvegarde.is_file():
            partie = charger(c.sauvegarde)
            u, p = partie.univers, partie.personnage
            fin = (partie.monde or {}).get("trame", {}).get("fin", {}).get("nom")
            suite = f"{p.nom}, {p.parcours} · " + ("mort" if p.etat is Etat.MORT else
                                                   f"terminée ({fin})" if trame.arretee(partie.monde) else
                                                   str(partie.moment))
        else:
            u, suite = charger_univers(c.univers), "création du personnage à finir"
    except Exception as erreur:  # une campagne abîmée ne doit pas empêcher de voir les autres
        return f"{nom} — illisible ({type(erreur).__name__})"
    magie = "magie" if u.magie_active else "sans magie"
    return f"{nom} — {u.nom} ({u.genre}, {u.curseur.value}, {magie}) · {suite}"


def nouvelle_campagne(entree=input, sortie=print):
    """Les questions d'une nouvelle campagne, puis la partie : l'univers, le personnage, l'amorce."""
    sortie("\n=== Nouvelle campagne === (Entrée seule à la première question : retour)")
    while True:
        reponse = entree("Le nom de la campagne (lettres, chiffres, tirets) : ").strip()
        if not reponse:
            return
        nom = campagne.nom_valide(reponse)
        if nom is None:
            sortie("  ✗ 40 caractères au plus : des lettres sans accent, des chiffres et des tirets.")
        elif (campagne.racine() / nom).exists():
            sortie(f"  ✗ La campagne « {nom} » existe déjà.")
        else:
            break
    bibliotheque = generateur.charger()
    genre = choisir_genre(entree, sortie)
    choix = generateur.choix_par_defaut(bibliotheque, genre)
    reponse = entree(f"Le nom de l'univers (Entrée : {genre} ; « s » : le MJ propose le nom et le cadre) : ").strip()
    surprends_moi = reponse.lower() == "s"
    if reponse and not surprends_moi:
        choix = replace(choix, nom=reponse, cadre=entree("Le cadre, en une phrase (Entrée : aucun) : ").strip())
        while True:
            annee = entree("L'année du cadre (Entrée : le MJ la déduit) : ").strip()
            if not annee or annee.lstrip("-").isdigit():
                choix = replace(choix, annee=int(annee) if annee else None)
                break
            sortie("  ✗ Une année en chiffres, par exemple 1925.")
    curseurs = [c.value for c in Curseur]
    reponse = entree(f"Le ton ({' / '.join(curseurs)} ; Entrée : {choix.curseur}) : ").strip().lower()
    if reponse in curseurs:
        choix = replace(choix, curseur=reponse)
    if bibliotheque.genres[genre]["magie"]["statut"] == generateur.OPTION:
        choix = replace(choix, magie=entree("Avec de la magie ? (o/n) ").strip().lower() in OUI)
    erreurs = generateur.verifier_choix(bibliotheque, choix)
    if erreurs:
        for erreur in erreurs:
            sortie(f"  ✗ {erreur}")
        sortie("Campagne non créée : recommence.")
        return
    type_campagne = choisir_type(entree, sortie)
    predefini = choisir_personnage(genre, entree, sortie)
    if predefini is not None:
        cran = predefini.cran  # un personnage prêt garde l'expérience qu'on lui a donnée
    else:
        cran = choisir_cran(trame.TYPES[type_campagne].depart, entree, sortie)
    if mj_disponible(entree, sortie):
        trame.ecrire_format(Campagne.nommee(nom), trame.Format(type_campagne, cran))
        jeu.lancer(Campagne.nommee(nom), choix, surprends_moi, predefini=predefini)


def choisir_type(entree=input, sortie=print) -> str:
    """Le type de campagne (REGLES.md 14.1) : il fixe la longueur de la trame et la façon d'ouvrir."""
    types = list(trame.TYPES.values())
    sortie("\nLes types de campagne :")
    for i, t in enumerate(types, 1):
        sortie(f"  {i}. {t.nom.capitalize()} — {t.description}")
    while True:
        reponse = entree(f"Ton type (numéro ; Entrée : {trame.STANDARD}) : ").strip()
        if not reponse:
            return trame.STANDARD
        if reponse.isdigit() and 0 < int(reponse) <= len(types):
            return types[int(reponse) - 1].nom
        sortie(f"  ✗ Un numéro de 1 à {len(types)}, ou Entrée.")


def choisir_cran(conseille: str = trame.DEBUTANT, entree=input, sortie=print) -> str:
    """L'expérience de départ du personnage (REGLES.md 5)."""
    crans = list(trame.CRANS)
    while True:
        reponse = entree(f"Son expérience de départ ({' / '.join(crans)} ; Entrée : {conseille}) : ").strip().lower()
        if not reponse:
            return conseille
        trouve = [c for c in crans if c.startswith(reponse) or c.replace("é", "e").startswith(reponse)]
        if len(trouve) == 1:
            return trouve[0]
        sortie(f"  ✗ {', '.join(crans)}, ou Entrée.")


def choisir_genre(entree=input, sortie=print) -> str:
    sortie("\nLes genres :")
    for i, genre in enumerate(GENRES, 1):
        sortie(f"  {i}. {genre}" + ("" if genre == GENRE_COMPLET else " (contenu encore léger)"))
    while True:
        reponse = entree("Ton genre (numéro) : ").strip()
        if reponse.isdigit() and 0 < int(reponse) <= len(GENRES):
            return GENRES[int(reponse) - 1]
        sortie(f"  ✗ Un numéro de 1 à {len(GENRES)}.")


def choisir_personnage(genre: str, entree=input, sortie=print) -> "personnages.Predefini | None":
    """Pour une nouvelle campagne : un personnage préparé pour ce genre, ou None pour le créer sur place."""
    prets = personnages.lister(genre)
    if not prets:
        return None
    sortie("\nTes personnages prêts pour ce genre :")
    for i, pret in enumerate(prets, 1):
        sortie(f"  {i}. {pret.titre()}")
    while True:
        reponse = entree("Ton personnage (numéro ; Entrée : le créer pour cette campagne) : ").strip()
        if not reponse:
            return None
        if reponse.isdigit() and 0 < int(reponse) <= len(prets):
            return prets[int(reponse) - 1]
        sortie(f"  ✗ Un numéro de 1 à {len(prets)}, ou Entrée.")


def reprendre(entree=input, sortie=print):
    """La liste des campagnes : en reprendre une, ou en mettre une à la corbeille."""
    while True:
        noms = campagne.noms()
        if not noms:
            sortie("\nAucune campagne pour l'instant : commence par « Nouvelle campagne ».")
            return
        sortie("\n=== Tes campagnes ===")
        for i, nom in enumerate(noms, 1):
            sortie(f"{i}. {resumer(nom)}")
        reponse = entree("Un numéro pour reprendre, « s 2 » pour supprimer la 2, Entrée pour revenir : ").strip().lower()
        if reponse in RETOUR:
            return
        supprimer = reponse.startswith("s")
        numero = reponse[1:].strip() if supprimer else reponse
        if not (numero.isdigit() and 0 < int(numero) <= len(noms)):
            sortie(f"  ✗ Un numéro de 1 à {len(noms)}.")
            continue
        nom = noms[int(numero) - 1]
        if not supprimer:
            if mj_disponible(entree, sortie):
                jeu.lancer(Campagne.nommee(nom))
            return
        if entree(f"Mettre « {nom} » à la corbeille ? (o/n) ").strip().lower() in OUI:
            campagne.supprimer(nom)
            sortie(f"« {nom} » est dans la corbeille : tu peux la restaurer depuis les réglages.")


# --- Les personnages prédéfinis -------------------------------------------------------------------------

def menu_personnages(entree=input, sortie=print):
    """Les personnages préparés à l'avance : en créer un pour un genre, ou en supprimer un."""
    while True:
        prets = personnages.lister()
        sortie("\n=== Tes personnages ===")
        for i, pret in enumerate(prets, 1):
            sortie(f"{i}. {pret.titre()}")
        reponse = entree("« n » pour en créer un, « s 2 » pour supprimer le 2, Entrée pour revenir : ").strip().lower()
        if reponse in RETOUR:
            return
        if reponse == "n":
            nouveau_personnage(entree, sortie)
            continue
        numero = reponse[1:].strip() if reponse.startswith("s") else ""
        if not (numero.isdigit() and 0 < int(numero) <= len(prets)):
            sortie(f"  ✗ « n », « s » suivi d'un numéro de 1 à {len(prets)}, ou Entrée.")
            continue
        pret = prets[int(numero) - 1]
        if pret.fichier is None:
            sortie(f"  ✗ {pret.nom} est livré avec le jeu : il ne se supprime pas.")
        elif entree(f"Supprimer {pret.nom} pour de bon ? C'est définitif. (o/n) ").strip().lower() in OUI:
            personnages.supprimer(pret)
            sortie(f"{pret.nom} est supprimé.")


def nouveau_personnage(entree=input, sortie=print):
    """Crée un personnage dans l'univers de base d'un genre, puis le range. Avec le MJ s'il est disponible et
    si le joueur le veut : c'est lui qui propose le nom et la personnalité."""
    genre = choisir_genre(entree, sortie)
    univers = personnages.univers_de_base(genre)
    cran = choisir_cran(trame.DEBUTANT, entree, sortie)
    avec_mj = entree("Charger le MJ pour qu'il propose le nom et la personnalité ? (o/n) ").strip().lower() in OUI
    try:
        if avec_mj and mj_disponible(entree, sortie):
            with jeu.mj_charge() as mj:
                if mj is None:
                    return
                serveur, profil, _ = mj
                brouillon = creation_texte.Guide(univers, entree, sortie, serveur,
                                                 banc_generateur.budget_generateur(profil), cran=cran).composer()
        else:
            brouillon = creation_texte.Guide(univers, entree, sortie, cran=cran).composer()
    except creation_texte.Abandon:
        sortie("Création abandonnée.")
        return
    pret = personnages.enregistrer(brouillon, genre)
    sortie(f"\n{pret.nom} est prêt : tu pourras le prendre en lançant une nouvelle campagne de {genre}.")


# --- Les réglages ---------------------------------------------------------------------------------------

def montrer_mj(sortie=print):
    profil = banc.profil_valide()
    if profil is None:
        sortie("Pas de MJ qualifié sur ce PC : lance « Requalifier le MJ ».")
        return
    sortie(f"Modèle : {profil['modele']} ({profil['fichier']})")
    sortie(f"Réflexion : {profil['budget_reflexion']} jetons par action, "
           f"{banc_generateur.budget_generateur(profil)} pour créer un univers, un personnage ou une amorce.")
    sortie(f"Serveur : {llm.MOTEUR}")


def ouvrir_donnees(sortie=print):
    """Le dossier des données est toujours .Aria-JDR, dans le dossier de l'utilisateur : on ne le change pas,
    on l'ouvre."""
    sortie(f"Dossier des données : {chemins.DONNEES}")
    if hasattr(os, "startfile"):
        try:
            os.startfile(chemins.DONNEES)
        except OSError as erreur:
            sortie(f"Impossible de l'ouvrir ({erreur}).")


def gerer_corbeille(entree=input, sortie=print):
    while True:
        jetees = campagne.jetees()
        if not jetees:
            sortie("\nLa corbeille est vide.")
            return
        sortie("\n=== Corbeille ===")
        for i, jetee in enumerate(jetees, 1):
            sortie(f"{i}. {jetee}")
        reponse = entree("Un numéro pour restaurer, « vider » pour tout effacer, Entrée pour revenir : ").strip().lower()
        if reponse in RETOUR:
            return
        if reponse == "vider":
            if entree(f"Effacer pour de bon ces {len(jetees)} campagnes ? C'est définitif. (o/n) ").strip().lower() in OUI:
                sortie(f"{campagne.vider_corbeille()} campagnes effacées.")
            continue
        if not (reponse.isdigit() and 0 < int(reponse) <= len(jetees)):
            sortie(f"  ✗ Un numéro de 1 à {len(jetees)}, ou « vider ».")
            continue
        nom = campagne.restaurer(jetees[int(reponse) - 1])
        sortie(f"« {nom} » est restaurée." if nom else "  ✗ Une campagne du même nom existe déjà : supprime-la d'abord.")


def reglages(entree=input, sortie=print):
    while True:
        sortie(REGLAGES)
        choix = entree("Ton choix : ").strip().lower()
        if choix == "1":
            montrer_mj(sortie)
        elif choix == "2":
            if moteur_present(sortie) and banc.qualifier(afficher=sortie):
                banc_generateur.main([])  # puis le générateur d'univers, avec le modèle retenu
        elif choix == "3":
            ouvrir_donnees(sortie)
        elif choix == "4":
            gerer_corbeille(entree, sortie)
        elif choix == "5":
            demo.main()
        elif choix in ("6", *RETOUR):
            return
        else:
            sortie("Choisis de 1 à 6.")


def menu(entree=input, sortie=print):
    chemins.DONNEES.mkdir(exist_ok=True)
    while True:
        sortie(MENU)
        try:
            choix = entree("Ton choix : ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        try:
            if choix == "1":
                nouvelle_campagne(entree, sortie)
            elif choix == "2":
                reprendre(entree, sortie)
            elif choix == "3":
                menu_personnages(entree, sortie)
            elif choix == "4":
                reglages(entree, sortie)
            elif choix == "5":
                return
            else:
                sortie("Choisis de 1 à 5.")
        except KeyboardInterrupt:
            sortie("\nInterrompu.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        menu()
    except Exception:
        traceback.print_exc()
        if chemins.EMBARQUE:  # sinon la console de l'exe se fermerait avant qu'on lise l'erreur
            input("\nAria-JDR a planté. Appuie sur Entrée pour fermer.")


if __name__ == "__main__":
    main()
