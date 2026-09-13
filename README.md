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
- **SQLite** é um arquivo único, sem servidor de banco para administrar.
  Trocar para PostgreSQL depois é só mudar `DATABASES` em
  `clinica/settings.py`.
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
  para retomar, consultas do dia e tarefas atrasadas.
- Relatório financeiro por período.

### O que fica para as próximas etapas

- Módulo de Programas de Acompanhamento (3/6/9 meses) e conversão formal do
  lead em "paciente ativa" com jornada do programa.
- Ficha completa da paciente: anamnese, modulação em fases, evolução
  fotográfica, feedbacks.
- Indicadores/conversões (funil, origem que mais converte, etc.) além dos
  contadores do painel do dia.
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

## Próximos passos sugeridos

- Autenticação/permissões por perfil (recepção, profissional, financeiro)
  usando grupos do Django.
- Tela de auto-cadastro de novas organizações (hoje é via linha de comando).
- Exportação do relatório financeiro em PDF/CSV.
- Migrar para PostgreSQL e configurar variáveis de ambiente
  (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`) antes de
  colocar em produção.
