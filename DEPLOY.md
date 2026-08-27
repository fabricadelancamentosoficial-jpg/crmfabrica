# Deploy — Railway

O código já está pronto pra produção (gunicorn, banco em caminho configurável, tudo
versionado no git local). Faltam duas contas que só você pode criar — o resto eu deixei
pronto pra ser 5 minutos de clique depois disso.

## 1. Criar o repositório no GitHub (você)

1. Acesse **github.com/new**
2. Nome do repositório: `fabrica-crm`
3. Deixe **Private** marcado (não é código público)
4. **Não** marque "Add a README" (já temos um) — crie vazio
5. Depois de criado, copia a URL que aparece (algo como
   `https://github.com/SEU-USUARIO/fabrica-crm.git`) e me manda aqui

Quando eu tiver essa URL, eu mesmo conecto e envio o código (comando `git push`) —
não precisa fazer mais nada nessa parte.

## 2. Criar conta no Railway (você)

1. Acesse **railway.app** → "Login" → entre com sua conta do GitHub (mais simples,
   já autoriza o acesso ao repositório)
2. Clique em **"New Project"** → **"Deploy from GitHub repo"** → selecione `fabrica-crm`
3. O Railway já detecta o `Procfile` sozinho e começa a build

## 3. Adicionar o disco persistente (você, dentro do Railway)

Isso é o que garante que os leads não somem quando o app reiniciar:

1. No serviço criado, vá em **Settings → Volumes → New Volume**
2. Mount path: `/data`
3. Salve

## 4. Variáveis de ambiente (você, dentro do Railway)

Em **Variables**, adicione:

```
FABRICA_DB_PATH=/data/fabrica.db
FABRICA_CRM_PASSWORD=escolha-uma-senha-forte-aqui
FABRICA_SECRET_KEY=1d6884e5a633d0ba321224e7694ecb7e8f1813ff9ff34eec4aa1400828ac93e7
```

(A chave acima eu já gerei aleatória pra você — pode usar direto, é só pra assinar a
sessão de login, não precisa trocar.)

Se quiser já deixar o resumo por e-mail e o webhook funcionando, adicione também as
variáveis de `.env.example` (`FABRICA_SMTP_*`, `FABRICA_DIGEST_TO`, `FABRICA_WEBHOOK_SECRET`).

## 5. Pronto

O Railway te dá uma URL pública (tipo `fabrica-crm-production.up.railway.app`). A partir
daí, Cris e Amanda acessam de qualquer lugar, e toda vez que eu mudar o código e mandar
pro GitHub, o Railway atualiza sozinho em 1-2 minutos.

---

**Depois que os passos 1 e 2 estiverem feitos, me avisa que eu cuido do resto** (push do
código, confirmar que subiu certo, testar o login lá).
