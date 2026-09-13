# central-sistemamelanogenico

Sistema de gestão de clínica — CRM de leads com cadência de contato, agenda
visual por semana, prontuário/histórico por paciente e módulo financeiro.
Multi-tenant: cada organização (clínica/mentorada) só enxerga os próprios
dados.

## Tecnologia

**Django (Python) + SQLite**, com o próprio painel administrativo do Django
(`/admin/`) para cadastros de apoio (profissionais, tipos de consulta,
origens de lead, tabela de preços...) e telas próprias para o dia a dia
(painel "o que preciso fazer hoje", CRM em Kanban, agenda semanal).

- Um único framework cobre ORM, autenticação, formulários, admin e
  segurança — pouca peça extra para manter.
- **SQLite** localmente (arquivo único, zero configuração) e **PostgreSQL**
  em produção — o projeto já lê a variável de ambiente `DATABASE_URL` e troca
  de banco sozinho, sem precisar mexer em código (veja "Colocar o sistema
  online" mais abaixo).
- Sem build de frontend: os templates são HTML+CSS simples renderizados
  pelo próprio Django.
- **WhatsApp assistido**: o sistema guarda os modelos de mensagem de cada
  etapa da cadência (editáveis) e, ao confirmar o envio, abre o WhatsApp
  Web/app com o número e o texto já preenchidos — sem precisar contratar
  nenhuma API paga.

## Estrutura do projeto

```
clinica/          # configurações do projeto (settings, urls)
contas/           # organizações (tenants), usuários e isolamento multi-tenant
leads/            # CRM: leads, cadência de contato, kanban, pausas, mensagens
core/             # painel "o que preciso fazer hoje"
pacientes/        # cadastro de pacientes
profissionais/    # profissionais da clínica e horários de atendimento
agenda/           # tipos de consulta, bloqueios de horário e consultas
prontuarios/      # atendimentos realizados (queixa, diagnóstico, conduta)
financeiro/       # tabela de preços, pagamentos e relatório financeiro
templates/        # HTML compartilhado
```

Como as peças se conectam:

- Toda tabela do sistema pertence a uma **Organização** (`contas.Organizacao`)
  — uma mentorada nunca vê os dados de outra. Um usuário sem organização é um
  **administrador geral** e só configura o sistema pelo `/admin/`.
- Um **Lead** entra pelo CRM, passa pela cadência (1º a 4º contato) e, ao
  agendar, vira automaticamente um **Paciente** — sem recadastro — e gera uma
  **Consulta** na agenda.
- Uma **Consulta** tem um **Tipo de Consulta** (cor própria na agenda) e pode
  gerar um **Atendimento** (prontuário) e **Pagamentos** (financeiro).

### O que já está pronto

- CRM em Kanban (Novos → 1º ao 4º contato), com pausa/retomada de cadência,
  motivo de perda obrigatório, histórico completo em linha do tempo por lead.
- Registro de ligações (atendeu/não atendeu) e envio assistido de WhatsApp
  por etapa, com mensagens-modelo editáveis.
- Agendamento direto a partir do lead (`Agendar consulta`), sem recadastro.
- Agenda semanal visual (08h–18h, intervalo configurável), com cores por
  tipo de consulta, bloqueios de horário e filtro por profissional.
- Painel "O que preciso fazer hoje": novos leads, leads por etapa, cadências
  para retomar, consultas do dia, tarefas atrasadas e alertas de
  acompanhamento.
- Relatório financeiro por período e página de Indicadores (leads por
  status/origem, consultas por status, motivos de perda).
- **Programas de Acompanhamento** configuráveis (3/6/9 meses vêm cadastrados,
  mas nada é fixo no código) e **Ficha da Paciente** com jornada visual,
  checklist de consultas/kits, financeiro do programa e alertas automáticos
  (consulta a agendar, kit a enviar, término se aproximando).

### O que fica para as próximas etapas

- Ficha de Anamnese completa, Modulação em fases (com histórico de versões),
  evolução fotográfica e Feedbacks da paciente — módulo grande por si só, as
  abas já existem na Ficha da Paciente mas mostram "em construção".
- Indicadores de conversão (lead → consulta → venda, origem que mais
  converte) — hoje os indicadores são só contagens.
- Tela de administração para uma organização se auto-cadastrar (hoje isso é
  feito pelo comando `configurar_organizacao`, veja abaixo).

## Como rodar no Windows (mais fácil)

Com o [Python](https://www.python.org/downloads/) já instalado (marque
**"Add python.exe to PATH"** durante a instalação), dê duplo clique em
**`iniciar.bat`**, na raiz do projeto.

- Na primeira vez, ele cria o ambiente virtual, instala as dependências,
  aplica as migrações, pede para você criar o usuário administrador e o
  nome da sua clínica (isso já cria origens de lead, tipos de consulta e
  mensagens padrão para você editar depois).
- Nas próximas vezes, ele apenas sobe o servidor.
- Em ambos os casos, ele abre `http://127.0.0.1:8000/` automaticamente no
  navegador.
- Para parar o sistema, feche a janela chamada **"Servidor - Sistema da
  Clínica"**.

> **Atualizando de uma versão anterior?** Esta versão introduz múltiplas
> organizações e muda o modelo de usuário. Apague o arquivo `db.sqlite3` (se
> existir) antes de rodar `iniciar.bat` de novo — não há dados reais em
> risco nesta fase inicial do projeto.

## Como rodar localmente (manual)

Pré-requisito: Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser         # crie um usuário administrador
python manage.py configurar_organizacao "Nome da sua clínica"
python manage.py runserver
```

Depois acesse:

- `http://127.0.0.1:8000/` — painel "O que preciso fazer hoje".
- `http://127.0.0.1:8000/leads/` — CRM em Kanban.
- `http://127.0.0.1:8000/agenda/semana/` — agenda semanal.
- `http://127.0.0.1:8000/financeiro/relatorio/` — relatório financeiro.
- `http://127.0.0.1:8000/admin/` — cadastros de apoio (profissionais, tipos
  de consulta, origens, mensagens-modelo, pacientes, prontuários...).

## Colocar o sistema online (e depois no seu domínio)

O projeto já está pronto para produção: usa `gunicorn` (servidor de verdade,
em vez do `runserver` de desenvolvimento), serve os arquivos estáticos
sozinho (`whitenoise`) e troca de SQLite para PostgreSQL automaticamente
quando a variável `DATABASE_URL` existir. Falta só escolher uma hospedagem.

**Recomendação: [Railway](https://railway.app/)** — plano gratuito para
testar, depois cobra por uso (tende a ficar uns US$ 5–10/mês para um sistema
pequeno como este), deploy direto do GitHub, HTTPS e domínio próprio de
graça. Alternativas com o mesmo tipo de fluxo: [Render](https://render.com/)
e [PythonAnywhere](https://www.pythonanywhere.com/) (esse último é mais
manual, mas tem um plano pago bem barato e é focado em Python/Django).

### Passo a passo (Railway)

1. **Crie a conta** em railway.app (dá para entrar com a conta do GitHub).
2. **New Project → Deploy from GitHub repo** e escolha o repositório
   `central-sistemamelanogenico` (autorize o Railway a acessar o GitHub se
   pedir).
3. **Adicione o banco de dados**: no mesmo projeto, clique em **+ New →
   Database → PostgreSQL**. Isso cria um serviço Postgres separado, com sua
   própria variável `DATABASE_URL` — mas ela **não** aparece sozinha no
   serviço da aplicação. É o próximo passo que resolve isso.
4. **Configure as variáveis de ambiente** do serviço da **aplicação** (não do
   Postgres — aba *Variables* do serviço que roda o Django):
   - `DATABASE_URL` → clique em **+ New Variable → Add Reference** e escolha
     a variável `DATABASE_URL` do serviço Postgres. **Este passo é o que
     mais gente esquece** — sem ele, o sistema roda em SQLite dentro do
     container e perde todos os dados a cada deploy. (Se você adicionou o
     Postgres pela mesma tela do serviço da aplicação, ou clicou em
     "Connect" entre os dois serviços, o Railway pode já ter feito isso
     sozinho — confira se a variável aparece antes de adicionar de novo.)
   - `DJANGO_SECRET_KEY` → uma senha longa e aleatória só sua (pode gerar em
     https://djecrety.ir/)
   - `DJANGO_DEBUG` → `False`
   - `DJANGO_ALLOWED_HOSTS` → o domínio que o Railway vai gerar, por exemplo
     `meusistema.up.railway.app` (aparece na aba *Settings → Domains* depois
     do primeiro deploy; edite a variável de novo se mudar)
   - `DJANGO_CSRF_TRUSTED_ORIGINS` → o mesmo domínio, mas com `https://` na
     frente, ex.: `https://meusistema.up.railway.app`

   > A partir de agora, se `DATABASE_URL` não estiver configurada
   > corretamente, o próprio sistema recusa subir (em vez de usar SQLite
   > escondido) e mostra exatamente essa instrução no log de deploy.
5. O Railway já detecta o `Procfile` e faz o deploy automaticamente. Ele
   roda as migrações, coleta os arquivos estáticos e sobe o `gunicorn`
   sozinho a cada push no GitHub.
6. Abra a URL gerada, rode o setup inicial pelo **Shell** do próprio Railway
   (aba do serviço → *Shell* ou *Settings → Deploy → Run command*):
   ```bash
   python manage.py createsuperuser
   python manage.py configurar_organizacao "Nome da sua clínica"
   ```
7. Pronto — acesse a URL do Railway no navegador e use o sistema online.

> **Perdendo usuários/dados a cada deploy?** É o sintoma exato de estar
> rodando em SQLite dentro do container em vez do Postgres — normalmente
> porque a `DATABASE_URL` não foi referenciada no serviço da aplicação
> (passo 4 acima). Depois de corrigir a variável, rode o passo 6
> novamente — os dados criados enquanto rodava em SQLite já se perderam,
> mas a partir daí passam a persistir de verdade.

> **Deploy travando com "gunicorn: command not found"?** Já corrigimos isso
> no `Procfile`/`nixpacks.toml` (usamos `python -m gunicorn` em vez de
> `gunicorn` puro, que depende do `PATH` do ambiente de build). Se aparecer
> de novo, no Railway vá em **Settings → Deploy** e confirme que não há um
> "Start Command" customizado sobrescrevendo o do `Procfile` — se houver,
> apague para o Railway usar o nosso.

### Depois: colocar no seu próprio domínio

1. No Railway, vá em **Settings → Domains → Custom Domain** e digite seu
   domínio (ex.: `sistema.suaclinica.com.br`).
2. O Railway mostra um registro **CNAME** para você criar.
3. No painel do seu domínio (Registro.br, GoDaddy, Hostgator, etc.), abra a
   área de **DNS** e crie esse registro CNAME apontando para o valor que o
   Railway deu.
4. Espere a propagação (de minutos a algumas horas) — o Railway emite o
   certificado HTTPS sozinho assim que detectar o domínio configurado.
5. Atualize `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` incluindo
   também o novo domínio (pode manter os dois, separados por vírgula).

### Atenção antes de usar com pacientes de verdade

- **Fotos de prova social** (`ProvaSocial`) ficam salvas no disco do
  servidor. Na maioria das hospedagens (incluindo o plano gratuito do
  Railway) esse disco **não é permanente** — um redeploy pode apagar as
  fotos já enviadas. Se for usar esse recurso de verdade, me avise para
  configurarmos um armazenamento externo (ex.: Cloudflare R2 ou AWS S3,
  ambos com camada gratuita).
- Depois do primeiro deploy, troque a senha do superusuário e crie usuários
  de verdade para a equipe pelo `/admin/` (Contas → Usuários), vinculando
  cada um à organização certa.
- Faça backup do banco periodicamente (o Railway tem backup automático do
  Postgres nos planos pagos; confirme no painel).

## Próximos passos sugeridos

- Autenticação/permissões por perfil (recepção, profissional, financeiro)
  usando grupos do Django.
- Tela de auto-cadastro de novas organizações (hoje é via linha de comando).
- Exportação do relatório financeiro em PDF/CSV.
- Armazenamento externo (S3/R2) para fotos de prova social sobreviverem a
  redeploys em produção.
