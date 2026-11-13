# Aria-JDR — Livre de règles

Version 1.2 — 12 novembre 2026. Règles validées par Jérémy.

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

À la création d'une campagne, ils sont **préremplis selon le genre** ; le joueur peut tout changer, sauf la magie là où le genre l'impose (annexe A) :

| Genre | Létalité | Monde impitoyable | Chocs banals (sans test) | Magie |
|---|---|---|---|---|
| Fantasy | Héroïque | Non | Phénomène étrange, surnaturel indéniable | Activée |
| Dark fantasy | Standard | Oui | Violence brutale, cadavre d'un inconnu | Activée |
| Horreur | Réaliste | Non | Aucun | Activée |
| Contemporain | Standard | Non | Aucun | Désactivée |
| Militaire | Standard | Oui | Violence brutale, cadavre d'un inconnu | Désactivée |
| Science-fiction | Standard | Non | Phénomène étrange | Activée |
| Cyberpunk | Standard | Oui | Violence brutale | Désactivée |
| Post-apo | Réaliste | Oui | Violence brutale, cadavre d'un inconnu | En option, désactivée par défaut |

### 1.3 La bibliothèque

Aria-JDR est une **bibliothèque** : tout ce qui peut exister dans une partie y est rangé une seule fois (parcours, compétences thématiques, domaines et sorts, armes, armures, modifications, implants, véhicules, événements de route…), avec ses étiquettes :

- **ses genres**, un par un ou par raccourci : *médiéval* (Fantasy, Dark fantasy), *moderne* (Contemporain, Horreur, Militaire, Cyberpunk, Post-apo), *futuriste* (Cyberpunk, Science-fiction), *tous* ;
- **sa condition de magie** : seulement avec magie (le Mage, les domaines), ou indifférent ;
- **électronique** ou non : c'est ce qui grille sous une IEM (voir 7.10) ;
- **son année d'apparition** (armes, armures, véhicules) : une campagne n'a que ce qui existe à l'année de son cadre. Un véhicule n'est jamais plus ancien que les armes qu'il porte.

Une campagne ne crée rien de zéro :

1. Le joueur choisit le genre, le cadre et la magie.
2. Le **filtre** ne garde de la bibliothèque que ce qui y a droit.
3. Le **générateur** pioche dans ce qui reste, adapte les noms au cadre et à l'époque (le pistolet lourd devient un Colt .45 dans les années 1920), et ajoute quelques touches propres à la campagne, que le moteur vérifie.
4. L'univers de la campagne est **une copie figée** dans son dossier : si la bibliothèque évolue, la campagne en cours ne change pas.

La bibliothèque se remplit genre par genre, et elle grandit en jouant : un objet, un PNJ ou un sort inventé en campagne peut y être versé, après validation du joueur.

Ainsi, **le logiciel porte tout ce qui est règle et contenu ; le LLM n'a qu'à raconter** l'histoire autour.

Les listes de la bibliothèque vivent dans des fichiers de données que le moteur vérifie ; les annexes de ce livre en sont des vues lisibles.

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

Si l'univers l'active, la Magie peut se découper en **écoles** (Pyromancie, Nécromancie…), devenir de la **Psionique** en science-fiction, ou rester rare et dangereuse en Horreur (chaque sort coûte aussi de la Santé mentale). Les règles des sorts sont en 10.

---

## 5. Création de personnage

1. **Caractéristiques** : répartir **300 points** entre les six caractéristiques, chacune entre **20 et 80**. Les jets de dés (3d6 × 5) pourront être proposés en option.
2. **Parcours** : choisir un parcours de l'univers (l'équivalent d'un métier). Il donne **8 compétences**, entre lesquelles on répartit **300 points**.
3. **Points personnels** : **100 points** à répartir sur n'importe quelles compétences.
4. **Plafonds à la création** : **75** dans une compétence, **50** en Magie. Les points s'ajoutent à la base de la compétence.
5. **Roleplay** : une **motivation** (ce que le perso cherche), un **lien** (quelqu'un ou quelque chose qui compte pour lui) et un **défaut**. Ces trois lignes n'ont pas d'effet direct sur les règles, mais le lien sert à la Santé mentale (voir 9) et le MJ s'en sert pour l'histoire.

Comme les compétences thématiques, les parcours peuvent être générés par le LLM et sont validés par le code.

**Les parcours** sont les métiers du monde : ils servent au personnage du joueur, et aussi aux compagnons et aux PNJ (exemples par genre en annexe D).

- Un parcours a un nom, une description de 3 phrases (ce qu'il fait, comment le monde le voit, ses forces et sa faiblesse) et 8 compétences distinctes.
- Un parcours de lanceur de sorts contient la Magie, seulement dans un univers qui l'active ; il conseille des domaines, sans les imposer.
- Un parcours n'est pas obligé de savoir se défendre : un salaryman ou un fermier n'a ni arme ni Esquive. Mais si le personnage du joueur n'a aucune compétence parmi Corps à corps, Armes à distance, Esquive ou Magie, la création le prévient : sans compagnon pour le protéger, le premier combat peut lui être fatal. Le joueur choisit en connaissance de cause.
- À la création, tout l'équipement du personnage est **d'origine** (voir 7.5) : rien d'usé, rien de personnalisé, qui se gagne en jouant.
- Le parcours donne **une armure au plus**, et beaucoup n'en donnent pas : c'est le métier qui décide. À la création, sa protection est de **3 au plus** ; les armures de protection 4 se gagnent en jouant (les PNJ peuvent en porter d'emblée). Une armure implantée et une armure portée ne se cumulent pas (voir 11.3), dès la création.
- Le parcours donne aussi **de 2 à 3 objets racontés** (un deck, une trousse de soins, un badge…). Ils n'ont jamais de bonus chiffré, mais ils peuvent ouvrir ou fermer une action : sans deck, pas de piratage à distance. C'est le MJ qui en juge. On peut les perdre, se les faire voler ou les casser.
- Dans un univers qui a des implants, le parcours peut donner **un implant de gamme standard** (un neuroport, des lames-mantis…), qui coûte ses 2 points de Santé mentale maximum dès la création (voir 11.4). Les implants avancés et militaires se gagnent en jouant.
- Un parcours peut ne donner **aucune arme** (une idol, un salaryman…). Comme pour la défense, la création prévient sans interdire : le personnage devra en trouver une, ou compter sur ses compagnons.
- **Le joueur choisit son équipement dans des listes.** Pour chaque case (arme, armure, implant, et véhicule si le métier l'exige), le parcours propose de 2 à 3 options ; pour les objets racontés, il en propose 3 ou 4, dont on garde 2. Toutes les options d'une case se valent, et chacune respecte les règles ci-dessus.
- À la création, l'équipement est **générique** : pas de fabricant, car sa modification d'usine serait un bonus gratuit (voir 7.5). Les marques se gagnent en jouant.
- Un parcours ne propose un **véhicule** (léger ou moyen, d'origine) que si le métier l'exige : le pick-up du nomade, la moto du coursier.
- L'**esthétique** (tatouages lumineux, cheveux de fibre optique…) est offerte à la création, en plus du reste ; ensuite, elle s'achète (voir 13).
- Un objet raconté peut être une **relation** (des fans fidèles, des faveurs qu'on lui doit, une source anonyme) : le MJ la fait jouer dans l'histoire, et elle pourra devenir un compagnon.
- L'équipement de départ dépend de l'**armurerie de chaque univers** : le générateur écrit les listes de chaque parcours dans celle qu'il vient de créer, et le code vérifie que tout existe, que tout est d'origine, que la protection ne dépasse pas 3 et que l'implant est de gamme standard.
- L'argent de départ dépend du rang de revenu du métier, et vient en plus de l'équipement (voir 13.4). Ensuite, un objet s'achète, se trouve ou se gagne (voir 13).
- Un univers a **de 15 à 30 parcours** : un maximum, pour le choix du joueur et pour peupler le monde. Le générateur part de ceux du genre (annexe D), les adapte au cadre et à l'époque, retire ceux qui n'y ont pas leur place (les parcours de magie si elle est désactivée) et en ajoute de propres au cadre.

### L'expérience de départ

Le joueur choisit l'expérience de son personnage, selon le type de campagne (voir 14.1) :

| Expérience | Points personnels | Plafond d'une compétence | Plafond en Magie | Pièces au-dessus | Argent de départ |
|---|---|---|---|---|---|
| Débutant | 100 | 75 | 50 | aucune | selon le rang (13.4) |
| Aguerri | 200 | 85 | 60 | 1 | un palier au-dessus |
| Vétéran | 300 | 90 | 65 | 2 | deux paliers au-dessus |

- Les **300 points de parcours** ne changent pas : le métier reste le même.
- **Une pièce au-dessus** : une arme personnalisée (de marque, le plus souvent), une armure de protection 4 ou un implant de gamme avancée, pris dans l'univers. Une seule de chaque sorte. L'arme ou l'armure remplace celle du métier ; l'implant s'ajoute, avec son prix en Santé mentale maximum.
- Un personnage prêt (voir « Les personnages prédéfinis ») garde l'expérience qu'on lui a donnée.
- L'antagoniste de la campagne suit l'expérience du personnage (voir 14.9).

### La création guidée

À chaque étape, le code propose et le joueur garde, relance ou saisit lui-même. « Tout proposer » fait tout d'un coup :

- **Le code propose les chiffres** : des caractéristiques orientées par le parcours, les points sous les plafonds, une défense et une compétence de combat grâce aux points personnels, l'équipement tiré dans les listes.
- **Le LLM propose le nom et la personnalité** (motivation, lien, défaut, allure en deux phrases). Le code vérifie ; si rien de valide ne sort, le joueur les écrit.
- Pour varier les propositions, le code tire si le personnage est **une femme ou un homme** (le joueur peut le choisir), trois initiales possibles pour son prénom et le genre de son lien (un parent, un mentor, un lieu, une promesse…).

### Les personnages prédéfinis

Le joueur peut préparer un personnage à l'avance, hors campagne, pour un genre : il le crée avec les métiers et l'équipement de base du genre, tels que la bibliothèque les donne.

- Quand une campagne de ce genre commence avec lui, le générateur **garde son métier** dans l'univers, quoi qu'il adapte par ailleurs.
- Son équipement prend les noms que le cadre lui a donnés. Ce que le cadre a retiré est reproposé dans les listes de son métier, et le jeu le dit.
- S'il ne peut pas vivre dans cet univers (un lanceur de sorts dans un univers sans magie), le joueur crée un personnage sur place.
- Kaito, le Netrunner de Néo-Tokyo, est livré avec le jeu.

### L'amorce de la campagne

Après la création, l'amorce pose ce qui existe avant la première scène. Elle part d'un **plan** en une phrase :

- **l'idée du joueur**, telle quelle ;
- ou, s'il n'est pas inspiré, **un plan tiré dans la bibliothèque** : 50 plans valables dans tous les genres, plus ceux du genre de l'univers (15 par genre, écrits avec chaque genre), corsé par **une complication** tirée à part parmi 20. Un plan déjà pioché ne revient pas, d'une campagne à l'autre, tant qu'il en reste des neufs.

Le LLM adapte le plan au cadre et au personnage, et le code vérifie :

- **son passé**, en deux ou trois phrases ;
- **le lieu** où tout commence et **la situation** d'ouverture, qui lance le plan sans décider à la place du joueur ;
- **de 2 à 4 PNJ** vivants qu'il connaît déjà, dont celui de son lien si c'est une personne vivante ;
- **de 1 à 3 fils** ouverts, dont un tiré de sa motivation ;
- **un secret** : ce que le personnage ignore (qui ment, qui tire les ficelles). Il n'est jamais montré au joueur ; le MJ le garde comme un fil, qu'il clôt quand le personnage le découvre.

Le joueur voit tout sauf le secret (le reste, son personnage le sait déjà), puis garde l'amorce, en demande une autre ou donne une autre idée. Gardée, elle est rangée dans la mémoire de la campagne (souvenirs, PNJ, fils). Si le LLM ne propose rien de valide, le MJ ouvre la campagne seul.

### Exemple : un Netrunner en Cyberpunk

- **Caractéristiques** : Force 35, Constitution 45, Dextérité 60, Intelligence 75, Volonté 50, Présence 35 (total 300). PV 23 en Standard (8 + 15), SM 50 avant les implants.
- **Parcours** (300 points) : Piratage 75, Data-mining 55, Contre-mesures 55, Vigilance 50, Infiltration 50, Bricolage tech 45, Esquive 45, Arnaque 30.
- **Points personnels** (100 points) : Armes à distance 50, Esquive 50, Conduite 40, Empathie 40, Athlétisme 35.
- **Équipement**, choisi dans les listes du Netrunner : un pistolet silencieux, une veste renforcée, un neuroport (2 points de Santé mentale maximum : SM 48), un deck et une fausse identité numérique.
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
- Apprendre un nouveau sort reste à définir (voir 16) : à la création, le perso connaît déjà tous les sorts de ses deux domaines (voir 10.5).

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
- **Recharger** coûte une action mineure ou simple, selon l'arme. Les munitions sont comptées : voir 13.5 pour les chargeurs et le garnissage à la main.
- Un round dure **environ 6 secondes**.
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
| Calibre | Pour une arme à feu : une étiquette (« .45 ACP », « 5,56 mm »), sans effet sur les dégâts |
| Qualité | Voir l'échelle ci-dessous |
| Modifications | Selon la qualité |

Le **calibre** suit l'époque : dans la bibliothèque, une arme à feu a la liste de ses calibres avec leur année (le pistolet lourd : .45 ACP en 1911, .357 Magnum en 1935, .44 Magnum en 1955, .50 AE en 1991), et une campagne prend le plus récent qui existe à l'année de son cadre. Il donne son nom juste à l'arme ; plus tard, l'inventaire s'en servira pour les munitions compatibles.

Une arme **lancée** (javelot, dague…) quitte la main : il faut la récupérer. Une arme **fragile** se brise sur une maladresse. Contre une arme **perforante**, l'armure (ou le blindage) ne compte qu'à moitié.

**Fiche d'armure** : même principe (protection, malus, propriétés, qualité, modifications). L'armure réduit les dégâts reçus d'une valeur fixe.

**Bornes de l'armurerie**, vérifiées par le code avant les modifications :

- **Armes** : dégâts de **1d4 à 2d6+2**, soit une moyenne de 2,5 à 9 et 14 au plus. Au-delà de 1d10 (plus de 5,5 en moyenne), l'arme a la propriété **deux mains**.
- **Armures** : protection de **1 à 4**. À partir de 3, l'armure a **au moins un malus de −10**.
- Un objet **légendaire**, écrit à la main pour la campagne, échappe à ces bornes.

**Échelle de qualité**, la même pour les armes, les armures et les implants (voir 11), dans tous les univers, vérifiée par le code :

| Qualité | Emplacements de modification | Ce que c'est |
|---|---|---|
| **Usé** | 0 | Un objet abîmé, d'occasion ou bricolé, avec un défaut |
| **D'origine** | 1 | L'objet tel qu'il sort de l'atelier, celui de l'armurerie |
| **Personnalisé** | 2 | Un objet retouché par quelqu'un qui s'y connaît |
| **Unique** | 3 | Un objet d'exception, avec un nom et une histoire ; il peut être généré, mais rarement |

Les modifications (un viseur, un nouveau calibre, des plaques de renfort…) donnent les bonus de l'objet. Les noms des qualités suivent le genre : en Fantasy et en Dark fantasy, un objet d'origine est « ordinaire » et un objet personnalisé est « de maître ».

**Le défaut d'un objet usé**, au choix dans cette liste :

- une arme : −5 au jet, ou elle devient fragile ;
- une armure : −1 de protection (jamais en dessous de 1), ou un malus de −10 en plus ;
- un implant d'occasion ou du marché noir, mal calibré : 2 points de Santé mentale maximum perdus en plus (voir 11.4).

Un jet réussi de la compétence de l'objet (Artisanat pour une arme ou une armure, Cybernétique pour un implant, selon l'univers) **répare** un objet usé : il redevient d'origine.

Au-dessus de l'échelle, un objet **légendaire** est écrit à la main pour la campagne, et jamais généré.

**Les modifications**

1. Une modification occupe un emplacement (voir l'échelle de qualité ci-dessus).
2. Elle donne un seul petit effet, pris dans cette liste :

| Effet | Armes | Armures | Implants |
|---|---|---|---|
| Précision | +5 au jet | — | — |
| Puissance | +1 aux dégâts | +1 de protection | +5 au bonus de l'implant |
| Confort | — | 5 points de malus en moins | — |
| Propriété | une propriété en plus (silencieuse, perforante, dissimulable…) | — | — |
| Munitions | chargeur doublé, ou une recharge simple qui devient mineure | — | — |
| Utilitaire | un effet raconté, sans bonus chiffré | idem | idem |

3. Chaque modification ne se pose qu'une fois par objet : pour +10 au jet, il faut deux modifications différentes.
4. **Plafond**, quelle que soit la qualité : +10 au jet, +2 aux dégâts, +2 de protection, une seule propriété ajoutée ; un implant ne dépasse jamais +10. Le confort retire du malus sans jamais en faire un bonus.
5. **La pose** se fait hors combat, par un jet de la compétence de l'objet (Artisanat pour une arme ou une armure, Cybernétique pour un implant, selon l'univers) : réussi, la modification est posée ; raté, elle ne l'est pas, mais la pièce est récupérable ; maladresse, la pièce est cassée. Retirer ou échanger une modification demande le même jet.
6. Les modifications sont des objets : on les trouve, on les achète, on les récupère sur une arme usée. Chaque modification d'un implant coûte en plus 1 point de Santé mentale maximum (voir 11.4).

Les noms suivent le genre, pas les effets : en Fantasy, un « affûtage de maître » plutôt qu'un fil monomoléculaire. Des runes ne sont possibles que dans un univers avec magie, avec exactement les mêmes effets. Exemples en annexe F.

**Les fabricants**

Une arme, une armure, un implant ou un véhicule peut porter la marque d'un fabricant (une corpo, une forge, une guilde…). Un fabricant, c'est :

1. **Ses catégories** : ce qu'il fabrique, dans une liste fermée (armes de poing, fusils, armes intelligentes, armes de mêlée, armures, implants optiques, implants neuro, motos, voitures, utilitaires, AV…). Le code refuse une marque sur un objet qui n'est pas de ses catégories.
2. **Une modification d'usine par catégorie**, prise dans les listes de modifications : elle occupe un emplacement de l'objet. Un fabricant peut aussi n'en donner aucune, et sortir des objets usés.
3. **Une réputation**, racontée : qui l'aime, qui la déteste, ce qu'elle dit de son porteur. Le MJ en joue avec les PNJ.

Le générateur peut inventer des fabricants pour les catégories qui n'en ont pas, avec les mêmes règles. Ils suivent le genre : des corpos en Cyberpunk, des forges et des guildes en Fantasy. Exemples en annexe F.

**Exemple**

| Arme | Compétence | Dégâts | Portée | Munitions | Propriétés | Qualité | Bonus de ses modifications |
|---|---|---|---|---|---|---|---|
| Arc long elfique | Armes à distance | 1d8 | Longue | Carquois de 20, recharge mineure | Deux mains, silencieuse | Personnalisé | +10 au jet |
| Pistolet lourd Arasaka | Armes à distance | 1d10 | Courte | Chargeur de 8, recharge mineure | Dissimulable | Personnalisé | +1 aux dégâts |

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
- Son équipement est d'origine par défaut, usé pour un PNJ démuni (un ganger fauché), et jusqu'à personnalisé pour un PNJ puissant ou important (voir 7.5). Un objet unique reste rare, réservé par le MJ à des PNJ marquants ; un objet légendaire est toujours écrit à la main.

### 7.9 Les armes de zone

Une grenade, une roquette ou un obus touche une **zone**, pas une cible. Le combat n'a pas de carte : les zones sont abstraites, comme la propriété « zone » des sorts.

| Zone | Cibles au plus | Exemples |
|---|---|---|
| Petite | 2 cibles proches | grenade, lance-flammes |
| Moyenne | 4 cibles proches | roquette, obus de char |
| Grande | tous ceux qui sont là, 8 au plus | charge d'explosif, frappe d'AV |

Le MJ désigne les cibles présentes dans la zone, **alliés compris** ; le moteur vérifie leur nombre.

**Le jet de l'attaquant** : Athlétisme pour une grenade lancée, Armes à distance pour un lanceur, Explosifs (ou Artisanat sans cette compétence thématique) pour une charge posée.

| Résultat | Effet |
|---|---|
| Réussite | Le projectile tombe où il faut : les dégâts entiers sur chaque cible |
| Échec | Il dévie : la moitié des dégâts, et les cibles ont +20 pour esquiver |
| Maladresse | Il tombe aux pieds du lanceur : lui et ses voisins deviennent les cibles |

**Se protéger** : chaque cible peut esquiver (c'est sa défense gratuite du round). Esquive réussie, la moitié des dégâts ; majeure ou critique, aucun. Un couvert lourd divise aussi les dégâts par deux, en plus de l'esquive. L'armure compte, à moitié seulement contre une arme perforante (comme en 7.5).

**Bornes** : des dégâts de 2d6 à 4d6, au-delà des armes ordinaires ; un lanceur se tient à deux mains ; de 1 à 6 munitions ; une grenade ou une charge s'utilise une seule fois.

**Les effets spéciaux**

| Effet | Ce qu'il fait |
|---|---|
| Brûlure | Comme un sort persistant (10.6) : un jet de Constitution au début de chaque tour, 1d3 dégâts s'il est raté, 3 fois au plus |
| Fumée | Pas de dégâts ; tirer à travers donne un couvert lourd (−40) pendant 3 rounds |
| Aveuglant | Pas de dégâts ; test de Constitution, sinon −20 à tout pendant 1 round |
| IEM | Pas de dégâts ; tout ce qui est électronique dans la zone est touché (voir 7.10) |

Exemples en annexe F.

### 7.10 L'IEM et l'électronique

Une impulsion électromagnétique (grenade, mine, charge, drone brouilleur) touche tout ce qui porte l'étiquette **électronique** dans sa zone, selon sa fragilité :

| Ce qui est touché | Sans protection | Avec un blindage IEM |
|---|---|---|
| Drone | Grillé : une épave, à réparer en atelier | Coupé 1 round |
| Petite électronique (deck externe, téléphone, lunettes AR, radio) | Grillée : hors d'usage jusqu'à réparation (Bricolage tech) | Coupée 1 round |
| Implant | Coupé 1 round : plus de bonus ni d'effet ; une arme implantée est inutilisable, un système d'exploitation est éteint | Aucun effet |
| Yeux cybernétiques | Coupés 1 round, et la cible est aveuglée : −20 à tout pendant ce round | Aucun effet |
| Arme intelligente, modification électronique | Les bonus électroniques (viseur, pointeur, arme intelligente) sont coupés 1 round ; l'arme tire toujours | Aucun effet |
| Véhicule terrestre moderne | −1 cran de vitesse et pilote automatique coupé, pendant 1 round | Aucun effet |
| Véhicule aérien | Test de Pilotage difficile, sinon c'est l'accident (12.5) | Aucun effet |
| Arme ou objet mécanique | Rien | — |

- Un implant ne grille jamais : il est seulement coupé.
- Le **blindage IEM** est une modification (pour un implant, un drone, une arme intelligente, une petite électronique) ou un système défensif (pour un véhicule). Le **pare-feu**, lui, protège du piratage, pas de l'IEM.

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

**Limite : un soin réussi par patient et par demi-journée**, au même rythme que les repos. Après un échec, il faut attendre la demi-journée suivante ou trouver un **autre** soigneur : le même ne retente pas. Dès qu'un jet réussit, le patient a eu son soin de la demi-journée. Le jet qui soigne une blessure grave avant la nuit (voir 8.2) compte dans cette limite.

- Une **réussite avec complication** soigne comme une réussite (1d3), avec un prix raconté par le MJ.
- **Pas de jet de Médecine la nuit** : la nuit est réservée au repos long et à la thérapie de Santé mentale (voir 9.5).
- Un soin qui rend des PV **réveille** un perso inconscient, stabilisé ou mourant.
- Le soin magique a sa propre limite, qui se cumule avec celle-ci (voir 10.7).
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

## 10. Magie

Ces règles valent pour toute forme de magie : Arcanes en Fantasy, Psionique en science-fiction, Rituels en Horreur, mutants psi en Post-apo… Seul le nom change selon l'univers.

### 10.1 Les points de magie

- **PM = Volonté / 5** (voir 3.2), seulement si l'univers active la magie.
- Lancer un sort est une **action simple** (voir 7.2) : un jet de Magie, avec la difficulté que fixe sa puissance.

### 10.2 La puissance

Le MJ choisit la puissance dans cette liste ; elle fixe le coût et la difficulté.

| Puissance | Coût | Difficulté |
|---|---|---|
| Mineur | 1 PM | Facile (+20) |
| Modéré | 3 PM | Normale |
| Majeur | 6 PM | Difficile (−20) |

### 10.3 Les effets

Un sort a **un seul effet**, choisi dans cette liste : il imite une mécanique que le moteur connaît déjà.

| Effet | Mineur | Modéré | Majeur |
|---|---|---|---|
| **Attaque** | 1d6 | 2d6 | 3d6 |
| **Soin** | 1d3 PV | 1d6 PV | 2d6 PV |
| **Protection** (armure, jusqu'à la fin du combat) | +1 | +2 | +3 |
| **Renfort ou entrave** (bonus ou malus à une cible) | ±10 pendant 1 round | ±20 pendant 1 round | ±20 pendant tout le combat |
| **Utilitaire** (lumière, illusion, détection, ouvrir…) | Un petit effet | Un effet notable | Un effet spectaculaire |

- Une **attaque** se résout comme un tir : pas d'esquive, et le couvert compte (voir 7.3).
- Hors combat, « 1 round » vaut pour le **prochain jet** de la cible.
- L'**utilitaire** est raconté par le MJ : il ne blesse pas, ne soigne pas et ne donne aucun bonus chiffré. Sa puissance borne seulement ce que le MJ peut raconter.

### 10.4 Les degrés

| Degré | Effet |
|---|---|
| **Critique** | Effet maximum ; pour une attaque, l'armure ne compte qu'à moitié |
| **Réussite majeure** | Pour une attaque ou un soin, un dé de plus |
| **Réussite** | L'effet normal |
| **Réussite avec complication** (hors combat) | Le sort marche, avec un prix raconté par le MJ |
| **Échec** | Rien ne se passe, et la **moitié des PM** est perdue (arrondie au-dessus) |
| **Maladresse** | **Tous les PM** du sort sont perdus, et le sort se retourne contre son lanceur : il en subit l'effet en mineur s'il était nocif, 1d6 dégâts sinon |

### 10.5 Domaines, sorts appris et improvisations

Chaque univers a **de 3 à 6 domaines** de magie (Pyromancie, Guérison, Illusion…). Chaque domaine autorise certains effets seulement : la Guérison n'attaque pas.

| | Sorts appris | Improvisations |
|---|---|---|
| **Ce que c'est** | Les sorts maîtrisés, avec un nom | Les usages libres du domaine |
| **Par domaine** | 4 à 6 | 3 à 5 |
| **Puissance** | Mineur à Majeur | Modéré au plus |
| **Difficulté** | Celle de la puissance | **Un cran de plus** (Normale en Mineur, Difficile en Modéré) |
| **Propriété** | Une au plus (voir 10.6) | Jamais |

- À la création, le perso choisit **2 domaines** et connaît tous leurs sorts appris et leurs improvisations.
- **Hors de ses domaines, il ne peut rien lancer.**
- Le MJ ne lance que des sorts de ces listes : il ne peut ni en inventer un, ni en gonfler un.

Les domaines et les sorts de l'annexe C sont des exemples, pas une liste figée. Le générateur d'univers s'en sert comme modèles et les adapte à chaque univers. Plus tard, les sorts que le MJ accepte en cours de campagne pourront rejoindre la mémoire, dans un fichier `sorts.md`, comme les PNJ et les fils.

### 10.6 Les propriétés de sort

Un sort appris peut avoir **une propriété au plus**, pour **+1 PM**.

| Propriété | Effet |
|---|---|
| **Zone** | Le sort touche 2 cibles proches, avec un seul jet de Magie |
| **Persistant** | L'effet continue après le round où il est lancé (voir ci-dessous) |
| **Silencieux** | Le sort se lance sans un bruit ni un geste visible |

**Persistant** :

- Contre une **attaque** ou une **entrave**, la victime fait un jet de sauvegarde **au début de son tour** : **Constitution** contre une attaque (brûlure, nécrose…), **Volonté** contre une entrave (terreur, illusion…). Réussi, l'effet s'arrête. Raté, elle subit **1d3 dégâts** (attaque) ou **le malus encore un round** (entrave).
- L'effet dure **au plus 3 rounds**.
- Une **protection** ou un **renfort** persistant dure simplement un round de plus, sans jet.
- Un PNJ fait sa sauvegarde à **50**.

### 10.7 Le soin magique

- Le soin magique a les **mêmes limites que la Médecine** (voir 8.1) : **un soin magique réussi par patient et par demi-journée** (après un échec, un autre lanceur peut tenter), et pas de soin magique la nuit.
- Les deux limites sont **séparées et se cumulent** : dans la même demi-journée, un patient peut recevoir un jet de Médecine **et** un soin magique. Un mage guérisseur qui a aussi appris la Médecine est un vrai soigneur.

### 10.8 Récupérer ses PM, et à court de PM

- Les PM se récupèrent **comme les PV**, avec la même table des repos (voir 8.2).
- À court de PM, on peut **puiser dans sa vie** : **1 PV par PM manquant**.
- En **Horreur**, chaque sort coûte aussi **son coût en Santé mentale**.

### 10.9 Ce que la magie ne fait pas

Aucun sort, appris ou improvisé, ne peut :

- invoquer ou animer un allié (mort-vivant, élémentaire, familier qui se bat) ;
- téléporter ou faire voyager instantanément ;
- transformer ou métamorphoser quelqu'un ;
- contrôler un esprit, forcer quelqu'un à agir ou le charmer contre sa volonté ;
- ressusciter un mort ;
- tuer d'un coup ou désintégrer, sans passer par les dégâts ;
- lire les pensées ou prédire l'avenir ;
- créer de l'or, des objets ou des armes qui durent ;
- arrêter le temps ou revenir en arrière.

Le MJ refuse toute demande de ce genre, et le générateur n'en crée jamais (liste reprise dans `aria/prompts/magie_interdite.md`).

### 10.10 Les PNJ

Un PNJ lanceur de sorts a un **% de Magie** et des **PM** fixés à sa création, comme son % de combat (voir 7.8), et une liste de sorts tirée des domaines de l'univers.

---

## 11. Implants

Dans les univers qui en ont (le Cyberpunk d'abord ; la science-fiction ou le post-apo peuvent en avoir), un implant améliore le corps, et coûte un peu d'humanité. Inspiré de Cyberpunk RED et de Cyberpunk 2077 ; exemples en annexe E.

### 11.1 L'effet, une liste fermée

Comme un sort, un implant imite une mécanique que le moteur connaît déjà :

| Effet | Ce qu'il fait |
|---|---|
| **Arme** | Se joue comme une arme de l'armurerie, dans les bornes de 7.5 |
| **Armure** | Se joue comme une armure, dans les bornes de 7.5 |
| **Bonus de compétence** | +5 (gamme avancée) ou +10 (gamme militaire) à une compétence |
| **Utilitaire** | Un effet raconté (vision nocturne, radio interne…), sans bonus chiffré |
| **Esthétique** | Tatouages lumineux, cheveux de fibre optique… : rien d'autre que l'apparence |

Un implant **médical** remplace un membre perdu sans l'améliorer : ni option, ni bonus.

### 11.2 Les systèmes, les fondations et les options

- Le corps est découpé en **systèmes** (cortex frontal, système d'exploitation, système nerveux, visage et yeux, oreilles et gorge, peau, squelette, organes internes, bras, mains, jambes). Chacun a un nombre d'emplacements.
- Certains implants sont des **fondations** (bras cybernétique, yeux cybernétiques, suite cyberaudio, jambes cybernétiques, neuroport) : ils ouvrent des emplacements d'**options**. Pas de lames-mantis sans bras cybernétique, pas de viseur sans yeux cybernétiques.
- **Le système d'exploitation est unique** : un seul implant parmi le deck neural, le deck militaire, le Sandevistan et le Berserk.
- L'esthétique n'occupe pas d'emplacement.

### 11.3 Ce qui ne se cumule pas

- **Un seul bonus par compétence** : seul le meilleur compte (un viseur à +5 et des optiques à +10 donnent +10).
- **Une armure implantée et une armure portée ne se cumulent pas** : seule la meilleure protection compte.

### 11.4 Le prix : l'humanité

Un implant a une **gamme**, qui fixe sa puissance et son prix, et une **qualité** (usé, d'origine, personnalisé, unique, voir 7.5), qui dit son état et ses emplacements de modification. Chaque implant baisse la **Santé mentale maximum**, comme le Mythe en Horreur ; les armes et les armures ne coûtent jamais de Santé mentale.

| Implant | SM maximum perdue |
|---|---|
| Esthétique ou médical | 0 |
| Gamme standard (arme, armure ou utilitaire) | 2 |
| Gamme avancée (+5 à une compétence) | 4 |
| Gamme militaire (+10 à une compétence) | 6 |
| Implant usé (d'occasion, mal calibré) | 2 de plus |
| Chaque modification d'un implant | 1 de plus |

La perte est la même à la création et pour un implant posé en cours de jeu : elle est fixe, sans jet. À 0 de SM, c'est la folie (voir 9.4), qu'on appelle la **cyberpsychose** en Cyberpunk : le personnage devient un PNJ, sauf point de destin.

---

## 12. Véhicules

### 12.1 La fiche du véhicule

| Champ | Contenu |
|---|---|
| **Nom** | Le nom dans l'univers |
| **Type** | Terrestre, aérien, nautique ou spatial |
| **Vitesse** | Lente, moyenne, rapide ou très rapide |
| **Maniabilité** | −10, 0 ou +10 aux jets de Pilotage |
| **Structure** | Les « PV » du véhicule |
| **Blindage** | Sa protection : il réduit les dégâts, comme une armure |
| **Places** | Le conducteur compris |
| **Armes montées** | Sur ses points d'emport (voir 12.7) |
| **Propriétés** | Tout-terrain, amphibie, discret, cargo… |
| **Qualité** | Usé, d'origine, personnalisé ou unique, avec les mêmes emplacements de modification que les armes (voir 7.5) |

**Bornes**, vérifiées par le code avant les modifications :

| Gabarit | Exemples | Structure | Blindage |
|---|---|---|---|
| Léger | moto, scooter, jet-ski | 10 à 20 | 0 à 2 |
| Moyen | voiture, pick-up, hovercar | 20 à 40 | 2 à 4 |
| Lourd | camion, bus, blindé léger | 40 à 60 | 4 à 8 |
| Militaire | char, hélicoptère d'assaut | 60 à 100 | 8 à 12 |

Une **monture** (cheval, chameau, griffon…) suit la même fiche : un cheval est léger, rapide, avec une structure de 15, aucun blindage et une maniabilité de +10. Une monture se soigne au lieu de se réparer, et elle peut paniquer (voir 12.5).

### 12.2 Conduire

- Conduire normalement ne demande aucun jet, comme marcher.
- Un jet de **Pilotage** (Conduite, Équitation… selon l'univers) quand la conduite devient risquée : manœuvre dangereuse, terrain difficile, mauvais temps, vitesse excessive, véhicule inconnu. Le MJ fixe la difficulté dans la liste de 2.3, et la **maniabilité** s'ajoute.
- Une réussite avec complication, hors combat : on passe, avec un prix (une aile arrachée, un temps perdu, un témoin). Un échec : on n'y arrive pas, on perd du temps ou du terrain. Une maladresse : l'accident (voir 12.5).
- En combat, conduire compte comme un **déplacement** ; une manœuvre risquée (dérapage, se faufiler, sauter un obstacle) est une **action simple**, avec son jet. Les passagers, eux, agissent normalement.

### 12.3 Les poursuites

**La distance**, en crans. Une poursuite commence en général à « Proche ».

| Distance | Ce que ça veut dire |
|---|---|
| **Au contact** | Rattrapé : on peut aborder, éperonner, se battre |
| **Proche** | Dans les rétros, à portée de tir courte |
| **Loin** | On se voit encore, à portée de tir longue seulement |
| **Semé** | Perdu de vue : la poursuite est finie |

**Chaque round** :

1. Le moteur tire un **événement de la route** (1d10, dans la colonne de la zone, voir plus bas), et l'applique.
2. Puis un **jet opposé de Pilotage** entre le fuyard et le poursuivant. Chacun ajoute la maniabilité de son véhicule ; le plus rapide ajoute +10 par cran de vitesse d'écart. Le terrain donne une difficulté choisie par le MJ, la même pour les deux.

| Résultat du jet opposé | Effet |
|---|---|
| Réussite | Le gagnant gagne 1 cran (le fuyard vers « Semé », le poursuivant vers « Au contact ») |
| Réussite majeure ou critique | Le gagnant gagne 2 crans |
| Égalité | Rien ne bouge |
| Maladresse de l'un des deux | Accident (voir 12.5) |

- **Nitro** : +10 à un seul jet de la poursuite, une fois par scène.
- **Les passagers** peuvent tirer à chaque round (voir 12.4).
- **À pied**, mêmes règles, avec l'Athlétisme, sans vitesse ni maniabilité. Contre un véhicule, le coureur compte un cran sous « lente ».
- **Plusieurs poursuivants** : un jet opposé contre chacun, et chacun a sa distance.
- Le MJ peut décider qu'un poursuivant renonce (blessé, à court de carburant, d'autres priorités).

**Les événements de la route**

| Événement | Effet ce round |
|---|---|
| Voie dégagée | Rien de spécial |
| Ligne droite | Le bonus de vitesse est doublé |
| Circulation dense | Le bonus de vitesse est annulé, la maniabilité doublée |
| Obstacle soudain | Chacun fait un test de Pilotage normal avant le jet opposé |
| Virage serré, chaussée glissante | Chacun fait un test de Pilotage difficile avant le jet opposé |
| Terrain accidenté | Chacun fait un test de Pilotage difficile ; −20 en plus sans la propriété tout-terrain |
| Raccourci | Le fuyard peut le tenter (Pilotage difficile) : réussi, un cran de plus ; raté, un cran de moins |
| Barrage | Chacun fait un test de Pilotage difficile ; celui qui le rate est bloqué : il ne bouge pas ce round, et perd le jet opposé sans le lancer |
| Coup de chance | +10 au jet opposé pour celui qui est en train de perdre : le fuyard jusqu'à « Proche », le poursuivant à « Loin » |

Un test d'obstacle raté fait perdre un cran (le fuyard se rapproche, le poursuivant s'éloigne) ; une maladresse, c'est l'accident (voir 12.5).

**Les zones**, chacune avec ses événements (1d10) :

| Événement | Centre-ville | Banlieue | Bas-quartiers | Zone industrielle | Autoroute | Hors de la ville |
|---|---|---|---|---|---|---|
| Voie dégagée | 1 | 1-2 | 1 | 1 | 1-2 | 1 |
| Ligne droite | 2 | 3-4 | — | 2-3 | 3-6 | 2-4 |
| Circulation dense | 3-5 | 5 | 2 | 4 | 7 | — |
| Obstacle soudain | 6 | 6 | 3-4 | 5-6 | 8 | 8 |
| Virage serré | 7 | 7 | 5 | 7 | — | — |
| Terrain accidenté | — | — | — | — | — | 5-7 |
| Raccourci | 8 | 8 | 6-7 | 8 | — | 9 |
| Barrage | 9 | 9 | 8-9 | 9 | 9 | — |
| Coup de chance | 10 | 10 | 10 | 10 | 10 | 10 |

**Changer de zone**

- Un fuyard qui gagne avec une réussite majeure ou un critique peut, au lieu de son deuxième cran, entraîner la poursuite dans une zone voisine de son choix.
- Tous les 4 rounds, une poursuite qui dure passe d'elle-même dans une zone voisine, tirée au hasard par le moteur.

| Zone | Zones voisines |
|---|---|
| Centre-ville | Banlieue, Bas-quartiers, Autoroute |
| Banlieue | Centre-ville, Autoroute, Hors de la ville |
| Bas-quartiers | Centre-ville, Zone industrielle |
| Zone industrielle | Bas-quartiers, Autoroute |
| Autoroute | Centre-ville, Banlieue, Zone industrielle, Hors de la ville |
| Hors de la ville | Banlieue, Autoroute |

Les événements et les zones gardent leurs effets ; leur décor suit le genre. En Fantasy, par exemple : le cœur de la cité, les faubourgs, les bas-fonds, le port, la route royale, la campagne ; un marché bondé, une charrette renversée, un gué, une herse qui se baisse. Une monture peut aussi paniquer sur un obstacle (voir 12.5).

### 12.4 Le combat avec des véhicules

**Tirer depuis un véhicule en mouvement**

| Qui tire | Malus | Ce qu'il peut faire |
|---|---|---|
| Le conducteur | −20 | Une arme à une main seulement, et pas dans un round de manœuvre risquée |
| Un passager | −10 | N'importe quelle arme |
| Une arme montée | 0 | Tirée par un passager (ou par le conducteur avec un pilote automatique) : elle est stabilisée (voir 12.7) |

**La portée selon la distance de la poursuite**

| Distance | Armes qui portent |
|---|---|
| Au contact | Toutes, mêlée comprise |
| Proche | Portée courte et au-delà |
| Loin | Portée longue seulement |
| Semé | Aucune |

**Tirer sur un véhicule**

| Cible | Difficulté | Effet si on touche |
|---|---|---|
| La carrosserie | Normale | Les dégâts, moins le blindage, sont retirés à la structure |
| Un occupant | Couvert partiel (−20), lourd (−40) si le véhicule est blindé | Les dégâts touchent l'occupant, comme un tir normal |
| Les pneus, le moteur | Difficile | Pas de dégâts, mais −1 cran de vitesse (pas sur un véhicule blindé) |

Un véhicule est **blindé** à partir d'un blindage de 4, modifications comprises. Une réparation réussie rend aussi la vitesse perdue.

**Éperonner**, au contact seulement : un jet opposé, le Pilotage de l'attaquant contre le Pilotage de la cible, ou son Esquive si c'est un piéton.

| Gabarit de l'attaquant | Dégâts infligés |
|---|---|
| Léger | 1d6 |
| Moyen | 2d6 |
| Lourd | 3d6 |
| Militaire | 4d6 |

- +1d6 si le véhicule de l'attaquant est rapide ou très rapide.
- L'attaquant prend la moitié des dégâts sur sa propre structure.
- Contre un véhicule, les dégâts moins le blindage vont à la structure ; contre un piéton, à ses PV, moins son armure.
- Ces dégâts dépassent volontairement les bornes des armes (7.5) : se faire renverser par un camion fait plus mal qu'un coup de fusil.

### 12.5 Dégâts, accidents et réparation

**L'état du véhicule**

| Structure restante | État | Effet |
|---|---|---|
| Plus de la moitié | Intact | Aucun |
| La moitié ou moins | Endommagé | −1 cran de vitesse et −10 de maniabilité |
| 0 | Épave | Il ne roule plus ; les occupants doivent sortir, et seul un atelier peut le réparer |

**L'accident**, sur une maladresse au volant : les dégâts dépendent de la vitesse au moment du choc.

| Vitesse | Dégâts à chaque occupant | Dégâts à la structure |
|---|---|---|
| Lente | 1d4 | 1d6 |
| Moyenne | 1d6 | 2d6 |
| Rapide | 2d6 | 3d6 |
| Très rapide | 3d6 | 4d6 |

- L'armure protège les occupants, comme contre un coup.
- Sur un véhicule léger (moto, monture…), les occupants prennent 1d6 de plus : pas de carrosserie pour encaisser.
- En poursuite, l'accidenté a perdu : le fuyard est rattrapé, le poursuivant est semé.

**La réparation** : un jet de Mécanique (Bricolage, Forge… selon l'univers), hors combat, un par véhicule et par demi-journée. C'est la table de la Médecine (8.1), doublée : critique 4d6 de structure, réussite majeure 2d6, réussite 1d6, échec rien, maladresse −1d6. Dans un atelier, Facile ; en pleine rue, Normale ; une épave ne se répare qu'en atelier.

**Les montures** vivent :

- Leur structure, ce sont leurs PV : à 0, elles sont mourantes, comme un personnage.
- Elles se soignent avec la Survie (s'occuper des animaux), avec la table de la Médecine, et pas en atelier.
- Sur un obstacle, un barrage, un tir ou une explosion, le cavalier fait un test d'Équitation Normal (Facile avec le dressage de guerre). Raté, la monture panique pendant 1 round : le cavalier ne la contrôle plus, et il perd un cran s'il est en poursuite.

### 12.6 Personnaliser son véhicule

Deux couches, bien séparées : la mécanique, qui passe par les modifications, et l'esthétique, qui est libre.

**La qualité**, comme pour les armes (voir 7.5) :

| Qualité | Emplacements de modification | Exemple |
|---|---|---|
| Usé | 0, et un défaut | une épave qui tousse |
| D'origine | 1 | le modèle tel qu'il sort de l'usine |
| Personnalisé | 2 | une caisse retouchée par un pro |
| Unique | 3 | la légende du quartier |

**Le défaut d'un véhicule usé**, un seul au choix :

| Défaut | Effet |
|---|---|
| Moteur fatigué | un cran de vitesse en moins |
| Direction molle | −5 de maniabilité |
| Carrosserie rouillée | −5 de structure |
| Capricieux | sur une maladresse au jet de Pilotage, il cale au lieu de l'accident : pas de dégâts, mais il s'arrête (en poursuite, il a perdu) |

**Les modifications**, un seul effet chacune, une seule fois par véhicule ; la pose se fait hors combat, par un jet de l'artisanat de l'univers (Mécanique, Bricolage, Forge…), comme en 7.5 :

| Effet | Ce que ça donne | Plafond total |
|---|---|---|
| Moteur | +1 cran de vitesse | +1 cran |
| Châssis | +5 de maniabilité | +10 |
| Renfort | +5 de structure | +10 |
| Blindage | +1 de blindage | +2 |
| Propriété | une propriété en plus | une seule |
| Support d'arme | un point d'emport en plus | un seul |
| Nitro | +10 à un seul jet de Pilotage | une fois par scène |
| Utilitaire | un effet raconté, sans bonus | — |

**L'esthétique** ne prend aucun emplacement, ne demande aucun jet et ne donne aucun bonus. Mais le MJ en tient compte dans l'histoire : ce qui se voit, on le reconnaît, on le suit, on le retrouve.

| Élément | Ce que ça fait en jeu |
|---|---|
| Peinture, vinyles, logos | On reconnaît le véhicule |
| Néons, éclairage | Il se voit de loin la nuit, et ne peut pas être « discret » |
| Jantes, kit carrosserie | Du style |
| Échappement sport | On l'entend arriver, et il ne peut pas être « discret » |
| Peinture mate, vitres teintées | Plus difficile à repérer et à reconnaître |

Exemples de modifications en annexe F.

### 12.7 Armement, systèmes défensifs et drones

**Les points d'emport**, selon le gabarit :

| Gabarit | Points d'emport | Ce qu'on y monte |
|---|---|---|
| Léger | 0 | rien : le passager tire à la main |
| Moyen | 1 | une tourelle légère |
| Lourd | 2 | des tourelles légères ou lourdes |
| Militaire | 3 | tout, y compris les armes de zone |

Une **tourelle légère** porte une arme à distance ordinaire ; une **tourelle lourde**, une arme lourde montée ou une arme de zone (7.9).

**Les armes lourdes montées** : trop lourdes pour un homme, elles ont leurs propres bornes (jusqu'à 3d6) et ne se tirent que d'un véhicule ou d'un trépied. Exemples en annexe F.

**Les systèmes défensifs**, qui occupent un emplacement de modification :

| Système | Effet |
|---|---|
| Lance-fumigènes | Une fois par scène : un écran de fumée autour du véhicule, couvert lourd (−40) pendant 3 rounds |
| Leurres | Une fois par scène : une roquette ou un missile qui visait le véhicule rate d'office |
| Blindage IEM | Le véhicule résiste aux IEM (7.10) |
| Baie à drones | Le véhicule transporte et lance 2 drones |

**Les drones** sont des mini-véhicules, avec la même fiche, dans leur propre gabarit :

| Gabarit | Structure | Blindage | Vitesse |
|---|---|---|---|
| Drone | 5 à 10 | 0 à 1 | rapide ou très rapide |

- **Télépiloté** : l'opérateur dépense une action simple par round pour le faire agir, avec son Pilotage (ou son Piratage par un neuroport). Un opérateur pilote un seul drone à la fois.
- **Autonome** : le drone agit seul à son tour, avec un score fixe de 40.
- Sa structure fait ses PV, son blindage son armure ; à 0, c'est une épave, sans agonie.
- Un drone est électronique : une IEM le grille, sauf blindage IEM (7.10).

---

## 13. Économie et inventaire

Le code tient tous les comptes : le MJ ne manie jamais un nombre. Il dit ce qui se passe par un outil, et le moteur vérifie, débite, crédite ou refuse. Rien ne s'obtient sans outil : un objet n'existe que si le moteur l'a enregistré.

### 13.1 L'argent

- L'argent est **compté à l'unité** : un seul nombre sur la fiche, qui ne passe jamais sous zéro.
- **Une seule échelle pour tous les univers** : 1 unité vaut à peu près 1 euro d'aujourd'hui en pouvoir d'achat. Seul le nom de la monnaie change selon l'univers (crédits, couronnes, dollars…). Dans un univers de troc, l'unité reste la même et se paie en objets (cartouches, rations).
- Tous les prix sont pris dans une liste fermée, **les paliers** : 10 · 20 · 50 · 100 · 200 · 500 · 1 000 · 2 000 · 5 000 · 10 000, et ainsi de suite. Chaque palier vaut à peu près le double du précédent. Pour un service imprévu, le MJ choisit un palier.

### 13.2 Le niveau de vie

Le joueur choisit un niveau de vie, que le code débite **tous les 7 jours de jeu**. La première semaine est payée : la première échéance tombe au jour 8.

| Niveau de vie | Par semaine | Effet |
|---|---|---|
| **À la rue** | 0 | Pas d'endroit sûr : le repos long ne rend que ce que rend un repos moyen, et pas de jet de récupération de Santé mentale la nuit. Rien à laisser chez soi |
| **Modeste** | 350 | Aucun : les règles telles quelles |
| **Confortable** | 1 000 | +10 au jet de récupération de Santé mentale de la nuit |

- Si le personnage ne peut pas payer, il tombe « à la rue » jusqu'à ce qu'il repaie une semaine.
- Il change de niveau quand il veut ; le nouveau tarif vaut à l'échéance suivante.
- Chaque genre donne un visage aux trois niveaux : une capsule, un studio, un appartement en Cyberpunk ; une paillasse en salle commune, une chambre à l'auberge, une maison en Fantasy.

### 13.3 Les prix et la disponibilité

Le code calcule le prix d'un objet à partir de ce qu'il est, puis l'arrondit au palier le plus proche. La bibliothèque peut imposer un prix pour une exception.

- **Une arme** : ses dégâts, sa catégorie (une arme de mêlée vaut le quart d'une arme à feu, une arme lourde quatre fois plus) et ses propriétés (silencieuse, perforante, rafale).
- **Une armure** : sa protection, un peu moins chère si elle gêne beaucoup.
- **Un véhicule** : son gabarit, sa vitesse, son blindage et ses armes montées.
- **Un implant** : sa gamme. 2 000 en standard, 10 000 en avancée, 50 000 en militaire ; 500 pour l'esthétique et le médical.

La qualité et la marque (voir 7.5) se comptent en paliers :

| Objet | Prix |
|---|---|
| Usé | Un palier en dessous |
| D'origine | Le prix calculé |
| Personnalisé | Le prix, plus celui de chaque modification posée (de 200 à 2 000) |
| Unique | Deux paliers au-dessus ; jamais en boutique |
| De marque | Un palier au-dessus, modification d'usine comprise |

Trois niveaux de **disponibilité**, que le code déduit de l'objet :

| Niveau | Quoi | Comment l'obtenir |
|---|---|---|
| **Courant** | Armes de mêlée, armes de poing, fusils simples, armures de protection 1 et 2, implants standard, véhicules civils | En boutique, au prix |
| **Restreint** | Tir en rafale, silencieux, fusils de précision, grenades, armures de protection 3 et 4, implants avancés | Par un contact : un test de Réseau ou de Persuasion, un délai de 1 à 3 jours, un palier au-dessus |
| **Militaire** | Armes lourdes, explosifs, implants militaires, véhicules armés | Jamais en vente : butin, ou récompense de mission |

Le lieu règle la difficulté du test : normale dans une grande ville, difficile dans une petite, impossible dans un village ou en pleine nature.

### 13.4 L'argent de départ

Chaque métier a un **rang de revenu**. Il fixe l'argent de départ, et ce que rapporte une semaine de travail (voir 13.6).

| Rang | Argent de départ | Niveau de vie au départ | Revenu d'une semaine de travail |
|---|---|---|---|
| **Précaire** | 500 | Modeste | 350 |
| **Établi** | 2 000 | Modeste | 700 |
| **Aisé** | 5 000 | Confortable | 2 000 |

L'équipement de départ reste celui des listes du métier (voir 5) : l'argent vient en plus. Une arme à feu de départ vient avec deux chargeurs garnis (ou deux chargeurs rapides pour un revolver) et une boîte de 20 cartouches ; une arme sans chargeur, chargée, avec sa boîte.

### 13.5 Les munitions

Les munitions sont comptées à l'unité, dans deux réserves :

- **les cartouches en vrac**, par calibre : deux armes du même calibre se les partagent ;
- **les chargeurs**, comptés un par un, chacun avec son contenu. Un chargeur entamé reste entamé. Un chargeur va avec une arme précise, pas seulement avec un calibre.

En combat :

- **Changer de chargeur** : l'action de rechargement de l'arme (voir 7.2), avec un chargeur garni sous la main. Le chargeur retiré est gardé.
- **Garnir à la main**, un chargeur ou une arme sans chargeur : une action simple, pour un nombre de cartouches qui dépend de la compétence Armes à distance. L'action mineure du même round, si elle y est consacrée, ajoute 2 cartouches.

| Armes à distance | À la main | Avec un garnisseur | Avec une lame-chargeur |
|---|---|---|---|
| Moins de 50 | 3 | 6 | 10 |
| De 50 à 74 | 5 | 10 | 10 |
| 75 et plus | 7 | 14 | 15 |

- Le **garnisseur** sert aux pistolets et aux fusils, et se réutilise. La **lame-chargeur** ne sert qu'aux fusils et se consomme. Le **chargeur rapide** d'un revolver, garni à l'avance, recharge le barillet entier en une action mineure.
- Hors combat, regarnir ses chargeurs ne demande aucun jet, tant qu'il reste du vrac.
- La règle vaut pour les PNJ.

Les cartouches se vendent par boîte de 20 : 20 pour une arme de poing, 50 pour un fusil, 100 pour un fusil de précision, 200 pour une arme lourde ; les flèches et les carreaux, 20 les 20. Un chargeur vide coûte 50 ; une arme est vendue avec un chargeur. Les grenades et les explosifs s'achètent à l'unité.

### 13.6 Gagner de l'argent

**Les missions.** Le MJ choisit la récompense dans une liste fermée. Elle est fixée à l'ouverture de la mission, enregistrée avec son fil (voir la mémoire de campagne), et versée par le code quand le fil est clos sur une réussite.

| Mission | Récompense |
|---|---|
| Un service | 200 |
| Simple | 500 |
| Risquée | 2 000 |
| Dangereuse | 5 000 |
| Très dangereuse | 10 000 |
| Exceptionnelle | 20 000 et plus |

Une récompense peut aussi être un objet, une faveur ou un contact : c'est la seule porte d'entrée du matériel militaire, avec le butin.

**Exercer son métier.** Une semaine entière sans aventure : un test de la compétence principale du métier. Maladresse : rien, et un ennui que le MJ raconte. Échec : rien. Réussite : le revenu du rang (voir 13.4). Réussite majeure : une fois et demie. Critique : le double. La semaine passe pour de bon : le coût de la vie est débité, le personnage se repose.

**La revente.** Le butin se vend chez un receleur, à **deux paliers sous sa valeur**. Le matériel militaire, ou marqué par une police ou une corporation, ne se vend que par un contact.

### 13.7 Dépenser

**Les boutiques.** Dans une grande ville, le matériel courant se trouve toujours, au prix. Chaque boutique a en plus 3 occasions tirées par le code (usées ou de marque), et chaque contact du marché noir 4 objets restreints tirés. Les stocks se renouvellent tous les 7 jours.

**Les services.**

| Service | Prix |
|---|---|
| Un trajet en taxi, un repas correct | 20 |
| Une consultation, un soin par un médecin | 100 |
| Une séance de thérapie | 200 |
| Soigner une blessure grave | 500 |
| Faire poser une modification | 100, en plus de son prix |
| Réparer un objet ou un véhicule | Deux paliers sous sa valeur |
| Une information, un pot-de-vin | Un palier choisi par le MJ, de 50 à 2 000 |

Le soigneur payé fait son jet comme n'importe quel soigneur : on paie l'acte, pas le résultat.

**La pose d'un implant** coûte 500 en standard, 2 000 en avancée, 5 000 en militaire, en plus de l'implant. Le charcudoc fait un jet de Médecine : sur un échec, l'implant est mal calibré et coûte 2 points de Santé mentale maximum en plus (voir 11.4) ; sur une maladresse, s'y ajoute une blessure grave. Une clinique clandestine coûte un palier de moins, avec un charcudoc moins bon.

**Se détendre.** Une soirée, un plaisir, une offrande : 200, pour 1d6 de Santé mentale, une fois par semaine, en plus des récupérations de 9.5.

**Les personnes à charge.** Si le lien du personnage dépend de lui, il coûte 200 par semaine, débités avec le coût de la vie. Le temps passé avec lui rend alors 1d6 au lieu de 1d3. Une semaine impayée : cette récupération est perdue jusqu'au prochain paiement, et le MJ ouvre un fil.

**Les dettes.** Une dette a un créancier, un montant et une échéance par semaine. On emprunte jusqu'à 5 000, remboursés par dixièmes pendant 12 semaines. Le code débite l'échéance avant le loyer. Une échéance manquée : le MJ fait monter la menace d'un cran.

### 13.8 Le butin

On trouve ce que l'adversaire avait vraiment. Le code déduit la **menace** d'un PNJ de son pourcentage de combat.

| Menace | Combat | Argent | Chance d'un objet en plus |
|---|---|---|---|
| Faible | 40 ou moins | 10 à 60 | 1 sur 6 |
| Moyenne | 41 à 60 | 20 à 120 | 2 sur 6 |
| Forte | 61 à 75 | 50 à 300 | 3 sur 6 |
| Élite | 76 et plus | 100 à 600 | 4 sur 6 |

- **Son arme** : usée 6 fois sur 10, d'origine sinon, avec le chargeur engagé au nombre de cartouches qu'il lui restait, et de 0 à 2 chargeurs de rechange.
- **Son armure** : toujours usée s'il a été abattu.
- **L'objet en plus** est tiré dans une table du genre.
- **Un implant** se récupère sur un mort par un charcudoc (test de Médecine) : il est usé, et coûte 2 points de Santé mentale maximum de plus à la pose.
- Fouiller un corps prend quelques minutes, hors combat. En combat, ramasser une arme au sol coûte une action mineure.

**Les caches.** Le MJ choisit la taille ; le code tire la valeur dans la fourchette, deux fois, et garde le plus petit résultat. Le contenu est à peu près pour moitié de l'argent, pour moitié des objets.

| Cache | Minimum | Maximum |
|---|---|---|
| Petite (un tiroir, un sac) | 50 | 500 |
| Moyenne (une planque, un coffre) | 500 | 2 000 |
| Grosse (une réserve de gang) | 2 000 | 10 000 |
| Un trésor (le coffre d'une corporation) | 10 000 | 50 000 |

Une cache n'est jamais vide par hasard : elle ne l'est que si un événement précis a touché le lieu (une attaque, un pillage récent).

### 13.9 L'inventaire

- **Ce que le corps supporte** : 4 + Force ÷ 10 emplacements.
- **Ce qu'on a sous la main** : les emplacements **prêts**, 3 sans équipement. On y prend un objet en une action mineure. Le reste est **rangé** : en sortir un objet coûte une action simple en combat.

| Objet | Emplacements |
|---|---|
| Arme à une main | 1 |
| Arme à deux mains | 2 |
| Arme encombrante | 3 |
| Petits objets : chargeurs, boîtes de cartouches, grenades, garnisseur | 1 pour deux |
| Un objet courant : deck, trousse de soins, outils | 1 |
| Une armure transportée, pas portée | 2 |
| L'armure portée, les implants, l'argent | 0 |

Au-delà de ses emplacements, le personnage est **surchargé** : −20 en Athlétisme, en Esquive et en Discrétion. Il ne porte jamais plus du double. Chez soi, la place n'est pas comptée, à partir du niveau de vie modeste. Un véhicule emporte 4 emplacements (léger), 20 (moyen) ou 60 (lourd).

**L'équipement de portage** ajoute des emplacements prêts : il met des objets sous la main, sans rien ajouter à ce que le corps supporte. On en porte un seul de chaque sorte, et il se voit, sauf mention contraire.

| Portage | Prêts en plus | Remarque | Prix |
|---|---|---|---|
| Holster | +1, une arme à une main | | 50 |
| Holster dissimulé | +1, une arme dissimulable | L'arme reste cachée | 100 |
| Sangle d'arme | +1, une arme à deux mains | | 50 |
| Sangles de cuisse | +2, petits objets | | 100 |
| Ceinture renforcée | +1 | Passe pour une ceinture ordinaire | 50 |
| Ceinture tactique | +2 | | 100 |
| Ceinture de combat | +3 | | 200 |
| Gilet tactique léger | +2, petits objets | Se cache sous une veste | 100 |
| Gilet tactique moyen | +4, petits objets | | 200 |
| Gilet tactique lourd | +6, petits objets | −10 en Discrétion | 500 |

**Les sacs**, eux, ajoutent des emplacements à ce que le corps supporte. On porte un seul sac à dos, plus une sacoche. Poser son sac coûte une action mineure.

| Sac | Rangés en plus | Poches latérales (prêts) | Remarque | Prix |
|---|---|---|---|---|
| Sacoche | +2 | 0 | Passe partout | 50 |
| Sac à dos de ville | +4 | 0 | Passe partout | 100 |
| Sac à dos tactique | +6 | 2 | | 200 |
| Sac de sport | +8 | 0 | Occupe une main | 100 |
| Sac de randonnée | +10 | 2 | −10 en Athlétisme et en Esquive tant qu'il est sur le dos | 200 |

### 13.10 Le marchandage

Un test de Persuasion, une seule fois par transaction ; le personnage peut toujours payer sans marchander. La difficulté vient de l'attitude du PNJ : facile s'il est amical, normale s'il est neutre, difficile s'il est hostile.

| Résultat | À l'achat | À la revente | Pour une mission |
|---|---|---|---|
| Critique | Un palier en dessous | Un palier sous la valeur, plus un geste | Un palier au-dessus |
| Réussite | Un geste du vendeur | Un palier sous la valeur au lieu de deux | Une avance |
| Échec | Le prix affiché | Le prix du receleur | La récompense prévue |
| Maladresse | Il refuse de vendre aujourd'hui | Il refuse d'acheter aujourd'hui | Un palier de moins, ou l'offre retirée |

- **Un geste du vendeur** : un chargeur ou une boîte de cartouches en plus, une pose offerte, ou un jour de délai en moins.
- **Une avance** : deux paliers sous la récompense, versée tout de suite et déduite à la fin.
- Par l'**Intimidation**, les effets sont les mêmes, mais l'attitude du PNJ baisse d'un cran, réussite ou non.

---

## 14. Le monde et la trame

Le monde vit sans attendre le joueur, et la trame n'avance que quand il s'en occupe. Comme pour l'argent, le code tire et tient les comptes : le MJ raconte ce que le moteur lui donne, il ne décide ni d'un événement, ni d'une mêlée, ni d'une révélation.

### 14.1 Les types de campagne

Le joueur choisit le type avant l'amorce.

| Type | Actes | Missions principales par acte | XP par mission principale | Départ conseillé | Ouverture |
|---|---|---|---|---|---|
| Contrat | 1 | 1 | 0 | aguerri ou vétéran | au cœur du problème |
| Courte | 3 | 1 / 2 / 1 | 3 | aguerri | au cœur du problème |
| Standard | 3 | 2 / 4 / 2 | 2 | débutant | la situation lance le plan |
| Longue | 5 | 2 / 3 / 4 / 3 / 2 | 1 | débutant | le quotidien du personnage |
| Sans fin | 3 par arc | 2 / 4 / 2, puis un nouvel arc | 1 | débutant | le quotidien du personnage |

- Le départ conseillé n'est pas imposé (voir 5, « L'expérience de départ »).
- Les montants d'XP seront revus avec la progression (voir 16) ; le principe est fixé : la vitesse dépend du type.
- **Au cœur du problème** : le commanditaire ou la menace est déjà dans la première scène. **Le quotidien** : la campagne s'ouvre sur la vie ordinaire du personnage, et le problème n'arrive qu'à la fin du premier acte.

### 14.2 Le temps du monde

- **Tous les 7 jours** : les dépenses du joueur seulement (loyer, dettes, lien à charge, voir 13).
- **Tout le reste est aléatoire.** Après chaque événement, le code tire la date du suivant et la garde cachée, avec le moment de la journée.
- **La trame n'a pas d'horloge** : rien ne se dégrade pendant qu'une mission principale attend, et le MJ ne relance jamais la trame de lui-même.

### 14.3 La carte

| Cadre | Districts | Quartiers | Factions |
|---|---|---|---|
| Bourg, station, colonie | 1 | 3 à 4 | 3 |
| Ville | 3 | 8 à 10 | 5 |
| Mégapole | 6 | 18 à 20 | 8 |

- Le **district** est une grande zone avec son ambiance ; le **quartier** est ce qu'on contrôle et ce qu'on attaque.
- Chaque quartier a des **voisins**, et la carte tient d'un seul bloc.
- Chaque **faction** a un type (gang, corporation, autorités, syndicat ou guilde, milice ou culte, selon le genre), un chef, une rivale désignée et les quartiers qu'elle tient. Les autorités sont une faction comme les autres.

### 14.4 Le contrôle d'un quartier et les mêlées

- Le contrôle va de **0 à 10**. Au début de la campagne, chaque quartier a **3 + 1d5** ; un quartier qui vient d'être pris a **5**.
- Un quartier est **disputé** s'il touche un quartier tenu par une faction hostile à son maître. Seuls les quartiers disputés sont attaqués.
- Un quartier disputé est attaqué tous les **1d3 jours**, par une faction hostile voisine tirée au hasard.
- **La mêlée** : 1d10 pour l'attaquant, 1d10 pour le défenseur, chacun avec ses bonus, plafonnés à **+3 par camp**. Le plus haut gagne ; à égalité, rien ne bouge.

| Bonus | Valeur |
|---|---|
| Le camp domine le district | +1 |
| Un clan s'est préparé, sans le joueur | 1d6 : sur 5, +1 ; sur 6, +2 |
| Le joueur a préparé le terrain (un seul préparatif par mêlée) | réussite +1, réussite majeure +2, critique +3 |
| Le joueur s'est battu et a gagné | +2 |
| Le joueur s'est battu et a perdu ou fui | −2 |

- L'attaquant gagne : le quartier perd **1 point**, **2** si l'écart des dés est de 5 ou plus. Le défenseur gagne : il en reprend autant, jusqu'à 10.
- **À 0**, le quartier passe à l'attaquant et repart à 5.
- Le joueur est prévenu **la veille** s'il est membre d'un des deux camps, **le jour même** s'il y est ami ; sinon il l'apprend sur place ou par les nouvelles.
- Préparer se fait des deux côtés : en défense (barricades, guetteurs, piège, brouillage), en attaque (repérage, complice, sabotage, armes fournies). Se battre est une vraie scène de combat.
- Une **mission** du joueur pour ou contre le maître d'un quartier déplace **2 points** tout de suite.

### 14.5 Tenir un quartier, dominer un district

Qui tient un quartier en change la vie, selon le type de la faction :

| Type | Commerce | Sécurité |
|---|---|---|
| Gang | marché noir ouvert | pas de police ; racket et bagarres |
| Corporation | le matériel courant un palier plus cher | contrôles d'identité, armes visibles interdites |
| Autorités | pas de marché noir ni de receleur | patrouilles ; une arme sortie attire la police |
| Syndicat ou guilde | réparations et services un palier moins cher | calme tant qu'on paie sa part |
| Milice ou culte | peu de boutiques, troc | étrangers surveillés, couvre-feu |

Une faction **domine un district** quand elle tient plus de la moitié de ses quartiers :

- **+1** à son dé dans toutes les mêlées du district ;
- une **place forte**, lieu unique selon son type (clinique, armurerie, atelier, tripot, tribunal) ;
- des **barrages** aux entrées et aux sorties ;
- les missions les plus nombreuses et les mieux payées du district.

**Sans majorité, le district est en guerre ouverte** : ni place forte ni barrages, et les événements de quartier y tombent deux fois plus souvent.

### 14.6 La réputation

Un cran par faction :

| Cran | Dans les districts que la faction domine |
|---|---|
| Membre | logé sans payer (niveau de vie modeste), place forte ouverte, prévenu des attaques la veille |
| Ami | place forte ouverte, ses vendeurs valent un contact, marchandage en « amical » |
| Neutre | rien de particulier |
| Hostile | un test ou un pot-de-vin aux barrages, vendeurs fermés, impossible d'y habiter |
| Recherché | en plus, l'événement « ils te cherchent » peut tomber, joué en embuscade |

- Elle **monte d'un cran** : une mission réussie pour la faction, une mêlée gagnée dans son camp.
- Elle **baisse d'un cran** : une mission ratée pour elle, une mission réussie contre elle, une mêlée dans le camp d'en face, un de ses hommes tué devant témoin.
- **Aider une faction baisse d'un cran sa rivale désignée.**
- Au départ, tout le monde est **neutre**, sauf ce que le métier ou l'amorce impose.
- **Devenir membre se demande** : il faut être ami, puis réussir une mission d'entrée.
- Pas de rente : la récompense est le logement et la place forte.

### 14.7 Les événements

| Échelle | Prochain dans | Table par genre |
|---|---|---|
| Quartier (celui où se trouve le joueur) | 1d5 jours | 50 au moins |
| Ville (à l'échelle d'un district) | 1d20 jours | 25 |
| Mégapole ou monde | 2d20 jours | 15 |

- Chaque événement porte **un effet que le moteur applique** (un palier de prix en plus ou en moins sur une catégorie, un vendeur fermé, des soins plus chers, un barrage, un bonus à une mêlée, une cache vidée) et **dure de 1 à 7 jours**.
- **Une cache n'est vide que si un événement a touché son lieu** (voir 13.8).
- Le MJ reçoit **les 3 nouvelles les plus importantes** depuis la dernière fois : la plus grande échelle d'abord, puis ce qui touche le joueur, son quartier ou ses contacts. Le reste va dans le **journal du monde**.
- Le joueur lit le journal avec `monde`, et la carte (qui tient quoi, sa réputation) avec `carte`.

### 14.8 Les missions

Une mission vient d'une faction (selon la réputation), d'un contact, d'un événement, d'une mêlée ou de la trame. Le code en tire l'ossature, le MJ l'habille :

- **le commanditaire** : une faction de la carte ;
- **l'objectif**, parmi 12 : voler, livrer, protéger, escorter, éliminer, retrouver quelqu'un, extraire quelqu'un, saboter, infiltrer, enquêter, négocier, défendre un lieu ;
- **le lieu** : un quartier de la carte ;
- **la cible** : une faction adverse ;
- **le danger**, sur le barème de 13.6, qui fixe la récompense : le plus souvent celui de l'expérience de départ, parfois un cran en dessous, rarement un cran au-dessus ;
- **un retournement**, 1 fois sur 3, tiré dans une table d'une trentaine. Le MJ le connaît, jamais le joueur.

**Les offres** : 1d3 offres ouvertes dans le district où se trouve le joueur, renouvelées tous les 1d5 jours. Une offre non prise disparaît. Le MJ peut toujours ouvrir une mission de lui-même.

| À la fin | Réussie | Ratée |
|---|---|---|
| Argent | la récompense | rien ; l'avance reste acquise |
| Réputation chez le commanditaire | +1 cran | −1 cran |
| Réputation chez la cible | −1 cran | rien |
| Contrôle du quartier, si la mission le vise | 2 points pour le commanditaire | rien |
| XP, pour une mission principale | selon le type de campagne | la moitié |

### 14.9 La trame

À l'amorce, le code tire **l'antagoniste** (son type, ce qu'il veut) : c'est une faction de la carte, ou quelqu'un derrière elle. Le MJ l'habille et le relie au secret. Chaque acte a un enjeu et un tournant.

- **Une mission principale** sort du générateur de 14.8 : sa cible est l'antagoniste ou ses alliés. Une seule à la fois, visible comme une piste dans les fils ; elle ne disparaît jamais.
- **Le danger monte d'un cran par acte** : risquée, dangereuse, très dangereuse pour une campagne courte ou standard ; de simple à exceptionnelle pour une longue. Un cran de plus pour un personnage aguerri, deux pour un vétéran, sans dépasser « exceptionnelle ».
- **Ratée**, elle ne bloque rien : la trame avance, et le code tire **une cicatrice** (un contact perdu, un quartier qui bascule, une dette, une blessure pour le lien). Elle compte pour la fin.
- **Les missions secondaires** sont libres et sans limite. Une sur quatre **touche la trame** : elle croise un homme de l'antagoniste ou laisse un indice.
- Après un tournant d'acte, la mission principale suivante arrive **1d5 jours** plus tard.

### 14.10 Les révélations

Le secret de l'amorce s'écrit en **trois couches** : quelque chose cloche ; qui ; pourquoi (la vérité entière). Le code ne donne au MJ que les couches ouvertes et la suivante.

- Une couche s'ouvre avec **2 indices** (campagne courte), **3** (standard) ou **4** (longue).
- **Un indice** : une mission principale réussie ; une mission secondaire qui touche la trame, réussie ; ou un test d'enquête réussi dans une scène liée à l'antagoniste, une fois par scène. Le code l'accorde, le MJ le décrit.
- Quand une couche s'ouvre, le MJ joue **une scène de révélation**.
- **La troisième couche ne s'ouvre qu'au dernier acte.** Les indices en trop servent dans la mission finale.
- **Deviner n'est pas prouver** : tant que la couche n'est pas ouverte, les PNJ nient, et une accusation sans preuve se joue comme un bluff.
- Le joueur relit ses indices avec `pistes`, sans le nombre de ceux qui manquent.

### 14.11 La fin

La mission finale est la dernière mission principale du dernier acte. Le code accorde **3 atouts au plus** :

| D'où il vient | Ce qu'il donne |
|---|---|
| Un indice en trop | le bras armé de l'antagoniste perd un cran de menace |
| Une faction dont le joueur est ami ou membre | un allié se bat à ses côtés |
| Le quartier de la finale tenu par une faction amie | une entrée sûre, et le premier round au joueur |

| Fin | Finale | Missions principales réussies |
|---|---|---|
| Triomphe | réussie | les trois quarts ou plus |
| Victoire amère | réussie | moins des trois quarts |
| Défaite honorable | ratée | la moitié ou plus |
| Chute | ratée | moins de la moitié |

- **La mort** du personnage, une fois les points de destin joués (7.7), est une cinquième fin.
- Victoire : la faction de l'antagoniste perd **3 points** dans tous ses quartiers. Défaite : elle en gagne **2**, et le joueur y devient recherché.
- **L'épilogue** : le MJ écrit, d'après les faits que le code lui donne, ce que deviennent le lien, les contacts, le quartier, la carte, et le secret entier.
- Ensuite, le joueur **arrête** (la campagne est archivée ; le personnage est gardé parmi les personnages prêts et peut repartir aguerri ou vétéran) ou **continue** : même monde, un nouvel antagoniste parmi les factions encore debout, une nouvelle trame 1d20 + 10 jours plus tard.
- Un **contrat** n'a ni atouts ni quatre fins : réussi ou raté, et un épilogue court.

---

## 15. L'aléatoire du monde

Le MJ raconte, le code tire. Les noms, les PNJ, le temps qu'il fait, les lieux et les rencontres ne s'inventent plus au fil de l'eau : le MJ choisit dans des listes fermées, et le moteur tire le reste. Ces règles valent pour les campagnes créées avec elles ; une campagne plus ancienne garde l'ancien fonctionnement.

### 15.1 Les noms

- **Des tables par origine.** Chaque origine a 20 prénoms d'homme, 20 prénoms de femme et 20 noms de famille, soit 800 noms possibles.
- **Des origines par genre** : six en Cyberpunk (japonaise, coréenne, chinoise, européenne, arabe, latine), trois ou quatre ailleurs. Un genre sans table prend celles du jeu générique.
- **Le cadre pèse.** Le code tire l'origine sur 1d10 : l'origine du cadre prend 5 faces (Osaka : japonaise), les autres se partagent le reste. Le MJ peut imposer une origine quand l'histoire le demande.
- **Les surnoms** : 40 par genre. Un membre de gang en porte un 1 fois sur 3 ; les autres PNJ, jamais.
- **Jamais deux fois le même.** Un nom tiré ne ressort plus de la campagne.
- **Le MJ ne nomme plus.** Pour un nouveau PNJ, il donne le sexe, et le code rend le nom. Un PNJ déjà nommé, par l'amorce, par la carte ou par une scène d'avant, garde le sien.

### 15.2 Les PNJ

Le MJ ne fixe plus les chiffres d'un PNJ. Il choisit un **rôle** et une **menace** dans des listes fermées ; le code tire le reste.

| Menace | Combat | Points de vie | Compétences du rôle |
|---|---|---|---|
| Faible | 20 + 2d10 | 6 + 1d6 | 40 |
| Moyenne | 40 + 2d10 | 10 + 1d6 | 55 |
| Forte | 55 + 2d10 | 14 + 1d8 | 70 |
| Élite | 75 + 1d10 | 20 + 1d10 | 80 |

- La **Dextérité** se tire pour tous sur 40 + 2d10. Les seuils de menace sont ceux du butin (13.8).
- **Douze rôles par genre.** En Cyberpunk : passant, commerçant, voyou, garde, policier, soldat de corpo, tueur, technicien, médecin de rue, fixer, cadre, chef. Un genre sans table prend les rôles du jeu générique.
- **Un rôle donne** trois compétences, au niveau de la menace, et un équipement tiré dans l'armurerie de l'univers : rien pour un passant, une arme de mêlée ou de poing pour un voyou, une arme longue et une armure lourde pour un soldat. Une armure légère protège de 1 ou 2, une lourde de 2 à 4, selon la menace.
- **Un rôle borne la menace** : un passant ou un commerçant reste faible, un chef est au moins fort.
- **Deux traits** : un caractère et un signe physique, tirés chacun dans une table de 40. Le MJ joue le PNJ avec.
- **Le plafond.** En mission, le danger borne la menace : un service ou une mission simple, moyenne au plus ; risquée, forte ; dangereuse et au-delà, élite. Hors mission, forte au plus. **Un seul PNJ d'élite par scène.**
- Les hommes d'une faction dans une mêlée (14.4) et le bras armé de la finale (14.11) gardent les chiffres que le moteur leur donne.
- **Un lanceur de sorts** a sa Magie au niveau des compétences de sa menace, et la moitié en points de magie. Ses sorts restent choisis par le MJ dans les domaines de l'univers.

---

## 16. À définir

- Les montants de gain d'XP par jalon.
- Les armureries de chaque univers (avec le générateur d'univers).
- L'effet chiffré de la propriété **rafale**.
- L'apprentissage de nouveaux sorts avec l'XP, et le fichier `sorts.md`.
- Les effets de magie hors V1 : invocation, transformation, téléportation… (voir 10.9).
- Les tables de crises passagères et de troubles durables.
- Les règles de pouvoirs pour le genre Super-héros (hors V1).
- Les vaisseaux spatiaux, pour la science-fiction : à voir avec ce genre (gabarits spatiaux, zones spatiales, postes d'équipage). En Cyberpunk, l'espace reste raconté.

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
| **Post-apo** | Corps à corps → Bagarre · Perception → Vigilance · Perspicacité → Flair · Investigation → Enquête · Persuasion → Marchandage · Tromperie → Embrouille · Escamotage → Chapardage · Arts → Conteur · Commandement → Meneur · Érudition → Savoir d'avant · Occultisme → Superstitions · Artisanat → Bricolage · Technologie → Tech d'avant · Sécurité → Pièges · Pilotage → Conduite | Désactivée (activable : Psi, le don des mutants) |

## Annexe B — Compétences thématiques par genre

| Genre | Compétences thématiques |
|---|---|
| Fantasy | Alchimie (potions, poisons, élixirs), Foi (prières et miracles) |
| Dark fantasy | Démonologie (nommer, reconnaître, repousser par les rites ; jamais invoquer d'allié), Foi (prières, exorcismes, inquisition) |
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

## Annexe C — Exemples de domaines de magie (Fantasy)

Des exemples, pas une liste figée (voir 10.5). Coût : Mineur 1 PM, Modéré 3 PM, Majeur 6 PM, +1 PM pour une propriété. Improvisations : Normale en Mineur, Difficile en Modéré.

### Pyromancie

| Sort | Effet | Puissance | Propriété | Coût | Ce qu'il fait |
|---|---|---|---|---|---|
| Étincelle | Attaque | Mineur | | 1 | 1d6 |
| Trait de feu | Attaque | Modéré | | 3 | 2d6 |
| Gerbe de flammes | Attaque | Modéré | Zone | 4 | 2d6 sur 2 cibles proches |
| Peau de braise | Protection | Modéré | | 3 | Armure +2 jusqu'à la fin du combat |
| Brasier | Attaque | Majeur | Persistant | 7 | 3d6, puis 1d3 par sauvegarde ratée |

Improvisations : allumer ou souffler une flamme (utilitaire, mineur) · réchauffer un allié transi (renfort +10, mineur) · chauffer ou faire fondre (utilitaire, modéré) · écran de fumée (entrave −20, modéré).

### Givre

| Sort | Effet | Puissance | Propriété | Coût | Ce qu'il fait |
|---|---|---|---|---|---|
| Morsure du froid | Entrave | Mineur | | 1 | −10 à la cible pendant 1 round |
| Armure de givre | Protection | Mineur | | 1 | Armure +1 |
| Lance de glace | Attaque | Modéré | | 3 | 2d6 |
| Sol verglacé | Entrave | Modéré | Zone | 4 | −20 à 2 cibles pendant 1 round |
| Tempête de grêle | Attaque | Majeur | Zone | 7 | 3d6 sur 2 cibles proches |

Improvisations : conserver des vivres (utilitaire, mineur) · givrer une lame (renfort +10, mineur) · geler l'eau, pour un pont de glace ou une serrure bloquée (utilitaire, modéré) · brume givrante (entrave −20, modéré).

### Guérison (aucune attaque)

| Sort | Effet | Puissance | Propriété | Coût | Ce qu'il fait |
|---|---|---|---|---|---|
| Apaiser | Soin | Mineur | | 1 | 1d3 PV |
| Refermer les plaies | Soin | Modéré | | 3 | 1d6 PV |
| Bénédiction | Renfort | Modéré | | 3 | +20 à un allié pendant 1 round |
| Égide | Protection | Modéré | Zone | 4 | Armure +2 à 2 alliés |
| Grâce de vie | Soin | Majeur | | 6 | 2d6 PV |

Improvisations : purifier l'eau ou la nourriture (utilitaire, mineur) · diagnostiquer un mal (utilitaire, mineur) · calmer la douleur (renfort +10, mineur) · ranimer un mourant (soin 1d3, mineur).

### Illusion

| Sort | Effet | Puissance | Propriété | Coût | Ce qu'il fait |
|---|---|---|---|---|---|
| Leurre | Utilitaire | Mineur | Silencieux | 2 | Un son ou une image fugace |
| Image miroir | Protection | Modéré | | 3 | Armure +2 : les coups frappent des reflets |
| Terreur fantasmatique | Entrave | Modéré | | 3 | −20 à la cible pendant 1 round |
| Voile d'ombre | Renfort | Modéré | Silencieux | 4 | +20 au prochain jet de Discrétion |
| Mirage | Utilitaire | Majeur | | 6 | Une illusion spectaculaire : un mur, une armée… |

Improvisations : ventriloquie (utilitaire, mineur) · effacer ses traces (utilitaire, mineur) · éblouir (entrave −10, mineur) · changer d'apparence (utilitaire, modéré).

### Nécromancie

| Sort | Effet | Puissance | Propriété | Coût | Ce qu'il fait |
|---|---|---|---|---|---|
| Toucher glacial | Attaque | Mineur | | 1 | 1d6 |
| Carapace d'os | Protection | Mineur | | 1 | Armure +1 |
| Parler aux morts | Utilitaire | Modéré | | 3 | Trois questions à un cadavre |
| Malédiction lente | Attaque | Modéré | Persistant | 4 | 2d6, puis 1d3 par sauvegarde ratée |
| Effroi sépulcral | Entrave | Majeur | | 6 | −20 à la cible pendant tout le combat |

Improvisations : sentir la mort proche (utilitaire, mineur) · conserver un corps (utilitaire, mineur) · murmures d'outre-tombe (entrave −10, mineur) · faire bouger un cadavre un instant (utilitaire, modéré).

### Nature

| Sort | Effet | Puissance | Propriété | Coût | Ce qu'il fait |
|---|---|---|---|---|---|
| Baies de vie | Soin | Mineur | | 1 | 1d3 PV |
| Parler aux bêtes | Utilitaire | Mineur | | 1 | Comprendre un animal et lui parler |
| Ronces | Entrave | Modéré | | 3 | −20 à la cible pendant 1 round |
| Peau d'écorce | Protection | Modéré | | 3 | Armure +2 |
| Colère de la forêt | Attaque | Majeur | Zone | 7 | 3d6 sur 2 cibles proches |

Improvisations : trouver de l'eau ou de la nourriture (utilitaire, mineur) · calmer un animal (utilitaire, mineur) · se fondre dans les bois (renfort +10 en Discrétion, mineur) · faire pousser ou écarter la végétation (utilitaire, modéré).

## Annexe D — Parcours par genre

Des modèles, pas une liste figée : le générateur d'univers les adapte au cadre de chaque campagne. Un parcours est le métier de quelqu'un dans le monde : il sert au personnage du joueur, et plus tard aux compagnons et aux PNJ. Les compétences portent ici leur nom d'univers (voir l'annexe A).

### Cyberpunk

**La rue armée**

1. **Solo** — Mercenaire augmenté, payé pour protéger, escorter ou tuer. C'est le premier qu'on appelle quand ça tire, le dernier qu'on invite à une négociation. Il a vendu un peu de son humanité à chaque implant. *Armes à distance, Combat rapproché, Esquive, Athlétisme, Vigilance, Intimidation, Conduite, Cybernétique.*
2. **Ganger** — Membre d'un gang de quartier, qui vit de racket, de deal et de guerres de territoire. Pour lui, la loyauté envers la bande passe avant tout. Il est dangereux en meute et beaucoup moins quand il est seul. *Combat rapproché, Armes à distance, Intimidation, Athlétisme, Vigilance, Doigts agiles, Conduite, Esquive.*
3. **Kobun yakuza** — Soldat d'un clan, lié par le giri et tatoué jusqu'aux os. Il gère les tripots et les dettes de son oyabun. Respecté et craint dans le quartier, il ne peut jamais tourner le dos à son clan. *Intimidation, Négociation, Combat rapproché, Armes à distance, Réseau, Empathie, Arnaque, Vigilance.*
4. **Agent d'infiltration** — Le shinobi des corporations : vol de prototypes, sabotage, extraction de cadres. Il entre là où personne n'entre et repart sans laisser de trace. Il est redoutable seul, et on le sacrifie sans hésiter s'il est pris. *Infiltration, Combat rapproché, Esquive, Athlétisme, Arnaque, Contre-mesures, Vigilance, Doigts agiles.*

**L'ordre et les corpos**

5. **Flic de la NeoPol** — Inspecteur dans une police sous-payée et à moitié rachetée par les corpos. Il a un badge, une arme et des enquêtes qu'on lui demande d'enterrer. Il est utile, mais toujours tiraillé entre la loi, l'argent et sa conscience. *Armes à distance, Data-mining, Intimidation, Vigilance, Conduite, Empathie, Combat rapproché, Réseau.*
6. **Agent de sécurité corpo** — Garde d'élite d'une tour Arasaka ou d'un labo privé, équipé du meilleur matériel. Il obéit aux protocoles. Il est discipliné et bien armé, et il ne voit pas plus loin que son badge d'accès. *Armes à distance, Esquive, Vigilance, Contre-mesures, Intimidation, Athlétisme, Meneur, Cybernétique.*
7. **Cadre corpo** — Requin en costume, qui grimpe les étages de la tour à coups de trahisons feutrées. Il manie les budgets, les contrats et les gens. Il est puissant dans les salles de réunion et perdu dans une ruelle. *Négociation, Meneur, Éducation, Arnaque, Empathie, Data-mining, Réseau, Armes à distance.*
8. **Salaryman** — Employé de bureau broyé par les heures sup', les dettes et les promesses de promotion. C'est l'homme ordinaire de Néo-Tokyo. Il est invisible, donc il a accès à beaucoup de choses sans que personne ne s'en méfie. *Éducation, Négociation, Data-mining, Empathie, Piratage, Meneur, Conduite, Esquive.*

**La tech**

9. **Netrunner** — Pirate de génie qui plonge dans les réseaux des corpos pour voler, saboter ou effacer. Dans la rue, il passe pour un gamin fragile ; dans le Net, il est un dieu. Il est indispensable pour un job et vulnérable dès que ça tire. *Piratage, Data-mining, Contre-mesures, Vigilance, Infiltration, Bricolage tech, Arnaque, Esquive.*
10. **Techie** — Bricoleur de génie qui répare, trafique et invente avec ce qu'il trouve. Son atelier est une caverne d'Ali Baba de pièces détachées. Tout le monde a besoin de lui, et personne ne le paie à l'heure. *Bricolage tech, Piratage, Sciences, Contre-mesures, Conduite, Vigilance, Doigts agiles, Armes à distance.*
11. **Charcudoc** — Chirurgien des bas-fonds, il pose des implants et recoud des blessures par balle sans poser de questions. Toute la rue lui doit la vie, ou un bras. C'est un médecin génial, souvent mêlé à des affaires louches. *Médecine, Cybernétique, Sciences, Piratage, Empathie, Vigilance, Négociation, Esquive.*
12. **Ferrailleur** — Il fouille les décharges et les carcasses de drones pour revendre ce qui marche encore. Il sait ce que vaut chaque pièce et où la trouver. Débrouillard, il vit en marge, et ses trouvailles attirent parfois de mauvaises attentions. *Bricolage tech, Survie, Vigilance, Doigts agiles, Athlétisme, Négociation, Contre-mesures, Combat rapproché.*

**Les gens de parole**

13. **Fixer** — Intermédiaire de l'ombre, il connaît tout le monde et doit quelque chose à chacun. Il trouve les jobs, les armes et les portes de sortie. Il est redoutable avec les mots, et son réseau est une toile qui peut l'étrangler. *Réseau, Négociation, Empathie, Arnaque, Intimidation, Vigilance, Armes à distance, Data-mining.*
14. **Informateur** — Barman, sans-abri ou concierge, il voit tout et il vend ce qu'il voit. C'est l'oreille du quartier. Il est précieux, il ne paie pas de mine et il n'est jamais loin d'une balle perdue. *Réseau, Vigilance, Infiltration, Empathie, Arnaque, Doigts agiles, Data-mining, Esquive.*
15. **Journaliste** — Reporter indépendant qui traque les scandales que les médias corpos étouffent. Une vidéo de lui peut faire tomber un cadre. Il délie les langues comme personne, et il a une cible dans le dos. *Data-mining, Négociation, Empathie, Arnaque, Infiltration, Réseau, Vigilance, Esquive.*
16. **Rockerboy** — Musicien rebelle dont les chansons appellent à brûler les tours. La rue l'adore, les corpos le surveillent. C'est un leader né, et sa célébrité le rend facile à trouver. *Performance, Négociation, Meneur, Empathie, Intimidation, Réseau, Combat rapproché, Conduite.*
17. **Idol** — Star de la pop, fabriquée et vendue par une corpo du divertissement. Des millions de fans, un contrat qui l'étrangle. Elle a un accès partout, et aucune liberté nulle part. *Performance, Négociation, Empathie, Arnaque, Athlétisme, Réseau, Éducation, Esquive.*

**La route**

18. **Nomade** — Membre d'un clan qui vit sur les routes, hors des mégapoles et de leurs lois. Il transporte, il trafique et il protège les siens. Pilote hors pair et solide survivant, il reste un étranger en ville. *Conduite, Survie, Armes à distance, Bricolage tech, Vigilance, Athlétisme, Négociation, Combat rapproché.*
19. **Coursier** — Livreur à moto qui traverse Néo-Tokyo plus vite que n'importe qui, colis légaux ou non. Il connaît chaque raccourci et chaque contrôle. Rapide et insaisissable, il en sait toujours trop sur ce qu'il transporte. *Conduite, Athlétisme, Vigilance, Esquive, Infiltration, Réseau, Bricolage tech, Armes à distance.*

**Équipement de départ** (voir 5) : une option par case, et deux objets racontés.

| Parcours | Arme | Armure | Implant (−2 SM) | Objets (2 parmi) |
|---|---|---|---|---|
| Solo | Pistolet lourd · Fusil à pompe · Katana | Gilet balistique (3) · Manteau blindé (2) | Bras cybernétique · Yeux cybernétiques · Peau dermique | chargeurs de rechange · lunettes de vision nocturne · trousse de premiers soins · un charcudoc qui lui doit un service |
| Ganger | Machette · Batte de baseball · Pistolet léger | Veste renforcée (1) · — | Griffes-rasoirs · Suite cyberaudio · — | les couleurs du gang · téléphone jetable · bombe de peinture · dose de stim |
| Kobun yakuza | Katana · Wakizashi · Pistolet lourd | Manteau blindé (2) · Veste renforcée (1) | Suite cyberaudio · — | irezumi du clan · carnet des dettes · téléphone du clan · étui à cigares |
| Agent d'infiltration | Kunai · Tantō · Pistolet silencieux | — · Veste renforcée (1) | Yeux cybernétiques · Neuroport | combinaison furtive · kit de crochetage électronique · grappin · faux badge corpo |
| Flic de la NeoPol | Pistolet lourd · Revolver lourd | Gilet balistique (3) · Gilet pare-balles léger (2) | Suite cyberaudio · — | badge · menottes · radio de service · lampe tactique |
| Agent de sécurité corpo | Pistolet-mitrailleur · Pistolet lourd · Matraque électrique | Gilet balistique (3) · Armure de garde corpo (3) | Suite cyberaudio · Yeux cybernétiques | badge d'accès · uniforme de la corpo · menottes · radio cryptée |
| Cadre corpo | Pistolet léger · Pistolet compact · — | — · Gilet pare-balles léger (2) | Neuroport · Suite cyberaudio | carte d'accès à la tour · terminal corpo · costume sur mesure · carnet de contacts |
| Salaryman | — · Pistolet compact | — | Neuroport · — | badge d'entreprise · mallette · téléphone · abonnement de métro |
| Netrunner | Pistolet léger · Pistolet silencieux · — | — · Veste renforcée (1) | Neuroport · Paume d'interface | deck · câbles d'interface · lunettes AR · fausse identité numérique |
| Techie | Fusil à pompe · Pistolet léger · Marteau lourd | — · Veste renforcée (1) | Paume d'interface · Bras cybernétique | outils multifonctions · poste à souder portatif · petit drone de réparation (raconté) · stock de pièces détachées |
| Charcudoc | Pistolet léger · Couteau | — · Veste renforcée (1) | Yeux cybernétiques · Paume d'interface | kit chirurgical · scanner médical · stock d'anesthésiants · table d'opération pliante |
| Ferrailleur | Machette · Batte de baseball · Fusil à pompe | Veste renforcée (1) · Combinaison de motard (1) | Filtre toxique · Poumons renforcés | chalumeau · détecteur de métaux · sac de récupération · masque à gaz |
| Fixer | Pistolet lourd · Pistolet silencieux | Manteau blindé (2) · Gilet pare-balles léger (2) | Suite cyberaudio · Neuroport | carnet d'adresses chiffré · téléphones jetables · faux papiers · faveurs qu'on lui doit |
| Informateur | Couteau · Pistolet compact | — | Suite cyberaudio · — | oreillette d'écoute · double des clés du quartier · carnet de notes · appareil photo discret |
| Journaliste | Pistolet léger · — | — · Veste renforcée (1) | Yeux cybernétiques · — | caméra holo · enregistreur · carte de presse · source anonyme |
| Rockerboy | Pistolet lourd · Batte de baseball | Veste renforcée (1) · Manteau blindé (2) | Suite cyberaudio · — | guitare électrique · ampli portable · fans fidèles · vieux contrat de disque |
| Idol | — · Pistolet compact | — | Yeux cybernétiques · — | garde-robe de scène · contrat d'agence · lunettes de star · numéro privé d'un producteur |

| Parcours | Arme | Armure | Implant (−2 SM) | Véhicule | Objets (2 parmi) |
|---|---|---|---|---|---|
| Nomade | Fusil à pompe · Carabine · Machette | Manteau blindé (2) · Combinaison de motard (1) | Filtre toxique · — | Pick-up · Moto lourde | kit de survie · outils du clan · jerricans · carte des pistes |
| Coursier | Pistolet léger · Matraque télescopique | Combinaison de motard (1) · Veste renforcée (1) | Suite cyberaudio · — | Moto de livraison · Scooter électrique | casque connecté · sac de livraison scellé · plan des raccourcis · antivol renforcé |

### Fantasy

Un parcours marqué **(magie)** n'existe que si l'univers active la magie ; il conseille des domaines, et dit ce qui le remplace sans magie. Les autres valent dans les deux cas.

**Le fer**

1. **Homme d'armes** — Soldat de métier, ancien garde ou vétéran d'une guerre oubliée, il vit de son épée et de sa réputation. Dans une taverne, on lui cède la place ; sur un champ de bataille, on se range derrière lui. Il est solide et rassurant, et démuni face aux énigmes et aux intrigues de cour. *Armes de mêlée, Esquive, Athlétisme, Intimidation, Perception, Commandement, Équitation & navigation, Survie.*
2. **Chevalier** — Fils de noblesse lié par un serment, à un seigneur, à un dieu ou à une cause perdue. Sa lance et son nom ouvrent les portes des châteaux. Il est redoutable à cheval et respecté partout, et il est prisonnier de son honneur quand le monde, lui, n'en a pas. *Armes de mêlée, Équitation & navigation, Commandement, Éloquence, Athlétisme, Intimidation, Lettres & légendes, Foi.*
3. **Garde de la cité** — Il veille sur les remparts et les ruelles, entre ivrognes, voleurs et nobles capricieux. Il connaît sa ville par cœur et tout le monde le connaît. Il est utile dans une enquête, mais lié par ses ordres et son capitaine. *Armes de mêlée, Armes à distance, Perception, Intimidation, Enquête, Perspicacité, Athlétisme, Commandement.*
4. **Barbare** — Né dans les steppes ou les montagnes, loin des lois des royaumes. Il se bat avec une fureur que les chevaliers ne comprennent pas. Il est endurant et terrifiant, et la civilisation le regarde comme une bête. *Armes de mêlée, Athlétisme, Survie, Intimidation, Esquive, Perception, Équitation & navigation, Médecine.*
5. **Rôdeur** — Chasseur et éclaireur des marches sauvages, il connaît chaque sentier et chaque piste. Les villageois l'appellent quand une bête rôde, les seigneurs quand une armée doit passer. Il est imbattable en forêt et à l'étroit entre les murs d'une ville. *Armes à distance, Survie, Discrétion, Perception, Athlétisme, Armes de mêlée, Médecine, Esquive.*

**L'ombre**

6. **Voleur** — Monte-en-l'air, coupe-bourse ou cambrioleur de guilde, il ouvre ce qui est fermé et prend ce qui brille. On le méprise en public et on l'engage en secret. Agile et rusé, il évite le combat loyal, qu'il a toutes les chances de perdre. *Larcin, Crochetage & pièges, Discrétion, Duperie, Perception, Armes de mêlée, Athlétisme, Esquive.*
7. **Assassin** — Lame d'une confrérie ou tueur solitaire, il règle les héritages trop lents et les rivalités trop longues. Il frappe une fois, dans l'ombre, avec du poison s'il le faut. Il est mortel par surprise et fragile dès qu'on le voit venir. *Discrétion, Armes de mêlée, Esquive, Alchimie, Duperie, Perception, Athlétisme, Crochetage & pièges.*
8. **Contrebandier** — Il fait passer les épices, les reliques et les fugitifs entre les ports et les frontières. Il connaît les criques, les douaniers corrompus et les routes oubliées. Il est débrouillard et beau parleur, et il est toujours à une trahison de la potence. *Équitation & navigation, Duperie, Éloquence, Perception, Armes à distance, Discrétion, Larcin, Survie.*

**Le savoir et la foi**

9. **Mage (magie)** — Érudit des Arcanes, formé dans une tour ou auprès d'un maître exigeant. On le craint autant qu'on le recherche, car un sort bien placé change le cours d'une bataille. Il est redoutable à distance et se brise vite au corps à corps, et chaque sort lui coûte. *Arcanes, Savoir occulte, Lettres & légendes, Perception, Perspicacité, Médecine, Éloquence, Esquive.* Domaines conseillés : au choix, selon son école. Sans magie : remplacé par l'Érudit.
10. **Prêtre (magie)** — Serviteur d'un dieu, il bénit, il soigne et il guide les fidèles, parfois l'épée à la main. Son temple lui donne une autorité que les seigneurs respectent. Il est un pilier pour les siens, et un ennemi juré pour les autres cultes. *Foi, Médecine, Éloquence, Perspicacité, Lettres & légendes, Arcanes, Armes de mêlée, Commandement.* Domaines conseillés : Guérison, plus un domaine propre à son dieu. Sans magie : Savoir occulte remplace Arcanes, et sa Foi devient rites, sermons et réconfort, sans miracles.
11. **Érudit** — Archiviste, précepteur ou chercheur, il lit les langues mortes et se souvient de ce que le monde a oublié. Les rois le consultent, les bibliothèques lui ouvrent leurs portes. Il est précieux pour comprendre, et inutile pour se défendre. *Lettres & légendes, Philosophie naturelle, Savoir occulte, Enquête, Perspicacité, Éloquence, Médecine, Esquive.*
12. **Alchimiste** — Il distille les potions, les poisons et les poudres qui explosent. Moitié savant, moitié charlatan aux yeux du peuple. Il est inventif et redouté, et chacune de ses fioles peut lui sauter au visage. *Alchimie, Philosophie naturelle, Médecine, Perception, Forge & artisanat, Duperie, Armes à distance, Lettres & légendes.*
13. **Guérisseur** — Herboriste de village ou rebouteux des routes, il soigne avec les plantes, les mains et les prières. On le paie en pain et en reconnaissance. Il est indispensable et aimé, et il est sans défense quand la violence arrive. *Médecine, Survie, Alchimie, Perspicacité, Perception, Éloquence, Foi, Esquive.*
14. **Druide (magie)** — Gardien des forêts anciennes, il parle aux bêtes et fait plier les ronces. Les villages le craignent et le consultent à la fois. Il est puissant dans les bois, sans pouvoir dans les cités de pierre. *Arcanes, Survie, Médecine, Perception, Discrétion, Perspicacité, Savoir occulte, Armes de mêlée.* Domaines conseillés : Nature, plus Guérison ou Givre. Sans magie : remplacé par le Guérisseur ou le Rôdeur.
15. **Lame-mage (magie)** — Guerrier qui mêle l'acier et les sorts, formé dans un ordre martial ou une académie de guerre. Il charge là où les mages restent en retrait. Il est polyvalent, mais il n'égale ni le vrai guerrier ni le vrai mage. *Arcanes, Armes de mêlée, Esquive, Athlétisme, Savoir occulte, Perception, Intimidation, Équitation & navigation.* Domaines conseillés : Pyromancie ou Givre. Sans magie : remplacé par le Chevalier ou l'Homme d'armes.

**La parole et la route**

16. **Barde** — Conteur, musicien et colporteur de nouvelles, il est bienvenu dans chaque château et chaque taverne. Ses chansons font et défont les réputations. Il est charmeur et curieux, et sa langue lui attire autant d'ennuis qu'elle l'en sort. *Musique & contes, Éloquence, Duperie, Perspicacité, Lettres & légendes, Larcin, Armes de mêlée, Esquive.*
17. **Marchand** — Il fait voyager le sel, la soie et l'argent d'un royaume à l'autre. Il négocie comme d'autres se battent. Il est riche en contacts et en opportunités, et sa caravane est une cible ambulante. *Éloquence, Perspicacité, Équitation & navigation, Lettres & légendes, Duperie, Perception, Intimidation, Armes à distance.*
18. **Noble** — Héritier d'une maison, il manie les alliances, les mariages et les poisons de cour. Son nom ouvre toutes les portes, et ses ennemis aussi. Il est puissant dans les salons et vulnérable dès qu'il perd ses gardes. *Éloquence, Commandement, Lettres & légendes, Duperie, Perspicacité, Musique & contes, Équitation & navigation, Armes de mêlée.*
19. **Forgeron** — Artisan respecté, il fabrique les armes des chevaliers et les outils des paysans. Sa forge est le cœur du village. Il est fort et habile de ses mains, et il connaît l'acier mieux que quiconque, mais il est attaché à son atelier. *Forge & artisanat, Mécanismes, Athlétisme, Armes de mêlée, Perception, Éloquence, Philosophie naturelle, Intimidation.*
20. **Marin** — Matelot, pêcheur ou corsaire, il a vu des ports que les cartes ignorent. Il est à l'aise sur un pont qui tangue et au milieu d'une rixe de port. Il est endurant et bagarreur, mais perdu dès qu'il s'éloigne de la mer. *Équitation & navigation, Athlétisme, Armes de mêlée, Survie, Perception, Mécanismes, Intimidation, Musique & contes.*

Dans un univers sans magie, la Foi se limite aux rites, au savoir religieux et au réconfort : pas de miracles. Le générateur adapte sa description.

### Dark fantasy

La magie y est rare et corruptrice. Un parcours marqué **(magie)** n'existe que si l'univers l'active.

**Le fer**

1. **Mercenaire** — Une lame à louer dans un monde qui brûle. Sans foi ni bannière, il ne connaît que la parole du contrat et le poids de l'or. Il est endurant et pragmatique, ne fait confiance à personne, et personne ne lui fait confiance. *Armes de mêlée, Esquive, Athlétisme, Intimidation, Survie, Vigilance, Commandement, Forge & artisanat.*
2. **Chevalier déchu** — Il a perdu ses terres, son seigneur ou son honneur, parfois les trois. Il garde son armure cabossée et une colère froide. Il est redoutable et fier, et hanté par ce qu'il a fait ou laissé faire. *Armes de mêlée, Équitation, Intimidation, Commandement, Foi, Lettres anciennes, Athlétisme, Méfiance.*
3. **Chasseur de sorcières** — Traqueur au service d'un ordre implacable, il brûle ce que d'autres n'osent même pas nommer. Les villages le redoutent autant que les créatures qu'il pourchasse. Il est armé, savant et inflexible, et il voit des hérétiques partout, parfois à tort. *Armes de mêlée, Armes à distance, Savoir impie, Enquête, Intimidation, Vigilance, Foi, Esquive.*
4. **Tueur de monstres** — Il vit de primes sur les goules, les loups-garous et les choses des marais. On le paie, puis on le chasse du village. Il connaît chaque bête et son point faible, et il est seul, toujours. *Armes de mêlée, Esquive, Savoir impie, Survie, Vigilance, Athlétisme, Médecine, Philosophie naturelle.*
5. **Flagellant** — Fanatique qui expie les péchés du monde dans la douleur, et qui fait expier ceux des autres. Les foules le suivent, les prêtres s'en méfient. Il ne connaît ni la peur ni la mesure, ce qui fait de lui un allié aussi dangereux qu'un ennemi. *Armes de mêlée, Foi, Intimidation, Éloquence, Athlétisme, Méfiance, Chants & récits, Savoir impie.*
6. **Déserteur** — Il a fui une guerre qu'il ne comprenait plus, et on le pend s'il est repris. Il sait se cacher, voler et survivre. Il est rusé et endurant, et il est toujours sur le qui-vive. *Discrétion, Survie, Armes à distance, Vigilance, Duperie, Athlétisme, Larcin, Esquive.*

**L'ombre et la survie**

7. **Pilleur de tombes** — Il descend dans les cryptes et les tertres pour en remonter l'or des morts. Il connaît les pièges, les malédictions et les gardiens qui ne dorment jamais. Il est hardi et cupide, et parfois il réveille ce qu'il fallait laisser dormir. *Crochetage & pièges, Savoir impie, Discrétion, Vigilance, Lettres anciennes, Larcin, Athlétisme, Armes de mêlée.*
8. **Bandit de grand chemin** — Il détrousse les voyageurs sur les routes que plus aucun seigneur ne protège. Pour les uns c'est un hors-la-loi, pour les autres un héros du peuple. Il est rapide et sans scrupules, et la corde l'attend au prochain bourg. *Armes à distance, Armes de mêlée, Intimidation, Équitation, Discrétion, Survie, Duperie, Vigilance.*
9. **Rat des bas-fonds** — Il est né dans la boue des cités, entre les égouts, les tripots et la peste. Il survit à tout parce qu'il ne croit à rien. Il est malin et insaisissable, et il trahit avant d'être trahi. *Larcin, Discrétion, Duperie, Méfiance, Armes de mêlée, Vigilance, Crochetage & pièges, Esquive.*
10. **Fossoyeur** — Il enterre les morts de la peste et des guerres, et il sait ce qui remue parfois sous la terre. On l'évite dans la rue et on l'appelle la nuit. Il est solide et sans illusions, et il en sait trop sur ce qui suit la mort. *Savoir impie, Médecine, Athlétisme, Vigilance, Méfiance, Forge & artisanat, Armes de mêlée, Lettres anciennes.*

**Le savoir, la foi et les ténèbres**

11. **Sorcier renégat (magie)** — Il a lu ce qu'il ne fallait pas lire, et il a survécu. Pourchassé par l'Église, il marchande avec des puissances qui finissent toujours par réclamer leur dû. Son pouvoir est immense, et chaque pacte le rapproche du bûcher, ou de pire. *Sorcellerie, Démonologie, Savoir impie, Duperie, Méfiance, Discrétion, Médecine, Esquive.* Domaines conseillés : Nécromancie, Illusion. Sans magie : remplacé par l'Occultiste.
12. **Occultiste** — Collectionneur de grimoires interdits, il connaît les rituels sans toujours oser les accomplir. Il sait nommer les démons et les éloigner. Il est savant et précieux, et son savoir lui ronge l'âme. *Savoir impie, Démonologie, Lettres anciennes, Enquête, Méfiance, Éloquence, Philosophie naturelle, Esquive.*
13. **Exorciste (magie)** — Prêtre-guerrier qui chasse les démons des corps et des lieux, par la prière et par le feu. L'Église l'envoie là où les autres ont échoué. Il est implacable face aux ténèbres, et chaque possession lui laisse une cicatrice. *Foi, Sorcellerie, Démonologie, Éloquence, Méfiance, Savoir impie, Médecine, Armes de mêlée.* Domaines conseillés : Guérison, Pyromancie (le feu qui purifie). Sans magie : Savoir impie remplace Sorcellerie, et ses exorcismes deviennent des rites, sans effet chiffré.
14. **Moine** — Copiste, infirmier ou ermite, il garde la foi et le savoir dans un monde qui sombre. Son monastère est un dernier refuge. Il est sage et charitable, et il n'est pas fait pour la violence du dehors. *Foi, Médecine, Éloquence, Méfiance, Lettres anciennes, Chants & récits, Vigilance, Esquive.*
15. **Inquisiteur** — Juge de l'Église, il traque l'hérésie avec des questions, des aveux et des bûchers. Sa simple arrivée vide les rues. Il est redoutable d'intelligence et de pouvoir, et il est sûr d'avoir raison. *Enquête, Intimidation, Foi, Méfiance, Lettres anciennes, Éloquence, Armes de mêlée, Commandement.*
16. **Médecin de peste** — Sous son masque à bec, il soigne les mourants que tous les autres fuient. Il a vu la maladie de trop près pour croire encore aux remèdes miracles. Il est précieux et respecté, et la contagion le guette à chaque visite. *Médecine, Philosophie naturelle, Savoir impie, Méfiance, Vigilance, Éloquence, Lettres anciennes, Esquive.*
17. **Sorcière des marais (magie)** — Elle vit seule au bord des tourbières, entre les herbes, les os et les esprits. Les villageois viennent la voir en cachette, puis la dénoncent. Elle connaît les remèdes et les malédictions, et le bûcher n'est jamais loin. *Sorcellerie, Survie, Médecine, Savoir impie, Méfiance, Duperie, Discrétion, Armes de mêlée.* Domaines conseillés : Nature, Nécromancie. Sans magie : une rebouteuse, avec Savoir impie à la place de Sorcellerie, ou remplacée par le Médecin de peste.

**La parole et les gens**

18. **Colporteur** — Chanteur des ruines et marchand de nouvelles, il traverse les terres dévastées avec sa charrette. Il sait ce qui se passe partout, et il le vend. Il est charmeur et méfiant, et toujours sur une route peu sûre. *Chants & récits, Éloquence, Duperie, Méfiance, Larcin, Équitation, Vigilance, Esquive.*
19. **Noble décadent** — Héritier d'une maison qui pourrit de l'intérieur, entre fêtes, complots et poisons. Il a de l'or, des gardes et des secrets inavouables. Il est puissant mais corrompu, et entouré de gens qui attendent sa chute. *Éloquence, Commandement, Duperie, Méfiance, Lettres anciennes, Chants & récits, Équitation, Armes de mêlée.*
20. **Serf** — Paysan attaché à une terre qui ne lui appartient pas, il a survécu aux famines, aux guerres et aux seigneurs. Il est le peuple qu'on oublie. Il est endurant et débrouillard, et il a une colère qui couve. *Survie, Athlétisme, Forge & artisanat, Vigilance, Armes de mêlée, Méfiance, Équitation, Médecine.*

La Démonologie est un savoir : nommer, reconnaître et repousser par les rites. Elle n'invoque jamais d'allié, même quand la magie est active (voir 10.9).

### Horreur

Cadre par défaut contemporain ; le générateur adapte les parcours à l'époque choisie. La magie, ce sont des Rituels, qui coûtent aussi de la Santé mentale. Un parcours marqué **(magie)** n'existe que si l'univers l'active.

**Ceux qui cherchent**

1. **Détective privé** — Il vit de filatures, d'adultères et de disparitions que la police a classées trop vite. Il a appris à se méfier de tout le monde. Il est méthodique et discret, et une affaire de trop va le mener là où il ne fallait pas aller. *Investigation, Perception, Psychologie, Mensonge, Discrétion, Armes à distance, Conduite, Serrures & alarmes.*
2. **Policier** — Inspecteur de la criminelle, il a vu des scènes que ses collègues refusent de décrire. Il a un badge, une arme et des rapports qu'il n'ose pas finir. Il est efficace et protégé par l'institution, et l'institution n'a pas de case pour ce qu'il découvre. *Armes à distance, Investigation, Intimidation, Perception, Conduite, Psychologie, Combat rapproché, Persuasion.*
3. **Journaliste** — Reporter d'investigation, il tire sur un fil qui mène toujours plus loin. Ses sources disparaissent les unes après les autres. Il délie les langues comme personne, et il ne sait pas s'arrêter. *Investigation, Persuasion, Psychologie, Mensonge, Culture générale, Discrétion, Informatique, Esquive.*
4. **Enquêteur du paranormal** — Avec caméras, détecteurs et une chaîne qui compte trois mille abonnés, il traque les fantômes. Tout le monde se moque de lui, jusqu'au jour où le détecteur s'affole vraiment. Il est équipé et passionné, et il est totalement imprudent. *Informatique, Occultisme, Investigation, Perception, Mécanique, Arts, Persuasion, Esquive.*

**Ceux qui savent**

5. **Universitaire** — Professeur d'histoire, de linguistique ou d'anthropologie, il lit ce que personne ne sait plus lire. Un manuscrit légué à sa faculté va changer sa vie. Il est savant et méthodique, et il n'est pas fait pour courir. *Culture générale, Sciences, Occultisme, Investigation, Persuasion, Psychologie, Informatique, Esquive.*
6. **Archéologue** — Il fouille les sites oubliés, des déserts aux cavernes sous les montagnes. Il sait dater une pierre et lire une inscription morte. Il est endurant et curieux, et certaines tombes ont été scellées pour une bonne raison. *Culture générale, Occultisme, Investigation, Athlétisme, Survie, Perception, Sciences, Armes à distance.*
7. **Antiquaire** — Marchand de livres rares et d'objets anciens, il sait d'où vient chaque pièce, et à qui elle a coûté la raison. Les collectionneurs étranges le connaissent bien. Il est érudit et bien renseigné, et sa boutique attire les mauvaises personnes. *Culture générale, Occultisme, Persuasion, Perception, Investigation, Mensonge, Arts, Esquive.*
8. **Occultiste (magie)** — Collectionneur de grimoires, universitaire déchu ou héritier d'une lignée maudite. Il connaît les rituels, et il sait ce qu'ils coûtent. C'est la seule arme contre l'indicible, et chaque savoir interdit lui ronge un peu plus l'esprit. *Rituels, Occultisme, Mythe, Culture générale, Investigation, Psychologie, Arts, Esquive.* Domaines conseillés : Nécromancie, Illusion, adaptés à l'Horreur. Sans magie : Persuasion remplace Rituels ; il connaît les rites sans pouvoir les accomplir.
9. **Médium (magie)** — Voyante de quartier ou spirite renommée, elle entend ce que les autres n'entendent pas. La moitié de ses clients sont des escrocs, et elle aussi, parfois. Elle est un pont avec l'au-delà, et l'au-delà sait qu'elle écoute. *Rituels, Psychologie, Occultisme, Persuasion, Mensonge, Perception, Arts, Esquive.* Domaines conseillés : Nécromancie (parler aux morts), Illusion. Sans magie : une voyante charlatan, avec Discrétion à la place de Rituels.
10. **Prêtre** — Curé de campagne ou aumônier d'hôpital, il réconforte les vivants et enterre les morts. Il a la foi, mais pas toutes les réponses. Il est écouté et respecté, et il découvre que le Mal existe vraiment. *Occultisme, Psychologie, Persuasion, Culture générale, Médecine, Arts, Perception, Esquive.*

**Ceux qui soignent**

11. **Médecin** — Urgentiste, légiste ou généraliste, il a vu la mort de près, mais jamais comme ça. Il soigne les corps quand tout s'effondre. Il est indispensable à un groupe et démuni dès qu'il faut fuir ou se battre. *Médecine, Sciences, Psychologie, Perception, Persuasion, Investigation, Esquive, Conduite.*
12. **Psychiatre** — Il écoute les délires de ses patients depuis des années, et certains commencent à se ressembler un peu trop. Il comprend les esprits brisés. Il est précieux pour garder le groupe debout, et il est le prochain sur la liste. *Psychologie, Médecine, Persuasion, Sciences, Investigation, Culture générale, Perception, Esquive.*
13. **Infirmière** — De garde la nuit, elle a vu des patients guérir trop vite, ou mourir pour rien. Elle tient le coup quand les médecins craquent. Elle est solide, efficace et attentive, et elle est souvent la seule à remarquer ce qui cloche. *Médecine, Psychologie, Perception, Athlétisme, Persuasion, Conduite, Sciences, Esquive.*

**Ceux qui se battent**

14. **Vétéran** — Ancien soldat revenu d'une guerre qu'il ne raconte pas. Il dort mal et il garde une arme sous l'oreiller. Il est le meilleur quand ça dégénère, et ses propres démons l'attendent déjà. *Armes à distance, Combat rapproché, Esquive, Athlétisme, Survie, Perception, Intimidation, Médecine.*
15. **Chasseur** — Homme des bois et des campagnes isolées, il connaît chaque piste et chaque bête. Ces derniers temps, il trouve des traces qu'il ne sait pas nommer. Il est autonome et bon tireur, et méfiant envers les gens de la ville. *Armes à distance, Survie, Discrétion, Perception, Athlétisme, Conduite, Médecine, Mécanique.*
16. **Voyou** — Petit truand des quartiers, il vit de cambriolages, de deals et de services rendus. Il connaît les gens que la police ne connaît pas. Il est débrouillard et pas regardant, et il a des dettes envers des gens dangereux. *Combat rapproché, Pickpocket, Serrures & alarmes, Intimidation, Mensonge, Discrétion, Perception, Armes à distance.*

**Les gens ordinaires… ou presque**

17. **Artiste** — Peintre, écrivain ou musicien, il cherche l'inspiration dans les rêves, et les rêves lui répondent. Ses œuvres troublent ceux qui les regardent. Il est sensible et visionnaire, et fragile face à ce qu'il pressent. *Arts, Psychologie, Culture générale, Occultisme, Perception, Persuasion, Mensonge, Esquive.*
18. **Héritier fortuné** — Il a hérité d'une fortune, d'un manoir et des secrets de famille qui vont avec. L'argent ouvre toutes les portes, même celles qu'il faudrait laisser closes. Il a des moyens et des relations, et un passé familial qui le rattrape. *Persuasion, Culture générale, Conduite, Arts, Psychologie, Meneur, Armes à distance, Occultisme.*
19. **Ouvrier** — Mécano, électricien ou homme à tout faire, il répare ce qui casse et descend là où les autres ne vont pas. Il croit ce qu'il touche. Il est solide et pratique, et il ne croit pas aux fantômes, jusqu'à la cave de trop. *Mécanique, Athlétisme, Conduite, Perception, Serrures & alarmes, Combat rapproché, Survie, Intimidation.*
20. **Sectateur** — Membre d'un culte qui promet la vérité, la puissance ou l'éternité. Il connaît des secrets qu'il n'aurait jamais dû apprendre. Il est surtout fait pour les PNJ, mais c'est un perso fascinant pour qui veut jouer la rédemption, ou la chute. *Occultisme, Mythe, Mensonge, Persuasion, Discrétion, Combat rapproché, Psychologie, Arts.*

Le Mythe a un prix dès la création : chaque point baisse la Santé mentale maximum (99 − Mythe). Les parcours qui le contiennent commencent plus fragiles.

### Contemporain

Le monde d'aujourd'hui, sans magie : polar, thriller, action.

**L'ordre**

1. **Flic** — Inspecteur de terrain, entre procédure et coups de pression. Il a un badge, une arme et un supérieur sur le dos. Efficace dans la rue comme dans un bureau, il est tenu par la loi… quand il la respecte. *Armes à distance, Investigation, Intimidation, Perception, Conduite, Psychologie, Combat rapproché, Bureaucratie.*
2. **Agent d'intervention** — Membre d'une unité d'élite, il enfonce les portes quand les négociations échouent. Il est entraîné, équipé et soudé avec son équipe. C'est le meilleur dans l'assaut, mais il est bridé par la hiérarchie et les règles d'engagement. *Armes à distance, Combat rapproché, Esquive, Athlétisme, Perception, Discrétion, Meneur, Médecine.*
3. **Garde du corps** — Il protège les riches, les célèbres et les menacés, et il prend la balle s'il le faut. Il voit le danger avant tout le monde. Il est vigilant et loyal, et il ne vit pas sa propre vie. *Combat rapproché, Armes à distance, Perception, Psychologie, Conduite, Athlétisme, Intimidation, Esquive.*
4. **Avocat** — Pénaliste ou conseiller d'affaires, il connaît la loi assez bien pour la contourner. Il sait faire sortir un client et couler un adversaire. Il est redoutable dans un tribunal, et désarmé dans une ruelle. *Persuasion, Bureaucratie, Psychologie, Mensonge, Culture générale, Investigation, Réseau, Esquive.*

**La rue**

5. **Voyou** — Petit truand des quartiers, il vit de deals, de rackets et de services rendus. Il connaît les gens que la police ne connaît pas. Il est débrouillard et pas regardant, et il a des dettes envers des gens dangereux. *Combat rapproché, Pickpocket, Serrures & alarmes, Intimidation, Mensonge, Discrétion, Perception, Armes à distance.*
6. **Cambrioleur** — Spécialiste des coffres, des alarmes et des fenêtres du troisième étage. Il prépare chaque coup pendant des semaines. Il est précis et silencieux, et il suffit d'un imprévu pour que tout parte en vrille. *Serrures & alarmes, Discrétion, Athlétisme, Perception, Pickpocket, Informatique, Mensonge, Esquive.*
7. **Escroc** — Faux héritier, faux expert, vraie arnaque. Il change de nom comme de chemise. Il est charmeur et insaisissable, et toujours poursuivi par quelqu'un qu'il a plumé. *Mensonge, Persuasion, Psychologie, Pickpocket, Réseau, Arts, Culture générale, Esquive.*
8. **Chauffeur** — Taxi de nuit, livreur ou pilote pour les braquages, il connaît chaque rue et chaque raccourci. On l'engage pour arriver vite, ou pour repartir encore plus vite. Il est imbattable au volant, et il en sait toujours trop sur ses passagers. *Conduite, Mécanique, Perception, Réseau, Esquive, Athlétisme, Mensonge, Armes à distance.*

**Le savoir et la tech**

9. **Hacker** — Il entre dans les systèmes comme d'autres entrent chez eux. Il travaille pour lui, pour un client ou pour une cause. Il est indispensable pour un coup moderne, et vulnérable dès qu'il quitte son écran. *Informatique, Investigation, Serrures & alarmes, Mensonge, Perception, Sciences, Réseau, Esquive.*
10. **Journaliste** — Reporter d'investigation, pigiste fauché ou star sur le déclin, il flaire le scandale. Son carnet d'adresses vaut de l'or, et ses ennemis aussi. Il délie les langues comme personne, et il est seul quand les menaces deviennent réelles. *Investigation, Persuasion, Psychologie, Mensonge, Culture générale, Réseau, Discrétion, Esquive.*
11. **Médecin** — Urgentiste ou chirurgien, il prend des décisions de vie ou de mort à trois heures du matin. Il garde son sang-froid quand tout le monde panique. Il est précieux partout, et il ne sait pas dire non à un blessé, même du mauvais côté. *Médecine, Sciences, Psychologie, Perception, Conduite, Persuasion, Athlétisme, Esquive.*
12. **Technicien** — Ingénieur, électricien ou mécanicien, il comprend comment les choses marchent, et comment les faire tomber en panne. Il entre partout avec une caisse à outils et un gilet orange. Il est pratique et ingénieux, et peu à l'aise avec les gens. *Mécanique, Informatique, Sciences, Perception, Serrures & alarmes, Conduite, Investigation, Combat rapproché.*

**Le pouvoir et la parole**

13. **Politicien** — Élu local ou conseiller ministériel, il manie les promesses, les dossiers et les alliances de couloir. Il connaît les gens qui décident. Il est influent et habile, et il a des casseroles plein les placards. *Persuasion, Bureaucratie, Réseau, Mensonge, Meneur, Psychologie, Culture générale, Esquive.*
14. **Chef d'entreprise** — Patron d'une start-up ou d'un groupe familial, il pense en contrats, en parts de marché et en rapports de force. L'argent lui ouvre les portes. Il est puissant dans son monde et fragile dès qu'on menace son empire. *Persuasion, Meneur, Bureaucratie, Réseau, Psychologie, Mensonge, Culture générale, Esquive.*
15. **Influenceur** — Des millions d'abonnés, une image à entretenir et des sponsors à satisfaire. Il peut mobiliser une foule avec une vidéo. Il est célèbre et persuasif, et il est surveillé en permanence. *Arts, Persuasion, Réseau, Psychologie, Mensonge, Informatique, Athlétisme, Esquive.*
16. **Étudiant** — Fac, colocation et petits boulots, il a la vie devant lui et pas un sou en poche. Il apprend vite et il connaît tout le monde. Il est curieux et adaptable, et totalement inexpérimenté quand les choses tournent mal. *Culture générale, Informatique, Sciences, Persuasion, Athlétisme, Arts, Réseau, Esquive.*

**Le terrain**

17. **Secouriste** — Pompier, ambulancier ou membre d'une équipe de montagne, il court vers le danger quand tout le monde le fuit. Il est calme dans le chaos et précieux dans une crise. Il est aussi trop humain pour laisser quelqu'un derrière, même quand il le faudrait. *Médecine, Athlétisme, Conduite, Perception, Survie, Esquive, Psychologie, Meneur.*
18. **Ancien militaire** — Revenu à la vie civile après des années d'opérations, il garde les réflexes et les cauchemars. Il fait de la sécurité privée ou des petits boulots. Il est redoutable quand ça dégénère, et il a du mal à trouver sa place ailleurs. *Armes à distance, Combat rapproché, Esquive, Athlétisme, Survie, Perception, Discrétion, Médecine.*
19. **Guide d'aventure** — Guide de haute montagne, de jungle ou de désert, il emmène les touristes là où les cartes s'arrêtent. Il sait survivre partout. Il est autonome et endurant, et il est responsable des vies des autres. *Survie, Athlétisme, Perception, Médecine, Conduite, Mécanique, Armes à distance, Meneur.*
20. **Combattant** — Boxeur, pratiquant de MMA ou ancien champion, il vit de ses poings et de sa réputation dans les salles. Il sait encaisser comme personne. Il est redoutable au contact, mais un pistolet reste plus rapide qu'un crochet. *Combat rapproché, Esquive, Athlétisme, Intimidation, Perception, Psychologie, Réseau, Médecine.*

Le Contemporain et l'Horreur se recoupent : pour une Horreur moderne, le générateur peut puiser dans les deux listes.

### Militaire

Sans magie. Le générateur adapte les parcours à l'époque : en 1944, l'opérateur de drones devient observateur d'artillerie ; dans le futur, les fantassins portent des exosquelettes.

**Au front**

1. **Fantassin** — L'épine dorsale de toute armée : il marche, il tient la position, il tire. Il sait vivre avec peu et se battre avec moins encore. C'est un combattant complet, qui a besoin d'ordres et de camarades pour donner son meilleur. *Armes à distance, Combat rapproché, Esquive, Athlétisme, Camouflage, Observation, Survie, Explosifs.*
2. **Tireur d'élite** — Il attend des heures, immobile, pour un seul tir. Une silhouette à huit cents mètres, une respiration retenue. Il est patient et mortel, et il est seul et exposé si on le repère. *Armes à distance, Camouflage, Observation, Survie, Athlétisme, Renseignement, Esquive, Transmissions.*
3. **Mitrailleur** — Il porte l'arme lourde et la caisse de munitions qui va avec. Quand il ouvre le feu, l'ennemi baisse la tête. C'est le pilier de la section en défense, et l'ennemi en fait sa première cible. *Armes à distance, Athlétisme, Esquive, Observation, Mécanique, Intimidation, Explosifs, Survie.*
4. **Commando** — Membre des forces spéciales, il frappe la nuit, loin derrière les lignes. Sabotage, raid, extraction : il fait ce que l'armée ne reconnaît pas officiellement. Il est polyvalent et redoutable, et souvent seul sans renforts. *Armes à distance, Combat rapproché, Camouflage, Athlétisme, Explosifs, Survie, Observation, Pièges & déminage.*
5. **Éclaireur** — Il part devant, voit l'ennemi en premier et revient le dire. Il connaît le terrain mieux que les cartes. Il est discret et rapide, et il est le premier à tomber dans une embuscade. *Camouflage, Observation, Survie, Athlétisme, Armes à distance, Renseignement, Conduite & pilotage, Esquive.*

**Le soutien**

6. **Transmetteur** — Les yeux et la voix de l'unité : radios, chiffrement, brouillage, écoute ennemie. Sans lui, la section est sourde et aveugle. Il est précieux et donc ciblé en priorité, et il est moins à l'aise au contact. *Transmissions, Électronique, Armes à distance, Observation, Renseignement, Camouflage, Pièges & déminage, Conduite & pilotage.*
7. **Infirmier de combat** — Il porte une trousse et un fusil, et il sait se servir des deux. Il soigne sous le feu et ramène les blessés coûte que coûte. Tout le monde l'aime, et tout le monde a besoin de lui… au même moment. *Médecine, Armes à distance, Esquive, Athlétisme, Perspicacité, Survie, Observation, Conduite & pilotage.*
8. **Sapeur** — Démineur, poseur de charges et bâtisseur de ponts sous le feu. Il ouvre la route et la referme derrière lui. Il est indispensable et méthodique, et il n'a droit qu'à une erreur. *Pièges & déminage, Explosifs, Mécanique, Observation, Athlétisme, Électronique, Armes à distance, Sciences.*
9. **Mécanicien** — Il garde les blindés, les camions et les groupes électrogènes en état de marche, avec trois clés et beaucoup de jurons. Sans lui, l'armée s'arrête. Il est ingénieux et respecté, et il est rarement entraîné au combat d'infanterie. *Mécanique, Électronique, Conduite & pilotage, Observation, Athlétisme, Armes à distance, Sciences, Survie.*
10. **Pilote** — Aux commandes d'un hélicoptère, d'un char ou d'un avion d'appui, il change le cours d'un combat en un passage. Son engin est sa force et sa prison. Il est puissant aux commandes et vulnérable une fois abattu. *Conduite & pilotage, Mécanique, Transmissions, Observation, Armes à distance, Électronique, Survie, Esquive.*
11. **Opérateur de drones** — Depuis un écran, à des kilomètres, il voit tout et frappe sans être vu. C'est la guerre moderne. Il est redoutable pour repérer et guider, et il ne sert presque à rien quand l'ennemi arrive dans la tranchée. *Électronique, Conduite & pilotage, Observation, Transmissions, Renseignement, Mécanique, Camouflage, Armes à distance.*

**Le commandement et le renseignement**

12. **Officier** — Lieutenant ou capitaine, il décide et il porte le poids de chaque décision. Il connaît la stratégie et l'histoire des batailles. Il est respecté par ses hommes, s'il les mérite, et coincé entre eux et l'état-major. *Commandement, Histoire militaire, Armes à distance, Persuasion, Perspicacité, Observation, Transmissions, Intimidation.*
13. **Sous-officier** — Le sergent qui transforme les ordres en actions et les bleus en soldats. Il gueule, il protège, il ramène ses hommes. C'est l'âme de la section, et il est usé par trop de campagnes. *Commandement, Armes à distance, Combat rapproché, Intimidation, Athlétisme, Observation, Médecine, Survie.*
14. **Officier de renseignement** — Il lit les cartes, les interceptions et les visages des prisonniers. Il sait ce que l'ennemi va faire avant lui. Il est précieux et cérébral, et il est souvent loin du terrain qu'il analyse. *Renseignement, Perspicacité, Tromperie, Persuasion, Histoire militaire, Électronique, Observation, Armes à distance.*
15. **Agent infiltré** — Il vit dans le camp ennemi sous une fausse identité, et un mot de travers le condamne. Il transmet, il sabote, il ment. C'est l'arme la plus discrète de la guerre, et la plus seule. *Tromperie, Camouflage, Renseignement, Perspicacité, Escamotage, Combat rapproché, Persuasion, Observation.*
16. **Interprète** — Recruté sur place ou formé aux langues, il fait le pont entre l'armée et les civils. Il comprend ce que disent vraiment les gens. Il est indispensable, et les deux camps le soupçonnent. *Persuasion, Perspicacité, Histoire militaire, Renseignement, Tromperie, Observation, Esquive, Médecine.*

**Autour de la guerre**

17. **Correspondant de guerre** — Appareil photo et carnet en main, il suit les troupes là où l'histoire s'écrit. Il raconte ce que les communiqués taisent. Il est courageux et témoin de tout, et il n'est pas armé. *Renseignement, Persuasion, Perspicacité, Arts, Observation, Camouflage, Esquive, Survie.*
18. **Aumônier** — Il bénit les vivants, enterre les morts et écoute ceux qui ne dorment plus. Il ne porte pas d'arme, mais il porte le moral. Il est le soutien de toute l'unité, et il porte seul le poids de ce qu'il entend. *Perspicacité, Persuasion, Médecine, Histoire militaire, Arts, Observation, Esquive, Commandement.*
19. **Contractor** — Mercenaire d'une société militaire privée, il est mieux payé et moins encadré que les soldats. Il travaille pour le contrat, pas pour le drapeau. Il est bien équipé et efficace, et personne ne pleure un contractor. *Armes à distance, Combat rapproché, Esquive, Intimidation, Observation, Conduite & pilotage, Tromperie, Survie.*
20. **Partisan** — Civil qui a pris les armes contre l'occupant, il connaît chaque ferme et chaque chemin creux. Il frappe et disparaît dans la population. Il est insaisissable et motivé, et ses proches paient ses actes. *Camouflage, Armes à distance, Explosifs, Survie, Tromperie, Observation, Escamotage, Athlétisme.*

### Science-fiction

La magie, c'est la Psionique. Un parcours marqué **(magie)** n'existe que si l'univers l'active. La Psionique respecte les interdits de 10.9 : ni lire les pensées, ni prédire l'avenir, ni contrôler un esprit. Ses domaines conseillés sont la Télékinésie (attaque, protection, utilitaire), l'Empathie (sentir et influencer les émotions, en renfort ou en entrave, sans jamais contrôler) et la Biokinésie (soin, renfort).

**L'équipage**

1. **Pilote** — As du manche, contrebandier ou ancien de la flotte, il fait voler ce qui ne devrait pas voler. Son vaisseau est sa maison et son arme. Il est génial aux commandes et se sent nu dès qu'il pose le pied au sol. *Conduite & pilotage, Astrogation, Systèmes & IA, Perception, Armes à distance, Artillerie embarquée, Esquive, Athlétisme (zéro G).*
2. **Navigateur** — Il calcule les sauts, lit les cartes stellaires et sent les anomalies avant les capteurs. Une erreur de sa part, et le vaisseau sort au cœur d'une étoile. Il est précieux et méticuleux, et il passe sa vie penché sur des équations. *Astrogation, Sciences, Systèmes & IA, Conduite & pilotage, Perception, Xénoculture, Investigation, Esquive.*
3. **Ingénieur** — Mécanicien de bord ou technicien de station, il garde le vaisseau en vie avec du ruban adhésif et du génie. Il comprend les machines mieux que les gens. Il est irremplaçable à bord, et vulnérable dès qu'il faut tirer. *Ingénierie, Systèmes & IA, Sciences, Contre-mesures, Conduite & pilotage, Investigation, Perception, Armes à distance.*
4. **Canonnier** — Aux tourelles quand le vaisseau combat, il transforme les données de visée en coups au but. Il parle aux canons comme à des animaux familiers. Il est décisif en combat spatial, et beaucoup moins dans une coursive. *Artillerie embarquée, Armes à distance, Systèmes & IA, Perception, Ingénierie, Astrogation, Athlétisme (zéro G), Esquive.*
5. **Capitaine** — Commandant d'un cargo, d'un corsaire ou d'une frégate, il répond de chaque vie à bord. Il négocie les contrats, il décide quand fuir et quand se battre. Il est respecté de son équipage, et seul avec ses choix. *Commandement, Diplomatie, Conduite & pilotage, Astrogation, Perspicacité, Armes à distance, Tromperie, Xénoculture.*
6. **Médecin de bord** — Il soigne les humains, les hybrides et parfois ce qu'il ne sait pas nommer. Son infirmerie est le cœur discret du vaisseau. Il est indispensable, et il découvre des pathologies qu'aucun manuel ne décrit. *Médecine, Sciences, Perspicacité, Xénoculture, Systèmes & IA, Diplomatie, Perception, Esquive.*

**Les armes**

7. **Marine** — Soldat d'élite des abordages et des débarquements, entraîné à se battre en apesanteur. Quand ça tourne mal sur une station, c'est lui qu'on envoie. C'est une force de frappe redoutable, disciplinée jusqu'à la rigidité. *Armes à distance, Combat rapproché, Esquive, Athlétisme (zéro G), Intimidation, Perception, Commandement, Survie.*
8. **Chasseur de primes** — Il traque les fugitifs d'un système à l'autre, pour une prime et sans poser de questions. Sa réputation le précède dans chaque spatioport. Il est tenace et efficace, et toujours une cible pour ceux qu'il a déjà livrés. *Armes à distance, Investigation, Perception, Intimidation, Conduite & pilotage, Combat rapproché, Tromperie, Survie.*
9. **Agent de sécurité** — Il garde une station, un convoi ou un cadre important, dans des coursives où un tir perdu peut percer la coque. Il connaît chaque sas et chaque protocole. Il est fiable et bien équipé, et il obéit à ceux qui le paient. *Armes à distance, Contre-mesures, Perception, Intimidation, Combat rapproché, Perspicacité, Systèmes & IA, Athlétisme (zéro G).*

**Les découvreurs**

10. **Explorateur** — Il pose le pied le premier sur les mondes que personne n'a cartographiés. Il sait survivre dans des atmosphères hostiles et parmi des faunes inconnues. Il est autonome et curieux, et toujours le premier exposé à l'inconnu. *Survie, Perception, Xénoculture, Armes à distance, Athlétisme (zéro G), Conduite & pilotage, Médecine, Sciences.*
11. **Xénobiologiste** — Scientifique des formes de vie extraterrestres, il étudie, classe et comprend. Pour lui, chaque créature est une merveille, même celle qui veut le dévorer. Il est brillant et passionné, et dangereusement curieux. *Sciences, Xénoculture, Anomalies, Investigation, Médecine, Systèmes & IA, Perception, Esquive.*
12. **Diplomate** — Ambassadeur, médiateur ou négociateur de premiers contacts, il évite les guerres avec des mots. Il connaît les coutumes de dix espèces. Il est indispensable pour la paix, et démuni quand elle échoue. *Diplomatie, Xénoculture, Perspicacité, Tromperie, Commandement, Arts, Perception, Esquive.*
13. **Chercheur d'anomalies** — Il traque les ruines d'espèces disparues et les phénomènes que la physique n'explique pas. Les universités le financent, les corpos le surveillent. Il est savant et intrépide, et certains artefacts n'auraient jamais dû être réveillés. *Anomalies, Xénoculture, Investigation, Survie, Sciences, Athlétisme (zéro G), Perception, Armes à distance.*

**L'ombre**

14. **Contrebandier** — Il fait passer ce que les douanes interdisent, d'un bout de la galaxie à l'autre. Il connaît chaque route discrète et chaque fonctionnaire corruptible. Il est débrouillard et beau parleur, et il a toujours une dette envers quelqu'un. *Conduite & pilotage, Tromperie, Diplomatie, Astrogation, Contre-mesures, Armes à distance, Escamotage, Perception.*
15. **Pirate informatique** — Il parle aux IA, trompe les systèmes de bord et vide les comptes des corpos. Dans ce monde, une IA mal protégée vaut une flotte. Il est indispensable et insaisissable, et dangereux pour tous ceux qui l'emploient. *Systèmes & IA, Contre-mesures, Investigation, Tromperie, Sciences, Perception, Discrétion, Esquive.*
16. **Espion** — Agent d'une corporation ou d'une puissance stellaire, il change d'identité comme de station. Il vole des secrets et retourne des alliés. Il est subtil et mortel, et il ne sait plus très bien pour qui il travaille. *Tromperie, Discrétion, Contre-mesures, Perspicacité, Diplomatie, Escamotage, Combat rapproché, Systèmes & IA.*

**Les gens ordinaires**

17. **Mineur d'astéroïdes** — Il fore la roche dans le vide pour un salaire de misère et une ration d'oxygène. Les « Ceinturiens » sont durs comme leur métier. Il est endurant et solidaire des siens, et en colère contre ceux qui l'exploitent. *Ingénierie, Athlétisme (zéro G), Conduite & pilotage, Survie, Perception, Sciences, Combat rapproché, Médecine.*
18. **Colon** — Pionnier d'un monde lointain, il défriche, il construit et il défend ce qu'il a bâti. Il est loin de tout et autonome par force. Il est polyvalent et courageux, et sa colonie est toujours à une catastrophe près. *Survie, Ingénierie, Médecine, Conduite & pilotage, Perception, Armes à distance, Diplomatie, Athlétisme (zéro G).*

**La Psionique**

19. **Psion (magie)** — Né avec un don que la science explique mal, il ressent les émotions et plie la matière. On le surveille, on l'exploite ou on le craint. Il est unique et puissant, et son esprit est aussi sa plus grande faiblesse. *Psionique, Perspicacité, Diplomatie, Xénoculture, Anomalies, Perception, Esquive, Médecine.* Domaines conseillés : Télékinésie, Empathie. Sans magie : remplacé par le Diplomate ou le Chercheur d'anomalies.
20. **Chevalier psi (magie)** — Membre d'un ordre ancien qui mêle le combat et la discipline de l'esprit. Il protège, il juge et il garde la paix entre les étoiles. Il est redoutable et respecté, et son ordre exige une obéissance totale. *Psionique, Combat rapproché, Esquive, Athlétisme (zéro G), Perspicacité, Perception, Diplomatie, Xénoculture.* Domaines conseillés : Télékinésie, Biokinésie. Sans magie : remplacé par le Marine.

### Post-apo

La magie y est désactivée par défaut ; activée, elle prend la forme du Psi des mutants. Un parcours marqué **(magie)** n'existe que dans ce cas. Une mutation est racontée : elle donne l'apparence, jamais de bonus chiffré.

**Survivre**

1. **Fouineur** — Pilleur de ruines, il descend là où personne ne va pour remonter ce qui fait vivre la communauté. Il connaît les pièges du monde d'avant. Débrouillard et discret, il préfère éviter les ennuis plutôt que les affronter. *Récupération, Vigilance, Discrétion, Pièges, Tech d'avant, Athlétisme, Survie, Esquive.*
2. **Pisteur** — Chasseur des terres désolées, il trouve l'eau, le gibier et les pistes des pillards. Il sait survivre seul là où d'autres meurent. Il est autonome et précis, et il a du mal avec les gens. *Survie, Armes à distance, Vigilance, Discrétion, Purification, Athlétisme, Bagarre, Médecine.*
3. **Vagabond** — Il marche depuis si longtemps qu'il a oublié d'où il vient. Il ne possède que ce qu'il porte, et il ne fait confiance qu'à son instinct. Il est increvable et imprévisible, et il est toujours de passage, nulle part chez lui. *Survie, Discrétion, Bagarre, Esquive, Flair, Chapardage, Purification, Athlétisme.*

**La violence**

4. **Pillard** — Membre d'une bande qui vit de raids sur les convois et les fermes. Il prend ce qu'il veut, parce qu'il le peut. Il est brutal et redouté, et sa bande peut se retourner contre lui au premier signe de faiblesse. *Bagarre, Armes à distance, Intimidation, Conduite, Athlétisme, Vigilance, Chapardage, Esquive.*
5. **Milicien** — Il défend les murs de sa communauté contre les pillards, les mutants et les affamés. Il connaît chaque visage du village. Il est fiable et protecteur, et prêt à tout pour les siens, même au pire. *Armes à distance, Bagarre, Vigilance, Meneur, Intimidation, Pièges, Athlétisme, Flair.*
6. **Gladiateur** — Il se bat dans les arènes des seigneurs de guerre pour de l'eau, de la gloire ou sa liberté. La foule scande son nom. Il est spectaculaire et endurci, et il est la propriété de quelqu'un. *Bagarre, Esquive, Athlétisme, Intimidation, Conteur, Vigilance, Médecine, Flair.*
7. **Chasseur de mutants** — Il traque les bêtes et les monstres nés des radiations, pour une prime ou par vengeance. Il connaît leurs habitudes et leurs faiblesses. Il est redoutable et expérimenté, et il ne fait pas toujours la différence entre un monstre et un mutant pacifique. *Armes à distance, Bagarre, Survie, Vigilance, Superstitions, Pièges, Médecine, Esquive.*

**La route**

8. **Marchand de caravane** — Il fait circuler l'eau, les munitions et les nouvelles entre des communautés qui se méfient de tout. Il est respecté parce qu'il est utile. Excellent négociateur, il est toujours sur la route, donc toujours exposé. *Marchandage, Flair, Conduite, Intimidation, Vigilance, Armes à distance, Survie, Purification.*
9. **Routier** — Pilote d'un engin bricolé, blindé et hérissé de pointes, il dévore les autoroutes mortes. Son véhicule est sa vie et son arme. Il est imbattable sur la route, et à pied, il n'est plus grand-chose. *Conduite, Bricolage, Armes à distance, Vigilance, Athlétisme, Intimidation, Survie, Esquive.*
10. **Messager** — Il porte les lettres, les traités et les colis entre des communautés que tout sépare. Il connaît les raccourcis et les zones à éviter. Il est rapide et endurant, et on le tue souvent pour ce qu'il transporte. *Athlétisme, Survie, Discrétion, Vigilance, Conduite, Marchandage, Esquive, Purification.*

**Le savoir et la tech**

11. **Bricoleur** — Il fait marcher un générateur avec des pièces de grille-pain et redonne vie aux machines d'avant. Son atelier est un trésor. Il est indispensable à toute communauté, et convoité par toutes les bandes. *Bricolage, Tech d'avant, Récupération, Conduite, Vigilance, Sciences, Bagarre, Marchandage.*
12. **Toubib** — Médecin formé sur le tas, il recoud, il ampute et il soigne avec ce qu'il trouve. On lui pardonne tout parce qu'on aura besoin de lui. Il est précieux et respecté, et il a toujours plus de patients que de médicaments. *Médecine, Purification, Sciences, Flair, Vigilance, Marchandage, Récupération, Esquive.*
13. **Archiviste** — Gardien des livres et des savoirs d'avant, il essaie de comprendre ce qu'était le monde. Il sait lire les plans, les cartes et les manuels. Il est savant et précieux, et il est souvent pris pour un sorcier. *Savoir d'avant, Tech d'avant, Sciences, Enquête, Conteur, Marchandage, Vigilance, Esquive.*
14. **Purificateur** — Il sait rendre l'eau buvable, la nourriture saine et l'air respirable. Dans ce monde, c'est plus précieux que l'or. Il est vital pour une communauté, et les seigneurs de guerre se le disputent. *Purification, Sciences, Médecine, Bricolage, Marchandage, Vigilance, Survie, Armes à distance.*

**Le pouvoir et la parole**

15. **Chef de clan** — Il dirige une communauté, une bande ou une tribu, et il porte la survie de tous. Il décide qui mange, qui se bat et qui part. Il est respecté et craint, et entouré de rivaux qui attendent son erreur. *Meneur, Intimidation, Marchandage, Flair, Armes à distance, Vigilance, Conteur, Survie.*
16. **Prêcheur** — Il annonce la fin des temps, ou un nouveau commencement, à des survivants qui ont besoin d'y croire. Ses sermons rassemblent les foules. Il est charismatique et influent, et il est dangereux quand il croit à ce qu'il prêche. *Conteur, Superstitions, Marchandage, Flair, Embrouille, Meneur, Médecine, Esquive.*
17. **Bonimenteur** — Il vend de l'eau « bénite », des remèdes miracles et des cartes vers des paradis qui n'existent pas. Il a toujours un tour d'avance. Il est charmeur et insaisissable, et il ne repasse jamais deux fois par le même village. *Embrouille, Marchandage, Chapardage, Flair, Conteur, Discrétion, Superstitions, Esquive.*
18. **Fermier** — Il cultive une terre empoisonnée et la défend contre tout ce qui a faim. Il nourrit les autres. Il est tenace et pragmatique, et ses récoltes attirent tous les prédateurs. *Survie, Purification, Bricolage, Vigilance, Armes à distance, Médecine, Marchandage, Athlétisme.*

**Les mutants**

19. **Mutant** — Né avec un corps marqué par les radiations : peau écailleuse, yeux sans pupilles, carrure démesurée. Rejeté par les communautés, il vit en marge. Il est endurant et résistant, et il est la cible de tous les préjugés. *Athlétisme, Survie, Bagarre, Intimidation, Discrétion, Vigilance, Superstitions, Purification.*
20. **Mutant psi (magie)** — Les radiations lui ont donné un don : déplacer les objets, ressentir les émotions, soigner par la pensée. Les uns le vénèrent, les autres veulent le brûler. Il est puissant et unique, et son don le consume. *Psi, Flair, Superstitions, Survie, Discrétion, Vigilance, Esquive, Intimidation.* Domaines conseillés : Télékinésie, Empathie, comme la Psionique de la science-fiction. Sans magie : remplacé par le Mutant.

## Annexe E — Implants du Cyberpunk

Des modèles, pas une liste figée (voir 11). **F** : une fondation, qui ouvre des options. Prix en SM maximum selon la gamme (voir 11.4) : 0 pour l'esthétique et le médical, 2 en standard, 4 en avancée, 6 en militaire.

### Cortex frontal — 3 emplacements, il faut un neuroport

| Implant | Effet | Gamme |
|---|---|---|
| Puce de langue | utilitaire : une langue de plus | standard |
| Mémoire eidétique | +5 Éducation | avancée |
| Puce de compétence | +5 à une compétence de savoir, choisie à l'installation | avancée |
| Coprocesseur tactique | +5 Vigilance | avancée |
| Extension de mémoire vive | +5 Piratage | avancée |

### Système d'exploitation — un seul implant

| Implant | Effet | Gamme |
|---|---|---|
| Deck neural | utilitaire : pirater sans deck externe | standard |
| Deck militaire | +10 Piratage | militaire |
| Sandevistan | +10 Esquive | militaire |
| Berserk | +10 Combat rapproché | militaire |

### Système nerveux — 2 emplacements

| Implant | Effet | Gamme |
|---|---|---|
| **F** Neuroport | utilitaire : se brancher à une machine ; ouvre le cortex frontal | standard |
| Inhibiteur de douleur | utilitaire : rester lucide sous la torture | standard |
| Réflexes câblés Kerenzikov | +5 Esquive | avancée |
| Synapses accélérées | +5 Vigilance | avancée |

### Visage et yeux — fondation : les yeux cybernétiques, 3 options

| Implant | Effet | Gamme |
|---|---|---|
| **F** Yeux cybernétiques | utilitaire : zoom, mise au point instantanée | standard |
| Vision nocturne | utilitaire : voir dans le noir | standard |
| Vision thermique | utilitaire : voir les sources de chaleur, même derrière la fumée | standard |
| Caméra oculaire | utilitaire : enregistrer ce que l'on voit | standard |
| Scanner d'implants | +5 Cybernétique | avancée |
| Viseur balistique | +5 Armes à distance | avancée |
| Optiques Kiroshi | +10 Armes à distance | militaire |
| Visage malléable | +10 Arnaque (changer de traits) | militaire |

### Oreilles et gorge — fondation : la suite cyberaudio, 3 options

| Implant | Effet | Gamme |
|---|---|---|
| **F** Suite cyberaudio | utilitaire : radio et téléphone internes | standard |
| Filtre respiratoire | utilitaire : respirer la fumée, les gaz, l'air pollué | standard |
| Audio amplifié | +5 Vigilance | avancée |
| Analyseur de stress vocal | +5 Empathie | avancée |
| Détecteur de micros | +5 Contre-mesures | avancée |
| Modulateur vocal | +5 Arnaque | avancée |

### Peau — 2 emplacements, plus l'esthétique à volonté

| Implant | Effet | Gamme |
|---|---|---|
| Tatouages lumineux, cheveux de fibre optique, peau chromée | esthétique | standard |
| Peau dermique | armure, protection 2 | standard |
| Glandes à phéromones | +5 Négociation | avancée |
| Peau caméléon | +10 Infiltration | militaire |

### Squelette — 2 emplacements

| Implant | Effet | Gamme |
|---|---|---|
| Ossature blindée | armure, protection 3, Infiltration −10 | standard |
| Os en titane | +5 Athlétisme | avancée |

### Organes internes — 3 emplacements

| Implant | Effet | Gamme |
|---|---|---|
| Biomoniteur | utilitaire : alerte sur son état de santé | standard |
| Poumons renforcés | utilitaire : apnée prolongée | standard |
| Filtre toxique | utilitaire : résister aux poisons et aux drogues | standard |
| Compartiment caché | utilitaire : cacher un petit objet | standard |

### Bras — fondation : le bras cybernétique (par bras), 3 options

| Implant | Effet | Gamme |
|---|---|---|
| **F** Bras cybernétique | utilitaire : un bras qui ne fatigue pas | standard |
| Pistolet intégré | arme : 1d6, portée courte, 4 coups, recharge simple, dissimulable | standard |
| Lames-mantis | arme : 1d8, dissimulable | standard |
| Fouet monofilament | arme : 1d8, perforante | standard |
| Bras-marteau | arme : 1d10, encombrante | standard |
| Lance-grappin | utilitaire : grimper, se hisser, saisir à distance | standard |
| Servomoteurs | +5 Athlétisme | avancée |

### Mains — 1 emplacement par main

| Implant | Effet | Gamme |
|---|---|---|
| Griffes-rasoirs | arme : 1d4, dissimulable | standard |
| Paume d'interface | utilitaire : se brancher sans câble | standard |
| Poigne magnétique | utilitaire : s'accrocher au métal | standard |
| Doigts-outils | +5 Bricolage tech | avancée |
| Doigts de crochetage | +5 Contre-mesures | avancée |
| Doigts de pickpocket | +5 Doigts agiles | avancée |

### Jambes — fondation : les jambes cybernétiques (la paire), 2 options

| Implant | Effet | Gamme |
|---|---|---|
| **F** Jambes cybernétiques | utilitaire : marcher des jours sans fatigue | standard |
| Compartiment de jambe | utilitaire : cacher une arme ou un objet | standard |
| Amortisseurs silencieux | +5 Infiltration | avancée |
| Chevilles à ressorts | +10 Athlétisme | militaire |

### Médical — n'importe quel membre

| Implant | Effet | Gamme |
|---|---|---|
| Prothèse médicale | remplace un membre perdu, sans option ni bonus | standard |

## Annexe F — Armureries par genre

Des modèles, pas une liste figée : le générateur les adapte au cadre. Toutes respectent les bornes de 7.5. Les objets marqués « (implant) » existent aussi comme implants (annexe E).

### Cyberpunk

**Mêlée — Combat rapproché, portée contact**

| Arme | Dégâts | Propriétés |
|---|---|---|
| Poing américain | 1d4 | dissimulable |
| Couteau | 1d4 | dissimulable |
| Griffes-rasoirs (implant) | 1d4 | dissimulable |
| Tantō | 1d6 | dissimulable |
| Matraque télescopique | 1d6 | dissimulable |
| Tonfa | 1d6 | |
| Batte de baseball | 1d6 | fragile |
| Matraque électrique | 1d6 | |
| Hachette | 1d6 | lancer |
| Machette | 1d8 | |
| Wakizashi | 1d8 | |
| Lames-mantis (implant) | 1d8 | dissimulable |
| Katana | 1d10 | |
| Bras-marteau (implant) | 1d10 | encombrante |
| Nodachi | 1d12 | deux mains |
| Marteau lourd | 1d12 | deux mains, encombrante |
| Naginata électrique | 1d12 | deux mains |
| Tronçonneuse | 2d6 | deux mains, encombrante, fragile |

**Lancer**

| Arme | Dégâts | Portée | Propriétés |
|---|---|---|---|
| Shuriken | 1d4 | courte | lancer, dissimulable |
| Couteaux de lancer | 1d4 | courte | lancer, dissimulable |
| Kunai | 1d4 | courte | lancer, dissimulable, silencieuse |

**Armes à distance**

| Arme | Dégâts | Portée | Munitions | Propriétés |
|---|---|---|---|---|
| Pistolet compact | 1d4 | courte | 6, mineure | dissimulable |
| Pistolet léger | 1d6 | courte | 12, mineure | dissimulable |
| Pistolet silencieux | 1d6 | courte | 10, mineure | dissimulable, silencieuse |
| Mitraillette compacte | 1d6 | courte | 20, mineure | rafale, dissimulable |
| Pistolet intelligent | 1d8 | courte | 10, mineure | dissimulable |
| Pistolet-mitrailleur | 1d8 | courte | 30, mineure | rafale |
| Arbalète à poulies | 1d8 | moyenne | 1, simple | deux mains, silencieuse |
| Pistolet lourd | 1d10 | courte | 8, mineure | dissimulable |
| Revolver lourd | 1d10 | courte | 6, simple | |
| Carabine | 2d6 | moyenne | 20, mineure | deux mains |
| Fusil à pompe | 2d6 | courte | 6, simple | deux mains |
| Fusil à pompe automatique | 2d6 | courte | 10, mineure | deux mains, rafale, encombrante |
| Mitrailleuse légère | 2d6+1 | longue | 100, simple | deux mains, rafale, encombrante |
| Fusil d'assaut | 2d6+2 | longue | 30, mineure | deux mains, rafale |
| Fusil de précision | 2d6+2 | longue | 5, simple | deux mains, perforante, encombrante |
| Fusil à rail | 2d6+2 | moyenne | 4, simple | deux mains, perforante, encombrante |

**Armures**

| Armure | Protection | Malus |
|---|---|---|
| Veste renforcée | 1 | — |
| Combinaison de motard | 1 | — |
| Gilet pare-balles léger | 2 | — |
| Manteau blindé | 2 | — |
| Peau dermique (implant) | 2 | — |
| Gilet balistique | 3 | Infiltration −10 |
| Armure de garde corpo | 3 | Infiltration −10, Esquive −10 |
| Ossature blindée (implant) | 3 | Infiltration −10 |
| Armure tactique | 4 | Infiltration −20, Athlétisme −10 |
| Exosquelette léger | 4 | Infiltration −10, Esquive −10 |

**Les marques : exemples de qualité**

| Objet | Qualité | Bonus de ses modifications |
|---|---|---|
| Pistolet lourd Arasaka | personnalisé | +1 aux dégâts, recharge mineure (rechargeur rapide, nouveau calibre) |
| Fusil d'assaut Militech « Ronin » | personnalisé | +5 au jet, +1 aux dégâts (viseur holographique, nouveau calibre) |
| Couteau en céramique | personnalisé | +5 au jet (équilibrage) |
| Pistolet intelligent Kang Tao « Kenshin » | personnalisé | +10 au jet (viseur holographique, pointeur laser) |
| Katana monomoléculaire | personnalisé | +2 aux dégâts (fil monomoléculaire, gaine thermique) |
| Gilet balistique Militech | personnalisé | +1 de protection, 5 points de malus en moins |
| Armure tactique Arasaka | personnalisé | +1 de protection, 5 points de malus en moins |
| Fusil à rail Militech « Breakthrough » | unique | +10 au jet, +1 aux dégâts (nouveau calibre, viseur, pointeur laser) |
| Fusil de précision Tsunami « Nekomata » | unique | +10 au jet, silencieuse (pointeur laser, viseur, silencieux) |

**Les modifications**

Armes à distance :

| Modification | Effet |
|---|---|
| Viseur holographique | +5 au jet |
| Pointeur laser | +5 au jet |
| Nouveau calibre | +1 aux dégâts |
| Munitions perforantes | la propriété perforante |
| Silencieux | la propriété silencieuse |
| Canon raccourci | la propriété dissimulable (pas sur une arme à deux mains) |
| Chargeur grande capacité | munitions doublées |
| Rechargeur rapide | une recharge simple devient mineure |
| Lampe tactique | utilitaire : éclairer sans lâcher son arme |
| Blindage IEM | utilitaire : l'arme intelligente ou l'objet électronique résiste aux IEM (aussi sur un drone, un deck, un téléphone…) |

Armes de mêlée :

| Modification | Effet |
|---|---|
| Équilibrage | +5 au jet |
| Poignée ergonomique | +5 au jet |
| Fil monomoléculaire | +1 aux dégâts |
| Gaine thermique | +1 aux dégâts |
| Lame rétractable | la propriété dissimulable |

Armures :

| Modification | Effet |
|---|---|
| Plaques de renfort | +1 de protection |
| Doublure souple | 5 points de malus en moins |
| Revêtement furtif | 5 points de malus en moins, seulement en Infiltration |
| Poches tactiques | utilitaire : tout à portée de main |
| Isolation thermique | utilitaire : supporter le froid et le feu ambiant |

Implants (1 point de Santé mentale maximum chacune) :

| Modification | Effet |
|---|---|
| Calibrage fin | +5 au bonus de l'implant (plafond +10) |
| Pare-feu | utilitaire : l'implant résiste au piratage |
| Blindage IEM | utilitaire : l'implant résiste aux impulsions électromagnétiques |
| Gaine discrète | utilitaire : l'implant échappe aux scanners |

Les implants-armes (lames-mantis, griffes-rasoirs…) prennent aussi les modifications de mêlée ou de tir.

**Les modifications de véhicules**

| Modification | Effet |
|---|---|
| Reprogrammation moteur | Moteur : +1 cran de vitesse |
| Turbo | Moteur : +1 cran de vitesse |
| Suspensions sport | Châssis : +5 de maniabilité |
| Direction assistée IA | Châssis : +5 de maniabilité |
| Châssis renforcé | Renfort : +5 de structure |
| Pare-buffle | Renfort : +5 de structure |
| Plaques de blindage | Blindage : +1 |
| Vitrage pare-balles | Blindage : +1 |
| Pneus tout-terrain | Propriété : tout-terrain |
| Moteur électrique silencieux | Propriété : discret |
| Coffre agrandi | Propriété : cargo |
| Tourelle télécommandée | Support d'arme |
| Kit nitro | Nitro |
| Pilote automatique | Utilitaire : le véhicule roule seul jusqu'à une adresse |
| GPS piraté | Utilitaire : invisible pour les contrôles de la NeoPol |
| Compartiment secret | Utilitaire : cacher des armes ou un passager |

**Les armes de zone** (voir 7.9)

| Arme | Dégâts | Zone | Portée | Munitions | Propriétés | Genres |
|---|---|---|---|---|---|---|
| Grenade à fragmentation | 3d6 | petite | courte | usage unique | lancer | moderne |
| Grenade incendiaire | 2d6 | petite | courte | usage unique | lancer, brûlure | moderne |
| Grenade fumigène | — | petite | courte | usage unique | lancer, fumée | moderne |
| Grenade flash | — | petite | courte | usage unique | lancer, aveuglant | moderne |
| Grenade IEM | — | petite | courte | usage unique | lancer, IEM | futuriste |
| Lance-grenades | 3d6 | petite | moyenne | 6, recharge simple | deux mains | moderne |
| Lance-flammes | 2d6 | petite | courte | 3, recharge simple | deux mains, brûlure | moderne |
| Lance-roquettes | 4d6 | moyenne | longue | 1, recharge simple | deux mains, perforante, encombrante | moderne |
| Charge d'explosif | 4d6 | grande | contact (posée) | usage unique | — | moderne |
| Canon de char | 4d6 | moyenne | longue | arme montée | perforante | Militaire, Cyberpunk |
| Mine IEM | — | moyenne | contact (posée) | usage unique | IEM | futuriste |
| Charge IEM lourde | — | grande | contact (posée) | usage unique | IEM | futuriste, Militaire |

**Les armes lourdes montées** (voir 12.7)

| Arme | Dégâts | Portée | Munitions | Propriétés | Genres |
|---|---|---|---|---|---|
| Mitrailleuse lourde | 3d6 | longue | 100 | rafale, perforante | moderne |
| Canon automatique | 3d6 | longue | 30 | perforante | moderne |
| Minigun | 2d6+2 | moyenne | 200 | rafale | moderne |

**Les fabricants**

| Fabricant | Catégories | Modification d'usine | Réputation |
|---|---|---|---|
| Arasaka | armes de poing, armures, AV | rechargeur rapide (armes), plaques de renfort (armures), plaques de blindage (AV) | Luxe et fiabilité ; la rue la hait, la police la respecte |
| Militech | fusils, armes lourdes, armures, véhicules militaires | nouveau calibre (armes), plaques de renfort (armures), plaques de blindage (véhicules) | La puissance brute, l'armée, les mercenaires |
| Kang Tao | armes intelligentes, armes de poing | viseur holographique | La high-tech chinoise ; les netrunners adorent |
| Tsunami | fusils de précision | pointeur laser | L'élégance japonaise, à un prix exorbitant |
| Budget Arms | armes de poing, fusils | aucune : l'arme sort usée | L'arme des gangers fauchés |
| Kiroshi | implants optiques | calibrage fin | La référence des yeux cybernétiques |
| Zetatech | implants neuro, decks | pare-feu | Le cerveau des netrunners |
| Biotechnica | implants de peau, organes internes | gaine discrète | Le biotech qui ne se voit pas |
| Yaiba | motos | reprogrammation moteur | La moto des coursiers qui se respectent |
| Quadra | voitures de sport | turbo | Le muscle américain |
| Rayfield | voitures de luxe | vitrage pare-balles | La voiture des cadres corpo |
| Thorton | pick-ups, utilitaires | pneus tout-terrain | Le robuste, le pratique ; les nomades |
| Delamain | taxis automatiques | pilote automatique | Le taxi intelligent qui ne pose pas de questions |

### Fantasy

**Les modifications des montures** (aussi en Dark fantasy)

| Modification | Effet |
|---|---|
| Fers de course | Moteur : +1 cran de vitesse |
| Dressage de guerre | Châssis : +5 de maniabilité, et elle panique moins vite |
| Barde de cuir | Blindage : +1 |
| Caparaçon renforcé | Renfort : +5 de structure |
| Selle de bât | Propriété : cargo |
| Fers étouffés | Propriété : discret |

## Annexe G — Véhicules

Une vue de la bibliothèque (voir 1.3). *Moderne* : Contemporain, Horreur, Militaire, Cyberpunk, Post-apo ; *futuriste* : Cyberpunk, Science-fiction. Tous sont d'origine ; les modèles de marque montrent ce que donnent les modifications (voir 12.6).

**Légers**

| Véhicule | Type | Vitesse | Maniab. | Structure | Blindage | Places | Propriétés | Genres |
|---|---|---|---|---|---|---|---|---|
| Scooter électrique | terrestre | moyenne | +10 | 12 | 0 | 2 | discret | moderne |
| Moto de livraison | terrestre | rapide | +10 | 15 | 0 | 2 | cargo | moderne |
| Moto sportive | terrestre | très rapide | +10 | 15 | 1 | 2 | — | moderne |
| Moto lourde | terrestre | rapide | 0 | 20 | 2 | 2 | — | moderne |
| Jet-ski | nautique | très rapide | +10 | 10 | 0 | 2 | — | moderne |

**Moyens**

| Véhicule | Type | Vitesse | Maniab. | Structure | Blindage | Places | Propriétés | Genres |
|---|---|---|---|---|---|---|---|---|
| Citadine | terrestre | moyenne | +10 | 20 | 2 | 4 | — | moderne |
| Berline | terrestre | rapide | 0 | 30 | 3 | 5 | — | moderne |
| Voiture de sport | terrestre | rapide | +10 | 25 | 2 | 2 | — | moderne |
| Pick-up | terrestre | rapide | 0 | 35 | 3 | 3 | tout-terrain, cargo | moderne |
| Voiture de patrouille | terrestre | rapide | 0 | 35 | 4 | 4 | — | moderne |
| Vedette | nautique | rapide | 0 | 30 | 3 | 6 | — | moderne |
| Taxi automatique | terrestre | moyenne | 0 | 25 | 2 | 4 | pilote automatique | futuriste |
| Hovercar | aérien | rapide | 0 | 30 | 2 | 4 | — | futuriste |
| Fourgon de netrunner | terrestre | moyenne | −10 | 35 | 3 | 3 | baie à drones (2 drones brouilleurs) ; poste de piratage embarqué (utilitaire) | futuriste |

**Lourds**

| Véhicule | Type | Vitesse | Maniab. | Structure | Blindage | Places | Propriétés | Genres |
|---|---|---|---|---|---|---|---|---|
| Fourgon | terrestre | moyenne | −10 | 45 | 4 | 3 | cargo | moderne |
| Bus | terrestre | lente | −10 | 55 | 4 | 40 | — | moderne |
| Camion | terrestre | lente | −10 | 60 | 6 | 2 | cargo | moderne |
| Blindé de transport | terrestre | moyenne | −10 | 60 | 8 | 8 | tout-terrain ; tourelles lourdes : mitrailleuse lourde, lance-grenades ; lance-fumigènes | moderne |
| Blindé de reconnaissance | terrestre | rapide | 0 | 50 | 6 | 4 | tout-terrain ; tourelle légère : mitrailleuse légère ; baie à drones (2 drones de reconnaissance) ; lance-fumigènes | moderne |
| AV de corpo | aérien | très rapide | 0 | 50 | 6 | 6 | tourelles lourdes : minigun, lance-roquettes | Cyberpunk |

**Militaires**

| Véhicule | Type | Vitesse | Maniab. | Structure | Blindage | Places | Propriétés | Genres |
|---|---|---|---|---|---|---|---|---|
| AV d'assaut | aérien | très rapide | 0 | 80 | 10 | 4 | tourelles lourdes : canon automatique, lance-roquettes ; tourelle légère : mitrailleuse légère ; leurres | Militaire, Cyberpunk |
| Char | terrestre | lente | −10 | 100 | 12 | 3 | tout-terrain ; tourelles lourdes : canon de char, mitrailleuse lourde ; tourelle légère : mitrailleuse légère ; lance-fumigènes | Militaire, Cyberpunk |

**Drones** (voir 12.7)

| Drone | Vitesse | Structure | Blindage | Effet | Genres |
|---|---|---|---|---|---|
| Drone de reconnaissance | très rapide | 5 | 0 | utilitaire : voir à distance, repérer les embuscades | futuriste, Militaire |
| Drone de combat | rapide | 10 | 1 | arme montée : pistolet-mitrailleur | futuriste, Militaire |
| Drone kamikaze | très rapide | 5 | 0 | il explose : 3d6 sur une petite zone, usage unique | futuriste, Militaire |
| Drone brouilleur | rapide | 8 | 1 | une IEM sur une petite zone, une fois par scène | futuriste |
| Drone de livraison | rapide | 5 | 0 | utilitaire : transporter un petit objet | futuriste, Contemporain |

**Les modèles de marque : exemples de qualité**

| Véhicule | Qualité | Modifications |
|---|---|---|
| Moto lourde Yaiba « Kusanagi » | personnalisé | reprogrammation moteur (très rapide), kit nitro |
| Voiture de sport Quadra « Turbo-R » | personnalisé | turbo (très rapide), suspensions sport |
| Berline Rayfield blindée | personnalisé | vitrage pare-balles, plaques de blindage |
| AV Arasaka « Aquila » | unique | plaques de blindage, direction assistée IA, tourelle télécommandée |

---

## Annexe H — Prix du Cyberpunk

Une vue générée par le moteur (`python -m aria.economie`) : les prix sont calculés depuis la bibliothèque (voir 13.3), jamais écrits ici à la main. Un objet « militaire » ne se vend pas : on le gagne ou on le trouve.

**Armes**

| Objet | Prix | Disponibilité |
|---|---|---|
| Couteaux de lancer | 20 | courant |
| Grenade IEM | 20 | restreint |
| Grenade flash | 20 | restreint |
| Grenade fumigène | 20 | restreint |
| Kunai | 20 | courant |
| Shuriken | 20 | courant |
| Charge IEM lourde | 50 | militaire |
| Couteau | 50 | courant |
| Impulsion IEM de drone | 50 | militaire |
| Mine IEM | 50 | militaire |
| Poing américain | 50 | courant |
| Batte de baseball | 100 | courant |
| Grenade incendiaire | 100 | restreint |
| Hachette | 100 | courant |
| Matraque télescopique | 100 | courant |
| Matraque électrique | 100 | courant |
| Tantō | 100 | courant |
| Tonfa | 100 | courant |
| Grenade à fragmentation | 200 | restreint |
| Katana | 200 | courant |
| Machette | 200 | courant |
| Marteau lourd | 200 | courant |
| Naginata électrique | 200 | courant |
| Nodachi | 200 | courant |
| Pistolet compact | 200 | courant |
| Tronçonneuse | 200 | courant |
| Wakizashi | 200 | courant |
| Charge de drone kamikaze | 500 | militaire |
| Couteau en céramique | 500 | courant |
| Mitraillette compacte | 500 | restreint |
| Pistolet léger | 500 | courant |
| Pistolet silencieux | 500 | restreint |
| Arbalète à poulies | 1 000 | courant |
| Carabine | 1 000 | courant |
| Charge d'explosif | 1 000 | militaire |
| Fusil à pompe | 1 000 | courant |
| Fusil à pompe automatique | 1 000 | restreint |
| Katana monomoléculaire | 1 000 | courant |
| Pistolet lourd | 1 000 | courant |
| Pistolet-mitrailleur | 1 000 | restreint |
| Revolver lourd | 1 000 | courant |
| Fusil d'assaut | 2 000 | restreint |
| Pistolet intelligent | 2 000 | restreint |
| Pistolet lourd Arasaka | 2 000 | courant |
| Fusil d'assaut Militech « Ronin » | 5 000 | restreint |
| Fusil de précision | 5 000 | restreint |
| Fusil à rail | 5 000 | restreint |
| Lance-flammes | 5 000 | militaire |
| Mitrailleuse légère | 5 000 | militaire |
| Pistolet intelligent Kang Tao « Kenshin » | 5 000 | restreint |
| Lance-grenades | 10 000 | militaire |
| Minigun | 10 000 | militaire |
| Canon automatique | 20 000 | militaire |
| Canon de char | 20 000 | militaire |
| Fusil à rail Militech « Breakthrough » | 20 000 | militaire |
| Lance-roquettes | 20 000 | militaire |
| Mitrailleuse lourde | 20 000 | militaire |
| Fusil de précision Tsunami « Nekomata » | 50 000 | militaire |

**Armures**

| Objet | Prix | Disponibilité |
|---|---|---|
| Combinaison de motard | 200 | courant |
| Veste renforcée | 200 | courant |
| Gilet pare-balles léger | 1 000 | courant |
| Manteau blindé | 1 000 | courant |
| Armure de garde corpo | 2 000 | restreint |
| Gilet balistique | 2 000 | restreint |
| Armure tactique | 5 000 | restreint |
| Exosquelette léger | 5 000 | restreint |
| Gilet balistique Militech | 5 000 | restreint |
| Armure tactique Arasaka | 10 000 | restreint |

**Implants**

| Objet | Prix | Disponibilité |
|---|---|---|
| Cheveux de fibre optique | 500 | courant |
| Peau chromée | 500 | courant |
| Prothèse médicale | 500 | courant |
| Tatouages lumineux | 500 | courant |
| Biomoniteur | 2 000 | courant |
| Bras cybernétique | 2 000 | courant |
| Bras-marteau | 2 000 | courant |
| Caméra oculaire | 2 000 | courant |
| Compartiment caché | 2 000 | courant |
| Compartiment de jambe | 2 000 | courant |
| Deck neural | 2 000 | courant |
| Filtre respiratoire | 2 000 | courant |
| Filtre toxique | 2 000 | courant |
| Fouet monofilament | 2 000 | courant |
| Griffes-rasoirs | 2 000 | courant |
| Inhibiteur de douleur | 2 000 | courant |
| Jambes cybernétiques | 2 000 | courant |
| Lames-mantis | 2 000 | courant |
| Lance-grappin | 2 000 | courant |
| Neuroport | 2 000 | courant |
| Ossature blindée | 2 000 | courant |
| Paume d'interface | 2 000 | courant |
| Peau dermique | 2 000 | courant |
| Pistolet intégré | 2 000 | courant |
| Poigne magnétique | 2 000 | courant |
| Poumons renforcés | 2 000 | courant |
| Puce de langue | 2 000 | courant |
| Suite cyberaudio | 2 000 | courant |
| Vision nocturne | 2 000 | courant |
| Vision thermique | 2 000 | courant |
| Yeux cybernétiques | 2 000 | courant |
| Amortisseurs silencieux | 10 000 | restreint |
| Analyseur de stress vocal | 10 000 | restreint |
| Audio amplifié | 10 000 | restreint |
| Coprocesseur tactique | 10 000 | restreint |
| Doigts de crochetage | 10 000 | restreint |
| Doigts de pickpocket | 10 000 | restreint |
| Doigts-outils | 10 000 | restreint |
| Détecteur de micros | 10 000 | restreint |
| Extension de mémoire vive | 10 000 | restreint |
| Glandes à phéromones | 10 000 | restreint |
| Modulateur vocal | 10 000 | restreint |
| Mémoire eidétique | 10 000 | restreint |
| Os en titane | 10 000 | restreint |
| Puce de compétence | 10 000 | restreint |
| Réflexes câblés Kerenzikov | 10 000 | restreint |
| Scanner d'implants | 10 000 | restreint |
| Servomoteurs | 10 000 | restreint |
| Synapses accélérées | 10 000 | restreint |
| Viseur balistique | 10 000 | restreint |
| Berserk | 50 000 | militaire |
| Chevilles à ressorts | 50 000 | militaire |
| Deck militaire | 50 000 | militaire |
| Optiques Kiroshi | 50 000 | militaire |
| Peau caméléon | 50 000 | militaire |
| Sandevistan | 50 000 | militaire |
| Visage malléable | 50 000 | militaire |

**Véhicules**

| Objet | Prix | Disponibilité |
|---|---|---|
| Cheval | 2 000 | courant |
| Drone brouilleur | 2 000 | courant |
| Drone de livraison | 2 000 | courant |
| Drone de combat | 5 000 | militaire |
| Drone de reconnaissance | 5 000 | courant |
| Drone kamikaze | 5 000 | courant |
| Moto de livraison | 5 000 | courant |
| Scooter électrique | 5 000 | courant |
| Jet-ski | 10 000 | courant |
| Moto lourde | 10 000 | courant |
| Moto sportive | 10 000 | courant |
| Citadine | 20 000 | courant |
| Fourgon de netrunner | 20 000 | courant |
| Moto Yaiba « Kusanagi » | 20 000 | courant |
| Taxi automatique | 20 000 | courant |
| Berline | 50 000 | courant |
| Bus | 50 000 | courant |
| Camion | 50 000 | courant |
| Fourgon | 50 000 | courant |
| Pick-up | 50 000 | courant |
| Quadra « Turbo-R » | 50 000 | courant |
| Vedette | 50 000 | courant |
| Voiture de patrouille | 50 000 | courant |
| Berline Rayfield blindée | 100 000 | courant |
| Blindé de reconnaissance | 100 000 | militaire |
| Blindé de transport | 100 000 | militaire |
| Voiture de sport | 100 000 | courant |
| AV de corpo | 200 000 | militaire |
| Hovercar | 200 000 | courant |
| Char | 1 000 000 | militaire |
| AV Arasaka « Aquila » | 2 000 000 | militaire |
| AV d'assaut | 2 000 000 | militaire |
