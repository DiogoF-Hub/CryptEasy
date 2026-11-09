// CryptEasy : comportement des pages dans la fenêtre pywebview.
// - Aucune donnée n'est injectée dans ce fichier (CSP : pas de script en ligne).
// - Les textes viennent du bloc JSON #i18n (traductions), les règles de niveau de data-rules.
// - La page ne manipule jamais de chemin de fichier : seulement des identifiants
//   renvoyés par l'API après une boîte de dialogue native.
"use strict";

const I18N = JSON.parse(document.getElementById("i18n")?.textContent || "{}");
const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || "";

function tr(key, params = {}) {
  let text = I18N[key] || key;
  for (const [k, v] of Object.entries(params)) text = text.split(`{${k}}`).join(String(v));
  return text;
}

async function api(url, body) {
  const options = {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-CSRFToken": CSRF, "Content-Type": "application/json" },
    credentials: "same-origin",
    cache: "no-store",
  };
  if (body !== undefined) options.body = JSON.stringify(body);
  try {
    const resp = await fetch(url, options);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok && !data.error) data.error = tr("js.unexpected");
    return data;
  } catch {
    return { error: tr("js.unexpected") };
  }
}

const $ = (root, sel) => root.querySelector(sel);
const show = (el, visible = true) => { if (el) el.hidden = !visible; };

// ====================================================================== niveaux (F6)
function worstLevel(order, levels) {
  return levels.reduce((worst, lvl) => (order.indexOf(lvl) > order.indexOf(worst) ? lvl : worst), order[1]);
}

function passphraseLevel(cfg, length) {
  if (length >= cfg.veryStrongPassphrase) return "very_strong";
  return length >= cfg.minPassphrase ? "strong" : "weak";
}

function updateRating(form) {
  const box = $(form, "[data-rating]");
  if (!box) return;
  const cfg = JSON.parse(box.dataset.rules);
  const noPass = $(form, "[data-no-passphrase]")?.checked;
  const reasons = [];
  form.querySelectorAll("[data-rate]").forEach((el) => {
    if (noPass && el.hasAttribute("data-kdf-field")) return;
    let value = el.value;
    if (el.tagName === "SELECT") {
      const opt = el.selectedOptions[0];
      if (!opt) return;
      value = opt.dataset.rateValue ?? opt.value;
    }
    const level = (cfg.ratings[el.dataset.rate] || {})[value];
    if (level) reasons.push([level, cfg.reasons[`${el.dataset.rate}.${value}`]]);
  });
  const pass = $(form, "[data-rate-passphrase]");
  if (noPass) {
    reasons.push(["none", cfg.noPassphrase]);
  } else if (pass && pass.value) {
    const lvl = passphraseLevel(cfg, pass.value.length);
    reasons.push([lvl, cfg.passphraseReasons[lvl]]);
  }
  const level = worstLevel(cfg.order, reasons.map(([lvl]) => lvl));
  box.className = `rating rating-${level}`;
  $(box, ".rating-icon").textContent = cfg.icons[level];
  $(box, ".rating-label").textContent = cfg.labels[level];
  $(box, ".rating-reasons").replaceChildren(...reasons.map(([lvl, text]) => {
    const li = document.createElement("li");
    li.className = `lvl-${lvl}`;
    li.textContent = text; // textContent : jamais d'interprétation HTML
    return li;
  }));
}

// ====================================================================== protection de clé
function setupProtectionForm(form) {
  const cfg = JSON.parse($(form, "[data-rating]").dataset.rules);
  const levelSelect = $(form, "[data-level-select]");
  const help = $(form, "[data-level-help]");
  const noPass = $(form, "[data-no-passphrase]");
  const warning = $(form, "[data-no-passphrase-warning]");
  const passBlock = $(form, "[data-passphrase-block]");
  const kdf = $(form, "select[name=kdf]");
  const salt = $(form, "select[name=salt]");
  const presetFields = ["key_type", "kdf", "kdf_strength", "salt"];

  const syncSalt = () => {
    const none = salt && $(salt, "option[data-pbkdf2-only]");
    if (!none) return;
    none.disabled = kdf.value === "argon2id"; // Argon2id exige toujours un sel
    if (none.disabled && salt.value === none.value) salt.value = "16";
  };
  const currentPreset = () => {
    for (const [level, preset] of Object.entries(cfg.presets)) {
      const match = presetFields.every((f) => {
        const el = form.querySelector(`select[name=${f}]`);
        return !el || el.value === preset[f];
      });
      if (match) return level;
    }
    return "custom";
  };
  const syncHelp = () => { if (help) help.textContent = cfg.levelHelp[levelSelect.value] || ""; };
  const syncNoPass = () => {
    const on = noPass.checked;
    show(warning, on);
    show(passBlock, !on);
    passBlock.querySelectorAll("input").forEach((i) => { i.required = !on; if (on) i.value = ""; });
    form.querySelectorAll("[data-kdf-field]").forEach((el) => { el.disabled = on; });
    const confirmBox = warning && $(warning, "input");
    if (confirmBox) confirmBox.required = on;
  };

  levelSelect.addEventListener("change", () => {
    const preset = cfg.presets[levelSelect.value];
    if (preset) {
      for (const f of presetFields) {
        const el = form.querySelector(`select[name=${f}]`);
        if (el && preset[f]) el.value = preset[f];
      }
    } else {
      $(form, "details.advanced").open = true; // « personnalisé » : on montre les options
    }
    syncSalt();
    syncHelp();
    updateRating(form);
  });
  presetFields.forEach((f) => {
    form.querySelector(`select[name=${f}]`)?.addEventListener("change", () => {
      syncSalt();
      levelSelect.value = currentPreset();
      syncHelp();
    });
  });
  noPass.addEventListener("change", () => { syncNoPass(); updateRating(form); });
  syncSalt();
  syncNoPass();
}

// ====================================================================== robustesse
function setupPassphraseMeter(meter) {
  const form = meter.closest("form");
  const input = form.querySelector(`input[name="${meter.dataset.pwMeter}"]`);
  const cfg = JSON.parse($(form, "[data-rating]")?.dataset.rules || '{"minPassphrase":12,"veryStrongPassphrase":16}');
  const bar = $(meter, ".pw-bar span");
  const text = $(meter, ".pw-text");
  const sync = () => {
    const n = input.value.length;
    let state = null;
    if (n === 0) state = null;
    else if (n < cfg.minPassphrase) state = ["weak", tr("js.pw_short", { n, min: cfg.minPassphrase }), 25];
    else if (n < cfg.veryStrongPassphrase) state = ["ok", tr("js.pw_ok"), 60];
    else state = ["good", tr("js.pw_good"), 100];
    meter.className = `pw-meter${state ? ` pw-${state[0]}` : ""}`;
    bar.style.width = state ? `${state[2]}%` : "0";
    text.textContent = state ? tr("js.pw_label", { s: state[1] }) : "";
  };
  input.addEventListener("input", sync);
  sync();
}

// ====================================================================== boutons « Choisir… »
function setupChooser(chooser) {
  const hidden = $(chooser, "input[type=hidden]");
  const name = $(chooser, ".chooser-name");
  $(chooser, "button").addEventListener("click", async () => {
    const data = await api("/api/choisir", { what: chooser.dataset.choose });
    if (data.cancelled) return;
    if (data.error) {
      name.textContent = data.error;
      name.classList.add("chooser-error");
      return;
    }
    hidden.value = data.id;
    name.textContent = data.name;
    name.classList.remove("chooser-error");
    chooser.dispatchEvent(new CustomEvent("chosen", { bubbles: true, detail: data }));
  });
}

// ====================================================================== tâches
function poll(jobId, page, label, onDone) {
  const block = $(page, "[data-progress]");
  const bar = $(page, "[data-progress-bar]");
  const text = $(page, "[data-progress-text]");
  show(block);
  bar.style.width = "0";
  text.textContent = tr(label, { p: 0 });
  const tick = async () => {
    const st = await api(`/api/taches/${encodeURIComponent(jobId)}`);
    if (st.status === "running") {
      bar.style.width = `${st.percent}%`;
      text.textContent = tr(label, { p: st.percent });
      setTimeout(tick, 500); // la page demande l'avancement toutes les demi-secondes (§ 5.5)
      return;
    }
    show(block, false);
    onDone(st);
  };
  setTimeout(tick, 200);
}

function showError(page, message) {
  const box = $(page, "[data-error]");
  box.textContent = message;
  show(box, Boolean(message));
}

function showSelection(page, data, icon) {
  show($(page, "[data-selection]"));
  $(page, "[data-sel-name]").textContent = `${icon || (data.is_folder ? "📁" : "📄")} ${data.name}`;
  const parts = [`📦 ${data.size}`];
  if (data.files != null) parts.push(tr("js.files", { n: data.files }));
  parts.push(data.estimate ? data.estimate : tr("js.measuring"));
  $(page, "[data-sel-meta]").textContent = parts.join(" · ");
  show($(page, "[data-sel-big]"), data.big);
}

function setupReveal(page, getJob) {
  $(page, "[data-reveal]")?.addEventListener("click", () => {
    const job = getJob();
    if (job) api(`/api/taches/${encodeURIComponent(job)}/ouvrir-dossier`, {});
  });
}

// ====================================================================== Chiffrer (F4)
function setupEncryptPage(page) {
  const run = $(page, "[data-run]");
  const recipient = $(page, "select[name=recipient]");
  const cipher = $(page, "select[name=cipher]");
  let selection = null;
  let job = null;
  const sync = () => { run.disabled = !(selection && recipient.value); };

  page.querySelectorAll("[data-pick]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      showError(page, "");
      const data = await api("/api/choisir", { what: btn.dataset.pick });
      if (data.cancelled) return;
      if (data.error) { showError(page, data.error); return; }
      selection = data.id;
      showSelection(page, data);
      show($(page, "[data-result]"), false);
      sync();
    });
  });
  recipient.addEventListener("change", sync);
  setupReveal(page, () => job);

  run.addEventListener("click", async () => {
    showError(page, "");
    show($(page, "[data-result]"), false);
    if (!selection) { showError(page, tr("js.choose_source")); return; }
    if (!recipient.value) { showError(page, tr("js.choose_recipient")); return; }
    run.disabled = true;
    const data = await api("/api/chiffrer", { selection, recipient: recipient.value, cipher: cipher.value });
    if (data.cancelled || data.error) {
      if (data.error) showError(page, data.error);
      sync();
      return;
    }
    job = data.job;
    poll(job, page, "js.encrypting", (st) => {
      sync();
      if (st.status === "done") {
        $(page, "[data-result-text]").textContent = tr("js.encrypted", { path: st.saved });
        show($(page, "[data-result]"));
      } else {
        showError(page, st.error || tr("js.unexpected"));
      }
    });
  });
  sync();
}

// ====================================================================== Déchiffrer (F5)
function setupDecryptPage(page) {
  const run = $(page, "[data-run]");
  const passField = $(page, "[data-passphrase-field]");
  const passInput = $(passField, "input");
  const keyFileBlock = $(page, "[data-key-file-block]");
  const keyFileInput = $(keyFileBlock, "input[name=key_selection]");
  const otherKey = $(page, "[data-show-key-file]");
  let selection = null;
  let hasKey = false;
  let job = null;

  const sync = () => { run.disabled = !(selection && (hasKey || keyFileInput.value)); };
  const resetAfter = () => {
    show($(page, "[data-save-choice]"), false);
    show($(page, "[data-result]"), false);
  };

  $(page, "[data-pick=package]").addEventListener("click", async () => {
    showError(page, "");
    const data = await api("/api/choisir", { what: "package" });
    if (data.cancelled) return;
    if (data.error) { showError(page, data.error); return; }
    resetAfter();
    selection = data.id;
    showSelection(page, data, "🔒");
    show($(page, "[data-key-step]"));
    keyFileInput.value = "";
    $(keyFileBlock, ".chooser-name").textContent = "";
    hasKey = Boolean(data.key);
    const found = $(page, "[data-key-found]");
    const missing = $(page, "[data-key-missing]");
    if (data.key) {
      found.textContent = `🔑 ${tr("js.key_found", { name: data.key.name, kind: data.key.kind })}`;
      show(found);
      show(missing, false);
      show(keyFileBlock, false);
      show(otherKey);
      show(passField, data.key.protected);
      show($(page, "[data-no-passphrase-note]"), !data.key.protected);
    } else {
      missing.textContent = data.no_key_message;
      show(missing);
      show(found, false);
      show(keyFileBlock);
      show(otherKey, false);
      show(passField);
      show($(page, "[data-no-passphrase-note]"), false);
    }
    sync();
  });
  otherKey.addEventListener("click", () => { show(keyFileBlock); show(otherKey, false); });
  keyFileBlock.addEventListener("chosen", () => {
    hasKey = false; // la clé choisie à la main remplace la clé trouvée
    show($(page, "[data-key-found]"), false);
    show($(page, "[data-no-passphrase-note]"), false);
    show(passField);
    sync();
  });
  setupReveal(page, () => job);

  run.addEventListener("click", async () => {
    showError(page, "");
    resetAfter();
    run.disabled = true;
    const data = await api("/api/dechiffrer", {
      selection,
      passphrase: passInput.value,
      key_selection: keyFileInput.value || null,
    });
    passInput.value = ""; // la phrase secrète ne reste pas dans la page
    if (data.error) { showError(page, data.error); sync(); return; }
    job = data.job;
    poll(job, page, "js.decrypting", (st) => {
      sync();
      if (st.status !== "done") { showError(page, st.error || tr("js.unexpected")); return; }
      $(page, "[data-save-text]").textContent = tr(st.is_folder ? "js.decrypted_folder" : "js.decrypted_file", { name: st.name });
      show($(page, "[data-save-file]"), !st.is_folder);
      show($(page, "[data-save-folder]"), st.is_folder);
      show($(page, "[data-save-choice]"));
    });
  });

  page.querySelectorAll("[data-save]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      showError(page, "");
      const data = await api(`/api/taches/${encodeURIComponent(job)}/enregistrer`, { mode: btn.dataset.save });
      if (data.cancelled) return;
      if (data.error) { showError(page, data.error); return; }
      show($(page, "[data-save-choice]"), false);
      const key = btn.dataset.save === "extract" ? "js.extracted" : "js.saved";
      $(page, "[data-result-text]").textContent = tr(key, { path: data.saved });
      show($(page, "[data-result]"));
    });
  });
  sync();
}

// ====================================================================== démarrage
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => { if (!confirm(form.dataset.confirm)) e.preventDefault(); });
  });
  document.querySelectorAll("select[data-autosubmit]").forEach((sel) => {
    sel.addEventListener("change", () => sel.form.submit());
  });
  document.querySelectorAll("button[data-busy]").forEach((btn) => {
    btn.form?.addEventListener("submit", () => { btn.disabled = true; btn.textContent = btn.dataset.busy; });
  });
  document.querySelectorAll("[data-choose]").forEach(setupChooser);
  document.querySelectorAll("form[data-protection]").forEach(setupProtectionForm);
  document.querySelectorAll("[data-pw-meter]").forEach(setupPassphraseMeter);
  document.querySelectorAll("[data-rating]").forEach((box) => {
    const form = box.closest("form") || box.closest("[data-encrypt-page]");
    const refresh = () => updateRating(form);
    form.addEventListener("change", refresh);
    form.addEventListener("input", refresh);
    refresh();
  });
  const enc = document.querySelector("[data-encrypt-page]");
  if (enc && $(enc, "[data-run]")) setupEncryptPage(enc);
  const dec = document.querySelector("[data-decrypt-page]");
  if (dec) setupDecryptPage(dec);
});
