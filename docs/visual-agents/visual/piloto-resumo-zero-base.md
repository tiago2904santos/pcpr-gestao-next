# Piloto visual — Resumo do Ofício

08/10/2026. Branch `codex/viagens-piloto-resumo`, base `fdc662f`.

## Observar e entender

Inventário curto: Lista de Ofícios, Folha de um emitido, Roteiros e Termos,
somente leitura no PREVIEW sintético `pcpr_lab_demo`, porta PostgreSQL 55432.
Capturas em `../evidencias/piloto-resumo/inventario/`. O Resumo é o piloto:
concentra identificação, percurso, pessoas, valores e documentos; aparece também
na conferência de emissão. Não há redesenho simultâneo das outras páginas.

As duas capturas históricas de Roteiros/Termos foram arquivadas em
`var/visual-inventario-historico/`, fora dos commits exclusivos de Ofícios.

Problemas observados: número com pouco destaque, selos disputando espaço com o
destino, microtítulos indistintos, roteiro com rolagem interna e espaço ocioso,
diárias fragmentadas em três caixas, pessoas e documentos tratados como fichas
sem hierarquia. No celular a escala e as caixas apenas se empilham.

Melhores padrões preserváveis: fonte local Inter, paleta grafite/papel/dourado,
nomes claros das ações, modal nativo, menu canônico, rodapé disponível durante a
rolagem e conteúdo progressivo para cópia ao eProtocolo.

## Projetar

Direção: dossiê institucional, com número editorial, destino e situação em
camadas distintas; identificação enxuta, motivo legível, percurso contínuo,
conferência financeira lateral e pessoas em linhas. Dourado marca a estrutura,
grafite dá peso ao valor; evitar uma caixa para cada dado. Desktop tem duas
colunas proporcionais; tablet e celular recebem composição própria, sem
rolagem interna do roteiro. Uma única área vertical de leitura.

Variante do diálogo DETAIL existente, sem arquitetura nova ou regra nova.
CSS encapsulado em `dialogo--dossie`, usando tokens existentes do DS. Preservar
IDs, URLs, permissões, campos, mensagens, foco, polling e substituições HTMX.
Fonte funcional: `docs/product/oficios-documentos-versoes.md`,
`oficios-eprotocolo.md` e `oficios-lote-h.md`. D13 e tempo/adicional do legado
permanecem como já validados. Não alterar documentos oficiais.

## Implementar → testar → comparar → criticar → corrigir → validar

Capturar antes e depois em 360, 390, 768, 1024 e 1440; revisar topo e conteúdo
inferior, comparação lado a lado. Exercitar revisão, vazio, emitido, cancelado,
histórico e geração assíncrona; teclado/menu/fechar/foco, axe, console e overflow.
Testes funcionais existentes de Resumo, cópia e emissão; tokens e gate integral
antes de consolidar. Resultado e limitações serão registrados no QA do piloto.

## Ampliação autorizada: bloco exclusivo de Ofícios

O pedido posterior ampliou o piloto para Lista, Folha e seu painel Documentos.
O padrão projetado acima foi extraído em identidade documental e conferência
de valores compartilhadas. A Folha prova a reutilização do piloto; a Lista
recebe a mesma escala, superfícies e hierarquia. Componentes e variantes
constam em `../../design-system/components.md`. Nenhuma nova página de outro
módulo foi aberta depois dessa mudança de escopo.

Autocrítica e correção: a primeira iteração ainda mantinha rolagem interna
no roteiro por uma regra CSS mais específica; ela foi removida na variante.
A equipe ainda parecia uma coleção de cartões; virou faixa de pessoas.
Na Lista, regras móveis antigas anulavam a nova composição; a variante foi
posicionada depois delas. No editor móvel, a formatação consumia o espaço da
folha; passou a disclosure nativo, com comandos preservados. Ao revisar a
tabulação, o filtro passou a considerar `details` fechado sem eliminar o
tabstop de uma toolbar temporariamente inativa.

Comparações usam o mesmo dataset sintético e viewport. A falha local de
entrega dos assets documentais foi resolvida somente nos servidores de QA,
e a referência foi recapturada com fontes e brasão carregados. As primeiras
capturas desse ambiente ficaram preservadas e não são a comparação final.
