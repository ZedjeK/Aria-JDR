# Aria-JDR — Livre de règles

Version 0.8 — 30 octobre 2026. Règles de l'étape 1, validées par Jérémy.

Ce document est la référence unique du système de jeu. Le moteur (code) l'applique à la lettre, et le MJ (LLM) s'en sert pour comprendre ce que le moteur lui renvoie.

---

## 1. Principes

### 1.1 Le code arbitre, le LLM raconte

- **Le code** gère toute la mécanique : jets de dés, PV, Santé mentale, compétences, inventaire, munitions, XP. Il lance aussi les dés des ennemis.
- **Le LLM** raconte, décrit, fait parler les PNJ et choisit les actions des ennemis. Quand une règle s'applique, il appelle un outil du moteur et raconte le résultat.
- Quand le LLM doit choisir une valeur (difficulté, gravité d'un choc…), il la choisit **dans une liste fermée**. Le code refuse toute autre valeur.

### 1.2 Les réglages d'univers

Chaque univers fixe deux réglages qui modulent les règles :

| Réglage | Valeurs | Effets |
|---|---|---|
| **Curseur de létalité** | Héroïque, Standard, Réaliste | PV, points de destin, mort instantanée, repos, tests de Santé mentale |
| **Monde impitoyable** | Oui, Non | Les chocs légers ne déclenchent plus de test de Santé mentale |

---

## 2. Résolution des actions

### 2.1 Le jet

On lance un d100 et on doit faire **inférieur ou égal** à la compétence (ou à la caractéristique). La compétence est la vraie chance de réussir.

### 2.2 Les degrés de réussite

| Jet | Résultat |
|---|---|
| ≤ compétence / 5 | **Critique** |
| ≤ compétence / 2 | **Réussite majeure** |
| ≤ compétence − 10 | **Réussite** |
| Les 10 derniers points sous la compétence | **Réussite avec complication** (hors combat uniquement) |
| > compétence | **Échec** |
| 100 si compétence ≥ 50, 96 à 100 sinon | **Maladresse** |

Exemple avec une compétence à 50 : critique 01-10, majeure 11-25, réussite 26-40, réussite avec complication 41-50, échec 51-99, maladresse 100.

- **Les degrés se calculent sur la valeur finale**, après le modificateur de difficulté (voir 2.3). Avec 60 et une difficulté Difficile, on joue à 40 : critique jusqu'à 08, majeure jusqu'à 20.
- **Un 01 est toujours une réussite**, même si la valeur finale est inférieure à 1. C'est une réussite simple, sauf si 01 est déjà dans la zone critique ou majeure. Le MJ ne demande pas de jet pour une action vraiment impossible.

- **Réussite avec complication** : l'action réussit, mais elle a un prix que le MJ raconte (bruit, temps perdu, matériel abîmé…).
- **En combat**, cette bande compte comme une **réussite simple** (voir 7.4).

### 2.3 La difficulté

Le MJ choisit la difficulté dans cette liste, et seulement dans cette liste :

| Difficulté | Modificateur |
|---|---|
| Facile | +20 |
| Normale | 0 |
| Difficile | −20 |
| Extrême | −40 |

### 2.4 Forcer le jet

Après un échec, le joueur peut relancer **une fois**, en changeant d'approche. S'il échoue à nouveau, la conséquence est **grave** (blessure, alarme, objet perdu…).

---

## 3. Caractéristiques

### 3.1 Les six caractéristiques

Notées de 15 à 90 (50 = humain moyen). On peut les lancer directement au d100 quand aucune compétence ne correspond.

| Caractéristique | Couvre |
|---|---|
| **Force** | Puissance physique, dégâts au corps à corps |
| **Constitution** | Endurance, résistance aux poisons et aux maladies |
| **Dextérité** | Agilité, précision, réflexes, initiative |
| **Intelligence** | Raisonnement, mémoire, déduction |
| **Volonté** | Sang-froid, résistance mentale, carburant de la magie |
| **Présence** | Charisme, aura, capacité à impressionner |

### 3.2 Les valeurs dérivées

| Valeur | Calcul |
|---|---|
| **Points de vie (PV)** | (Force + Constitution) / 10, **+25 en Héroïque, +15 en Standard**, +0 en Réaliste |
| **Santé mentale (SM)** | Volonté (maximum 99 − Mythe dans les univers d'Horreur) |
| **Points de magie (PM)** | Volonté / 5, seulement si l'univers active la magie |

Les valeurs dérivées sont recalculées automatiquement quand une caractéristique change.

---

## 4. Compétences

### 4.1 Les 24 compétences du socle

Le code ne connaît que ces 24 compétences. La base est ce que tout le monde sait faire sans entraînement.

| Domaine | Compétence | Base |
|---|---|---|
| Physique | Athlétisme | 20 |
| | Discrétion | 20 |
| | Esquive | Dextérité / 2 |
| Combat | Corps à corps | 25 |
| | Armes à distance | 20 |
| Perception & enquête | Perception | 25 |
| | Perspicacité | 10 |
| | Survie | 10 |
| | Investigation | 10 |
| Social & ruse | Persuasion | 10 |
| | Intimidation | 15 |
| | Tromperie | 5 |
| | Escamotage | 5 |
| | Arts | 5 |
| | Commandement | 5 |
| Savoirs | Érudition | 10 |
| | Sciences | 5 |
| | Médecine | 5 |
| | Occultisme | 5 |
| Technique | Artisanat | 5 |
| | Technologie | 5 |
| | Sécurité | 5 |
| | Pilotage | 20 |
| Surnaturel | Magie | 0 |

Ce que couvre chaque compétence :

- **Athlétisme** : courir, sauter, grimper, nager, lancer.
- **Discrétion** : se cacher, se déplacer sans bruit, filer quelqu'un.
- **Esquive** : éviter un coup, un projectile visible ou une explosion.
- **Corps à corps** : poings, lames, armes contondantes.
- **Armes à distance** : tout ce qui tire ou se lance pour blesser.
- **Perception** : repérer, écouter, fouiller, remarquer un détail.
- **Perspicacité** : deviner les intentions, sentir un mensonge, réconforter.
- **Survie** : pister, chasser, s'orienter, trouver un abri, s'occuper des animaux.
- **Investigation** : fouiller des archives, recouper des indices, éplucher des données.
- **Persuasion** : convaincre, négocier, séduire.
- **Intimidation** : faire peur, imposer sa volonté, interroger durement.
- **Tromperie** : mentir, bluffer, se déguiser.
- **Escamotage** : vol à la tire, tour de passe-passe, dissimuler un objet.
- **Arts** : musique, chant, comédie, peinture.
- **Commandement** : diriger, tactique, stratégie, galvaniser.
- **Érudition** : histoire, langues, culture, lois, géographie.
- **Sciences** : chimie, physique, biologie, mathématiques.
- **Médecine** : premiers soins, soigner, diagnostiquer, opérer.
- **Occultisme** : savoir sur le surnaturel, les cultes, les créatures.
- **Artisanat** : fabriquer, réparer, mécanique.
- **Technologie** : utiliser et détourner des systèmes complexes.
- **Sécurité** : serrures, pièges, alarmes, coffres.
- **Pilotage** : conduire, chevaucher, piloter.
- **Magie** : lancer des sorts, sentir et contrer la magie. Absente si l'univers désactive la magie.

### 4.2 Les trois couches

1. **Le socle** : les 24 compétences ci-dessus, toujours présentes. C'est ce que le code connaît et équilibre.
2. **L'habillage** : chaque univers renomme et redécrit les compétences. Le joueur ne voit que le nom de l'univers ; la mécanique reste identique.
3. **Les compétences thématiques** : de 0 à 3 compétences propres à l'univers (exemples en annexe B).

### 4.3 Règle de nommage

**On ne renomme une compétence que si son contenu change vraiment.** Technologie devient Piratage en Cyberpunk parce que la compétence ne couvre plus la même chose. En revanche, tirer reste tirer : Armes à distance, Survie et Médecine gardent leur nom dans tous les univers.

Conventions :

- **Commandement** reste Commandement dans les univers à hiérarchie (Fantasy, Dark fantasy, Militaire, Science-fiction, Historique, Steampunk) et devient **Meneur** ailleurs.
- **Pilotage** devient **Conduite & pilotage** quand l'univers mélange plusieurs types de véhicules.

### 4.4 Garde-fous des compétences thématiques

Une compétence thématique, qu'elle soit écrite à la main ou générée par le LLM, doit avoir :

- une base de **10 au maximum** ;
- un champ d'action clair, qui ne recouvre pas une compétence du socle.

Le code refuse toute compétence thématique qui ne respecte pas ces règles.

### 4.5 La magie selon l'univers

Si l'univers l'active, la Magie peut se découper en **écoles** (Pyromancie, Nécromancie…), devenir de la **Psionique** en science-fiction, ou rester rare et dangereuse en Horreur (chaque sort coûte aussi de la Santé mentale). Le coût des sorts reste à définir (voir 10).

---

## 5. Création de personnage

1. **Caractéristiques** : répartir **300 points** entre les six caractéristiques, chacune entre **20 et 80**. Les jets de dés (3d6 × 5) pourront être proposés en option.
2. **Parcours** : choisir un parcours de l'univers (l'équivalent d'un métier). Il donne **8 compétences**, entre lesquelles on répartit **300 points**.
3. **Points personnels** : **100 points** à répartir sur n'importe quelles compétences.
4. **Plafonds à la création** : **75** dans une compétence, **50** en Magie. Les points s'ajoutent à la base de la compétence.
5. **Roleplay** : une **motivation** (ce que le perso cherche), un **lien** (quelqu'un ou quelque chose qui compte pour lui) et un **défaut**. Ces trois lignes n'ont pas d'effet direct sur les règles, mais le lien sert à la Santé mentale (voir 9) et le MJ s'en sert pour l'histoire.

Comme les compétences thématiques, les parcours peuvent être générés par le LLM et sont validés par le code.

### Exemple : un Netrunner en Cyberpunk

- **Caractéristiques** : Force 35, Constitution 45, Dextérité 60, Intelligence 75, Volonté 50, Présence 35 (total 300). PV 23 en Standard (8 + 15), SM 50.
- **Parcours** (300 points) : Piratage 75, Data-mining 55, Contre-mesures 55, Vigilance 50, Infiltration 50, Bricolage tech 45, Arnaque 30, Sciences 20.
- **Points personnels** (100 points) : Armes à distance 50, Esquive 50, Conduite 40, Empathie 40.
- **Roleplay** : veut effacer sa dette envers une corpo ; sa petite sœur est sa seule famille ; fait trop confiance aux machines.

---

## 6. Progression

### 6.1 À l'usage (moteur principal)

- Chaque compétence **réussie** pendant une session est cochée par le code.
- En fin de session, pour chaque compétence cochée, on lance un d100 : si le jet est **supérieur** à la compétence, elle gagne **1d10**.
- Plafond : **95**.
- Seules les **compétences** progressent à l'usage. Les caractéristiques ne montent qu'avec l'XP.

### 6.2 Avec l'XP (en complément)

| Coût | Effet |
|---|---|
| 1 XP | +5 dans une compétence (entraînement entre deux aventures) |
| 3 XP | Apprendre une nouvelle compétence thématique ou un nouveau sort |
| 5 XP | +5 dans une caractéristique (plafond 90) |

- Quand une caractéristique monte, les PV, la SM et les PM **actuels** gagnent autant que leur maximum.
- Une compétence thématique apprise démarre à sa **valeur de base**, puis progresse comme les autres.
- L'**Esquive** n'est pas recalculée quand la Dextérité monte : elle progresse comme une compétence normale.
- Apprendre un nouveau sort attend les règles de magie (voir 10).

Les gains d'XP sont des montants fixes déclenchés par des **jalons** enregistrés par le code (session jouée, objectif atteint, arc terminé…), jamais décidés librement par le LLM. Les montants restent à définir. Les mêmes jalons servent à la récupération de Santé mentale (voir 9.5).

---

## 7. Combat

### 7.1 Initiative

- Ordre de **Dextérité** décroissante, sans jet. La **Perception** départage les égalités.
- **Embuscade** : Perception des victimes contre Discrétion des agresseurs ; une égalité profite aux victimes. Le camp surpris perd son premier round : il ne peut ni agir ni se défendre.

### 7.2 Le round

À chaque round, on choisit :

- **soit** 1 déplacement + 1 action simple + 1 action mineure ;
- **soit** 2 déplacements + 1 action mineure.

| Type d'action | Exemples |
|---|---|
| **Simple** | Attaquer, soigner, pirater, lancer un sort, une manœuvre (désarmer, plaquer, pousser) |
| **Mineure** | Viser, dégainer, recharger, se relever, ouvrir une porte, crier un ordre |

- **Viser** donne +20 au tir du même round, à condition de **ne pas se déplacer de tout le round**. La visée se perd en fin de round.
- **Recharger** coûte une action mineure ou simple, selon l'arme.
- Se mettre à couvert et fuir s'appuient sur les déplacements.

### 7.3 L'attaque

- L'attaquant lance sa compétence de combat (Corps à corps ou Armes à distance).
- **Au corps à corps**, le défenseur choisit d'**esquiver** (Esquive) ou de **riposter** (Corps à corps). C'est le **meilleur degré de réussite** qui l'emporte. En cas d'égalité, l'**esquive gagne**, mais la **riposte perd** face à l'attaquant.
- **Contre une arme à distance**, on n'esquive pas : le tireur subit −20 contre une cible derrière un couvert partiel, −40 derrière un couvert lourd.
- **Une seule défense gratuite par round.** Chaque défense supplémentaire dans le même round prend −20, cumulable.
- Le MJ peut fixer la **difficulté** d'une attaque, dans la liste fermée de 2.3 : par exemple Facile contre une cible sans défense (inconsciente, ligotée…).

### 7.4 Les degrés en combat

Il n'y a **pas de réussite avec complication** en combat : l'échelle est critique > majeure > réussite > échec > maladresse.

| Degré | Effet |
|---|---|
| **Critique** | Dégâts maximum, et l'armure ne compte qu'à moitié |
| **Réussite majeure** | Dégâts normaux + un bonus au choix : désarmer, repousser, ou +1 dé de dégâts |
| **Réussite** | Dégâts normaux |
| **Échec** | Raté |
| **Maladresse** | Raté, avec une conséquence fâcheuse racontée par le MJ (arme fragile cassée, chute…) |

### 7.5 Armes et armures

Chaque univers a **sa propre armurerie**. Le moteur ne fournit que le format des fiches et les garde-fous.

**Bonus de Force** : au corps à corps, on ajoute aux dégâts de l'arme un bonus qui dépend du perso, pas de l'arme.

| Force | Bonus aux dégâts |
|---|---|
| 40 ou moins | −1 |
| 41 à 60 | Aucun |
| 61 à 75 | +1d4 |
| 76 et plus | +1d6 |

**Fiche d'arme**

| Champ | Contenu |
|---|---|
| Arme | Le nom dans l'univers |
| Compétence | Corps à corps ou Armes à distance |
| Dégâts | Les dés lancés |
| Portée | Contact, courte, moyenne ou longue |
| Munitions | Capacité et coût du rechargement (action mineure ou simple) ; vide pour une arme de mêlée |
| Propriétés | Deux mains, rafale, perforante, dissimulable, lancer, silencieuse, encombrante, fragile… |
| Rareté | Voir l'échelle ci-dessous |
| Bonus | Selon la rareté |

Une arme **lancée** (javelot, dague…) quitte la main : il faut la récupérer. Une arme **fragile** se brise sur une maladresse.

**Fiche d'armure** : même principe (protection, malus, propriétés, rareté, bonus). L'armure réduit les dégâts reçus d'une valeur fixe.

**Échelle de rareté**, identique dans tous les univers et vérifiée par le code :

| Rareté | Bonus maximum |
|---|---|
| Commune | Aucun |
| Peu commune | +5 au jet **ou** +1 aux dégâts |
| Rare | +10 au jet **ou** +2 aux dégâts **ou** une propriété en plus |
| Exceptionnelle | Deux bonus **différents** de « Rare » (par exemple +10 au jet et +2 aux dégâts, jamais +20 au jet) |
| Légendaire | Unique, écrite à la main pour la campagne, jamais générée au hasard |

Pour une armure, même échelle : la protection suit la colonne des dégâts (+1, +2), et le malus en moins celle du jet (5 ou 10 points retirés à chaque malus de l'armure, sans jamais en faire un bonus).

**Exemple**

| Arme | Compétence | Dégâts | Portée | Munitions | Propriétés | Rareté | Bonus |
|---|---|---|---|---|---|---|---|
| Arc long elfique | Armes à distance | 1d8 | Longue | Carquois de 20, recharge mineure | Deux mains, silencieuse | Rare | +10 au jet |
| Pistolet lourd Arasaka | Armes à distance | 1d10 | Courte | Chargeur de 8, recharge mineure | Dissimulable | Peu commune | +1 aux dégâts |

### 7.6 Blessures

- **Blessure grave** : un seul coup qui inflige au moins la **moitié des PV max**. Test de Constitution, sinon le perso tombe inconscient. Tant qu'elle n'est pas guérie : **−20 à toutes les actions** et **PV max divisés par deux**.
- **0 PV** : à terre et mourant. Chaque round, test de Constitution ; un échec, et c'est la mort. **Sursis** : le premier test se fait à la fin du round **suivant** celui où il tombe, pas dans la foulée. Un allié peut stabiliser le mourant avec un jet de Médecine.
- **Mort instantanée** (mode Réaliste uniquement) : un seul coup qui inflige au moins les **PV max**.
- Une **seconde blessure grave** ne divise pas les PV max une deuxième fois.
- Un perso **inconscient** reste hors jeu jusqu'à la fin du combat, ou jusqu'à ce qu'on le soigne.

### 7.7 Points de destin

Un point de destin permet de **relancer un jet**, ou de transformer une mort (ou une folie) en « laissé pour mort ».

| Curseur | Points de destin par campagne | Mort instantanée |
|---|---|---|
| Héroïque | 3 | Non |
| Standard | 2 | Non |
| Réaliste | 1 | Oui |

### 7.8 Les ennemis

Profil simplifié : un pourcentage de combat (pour attaquer, esquiver et riposter), des PV, une armure, une arme. Le LLM choisit leurs actions ; le code lance leurs dés.

- Pas de bonus de Force : il est déjà compté dans les dégâts de leur arme.
- Par défaut : Dextérité 50, Constitution 50, Perception 25.
- Un PNJ peut avoir d'autres talents chiffrés (Médecine 70 pour un charcudoc, Perspicacité 60 pour un psy…) ; ses autres compétences valent 25. Il peut ainsi soigner un perso ou l'aider en thérapie.

---

## 8. Soins et repos

### 8.1 Soigner avec Médecine

| Résultat | PV rendus |
|---|---|
| Critique | 2d6 |
| Réussite majeure | 1d6 |
| Réussite | 1d3 |
| Échec | Rien |
| Maladresse | −1 PV (la plaie est aggravée) |

Plus la compétence est haute, plus les critiques et les réussites majeures sont fréquents : un bon médecin soigne mieux sans règle supplémentaire.

**Limite : un jet de Médecine par patient et par demi-journée**, au même rythme que les repos. Après un échec, il faut attendre la demi-journée suivante ou trouver un autre soigneur. Le jet qui soigne une blessure grave avant la nuit (voir 8.2) compte dans cette limite.

- Une **réussite avec complication** soigne comme une réussite (1d3), avec un prix raconté par le MJ.
- **Pas de jet de Médecine la nuit** : la nuit est réservée au repos long et à la thérapie de Santé mentale (voir 9.5).
- Un soin qui rend des PV **réveille** un perso inconscient, stabilisé ou mourant.
- Le soigneur peut être un PNJ. Un soigneur qui a lui-même une blessure grave subit son −20, en Médecine comme en thérapie.

### 8.2 Les repos

- **Un repos court ou moyen par demi-journée** (un le matin, un l'après-midi), plus le **repos long** la nuit.
- Un repos interrompu ne rapporte rien, mais il compte quand même comme pris : le temps est passé.

| Repos | Héroïque | Standard | Réaliste |
|---|---|---|---|
| Court (30 min) | 1/4 des PV | 1/4 des PV | Rien |
| Moyen (1 à 2 h) | 1/2 des PV | 1/2 des PV | 1/4 des PV |
| Long (nuit complète) | Tous les PV, blessures graves comprises, même sans soins | Tous les PV, blessures graves comprises **si elles ont été soignées** avant (jet de Médecine réussi) | 1/2 des PV ; une blessure grave soignée guérit au bout de 3 nuits de repos long |

Une blessure grave qui n'a pas été soignée ne guérit pas avec le repos.

---

## 9. Santé mentale

### 9.1 La base

La Santé mentale (SM) de départ est égale à la **Volonté**. En Horreur, elle ne peut pas dépasser **99 − Mythe**.

### 9.2 Le test de Santé mentale

Face à un choc, on lance un d100 contre la SM actuelle. Réussi, on perd peu ; raté, on perd beaucoup.

| Gravité | Perte si réussi / si raté |
|---|---|
| Choc léger | 0 / 1d3 |
| Choc sérieux | 1 / 1d6 |
| Choc grave | 1d3 / 1d10 |
| Horreur absolue | 1d6 / 1d20 |

### 9.3 La liste des chocs

Le LLM choisit le choc dans cette liste ; **le code calcule la gravité finale** avec les modificateurs.

**Choc léger**
- Découvrir le cadavre d'un inconnu
- Assister à une violence brutale (passage à tabac, exécution vue de loin)
- Voir une blessure atroce ou une mutilation
- Rester piégé dans le noir ou dans un espace confiné
- Vivre un phénomène étrange et inexpliqué

**Choc sérieux**
- Tuer un humain pour la première fois
- Voir mourir un allié
- Subir la torture ou une humiliation extrême
- Frôler la mort (tomber à 0 PV)
- Découvrir un charnier ou plusieurs corps mutilés
- Voir un phénomène surnaturel indéniable
- Trahir sa parole ou ses propres principes

**Choc grave**
- Perdre son lien (mort ou trahison de la personne qui compte)
- Assister à un massacre ou à une atrocité de masse
- Être possédé ou contrôlé mentalement
- Voir son propre corps se transformer (mutation, rejet d'implant, malédiction)

**Horreur absolue**
- Contempler une entité cosmique ou divine
- Découvrir une vérité qui brise la réalité
- Se retrouver face à son propre double ou à son propre cadavre

**Modificateurs**, appliqués par le code :

1. **Le lien amplifie** : si le choc concerne le lien du perso, il monte d'un cran. Sauf « perdre son lien », déjà grave parce qu'il concerne le lien : on ne le compte pas deux fois.
2. **L'accoutumance** : après trois chocs du même type, ce type descend d'un cran.
3. **La normalité de l'univers** : ce qui est banal dans l'univers descend d'un cran ou ne déclenche plus de test (exemple : un sort spectaculaire en Fantasy).

**Réglages d'univers**

- **Monde impitoyable** : les chocs légers ne déclenchent plus de test. Activé par défaut en Post-apo, Dark fantasy, Militaire et Cyberpunk ; désactivé en Contemporain et en Horreur.
- **Curseur** : en Héroïque, seuls les chocs graves et l'horreur absolue déclenchent un test. En Standard, tous les chocs. En Réaliste, « tuer un humain pour la première fois » et « voir mourir un allié » s'appliquent aussi en plein combat.

### 9.4 Les conséquences

- **5 points ou plus perdus d'un coup** : **crise passagère** pendant 1d6 rounds. Le code la tire au hasard, à chances égales, parmi : panique, paralysie, fuite, rage, hallucination. Le joueur perd le contrôle de son perso pendant la crise.
- **Un cinquième de la SM perdu dans la même journée** (par rapport à la SM du début de la journée) : **trouble durable**, tiré au hasard parmi : phobie, cauchemars, paranoïa, tremblements. −20 dans les situations liées ; le MJ s'en sert dans l'histoire. Un seul nouveau trouble par jour.
- **0 en SM** : le perso sombre dans la folie et devient un PNJ. Un point de destin peut l'en sauver : il remonte alors à 1 en SM.

### 9.5 La récupération

| Source | SM récupérée | Limite |
|---|---|---|
| Repos long + jet de Perspicacité ou de Médecine (par le perso ou un allié) | Même table que les PV : critique 2d6, majeure 1d6, réussite 1d3, échec rien, maladresse −1 | Une fois par nuit |
| Du temps avec son lien, ou une longue discussion avec quelqu'un | 1d3 | Une fois par jour |
| Un objectif ou une quête réussis | 1d6 | Jalon enregistré par le code |
| Un arc de campagne terminé ou une motivation accomplie | 1d10 | Jalon enregistré par le code |

- **Plafond** : jamais au-dessus de la SM de départ (la Volonté), ni au-dessus de 99 − Mythe en Horreur.
- **Un trouble durable disparaît** quand la SM retrouve son niveau du **début de la journée** où il est apparu, c'est-à-dire quand le perso a récupéré tout ce qu'il a perdu ce jour-là. Exemple : passé de 50 à 40 dans la journée, il guérit en revenant à 50.
- Un perso qui a sombré dans la folie ne récupère plus de SM.

---

## 10. À définir

- Les montants de gain d'XP par jalon.
- Les armureries de chaque univers (avec le générateur d'univers).
- Les effets chiffrés des propriétés **perforante** et **rafale**.
- Le coût et le fonctionnement des sorts (points de magie).
- Les tables de crises passagères et de troubles durables.
- L'inventaire : encombrement et prix.
- Les règles de pouvoirs pour le genre Super-héros (hors V1).

---

## Annexe A — Habillage des compétences par genre

Seules les compétences renommées sont listées ; les autres gardent le nom du socle. Historique et Horreur suivent le cadre choisi (époque et lieu) ; les noms ci-dessous correspondent au cadre par défaut.

Genres de la V1 : Fantasy, Dark fantasy, Horreur, Contemporain, Militaire, Science-fiction, Cyberpunk, Post-apo. Super-héros est hors V1.

| Genre | Compétences renommées | Magie |
|---|---|---|
| **Fantasy** | Corps à corps → Armes de mêlée · Investigation → Enquête · Persuasion → Éloquence · Tromperie → Duperie · Escamotage → Larcin · Arts → Musique & contes · Érudition → Lettres & légendes · Sciences → Philosophie naturelle · Occultisme → Savoir occulte · Artisanat → Forge & artisanat · Technologie → Mécanismes · Sécurité → Crochetage & pièges · Pilotage → Équitation & navigation | Arcanes |
| **Dark fantasy** | Corps à corps → Armes de mêlée · Perception → Vigilance · Perspicacité → Méfiance · Investigation → Enquête · Persuasion → Éloquence · Tromperie → Duperie · Escamotage → Larcin · Arts → Chants & récits · Érudition → Lettres anciennes · Sciences → Philosophie naturelle · Occultisme → Savoir impie · Artisanat → Forge & artisanat · Technologie → Mécanismes · Sécurité → Crochetage & pièges · Pilotage → Équitation | Sorcellerie |
| **Urban fantasy** | Corps à corps → Combat rapproché · Perspicacité → Psychologie · Tromperie → Mensonge · Escamotage → Pickpocket · Commandement → Meneur · Érudition → Culture générale · Artisanat → Mécanique · Technologie → Informatique · Sécurité → Serrures & alarmes · Pilotage → Conduite | Sortilèges |
| **Horreur** | Comme Urban fantasy | Rituels |
| **Super-héros** | Corps à corps → Combat rapproché · Commandement → Meneur · Érudition → Culture générale · Occultisme → Mystique · Artisanat → Mécanique · Technologie → Informatique · Pilotage → Conduite & pilotage | Pouvoirs |
| **Contemporain** | Comme Urban fantasy | Désactivée |
| **Espionnage** | Discrétion → Infiltration · Corps à corps → Combat rapproché · Perception → Observation · Perspicacité → Profilage · Investigation → Renseignement · Persuasion → Manipulation · Intimidation → Interrogatoire · Tromperie → Couverture · Commandement → Meneur · Érudition → Langues & cultures · Artisanat → Mécanique · Technologie → Informatique · Sécurité → Effraction · Pilotage → Conduite & pilotage | Désactivée |
| **Militaire** | Discrétion → Camouflage · Corps à corps → Combat rapproché · Perception → Observation · Investigation → Renseignement · Érudition → Histoire militaire · Artisanat → Mécanique · Technologie → Électronique · Sécurité → Pièges & déminage · Pilotage → Conduite & pilotage | Désactivée |
| **Historique** | Sciences → Sciences de l'époque · Occultisme → Croyances & superstitions · Technologie → Mécanismes · Sécurité → Crochetage | Désactivée |
| **Aventure / pulp** | Corps à corps → Bagarre · Tromperie → Bluff · Escamotage → Pickpocket · Commandement → Meneur · Érudition → Archéologie & histoire · Occultisme → Mythes & légendes · Artisanat → Mécanique · Technologie → Mécanismes · Sécurité → Pièges & serrures · Pilotage → Conduite & pilotage | Reliques (optionnelle) |
| **Western** | Corps à corps → Bagarre · Investigation → Enquête · Persuasion → Baratin · Tromperie → Bluff · Escamotage → Pickpocket · Commandement → Meneur · Érudition → Instruction · Occultisme → Folklore & légendes · Technologie → Mécanismes · Sécurité → Coffres & serrures · Pilotage → Équitation & attelages | Rituels (optionnelle) |
| **Steampunk** | Corps à corps → Escrime & boxe · Investigation → Enquête · Persuasion → Éloquence · Escamotage → Pickpocket · Sciences → Sciences naturelles · Occultisme → Spiritisme · Artisanat → Ingénierie · Technologie → Automates & machines · Sécurité → Serrures & coffres · Pilotage → Conduite & pilotage | Éther (optionnelle) |
| **Science-fiction** | Athlétisme → Athlétisme (zéro G) · Corps à corps → Combat rapproché · Persuasion → Diplomatie · Érudition → Xénoculture · Occultisme → Anomalies · Artisanat → Ingénierie · Technologie → Systèmes & IA · Sécurité → Contre-mesures · Pilotage → Conduite & pilotage | Psionique |
| **Cyberpunk** | Discrétion → Infiltration · Corps à corps → Combat rapproché · Perception → Vigilance · Perspicacité → Empathie · Investigation → Data-mining · Persuasion → Négociation · Tromperie → Arnaque · Escamotage → Doigts agiles · Arts → Performance · Commandement → Meneur · Érudition → Éducation · Occultisme → Légendes urbaines · Artisanat → Bricolage tech · Technologie → Piratage · Sécurité → Contre-mesures · Pilotage → Conduite | Désactivée |
| **Post-apo** | Corps à corps → Bagarre · Perception → Vigilance · Perspicacité → Flair · Investigation → Enquête · Persuasion → Marchandage · Tromperie → Embrouille · Escamotage → Chapardage · Arts → Conteur · Commandement → Meneur · Érudition → Savoir d'avant · Occultisme → Superstitions · Artisanat → Bricolage · Technologie → Tech d'avant · Sécurité → Pièges · Pilotage → Conduite | Désactivée (activable : mutants psi) |

## Annexe B — Compétences thématiques par genre

| Genre | Compétences thématiques |
|---|---|
| Fantasy | Alchimie (potions, poisons, élixirs), Foi (prières et miracles) |
| Dark fantasy | Démonologie (invoquer, lier, bannir), Foi (prières, exorcismes, inquisition) |
| Urban fantasy | Le Voile (factions, lois et lieux du monde caché), Réseau (contacts, indics) |
| Horreur | Mythe (savoir interdit ; réduit la SM maximum) |
| Super-héros | Contrôle des pouvoirs, Identité secrète |
| Contemporain | Bureaucratie, Réseau |
| Espionnage | Techniques d'espionnage (filatures, boîtes aux lettres mortes), Déguisement |
| Militaire | Transmissions (radios, chiffrement, brouillage), Explosifs |
| Historique | Selon l'époque (par exemple Étiquette, Héraldique) |
| Aventure / pulp | Cartographie, Langues anciennes |
| Western | Dégainer, Jeu (poker, paris, tricherie) |
| Steampunk | Inventions (gadgets), Bonnes manières |
| Science-fiction | Astrogation (sauts hyperspatiaux), Artillerie embarquée |
| Cyberpunk | Cybernétique (implants), Réseau (fixers, contacts) |
| Post-apo | Récupération (fouiller les ruines), Purification (eau, nourriture, décontamination) |
