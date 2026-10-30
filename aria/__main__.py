"""Le lanceur d'Aria-JDR : un menu pour jouer avec le MJ, essayer la démo ou qualifier le MJ.

C'est le point d'entrée de l'exe portable, et de « python -m aria ».
"""

import sys
import traceback
from pathlib import Path

from aria import banc, chemins, demo, jeu, llm

MENU = """
=== Aria-JDR ===
1. Jouer avec le MJ
2. Démo sans MJ (la ruelle, avec des menus)
3. Qualifier le MJ sur ce PC (environ 15 minutes)
4. Quitter
"""


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
    if entree("Le qualifier maintenant (environ 15 minutes) ? (o/n) ").strip().lower() not in ("o", "oui"):
        return False
    return banc.qualifier(afficher=sortie) is not None


def menu(entree=input, sortie=print):
    chemins.PARTIES.mkdir(exist_ok=True)
    while True:
        sortie(MENU)
        try:
            choix = entree("Ton choix : ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        try:
            if choix == "1":
                if mj_disponible(entree, sortie):
                    jeu.main()
            elif choix == "2":
                demo.main()
            elif choix == "3":
                if moteur_present(sortie):
                    banc.qualifier(afficher=sortie)
            elif choix == "4":
                return
            else:
                sortie("Choisis 1, 2, 3 ou 4.")
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
