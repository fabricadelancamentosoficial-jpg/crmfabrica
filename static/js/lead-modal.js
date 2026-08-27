(function () {
  "use strict";
  var backdrop = document.getElementById("lead-modal-backdrop");
  if (!backdrop) return;

  var form = document.getElementById("lead-form");
  var titleEl = document.getElementById("lead-modal-title");
  var idInput = document.getElementById("f-id");
  var deleteBtn = document.getElementById("lead-delete-btn");
  var etapaSelect = document.getElementById("f-etapa");
  var motivoWrap = document.getElementById("f-motivo-wrap");
  var telefoneInput = document.getElementById("f-telefone");
  var whatsappLink = document.getElementById("f-whatsapp-link");
  var historyWrap = document.getElementById("f-history-wrap");
  var historyList = document.getElementById("f-history-list");

  function toggleMotivo() {
    motivoWrap.style.display = etapaSelect.value === "Fechado (Perdido)" ? "flex" : "none";
  }
  etapaSelect.addEventListener("change", toggleMotivo);

  function updateWhatsappLink() {
    var digits = telefoneInput.value.replace(/\D/g, "");
    if (digits) {
      whatsappLink.href = "https://wa.me/" + digits;
      whatsappLink.style.display = "flex";
    } else {
      whatsappLink.style.display = "none";
    }
  }
  telefoneInput.addEventListener("input", updateWhatsappLink);

  function timeAgo(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }

  function loadHistory(leadId) {
    historyWrap.style.display = "flex";
    historyList.innerHTML = '<div class="history-empty">Carregando...</div>';
    fetch("/api/leads/" + leadId + "/activity")
      .then(function (r) { return r.json(); })
      .then(function (items) {
        if (!items.length) {
          historyList.innerHTML = '<div class="history-empty">Sem histórico ainda.</div>';
          return;
        }
        historyList.innerHTML = items.map(function (it) {
          var texto = it.campo === "criação"
            ? it.valor_novo
            : (it.campo + ": " + (it.valor_antigo || "vazio") + " → " + (it.valor_novo || "vazio"));
          return '<div class="history-item"><div class="history-txt">' + texto +
            '</div><div class="history-meta">' + (it.autor || "—") + " · " + timeAgo(it.created_at) + "</div></div>";
        }).join("");
      })
      .catch(function () {
        historyList.innerHTML = '<div class="history-empty">Não consegui carregar o histórico.</div>';
      });
  }

  function open(lead, etapaDefault) {
    form.reset();
    if (lead) {
      titleEl.textContent = "Editar lead";
      idInput.value = lead.id;
      document.getElementById("f-nome").value = lead.nome || "";
      document.getElementById("f-area").value = lead.area || "";
      document.getElementById("f-origem").value = lead.origem || "";
      telefoneInput.value = lead.telefone || "";
      document.getElementById("f-ticket").value = lead.ticket || 0;
      document.getElementById("f-responsavel").value = lead.responsavel || "";
      document.getElementById("f-etapa").value = lead.etapa || "Lead novo";
      document.getElementById("f-ultimo-contato").value = lead.ultimo_contato || "";
      var proximo = lead.proximo_follow_up || "";
      if (proximo && proximo.indexOf("T") === -1) proximo += "T09:00";
      document.getElementById("f-proximo-follow-up").value = proximo;
      document.getElementById("f-notas").value = lead.notas || "";
      document.getElementById("f-motivo-perda").value = lead.motivo_perda || "";
      deleteBtn.style.display = "inline-flex";
      loadHistory(lead.id);
    } else {
      titleEl.textContent = "Novo lead";
      idInput.value = "";
      etapaSelect.value = etapaDefault || "Lead novo";
      document.getElementById("f-ticket").value = 0;
      deleteBtn.style.display = "none";
      historyWrap.style.display = "none";
    }
    updateWhatsappLink();
    toggleMotivo();
    backdrop.classList.add("visible");
    document.getElementById("f-nome").focus();
  }

  function close() {
    backdrop.classList.remove("visible");
  }

  document.getElementById("lead-modal-close").addEventListener("click", close);
  document.getElementById("lead-cancel-btn").addEventListener("click", close);
  backdrop.addEventListener("click", function (e) {
    if (e.target === backdrop) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var id = idInput.value;
    var payload = {
      nome: document.getElementById("f-nome").value.trim(),
      area: document.getElementById("f-area").value.trim(),
      origem: document.getElementById("f-origem").value.trim(),
      telefone: telefoneInput.value.trim(),
      ticket: parseInt(document.getElementById("f-ticket").value || "0", 10),
      responsavel: document.getElementById("f-responsavel").value,
      etapa: document.getElementById("f-etapa").value,
      ultimo_contato: document.getElementById("f-ultimo-contato").value || null,
      proximo_follow_up: document.getElementById("f-proximo-follow-up").value || null,
      notas: document.getElementById("f-notas").value.trim(),
      motivo_perda: document.getElementById("f-motivo-perda").value.trim(),
    };
    if (!payload.nome) {
      window.fabricaToast("Dê um nome ao lead.");
      return;
    }
    var url = id ? "/api/leads/" + id : "/api/leads";
    var method = id ? "PATCH" : "POST";
    fetch(url, { method: method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
      .then(function (r) {
        if (!r.ok) throw new Error("save failed");
        return r.json();
      })
      .then(function (saved) {
        window.fabricaToast(saved.aviso_agenda || (id ? "Lead atualizado" : "Lead criado"));
        setTimeout(function () { location.reload(); }, saved.aviso_agenda ? 1800 : 350);
      })
      .catch(function () {
        window.fabricaToast("Não consegui salvar. Tente de novo.");
      });
  });

  deleteBtn.addEventListener("click", function () {
    var id = idInput.value;
    if (!id) return;
    if (!confirm("Excluir este lead? Essa ação não pode ser desfeita.")) return;
    fetch("/api/leads/" + id, { method: "DELETE" })
      .then(function (r) {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(function () {
        window.fabricaToast("Lead excluído");
        setTimeout(function () { location.reload(); }, 350);
      })
      .catch(function () {
        window.fabricaToast("Não consegui excluir.");
      });
  });

  window.fabricaLeadModal = { open: open, close: close };
})();
