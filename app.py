import csv
import os
import sqlite3
import uuid
from datetime import datetime, date, timedelta
from functools import wraps
from io import StringIO
from urllib.parse import quote

from flask import Flask, g, render_template, request, session, redirect, url_for, jsonify, make_response

import automations

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def load_dotenv():
    """Lê um .env simples (KEY=VALUE por linha) sem precisar instalar nada."""
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


load_dotenv()

# Em produção (Railway/Render/Fly), aponte FABRICA_DB_PATH para o disco persistente
# (ex: /data/fabrica.db) — senão o banco some a cada novo deploy.
DB_PATH = os.environ.get("FABRICA_DB_PATH", os.path.join(BASE_DIR, "fabrica.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FABRICA_SECRET_KEY", "dev-secret-troque-em-producao")

CRM_PASSWORD = os.environ.get("FABRICA_CRM_PASSWORD", "fabrica2026")
RESPONSAVEIS_PADRAO = ["Arthur", "Cris", "Amanda"]
ETAPAS = [
    "Lead novo",
    "Qualificação",
    "Reunião agendada",
    "Reunião realizada",
    "Proposta enviada",
    "Em negociação",
    "Fechado (Ganho)",
    "Fechado (Perdido)",
    "Onboarding",
]
ETAPAS_ATIVAS = [e for e in ETAPAS if e not in ("Fechado (Ganho)", "Fechado (Perdido)")]
ETAPA_SLUG = {
    "Lead novo": "novo",
    "Qualificação": "qualif",
    "Reunião agendada": "reuniao-ag",
    "Reunião realizada": "reuniao-real",
    "Proposta enviada": "proposta",
    "Em negociação": "negociacao",
    "Fechado (Ganho)": "ganho",
    "Fechado (Perdido)": "perdido",
    "Onboarding": "onboarding",
}


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def get_meta_mes(db, mes):
    row = db.execute("SELECT valor_meta FROM metas_mensais WHERE mes = ?", (mes,)).fetchone()
    return row["valor_meta"] if row else 0


def get_responsaveis(db, apenas_ativos=True):
    sql = "SELECT nome FROM responsaveis"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY created_at"
    return [r["nome"] for r in db.execute(sql).fetchall()]


def seed_responsaveis(db):
    """Cria os responsáveis padrão só se a tabela ainda estiver vazia (nunca sobrescreve edições)."""
    total = db.execute("SELECT COUNT(*) FROM responsaveis").fetchone()[0]
    if total > 0:
        return
    now = datetime.utcnow().isoformat()
    for nome in RESPONSAVEIS_PADRAO:
        db.execute(
            "INSERT INTO responsaveis (id, nome, ativo, created_at) VALUES (?,?,1,?)",
            (str(uuid.uuid4()), nome, now),
        )
    db.commit()


def init_db():
    is_new = not os.path.exists(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())
    db.commit()
    migrate_db(db)
    seed_responsaveis(db)
    if is_new:
        seed_db(db)
    db.close()


def migrate_db(db):
    """Adiciona colunas novas a bancos já existentes, sem apagar nada."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(leads)").fetchall()}
    try:
        if "telefone" not in cols:
            db.execute("ALTER TABLE leads ADD COLUMN telefone TEXT DEFAULT ''")
        if "etapa_changed_at" not in cols:
            db.execute("ALTER TABLE leads ADD COLUMN etapa_changed_at TEXT")
            db.execute("UPDATE leads SET etapa_changed_at = created_at WHERE etapa_changed_at IS NULL")
        db.commit()
    except sqlite3.OperationalError:
        # outro worker do gunicorn já aplicou essa migração ao mesmo tempo
        db.rollback()


def seed_db(db):
    now = datetime.utcnow().isoformat()
    demo = [
        ("Dra. Camila Rezende", "Dermatologia", "Formulário de aplicação", "5548999110022", 12000, "Amanda", "Reunião agendada", "2026-08-20", "2026-08-25", "", "", 2),
        ("Dr. Henrique Souza", "Odontologia", "Formulário de aplicação", "5548999110023", 15000, "Arthur", "Proposta enviada", "2026-08-22", "2026-08-25", "", "", 3),
        ("Dra. Marina Costa", "Advocacia Tributária", "Indicação", "5548999110024", 10000, "Amanda", "Qualificação", "2026-08-23", "2026-08-26", "", "", 9),
        ("Dr. Rafael Lima", "Ortopedia", "Formulário de aplicação", "5548999110025", 13500, "Arthur", "Em negociação", "2026-08-21", "2026-08-27", "", "", 1),
        ("Dra. Beatriz Nogueira", "Nutrologia", "Instagram", "5548999110026", 11000, "Cris", "Reunião realizada", "2026-08-19", "2026-08-28", "", "", 6),
        ("Dr. Thiago Andrade", "Odontologia", "Formulário de aplicação", "5548999110027", 14000, "Amanda", "Lead novo", "2026-08-24", "2026-08-26", "", "", 1),
        ("Dra. Larissa Prado", "Ginecologia", "Formulário de aplicação", "5548999110028", 12500, "Amanda", "Lead novo", "2026-08-24", "2026-08-27", "", "", 1),
        ("Dr. Eduardo Chaves", "Advocacia Empresarial", "Indicação", "5548999110029", 11000, "Amanda", "Lead novo", "2026-08-24", "2026-08-28", "", "", 11),
        ("Dr. Fernando Melo", "Consultoria Empresarial", "Instagram", "5548999110030", 9000, "Amanda", "Qualificação", "2026-08-22", "2026-08-27", "", "", 4),
        ("Dr. Rodrigo Fialho", "Odontologia", "Formulário de aplicação", "5548999110031", 13000, "Cris", "Reunião agendada", "2026-08-23", "2026-08-29", "", "", 2),
        ("Dr. Gustavo Prado", "Ortopedia", "Indicação", "5548999110032", 15000, "Arthur", "Reunião realizada", "2026-08-20", "2026-08-30", "", "", 5),
        ("Dra. Juliana Ramos", "Dermatologia", "Formulário de aplicação", "5548999110033", 16000, "Arthur", "Proposta enviada", "2026-08-18", "2026-09-01", "", "", 8),
        ("Dra. Patrícia Lemos", "Cirurgia Plástica", "Indicação", "5548999110034", 18000, "Cris", "Fechado (Ganho)", "2026-08-15", None, "", "", 5),
        ("Dr. Marcelo Duarte", "Odontologia", "Formulário de aplicação", "5548999110035", 9500, "Amanda", "Fechado (Perdido)", "2026-08-12", None, "", "Orçamento", 8),
        ("Dr. André Bittencourt", "Advocacia", "Formulário de aplicação", "5548999110036", 14500, "Arthur", "Onboarding", "2026-08-20", None, "", "", 4),
    ]
    for nome, area, origem, telefone, ticket, resp, etapa, ultimo, proximo, notas, motivo, dias_atras in demo:
        lead_id = str(uuid.uuid4())
        changed_at = (datetime.utcnow() - timedelta(days=dias_atras)).isoformat()
        db.execute(
            "INSERT INTO leads (id, nome, area, origem, telefone, ticket, responsavel, etapa, etapa_changed_at,"
            " ultimo_contato, proximo_follow_up, notas, motivo_perda, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lead_id, nome, area, origem, telefone, ticket, resp, etapa, changed_at, ultimo, proximo, notas, motivo, now, now),
        )
        log_activity(db, lead_id, "criação", None, "Lead criado (dado de exemplo)", "Sistema", commit=False)
    db.commit()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


def log_activity(db, lead_id, campo, valor_antigo, valor_novo, autor, commit=True):
    db.execute(
        "INSERT INTO activity_log (id, lead_id, campo, valor_antigo, valor_novo, autor, created_at) VALUES (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), lead_id, campo, valor_antigo, valor_novo, autor, datetime.utcnow().isoformat()),
    )
    if commit:
        db.commit()


CAMPO_LABELS = {
    "nome": "Nome", "area": "Área de atuação", "origem": "Origem", "telefone": "Telefone",
    "ticket": "Ticket proposto", "responsavel": "Responsável", "etapa": "Etapa",
    "ultimo_contato": "Último contato", "proximo_follow_up": "Próximo follow-up",
    "notas": "Notas", "motivo_perda": "Motivo da perda",
}


def dias_parado(etapa_changed_at, today_str):
    if not etapa_changed_at:
        return 0
    try:
        changed = datetime.fromisoformat(etapa_changed_at).date()
        today = datetime.strptime(today_str, "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max(0, (today - changed).days)


STALE_DAYS = int(os.environ.get("FABRICA_STALE_DAYS", "7"))

# --- agendamento inteligente ---
AGENDA_INICIO = os.environ.get("FABRICA_AGENDA_INICIO", "09:00")
AGENDA_FIM = os.environ.get("FABRICA_AGENDA_FIM", "18:00")
AGENDA_DURACAO_MIN = int(os.environ.get("FABRICA_AGENDA_DURACAO_MIN", "60"))
AGENDA_DIAS = {int(d) for d in os.environ.get("FABRICA_AGENDA_DIAS", "0,1,2,3,4").split(",")}  # 0=segunda


def checar_agenda(db, responsavel, proximo_follow_up, lead_id=None):
    """Verifica conflito de horário e janela de atendimento. Retorna um aviso (string) ou None.
    Nunca bloqueia o salvamento — é um alerta, a pessoa decide."""
    if not proximo_follow_up or "T" not in proximo_follow_up or not responsavel:
        return None
    try:
        alvo = datetime.fromisoformat(proximo_follow_up)
    except ValueError:
        return None

    if alvo.weekday() not in AGENDA_DIAS:
        dias_semana = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
        return f"{dias_semana[alvo.weekday()]} não está nos dias de atendimento configurados."

    hora_inicio = datetime.strptime(AGENDA_INICIO, "%H:%M").time()
    hora_fim = datetime.strptime(AGENDA_FIM, "%H:%M").time()
    if not (hora_inicio <= alvo.time() <= hora_fim):
        return f"Fora do horário de atendimento ({AGENDA_INICIO}–{AGENDA_FIM})."

    janela_inicio = (alvo - timedelta(minutes=AGENDA_DURACAO_MIN - 1)).isoformat()
    janela_fim = (alvo + timedelta(minutes=AGENDA_DURACAO_MIN - 1)).isoformat()
    sql = (
        "SELECT nome, proximo_follow_up FROM leads WHERE responsavel = ? AND proximo_follow_up BETWEEN ? AND ?"
        " AND etapa NOT IN ('Fechado (Ganho)', 'Fechado (Perdido)')"
    )
    params = [responsavel, janela_inicio, janela_fim]
    if lead_id:
        sql += " AND id != ?"
        params.append(lead_id)
    conflito = db.execute(sql, params).fetchone()
    if conflito:
        return f"{responsavel} já tem {conflito['nome']} marcado perto desse horário ({conflito['proximo_follow_up'][11:16]})."
    return None


def fmt_brl(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return "R$ 0"
    return "R$ " + f"{value:,}".replace(",", ".")


def fmt_br_date(date_str):
    if not date_str:
        return "—"
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return date_str
    return d.strftime("%d/%m")


def relative_label(date_str, today_str):
    if not date_str:
        return {"label": "—", "state": "none"}
    tem_hora = "T" in date_str
    try:
        if tem_hora:
            dt = datetime.fromisoformat(date_str)
            d = dt.date()
            hora_txt = dt.strftime("%Hh%M")
        else:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            hora_txt = None
        today = datetime.strptime(today_str, "%Y-%m-%d").date()
    except ValueError:
        return {"label": date_str, "state": "none"}
    delta = (d - today).days
    sufixo = f", {hora_txt}" if hora_txt else ""
    if delta < 0:
        n = abs(delta)
        return {"label": f"Atrasado há {n} dia{'s' if n != 1 else ''}", "state": "late"}
    if delta == 0:
        return {"label": f"Hoje{sufixo}", "state": "today"}
    if delta == 1:
        return {"label": f"Amanhã{sufixo}", "state": "future"}
    if delta <= 6:
        return {"label": f"Em {delta} dias{sufixo}", "state": "future"}
    return {"label": d.strftime("%d/%m") + sufixo, "state": "future"}


@app.template_filter("brl")
def brl_filter(value):
    return fmt_brl(value)


@app.template_filter("brdate")
def brdate_filter(value):
    return fmt_br_date(value)


@app.template_filter("walink")
def walink_filter(telefone):
    digits = "".join(ch for ch in (telefone or "") if ch.isdigit())
    return f"https://wa.me/{digits}" if digits else ""


@app.template_filter("walink_msg")
def walink_msg_filter(telefone, texto=""):
    digits = "".join(ch for ch in (telefone or "") if ch.isdigit())
    if not digits:
        return ""
    if texto:
        return f"https://wa.me/{digits}?text={quote(texto)}"
    return f"https://wa.me/{digits}"


TITULOS_IGNORAR = {"dr.", "dr", "dra.", "dra", "sr.", "sr", "sra.", "sra"}


def sugerir_mensagem_boas_vindas(lead):
    """Mensagem de boas-vindas personalizada pro primeiro contato — o atendente confere e envia."""
    partes = (lead.get("nome") or "").split(" ")
    partes = [p for p in partes if p.lower() not in TITULOS_IGNORAR]
    primeiro_nome = partes[0] if partes else ""
    area = lead.get("area") or "a sua área"
    saudacao = f"Oi, {primeiro_nome}! " if primeiro_nome else "Oi! "
    return (
        f"{saudacao}Vi que você se aplicou pra estruturar um projeto em {area}. "
        "Recebemos seu contato e em breve alguém do nosso time fala com você por aqui pra entender melhor "
        "o seu momento. Qualquer coisa, é só chamar 🙂"
    )


# ---------------------------------------------------------------- auth
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    responsaveis = get_responsaveis(get_db())
    if request.method == "POST":
        nome = request.form.get("nome", "")
        senha = request.form.get("senha", "")
        if nome not in responsaveis:
            return render_template("login.html", erro="Escolha quem é você.", responsaveis=responsaveis, nome=nome, theme=get_theme()), 400
        if senha != CRM_PASSWORD:
            return render_template("login.html", erro="Senha incorreta.", responsaveis=responsaveis, nome=nome, theme=get_theme()), 401
        session["user"] = nome
        return redirect(url_for("painel"))
    if session.get("user"):
        return redirect(url_for("painel"))
    return render_template("login.html", erro=None, responsaveis=responsaveis, nome=None, theme=get_theme())


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


def get_theme():
    return request.cookies.get("theme", "dark")


# ---------------------------------------------------------------- painel
@app.route("/")
def index():
    return redirect(url_for("painel"))


@app.route("/painel")
@login_required
def painel():
    db = get_db()
    leads = [row_to_dict(r) for r in db.execute("SELECT * FROM leads").fetchall()]

    ativos = [l for l in leads if l["etapa"] not in ("Fechado (Ganho)", "Fechado (Perdido)")]
    ganhos = [l for l in leads if l["etapa"] == "Fechado (Ganho)"]
    perdidos = [l for l in leads if l["etapa"] == "Fechado (Perdido)"]
    fechados_total = len(ganhos) + len(perdidos)

    valor_pipeline = sum(l["ticket"] for l in ativos)
    taxa_conversao = round((len(ganhos) / fechados_total) * 100) if fechados_total else 0

    today = date.today().isoformat()
    atrasados = [l for l in ativos if l["proximo_follow_up"] and l["proximo_follow_up"] < today]

    funil_counts = []
    max_count = 1
    for etapa in ETAPAS_ATIVAS:
        count = sum(1 for l in ativos if l["etapa"] == etapa)
        funil_counts.append({"etapa": etapa, "count": count})
        max_count = max(max_count, count)
    for f in funil_counts:
        f["pct"] = round((f["count"] / max_count) * 100) if max_count else 0

    ticket_medio = round(valor_pipeline / len(ativos)) if ativos else 0

    mes_atual = today[:7]
    ganhos_mes = [l for l in ganhos if (l["etapa_changed_at"] or "").startswith(mes_atual)]
    fechados_mes = len(ganhos_mes)
    valor_faturado_mes = sum(l["ticket"] for l in ganhos_mes)
    meta_mes = get_meta_mes(db, mes_atual)
    pct_meta = round((valor_faturado_mes / meta_mes) * 100) if meta_mes else 0
    mes_label = MESES_PT[int(mes_atual[5:7])]

    proximos = sorted(
        [l for l in ativos if l["proximo_follow_up"]],
        key=lambda l: l["proximo_follow_up"],
    )[:6]
    for l in proximos:
        l.update(relative_label(l["proximo_follow_up"], today))

    carga = []
    for resp in get_responsaveis(db):
        count = sum(1 for l in ativos if l["responsavel"] == resp)
        carga.append({"nome": resp, "count": count})
    max_carga = max((c["count"] for c in carga), default=1) or 1
    for c in carga:
        c["pct"] = round((c["count"] / max_carga) * 100)

    parados = [l for l in ativos if dias_parado(l["etapa_changed_at"], today) >= STALE_DAYS]
    for l in parados:
        l["dias"] = dias_parado(l["etapa_changed_at"], today)
    parados.sort(key=lambda l: l["dias"], reverse=True)
    parados = parados[:6]

    # --- desempenho comercial ---
    def dias_ate_fechar(lead):
        try:
            fim = datetime.fromisoformat(lead["etapa_changed_at"])
            inicio = datetime.fromisoformat(lead["created_at"])
            return max(0, (fim - inicio).days)
        except (TypeError, ValueError):
            return None

    tempos_fechamento = [d for d in (dias_ate_fechar(l) for l in ganhos) if d is not None]
    tempo_medio_fechamento = round(sum(tempos_fechamento) / len(tempos_fechamento)) if tempos_fechamento else None

    ticket_medio_ganho = round(sum(l["ticket"] for l in ganhos) / len(ganhos)) if ganhos else 0
    valor_total_ganho = sum(l["ticket"] for l in ganhos)

    origem_stats = {}
    for l in leads:
        if l["etapa"] not in ("Fechado (Ganho)", "Fechado (Perdido)"):
            continue
        o = l["origem"] or "Sem origem"
        origem_stats.setdefault(o, {"ganho": 0, "total": 0})
        origem_stats[o]["total"] += 1
        if l["etapa"] == "Fechado (Ganho)":
            origem_stats[o]["ganho"] += 1
    melhor_origem = None
    if origem_stats:
        ranked = sorted(
            origem_stats.items(),
            key=lambda kv: (kv[1]["ganho"] / kv[1]["total"], kv[1]["total"]),
            reverse=True,
        )
        nome_origem, dados_origem = ranked[0]
        if dados_origem["ganho"] > 0:
            melhor_origem = {
                "nome": nome_origem,
                "pct": round((dados_origem["ganho"] / dados_origem["total"]) * 100),
                "total": dados_origem["total"],
            }

    return render_template(
        "painel.html",
        user=session["user"],
        theme=get_theme(),
        leads_ativos=len(ativos),
        valor_pipeline=valor_pipeline,
        taxa_conversao=taxa_conversao,
        atrasados_count=len(atrasados),
        funil_counts=funil_counts,
        ticket_medio=ticket_medio,
        fechados_mes=fechados_mes,
        valor_faturado_mes=valor_faturado_mes,
        meta_mes=meta_mes,
        pct_meta=pct_meta,
        mes_label=mes_label,
        proximos=proximos,
        carga=carga,
        parados=parados,
        stale_days=STALE_DAYS,
        tempo_medio_fechamento=tempo_medio_fechamento,
        ticket_medio_ganho=ticket_medio_ganho,
        valor_total_ganho=valor_total_ganho,
        melhor_origem=melhor_origem,
        today=today,
    )


# ---------------------------------------------------------------- atendimento
@app.route("/atendimento")
@login_required
def atendimento():
    db = get_db()
    fila = [row_to_dict(r) for r in db.execute(
        "SELECT * FROM leads WHERE etapa = 'Lead novo' ORDER BY created_at DESC"
    ).fetchall()]
    today_str = date.today().isoformat()
    for l in fila:
        l["dias_na_fila"] = dias_parado(l["created_at"], today_str)

    lead_id = request.args.get("lead") or (fila[0]["id"] if fila else None)
    selecionado = None
    mensagem_sugerida = None
    historico = []
    if lead_id:
        row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if row:
            selecionado = row_to_dict(row)
            mensagem_sugerida = sugerir_mensagem_boas_vindas(selecionado)
            historico = [row_to_dict(r) for r in db.execute(
                "SELECT * FROM activity_log WHERE lead_id = ? ORDER BY created_at DESC", (lead_id,)
            ).fetchall()]

    return render_template(
        "atendimento.html",
        user=session["user"],
        theme=get_theme(),
        fila=fila,
        selecionado=selecionado,
        mensagem_sugerida=mensagem_sugerida,
        historico=historico,
    )


@app.route("/api/atendimento/qualificar-automatico", methods=["POST"])
@login_required
def qualificar_automatico():
    db = get_db()
    ativos = [row_to_dict(r) for r in db.execute(
        "SELECT * FROM leads WHERE etapa NOT IN ('Fechado (Ganho)', 'Fechado (Perdido)')"
    ).fetchall()]
    ticket_medio = round(sum(l["ticket"] for l in ativos) / len(ativos)) if ativos else 0
    novos = [l for l in ativos if l["etapa"] == "Lead novo"]

    autor = session.get("user", "Sistema")
    now = datetime.utcnow().isoformat()
    qualificados = 0
    for l in novos:
        if ticket_medio and l["ticket"] >= ticket_medio:
            db.execute(
                "UPDATE leads SET etapa = 'Qualificação', etapa_changed_at = ?, updated_at = ? WHERE id = ?",
                (now, now, l["id"]),
            )
            log_activity(db, l["id"], "Etapa", "Lead novo", "Qualificação",
                         f"{autor} (automação)", commit=False)
            qualificados += 1
    db.commit()
    return jsonify({
        "ok": True,
        "qualificados": qualificados,
        "total_fila": len(novos),
        "ticket_medio": ticket_medio,
    })


# ---------------------------------------------------------------- pipeline
@app.route("/pipeline")
@login_required
def pipeline():
    db = get_db()
    today = date.today().isoformat()
    leads = [row_to_dict(r) for r in db.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()]
    for l in leads:
        l.update(relative_label(l["proximo_follow_up"], today))
        l["dias_parado"] = dias_parado(l["etapa_changed_at"], today)
        l["stale"] = l["dias_parado"] >= STALE_DAYS and l["etapa"] not in ("Fechado (Ganho)", "Fechado (Perdido)")
    columns = []
    for etapa in ETAPAS:
        col_leads = [l for l in leads if l["etapa"] == etapa]
        columns.append({
            "etapa": etapa,
            "leads": col_leads,
            "total": sum(l["ticket"] for l in col_leads),
        })
    total_ativo = sum(l["ticket"] for l in leads if l["etapa"] not in ("Fechado (Ganho)", "Fechado (Perdido)"))
    return render_template(
        "pipeline.html",
        user=session["user"],
        theme=get_theme(),
        columns=columns,
        etapas=ETAPAS,
        responsaveis=get_responsaveis(db),
        total_leads=len(leads),
        total_ativo=total_ativo,
        today=date.today().isoformat(),
    )


def filtrar_leads(db):
    """Aplica os filtros/ordenação da tela de Leads (usado na listagem e na exportação)."""
    q = request.args.get("q", "").strip()
    etapa_f = request.args.get("etapa", "")
    resp_f = request.args.get("responsavel", "")
    origem_f = request.args.get("origem", "")
    sort = request.args.get("sort", "created_at")
    direction = request.args.get("dir", "desc")

    sql = "SELECT * FROM leads WHERE 1=1"
    params = []
    if q:
        sql += " AND (nome LIKE ? OR area LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if etapa_f:
        sql += " AND etapa = ?"
        params.append(etapa_f)
    if resp_f:
        sql += " AND responsavel = ?"
        params.append(resp_f)
    if origem_f:
        sql += " AND origem = ?"
        params.append(origem_f)

    allowed_sort = {"nome", "ticket", "proximo_follow_up", "ultimo_contato", "created_at"}
    if sort not in allowed_sort:
        sort = "created_at"
    direction = "ASC" if direction == "asc" else "DESC"
    sql += f" ORDER BY {sort} {direction}"

    leads = [row_to_dict(r) for r in db.execute(sql, params).fetchall()]
    return leads, q, etapa_f, resp_f, origem_f, sort, direction


# ---------------------------------------------------------------- leads
@app.route("/leads")
@login_required
def leads_view():
    db = get_db()
    leads, q, etapa_f, resp_f, origem_f, sort, direction = filtrar_leads(db)
    today_str = date.today().isoformat()
    for l in leads:
        l.update(relative_label(l["proximo_follow_up"], today_str))
    origens = [r["origem"] for r in db.execute("SELECT DISTINCT origem FROM leads WHERE origem != ''").fetchall()]

    def sort_link(col):
        new_dir = "asc" if not (sort == col and direction == "ASC") else "desc"
        return url_for("leads_view", q=q, etapa=etapa_f, responsavel=resp_f, origem=origem_f, sort=col, dir=new_dir)

    sort_links = {c: sort_link(c) for c in ("nome", "ticket", "proximo_follow_up")}

    return render_template(
        "leads.html",
        user=session["user"],
        theme=get_theme(),
        leads=leads,
        etapas=ETAPAS,
        responsaveis=get_responsaveis(db),
        origens=origens,
        q=q, etapa_f=etapa_f, resp_f=resp_f, origem_f=origem_f,
        sort=sort, direction=direction.lower(),
        sort_links=sort_links,
        today=date.today().isoformat(),
    )


@app.route("/leads/exportar.csv")
@login_required
def exportar_leads_csv():
    """Exporta os leads (respeitando os filtros atuais da tela) num CSV que abre certinho no Excel."""
    db = get_db()
    leads, *_ = filtrar_leads(db)

    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Nome", "Área de atuação", "Origem", "Telefone", "Ticket proposto", "Responsável",
        "Etapa", "Último contato", "Próximo follow-up", "Notas", "Motivo da perda", "Criado em",
    ])
    for l in leads:
        writer.writerow([
            l["nome"], l["area"], l["origem"], l["telefone"], l["ticket"], l["responsavel"], l["etapa"],
            (l["ultimo_contato"] or "")[:10],
            (l["proximo_follow_up"] or "")[:16].replace("T", " "),
            l["notas"], l["motivo_perda"], (l["created_at"] or "")[:10],
        ])

    resp = make_response("\ufeff" + output.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename=leads-fabrica-{date.today().isoformat()}.csv"
    return resp


# ---------------------------------------------------------------- equipe (responsáveis)
@app.route("/equipe")
@login_required
def equipe():
    db = get_db()
    membros = [dict(r) for r in db.execute(
        "SELECT * FROM responsaveis ORDER BY ativo DESC, created_at"
    ).fetchall()]
    return render_template("equipe.html", user=session["user"], theme=get_theme(), membros=membros)


@app.route("/api/responsaveis", methods=["POST"])
@login_required
def api_criar_responsavel():
    data = request.get_json(force=True, silent=True) or {}
    nome = (data.get("nome") or "").strip()
    if not nome:
        return jsonify({"ok": False, "erro": "Digite um nome."}), 400

    db = get_db()
    existente = db.execute("SELECT id FROM responsaveis WHERE nome = ?", (nome,)).fetchone()
    if existente:
        db.execute("UPDATE responsaveis SET ativo = 1 WHERE id = ?", (existente["id"],))
        db.commit()
        return jsonify({"ok": True})

    db.execute(
        "INSERT INTO responsaveis (id, nome, ativo, created_at) VALUES (?,?,1,?)",
        (str(uuid.uuid4()), nome, datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/responsaveis/<rid>", methods=["PATCH"])
@login_required
def api_atualizar_responsavel(rid):
    data = request.get_json(force=True, silent=True) or {}
    db = get_db()
    if "ativo" in data:
        db.execute("UPDATE responsaveis SET ativo = ? WHERE id = ?", (1 if data["ativo"] else 0, rid))
        db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- meta mensal
@app.route("/api/meta", methods=["POST"])
@login_required
def api_salvar_meta():
    data = request.get_json(force=True, silent=True) or {}
    try:
        valor = int(float(data.get("valor")))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Valor inválido."}), 400
    if valor < 0:
        return jsonify({"ok": False, "erro": "Valor inválido."}), 400

    mes = date.today().isoformat()[:7]
    db = get_db()
    now = datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO metas_mensais (mes, valor_meta, updated_at) VALUES (?,?,?)"
        " ON CONFLICT(mes) DO UPDATE SET valor_meta = excluded.valor_meta, updated_at = excluded.updated_at",
        (mes, valor, now),
    )
    db.commit()
    return jsonify({"ok": True, "meta": valor})


# ---------------------------------------------------------------- importação em massa
@app.route("/leads/importar")
@login_required
def importar_leads_page():
    db = get_db()
    return render_template(
        "importar.html", user=session["user"], theme=get_theme(), responsaveis=get_responsaveis(db)
    )


@app.route("/api/leads/importar", methods=["POST"])
@login_required
def api_importar_leads():
    data = request.get_json(force=True, silent=True) or {}
    linhas = data.get("leads") or []
    pular_duplicados = data.get("pular_duplicados", True)

    db = get_db()
    autor = session.get("user", "Sistema")
    now = datetime.utcnow().isoformat()

    criados = 0
    duplicados = 0
    sem_nome = 0

    for linha in linhas:
        nome = (linha.get("nome") or "").strip()
        if not nome:
            sem_nome += 1
            continue

        telefone = (linha.get("telefone") or "").strip()
        if pular_duplicados and telefone:
            existente = db.execute("SELECT id FROM leads WHERE telefone = ?", (telefone,)).fetchone()
            if existente:
                duplicados += 1
                continue

        try:
            ticket = int(float(str(linha.get("ticket") or 0).replace(",", ".")))
        except ValueError:
            ticket = 0

        lead_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO leads (id, nome, area, origem, telefone, ticket, responsavel, etapa, etapa_changed_at,"
            " ultimo_contato, proximo_follow_up, notas, motivo_perda, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                lead_id,
                nome,
                (linha.get("area") or "").strip(),
                (linha.get("origem") or "").strip(),
                telefone,
                ticket,
                (linha.get("responsavel") or "").strip(),
                "Lead novo",
                now,
                None, None,
                (linha.get("notas") or "").strip(),
                "",
                now, now,
            ),
        )
        log_activity(db, lead_id, "criação", None, "Lead criado via importação de planilha", autor, commit=False)
        criados += 1

    db.commit()
    return jsonify({"ok": True, "criados": criados, "duplicados": duplicados, "sem_nome": sem_nome})


# ---------------------------------------------------------------- theme
@app.route("/api/theme", methods=["POST"])
def set_theme():
    theme = request.json.get("theme", "dark") if request.is_json else request.form.get("theme", "dark")
    resp = make_response(jsonify({"ok": True}))
    resp.set_cookie("theme", theme, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


# ---------------------------------------------------------------- automações
@app.route("/api/digest/send", methods=["POST"])
@login_required
def send_digest():
    result = automations.send_digest_email()
    status = 200 if result["ok"] else 400
    return jsonify(result), status


WEBHOOK_SECRET = os.environ.get("FABRICA_WEBHOOK_SECRET", "")


@app.route("/api/webhook/lead", methods=["POST"])
def webhook_lead():
    if WEBHOOK_SECRET:
        token = request.args.get("token") or request.headers.get("X-Webhook-Token")
        if token != WEBHOOK_SECRET:
            return jsonify({"error": "Token inválido."}), 401
    payload = request.get_json(silent=True) or request.form.to_dict()
    lead, error = automations.create_lead_from_webhook(payload)
    if error:
        return jsonify({"error": error}), 400
    return jsonify(lead), 201


@app.route("/api/webhook/calendly", methods=["POST"])
def webhook_calendly():
    if WEBHOOK_SECRET:
        token = request.args.get("token") or request.headers.get("X-Webhook-Token")
        if token != WEBHOOK_SECRET:
            return jsonify({"error": "Token inválido."}), 401
    body = request.get_json(silent=True) or {}
    result = automations.handle_calendly_event(body)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ---------------------------------------------------------------- leads API
@app.route("/api/leads", methods=["POST"])
@login_required
def create_lead():
    data = request.get_json(force=True)
    if not data.get("nome"):
        return jsonify({"error": "Nome é obrigatório."}), 400
    db = get_db()
    now = datetime.utcnow().isoformat()
    lead_id = str(uuid.uuid4())
    etapa = data.get("etapa") or "Lead novo"
    db.execute(
        "INSERT INTO leads (id, nome, area, origem, telefone, ticket, responsavel, etapa, etapa_changed_at,"
        " ultimo_contato, proximo_follow_up, notas, motivo_perda, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            lead_id,
            data.get("nome", ""),
            data.get("area", ""),
            data.get("origem", ""),
            data.get("telefone", ""),
            int(data.get("ticket") or 0),
            data.get("responsavel", ""),
            etapa,
            now,
            data.get("ultimo_contato") or None,
            data.get("proximo_follow_up") or None,
            data.get("notas", ""),
            data.get("motivo_perda", ""),
            now, now,
        ),
    )
    autor = session.get("user", "Sistema")
    log_activity(db, lead_id, "criação", None, f"Lead criado como \"{etapa}\"", autor, commit=False)
    db.commit()
    row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    result = row_to_dict(row)
    aviso = checar_agenda(db, result["responsavel"], result["proximo_follow_up"], lead_id)
    if aviso:
        result["aviso_agenda"] = aviso
    return jsonify(result), 201


ALLOWED_FIELDS = {
    "nome", "area", "origem", "telefone", "ticket", "responsavel", "etapa",
    "ultimo_contato", "proximo_follow_up", "notas", "motivo_perda",
}


@app.route("/api/leads/<lead_id>", methods=["PATCH"])
@login_required
def update_lead(lead_id):
    data = request.get_json(force=True)
    fields = {k: v for k, v in data.items() if k in ALLOWED_FIELDS}
    if not fields:
        return jsonify({"error": "Nada para atualizar."}), 400
    db = get_db()
    existing = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Lead não encontrado."}), 404
    existing = row_to_dict(existing)

    autor = session.get("user", "Sistema")
    for campo, novo_valor in fields.items():
        antigo_valor = existing.get(campo)
        if (antigo_valor or "") != (novo_valor or ""):
            label = CAMPO_LABELS.get(campo, campo)
            log_activity(db, lead_id, label, antigo_valor, novo_valor, autor, commit=False)

    now = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    if "etapa" in fields and fields["etapa"] != existing.get("etapa"):
        set_clause += ", etapa_changed_at = ?"
        values.append(now)
    values += [now, lead_id]
    db.execute(f"UPDATE leads SET {set_clause}, updated_at = ? WHERE id = ?", values)
    db.commit()
    row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    result = row_to_dict(row)
    aviso = checar_agenda(db, result["responsavel"], result["proximo_follow_up"], lead_id)
    if aviso:
        result["aviso_agenda"] = aviso
    return jsonify(result)


@app.route("/api/leads/<lead_id>/activity", methods=["GET"])
@login_required
def lead_activity(lead_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM activity_log WHERE lead_id = ? ORDER BY created_at DESC", (lead_id,)
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/leads/<lead_id>", methods=["DELETE"])
@login_required
def delete_lead(lead_id):
    db = get_db()
    db.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/leads/excluir-em-massa", methods=["POST"])
@login_required
def delete_leads_em_massa():
    data = request.get_json(force=True, silent=True) or {}
    ids = [i for i in (data.get("ids") or []) if i]
    if not ids:
        return jsonify({"ok": False, "erro": "Nenhum lead selecionado."}), 400

    db = get_db()
    placeholders = ",".join("?" * len(ids))
    db.execute(f"DELETE FROM leads WHERE id IN ({placeholders})", ids)
    db.commit()
    return jsonify({"ok": True, "excluidos": len(ids)})


# ---------------------------------------------------------------- página pública de aplicação
FABRICA_WHATSAPP_NUMERO = os.environ.get("FABRICA_WHATSAPP_NUMERO", "")

FATURAMENTO_OPCOES = [
    "Até R$50 Mil",
    "Entre R$50 Mil e R$100 Mil",
    "Entre R$100 Mil e R$200 Mil",
    "Entre R$200 Mil e R$300 Mil",
    "Mais de R$300 Mil por mês",
]
MOTIVACAO_OPCOES = [
    "Quero transformar meu conhecimento em uma mentoria premium",
    "Já vendo mentoria/consultoria e quero escalar",
    "Quero criar uma nova fonte de receita além dos atendimentos",
    "Hoje meu foco é apenas atrair mais pacientes",
]


@app.route("/aplicar", methods=["GET", "POST"])
def aplicar():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        area = request.form.get("area", "").strip()
        instagram = request.form.get("instagram", "").strip()
        faturamento = request.form.get("faturamento", "")
        motivacao = request.form.get("motivacao", "")
        dor = request.form.get("dor", "").strip()

        if not nome or not telefone:
            return render_template(
                "aplicar.html", erro="Preencha pelo menos nome e WhatsApp.",
                faturamento_opcoes=FATURAMENTO_OPCOES, motivacao_opcoes=MOTIVACAO_OPCOES,
            ), 400

        partes_notas = []
        if instagram:
            partes_notas.append(f"Instagram: {instagram}")
        if faturamento:
            partes_notas.append(f"Faturamento: {faturamento}")
        if motivacao:
            partes_notas.append(f"Momento: {motivacao}")
        if dor:
            partes_notas.append(f"O que impede: {dor}")

        lead, error = automations.create_lead_from_webhook({
            "nome": nome, "telefone": telefone, "area": area,
            "origem": "Formulário de aplicação", "notas": "\n".join(partes_notas),
        })
        if error:
            return render_template(
                "aplicar.html", erro=error,
                faturamento_opcoes=FATURAMENTO_OPCOES, motivacao_opcoes=MOTIVACAO_OPCOES,
            ), 400
        return redirect(url_for("aplicar_obrigado", lead_id=lead["id"]))

    return render_template(
        "aplicar.html", erro=None,
        faturamento_opcoes=FATURAMENTO_OPCOES, motivacao_opcoes=MOTIVACAO_OPCOES,
    )


@app.route("/aplicar/obrigado/<lead_id>")
def aplicar_obrigado(lead_id):
    db = get_db()
    row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        return redirect(url_for("aplicar"))
    lead = row_to_dict(row)
    partes_nome = [p for p in (lead["nome"] or "").split(" ") if p.lower() not in TITULOS_IGNORAR]
    primeiro_nome = partes_nome[0] if partes_nome else ""
    mensagem = f"Oi! Sou {lead['nome']} e acabei de aplicar no formulário da Fábrica. Gostaria de falar agora, se possível 🙂"
    whatsapp_link = (
        f"https://wa.me/{FABRICA_WHATSAPP_NUMERO}?text={quote(mensagem)}"
        if FABRICA_WHATSAPP_NUMERO else ""
    )
    return render_template(
        "aplicar_obrigado.html", lead=lead, primeiro_nome=primeiro_nome, whatsapp_link=whatsapp_link,
    )


@app.route("/api/aplicar/<lead_id>/preferencia", methods=["POST"])
def registrar_preferencia_contato(lead_id):
    data = request.get_json(force=True, silent=True) or {}
    preferencia = data.get("preferencia")
    if preferencia not in ("Quer falar agora", "Prefere mais tarde"):
        return jsonify({"ok": False}), 400
    db = get_db()
    log_activity(db, lead_id, "Preferência de contato", None, preferencia, "Formulário de aplicação")
    return jsonify({"ok": True})


@app.context_processor
def inject_globals():
    return {"ETAPAS": ETAPAS, "RESPONSAVEIS": get_responsaveis(get_db()), "ETAPA_SLUG": ETAPA_SLUG}


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5050)
