# ADR 0029 — Composição do Resumo como mesa operacional

Status: proposta visual, limitada ao piloto; validação funcional obrigatória e aprovação estética do usuário pendente.

## Contexto

O Resumo preserva as funções institucionais, mas sua composição de ficha em modal foi reprovada visualmente. Documentos e decisões aparecem depois de uma sequência longa de metadados. A mudança necessária é estrutural de apresentação, sem alteração de domínio.

## Decisão

Explorar três composições no UI Lab antes de escolher a final. A candidata operacional separa identidade, missão e estação documental, com contexto administrativo lateral em telas amplas e leitura sequencial em telas estreitas. Extrair padrões semânticos compartilhados no Design System. Manter o diálogo nativo, uma rolagem, IDs HTMX/OOB, footer, foco, URLs, condições de permissão e conteúdos integrais.

Não criar rota de negócio, API, biblioteca, cálculo ou estado institucional novo. A exploração do UI Lab é sintética e não executa operações. Somente o piloto recebe a nova variante, até aprovação visual.

## Alternativas

- Documento operacional vivo: privilegia leitura, mas mantém arquivos longe das decisões.
- Registro editorial: identidade forte, porém pode consumir área sem ajudar a operação.
- Microajustes no dossiê atual: rejeitados explicitamente pelo usuário.

## Consequências

Templates se dividem em unidades de apresentação reutilizáveis; estilos usam tokens existentes. A troca da ordem requer testes de teclado, axe, estados documentais, revisão, menus, cópia e polling. Capturas das alternativas e duas iterações são obrigatórias. Não propagar a variante sem aprovação estética do piloto.
## Refinamento da composição solicitado pelo usuário

Depois da reconstrução, o usuário declarou a direção melhor e a base boa, mas
solicitou correções no mesmo piloto. Cabeçalho e ações permanecem fora do corpo
rolável; equipe/transporte passam a uma faixa completa depois do roteiro/contexto.
Dados copiáveis recebem variante compacta, com os mesmos controles nativos e IDs.
Conferência serena separa total e metadados; tipo/prazo conservam explicação integral
em divulgação acessível. Nenhuma alteração no domínio, nas permissões ou nos documentos.

Evidências e diagnóstico: `docs/visual-agents/visual/oficios-resumo-refinamento.md` e
`docs/visual-agents/qa/oficios-resumo-refinamento-evidencias.md`. A aceitação da direção
como base não equivale à aprovação visual definitiva desta implementação.
