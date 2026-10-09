# ADR 0030 — Reconstruir Lista e preparação com a identidade do Resumo

- **Status:** aceito para implementação; aprovação estética das duas páginas pendente
- **Data:** 2026-10-08

## Contexto

O usuário aprovou somente o Resumo/Detalhe. Reprovou Lista e Cadastro/Edição/Folha
e determinou reconstrução estrutural de ambas, nessa ordem. As avaliações anteriores
são históricas. O legado local em `Solicitações de eventos` foi lido sem alteração:
lista, abas, formulário e fluxos documentais. A cobertura existente está registrada
em `docs/visual-agents/parity/oficios-lista.md` e `oficios-folha.md`.

## Decisão

Aplicar os princípios do Resumo a dois arquétipos operacionais, preservando contratos
de formulário, HTMX, permissões e domínio.

- Lista: cabeçalho institucional grafite; navegação temporal como índice compacto;
  busca e documento em uma faixa clara; registros com número forte, destino e
  período prioritários, equipe/transporte agrupados e diárias em área própria.
  No celular, índice horizontal e registro com identidade/status, destino, agenda,
  equipe e valor hierarquizados. Filtros completos permanecem no painel existente.
- Cadastro: cabeçalho oficial compartilhado; índice de preparação compacto;
  identificação em campos com largura semântica; missão, equipe/transporte e roteiro
  como áreas de trabalho; conferência financeira com a variante aprovada no Resumo;
  documentos e pendências encerram a preparação. Autosave e ações permanecem visíveis.
- Extrair variantes reutilizáveis no Design System e demonstrá-las no UI Lab.
  Não modificar documentos oficiais, regras, integrações, modelos ou histórico.

## Alternativas consideradas

Manter a estrutura e polir bordas não atende à reprovação explícita. Copiar o modal
literalmente dificultaria busca e preenchimento. Criar interfaces isoladas por página
duplicaria o sistema visual; as variantes compartilham identidade, blocos e valores.

## Consequências

Obrigatórios: antes/depois reais nas cinco larguras; cobertura de funções existentes;
teclado, foco, axe, testes afetados e gate consolidado; custo de recursos medido.
Não propagar para outros módulos. A aprovação estética do Resumo é do usuário;
a aprovação de Lista e Cadastro ainda depende da nova entrega.

## Complemento de confiabilidade encontrado no gate

A composição anterior do Resumo retirou versões históricas da estação principal,
mas o pacote de download seleciona somente a emissão corrente. Preservar leitura
histórica é requisito protegido. Recuperar o acesso por uma janela secundária em
Mais ações, usando a projeção já autorizada e os links existentes de PDF/via assinada.
A estação principal permanece dedicada à emissão corrente. Não alterar pacote,
geração, snapshots, dados ou permissões; validar teclado e as guardas documentais.

Na cópia HTMX, o navegador registrou tentativas do vendor de restaurar atributos
`style` incompatíveis com a CSP existente. Limitar `attributesToSettle` a class,
width e height; não relaxar a política nem filtrar console. Cobrir a troca real,
cópia com fallback, foco e autosave nas duas páginas tocadas.
