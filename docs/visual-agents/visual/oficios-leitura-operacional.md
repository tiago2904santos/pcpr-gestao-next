# Ofícios — leitura operacional

Base observada: `0213d75`. Piloto: Lista. Segunda tela: Resumo. Ambiente PREVIEW
local, dados sintéticos, PostgreSQL LAB em 127.0.0.1:55432. Nenhuma regra muda.

## Observar e entender

A lista atual preserva todas as funções, mas repete cinco ícones por linha, corta
nomes cedo e mistura estado, destino e conferência financeira numa leitura lateral.
A identificação editorial e a barra persistente são os melhores padrões existentes.
O Resumo tem boa composição, mas seus metadados ainda não possuem um componente próprio.

## Projetar

Criar uma variante operacional do registro existente: identificação; viagem e
período/protocolo; equipe e transporte; conferência de diárias; menu. Desktop tem
cabeçalhos alinhados e menos ruído. Tablet conserva a leitura em faixas. Celular
prioriza número, destino, estado e período, com equipe/transporte e valor legíveis.
Não transformar a lista semântica em uma tabela ARIA incompleta.

Extrair metadado rotulado como componente de descrição e identidade compacta como
variante do componente existente. Aplicar a gramática ao Resumo e demonstrar no UI Lab.
Busca, filtros, ordenação, paginação, atalhos, menus, cancelados, motorista externo,
valores e abertura do Resumo mantêm dados e contratos existentes.

## Referências oficiais consultadas

- [Stripe: busca](https://docs.stripe.com/dashboard/search): busca contextual e
  refinamento visível. Preservar a busca abrangente e os filtros ativos do produto.
- [Vercel: overview](https://vercel.com/docs/deployments/overview): estado e dados
  relevantes junto ao registro; ações secundárias em menu.
- [Retool: painéis internos](https://retool.com/use-cases/admin-panels): filtros,
  paginação e ações condicionadas às permissões. Nenhuma ação nova nesta rodada.
- [Jira: lista](https://support.atlassian.com/jira-cloud-administration/docs/configure-the-default-issue-navigator/):
  colunas consistentes para comparação entre registros.
- [Notion: vistas](https://www.notion.com/help/views-filters-and-sorts): agrupamento
  e detalhe contextual. Preservar agrupamento por mês e janela de leitura.
- [GOV.UK: tabela](https://design-system.service.gov.uk/components/table/): rótulos
  claros e alinhamento numérico. Aplicar princípios sem copiar aparência.
- [DWP: serviço interno](https://design-system.dwp.gov.uk/patterns/internal-service-page/):
  identidade própria de serviço interno.
- [Home Office: componentes](https://design.homeoffice.gov.uk/components): componentes
  consistentes e acessibilidade como parte do acabamento.

## Evidências previstas

Capturas reais da base e do resultado em 360/390/768/1024/1440, console, axe,
teclado, fluxos existentes, orçamento real de recursos antes/depois e gate integral.
As evidências desta rodada ficam em `evidencias/oficios-leitura-operacional/`;
as evidências anteriores permanecem intactas.

## Comparar, criticar e corrigir

A primeira composição tinha linhas de aproximadamente 128 px; reduziu-se o respiro
vertical a 12 px e agrupou-se período/protocolo na mesma faixa. O registro usual
ficou com aproximadamente 96 px no desktop observado. O cabeçalho também perdeu espaço
sem função. O primeiro render revelou uma regra antiga que limitava a altura da
composição financeira a uma linha; a variante agora apresenta valor e composição
sem recorte vertical. Teste de navegador verifica esse contrato.

Os filetes dos metadados tinham respiro excessivo na primeira proposta. O padding
inferior passou a 8 px e a distância entre rótulo/valor, a 4 px, pelos tokens existentes.
O celular ganha leitura de protocolo/equipe e, por isso, mostra menos registros por
viewport que a base. É uma escolha de clareza, registrada na comparação de 360 px.

O gate detectou a retirada da classe `placa__numero`, usada pelos testes HTTP para
conferir o recorte. Ela foi restaurada dentro da variante compacta. Os testes não
foram adaptados para esconder a regressão; os 31 casos de filtros/ordenação passaram.

No celular, protocolo passa a estar visível e equipe/transporte ocupam a largura
inteira. Nomes completos continuam no título e no Resumo. Destinos longos continuam
acessíveis pelo nome do link e pela abertura do Resumo. Não se mudou a seleção de
destinos, a ordem do motorista ou o orçamento de selos.

O navegador integrado conservou CSS da URL anterior apesar de recarregamento.
A prévia limpa usa 8012, com o mesmo código e dataset LAB. As capturas automatizadas
usam contextos novos; nenhuma política de cache do produto foi alterada.
