(function () {
  "use strict";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var label = document.getElementById("theme-label");
    if (label) label.textContent = theme === "dark" ? "Tema escuro" : "Tema claro";
  }

  function persistTheme(theme) {
    fetch("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: theme }),
    }).catch(function () {});
  }

  document.querySelectorAll("#theme-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      persistTheme(next);
    });
  });

  applyTheme(currentTheme());

  window.fabricaToast = function (msg) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("visible");
    clearTimeout(window.__toastTimer);
    window.__toastTimer = setTimeout(function () {
      el.classList.remove("visible");
    }, 2600);
  };
})();
