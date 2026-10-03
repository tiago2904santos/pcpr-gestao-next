# ADR 0017 — Leitura do ofício na janela de resumo, sem página de detalhe

**Status:** aceita · **Data:** 2026-10-02

## Contexto
O piloto tinha três telas por ofício: lista, **detalhe** (somente leitura) e edição. O detalhe
repetia o que a janela de resumo da lista já mostrava (dados, equipe, roteiro, diárias,
documentos, histórico) e obrigava a navegar para fora da lista para ler um emitido e voltar.
A evolução da janela de resumo (abre na própria lista, `?resumo=<pk>` reabre por link) a
tornou a leitura completa do ofício.

## Decisão
A página de detalhe foi **removida**. Ler um ofício é abrir a janela de resumo na lista
(`/viagens/oficios/?resumo=<pk>`); alterar é a folha de edição (`/oficios/<pk>/editar/`),
que só rascunhos abrem. Links que apontavam ao detalhe passam a apontar ao resumo; a
folha de edição ganhou os blocos de leitura que faltavam (documentos e histórico, no cartão
Documentos), para que quem edita também veja o que o detalhe mostrava.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Manter detalhe e resumo | Duas telas para o mesmo conteúdo; divergiam a cada ajuste visual. |
| Detalhe como a única leitura (sem janela) | Perde o contexto da lista e a leitura rápida de vários ofícios em sequência. |

## Consequências
- Positivas: um só lugar de leitura; menos rotas, menos CSS e menos testes duplicados.
- Negativas: a janela é modal — ler dois ofícios lado a lado exige duas abas (`?resumo=`).
- Obrigatório: toda informação de leitura nova entra na janela de resumo (e, quando faz
  sentido para quem edita, na folha de edição), nunca numa página própria.
