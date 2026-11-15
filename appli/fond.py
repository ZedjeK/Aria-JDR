"""Règles du fond animé, communes à toutes les applis Aria. Le navigateur les applique (statique/app.js) : le motif, propre
à chaque appli, ne fait que dessiner un passage.

- coupé : désactivé dans les réglages, ou le système demande moins d'animations (prefers-reduced-motion) ;
- en pause : la page est cachée ; il reprend quand elle revient ;
- sinon il tourne, par passages dont la durée suit fond.vitesse et le nombre d'éléments est tiré au hasard entre
  fond.minimum et fond.maximum.
"""

import random

from appli.donnees import Fond

DUREES = {"lente": 14.0, "normale": 7.0, "rapide": 3.5}  # secondes par passage

COUPE, EN_PAUSE, ACTIF = "coupe", "en pause", "actif"


def mode(fond: Fond, page_visible: bool, animations_systeme: bool) -> str:
    """Coupé si fond.actif est faux ou si le système demande moins d'animations ; en pause si la page est cachée."""
    if not fond.actif or not animations_systeme:
        return COUPE
    return ACTIF if page_visible else EN_PAUSE


def duree_passage(fond: Fond) -> float:
    """14 s, 7 s ou 3,5 s selon fond.vitesse."""
    return DUREES[fond.assaini().vitesse]


def tirage(fond: Fond, hasard: random.Random | None = None) -> int:
    """Nombre d'éléments d'un passage, entre fond.minimum et fond.maximum compris."""
    bornes = fond.assaini()
    return (hasard or random).randint(bornes.minimum, bornes.maximum)
