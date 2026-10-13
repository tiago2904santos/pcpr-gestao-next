# VI02/VI03 — Folha e lote de Viagens, 12/10/2026

Base `b2b8887`; cobertura ainda21/100. Contrato em product/propagacao-identidade.md.
Dados DEMO preservados: navegação/capturas somente GET/HEAD; suíte em banco e mídia
TEST isolados. Arquivo de equipe do usuário intocado.

## Evidências antes

Doze capturas `viagens-folha-retomada-*`: vinculada1, básica5, cancelada3 e
lote1, em360/768/1440, todas HTTP200/console vazio/sem overflow. Mais18capturas
`viagens-folha-secao-*` e `viagens-folha-menu-*` mostram partes inferiores em
tamanho legível e menu aberto; Enter/Escape/devolução de foco passaram.

## Problemas concretos

1. `_leitura.html`: `dl.metadados` sem grid e filhos sem classe `metadado`.
   Tipo/Período/Destinos ficam empilhados sem hierarquia no modo consulta/cancelada.
   Solução: padrão canônico do Resumo, já carregado por listas.css; sem novo CSS.
2. `_conferencia.html`: conteúdo direto de `li.checklist__item` é distribuído
   em vários itens flexíveis. A captura `viagens-folha-secao-conferencia-360.png`
   demonstra datas e números fragmentados em pequenas colunas. Solução: mensagem
   num único bloco inline, preservando link/ênfase/textos e ação Aplicar em todos.

Restante da composição preservável após revisão própria e independente: vínculos,
grupos documentais, equipe/transporte do lote, histórico e barra no fluxo.
Descrição ausente no modo consulta já ocorre em3708d54; lacuna anterior registrada,
não atribuir à correção visual nem inventar comportamento nesta rodada.

## Limpeza

Revalidados template/includes/JS e seletores removidos anteriormente: cinco regras
`.vinculo .caixas*` e duas `checklist__sub` não reapareceram. Bases caixas/checklist
mantêm consumidores legítimos, inclusive UI Lab. Não há nova exclusão segura indicada.

## Validação final

Suíte integrada92178 terminou **17 aprovados em320s**: identidade Folha/lote,
fluxo Viagem, Lista e acessibilidade. Nova cobertura de leitura preparada
para consulta/cancelada em três larguras, com texto longo, conteúdo preservado,
hierarquia real, axe e ausência de overflow. As duas correções foram aplicadas
após o baseline. Suíte focada62728 terminou: **13 aprovados em145,02s**, incluindo HTTP da conferência.
Doze capturas `viagens-folha-refinado-*` concluídas com HTTP200/console vazio/
sem overflow. A imagem ampliada da conferência360 agora mostra frases contínuas;
cancelada768 organiza Tipo/Período/Destinos em colunas com rótulo discreto.
Não se alterou CSS, regra, textos ou documentos oficiais. Ainda falta resultado
terminal, capturas do teste de consulta/cancelada e revisão final no checkpoint anterior;
os três itens estão agora concluídos. As seis capturas de leitura e duas de lote
preenchido estão preservadas e incluídas na galeria, junto às 30 capturas finais
de páginas, seções e menus. Revisor independente conferiu o candidato atual,
as imagens e o log terminal: sem bloqueante novo. Homologação visual do usuário
e gate global permanecem pendentes. Nenhum CSS ou JavaScript foi acrescentado.

Avisos SQL de contexto/autosave/lote são anteriores à alteração, como demonstram
os logs de base e QA de10/10; budgets preservados, sem alegar ganho de desempenho.
