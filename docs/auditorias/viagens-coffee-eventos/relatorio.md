# Relatório final — auditoria visual e de paridade de Coffee Break e Eventos Sociais

Missão: comparar Coffee Break e Eventos Sociais com as telas aprovadas de Viagens (referência
visual) e com o sistema antigo (inventário funcional), corrigir o que diverge e comprovar o
resultado. Registro da execução em [`registro.md`](registro.md); matrizes em
[`matriz-visual.md`](matriz-visual.md), [`matriz-paridade-eventos.md`](matriz-paridade-eventos.md)
e [`matriz-paridade-coffee.md`](matriz-paridade-coffee.md); evidências em
[`evidencias/`](evidencias/).

**Não está "100% migrado".** Restam itens parciais, ausentes, não verificados e quatro que
dependem de decisão do usuário. Todos estão listados abaixo, com a contagem e o denominador.

## Escopo e método

| Item | Valor |
|---|---|
| Sistema novo | `pcpr-gestao-next`, branch `ccr-fefbaf91-facwfi` (PR #22), sobre `main` `ef66a4b` |
| Sistema antigo | `Sistema-de-Gest-o-de-Eventos-Sociais` @ `53dbf3f`, **lido, não executado** (sem ambiente) |
| Ambiente | PREVIEW local (`scripts/preview.sh local`, PostgreSQL `pcpr_preview`, DEMO, dados sintéticos) |
| Fora do escopo (respeitado) | deploy, dados de produção, numeração oficial, e-mails ou integrações reais |
| Capturas | `scripts/auditoria_coffee_eventos.py`: 40 cenários (34 de Coffee/Eventos + 6 de Viagens) × 360/768/1440 px, com rolagem horizontal, erros de console e axe (WCAG 2.2 AA) |
| Desempenho | mesmo script, `medir`: consultas SQL e mediana de 5 respostas por página, no processo, como o usuário demo |

## Resultado — auditoria visual

24 linhas na matriz (31 IDs de página; algumas linhas agrupam páginas irmãs):

| Situação final | Linhas |
|---|---|
| Corrigida | 16 |
| Alinhada (já seguia a referência) | 6 |
| Alinhada com diferença de domínio (justificada) | 2 |
| **Total** | **24** |

Principais correções: catálogo de Eventos refeito no padrão VR-15 (a **paginação nunca
aparecia** — o bloco não existia na base); barras de rodapé no padrão de Viagens ("Voltar" à
esquerda, status, `barra-acoes__acoes`, Finalizar como principal) em 5 folhas e em 5 páginas
que não tinham barra; "Ordenar por" na gaveta "Filtros e ordem" das listas; lista de lotes com
busca, exercício, ordem, paginação e contagem nas abas; histórico das folhas na linha do tempo
de Viagens (`historico_folha`); seções da OS numeradas em sequência; despacho e transferência
em `campos-folha`; painel do Coffee com a lateral em pilha; cadastros com `registro--catalogo`.

Pendências visuais declaradas dentro das linhas "Corrigida": a linha da lista ainda não abre o
resumo numa janela (CB-P02, EV-P02); a folha da OS não tem autosave e mantém dois formulários
(financeiro e documentos gravam em separado) (CB-P05); classes `campo--md/lg` sem efeito
dentro de `campos-folha` na nova solicitação (EV-P03, sem impacto visual).

Medidas nas capturas "depois" (40 cenários × 3 larguras): **0** rolagem horizontal, **0**
erro de console, **0** violação do axe em Coffee e Eventos. A única violação é do fragmento de
resumo de Viagens (VI-D02, 2 em 360 e 1440), **anterior à missão** (igual na rodada "antes").
Antes × depois de 18 páginas em `evidencias/*-antes-depois.png`; todas as 40 em
`artifacts/auditoria-coffee-eventos/comparacoes/index.html` (gerado, fora do git).

## Resultado — paridade funcional

| Situação final | Eventos (de 96) | Coffee (de 111) |
|---|---|---|
| Equivalente (lida no legado; coberta por testes do novo) | 45 | 73 |
| Equivalente — **corrigida nesta missão** (com teste) | 14 | 12 |
| Equivalente — **verificada nesta missão** (com teste) | 1 | 1 |
| Substituída (justificada) | 9 | 13 |
| Descontinuada (decisão documentada) | 0 | 1 |
| Parcial | 19 | 5 |
| Ausente | 6 | 2 |
| Pendente de decisão do usuário | 0 | 4 |
| Não verificada | 2 | 0 |
| **Total** | **96** | **111** |

Defeitos encontrados: **9 em Eventos e 6 no Coffee — todos corrigidos**, cada um com teste:

- Eventos: cancelar apagava a decisão da DG (F44); anexos editáveis durante e depois do despacho
  (F50); transferir terminava em 404 (F46); quantidade inválida da DG ignorada e versão sem
  mudar (F37); CEP sem validação (F12); motorista entre todos os servidores (F14); histórico
  perdia os campos no reenvio (F28); operador de Viagens não gerava a viagem (F65);
  paginação do catálogo (F02b).
- Coffee: o ano do número da OS mudava na edição (F26); "parada há" zerada por evento futuro
  (F94); `{local}` do e-mail sem endereço (F97); vias do ofício fora da OS principal do
  pagamento conjunto (F64); parte vazia interrompia o download do protocolo (F72); corrida ao
  salvar a configuração dava erro 500 (F14).

Lacunas preenchidas além dos defeitos: ordenação e exportação na ordem da tela (EV-F82,
CB-F85), lista de lotes (CB-F79), valores e contatos do lote (CB-F81), protocolo do ofício que
vira o de pagamento (CB-F52), textos prontos que se somam no despacho (EV-F41), faixa da
devolução com data e autor (EV-F57), "Marcar como atendida" e "Registrar a entrega" nos ⋮
(EV-F85, CB-F87 parcial), botões "Enviar a OS/OB" no painel (CB-F93), atalho do relatório do
contrato (CB-F09), trilha do banco em todas as tabelas (CB-F109; o lembrete diário de Eventos
fica fora por decisão do modelo) e anexos só pela view de quem vê (EV-F96).

### O que falta (não migrado ou não comprovado)

- **Decisão do usuário (4, Coffee):** numeração da OS e do ofício compartilhada com Viagens
  (CB-F25, CB-F28); importar o PDF do processo de pagamento (CB-F110) e a planilha (CB-F111).
  Também pede decisão: visões SQL para Power BI (EV-F93, sem decisão documentada).
- **Ausente (8):** Eventos — anexos na criação (F23), guardar o e-mail original como anexo
  (F76), sincronizar a viagem ao reabrir (F60, fora de E4), rotina de viagens pendentes (F68),
  visões SQL (F93), importar/exportar entre ambientes (F94); Coffee — busca de endereços já
  usados (F36), soltar o PDF do processo na lista (F89, depende de F110).
- **Parcial (24):** listadas nas matrizes com o que falta em cada uma (ex.: preencher com
  e-mail — formatos, campos vazios e órgão sugerido; etapas sem quem/quando; conferência de
  agenda ao vivo; validade do link do fornecedor fixa em 30 dias; copiar o CNPJ nas certidões).
- **Não verificada (2):** resumo diário "N eventos em 30 dias" (EV-F92) e falha de banco no
  despacho (EV-F95 — transação existe, falta teste de falha simulada).

## Desempenho

Consultas SQL por página (determinísticas):

| Página | Antes | Depois |
|---|---|---|
| Folha da OS (CB-D01..D04) | 31–33 | **21–23** |
| Folha da solicitação (EV-D01..D06) | 34–39 | **30–36** |
| Catálogo de tipos de evento (EV-C02) | 30 | **14** |
| Lista de lotes (CB-L04) | 13 | 16 (contagem das abas e lista de exercícios — dentro do orçamento) |
| Detalhe do lote (CB-D07) | 14 | 15 (valores do lote) |
| Demais páginas de Coffee e Eventos | — | iguais |

A folha da solicitação de Eventos **continua acima do orçamento de 25** do middleware (26–32
pela conta dele; o script conta também sessão e usuário): o que sobra é histórico, conflitos e
os selects do formulário. Fica como pendência de desempenho.

Tempo de resposta: as medianas "depois" subiram também em páginas que a missão não tocou
(VI-L02 413→547 ms, VI-P01 118→145 ms, CB-C04 22→34 ms), sinal de variação do ambiente; por
isso **não declaro ganho nem perda de tempo** — o ganho comprovado é o de consultas. Dados em
`evidencias/{antes,depois}-desempenho.json`. (VI-D01 não é comparável: na rodada "antes" o
cenário apontava para um ofício emitido, que redireciona.)

## Validação

| Verificação | Resultado |
|---|---|
| Testes rápidos (toda a suíte, `-m "not e2e and not visual and not a11y and not perf"`) | **2786 aprovados, 5 falhas** — as 5 em Viagens e **anteriores à missão**: falham igual em `origin/main` sem as mudanças (2 de OCR sem conversor no ambiente; `test_prestacao::test_lista_cartao_e_acoes`, `test_prestacao_texto::…versoes`, `test_diario::test_motorista_de_outro_oficio…`) |
| Coffee + Eventos + integração com Viagens + trilha (rodada final, depois dos últimos ajustes) | **182 aprovados** |
| ruff, fronteiras (16 contratos), mypy (327 arquivos), bandit, migrações, tipos JS | verdes |
| Navegador: `test_coffee`, `test_eventos`, `test_solicitacoes_evento` e os casos de Coffee/Eventos de `test_acessibilidade` | **26 aprovados** |
| Regressão de Viagens | telas de referência recapturadas sem mudança de medidas; único componente de Viagens alterado: `oficios/_evento.html` (mostra `h.mudancas` só quando existe — Viagens não passa) |

Testes que mudaram de expectativa, e por quê (comportamento corrigido para o da referência,
não para esconder regressão): devolver não aplica mais as quantidades da DG (EV-F35);
operador de Viagens gera sem ver a solicitação (EV-F65); o botão do painel leva ao e-mail da OS
ainda não enviada (CB-F93); catálogo de Eventos com a nova interface (e2e).
