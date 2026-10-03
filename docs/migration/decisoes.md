# Decisões do dono do produto

Registro oficial das decisões que mudam regra de negócio, permissão, documento, numeração ou
comportamento institucional. Cada decisão aponta requisitos, arquivos e testes. Pendências
classificadas como **bloqueante** (exige decisão), **não bloqueante** (técnica) ou
**dependência externa** (credencial, autorização, ambiente).

## Ofícios — decisões confirmadas em 03/10/2026

| # | Decisão | Comportamento comprovado na referência | Implementação no novo | Testes | Situação |
|---|---|---|---|---|---|
| D1 | **Arquivar ofícios** — implementar; não é exclusão | `acao == 'arquivar'` muda o status para ARQUIVADO (`viagens_oficios/views.py:829`). Sem botão na tela, sem desarquivar, sem aba, sem regra de quem pode | marca `arquivado_em/por` (migração 0011), `services.arquivar/desarquivar`, `policies.pode_arquivar/desarquivar`, aba **Arquivados**, menu da linha e da janela | `test_servicos.py::TestArquivar`, `test_views.py::TestCicloDeVidaNaTela::test_arquivar_leva_para_a_aba_arquivados` | ✅ implementado e testado |
| D2 | **Reativar cancelado** — só gestor, com justificativa | `reativar()` desliga o cancelamento e **apaga** o motivo (`core/models.py:32`); volta ao status que tinha | `situacao_anterior` (guardada ao cancelar; migração preenche os antigos pelo histórico), `services.reativar`, permissão `viagens.reativar_oficio` (só gestor), janela "pedir motivo" | `test_servicos.py::TestReativarCancelado` (sem permissão, sem justificativa, emitido→emitido com mesmo número e documentos, rascunho→rascunho, histórico de→para), `test_views.py::TestCicloDeVidaNaTela` | ✅ implementado e testado |
| D3 | **Motorista externo** — migrar | modo SERVIDOR/MANUAL; manual exige nome; motorista fora da equipe (manual ou servidor) exige ofício de origem `N/AAAA` e protocolo de 9 dígitos (`services.py:170-195`); diárias contam só a equipe (`forms.py:161`); documento mostra o nome (`documents.py:245`) | ver §D3 | ver §D3 | em andamento |
| D4 | **Editor visual principal; validar cobertura do DOCX** | geração DOCX + PDF por tipo | análise em [docx-cobertura.md](docx-cobertura.md) | — | em andamento |
| D5 | **Manter filtro por data de criação** | `criacao_de`/`criacao_ate` com calendário próprio; ordenação "Criação: mais recente/antiga" | `criacao_de/criacao_ate` → `data_oficio` (é o que a referência filtra), período na gaveta "Mais filtros", ordenação "Data do ofício" | `test_views.py::TestFiltroPorDataDoOficio` (limites inclusivos, pontas invertidas, data inválida, combinação com situação/busca/ordem, paginação, contagem de filtros) | ✅ implementado e testado |
| D6 | **Lista própria de justificativas** | lista com situações (Todas/Pendentes/Preenchidas), busca, regra de prazo, texto, modelo, editar (janela), excluir (limpa o texto), documentos (`docs/paridade/justificativas-lista.md` da referência) | ver §D6 | ver §D6 | em andamento |
| D7 | **Marcador "Autorização"** | — | já é o rótulo do marcador "nenhum" na folha (`forms.py`, choices do `marcador`); é só rótulo: o assunto Autorização × Convalidação continua calculado (`dominio/assunto.py`) | `test_views.py` (folha) | ✅ confirmado |
| D8 | **Teto de 40 requisições nas folhas de edição, condicionado a validação** | — | ver §D8 | `tests/e2e/test_desempenho.py` | em validação |

## Detalhamento

### D1 — Arquivar
- Lacunas da referência (documentadas, não inventadas como regra institucional): não diz quem
  desarquiva, se arquivado pode ser editado, nem como a lista trata arquivados.
- Escolhas técnicas, reversíveis e conservadoras (podem mudar por decisão): arquivar é uma
  marca **ortogonal** à situação (como o cancelamento na referência), com quem e quando;
  **desarquivar** existe (nada se perde); arquivado sai das abas de trabalho e aparece em
  "Arquivados"; permissão de editar ofício (operador e gestor, como a referência exige só
  operador); arquivado não é editado nem emitido até ser desarquivado.

### Regressão corrigida junto
Cancelar e reabrir tinham perdido o botão quando a página de detalhe foi apagada: as ações do
ciclo de vida voltaram no menu da linha e no "Mais ações" da janela de resumo
(`oficios/_acoes_ciclo.html`), decididas por `policies.acoes_do_oficio`.

### D2 — Reativar cancelado
- Diferença intencional: a referência apaga o motivo do cancelamento; aqui o cancelamento
  anterior continua no histórico e a reativação grava responsável, justificativa, situação
  anterior e posterior (Histórico + trilha do banco).
- O ofício volta à situação que tinha antes de cancelar (rascunho ou emitido). O número
  permanece o mesmo (cancelado já ocupava o número); documentos emitidos continuam os mesmos —
  reativar **não** emite de novo.

### D3 — Motorista externo
- Paridade: nome obrigatório; RG, CPF, cargo, unidade e observação opcionais; ofício de origem
  (`N/AAAA`, até 6 dígitos) e protocolo de 9 dígitos obrigatórios para emitir.
- Diárias: o motorista externo **não** entra na conta (a referência conta só a equipe).
- Documento: o nome do motorista externo sai no campo motorista.

### D5 — Data de criação
- Na referência, "criação" é `data_criacao`, que é a **data do ofício** (rótulos "Ofício a partir
  de / até"; desempate por `criado_em`). Aqui: `data_oficio`, rótulo "Data do ofício".
- Filtro `criacao_de`/`criacao_ate` (período) na gaveta "Mais filtros", combinável com busca,
  situação, demais filtros, ordem e paginação; ordenação por criação.

### D6 — Justificativas
- A justificativa continua sendo do ofício (sem cópia de dados): a lista é uma leitura dos
  ofícios com justificativa exigida ou escrita.

### D8 — Requisições
- O teto 40 só vale depois da validação descrita em `docs/quality/performance-budgets.md`.

## Pendências abertas

| Pendência | Tipo |
|---|---|
| Acesso autorizado à referência em execução para comparação visual/funcional | dependência externa |
| eProtocolo real (credenciamento, usuário de sistema, `consumerId`, IP fixo, escopos) | dependência externa |
| Central de Viagens (existência de API, requisitos) | dependência externa |
| Hospedagem/IA/n8n (plano, recursos, backups, custos) | dependência externa |
