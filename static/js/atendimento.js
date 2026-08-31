(function () {
  "use strict";

  var btnWhatsapp = document.getElementById("btn-abrir-whatsapp");
  var editor = document.getElementById("mensagem-editor");
  if (btnWhatsapp && editor) {
    btnWhatsapp.addEventListener("click", function () {
      var digits = (btnWhatsapp.getAttribute("data-telefone") || "").replace(/\D/g, "");
      if (!digits) return;
      var texto = encodeURIComponent(editor.value);
      window.open("https://wa.me/" + digits + "?text=" + texto, "_blank", "noopener");
    });
  }

  var btn = document.getElementById("btn-auto-qualificar");
  if (!btn) return;

  btn.addEventListener("click", function () {
    btn.disabled = true;
    var original = btn.innerHTML;
    btn.textContent = "Rodando automação...";

    fetch("/api/atendimento/qualificar-automatico", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.ok) {
          var msg = res.qualificados > 0
            ? res.qualificados + " lead" + (res.qualificados === 1 ? "" : "s") + " qualificado" + (res.qualificados === 1 ? "" : "s") + " automaticamente."
            : "Nenhum lead atingiu o critério de qualificação agora.";
          window.fabricaToast(msg);
          setTimeout(function () { window.location.reload(); }, 900);
        } else {
          window.fabricaToast("Não consegui rodar a automação.");
          btn.disabled = false;
          btn.innerHTML = original;
        }
      })
      .catch(function () {
        window.fabricaToast("Não consegui rodar a automação.");
        btn.disabled = false;
        btn.innerHTML = original;
      });
  });
})();
