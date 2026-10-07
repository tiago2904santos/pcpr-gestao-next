# Arquétipos de página

Cada arquétipo é um template-base reutilizável em `templates/arquetipos/` e aparece no piloto.

| Arquétipo | Template | Estrutura | Exemplo no piloto |
|---|---|---|---|
| **LIST** | `arquetipos/lista.html` | cabeçalho (título e descrição, **sem botões**) → abas temporais (com contagem do recorte) → cartão: barra de filtros (Busca · Segmentado · Filtros (n) → gaveta/folha) → fichas dos filtros que valem → lista agrupada por mês → paginação → **barra fixa** (contagem do recorte · Exportar planilha · Mais · ação primária) | Ofícios (`viagens/oficios/lista.html`) |
| **FORM** | `arquetipos/formulario.html` | cabeçalho → resumo de erros → índice + seções numeradas → barra de ações fixa | Novo ofício |
| **DETAIL** | `arquetipos/detalhe.html` | cabeçalho (título + selos + ações) → layout-detalhe (seções \| coluna de contexto: status, próximos passos, histórico) | Detalhe do ofício |
| **DASHBOARD** | `arquetipos/painel.html` | cabeçalho → indicadores (4) → pendências (lista curta acionável) → atividade recente | Painel de Viagens |
| **WIZARD** | `arquetipos/assistente.html` | etapas horizontais → uma etapa por vez → voltar/avançar | Emissão do ofício (checagem final) |
| **DOCUMENT** | `arquetipos/documento.html` | cabeçalho (versão, ações: baixar, imprimir) → prévia do PDF → metadados da versão | Documento do ofício |
| **CALENDAR** | `arquetipos/calendario.html` | cabeçalho → navegação de mês → grade semanal acessível (tabela) | Agenda de viagens (próximo módulo) |
| **REPORT** | `arquetipos/relatorio.html` | filtros de período → resumo numérico → tabela com totais → exportar | Relatório de diárias (próximo módulo) |
| **SEARCH** | `arquetipos/busca.html` | campo grande → resultados agrupados por tipo | Busca global sem JS |
| **SETTINGS** | `arquetipos/configuracoes.html` | navegação de seções à esquerda → formulários curtos; numa seção só, em uma coluna: indicadores do que se configura → formulário curto (resumo de erros, rótulo na borda, mensagens que dizem como resolver) → o que a regra faz com o dado (ex.: lacunas) → histórico lido da trilha | Configurações institucionais |
| **EMPTY** | `componentes/vazio.html` | ícone, título, orientação, ação | Lista sem ofícios |
| **ERROR** | `erros/erro.html`, `erros/500.html` | código, título, explicação, caminho de volta | 403 / 404 / 500 |

## Regras comuns
- Exatamente um `h1` por página (no cabeçalho do arquétipo).
- Ação primária: no cabeçalho (topo direito) em DETAIL/FORM/SETTINGS; em **LIST** ela mora na
  barra fixa do rodapé da lista (com a contagem, Exportar e "Mais"), que acompanha a rolagem —
  numa lista de centenas de linhas ninguém volta ao topo para começar um registro. Botão
  flutuante solto sobre as linhas, nunca (cobria o ⋮ da última linha no legado).
- Menu de linha (⋮) com itens descritos e grupos fixos; o mesmo menu onde o registro aparecer.
- Toda lista tem estado vazio e "sem resultados" distintos.
- Todo formulário tem destino de cancelamento explícito.
