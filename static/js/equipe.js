(function () {
  "use strict";
  var form = document.getElementById("form-equipe");
  var lista = document.getElementById("equipe-lista");
  if (!form || !lista) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var input = document.getElementById("equipe-nome");
    var nome = input.value.trim();
    if (!nome) return;

    fetch("/api/responsaveis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: nome }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, body: d }; }); })
      .then(function (res) {
        if (res.ok) {
          window.fabricaToast(nome + " adicionado(a).");
          window.location.reload();
        } else {
          window.fabricaToast(res.body.erro || "Não consegui adicionar.");
        }
      })
      .catch(function () {
        window.fabricaToast("Não consegui adicionar.");
      });
  });

  lista.addEventListener("click", function (e) {
    var btn = e.target.closest(".btn-toggle-membro");
    if (!btn) return;
    var row = btn.closest(".equipe-row");
    var id = row.getAttribute("data-id");
    var ativoAtual = btn.getAttribute("data-ativo") === "1" || btn.getAttribute("data-ativo") === "True";
    var novoAtivo = !ativoAtual;

    fetch("/api/responsaveis/" + id, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ativo: novoAtivo }),
    })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.ok) {
          window.fabricaToast(novoAtivo ? "Reativado(a)." : "Desativado(a).");
          window.location.reload();
        } else {
          window.fabricaToast("Não consegui atualizar.");
        }
      })
      .catch(function () {
        window.fabricaToast("Não consegui atualizar.");
      });
  });
})();
