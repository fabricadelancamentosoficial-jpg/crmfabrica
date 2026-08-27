(function () {
  "use strict";

  var novoBtn = document.getElementById("btn-novo-lead");
  if (novoBtn) {
    novoBtn.addEventListener("click", function () {
      window.fabricaLeadModal.open(null, "Lead novo");
    });
  }

  var dragSourceCard = null;
  var dragMoved = false;

  document.querySelectorAll(".lead-card").forEach(function (card) {
    card.addEventListener("dragstart", function (e) {
      dragSourceCard = card;
      dragMoved = false;
      card.classList.add("dragging");
      e.dataTransfer.setData("text/plain", card.getAttribute("data-id"));
      e.dataTransfer.effectAllowed = "move";
    });
    card.addEventListener("dragend", function () {
      card.classList.remove("dragging");
      dragSourceCard = null;
    });
    card.addEventListener("click", function (e) {
      if (dragMoved) { dragMoved = false; return; }
      try {
        var lead = JSON.parse(card.getAttribute("data-lead"));
        window.fabricaLeadModal.open(lead);
      } catch (err) { /* ignore malformed data */ }
    });
  });

  document.querySelectorAll(".column-drop").forEach(function (dropzone) {
    dropzone.addEventListener("dragover", function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      dropzone.classList.add("drag-over");
    });
    dropzone.addEventListener("dragleave", function () {
      dropzone.classList.remove("drag-over");
    });
    dropzone.addEventListener("drop", function (e) {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      var id = e.dataTransfer.getData("text/plain");
      var card = document.querySelector('.lead-card[data-id="' + id + '"]');
      if (!card) return;
      var newEtapa = dropzone.getAttribute("data-etapa");
      var oldEtapa = card.getAttribute("data-etapa");
      if (newEtapa === oldEtapa) return;

      dragMoved = true;
      var emptyMsg = dropzone.querySelector(".column-empty");
      if (emptyMsg) emptyMsg.remove();
      dropzone.appendChild(card);
      card.setAttribute("data-etapa", newEtapa);

      fetch("/api/leads/" + id, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ etapa: newEtapa }),
      })
        .then(function (r) {
          if (!r.ok) throw new Error("update failed");
          window.fabricaToast('Movido para "' + newEtapa + '"');
          setTimeout(function () { location.reload(); }, 450);
        })
        .catch(function () {
          window.fabricaToast("Não consegui mover o lead. Recarregando...");
          setTimeout(function () { location.reload(); }, 800);
        });
    });
  });

  var searchInput = document.getElementById("pipeline-search");
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      var q = searchInput.value.trim().toLowerCase();
      document.querySelectorAll(".lead-card").forEach(function (card) {
        var match = !q || card.getAttribute("data-nome").indexOf(q) !== -1;
        card.style.display = match ? "" : "none";
      });
    });
  }
})();
