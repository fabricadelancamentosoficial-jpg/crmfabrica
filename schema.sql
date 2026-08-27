CREATE TABLE IF NOT EXISTS leads (
  id TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  area TEXT DEFAULT '',
  origem TEXT DEFAULT '',
  telefone TEXT DEFAULT '',
  ticket INTEGER NOT NULL DEFAULT 0,
  responsavel TEXT DEFAULT '',
  etapa TEXT NOT NULL DEFAULT 'Lead novo',
  etapa_changed_at TEXT,
  ultimo_contato TEXT,
  proximo_follow_up TEXT,
  notas TEXT DEFAULT '',
  motivo_perda TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
  id TEXT PRIMARY KEY,
  lead_id TEXT NOT NULL,
  campo TEXT NOT NULL,
  valor_antigo TEXT,
  valor_novo TEXT,
  autor TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_activity_lead ON activity_log(lead_id);
