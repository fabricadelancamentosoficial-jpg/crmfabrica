(function () {
  "use strict";

  var novoBtn = document.getElementById("btn-novo-lead");
  if (novoBtn) {
    novoBtn.addEventListener("click", function () {
      window.fabricaLeadModal.open(null, "Lead novo");
    });
  }

  document.querySelectorAll(".lead-row").forEach(function (row) {
    row.addEventListener("click", function () {
      try {
        var lead = JSON.parse(row.getAttribute("data-lead"));
        window.fabricaLeadModal.open(lead);
      } catch (err) { /* ignore malformed data */ }
    });
  });

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
