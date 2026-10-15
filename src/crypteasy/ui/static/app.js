// CryptEasy : conforts d'interface. Tout fonctionne aussi sans JavaScript.
// Aucune donnée n'est injectée dans ce fichier (CSP : pas de script en ligne).
// Les règles de l'indicateur viennent du serveur (security_levels.py) via data-rules.
"use strict";

const LEVEL_ORDER = ["good", "ok", "weak"];

// ------------------------------------------------------------ indicateur F6
function activeWhen(form, el) {
  const when = el.dataset.rateWhen;
  if (!when) return true;
  const toggle = form.querySelector(`[name="${when}"]`);
  return !toggle || toggle.checked;
}

function updateRating(form, box) {
  const cfg = JSON.parse(box.dataset.rules);
  const reasons = [];
  form.querySelectorAll("[data-rate]").forEach((el) => {
    if (!activeWhen(form, el)) return;
    let value = el.value;
    if (el.tagName === "SELECT") {
      const opt = el.selectedOptions[0];
      if (!opt) return;
      value = opt.dataset.rateValue ?? opt.value;
    }
    const rule = (cfg.rules[el.dataset.rate] || {})[value];
    if (rule) reasons.push(rule);
  });
  form.querySelectorAll("[data-rate-password]").forEach((el) => {
    if (activeWhen(form, el) && el.value && el.value.length < cfg.minPassword) {
      reasons.push(cfg.shortPassword);
    }
  });
  const level = reasons.reduce(
    (worst, [lvl]) => (LEVEL_ORDER.indexOf(lvl) > LEVEL_ORDER.indexOf(worst) ? lvl : worst), "good");

  box.className = `rating rating-${level}`;
  box.querySelector(".rating-icon").textContent = cfg.levels[level].icon;
  box.querySelector(".rating-label").textContent = cfg.levels[level].label;
  const list = box.querySelector(".rating-reasons");
  list.replaceChildren(...reasons.map(([lvl, text]) => {
    const li = document.createElement("li");
    li.className = `lvl-${lvl}`;
    li.textContent = text;          // textContent : jamais d'interprétation HTML
    return li;
  }));
}

// ------------------------------------------------------------ robustesse du mot de passe
// Indicatif seulement : calculé dans le navigateur, rien n'est envoyé au serveur.
function strength(pw, min) {
  if (!pw) return null;
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  if (pw.length < min) return { level: "weak", text: `Trop court (${pw.length}/${min})`, pct: 25 };
  if (pw.length >= 20 || (pw.length >= 15 && classes >= 3)) return { level: "good", text: "Robuste", pct: 100 };
  return { level: "ok", text: "Correct : plus long serait mieux", pct: 60 };
}

document.addEventListener("DOMContentLoaded", () => {
  // Confirmation avant les actions sensibles
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Case qui affiche / masque un bloc (ex. mot de passe supplémentaire)
  document.querySelectorAll("input[type=checkbox][data-toggle]").forEach((box) => {
    const target = document.querySelector(box.dataset.toggle);
    const sync = () => {
      target.hidden = !box.checked;
      target.querySelectorAll("input[type=password]").forEach((i) => { i.required = box.checked; });
    };
    box.addEventListener("change", sync);
    sync();
  });

  // Argon2id exige un sel : on désactive « aucun sel » quand Argon2id est choisi
  document.querySelectorAll("select[name=kdf]").forEach((kdf) => {
    const salt = kdf.form.querySelector("select[name=salt]");
    if (!salt) return;
    const sync = () => {
      const none = salt.querySelector("option[data-pbkdf2-only]");
      none.disabled = kdf.value === "argon2id";
      if (none.disabled && salt.value === none.value) salt.value = "16";
    };
    kdf.addEventListener("change", () => { sync(); salt.dispatchEvent(new Event("change", { bubbles: true })); });
    sync();
  });

  // Indicateur de niveau en direct
  document.querySelectorAll("[data-rating]").forEach((box) => {
    const form = box.closest("form");
    const refresh = () => updateRating(form, box);
    form.addEventListener("change", refresh);
    form.addEventListener("input", refresh);
    refresh();
  });

  // Robustesse des mots de passe
  document.querySelectorAll("[data-pw-meter]").forEach((meter) => {
    const input = meter.closest("form").querySelector(`input[name="${meter.dataset.pwMeter}"]`);
    const cfg = JSON.parse(meter.closest("form").querySelector("[data-rating]")?.dataset.rules || '{"minPassword":12}');
    const bar = meter.querySelector(".pw-bar span");
    const text = meter.querySelector(".pw-text");
    const sync = () => {
      const s = strength(input.value, cfg.minPassword);
      meter.className = `pw-meter${s ? " pw-" + s.level : ""}`;
      bar.style.width = s ? `${s.pct}%` : "0";
      text.textContent = s ? `Robustesse : ${s.text}` : "";
    };
    input.addEventListener("input", sync);
    sync();
  });

  // Zone de dépôt : nom du fichier choisi + effet au survol
  document.querySelectorAll(".dropzone").forEach((zone) => {
    const input = zone.querySelector("input[type=file]");
    const nameEl = zone.querySelector(".dropzone-name");
    const show = () => { nameEl.textContent = input.files.length ? input.files[0].name : ""; };
    input.addEventListener("change", show);
    ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, () => zone.classList.add("dragover")));
    ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, () => zone.classList.remove("dragover")));
  });

  // Formulaires dont la réponse est un téléchargement : la page ne change pas,
  // on indique donc ce qui se passe et on vide les mots de passe.
  document.querySelectorAll("form[data-download]").forEach((form) => {
    const btn = form.querySelector("button[type=submit]");
    const status = form.querySelector(".status");
    form.addEventListener("submit", () => {
      const label = btn.textContent;
      btn.disabled = true;
      btn.textContent = btn.dataset.busy || "Traitement…";
      setTimeout(() => {
        btn.disabled = false;
        btn.textContent = label;
        form.querySelectorAll("input[type=password]").forEach((pw) => { pw.value = ""; });
        form.dispatchEvent(new Event("input"));
        if (status) status.textContent = "Terminé : vérifiez vos téléchargements.";
      }, 1500);
    });
  });

  // Autres formulaires : indicateur de traitement
  document.querySelectorAll("form:not([data-download]) button[data-busy]").forEach((btn) => {
    btn.form.addEventListener("submit", () => {
      btn.disabled = true;
      btn.textContent = btn.dataset.busy;
    });
  });
});
