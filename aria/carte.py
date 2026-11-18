"""La carte de la campagne, pour l'afficher : la disposition des quartiers et ce que la page en montre.

Le monde (aria/monde.py) est un graphe : des districts, des quartiers qui ont des voisins, des factions qui les
tiennent. Il n'a pas de coordonnées. Ce module les calcule, toujours pareil pour la même carte : rien n'est rangé
dans la sauvegarde, et une campagne d'avant la carte graphique la reçoit aussi.

La page ne montre que ce que le joueur sait déjà par la commande « carte » : qui tient quoi, les chefs, les
rivalités, sa réputation, les lieux des quartiers qu'il a visités.
"""

import math

from aria import lieux, monde

LARGEUR = 100.0  # la carte tient dans un carré de 100 sur 100
MARGE = 9.0
ITERATIONS = 120
RAYON_DU_DISTRICT = 0.3  # la place d'un district sur l'anneau des districts, au départ


def _depart(etat: dict) -> dict[str, tuple[float, float]]:
    """Les districts sur un anneau, leurs quartiers en petit cercle autour de leur centre."""
    districts = list(etat["districts"])
    points = {}
    for i, district in enumerate(districts):
        angle = 2 * math.pi * i / len(districts) - math.pi / 2
        centre = (0.0, 0.0) if len(districts) == 1 else (math.cos(angle), math.sin(angle))
        membres = etat["districts"][district]
        for j, quartier in enumerate(membres):
            if len(membres) == 1:
                points[quartier] = centre
                continue
            a = 2 * math.pi * j / len(membres) - math.pi / 2
            points[quartier] = (centre[0] + RAYON_DU_DISTRICT * math.cos(a), centre[1] + RAYON_DU_DISTRICT * math.sin(a))
    return points


def disposition(etat: dict) -> dict[str, tuple[float, float]]:
    """La place de chaque quartier, dans un carré de 100 sur 100 : les voisins proches, les districts groupés.

    Un départ sur anneau, puis une relaxation à forces : les quartiers se repoussent, les voisins s'attirent. Rien
    n'est tiré au hasard : la même carte donne toujours la même disposition."""
    points = _depart(etat)
    noms = list(points)
    if len(noms) == 1:
        return {noms[0]: (LARGEUR / 2, LARGEUR / 2)}
    aretes = sorted({tuple(sorted((q, v))) for q in noms for v in etat["quartiers"][q]["voisins"]})
    district_de = {q: etat["quartiers"][q]["district"] for q in noms}
    ideal = 0.5
    chaleur = 0.4
    for _ in range(ITERATIONS):
        force = {q: [0.0, 0.0] for q in noms}
        for i, a in enumerate(noms):
            for b in noms[i + 1:]:
                dx, dy = points[a][0] - points[b][0], points[a][1] - points[b][1]
                d = max(math.hypot(dx, dy), 0.01)
                pousse = ideal * ideal / d
                # Deux quartiers du même district se repoussent moins : le district reste un groupe
                if district_de[a] == district_de[b]:
                    pousse *= 0.6
                for q, signe in ((a, 1), (b, -1)):
                    force[q][0] += signe * dx / d * pousse
                    force[q][1] += signe * dy / d * pousse
        for a, b in aretes:
            dx, dy = points[a][0] - points[b][0], points[a][1] - points[b][1]
            d = max(math.hypot(dx, dy), 0.01)
            tire = d * d / ideal
            for q, signe in ((a, -1), (b, 1)):
                force[q][0] += signe * dx / d * tire
                force[q][1] += signe * dy / d * tire
        for q in noms:
            fx, fy = force[q]
            norme = max(math.hypot(fx, fy), 0.01)
            pas = min(norme, chaleur)
            points[q] = (points[q][0] + fx / norme * pas, points[q][1] + fy / norme * pas)
        chaleur = max(chaleur * 0.96, 0.005)
    return _dans_le_carre(points)


def _dans_le_carre(points: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Le dessin tient dans le carré, centré, sans être déformé."""
    xs, ys = [p[0] for p in points.values()], [p[1] for p in points.values()]
    largeur, hauteur = max(xs) - min(xs), max(ys) - min(ys)
    echelle = (LARGEUR - 2 * MARGE) / max(largeur, hauteur, 0.01)
    decalage_x = (LARGEUR - largeur * echelle) / 2 - min(xs) * echelle
    decalage_y = (LARGEUR - hauteur * echelle) / 2 - min(ys) * echelle
    return {q: (round(x * echelle + decalage_x, 1), round(y * echelle + decalage_y, 1)) for q, (x, y) in points.items()}


def vue(etat: dict | None) -> dict | None:
    """Ce que la page affiche de la carte ; None : cette campagne n'a pas de monde."""
    if etat is None:
        return None
    places = disposition(etat)
    visites = set(etat["lieux"]["connus"]) if lieux.actifs(etat) else set()
    quartiers = {}
    for nom, q in etat["quartiers"].items():
        endroits = [{"nom": l["nom"], "type": l["type"], "tenancier": l["tenancier"]["nom"]}
                    for l in lieux.du_quartier(etat, nom)] if nom in visites else []
        quartiers[nom] = {"district": q["district"], "maitre": q["maitre"], "controle": q["controle"],
                          "dispute": monde.dispute(etat, nom), "voisins": list(q["voisins"]),
                          "x": places[nom][0], "y": places[nom][1], "visite": nom in visites, "lieux": endroits,
                          "pour_y_aller": monde.a(nom)}  # « au Pont », « à la Ruche » : la phrase du joueur est française
    districts = [{"nom": d, "quartiers": list(membres), "dominant": monde.domine(etat, d)}
                 for d, membres in etat["districts"].items()]
    factions = {}
    for nom, f in etat["factions"].items():
        factions[nom] = {"type": f["type"], "chef": f["chef"], "rivale": f["rivale"],
                         "reputation": monde.reputation(etat, nom),
                         "quartiers": sum(q["maitre"] == nom for q in etat["quartiers"].values())}
    return {"ici": etat["ici"], "districts": districts, "quartiers": quartiers, "factions": factions}
