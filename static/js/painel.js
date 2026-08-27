(function () {
  "use strict";
  var btn = document.getElementById("btn-send-digest");
  if (!btn) return;
  btn.addEventListener("click", function () {
    btn.disabled = true;
    var original = btn.textContent;
    fetch("/api/digest/send", { method: "POST" })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, body: d }; }); })
      .then(function (res) {
        if (res.ok) {
          window.fabricaToast("Resumo enviado (" + res.body.total + " pendências).");
        } else {
          window.fabricaToast(res.body.reason || "Não consegui enviar.");
        }
      })
      .catch(function () {
        window.fabricaToast("Não consegui enviar o resumo.");
      })
      .finally(function () {
        btn.disabled = false;
      });
  });
})();
