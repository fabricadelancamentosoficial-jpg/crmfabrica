# Fábrica CRM

CRM comercial interno da Fábrica — Painel, Pipeline (kanban com drag-and-drop) e Leads,
com login por nome + senha compartilhada e tema claro/escuro.

## Rodar localmente

```bash
cd ~/Documents/fabrica-crm
source venv/bin/activate
python3 app.py
```

Acesse **http://localhost:5050**. Login inicial:

- Nome: Arthur, Cris ou Amanda
- Senha: `fabrica2026` (troque isso — veja abaixo)

Na primeira execução, o banco `fabrica.db` (SQLite) é criado automaticamente e populado
com 15 leads de exemplo, iguais aos do mockup, só para você já poder testar arrastar
cards, editar, filtrar e ordenar. Pode apagar/editar todos livremente.

## Configuração (.env)

```bash
cp .env.example .env
```

Edite o `.env` com a senha do CRM, os dados de e-mail (se quiser o resumo automático) e
o token do webhook. O `.env` nunca vai pro git. Depois de editar, é só rodar
`python3 app.py` de novo — ele lê o arquivo sozinho.

## Automações

### 1. Resumo diário por e-mail

Assim que o `.env` tiver `FABRICA_SMTP_*` e `FABRICA_DIGEST_TO` preenchidos, você pode:

- Clicar em **"Enviar resumo por e-mail"** no Painel a qualquer momento, ou
- Rodar `python3 send_digest.py` (mesma coisa, via terminal — pensado pra automatizar).

O e-mail traz: follow-ups de hoje, atrasados e leads parados há muitos dias na mesma
etapa. Para receber isso automaticamente toda manhã sem precisar clicar em nada, agende
o script no `cron` (Mac/Linux):

```bash
crontab -e
# adicione a linha (roda às 8h, dias úteis):
0 8 * * 1-5 cd /Users/arthurfonsecadeoliveira/Documents/fabrica-crm && venv/bin/python3 send_digest.py
```

Gmail exige uma "senha de app" (não é a senha normal da conta) — gere uma em
https://myaccount.google.com/apppasswords com a verificação em duas etapas ativada.

### 2. WhatsApp automático — ainda não, precisa de uma conta de provedor

Diferente do e-mail, mandar mensagem de WhatsApp automaticamente exige uma API paga de
um provedor (Twilio ou a Meta Cloud API direto), com número de telefone comercial
verificado — isso eu não crio por você, precisa ser feito pela sua conta. O que já está
pronto: todo lead tem campo de telefone, e o card/modal já tem um botão que abre a
conversa no WhatsApp Web com um clique (`wa.me`). Quando você tiver a conta do provedor,
me avisa que eu conecto o envio automático de lembrete no lugar do clique manual.

### 3. Captura automática de leads do formulário de aplicação

Existe um endpoint pronto para receber leads de fora:

```
POST /api/webhook/lead?token=SEU_FABRICA_WEBHOOK_SECRET
Content-Type: application/json

{ "nome": "Dra. Fulana", "telefone": "5548999998888", "area": "Odontologia" }
```

Ele cria o lead direto como "Lead novo", com origem "Formulário de aplicação" por padrão.
Como conectar isso ao seu formulário de verdade depende de qual ferramenta você usa:

- **Typeform, Google Forms, Meta Lead Ads, etc.**: o caminho mais simples é um Zapier ou
  Make (antigo Integromat) gratuito — "quando um novo formulário chegar, faça um POST
  para essa URL". Não precisa escrever código.
- **Formulário HTML seu (landing page própria)**: dá pra postar direto pro endpoint
  acima a partir do próprio site.

Me diz qual ferramenta você usa no formulário de aplicação da Fábrica que eu já deixo o
mapeamento de campos certinho e, se quiser, o passo a passo específico do Zapier/Make.

### 4. Leads parados

Qualquer lead ativo que não muda de etapa há 7+ dias (ajustável via `FABRICA_STALE_DAYS`
no `.env`) aparece com um selo de alerta no card do Pipeline e numa lista própria no
Painel — e entra no resumo por e-mail.

### 5. Histórico por lead

Toda mudança de campo (etapa, responsável, ticket, etc.) fica registrada e aparece na
aba "Histórico" dentro do modal de edição do lead, com quem mudou e quando.

### 6. Agendamento inteligente

"Próximo follow-up" agora aceita data **e hora**, não só data. Ao salvar um lead, o
sistema avisa (sem bloquear) quando:

- o horário cai fora da janela de atendimento configurada;
- o dia não está entre os dias de atendimento;
- o mesmo responsável já tem outro lead marcado perto daquele horário (conflito de agenda).

Ajuste a janela no `.env`: `FABRICA_AGENDA_INICIO`, `FABRICA_AGENDA_FIM`,
`FABRICA_AGENDA_DURACAO_MIN` (duração de cada compromisso, em minutos) e
`FABRICA_AGENDA_DIAS` (0=segunda … 6=domingo). Isso ainda não sincroniza com Google
Calendar nem mostra uma grade de horários livres — é aviso inteligente, não agenda visual
completa. Se isso virar prioridade, é o próximo passo natural.

### 7. KPIs de desempenho comercial

O Painel agora traz, além do que já existia: tempo médio até fechar um lead, ticket médio
dos fechados (Ganho), valor total já fechado, e qual origem converte melhor. Tudo
calculado a partir dos dados reais — sem número inventado, sem "87 indicadores" de
vaidade, só o que ajuda a decidir alguma coisa.

### 8. Calendly (agenda de verdade) — receptor pronto, falta conectar

Já existe um endpoint que recebe agendamentos do Calendly e atualiza o lead sozinho
(ou cria um novo, se não achar):

```
POST /api/webhook/calendly?token=SEU_FABRICA_WEBHOOK_SECRET
```

Quando alguém marca um horário no Calendly da cliente, isso aqui: acha o lead pelo
telefone, muda a etapa pra "Reunião agendada", e já preenche o "Próximo follow-up" com
o horário exato marcado (convertido pro horário de Brasília automaticamente).

**O que falta pra ligar de verdade**: o Calendly só libera webhook em plano pago
(Premium ou acima) — não tem como usar isso no plano grátis. Com o token de API dela
(gerado no painel do Calendly), eu registro o webhook uma vez e fica funcionando sozinho
depois disso.

**Alternativa sem custo extra**: se ela já usa Google Agenda, dá pra integrar direto com
a Google Calendar API (gratuita) em vez do Calendly — faz a mesma coisa (bloqueia
horário, evita choque de agenda), só que sem mensalidade adicional. Vale perguntar pra
ela qual ferramenta prefere antes de eu seguir.

## Deixar Cris e Amanda acessarem também

Hoje o app roda só no seu computador (`localhost`). Para os três acessarem o mesmo
pipeline ao mesmo tempo, precisa hospedar em algum lugar que fique sempre ligado. Duas
opções simples quando quiser dar esse passo:

1. **Mesma rede/wifi (rápido, grátis)**: rodar `python3 app.py` e descobrir o IP local
   da sua máquina (`ipconfig getifaddr en0` no Mac) — Cris/Amanda acessam por
   `http://SEU-IP:5050` enquanto seu computador estiver ligado e no mesmo wifi.
2. **Hospedagem de verdade (recomendado para uso contínuo)**: subir esse mesmo código
   para um serviço como Railway, Render ou Fly.io (todos têm plano gratuito/barato para
   uma app assim). Aviso: para múltiplas pessoas editando ao mesmo tempo de lugares
   diferentes o ideal é trocar o SQLite por um Postgres gerenciado — é só me pedir
   quando for a hora e eu faço essa migração.

## Estrutura

```
app.py              # rotas, lógica de negócio, API
automations.py       # resumo por e-mail + captura de leads via webhook
send_digest.py        # script pra agendar no cron (dispara o resumo)
schema.sql           # schema do SQLite
templates/           # HTML (Jinja2)
static/css/style.css # design system (claro + escuro)
static/js/           # tema, drag-and-drop do pipeline, modal de lead
.env.example          # modelo de configuração (copie para .env)
fabrica.db            # banco local (gerado automaticamente, não vai pro git)
```
