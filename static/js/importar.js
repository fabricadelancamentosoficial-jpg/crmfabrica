(function () {
  "use strict";

  var fileInput = document.getElementById("import-file");
  var dropzone = document.getElementById("import-dropzone");
  var stepUpload = document.getElementById("import-step-upload");
  var stepMapping = document.getElementById("import-step-mapping");
  if (!fileInput || !dropzone) return;

  var CAMPOS = [
    { chave: "nome", label: "Nome", obrigatorio: true, aliases: ["nome", "name", "nome completo", "full name", "fullname", "nome do lead", "lead name"] },
    { chave: "telefone", label: "Telefone / WhatsApp", obrigatorio: false, aliases: ["telefone", "phone", "celular", "whatsapp", "phone number", "numero", "número", "tel"] },
    { chave: "area", label: "Área de atuação", obrigatorio: false, aliases: ["area", "área", "area de atuacao", "área de atuação", "especialidade", "profissao", "profissão", "categoria"] },
    { chave: "origem", label: "Origem", obrigatorio: false, aliases: ["origem", "source", "campanha", "campaign name", "campaign_name", "ad name", "ad_name", "anuncio", "anúncio"] },
    { chave: "ticket", label: "Ticket proposto", obrigatorio: false, aliases: ["ticket", "valor", "budget", "orcamento", "orçamento"] },
    { chave: "responsavel", label: "Responsável", obrigatorio: false, aliases: ["responsavel", "responsável", "owner", "dono"] },
    { chave: "notas", label: "Notas", obrigatorio: false, aliases: ["notas", "observacoes", "observações", "mensagem", "message", "comentario", "comentário"] },
  ];

  var headers = [];
  var rows = [];

  function normalizar(s) {
    return (s || "")
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function parseCSV(texto) {
    if (texto.charCodeAt(0) === 0xfeff) texto = texto.slice(1);
    var delimitador = (texto.split("\n")[0].split(";").length > texto.split("\n")[0].split(",").length) ? ";" : ",";
    var linhas = [];
    var linhaAtual = [];
    var campoAtual = "";
    var dentroAspas = false;
    for (var i = 0; i < texto.length; i++) {
      var c = texto[i];
      if (dentroAspas) {
        if (c === '"') {
          if (texto[i + 1] === '"') { campoAtual += '"'; i++; }
          else { dentroAspas = false; }
        } else {
          campoAtual += c;
        }
      } else if (c === '"') {
        dentroAspas = true;
      } else if (c === delimitador) {
        linhaAtual.push(campoAtual);
        campoAtual = "";
      } else if (c === "\n" || c === "\r") {
        if (c === "\r" && texto[i + 1] === "\n") i++;
        linhaAtual.push(campoAtual);
        campoAtual = "";
        if (linhaAtual.some(function (v) { return v !== ""; })) linhas.push(linhaAtual);
        linhaAtual = [];
      } else {
        campoAtual += c;
      }
    }
    if (campoAtual !== "" || linhaAtual.length) {
      linhaAtual.push(campoAtual);
      if (linhaAtual.some(function (v) { return v !== ""; })) linhas.push(linhaAtual);
    }
    return linhas;
  }

  function melhorAlias(cabecalhos, aliases) {
    var normalizados = cabecalhos.map(normalizar);
    for (var i = 0; i < aliases.length; i++) {
      var idx = normalizados.indexOf(aliases[i]);
      if (idx !== -1) return cabecalhos[idx];
    }
    return "";
  }

  function montarMapeamento() {
    var wrap = document.getElementById("import-mapping-fields");
    wrap.innerHTML = "";
    CAMPOS.forEach(function (campo) {
      var div = document.createElement("div");
      div.className = "import-mapping-field";
      var label = document.createElement("label");
      label.textContent = campo.label + (campo.obrigatorio ? " *" : "");
      var select = document.createElement("select");
      select.id = "map-" + campo.chave;
      var optVazia = document.createElement("option");
      optVazia.value = "";
      optVazia.textContent = "— não importar —";
      select.appendChild(optVazia);
      headers.forEach(function (h) {
        var opt = document.createElement("option");
        opt.value = h;
        opt.textContent = h;
        select.appendChild(opt);
      });
      var sugestao = melhorAlias(headers, campo.aliases);
      if (sugestao) select.value = sugestao;
      div.appendChild(label);
      div.appendChild(select);
      wrap.appendChild(div);
    });
  }

  function montarPreview() {
    var table = document.getElementById("import-preview-table");
    var thead = table.querySelector("thead");
    var tbody = table.querySelector("tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    var trh = document.createElement("tr");
    headers.forEach(function (h) {
      var th = document.createElement("th");
      th.textContent = h;
      trh.appendChild(th);
    });
    thead.appendChild(trh);

    rows.slice(0, 5).forEach(function (row) {
      var tr = document.createElement("tr");
      headers.forEach(function (h, i) {
        var td = document.createElement("td");
        td.textContent = row[i] || "";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function processarArquivo(file) {
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function (e) {
      var linhas = parseCSV(String(e.target.result));
      if (linhas.length < 1) {
        window.fabricaToast("Esse arquivo parece vazio.");
        return;
      }
      headers = linhas[0];
      rows = linhas.slice(1);
      document.getElementById("import-summary").textContent =
        rows.length + " linha" + (rows.length === 1 ? "" : "s") + " encontrada" + (rows.length === 1 ? "" : "s") + " em \"" + file.name + "\"";
      montarMapeamento();
      montarPreview();
      stepUpload.style.display = "none";
      stepMapping.style.display = "";
    };
    reader.onerror = function () {
      window.fabricaToast("Não consegui ler esse arquivo.");
    };
    reader.readAsText(file, "UTF-8");
  }

  dropzone.addEventListener("click", function (e) {
    if (e.target !== fileInput) fileInput.click();
  });
  fileInput.addEventListener("change", function () {
    if (fileInput.files[0]) processarArquivo(fileInput.files[0]);
  });
  ["dragover", "dragenter"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });
  dropzone.addEventListener("drop", function (e) {
    var file = e.dataTransfer.files[0];
    if (file) processarArquivo(file);
  });

  var btnCancelar = document.getElementById("btn-import-cancelar");
  if (btnCancelar) {
    btnCancelar.addEventListener("click", function () {
      fileInput.value = "";
      stepMapping.style.display = "none";
      stepUpload.style.display = "";
    });
  }

  var btnConfirmar = document.getElementById("btn-import-confirmar");
  if (btnConfirmar) {
    btnConfirmar.addEventListener("click", function () {
      var indice = {};
      CAMPOS.forEach(function (campo) {
        var select = document.getElementById("map-" + campo.chave);
        var col = select.value;
        indice[campo.chave] = col ? headers.indexOf(col) : -1;
      });

      if (indice.nome === -1) {
        window.fabricaToast("Escolha qual coluna é o Nome.");
        return;
      }

      var origemPadrao = document.getElementById("import-origem-padrao").value.trim();
      var responsavelPadrao = document.getElementById("import-responsavel-padrao").value;
      var pularDuplicados = document.getElementById("import-pular-duplicados").checked;

      var leads = rows.map(function (row) {
        function valor(chave) {
          var i = indice[chave];
          return i !== -1 && row[i] !== undefined ? row[i].trim() : "";
        }
        return {
          nome: valor("nome"),
          telefone: valor("telefone"),
          area: valor("area"),
          origem: valor("origem") || origemPadrao,
          ticket: valor("ticket"),
          responsavel: valor("responsavel") || responsavelPadrao,
          notas: valor("notas"),
        };
      }).filter(function (l) { return l.nome; });

      if (!leads.length) {
        window.fabricaToast("Nenhuma linha com nome preenchido.");
        return;
      }

      btnConfirmar.disabled = true;
      btnConfirmar.textContent = "Importando...";

      fetch("/api/leads/importar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leads: leads, pular_duplicados: pularDuplicados }),
      })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.ok) {
            var msg = res.criados + " lead" + (res.criados === 1 ? "" : "s") + " importado" + (res.criados === 1 ? "" : "s") + ".";
            if (res.duplicados) msg += " " + res.duplicados + " já existia(m) e foi(ram) pulado(s).";
            if (res.sem_nome) msg += " " + res.sem_nome + " linha(s) sem nome foram ignoradas.";
            window.fabricaToast(msg);
            setTimeout(function () { window.location.href = "/leads"; }, 1600);
          } else {
            window.fabricaToast("Não consegui importar.");
            btnConfirmar.disabled = false;
            btnConfirmar.textContent = "Importar leads";
          }
        })
        .catch(function () {
          window.fabricaToast("Não consegui importar.");
          btnConfirmar.disabled = false;
          btnConfirmar.textContent = "Importar leads";
        });
    });
  }
})();
