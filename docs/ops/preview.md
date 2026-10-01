# PREVIEW — ambiente navegável com entrada DEMO

Ambiente para ver e testar o sistema novo no navegador, como um usuário real, com uma base
**fictícia e populosa**. Decisão e proteções: `docs/adr/0011-ambiente-preview-demo.md`.

| | |
|---|---|
| Settings | `config.settings.preview` (`APP_ENV=preview`) |
| Entrada sem senha | `DEMO_MODE=true` (só vale no PREVIEW) |
| Banco | PostgreSQL próprio, nome com "preview"/"demo" (padrão `pcpr_preview`) |
| Usuário DEMO | login `demo` · "Operador de Demonstração" · `demo@demo.invalid` · papéis Gestor + Operador de Viagens, lotado na ASCOM, vê todas as unidades |
| Dados | `semear_demo`: ~260 ofícios, 170 servidores, 48 viaturas, 25 unidades, ~300 PDFs |

## Como entrar
1. Abra a URL do preview → **tela de login real do produto** (com o aviso "Ambiente de
   demonstração").
2. Deixe **usuário e senha em branco** e clique em **Entrar**.
3. Ou abra direto qualquer página (ex.: `/viagens/oficios/`): a sessão DEMO é criada sozinha.
4. **Sair** (menu do usuário) volta ao login e suspende a entrada automática até o próximo
   "Entrar".

## Opção A — GitHub Codespaces (URL sem infraestrutura nova)
1. No GitHub: **Code → Codespaces → Create codespace** no branch desejado.
2. O Codespace sobe `compose.preview.yml` (banco + web + worker) e semeia a base na primeira
   vez (~1–2 min); a porta **8000 "PCPR Preview"** abre no navegador:
   `https://<nome-do-codespace>-8000.app.github.dev`.
3. A porta é **privada** por padrão (só quem tem acesso ao Codespace entra). Tornar pública é
   decisão consciente do dono do produto (aba *Ports* → *Port visibility*).

## Opção B — qualquer máquina ou servidor com Docker
```bash
scripts/preview.sh subir          # constrói e sobe tudo → http://localhost:8000
scripts/preview.sh logs           # acompanha
scripts/preview.sh semear         # recria o dataset (idempotente)
scripts/preview.sh resetar        # zera o banco DEMO (migrações + flush) e recria
scripts/preview.sh verificar      # saúde + E2E do fluxo DEMO contra PREVIEW_URL
scripts/preview.sh parar          # para (os dados ficam no volume)
```
Atrás de um domínio com TLS: `PREVIEW_HOSTS=preview.exemplo.gov.br`,
`PREVIEW_ORIGENS=https://preview.exemplo.gov.br`, `PREVIEW_HTTPS=true`.
Rede com proxy que intercepta TLS: `docker build --secret id=ca,src=/caminho/ca.crt …`.

## Opção C — sem Docker (PostgreSQL local)
```bash
createdb pcpr_preview             # uma vez
scripts/preview.sh local          # check, migrate, semear_demo (se vazio), worker e gunicorn
```

## Comandos de dados
| Comando | O que faz | Onde roda |
|---|---|---|
| `manage.py semear_demo [--escala 1.0] [--sem-documentos] [--se-vazio]` | Apaga os dados de negócio e recria o dataset DEMO; gera os PDFs com 4 workers | só PREVIEW (e testes) |
| `manage.py resetar_demo` | `migrate` + `flush` + `semear_demo` | só PREVIEW (e testes) |

Determinismo: semente fixa e datas relativas a hoje — o mesmo dia produz o mesmo dataset
(executar 3 vezes não duplica nada). A trilha de auditoria não é apagada (append-only).

## Como desligar o modo DEMO
- Remova `DEMO_MODE` (ou `DEMO_MODE=false`) e reinicie: o login volta a exigir usuário e
  senha; a entrada automática deixa de existir (backend e middleware nem são instalados).
- Para usar outros usuários do dataset, defina senha com
  `manage.py changepassword <login>` (eles nascem sem senha utilizável).

## Por que produção nunca usa o bypass
- `config.settings.production` e `staging` **não carregam** com `DEMO_MODE=true`.
- Todo processo falha no startup se `DEMO_MODE=true` fora do PREVIEW (`PlataformaConfig.ready`).
- `check --deploy` reprova `DEMO_MODE` fora do PREVIEW (E004) e PREVIEW apontando para banco
  que não seja de demonstração (E005) — o entrypoint do contêiner roda esse check antes de
  subir.
- Em execução, backend, formulário e middleware exigem `APP_ENV=preview` **e** `DEMO_MODE`.
- Testes: `gestao/identidade/tests/test_demo.py` e `gestao/viagens/tests/test_demonstracao.py`.

## O que o dataset contém
- **Ofícios** em todas as situações (rascunho vazio, parcial, com pendência de protocolo ou
  justificativa, pronto para emitir; emitido; reaberto e reemitido com versão 2 dos
  documentos; cancelado antes ou depois da emissão), de dois anos atrás até viagens futuras.
- **Roteiros** com 1 destino, vários destinos, bate-volta (documento "por trechos"), mesmo dia,
  8 destinos; capitais, Brasília e municípios de nome longo; diárias de 0%, 15%, 30% e 100%.
- **Equipes** de 1 a 12 servidores, motorista quando há viatura; conflitos de agenda reais.
- **Casos de interface**: motivo muito longo, unidade de nome longo, valor alto
  (18 diárias × 12 servidores em Brasília), muitos destinos, lista com 13 páginas.
- **Histórico** coerente com o estado (criado → alterado → equipe → emitido → documento
  gerado → reaberto/cancelado), com datas plausíveis.
- **Não existe** módulo de notificações no produto ainda (a página é um placeholder): o
  dataset não cria notificações.

## Fictício por construção
Nomes combinados de listas de prenomes/sobrenomes; CPFs com dígito verificador
**inválido** (nunca coincidem com CPF real); placas da série `ZZ*`; protocolos iniciados por
`00`; e-mails em `.invalid`. O teste `test_dataset_e_ficticio` também compara (por hash) com
os dados reais que já estiveram no histórico do Git.
