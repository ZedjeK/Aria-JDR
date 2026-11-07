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
        return [f"💤 Repos {r['repos']} : +{r['pv_gagnes']} PV ({r['pv']})"
                + (f", +{r['pm_gagnes']} PM ({r['pm']})" if "pm" in r else "")]
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
    if o == "lancer_sort":
        return _decrire_sort(r)
    if o == "attaquer_zone":
        return _decrire_zone(r)
    if o == "poser_implant":
        return [f"🦾 {r['implant']} : {jet(r)}"
                + (f" → posé, −{r['sm_max_perdue']} SM maximum ({r['sm_max']})" if r["pose"] else " → pas posé")]
    if o == "stabiliser":
        return [f"🩹 Stabiliser : {jet(r)} → {r['etat']}"]
    if o == "fin_de_tour":
        return ([_decrire_sauvegarde(s) for s in r.get("sauvegardes", [])]
                + [f"💀 {t['qui']} agonise : Constitution {jet(t)}" for t in r["tests_des_mourants"]]
                + ([f"⚔️ Round {r['round']}"] if r["nouveau_round"] else []))
    if o == "fin_combat":
        return ["⚔️ Fin du combat"]
    if o == "fin_scene":
        return [f"📖 Souvenir : {' '.join(a['titre'].split())}"]
    if o == "noter_pnj":
        return [f"📇 {r['nom']} : {r['attitude']}"]
    if o == "ouvrir_fil":
        return [f"🧵 Nouveau fil : {r['texte']}"]
    if o == "clore_fil":
        return [f"🧵 Fil clos : {r['texte']} → {r['issue']}"]
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


def _decrire_zone(r: dict) -> list[str]:
    degats = f", {r['jet_degats']} dégâts" if r.get("jet_degats") else ""
    lignes = [f"💥 {r['attaquant']}, {r['arme']} : {jet(r['attaque'])} → {r['issue']}{degats}"]
    lignes += [f"   → {effet}" for effet in r.get("effets", [])]
    for c in r["cibles"]:
        esquive = f" (esquive {jet(c['esquive'])})" if "esquive" in c else ""
        if "pv" in c:
            armure = f", l'armure en arrête {c['armure']}" if c["armure"] else ""
            lignes.append(f"   → {c['qui']}{esquive} : {c['degats']} dégâts{armure}, il reste {c['pv']} PV")
            if c["blessure_grave"]:
                lignes.append("   → BLESSURE GRAVE !")
            if c["etat"] != Etat.ACTIF.value:
                lignes.append(f"   → {c['qui']} est {c['etat']}")
        elif "degats" in c:
            lignes.append(f"   → {c['qui']}{esquive} : indemne")
        if "contre_l_eclat" in c:
            lignes.append(f"   → {c['qui']}, Constitution : {jet(c['contre_l_eclat'])}")
        lignes += [f"   → {c['qui']} : {effet}" for effet in c.get("effets", [])]
    return lignes


def _decrire_sort(r: dict) -> list[str]:
    lignes = [f"✨ {r['lanceur']} lance {r['sort']} ({r['puissance']}) : {jet(r['test'])}, −{r['pm_depenses']} PM "
              f"({r['pm_restants']})"]
    if r.get("pv_puises"):
        lignes.append(f"   → À court de PM : −{r['pv_puises']} PV")
    if r.get("sm_perdue"):
        lignes.append(f"   → −{r['sm_perdue']} SM")
    for c in r.get("cibles", []):
        if "degats" in c:
            armure = f" (l'armure en arrête {c['armure']})" if c.get("armure") else ""
            lignes.append(f"   → {c['qui']} est touché : {c['degats']} dégâts{armure}, il reste {c['pv']} PV")
            if c.get("blessure_grave"):
                lignes.append("   → BLESSURE GRAVE !")
            if c.get("etat", Etat.ACTIF.value) != Etat.ACTIF.value:
                lignes.append(f"   → {c['qui']} est {c['etat']}")
        elif "pv_gagnes" in c:
            lignes.append(f"   → {c['qui']} : +{c['pv_gagnes']} PV")
        if c.get("effet"):
            lignes.append(f"   → {c['qui']} : {c['effet']}")
    if "retour" in r:
        lignes.append(f"   → {r['retour']}")
    return lignes


def _decrire_sauvegarde(s: dict) -> str:
    issue = "l'effet s'arrête" if s["fini"] else "l'effet continue"
    degats = f", {s['degats']} dégâts" if s["degats"] else ""
    return f"🔥 {s['qui']}, {s['sort']} : sauvegarde {jet(s)}{degats} → {issue}"
