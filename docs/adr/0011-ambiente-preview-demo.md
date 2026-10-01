# ADR 0011 — Ambiente PREVIEW com entrada DEMO e base fictícia populosa

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
O dono do produto precisa abrir uma URL e navegar pelo sistema novo como um usuário real,
sem terminal e sem credenciais, durante o desenvolvimento. O repositório não tinha
infraestrutura de deploy (só CI). A produção nunca pode ganhar uma porta sem senha.

## Decisão
1. **Novo ambiente `preview`** (`config.settings.preview`): mesmo código, rotas, templates,
   CSP, WhiteNoise com manifest e gunicorn de produção; `DEBUG=False`; chave obrigatória;
   banco PostgreSQL próprio (`pcpr_preview`) só com dados fictícios.
2. **Entrada DEMO** só com `APP_ENV=preview` **e** `DEMO_MODE=true`:
   - a tela de login é a do produto; com os dois campos vazios, "Entrar" autentica o usuário
     `demo` ("Operador de Demonstração") por um backend próprio (`DemoBackend`), criando uma
     sessão normal (`django.contrib.auth.login`); credenciais preenchidas seguem o fluxo
     normal (senha errada nunca cai no usuário demo);
   - **entrada direta**: abrir qualquer página já autentica o usuário demo
     (`EntradaDemoMiddleware`); depois de "Sair", um cookie suspende isso até o próximo login.
3. **Proteção em camadas** contra o bypass fora do PREVIEW:
   | Camada | Onde | Efeito |
   |---|---|---|
   | Configuração | `production_base.py` | STAGING/PRODUCTION com `DEMO_MODE=true` não carregam (`ImproperlyConfigured`) |
   | Instalação | `preview.py` | `DemoBackend` e o middleware só entram no PREVIEW com DEMO_MODE |
   | Startup | `PlataformaConfig.ready()` | qualquer processo (gunicorn, worker, shell) falha com DEMO_MODE fora do PREVIEW |
   | Check | `plataforma.E004` / `E005` | DEMO_MODE fora do PREVIEW; PREVIEW com banco cujo nome não indique preview/demo |
   | Execução | `ambiente.demo_ativo()` | backend, formulário e middleware exigem as duas condições a cada uso |
   | Testes | `gestao/identidade/tests/test_demo.py` | produção recusa login vazio; settings de produção não carregam com DEMO_MODE; bypass não liga por acidente |
   Nenhuma regra usa `DEBUG`.
4. **Dataset DEMO** (`semear_demo`, `resetar_demo`): ~260 ofícios, 170 servidores, 48
   viaturas e 25 unidades, gerados **pelos serviços reais** (numeração, diárias, prazos,
   histórico, documentos e auditoria coerentes por construção), determinístico por dia e
   idempotente; CPFs com dígito verificador inválido, placas `ZZ*`, protocolos `00…`,
   e-mails `.invalid`. Os comandos só rodam em PREVIEW (e nos testes).
5. **Entrega**: `Dockerfile` de produção + `compose.preview.yml` (banco, web, worker) —
   sobe igual em qualquer máquina ou servidor com Docker; **GitHub Codespaces**
   (`.devcontainer/`) dá uma URL `https://…app.github.dev` sem infraestrutura nova, privada
   por padrão (exige login no GitHub).
6. **Identificação visual**: selo "PREVIEW" no cabeçalho (≥ 480 px), "Demonstração ·
   PREVIEW" no menu do usuário e na gaveta do celular, e aviso na tela de login.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Bypass por `DEBUG` | Insuficiente e frágil (pedido explícito do dono do produto) |
| Login falso separado | A tela de login deixaria de ser a real |
| Provedor de hospedagem (Render, Fly.io, Railway…) | Nenhum configurado no projeto; exige conta e decisão do dono; o compose roda em qualquer um deles |
| Túnel público a partir da sessão do agente | Efêmero (morre com a sessão) e público sem controle de acesso |

## Consequências
- Ambiente sem senha só existe onde `APP_ENV=preview`; a URL do Codespaces continua
  protegida pelo login do GitHub (deixar a porta "pública" é decisão consciente do dono).
- A trilha de auditoria registra os resets do PREVIEW (append-only).
- Novas telas devem ter dados no `semear_demo` para serem avaliadas no PREVIEW.
