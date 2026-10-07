# Academia · Controle de acesso

Painel da recepção + API para catraca facial Intelbras.
**Stack:** Python 3.12 · FastAPI · MySQL 8 (SQL puro com PyMySQL) · WebSocket.

## Como rodar
```bash
cp .env.example .env                  # preencha os segredos (openssl rand -base64 32)
export DB_ROOT_PASSWORD=... DB_PASSWORD=...   # a DB_PASSWORD é a mesma do .env
docker compose up -d                  # MySQL já com as tabelas (sql/schema.sql)
python -m venv .venv && source .venv/bin/activate   # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                        # cria os usuários iniciais e os planos padrão
uvicorn app.main:app --reload         # API em http://localhost:8000 (docs em /docs)
```
Sem Docker: crie o banco `academia` no seu MySQL e rode `mysql academia < sql/schema.sql`.

`docs/demo-completo.html` é a interface integrada. Ao abrir `http://localhost:8000/`, a própria API FastAPI serve essa tela; depois do login, alunos, usuários, planos, pagamentos, histórico e acessos são lidos/gravadados no MySQL. O navegador mantém somente estado visual temporário.

## Catraca Intelbras
Tudo fica em `app/intelbras.py`. Os caminhos e o corpo das requisições **variam por modelo**: confira no manual da API do seu aparelho e ajuste o `.env`. Configure a catraca para enviar o webhook para `POST /api/v1/catraca/evento` com o cabeçalho `x-webhook-secret`. Para barrar inadimplentes, use o modo em que o servidor decide, ou remova a permissão do aluno na catraca ao bloquear a matrícula.

## Segurança
- **O que chega ao navegador, qualquer pessoa vê no F12.** Por isso o front não guarda dados nem senhas: só recebe o que a API entrega depois do login, e a API entrega o mínimo (CPF mascarado, nunca a foto).
- Login com senha em argon2, bloqueio após 5 erros, cookie `httpOnly` + `SameSite=Strict` (o JavaScript do navegador não lê o token).
- CPF e foto cifrados (AES-256-GCM) no MySQL; a busca por CPF usa hash com chave.
- Todas as consultas SQL usam parâmetros (`%s`), o que bloqueia SQL injection. Nunca monte SQL concatenando texto.
- Recuperação de senha com código de 6 dígitos que vale 10 minutos, guardado só como hash; resposta igual exista ou não o e-mail.
- Validação de toda entrada (pydantic), CORS restrito, limite de requisições, cabeçalhos de segurança, WebSocket só para quem está logado.
- Webhook da catraca protegido por segredo.
- Em produção: `APP_ENV=production`, HTTPS obrigatório, MySQL sem acesso externo, backup cifrado, `.env` fora do Git (já está no `.gitignore`).
- **LGPD:** rosto é dado biométrico sensível. Guarde o consentimento por escrito, defina por quanto tempo guarda e como apagar.

## Implementado nesta versão
- Dois perfis de login: Camila/recepção e Administrador.
- CRUD administrativo de usuários: criar, editar, excluir e trocar a função (ADMIN/RECEPCAO), protegido no backend pela permissão ADMIN.
- Cadastro manual de aluno com nome, CPF, nascimento, endereço, telefone e consentimento facial.
- Primeiro pagamento registrado com plano, data e forma de pagamento.
- Aba Planos com atualização manual de pagamentos e próximo vencimento.
- Pesquisa de aluno na liberação manual.
- Configurações com modo noturno e instruções básicas.
- Rotas `/api/v1/planos` para consulta e registro de pagamentos.
- Rotas `/api/v1/usuarios` para o CRUD administrativo de usuários.
- A exclusão de usuário respeita o histórico de auditoria: contas com liberações registradas não são apagadas.

## Integração atual
A interface já está ligada às rotas da API usando `fetch` com cookie de sessão e WebSocket em `/ws`. O MySQL é a fonte oficial para usuários, alunos, matrículas, planos, pagamentos e histórico. O PDF de relatório é gerado no backend a partir do banco.

## Pontos que ainda dependem do ambiente
- O envio de recuperação de senha por e-mail precisa de SMTP/Resend/SES configurado.
- O modelo da catraca Intelbras ainda precisa ser configurado conforme a API específica do equipamento.
- Em produção, use HTTPS, segredos reais e backup do MySQL.


### Credenciais de demonstração
- Atendente: `camila@academia.com` / `academia123`
- Administrador: `admin@academia.com` / `admin123`

Em produção, altere essas credenciais e não mantenha senhas de demonstração.

## CRUD de alunos
A aba **Alunos** permite ao atendente e ao administrador clicar no nome (ou em **Abrir**) para abrir o painel lateral com os dados do aluno. Nesse painel existem as ações **Editar aluno** e **Excluir aluno**.

A exclusão é lógica no banco: o cadastro deixa de aparecer na lista de ativos e a matrícula é cancelada, mas pagamentos, acessos e liberações continuam preservados para auditoria.

Para bancos já existentes, aplique `sql/migrations/001_alunos_crud.sql` e depois `sql/migrations/002_planos_integracao.sql` uma vez, antes de usar a versão integrada.

### Relatórios

- Histórico: botão "Exportar relatório" com períodos semanal, mensal e anual.
- Endpoint do backend: `GET /api/v1/relatorios/historico.pdf?periodo=semanal|mensal|anual`.
- O PDF reúne cadastro do aluno, plano, situação, histórico de acessos e pagamentos do período.
- A tela de demonstração gera o PDF localmente; a API gera o relatório a partir do banco.

### Perfis exibidos no login
A tela de login pode consultar `GET /api/v1/auth/usuarios-login` para montar os perfis disponíveis. Esse endpoint nunca retorna senha ou hash de senha.
