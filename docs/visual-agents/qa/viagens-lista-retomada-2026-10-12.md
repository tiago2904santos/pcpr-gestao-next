# VI01 — Lista de Viagens, retomada de 12/10/2026

Base `e973289`, branch `codex/oficios-transporte-cartoes`. Contrato atual
em `docs/product/propagacao-identidade.md`; levantamento funcional em
`docs/migration/viagem.md`. DEMO consultado somente por GET/HEAD; testes
mutáveis com banco UUID e mídia isolados. Alteração do usuário em
`oficios/_equipe.html` preservada.

## Inspeção e contrato

Doze capturas atuais: todas, futuras, canceladas e vazio em 360/768/1440,
arquivos `viagens-lista-retomada-*`. Todas HTTP200, console sem erros e sem
overflow. Inspeção própria e independente confirmou hero compacto, filtros
horizontais, identificador data/ID (não número oficial), período, destinos,
status, unidade e relações Ofícios/OS/Planos coerentes com Ofícios.
Preservar essa composição evita mudanças artificiais. Nenhum menu,
exportação ou documento inexistente foi acrescentado.

As lacunas funcionais já documentadas da referência — filtros combináveis,
25 por página, busca por protocolo e ações de linha — não foram ocultadas
nem resolvidas ficticiamente por apresentação.

## Defeito demonstrado e correção

A consulta sem permissão de criar, quando paginada, usava a mesma barra
aderente do operador. Em mobile seu único conteúdo, a contagem, era ocultado
pela regra global de status. Novo teste com 21 registros sintéticos e perfil
consulta falhou nos dois casos esperados: contagem invisível em360; sticky
sem ação em1440 (`viagens-consulta-baseline.log`, 2 falhas em62,98s).
Capturas originais preservadas como `viagens-consulta-antes-*`.

Correção delimitada: `barra-acoes--acompanha` exige paginação **e** permissão
de criar. Sem ação, o texto usa `texto-secundario texto-sm` e mantém
`role=status`, fora do contrato de status de salvamento que some no mobile.
Operador conserva barra, botão POST/CSRF e comportamento anterior. Não há
CSS novo, seletor duplicado, alteração global ou mudança de regra/permissão.

## Testes e evidências

- Baseline de Lista e fluxo de criação: 6 aprovados,116,54s.
- Testes novos demonstraram os dois defeitos antes de alterar o produto.
- Suíte posterior52555 ativa, `viagens-consulta-final`; sete cenários da
  Lista, incluindo operador/consulta, busca, paginação, teclado e axe.
- Capturas/métricas em `evidencias/migracao-identidade-20261012/`.
- Revisão independente favorável à composição e correção; resultado final
  e captura consulta pós-correção ainda pendentes.

## Limpeza e desempenho

HTML de apresentação alterado sem backend, CSS, JS ou novos recursos. Não
se alega ganho de latência. Avisos da Folha (62–69 SQL; autosave27–29) já
existiam nos registros anteriores, não são consultas novas na Lista.
Não elevar budgets. Verificação da Folha continua na próxima unidade.

Não foi identificado CSS exclusivo comprovadamente obsoleto a remover.
Variantes canônicas de relação/sem ações atendem os registros atuais;
preload de seletor inexistente na Lista já foi retirado anteriormente.

## Resultado posterior

52555 terminou: **7 aprovados em144,30s**, Ruff verde. Cenários novos de
consulta comprovam contagem visível, barra estática e paginação/filtro
preservados; o operador mantém o último registro acessível por teclado.
Capturas `viagens-consulta-depois-360/1440.png` guardam as páginas completas;
`viagens-consulta-rodape-*` são recortes identificados dos originais para
inspeção legível. A navegação fixa aparece na posição da rolagem no print
integral, sem edição para deslocá-la. Rodapé, contagem e paginação revisados.

Gate global e homologação visual do usuário permanecem pendentes.
