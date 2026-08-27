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

(function () {
  "use strict";
  var btnEdit = document.getElementById("btn-edit-meta");
  var editor = document.getElementById("meta-hero-editor");
  var input = document.getElementById("meta-input");
  var btnSave = document.getElementById("btn-save-meta");
  var btnCancel = document.getElementById("btn-cancel-meta");
  if (!btnEdit || !editor) return;

  btnEdit.addEventListener("click", function () {
    editor.style.display = editor.style.display === "none" ? "flex" : "none";
    if (editor.style.display === "flex") {
      input.focus();
      input.select();
    }
  });

  if (btnCancel) {
    btnCancel.addEventListener("click", function () {
      editor.style.display = "none";
    });
  }

  if (btnSave) {
    btnSave.addEventListener("click", function () {
      var valor = input.value.trim();
      if (!valor || Number(valor) < 0) {
        window.fabricaToast("Digite um valor válido.");
        return;
      }
      btnSave.disabled = true;
      fetch("/api/meta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ valor: valor }),
      })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.ok) {
            window.fabricaToast("Meta atualizada.");
            window.location.reload();
          } else {
            window.fabricaToast(res.erro || "Não consegui salvar.");
            btnSave.disabled = false;
          }
        })
        .catch(function () {
          window.fabricaToast("Não consegui salvar.");
          btnSave.disabled = false;
        });
    });
  }

  if (input) {
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") btnSave.click();
    });
  }
})();
