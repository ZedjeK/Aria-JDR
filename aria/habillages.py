"""L'habillage des cartes (la carte de la campagne et celle du combat) : un par groupe de genres, que la page dessine
avec ses couleurs et sa police. Le joueur peut en imposer un dans les Réglages ; sinon, c'est celui du genre."""

from aria.bibliotheque import GENRES

HABILLAGES = {"neon": "Néon", "parchemin": "Parchemin", "gothique": "Gothique", "etat-major": "État-major",
              "rouille": "Rouille"}
PAR_DEFAUT = "neon"
DU_GENRE = {
    "Cyberpunk": "neon",
    "Science-fiction": "neon",
    "Fantasy": "parchemin",
    "Dark fantasy": "gothique",
    "Horreur": "gothique",
    "Militaire": "etat-major",
    "Contemporain": "etat-major",
    "Post-apo": "rouille",
}
assert set(DU_GENRE) == set(GENRES) and set(DU_GENRE.values()) <= set(HABILLAGES)


def du_genre(genre: str | None) -> str:
    """L'habillage d'un genre ; Néon pour un genre inconnu."""
    return DU_GENRE.get(genre or "", PAR_DEFAUT)
