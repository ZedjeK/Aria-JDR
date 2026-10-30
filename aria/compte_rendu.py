"""Le compte rendu de ce que fait le moteur, en lignes lisibles (🎲 ⚔️ 🧠 🩹…).

Les mêmes lignes servent à l'écran du joueur, avant la narration du MJ, et à la fiche du
combat en cours (combat.md) : le joueur et le MJ voient exactement la même vérité.
"""

from aria.personnage import Etat

VERBES = {"deplacer": "se déplace", "viser": "vise", "recharger": "recharge", "degainer": "dégaine"}


def jet(r: dict) -> str:
    return f"{r['jet']:02d} / {r['valeur']} → {r['degre']}"


def decrire(outil: str, arguments: dict, resultat: dict, session) -> list[str]:
    """Les lignes qui montrent un appel d'outil. Rien pour un appel raté ou sans effet."""
    o, a, r = outil, arguments if isinstance(arguments, dict) else {}, resultat
    if "erreur" in r:
        return []  # le MJ corrige lui-même ses erreurs d'appel
    if o in ("test_competence", "test_caracteristique"):
        difficulte = f" ({a['difficulte']})" if a.get("difficulte", "normale") != "normale" else ""
        return [f"🎲 {r.get('competence') or r.get('caracteristique')}{difficulte} : {jet(r)}"]
    if o == "forcer_jet":
        return [f"🎲 {r['test']}, jet forcé : {jet(r)}" + (" — conséquence grave !" if r["consequence_grave"] else "")]
    if o == "choc":
        if "jet" not in r:
            return [f"🧠 {r['choc']} : pas de test."]
        lignes = [f"🧠 {r['choc']} : Santé mentale {jet(r)}"
                  + (f", −{r['perte']} SM ({r['sante_mentale']})" if r["perte"] else "")]
        if "crise" in r:
            lignes.append(f"   Crise : {r['crise']['type']} pendant {r['crise']['rounds']} rounds.")
        if "trouble" in r:
            lignes.append(f"   Un trouble s'installe : {r['trouble']}.")
        if r.get("folie"):
            lignes.append("   Tu sombres dans la folie.")
        return lignes
    if o == "soigner":
        return [f"🩹 Médecine : {jet(r)}, +{r['pv_gagnes']} PV ({r['pv']})"]
    if o == "repos":
        return [f"💤 Repos {r['repos']} : +{r['pv_gagnes']} PV ({r['pv']})"]
    if o == "recuperer_sante_mentale":
        return [("🧠 Santé mentale : " + jet(r) + ", " if "jet" in r else "🧠 ")
                + f"+{r['sm_gagnee']} SM ({r['sante_mentale']})"]
    if o == "jalon":
        return [f"⭐ Jalon « {r['jalon']} » : +{r['sm_gagnee']} SM, +{r['xp_gagnee']} XP"]
    if o == "point_de_destin":
        return [f"✨ Point de destin dépensé ({r['points_destin_restants']} restants)"]
    if o == "creer_pnj":
        return [f"👤 {r['nom']} : combat {a['combat']}, {r['pv']} PV" + (f", {r['arme']}" if r["arme"] else "")]
    if o == "embuscade":
        perception = session.univers.nom_affiche("Perception")
        return [f"🎲 Embuscade : leur Discrétion {jet(r['discretion'])}, ta {perception} {jet(r['perception'])}"
                + (" → tu es surpris !" if r["joueur_surpris"] else " → tu les repères à temps.")]
    if o == "debut_combat":
        return [f"⚔️ Combat ! Initiative : {', '.join(r['ordre_initiative'])}"]
    if o == "action_combat":
        arme = f" ({a['arme']})" if a.get("arme") else ""
        return [f"⚔️ {session.combattant(r['qui']).nom} {VERBES[r['action']]}{arme}"]
    if o == "attaquer":
        return _decrire_attaque(r)
    if o == "stabiliser":
        return [f"🩹 Stabiliser : {jet(r)} → {r['etat']}"]
    if o == "fin_de_tour":
        return ([f"💀 {t['qui']} agonise : Constitution {jet(t)}" for t in r["tests_des_mourants"]]
                + ([f"⚔️ Round {r['round']}"] if r["nouveau_round"] else []))
    if o == "fin_combat":
        return ["⚔️ Fin du combat"]
    if o == "avancer_temps":
        return [f"🕐 {r['moment']}"]
    return []  # etat : le MJ se renseigne, rien ne change


def _decrire_attaque(r: dict) -> list[str]:
    lignes = [f"⚔️ {r['attaquant']} attaque {r['cible']} : {jet(r['attaque'])}"]
    if "defense" in r:
        lignes.append(f"   Défense : {jet(r['defense'])}")
    if "touche" in r:
        t = r["touche"]
        armure = f" (l'armure en arrête {t['armure']})" if t["armure"] else ""
        lignes.append(f"   → {t['qui']} est touché : {t['degats']} dégâts{armure}, il reste {t['pv']} PV")
        if t["blessure_grave"]:
            lignes.append("   → BLESSURE GRAVE !")
        if "test_constitution" in t:
            lignes.append(f"   → Constitution : {jet(t['test_constitution'])}")
        if t["etat"] != Etat.ACTIF.value:
            lignes.append(f"   → {t['qui']} est {t['etat']}")
    else:
        lignes.append("   → Le coup est évité." if r["issue"] == "défenseur" else "   → Raté.")
    lignes += [f"   → {effet}" for effet in r.get("effets", [])]
    return lignes
