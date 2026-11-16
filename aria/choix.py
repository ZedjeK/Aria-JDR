"""Poser un choix au joueur dans une liste fermée : la troisième fonction du moteur, à côté de `entree` et `sortie`.

`choisir(titre, options)` renvoie l'indice de l'option choisie. Une option grisée dit pourquoi elle ne se choisit pas.
La console numérote les options ; la page (appli/partie.py) en fait des boutons. Sans `choisir`, le moteur garde son
comportement d'avant : c'est le MJ qui mène le combat (REGLES.md 7.8).
"""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Option:
    libelle: str
    raison: str = ""  # non vide : l'option est grisée, et c'est la raison pour laquelle on ne peut pas la choisir

    @property
    def active(self) -> bool:
        return not self.raison


Choisir = Callable[[str, list[Option]], int]


def choisir_console(entree: Callable[[str], str], dire: Callable[[str], None]) -> Choisir:
    """Le choix en console : une liste numérotée, et on tape le numéro. Un numéro grisé redit sa raison."""

    def choisir(titre: str, options: list[Option]) -> int:
        dire(titre)
        for numero, option in enumerate(options, 1):
            dire(f"  {numero}. {option.libelle}" + ("" if option.active else f"  (impossible : {option.raison})"))
        while True:
            reponse = entree("> ").strip()
            if not reponse.isdigit() or not 1 <= int(reponse) <= len(options):
                dire(f"Tape un nombre entre 1 et {len(options)}.")
                continue
            option = options[int(reponse) - 1]
            if option.active:
                return int(reponse) - 1
            dire(f"Impossible : {option.raison}.")

    return choisir
