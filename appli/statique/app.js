"use strict";

// --- Appels à l'API : le cookie du jeton part tout seul avec chaque requête de la même origine ---
async function api(chemin, options) {
  const reponse = await fetch(chemin, options);
  if (!reponse.ok) {
    let detail = "";
    try { detail = (await reponse.json()).detail; } catch (_) { /* pas de JSON */ }
    throw new Error(detail || `Erreur ${reponse.status}`);
  }
  return reponse.json();
}

// --- Le fond animé : règles d'appli/fond.py ---
// Coupé : fond.actif faux, ou le système demande moins d'animations. En pause : la page est cachée.
// Motif d'Aria JDR : des d20 (contour d'un hexagone, triangle au centre) traversent la zone de gauche à droite en
// roulant sur eux-mêmes, à une hauteur, une taille et un départ tirés au hasard à chaque passage.
const Fond = (() => {
  const toile = document.getElementById("fond");
  const dessin = toile.getContext("2d");
  const couleurs = ["#7df9ff", "#5c8bff"];
  const reduit = window.matchMedia("(prefers-reduced-motion: reduce)");
  let reglage = { actif: true, duree: 7, minimum: 2, maximum: 5 };
  let points = [];
  let debut = 0;
  let cadre = 0;

  function taille() {
    toile.width = toile.clientWidth * devicePixelRatio;
    toile.height = toile.clientHeight * devicePixelRatio;
    dessin.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  }

  function nouveauPassage(maintenant) {
    const nombre = reglage.minimum + Math.floor(Math.random() * (reglage.maximum - reglage.minimum + 1));
    points = Array.from({ length: nombre }, () => {
      const trajet = reglage.duree * (0.6 + 0.4 * Math.random());
      return {
        y: 40 + Math.random() * Math.max(0, toile.clientHeight - 80),
        rayon: 10 + Math.random() * 8,
        tours: (Math.random() < 0.5 ? -1 : 1) * (1 + Math.random() * 2),
        couleur: couleurs[Math.floor(Math.random() * couleurs.length)],
        depart: (reglage.duree - trajet) * Math.random(),
        trajet,
      };
    });
    debut = maintenant;
  }

  // Un d20 vu de face : l'hexagone, le triangle central, et ses arêtes vers l'hexagone
  function d20(x, y, r, angle) {
    const sommet = (rayon, degres) => {
      const a = angle + (degres * Math.PI) / 180;
      return [x + rayon * Math.cos(a), y + rayon * Math.sin(a)];
    };
    const hexagone = [-90, -30, 30, 90, 150, 210].map((d) => sommet(r, d));
    const triangle = [-90, 30, 150].map((d) => sommet(r * 0.52, d));
    dessin.beginPath();
    hexagone.forEach(([a, b], i) => (i ? dessin.lineTo(a, b) : dessin.moveTo(a, b)));
    dessin.closePath();
    triangle.forEach(([a, b], i) => (i ? dessin.lineTo(a, b) : dessin.moveTo(a, b)));
    dessin.closePath();
    // Chaque sommet du triangle rejoint le sommet de l'hexagone dans sa direction et ses deux voisins de face
    const liens = [[0, 0], [0, 1], [0, 5], [1, 2], [1, 1], [1, 3], [2, 4], [2, 3], [2, 5]];
    for (const [t, h] of liens) {
      dessin.moveTo(...triangle[t]);
      dessin.lineTo(...hexagone[h]);
    }
    dessin.stroke();
  }

  function image(maintenant) {
    cadre = 0;
    if (!reglage.actif || reduit.matches || document.hidden) return;
    const ecoule = (maintenant - debut) / 1000;
    if (ecoule >= reglage.duree) nouveauPassage(maintenant);
    dessin.clearRect(0, 0, toile.clientWidth, toile.clientHeight);
    for (const p of points) {
      const t = (ecoule - p.depart) / p.trajet;
      if (t < 0 || t > 1) continue;
      const x = -p.rayon + t * (toile.clientWidth + 2 * p.rayon);
      dessin.globalAlpha = 0.55 * Math.min(1, t * 6, (1 - t) * 6);
      dessin.shadowColor = p.couleur;
      dessin.shadowBlur = 10;
      dessin.strokeStyle = p.couleur;
      dessin.lineWidth = 1.6;
      d20(x, p.y, p.rayon, t * p.tours * 2 * Math.PI);
    }
    cadre = requestAnimationFrame(image);
  }

  function relancer() {
    cancelAnimationFrame(cadre);
    dessin.clearRect(0, 0, toile.clientWidth, toile.clientHeight);
    if (reglage.actif && !reduit.matches && !document.hidden) {
      nouveauPassage(performance.now());
      cadre = requestAnimationFrame(image);
    }
  }

  window.addEventListener("resize", () => { taille(); relancer(); });
  document.addEventListener("visibilitychange", relancer);  // pause quand la page est cachée, reprise au retour
  reduit.addEventListener("change", relancer);
  taille();

  return { configurer(nouveau) { reglage = nouveau; relancer(); } };
})();

// --- Réglages ---
const champ = (id) => document.getElementById(id);
const message = champ("message");

function afficher(reglages) {
  champ("fond-actif").checked = reglages.fond.actif;
  champ("fond-vitesse").value = reglages.fond.vitesse;
  champ("fond-minimum").value = reglages.fond.minimum;
  champ("fond-maximum").value = reglages.fond.maximum;
}

champ("formulaire").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  message.className = "";
  try {
    const enregistres = await api("/api/reglages", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fond: {
          actif: champ("fond-actif").checked,
          vitesse: champ("fond-vitesse").value,
          minimum: Number(champ("fond-minimum").value),
          maximum: Number(champ("fond-maximum").value),
        },
      }),
    });
    afficher(enregistres);
    Fond.configurer(await api("/api/fond"));
    message.textContent = "Réglages enregistrés.";
  } catch (erreur) {
    message.className = "erreur";
    message.textContent = erreur.message;
  }
});

champ("quitter").addEventListener("click", async () => {
  try {
    await api("/api/quitter", { method: "POST" });
    document.body.innerHTML = "<p class='arret'>L'appli est arrêtée. Tu peux fermer cet onglet.</p>";
  } catch (erreur) {
    message.className = "erreur";
    message.textContent = erreur.message;
  }
});

// --- Menu : la section affichée suit l'ancre ---
function section() {
  const cible = location.hash || "#accueil";
  for (const lien of document.querySelectorAll(".menu nav a")) lien.classList.toggle("actif", lien.hash === cible);
  for (const panneau of document.querySelectorAll(".panneau")) panneau.hidden = `#${panneau.id}` !== cible;
}
window.addEventListener("hashchange", section);
section();

// --- La gestion : campagnes, corbeille, personnages, MJ ---
// Ce que le joueur ou le MJ ont écrit (noms d'univers, de personnages…) n'entre jamais dans du HTML : textContent seulement.
function el(balise, classe, texte) {
  const noeud = document.createElement(balise);
  if (classe) noeud.className = classe;
  if (texte !== undefined) noeud.textContent = texte;
  return noeud;
}

function ligne(titre, detail, classeDetail, boutons) {
  const li = el("li");
  const texte = el("div");
  texte.append(el("div", "titre", titre), el("div", `detail ${classeDetail || ""}`, detail));
  const actions = el("div");
  for (const [libelle, action] of boutons) {
    const bouton = el("button", "secondaire", libelle);
    bouton.type = "button";
    bouton.addEventListener("click", action);
    actions.append(bouton);
  }
  li.append(texte, actions);
  return li;
}

function vide(liste, texte) {
  liste.replaceChildren(el("li", "vide", texte));
}

async function agir(statut, chemin, options, reussite) {
  statut.className = "statut";
  try {
    const reponse = await api(chemin, { method: "POST", ...options });
    statut.textContent = reussite(reponse);
  } catch (erreur) {
    statut.className = "statut erreur";
    statut.textContent = erreur.message;
  }
  await Promise.all([campagnes(), corbeille(), personnages()]);
}

async function campagnes() {
  const liste = champ("liste-campagnes");
  const toutes = await api("/api/campagnes");
  if (!toutes.length) return vide(liste, "Aucune campagne pour l'instant.");
  liste.replaceChildren(...toutes.map((c) => {
    const jeter = ["Mettre à la corbeille", () => {
      if (confirm(`Mettre « ${c.nom} » à la corbeille ? Tu pourras la restaurer.`)) {
        agir(champ("statut-campagnes"), `/api/campagnes/${encodeURIComponent(c.nom)}/corbeille`, {},
          () => `« ${c.nom} » est dans la corbeille.`);
      }
    }];
    if (!c.lisible) return ligne(c.nom, `illisible (${c.erreur})`, "etat-mort", [jeter]);
    const reprendre = ["Reprendre", () => demarrer("/api/partie/reprendre", { nom: c.nom }, champ("statut-campagnes"))];
    const perso = c.personnage ? `${c.personnage.nom}, ${c.personnage.parcours} · ` : "";
    const detail = `${c.univers} (${c.genre}, ${c.ton}, ${c.magie ? "magie" : "sans magie"}) · ${perso}${c.etape}`;
    return ligne(c.nom, detail, `etat-${c.etat}`, [reprendre, jeter]);
  }));
}

async function corbeille() {
  const liste = champ("liste-corbeille");
  const jetees = await api("/api/corbeille");
  champ("vider-corbeille").hidden = !jetees.length;
  if (!jetees.length) return vide(liste, "La corbeille est vide.");
  liste.replaceChildren(...jetees.map((j) => ligne(j.nom, j.date ? `jetée le ${j.date}` : "", "", [["Restaurer", () =>
    agir(champ("statut-campagnes"), `/api/corbeille/${encodeURIComponent(j.id)}/restaurer`, {},
      (r) => `« ${r.nom} » est restaurée.`)]])));
}

async function personnages() {
  const liste = champ("liste-personnages");
  const prets = await api("/api/personnages");
  liste.replaceChildren(...prets.map((p) => ligne(p.nom, p.titre, "", p.livre ? [] : [["Supprimer", () => {
    if (confirm(`Supprimer ${p.nom} pour de bon ? C'est définitif.`)) {
      agir(champ("statut-personnages"), `/api/personnages/${encodeURIComponent(p.id)}/supprimer`, {},
        (r) => `${r.nom} est supprimé.`);
    }
  }]])));
}

champ("vider-corbeille").addEventListener("click", () => {
  if (confirm("Effacer pour de bon tout ce que contient la corbeille ? C'est définitif.")) {
    agir(champ("statut-campagnes"), "/api/corbeille/vider",
      { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirme: true }) },
      (r) => `${r.effacees} campagne(s) effacée(s).`);
  }
});

champ("qualifier").addEventListener("click", () => {
  if (confirm("Qualifier le MJ prend plus d'une heure et occupe la carte graphique. Ne lance rien de lourd pendant ce temps. Continuer ?")) {
    demarrer("/api/banc", {}, champ("statut-reglages"));
  }
});

champ("ouvrir-donnees").addEventListener("click", () =>
  agir(champ("statut-reglages"), "/api/donnees/ouvrir", {}, (r) => `Dossier ouvert : ${r.dossier}`));

async function mj() {
  const info = await api("/api/mj");
  const accueil = champ("mj");
  const detail = champ("mj-detail");
  champ("qualifier").textContent = info.qualifie ? "Requalifier le MJ" : "Qualifier le MJ";
  if (info.qualifie) {
    accueil.textContent = `MJ retenu sur ce PC : ${info.modele}, réflexion ${info.budget_reflexion} jetons.`;
    detail.textContent = `Modèle : ${info.modele} (${info.fichier}). Réflexion : ${info.budget_reflexion} jetons par action, `
      + `${info.budget_generateur} pour créer un univers, un personnage ou une amorce.`;
  } else {
    accueil.textContent = "Aucun MJ n'est qualifié sur ce PC : qualifie-le dans les Réglages.";
    detail.textContent = "Pas de MJ qualifié sur ce PC : la qualification, plus bas, le fera.";
  }
  const manque = info.moteur_present ? "" : ` Le serveur du MJ est introuvable : ${info.moteur}. Place le dossier Aria-LLM `
    + "à côté de l'exe, ou dans ton dossier d'utilisateur.";
  detail.textContent += manque;
  accueil.className = detail.className = info.qualifie && info.moteur_present ? "mj ok" : "mj";
}

// --- La partie : le moteur tourne dans un fil du serveur ; la page lit ce qu'il dit et lui envoie les réponses ---
async function envoyer(chemin, corps) {
  return api(chemin, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
}

const rafraichirTout = () => Promise.all([campagnes(), corbeille(), personnages()]);

const Partie = (() => {
  const journal = champ("journal");
  let dernier = 0;
  let suivi = false;
  let etat = { actif: false, nature: "" };

  function ecrire(classe, texte) {
    const bas = journal.scrollHeight - journal.scrollTop - journal.clientHeight < 40;
    journal.append(el("p", classe, texte));
    if (bas) journal.scrollTop = journal.scrollHeight;  // on ne ramène pas en bas celui qui relit plus haut
  }

  function afficher(evenement) {
    if (evenement.type === "texte") ecrire("l-texte", evenement.texte);
    else if (evenement.type === "joueur") ecrire("l-joueur", `> ${evenement.texte}`);
    else if (evenement.type === "invite" && evenement.texte.trim() !== ">") ecrire("l-invite", evenement.texte.trim());
  }

  function controles(actif, attend) {
    const pret = attend !== null && attend !== undefined;
    const texte = champ("saisie-texte");
    texte.disabled = champ("saisie-envoyer").disabled = !pret;
    texte.placeholder = !pret ? "" : attend.trim() === ">" ? "Écris ce que fait ton personnage" : attend.trim();
    if (pret) texte.focus({ preventScroll: true });
    champ("commandes").hidden = !(actif && pret && attend.trim() === ">" && etat.nature === "campagne");
    champ("interrompre").hidden = !actif;
    champ("partie-etat").textContent = !actif
      ? (dernier ? "Partie terminée." : "Aucune partie n'est ouverte.")
      : pret ? "À toi de jouer."
        : etat.nature === "banc" ? "La qualification tourne : une ligne par situation, plus d'une heure en tout."
        : "Le jeu travaille… (le MJ réfléchit, parfois une minute)";
  }

  async function suivre() {
    if (suivi) return;
    suivi = true;
    try {
      for (;;) {
        const lot = await api(`/api/partie/evenements?apres=${dernier}&attente=20`);
        lot.evenements.forEach(afficher);
        dernier = lot.dernier;
        etat = { ...etat, actif: lot.actif };
        controles(lot.actif, lot.attend);
        if (!lot.actif) break;
      }
    } catch (erreur) {
      ecrire("l-erreur", `Connexion perdue : ${erreur.message}`);
    } finally {
      suivi = false;
      rafraichirTout().catch(() => {});
      mj().catch(() => {});  // un banc a pu qualifier le MJ
    }
  }

  async function demarrer(chemin, corps, statut) {
    statut.className = "statut";
    statut.textContent = "";
    try {
      etat = await envoyer(chemin, corps);
      journal.replaceChildren();
      dernier = 0;
      champ("partie-titre").textContent = etat.titre;
      location.hash = "#partie";
      suivre();
    } catch (erreur) {
      statut.className = "statut erreur";
      statut.textContent = erreur.message;
    }
  }

  async function reprendreAffichage() {
    etat = await api("/api/partie");
    if (etat.titre) champ("partie-titre").textContent = etat.titre;
    if (etat.actif) location.hash = "#partie";
    if (etat.dernier) {
      journal.replaceChildren();
      dernier = 0;
      suivre();  // relit tout le fil, puis continue tant que la partie tourne : on n'attend pas sa fin ici
    }
  }

  return { demarrer, reprendreAffichage };
})();
const demarrer = Partie.demarrer;

champ("saisie").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  const texte = champ("saisie-texte");
  const valeur = texte.value;
  texte.value = "";
  texte.disabled = champ("saisie-envoyer").disabled = true;  // la réponse part : on attend la suite du jeu
  try { await envoyer("/api/partie/saisie", { texte: valeur }); } catch (erreur) { champ("partie-etat").textContent = erreur.message; }
});

for (const bouton of document.querySelectorAll("[data-commande]")) {
  bouton.addEventListener("click", async () => {
    champ("commandes").hidden = true;
    try { await envoyer("/api/partie/saisie", { texte: bouton.dataset.commande }); } catch (erreur) { champ("partie-etat").textContent = erreur.message; }
  });
}

champ("interrompre").addEventListener("click", async () => {
  const banc = (await api("/api/partie")).nature === "banc";
  if (!confirm(banc
    ? "Interrompre la qualification ? Elle s'arrête à la fin de la situation en cours, et le profil actuel du MJ est gardé tel quel."
    : "Interrompre la partie ? La dernière sauvegarde est gardée ; ce qui n'est pas sauvegardé est perdu.")) return;
  try { await envoyer("/api/partie/arreter", {}); } catch (erreur) { champ("partie-etat").textContent = erreur.message; }
});

// --- Les formulaires : nouvelle campagne, nouveau personnage ---
let options = null;
const option = (valeur, texte) => { const o = el("option", "", texte); o.value = valeur; return o; };

async function charger_options() {
  options = options || await api("/api/creation");
  return options;
}

function genreChoisi(id) {
  return options.genres.find((g) => g.nom === champ(id).value);
}

function majGenre() {
  const g = genreChoisi("nv-genre");
  champ("nv-magie-ligne").hidden = !g.magie_au_choix;
  champ("nv-ton").value = g.ton;
  champ("nv-perso").replaceChildren(option("", "Le créer pour cette campagne"), ...g.personnages.map((p) => option(p.id, p.titre)));
  majPerso();
}
const majPerso = () => { champ("nv-cran-ligne").hidden = champ("nv-perso").value !== ""; };
function majType() {
  const t = options.types.find((x) => x.nom === champ("nv-type").value);
  champ("nv-type-desc").textContent = t.description;
  champ("nv-cran").value = t.cran;
}

champ("nouvelle-campagne").addEventListener("click", async () => {
  const o = await charger_options();
  champ("nv-genre").replaceChildren(...o.genres.map((g) => option(g.nom, g.complet ? g.nom : `${g.nom} (contenu encore léger)`)));
  champ("nv-ton").replaceChildren(...o.tons.map((t) => option(t, t)));
  champ("nv-type").replaceChildren(...o.types.map((t) => option(t.nom, t.nom)));
  champ("nv-genre").value = (o.genres.find((g) => g.complet) || o.genres[0]).nom;  // le genre qui a du contenu, d'abord
  champ("nv-type").value = o.type_standard;
  champ("nv-cran").replaceChildren(...o.crans.map((c) => option(c, c)));
  majGenre();
  majType();
  location.hash = "#nouvelle";
});
champ("nv-genre").addEventListener("change", majGenre);
champ("nv-perso").addEventListener("change", majPerso);
champ("nv-type").addEventListener("change", majType);
champ("nv-annuler").addEventListener("click", () => { location.hash = "#campagnes"; });

champ("form-nouvelle").addEventListener("submit", (evenement) => {
  evenement.preventDefault();
  const annee = champ("nv-annee").value;
  demarrer("/api/partie/nouvelle", {
    nom: champ("nv-nom").value, genre: champ("nv-genre").value, univers: champ("nv-univers").value,
    cadre: champ("nv-cadre").value, annee: annee === "" ? null : Number(annee), surprends_moi: champ("nv-surprends").checked,
    ton: champ("nv-ton").value, magie: champ("nv-magie").checked, type: champ("nv-type").value,
    personnage: champ("nv-perso").value, cran: champ("nv-cran").value,
  }, champ("statut-nouvelle"));
});

champ("nouveau-personnage").addEventListener("click", async () => {
  const o = await charger_options();
  champ("pe-genre").replaceChildren(...o.genres.map((g) => option(g.nom, g.complet ? g.nom : `${g.nom} (contenu encore léger)`)));
  champ("pe-cran").replaceChildren(...o.crans.map((c) => option(c, c)));
  champ("pe-genre").value = (o.genres.find((g) => g.complet) || o.genres[0]).nom;
  location.hash = "#creer-personnage";
});
champ("pe-annuler").addEventListener("click", () => { location.hash = "#personnages"; });
champ("form-personnage").addEventListener("submit", (evenement) => {
  evenement.preventDefault();
  demarrer("/api/partie/personnage", { genre: champ("pe-genre").value, cran: champ("pe-cran").value, avec_mj: champ("pe-mj").checked },
    champ("statut-personnage"));
});

// --- Démarrage ---
(async () => {
  try {
    const etat = await api("/api/etat");
    champ("version").textContent = `Version ${etat.version}`;
    afficher(await api("/api/reglages"));
    Fond.configurer(await api("/api/fond"));
    await Promise.all([mj(), campagnes(), corbeille(), personnages()]);
    await Partie.reprendreAffichage();
  } catch (erreur) {
    message.className = "erreur";
    message.textContent = erreur.message;
  }
})();
