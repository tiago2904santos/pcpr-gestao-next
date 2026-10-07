# Plano aprovado pelo orquestrador — Resumo, Folha (cadastro/edição) e Documentos do ofício

> Consolida `parity/oficios-folha.md` (E1–E85, G1–G12), `parity/oficios-resumo.md` (R1–R42) e
> `parity/oficios-documentos.md` (D1–D44, F1–F10). IDs de item: H-nn (correção urgente),
> RS-nn (resumo), FL-nn (folha), DC-nn (documentos).

## Decisões do orquestrador

| # | Tema | Decisão | Por quê |
|---|---|---|---|
| D12 | Ordem | **Lote H primeiro** (perda de dados e documento travado), depois Resumo → Folha → Documentos | Prioridades 1–2 da missão: não perder dados nem quebrar regras |
| D13 | Data do ofício na emissão | Como o legado: ao emitir, a data do ofício passa a ser **hoje**, salvo se a pessoa alterou a data à mão. A revisão mostra a mudança e a consequência (Autorização × Convalidação, justificativa). Regra no domínio puro. | Fonte de verdade funcional; evita assunto/justificativa errados |
| D14 | Reabrir para correção | Entra no ⋮ e no "Mais ações" do resumo para quem tem a permissão, com motivo obrigatório | Rota/serviço existem e estavam inalcançáveis |
| D15 | Textos oficiais | Voltar ao texto do modelo oficial do legado **a menos que** o histórico do git mostre que o dono mudou o texto de propósito (então registrar aqui e manter) | Conteúdo de documento oficial não muda sem decisão |
| D16 | Regra de tempo de viagem (ADR 0016) | **Mantida** até decisão do dono — pergunta registrada | Decisão estrutural anterior do próprio projeto |
| D17 | "Emitir nova versão" sem retificar | **Não** nesta etapa — pergunta ao dono | Muda o ciclo de vida do documento |
| D18 | Dados para o eProtocolo | Componente único (domínio puro `dominio/eprotocolo.py` + parcial com Copiar/Copiar tudo) usado no resumo e na folha (depois Termos e Prestação) | Lacuna do legado, alto uso diário |

## Lote H — correções urgentes (dados e documentos)
- H-01 G1: salvar a folha não pode desmarcar o motorista (campos do bloco fechado `disabled`; serviço só normaliza quando o modo mudou) + teste de serviço e e2e (marcar → autosave → recarregar) + saneamento dos rascunhos afetados (comando idempotente ou migração de dados; PREVIEW 247/260/262/263).
- H-02 F1: geração que falha grava `falhou` com o erro fora do savepoint; tela mostra "Falhou" + "Gerar de novo" (serviço idempotente); `gerando` acompanha por polling até pronto.
- H-03 G3: "Outro meio" — uma regra só no serviço e na tela.
- H-04 D13: data do ofício na emissão.
- H-05 e2e de `test_fluxo_oficio.py`: os 5 desatualizados atualizados para o produto atual (sem mascarar defeito) e o de G1 verde.

## Lote RS — Resumo
P0 e P1 de `parity/oficios-resumo.md`: Dados para o eProtocolo (D18); Reabrir (D14); PDF que vale × minuta e polling de geração; uma lista de documentos (ordem ofício → justificativa → termos, versão, emitido em/por, assinado, versões anteriores recolhidas); histórico visível para emitido/cancelado; consistência com a identidade (Roteiros/Termos).

## Lote FL — Folha (cadastro e edição)
P0–P2 de `parity/oficios-folha.md`: indicador de salvamento visível (E70/G5); avisos de protocolo repetido e condutor não autorizado na conferência; uma pendência por falta; avisos de viatura no bloco certo; diárias ao vivo e "como foi calculado" + valor por extenso; sugestão do ofício de origem do motorista de fora; marcadores `{destino}`/`{periodo}` nos textos prontos; Dados para o eProtocolo (D18); duplicar sem copiar marcas; erro 500 do motorista inválido; consultas ≤ 25; esqueleto com altura reservada nas folhas de documento.

## Lote DC — Documentos
P0–P1 de `parity/oficios-documentos.md`: ofício/protocolo de origem do motorista de fora no papel; nº da solicitação por servidor quando houver; marca d'água atrás do conteúdo; justificativa com sede e data por extenso; textos oficiais (D15); DOCX com a mesma paginação do PDF; valor por extenso impresso (ou tirar o anúncio); conferência do PDF assinado antes de anexar.

## Perguntas ao dono do produto (não bloqueiam)
1. ADR 0016 — tempo de viagem/adicional diferente do legado: manter?
2. "Emitir nova versão" sem retificar (o legado permitia)?
3. Reaproveitar rascunho vazio abandonado (legado, L9)?
4. Nº da solicitação na tabela de equipe do ofício quando ainda não existe prestação.
