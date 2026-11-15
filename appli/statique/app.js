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
    const perso = c.personnage ? `${c.personnage.nom}, ${c.personnage.parcours} · ` : "";
    const detail = `${c.univers} (${c.genre}, ${c.ton}, ${c.magie ? "magie" : "sans magie"}) · ${perso}${c.etape}`;
    return ligne(c.nom, detail, `etat-${c.etat}`, [jeter]);
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

champ("ouvrir-donnees").addEventListener("click", () =>
  agir(champ("statut-reglages"), "/api/donnees/ouvrir", {}, (r) => `Dossier ouvert : ${r.dossier}`));

async function mj() {
  const info = await api("/api/mj");
  const accueil = champ("mj");
  const detail = champ("mj-detail");
  if (info.qualifie) {
    accueil.textContent = `MJ retenu sur ce PC : ${info.modele}, réflexion ${info.budget_reflexion} jetons.`;
    detail.textContent = `Modèle : ${info.modele} (${info.fichier}). Réflexion : ${info.budget_reflexion} jetons par action, `
      + `${info.budget_generateur} pour créer un univers, un personnage ou une amorce.`;
  } else {
    accueil.textContent = "Aucun MJ n'est qualifié sur ce PC : le banc d'essai le fera.";
    detail.textContent = "Pas de MJ qualifié sur ce PC : le banc d'essai (bientôt dans cette interface) le qualifiera.";
  }
  const manque = info.moteur_present ? "" : ` Le serveur du MJ est introuvable : ${info.moteur}. Place le dossier Aria-LLM `
    + "à côté de l'exe, ou dans ton dossier d'utilisateur.";
  detail.textContent += manque;
  accueil.className = detail.className = info.qualifie && info.moteur_present ? "mj ok" : "mj";
}

// --- Démarrage ---
(async () => {
  try {
    const etat = await api("/api/etat");
    champ("version").textContent = `Version ${etat.version}`;
    afficher(await api("/api/reglages"));
    Fond.configurer(await api("/api/fond"));
    await Promise.all([mj(), campagnes(), corbeille(), personnages()]);
  } catch (erreur) {
    message.className = "erreur";
    message.textContent = erreur.message;
  }
})();
