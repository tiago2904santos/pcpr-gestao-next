# Evidências — preparação da implantação (2026-10-13)

**Onde:** VPS **simulada** — Docker 29.8 num contêiner Linux isolado (4 vCPU, 15 GB), com os
mesmos scripts, caminhos configuráveis (`PCPR_RAIZ`/`PCPR_ETC`) e domínio fictício
`homologacao.pcpr.test` atrás do Caddy com TLS interno. **A VPS Hostinger real não foi
acessada** (sem credenciais; porta 22 de saída bloqueada no ambiente do agente).

**Versões:** produto `b3471bd6a639b21f0741e147d546f57f874dcc1f` (main em 2026-10-13, imagem
construída por `git archive` do commit, `Dockerfile` da raiz sem alterações); PostgreSQL
16.15 (`sha256:0ea6700a…`); Caddy 2.11.7 (`sha256:d8542f48…`); restic 0.18.1 (`sha256:39d9072f…`).

| # | Verificação | Resultado |
|---|---|---|
| 1 | `implantar.sh homologacao <sha> --semear` (1ª vez) | ✅ 2 min 46 s — `check --deploy`, 119 migrações como `pcpr_owner`, privilégios pós-migração, dataset sintético (258 ofícios, 292 PDFs gerados na raiz somente leitura), smoke 13/13 |
| 2 | Smoke pelo HTTPS público (`smoke.sh`) | ✅ 20/20 — `/saude/`, CSP, X-Frame-Options, nosniff, Referrer-Policy, COOP, **HSTS**, cookie CSRF `Secure`, **http→https 308**, sem `localhost` no HTML, `/` sem sessão → login, estático com `immutable`, `/media/` e `/var/media/` **404**, login com senha, lista autenticada, **PDF baixado**, PDF **sem sessão bloqueado (302)** |
| 3 | Worker e documentos (`testar-documentos.sh`) | ✅ reemissão processada pelo worker em execução (LISTEN/NOTIFY entre contêineres); **v2 criada, v1 preservada**; SHA-256 de todas as versões confere; **falha de escrita induzida** registrada (`PermissionError`) e **retry automático** concluído após devolver a escrita; nenhuma mensagem com falha definitiva; PDF novo baixado por HTTPS igual ao SHA-256 do banco |
| 4 | Classes documentais por HTTPS (`testar-classes.sh`) | ✅ 13/13 — Ofício (PDF, minuta, DOCX), Justificativa, Termo (PDF único e ZIP de DOCX), Plano, Ordem de serviço, Diário de bordo (PDF e XLSX), Relatório técnico (PDF e DOCX), Pauta |
| 5 | Renderização VPS × gravado (`comparar-renderizacao.sh`) | ✅ 8/8 **idênticos em bytes** ao PDF gravado (geração determinística) |
| 6 | Renderização VPS × local (fora do Docker, venv do repositório) | ✅ 8/8 **equivalentes** (mesmas páginas, fontes embutidas e texto); bytes diferem porque o ambiente local não tem `libharfbuzz-subset` (WeasyPrint usa fontTools) — a imagem tem |
| 7 | Roteiro no navegador (Chromium, `roteiro_navegador.py`) a 360 e 1440 px | ✅ 22/22 — sem sessão → login sem DEMO; login com senha; Central; painel; lista (255) e paginação; busca ao vivo e estado vazio; filtro; resumo com documentos e PDF; edição com **autosave**; finalizar; sair; **perfil consulta recebe 403** ao criar ofício; **zero** erros de console/HTTP; **nenhuma requisição a outros hosts** (inclui localhost); sem rolagem horizontal |
| 8 | Queda real (SIGKILL no PID do host) de web e worker | ✅ web `healthy` de novo em **8 s**; worker reiniciado (`restart: unless-stopped`) |
| 9 | Restart do PostgreSQL com a aplicação no ar | ✅ `/saude/` 200 em 10/10 amostras; worker cai e volta sozinho |
| 10 | `down` + `up` (recria todos os contêineres) | ✅ 258 ofícios antes e depois; smoke ok (dados só nos bind mounts) |
| 11 | Backup diário (`backup.sh --motivo diario`) | ✅ dump 2,8 MB validado (1594 objetos, SHA-256) + **cópia externa** criptografada (restic → rest-server simulando o destino externo; 50 MB com documentos) |
| 12 | Restauração-teste **a partir da cópia externa** (perda total simulada) | ✅ 14 s — PostgreSQL isolado, `pg_restore` sem erros, contagens, **cadeia de auditoria íntegra (8871 eventos)** pelo `verificar_auditoria` do produto, **294 PDFs com SHA-256 conferido** |
| 13 | Atualização (mesmo produto, infra nova) | ✅ backup prévio + cópia externa, **0 migrações**, smoke ok, versão anterior registrada |
| 14 | Reversão (`pcpr.sh reverter`) | ✅ volta à imagem anterior, banco intacto, smoke ok |
| 15 | Restauração destrutiva ao vivo (`restaurar-banco`) | ✅ recusa sem `--confirmo-sobrescrever-homologacao`; com ela: backup antes, restauração, smoke ok; escrita da aplicação (`pcpr_app`) e worker validados depois |
| 16 | Rotinas diárias (`pcpr.sh rotinas`) | ✅ "Cadeia íntegra: 8906 evento(s)" |
| 17 | Monitor (`monitorar.sh`) | ✅ sem problemas; worker parado → alerta "serviço worker não está rodando"; ao voltar → "RESOLVIDO" (sem repetição) |
| 18 | Limpeza de imagens | ✅ mantém atual + anterior de todas as instâncias e a base do produto |
| 19 | Lint | ✅ `shellcheck -S warning` em todos os scripts; `ruff check .` limpo; `lint-imports` 16 contratos; `tsc` ok |
| 20 | Testes do produto pertinentes (`gestao/plataforma`, `gestao/identidade`) | ✅ 73 passed |
| 21 | `scripts/verificar.sh` (o mesmo que o CI roda, exceto o navegador) | ✅ ruff, import-linter (16 contratos), mypy, bandit, migrações sem pendência, `tsc` e **2376 testes** passaram (`✔ tudo verde`, 21 min). O E2E (navegador) desta branch falha pelas mesmas causas da `main` (`b3471bd`), corrigidas na PR #10 — este diff só toca `deploy/` e o ADR |

### Revisão da PR (Codex) — revalidação na mesma VPS simulada

| # | Verificação | Resultado |
|---|---|---|
| R1 | Instância de nome arbitrário (`prod`) com `config.settings.production` | ✅ recusa commit não aprovado, `--sem-backup`, `--semear` e imagem do produto ausente (sem `--construir-base`); `testar-classes`, `testar-documentos` e `comparar-renderizacao` recusam |
| R2 | Migração pendente (0050 desaplicada no banco sintético) | ✅ web e worker param, migração aplicada, serviços sobem, smoke ok |
| R3 | Migração que falha (coluna já existente) | ✅ alerta crítico, web e worker **ficam parados**, saída 1 |
| R4 | `restaurar-banco` com dump truncado / com SHA-256 divergente | ✅ ambos recusados **antes** do DROP (banco intacto: 258 ofícios); dump válido restaura com smoke ok |
| R5 | `comparar-renderizacao` | ✅ 8/8 iguais ao gravado (saída 0); com SHA gravado adulterado, saída 1 |
| R6 | `testar-documentos` interrompido (SIGTERM) com a pasta travada | ✅ trap devolve 0750; execução completa: tudo ok |
| R7 | Token do feed ICS nos logs | ✅ Gunicorn, Caddy (URI e Referer) e Nginx 1.29 (portas 80 e 443) gravam `/agenda/ics/[token]`; antes, o Gunicorn gravava o token |
| R8 | `docker stop` do worker | ✅ 0 s com `init: true` (antes: 60 s até o SIGKILL) |
| R9 | Reimplantar a mesma imagem | ✅ a imagem anterior registrada é preservada |
| R10 | Regressão | ✅ smoke 20/20, classes documentais 13/13, `shellcheck`, `ruff` |
| R11 | Backup com banco e documentos do mesmo instante | ✅ web e worker congelados ~3 s (dump + cópia por hardlinks), depois descongelados; snapshot externo restaurado e **aprovado** (300 documentos, cadeia íntegra) |
| R12 | Falha do dump com os serviços congelados | ✅ alerta crítico e web/worker descongelados pelo trap |
| R13 | `restaurar-teste --origem extenro` | ✅ recusado; `externo` aprovado 3×, após corrigir a espera pelo PostgreSQL efêmero (o servidor temporário da imagem respondia ao `pg_isready` e reiniciava) |
| R14 | `comparar_renderizacao.py` com amostras diferentes | ✅ documento só de um lado = divergência (saída 1), nos dois sentidos |
| R15 | `impressoes.tsv` das classes | ✅ bytes, SHA-256 do arquivo, páginas, fontes e SHA-256 do texto extraído (pypdf da imagem) |
| R16 | Boot do Gunicorn 26 | ✅ sem o ERROR do socket de controle (desligado; a raiz é somente leitura) |
| R17 | Instância de dados reais sem registro de homologação do trio produto + infra + imagem | ✅ recusada (registro em `/srv/pcpr/homologados.tsv`, gravado só por implantação sintética bem-sucedida) |
| R18 | `--porta 99999` | ✅ recusada antes de criar qualquer arquivo |
| R19 | Cópia por hardlinks impossível (simulada) | ✅ backup falha com alerta crítico; web/worker descongelados; nenhuma cópia ao vivo |
| R20 | `restaurar-banco` | ✅ web e worker param **antes** do backup de segurança (sem congelamento: já parados); restauração e smoke ok |
| R21 | Restauração-teste com SHA-256 de vias assinadas e anexos de prestação | ✅ externa aprovada com 318 arquivos conferidos (300 + 3 + 15); anexo adulterado reprovado ("arquivos divergentes do banco") |
| R22 | `reverter` depois de uma implantação que migrou (0050) | ✅ sem dump: recusado; com o dump pré-implantação: para, backup, restaura, sobe a imagem anterior, smoke ok (0050 desfeita) |
| R23 | `restaurar-banco` com um anexo referenciado ausente | ✅ alerta crítico listando o arquivo; web e worker ficam parados (antes desta correção, o `docker compose exec` no laço consumia a entrada e a checagem não via nada) |
| R24 | Monitor com o webhook fora do ar | ✅ estado não é dado por avisado; com o webhook de volta, o alerta é entregue e registrado; rodada seguinte não repete |

Consumo em repouso: web 303 MiB (3 workers), worker 69 MiB, PostgreSQL 80 MiB, Caddy 13 MiB.

## Achados durante a validação (corrigidos na infraestrutura)
- `check --deploy` reprovava por `mail.E001` → `verificar.py` com exceção explícita e condicionada.
- `COPY --chmod=0644` tirava o `x` da pasta `/opt/pcpr` → 0755.
- PGDATA em subpasta não era alcançável pelo usuário `postgres` → pasta montada como PGDATA, dono 999.
- Backup prévio com o banco parado → o deploy sobe o `db` antes do backup.
- uid 1000 da imagem coincide com usuário real do host → uid dedicado 10001.
- Monitor lia errado o estado de contêiner sem health check → separador explícito.

## Reproduzir a simulação
```bash
export PCPR_RAIZ=$PWD/sim/srv PCPR_ETC=$PWD/sim/etc
git clone -b <branch-de-deploy> <repo> sim/srv/infra && cd sim/srv/infra
deploy/vps/preparar-instancia.sh homologacao --dominio homologacao.pcpr.test --porta 8101
echo 'PCPR_SMOKE_MODO=local' >> "$PCPR_ETC/homologacao/instancia.env"
deploy/vps/implantar.sh homologacao <sha-40> --semear
```
(Proxy com `tls internal` e `/etc/hosts` só na simulação; na VPS o certificado é Let's Encrypt.)
