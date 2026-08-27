"""
Automações da Fábrica CRM: resumo diário por e-mail e captura de leads via webhook.

Para o resumo por e-mail funcionar, defina estas variáveis de ambiente (num arquivo
.env carregado pelo run.sh, ou exportadas no shell antes de rodar):

    FABRICA_SMTP_HOST=smtp.gmail.com
    FABRICA_SMTP_PORT=587
    FABRICA_SMTP_USER=seuemail@gmail.com
    FABRICA_SMTP_PASSWORD=senha-de-app-do-gmail   # não é a senha normal, é uma "senha de app"
    FABRICA_DIGEST_TO=arthur@exemplo.com,cris@exemplo.com,amanda@exemplo.com
    FABRICA_APP_URL=http://localhost:5050

Sem essas variáveis configuradas, o envio é ignorado silenciosamente (só loga um aviso) —
o resto do CRM continua funcionando normalmente.

Para automatizar o disparo diário, agende este script no cron/launchd:
    0 8 * * 1-5  cd /caminho/para/fabrica-crm && venv/bin/python3 send_digest.py
"""
import os
import smtplib
import sqlite3
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

DB_PATH = os.environ.get("FABRICA_DB_PATH", os.path.join(BASE_DIR, "fabrica.db"))

STALE_DAYS = int(os.environ.get("FABRICA_STALE_DAYS", "7"))


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _dias_parado(etapa_changed_at, today):
    if not etapa_changed_at:
        return 0
    try:
        changed = datetime.fromisoformat(etapa_changed_at).date()
    except ValueError:
        return 0
    return max(0, (today - changed).days)


def digest_data():
    """Monta o resumo do dia: follow-ups de hoje, atrasados e leads parados."""
    db = _db()
    today = date.today()
    today_str = today.isoformat()
    leads = [dict(r) for r in db.execute(
        "SELECT * FROM leads WHERE etapa NOT IN ('Fechado (Ganho)', 'Fechado (Perdido)')"
    ).fetchall()]
    db.close()

    hoje = [l for l in leads if l["proximo_follow_up"] == today_str]
    atrasados = sorted(
        [l for l in leads if l["proximo_follow_up"] and l["proximo_follow_up"] < today_str],
        key=lambda l: l["proximo_follow_up"],
    )
    parados = sorted(
        [l for l in leads if _dias_parado(l["etapa_changed_at"], today) >= STALE_DAYS],
        key=lambda l: _dias_parado(l["etapa_changed_at"], today),
        reverse=True,
    )
    return {"hoje": hoje, "atrasados": atrasados, "parados": parados, "today": today_str}


def render_digest_text(data):
    app_url = os.environ.get("FABRICA_APP_URL", "http://localhost:5050")
    lines = [f"Resumo Fábrica CRM — {data['today']}", ""]

    lines.append(f"FOLLOW-UPS DE HOJE ({len(data['hoje'])})")
    if data["hoje"]:
        for l in data["hoje"]:
            lines.append(f"  - {l['nome']} ({l['etapa']}) · responsável: {l['responsavel'] or '—'}")
    else:
        lines.append("  Nenhum follow-up agendado para hoje.")
    lines.append("")

    lines.append(f"ATRASADOS ({len(data['atrasados'])})")
    if data["atrasados"]:
        for l in data["atrasados"]:
            lines.append(f"  - {l['nome']} ({l['etapa']}) · venceu em {l['proximo_follow_up']} · responsável: {l['responsavel'] or '—'}")
    else:
        lines.append("  Nenhum, tudo em dia.")
    lines.append("")

    lines.append(f"PARADOS HÁ {STALE_DAYS}+ DIAS NA MESMA ETAPA ({len(data['parados'])})")
    if data["parados"]:
        for l in data["parados"]:
            lines.append(f"  - {l['nome']} ({l['etapa']}) · responsável: {l['responsavel'] or '—'}")
    else:
        lines.append("  Nenhum lead parado.")
    lines.append("")
    lines.append(f"Ver tudo: {app_url}/painel")
    return "\n".join(lines)


def send_digest_email():
    host = os.environ.get("FABRICA_SMTP_HOST")
    port = int(os.environ.get("FABRICA_SMTP_PORT", "587"))
    user = os.environ.get("FABRICA_SMTP_USER")
    password = os.environ.get("FABRICA_SMTP_PASSWORD")
    to_raw = os.environ.get("FABRICA_DIGEST_TO", "")
    recipients = [addr.strip() for addr in to_raw.split(",") if addr.strip()]

    if not (host and user and password and recipients):
        return {"ok": False, "reason": "E-mail não configurado (veja automations.py para as variáveis de ambiente necessárias)."}

    data = digest_data()
    body = render_digest_text(data)

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    total_pendencias = len(data["hoje"]) + len(data["atrasados"])
    msg["Subject"] = f"Fábrica CRM — {total_pendencias} follow-up(s) hoje/atrasado(s)"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, recipients, msg.as_string())
    except Exception as exc:
        return {"ok": False, "reason": f"Falha ao enviar: {exc}"}

    return {"ok": True, "recipients": recipients, "total": total_pendencias}


# ---------------------------------------------------------------- webhook (captura de leads)
import uuid  # noqa: E402


def create_lead_from_webhook(payload):
    """Cria um lead a partir de dados externos (formulário de aplicação, Zapier, etc).
    Aceita nomes de campo em português (nome, area, telefone, ticket, origem) e
    tenta mapear variações comuns (name, phone, whatsapp, empresa/area_atuacao)."""
    def pick(*keys):
        for k in keys:
            if payload.get(k):
                return payload.get(k)
        return ""

    nome = pick("nome", "name", "full_name")
    if not nome:
        return None, "Campo 'nome' é obrigatório."

    db = _db()
    now = datetime.utcnow().isoformat()
    lead_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO leads (id, nome, area, origem, telefone, ticket, responsavel, etapa, etapa_changed_at,"
        " ultimo_contato, proximo_follow_up, notas, motivo_perda, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            lead_id,
            nome,
            pick("area", "area_atuacao", "especialidade"),
            pick("origem", "source") or "Formulário de aplicação",
            pick("telefone", "phone", "whatsapp", "numero"),
            int(pick("ticket") or 0),
            "",
            "Lead novo",
            now,
            None, None,
            pick("notas", "mensagem", "message"),
            "",
            now, now,
        ),
    )
    db.execute(
        "INSERT INTO activity_log (id, lead_id, campo, valor_antigo, valor_novo, autor, created_at) VALUES (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), lead_id, "criação", None, "Lead criado via formulário externo", "Webhook", now),
    )
    db.commit()
    row = dict(db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone())
    db.close()
    return row, None
