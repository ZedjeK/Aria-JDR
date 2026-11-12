"""Le compte rendu de ce que fait le moteur, en lignes lisibles (🎲 ⚔️ 🧠 🩹…).

Les mêmes lignes servent à l'écran du joueur, avant la narration du MJ, et à la fiche du
combat en cours (combat.md) : le joueur et le MJ voient exactement la même vérité.
"""

from aria.economie import montant
from aria.personnage import Etat

VERBES = {"deplacer": "se déplace", "viser": "vise", "recharger": "recharge", "degainer": "dégaine",
          "garnir": "garnit"}
VERBES_INVENTAIRE = {"preparer": "sous la main", "ranger": "rangé", "poser": "abandonné"}


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
        if r["action"] == "garnir":
            arme = f" {r['cartouches_garnies']} cartouches à la main"
        elif r["action"] == "recharger" and "munitions" in r:
            arme = f" ({r['munitions']} dans l'arme)"
        return [f"⚔️ {session.combattant(r['qui']).nom} {VERBES[r['action']]}{arme}"]
    if o == "acheter":
        if not r["achete"]:
            return [f"💰 {a['objet']} : {r['raison']}"]
        return [f"💰 Acheté : {a['objet']} pour {montant(r['prix'], r['monnaie'])} (reste {montant(r['argent'], r['monnaie'])})"
                + (f" — {r['geste']}" if r.get("geste") else "")]
    if o == "vendre":
        if not r["vendu"]:
            return [f"💰 {a['objet']} : {r['raison']}"]
        return [f"💰 Vendu : {a['objet']} pour {montant(r['prix'], r['monnaie'])} (tu as {montant(r['argent'], r['monnaie'])})"]
    if o == "payer":
        return [f"💰 {a['service'].capitalize()} : −{montant(r['prix'], r['monnaie'])} (reste {montant(r['argent'], r['monnaie'])})"
                + (f", Santé mentale +{r['sm_gagnee']}" if "sm_gagnee" in r else "")]
    if o == "commander":
        if not r["commande"]:
            return [f"💰 Commande de {a['objet']} : {r['raison']}"]
        return [f"💰 Commandé : {a['objet']} pour {montant(r['prix'], r['monnaie'])}, livré {r['arrive']}"]
    if o == "niveau_de_vie":
        return [f"💰 Niveau de vie : {r['visage']} ({r['choisi']}), prochaine échéance {r['prochaine_echeance']}"]
    if o == "inventaire":
        if r["action"] == "regarnir":
            garnies = sum(r["cartouches_garnies"].values())
            return [f"🎒 Chargeurs regarnis : {garnies} cartouches"] if garnies else []
        return [f"🎒 {a['objet']} : {VERBES_INVENTAIRE[r['action']]}"]
    if o == "attaquer":
        return _decrire_attaque(r)
    if o == "lancer_sort":
        return _decrire_sort(r)
    if o == "attaquer_zone":
        return _decrire_zone(r)
    if o == "tirer_arme_montee":
        return _decrire_zone(r) if "cibles" in r else _decrire_attaque(r)
    if o == "tirer_sur_vehicule":
        jet_ = f" : {jet(r['attaque'])}" if "attaque" in r else ""
        lignes = [f"🎯 {r['attaquant']} tire sur {r['vehicule']} ({r['partie']}){jet_}"]
        if "structure_perdue" in r:
            lignes.append(f"   → −{r['structure_perdue']} structure (le blindage en arrête {r['blindage']}) → {r['etat']}")
        elif "attaque" in r and not r["touche"]:
            lignes.append("   → Raté.")
        return lignes + [f"   → {e}" for e in r.get("effets", [])]
    if o == "eperonner":
        lignes = [f"🚗 {r['attaquant']} éperonne {r['cible']} : {jet(r['attaque'])} contre {jet(r['defense'])}"]
        if r["touche"]:
            reste = (f", il reste {r['pv']} PV" if "pv" in r
                     else f", structure {r['structure_cible']}" if "structure_cible" in r else "")
            lignes.append(f"   → {r['degats']} dégâts{reste} ; −{r['recul']} structure pour l'attaquant")
        return lignes + [f"   → {e}" for e in r.get("effets", [])]
    if o == "lance_fumigenes":
        return [f"💨 {r['vehicule']} : écran de fumée, {r['fumee_rounds']} rounds"]
    if o == "lancer_drone":
        return [f"🛸 {r['drone']} lancé ({r['mode']})"]
    if o == "piloter":
        return ([f"🚗 {r['vehicule']} : Pilotage {jet(r)}"] + ([f"   → {r['cale']}"] if "cale" in r else [])
                + (_decrire_accident(r["accident"]) if "accident" in r else []))
    if o == "reparer":
        return [f"🔧 {r['vehicule']} : {jet(r)} → {r['structure_rendue']:+d} structure ({r['structure']}, {r['etat']})"]
    if o == "debut_poursuite":
        return [f"🏁 Poursuite : {r['fuyard']} fuit, {r['zone']}"]
    if o == "round_poursuite":
        return _decrire_poursuite(r)
    if o == "fin_poursuite":
        return ["🏁 Fin de la poursuite" + (f" : {r['issue']}" if r.get("issue") else "")]
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
        monnaie = session.univers.monnaie
        return [f"🕐 {r['moment']}"] + [
            f"💰 Jour {e['jour']}, le coût de la vie ({e['niveau_de_vie']}) : "
            + (f"{montant(e['cout'], monnaie)} impayés, te voilà à la rue" if e.get("impayee")
               else f"−{montant(e['cout'], monnaie)}, il te reste {montant(e['argent'], monnaie)}")
            for e in r.get("echeances", [])] + [f"📦 Ta commande est arrivée : {nom}" for nom in r.get("commandes_arrivees", [])]
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


def _decrire_accident(a: dict) -> list[str]:
    lignes = [f"💥 Accident, {a['vehicule']} ({a['vitesse']}) : −{a['structure_perdue']} structure → {a['etat']}"]
    for o in a["occupants"]:
        lignes.append(f"   → {o['qui']} : {o['degats']} dégâts" + (f", il reste {o['pv']} PV" if "pv" in o else ""))
        if o.get("etat", Etat.ACTIF.value) != Etat.ACTIF.value:
            lignes.append(f"   → {o['qui']} est {o['etat']}")
    return lignes


def _decrire_poursuite(r: dict) -> list[str]:
    if "evenement" not in r:
        return ["🏁 Poursuite : " + (r.get("issue") or "des poursuivants renoncent")]
    lignes = [f"🏁 Round {r['round']} de poursuite, {r['zone']} : {r['evenement']}"]
    for o in r.get("obstacles", []):
        lignes.append(f"   {o['qui']} : {jet(o)} → {o['effet']}")
    for d in r.get("duels", []):
        jets = f"{jet(d['fuyard'])} contre {jet(d['jet_poursuivant'])}" if "fuyard" in d else "pas de jet"
        issue = f"{d['gagnant']} gagne {d['crans']} cran{'s' if d['crans'] > 1 else ''}" if d["gagnant"] else "rien ne bouge"
        lignes.append(f"   {d['poursuivant']} : {jets} → {issue} ({d['distance']})")
        lignes += [f"   → {e}" for e in d.get("effets", [])]
    for a in r.get("accidents", []):
        lignes += _decrire_accident(a)
    lignes += [f"   → {e}" for e in r.get("effets", [])]
    if r.get("nouvelle_zone"):
        lignes.append(f"   → La poursuite passe : {r['nouvelle_zone']}")
    if r.get("issue"):
        lignes.append(f"   → Fin : {r['issue']}")
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
