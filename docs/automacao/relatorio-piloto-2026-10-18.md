# Relatório do piloto WhatsApp + IA — 18/10/2026

Sistema de testes independente, com dados fictícios (ADR 0046). Tudo foi feito no ramo
`feat/piloto-whatsapp-ia` (worktree `piloto-whatsapp-ia`), **sem commit**. Nada foi ligado contra
a Meta nem contra a Anthropic. A matriz item a item está em
[implementacao-piloto.md](implementacao-piloto.md).

## 1. Funcionalidades e onde acessar

| O quê | Onde |
|---|---|
| Painel da automação: indicadores, comunicações recentes, exceções, canal, simulador | `/automacao/` |
| Comunicações: abas Aguardando aprovação, A sair, Com problema, Enviadas, Não saíram; aprovação em lote; detalhe com tentativas, status, recebidos e exceções | `/automacao/comunicacoes/` |
| Recebidos: quarentena, associação, conferência, descarte, arquivo protegido | `/automacao/recebidos/` |
| Fila de exceções com responsável e ações | `/automacao/excecoes/` |
| Contatos verificados e opt-in; testadores do LAB (lista fechada) | `/automacao/contatos/`, `/automacao/testadores/` |
| Canal e chaves: geral, por canal e por fluxo; modos sombra, assistido e automático | `/automacao/canal/` |
| Credenciais por integração, com rotação e emergência; aprovações; histórico das ferramentas; links pessoais; delegação | `/automacao/credenciais/`, `/aprovacoes/`, `/execucoes/`, `/links/`, `/delegar/` |
| Webhook da Cloud API (GET de verificação e POST assinado) | `/integracoes/whatsapp/webhook/` |
| API de automação v1 (desligada no PREVIEW) | `/api/automacao/v1/` |
| Link de km sem login, offline | `/p/<token>/` (chega pela mensagem) |
| Central de ajuda e Minha situação | `/ajuda/` |
| Sugestões de IA, usos e orçamento | `/assistencia/` e links nas telas de RT, ofício, plano, importação, comprovante, catálogo e relatórios |
| Proposta consolidada | Viagem → ações → "Proposta consolidada" (`/viagens/proposta/`) |
| Situação do aviso na prestação | Menu do cartão da prestação |

No PREVIEW (`/conta/entrar/`, campos vazios) tudo aparece com dados de demonstração e o canal
simulado.

## 2. Arquivos e migrações

- **Contextos novos:**
  - `gestao/automacao/`: modelos, serviços, worker, API v1, telas, ferramentas e simulador;
  - `gestao/integracoes/whatsapp/`: porta, adaptadores simulado e Cloud API, webhook e transporte;
  - `gestao/integracoes/ia/`: porta, simulado, gravado e Anthropic;
  - `gestao/assistencia/`: usos de IA, orçamento, central de ajuda e assistente.
- **Viagens:** `comunicacoes.py`, `comunicacoes_viagem.py`, `km_link.py`, `proposta.py`,
  `ferramentas_automacao.py`, `ia_usos.py`, `ia_leituras.py`, `situacao_servidor.py`, as views e os
  templates correspondentes, e ganchos em `prestacao.py`, `services.py` e `diario.py`.
- **Migrações:**
  - `automacao`: 0001 (inicial), 0002 (auditoria, sem contatos), 0003 (links e API),
    0004 (eventos de contato), 0005 (reservas anteriores), 0006 (índices de limpeza e do limite
    por hora), 0007 (ids do canal até 300 caracteres);
  - `assistencia`: 0001 a 0003.
  - Nenhuma migração de dados reais.
- **Configuração:** `config/settings/base.py` e `preview.py`, `config/urls.py`,
  `pyproject.toml` (contratos de import), `compose.preview.yml` (serviços `automacao` e `ia`,
  simulados), além dos modelos de proxy e do gunicorn, que mascaram `/p/<token>`.
- **Documentação:**
  - ADR 0047 e ADR 0048;
  - `docs/ops/lab-whatsapp-ia.md`;
  - `docs/integrations/whatsapp-cloud-api-referencia.md`;
  - `docs/automacao/ia-usos.md` e `proposta-consolidada.md`;
  - `docs/parity/automacao-whatsapp-ia.md`;
  - este relatório.
- **Não commitar:** 10 arquivos de Eventos, Coffee e `components.css` estão aqui na versão do
  PR #22, porque o main tem marcadores de conflito neles (lista em
  `scratchpad/piloto/NAO-COMMITAR.txt`).

## 3. Testes e resultados

| Suíte | Resultado |
|---|---|
| Suíte rápida completa (`pytest -m "not e2e…" -n 6`) | 3305 passaram, 16 falharam, **nenhuma da automação**: 13 em Eventos (arquivos com conflito no main) e 3 de OCR/LibreOffice (não instalados nesta máquina) |
| Automação, API e garantias (unit) | 76 passaram, incluindo D1–D4, chave longa ou não ASCII e envelope × esquema |
| IA e assistência | 160 passaram |
| Navegador: `tests/e2e/test_automacao.py` (fluxo ponta a ponta, axe, sem rolagem) e `test_km_offline.py` (offline, Enter, reflow a 360 px) | 8 passaram |
| `scripts/verificar.sh`, parte estática (ruff, 20 contratos de import, mypy, bandit, migrações, tsc) | tudo verde; `mypy` sem erros em 438 arquivos |
| Protótipo n8n × simuladores (PR #23): T1–T20 e TW0–TW16 | todos passaram no n8n 2.43.7 |
| n8n × **API real** do PCPR (`testar_pcpr_real.py`) | rodada final: **todos os aplicáveis passaram** (T1–T5, T7, T8, T10, T12, T13, TW0–TW13, X1, X2); 4 não se aplicam (T6, T9, T11, TW4) |

**n8n × API real.** Na primeira rodada, 24 cenários passaram, 6 falharam e 4 não se aplicam.
Os defeitos achados foram corrigidos na implementação, com teste:

- **D1:** envelopes fora do esquema;
- **D2:** status repetido com outro horário dava 422;
- **D3:** canal de entrada bloqueado não era respeitado;
- **D4:** mesma chave com outro arquivo dava 422 em vez de 409;
- **O1:** `hub.challenge` ecoado sem filtro.

Na rodada final, tudo o que se aplica passou. O detalhe está em
`docs/automacao/n8n/pcpr/README.md` e em `prototipo/resultados/resultados-pcpr-real.json`.

## 4. Evidência visual

- `artifacts/capturas/piloto-whatsapp-ia/{360,1440}/`: 19 telas em 2 larguras. Não versionado;
  para gerar de novo, use `scripts/capturar.py` com o servidor de captura.
- Revisões feitas antes de fechar:
  - UX: todos os P1 corrigidos;
  - acessibilidade: altos e médios corrigidos;
  - desempenho: consultas, índices e peso da página de km;
  - segurança: as rodadas anteriores (M1–M8).

## 5. Workflows do n8n exportados desligados

- `docs/automacao/n8n/pcpr/`: W1–W3 e W5–W8 para a **API real**, com `"active": false` e
  credenciais só por id e nome. O README explica importação, ativação no LAB e a avaliação dos
  nós nativos (presos na Graph v13/v19, daí o uso de HTTP Request).
- `docs/automacao/n8n/`: W1–W8 do protótipo × simuladores (PR #23).

## 6. Rodar localmente

```bash
# testes (PostgreSQL de teste descartável)
uv run pytest -m "not e2e and not visual and not a11y and not perf" -n auto
uv run pytest tests/e2e/test_automacao.py tests/e2e/test_km_offline.py
# preview navegável (DEMO, simulado)
scripts/preview.sh local
# worker da automação (simulado) e da IA
uv run python manage.py processar_automacao
uv run python manage.py processar_ia
```

Ensaio no simulador: em `/automacao/`, use "Processar a fila agora" e, em cada comunicação,
simule a entrega, a leitura, uma falha ou a resposta com um PDF fictício.

## 7. Configurações e credenciais que ainda faltam (nenhum segredo aqui)

Todas só no ambiente do LAB e fora do repositório (`docs/ops/lab-whatsapp-ia.md`, seção 2):

- `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WABA_ID`, `WHATSAPP_ACCESS_TOKEN` (usuário de sistema),
  `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`;
- modelos aprovados na Meta (`WHATSAPP_MODELOS`);
- para o n8n: `N8N_EVENTOS_URL` e `N8N_EVENTOS_SEGREDO`, e a credencial de transporte criada em
  `/automacao/credenciais/`;
- para a IA, só com autorização de custo: `IA_MODO=anthropic`, `IA_API_KEY` e `IA_MODELO`;
- testadores autorizados, com contato verificado e opt-in.

## 8. O que funciona com simulador × o que foi validado com o provedor real

- **Simulador / adaptador gravado:** todos os fluxos da primeira entrega, a fundação, os avisos
  de viagem, o link de km e os 11 usos de IA implementados. O n8n também foi testado contra os
  simuladores e contra a API real do PCPR, com a Graph API simulada.
- **Provedor real:** **nada foi validado** contra a Meta ou a Anthropic. Isso depende do LAB e
  das credenciais.
- **Não implementado:** envio de documentos como mídia, DB/RT para assinatura, resumos de
  outros módulos, AUT-92 e AUT-171.

## 9. Custos e como ficar sem custo extra

- **Simulador e PREVIEW:** custo zero, sem rede.
- **WhatsApp:**
  - cobrança por mensagem, conforme a categoria do modelo;
  - o PCPR registra `pricing` de cada status, sem presumir gratuidade;
  - para custo zero, não ligue `WHATSAPP_MODO=cloud_api`;
  - no LAB, use o número de teste, `WHATSAPP_LIMITE_POR_HORA` baixo e lista curta de testadores.
- **IA:**
  - fica simulada enquanto não houver chave;
  - com chave, há teto mensal por uso e global em `/assistencia/`; ao atingir o teto, bloqueia e
    volta ao caminho sem IA;
  - o custo exibido é **estimado**, não a fatura.
- **n8n:** Community self-hosted, sem licença. O editor não deve ser publicado sem a análise da
  infraestrutura.
- Nada pago foi contratado nem ligado.

## 10. Ligar o LAB, desligar e reverter

**Ligar** (detalhe em `docs/ops/lab-whatsapp-ia.md`, seções 1 a 5):

1. Conferir o portão de pré-requisitos.
2. Definir as variáveis e rodar `whatsapp_check` (com `--ping`, que só lê).
3. Configurar o webhook na Meta.
4. Ligar a chave geral, depois o canal, depois cada fluxo, sempre na ordem sombra → assistido →
   automático.
5. Subir o worker.
6. Fazer o ensaio ponta a ponta com um testador.

**Desligar e reverter** (seção 6 do roteiro):

- "Desligar tudo agora" no painel para os efeitos novos; status e mensagens continuam sendo
  registrados.
- Para voltar ao simulador, remova `WHATSAPP_MODO` e reinicie.
- Para desfazer o LAB:
  1. remova as variáveis;
  2. remova a assinatura do webhook na Meta;
  3. revogue o token de sistema;
  4. revogue as credenciais do n8n.
- O banco não precisa ser apagado: a trilha fica.
