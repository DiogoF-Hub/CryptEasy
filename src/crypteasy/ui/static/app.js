// CryptEasy : petits conforts d'interface. Tout fonctionne aussi sans JavaScript.
// Aucune donnée n'est injectée dans ce fichier (CSP : pas de script en ligne).
document.addEventListener("DOMContentLoaded", () => {
  // Confirmation avant les actions destructrices
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
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
  // on indique donc ce qui se passe et on vide le mot de passe.
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
