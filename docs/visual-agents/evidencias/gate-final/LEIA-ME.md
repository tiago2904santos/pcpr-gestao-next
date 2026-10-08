# Evidências do fechamento delimitado

Fonte da decisão e dos resultados completos:
[pacote final](../../qa/fechamento-gate-final-2026-10-07.md).
Esta pasta preserva também execuções reprovadas; sua presença não significa
aprovação. Integral final:2187verdes/zero falhas em40min21s; decisão do bloco
aprovado com ressalvas, sem CI global/performance/paridade editorial completos.

- H: [Folha 360](folha-360.png), [1440](folha-1440.png),
  [falha documental 360](falha-documentos-360.png),
  [1440](falha-documentos-1440.png). Antes/depois/composição das cinco larguras
  permanecem em [H antes 360](../lote-h/antes-folha-360.png) e
  [comparação documental 360](../lote-h/comparacao-falha-documentos-360.png),
  com a matriz completa na pasta lote-h.
- CSS rejeitado: [360](css-reprovado-resumo-360.png),
  [1440](css-reprovado-resumo-1440.png). Resumo corrente após restauração:
  [360](corrente-pronta-360.png), [1440](corrente-pronta-1440.png).
  Estados/documentos das capturas diferem; a comparação do estilo específico
  também tem assertion de computedStyle no E2E, não é igualdade pixel a pixel.
  [Resumo anterior 1440](../eprotocolo-editor/resumo-1440.png) preserva o baseline.
- Baixar: [360](baixar-360.png), [1440](baixar-1440.png).
  Cadastro servidor: [360](servidor-360.png), [1440](servidor-1440.png).
  Filtros/calendário assentados: [360](filtros-360.png), [1440](filtros-1440.png).
- Teclado/axe: seis JSON cadastro-adiado-axe-inicial/axe/ax, nas duas larguras.
  [Chromium AX 360](cadastro-adiado-ax-360.json),
  [axe modal 360](cadastro-adiado-axe-360.json),
  [CSP final de cópia](csp-resumo.json). Escopo e intermitência constam no pacote.
- Legado: [rota antes 360](../rota-legado/antes-ajuste/rota-360.png),
  [depois 360](../rota-legado/depois-ajuste/rota-360.png),
  [depois 1440](../rota-legado/depois-ajuste/rota-1440.png).
- Documentos reais sintéticos:
  [PDF já testado](../fechamento-bloco/oficio-sintetico-testado.pdf),
  [origem/páginas/hash](../fechamento-bloco/documento.txt). Não substituem
  validação externa PDF/A nem comparação editorial completa DOCX→PDF.
- Logs em logs/: focused, HTTP, navegador, baseline, correções, primeiro integral
  reprovado e tentativa de reuso interrompida. Nenhum resultado parcial é contado
  como suíte completa verde. [Integral final completo](logs/fechar-verificar-integral-final.log).
- Performance: [comparação](performance/comparacao.json), JSON de lista/Resumo/
  Folha em baseline/ e candidato/, recursos e hashes dos arquivos de coleta.
  Mesmo coletor/budgets; três falhas em cada lado. Números não foram alterados.
- [Manifesto das 43 fontes congeladas](manifesto-fontes.json), com SHA256 após
  CRLF→LF e CSS original como guard. A incorporação também conferirá árvores Git
  completas de gestao/static/templates/tests/scripts/config:
  [43 hashes e897fontes idênticas](fontes-integradas.json), sem usar resultado
  deste gate para validar fonte divergente.
