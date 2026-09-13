# central-sistemamelanogenico

Sistema de gestão de clínica (CRM) — cadastro de pacientes, agenda de
consultas, prontuário e módulo financeiro.

## Tecnologia

**Django (Python) + SQLite**, com o próprio painel administrativo do Django
(`/admin/`) como interface de cadastro/CRUD. Motivos da escolha:

- Um único framework cobre ORM, autenticação, formulários, admin e
  segurança (CSRF, proteção de senha, etc.) — pouca peça extra para manter.
- O **Django Admin** já entrega cadastro, edição, busca e filtros de
  pacientes, profissionais, agenda, prontuários e financeiro sem escrever
  telas do zero. Novas telas customizadas só quando fizer falta (como o
  relatório financeiro).
- **SQLite** é um arquivo único, zero servidor de banco para administrar —
  suficiente para uma clínica pequena/média. Trocar para PostgreSQL depois é
  só mudar `DATABASES` em `clinica/settings.py`, sem alterar código.
- Sem build de frontend (não há Node/webpack): os templates são HTML+CSS
  simples renderizados pelo próprio Django.

## Estrutura do projeto

```
clinica/          # configurações do projeto (settings, urls)
core/             # página inicial (dashboard) do sistema
pacientes/        # cadastro de pacientes (dados pessoais, contato, histórico de saúde)
profissionais/    # profissionais da clínica e seus horários de atendimento
agenda/           # consultas: paciente + profissional + data/hora + status
prontuarios/      # atendimentos realizados (queixa, diagnóstico, conduta, prescrição)
financeiro/       # tabela de preços (Serviço), pagamentos e relatório financeiro
templates/        # HTML compartilhado (base + páginas customizadas)
```

Relação entre os módulos:

- Um **Paciente** tem várias **Consultas** (agenda) e vários **Atendimentos**
  (prontuário).
- Uma **Consulta** pode originar um **Atendimento** (prontuário) e um ou mais
  **Pagamentos** (financeiro).
- **Profissional** tem horários de atendimento recorrentes
  (`HorarioAtendimento`) usados como referência para a agenda.

## Como rodar localmente

Pré-requisito: Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # crie um usuário administrador
python manage.py runserver
```

Depois acesse:

- `http://127.0.0.1:8000/` — painel inicial (consultas do dia, próximas
  consultas, pagamentos pendentes).
- `http://127.0.0.1:8000/admin/` — cadastro de pacientes, profissionais,
  consultas, prontuários, serviços e pagamentos.
- `http://127.0.0.1:8000/financeiro/relatorio/` — relatório financeiro por
  período (total recebido, pendente, por forma de pagamento e por
  profissional).

## Próximos passos sugeridos

- Autenticação/permissões por perfil (recepção, profissional de saúde,
  financeiro) usando grupos do Django.
- Tela de agenda em formato de calendário (hoje é lista via admin).
- Exportação do relatório financeiro em PDF/CSV.
- Notificações de consulta (e-mail/WhatsApp) e lembretes automáticos.
- Migrar para PostgreSQL e configurar variáveis de ambiente
  (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`) antes de
  colocar em produção.
