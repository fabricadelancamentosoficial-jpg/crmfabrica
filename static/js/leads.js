(function () {
  "use strict";

  var novoBtn = document.getElementById("btn-novo-lead");
  if (novoBtn) {
    novoBtn.addEventListener("click", function () {
      window.fabricaLeadModal.open(null, "Lead novo");
    });
  }

  document.querySelectorAll(".lead-row").forEach(function (row) {
    row.addEventListener("click", function (e) {
      if (e.target.closest(".check-col")) return;
      try {
        var lead = JSON.parse(row.getAttribute("data-lead"));
        window.fabricaLeadModal.open(lead);
      } catch (err) { /* ignore malformed data */ }
    });
  });

  var checkAll = document.getElementById("check-all");
  var checks = Array.prototype.slice.call(document.querySelectorAll(".lead-check"));
  var bulkBar = document.getElementById("bulk-bar");
  var bulkCount = document.getElementById("bulk-count");
  var btnBulkExcluir = document.getElementById("btn-bulk-excluir");
  var btnBulkCancelar = document.getElementById("btn-bulk-cancelar");

  function atualizarBarra() {
    var marcados = checks.filter(function (c) { return c.checked; });
    if (bulkBar) bulkBar.classList.toggle("is-visible", marcados.length > 0);
    if (bulkCount) bulkCount.textContent = marcados.length + (marcados.length === 1 ? " selecionado" : " selecionados");
    if (checkAll) {
      checkAll.checked = marcados.length > 0 && marcados.length === checks.length;
      checkAll.indeterminate = marcados.length > 0 && marcados.length < checks.length;
    }
  }

  checks.forEach(function (c) {
    c.addEventListener("change", atualizarBarra);
  });

  if (checkAll) {
    checkAll.addEventListener("change", function () {
      checks.forEach(function (c) { c.checked = checkAll.checked; });
      atualizarBarra();
    });
  }

  if (btnBulkCancelar) {
    btnBulkCancelar.addEventListener("click", function () {
      checks.forEach(function (c) { c.checked = false; });
      atualizarBarra();
    });
  }

  if (btnBulkExcluir) {
    btnBulkExcluir.addEventListener("click", function () {
      var ids = checks.filter(function (c) { return c.checked; }).map(function (c) { return c.getAttribute("data-id"); });
      if (!ids.length) return;
      var confirmMsg = ids.length === 1
        ? "Excluir esse lead? Essa ação não pode ser desfeita."
        : "Excluir esses " + ids.length + " leads? Essa ação não pode ser desfeita.";
      if (!window.confirm(confirmMsg)) return;

      btnBulkExcluir.disabled = true;
      fetch("/api/leads/excluir-em-massa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: ids }),
      })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.ok) {
            window.fabricaToast(res.excluidos + " lead" + (res.excluidos === 1 ? "" : "s") + " excluído" + (res.excluidos === 1 ? "" : "s") + ".");
            window.location.reload();
          } else {
            window.fabricaToast(res.erro || "Não consegui excluir.");
            btnBulkExcluir.disabled = false;
          }
        })
        .catch(function () {
          window.fabricaToast("Não consegui excluir.");
          btnBulkExcluir.disabled = false;
        });
    });
  }

  var form = document.getElementById("filter-form");
  var searchInput = form ? form.querySelector('input[name="q"]') : null;
  if (searchInput) {
    var timer = null;
    searchInput.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { form.submit(); }, 450);
    });
  }
})();
