# Termos — propagação da identidade, 10/10/2026

## Referência e contrato

Base: `9963f71`; referência Ofícios consolidada em `a675739`. Branch
`codex/oficios-transporte-cartoes`. Contrato em `product/propagacao-identidade.md`.
Lista, novo, edição, documentos e ações são o mesmo conjunto relacionado.
DEMO existente navegado; nenhum salvamento/reset/seed enviado nesse ambiente.
Suítes mutáveis usam banco TEST e mídia separados; execuções seguintes também
ganham nome de banco e diretório de mídia únicos.

## Migração e crítica

- Hero/identidade documental e filtros temporais horizontais canônicos.
- Registros de relações usam o mesmo grid, sem reservar coluna financeira vazia.
  Preservados destinos completos, período, vínculo, equipe, viatura, assinatura e menus.
- Barra dentro dos resultados HTMX: contagem/ações atualizam junto com a busca.
  Em lista curta/vazia fica no fluxo; paginação longa mantém acompanhamento.
- Folha de preparação: identificação, destinos/mapa, equipe/transporte e documentos.
  IDs de autosave, versão, permissões, formulários e endpoints preservados.
- Editor unificado recebe a variante operacional, mantendo múltiplas páginas,
  Texto/PDF, aplicar em todos, assinados, versões e downloads. Não alterado conteúdo
  oficial, margens ou paginação dos documentos.
- Histórico e estado real de salvamento integram a barra final no fluxo.
- Segunda crítica: campos Evento/Período precisavam de display grid explícito;
  marcadores de destino receberam ordem também no modelo clonado; viatura precisava
  do cartão canônico dentro de pc-transporte; equipe compacta recebeu variante
  explícita, com texto completo no DOM/title e remoção preservada.
- Terceira revisão das imagens: a grade de seis colunas do formulário tinha
  prioridade sobre a variante compacta. Corrigida na origem da variante; teste
  verifica largura mínima dos cartões (40% do grupo) e altura inferior a 80px.

## Classificação das falhas

- Preexistente, corrigida na interface: barra inferior encobria quatro controles
  de Destino 2 em 360px (`antes-termos-qa.json`, axe target-size/partiallyObscured).
  Renderização final registra zero violações nos 25 cenários, nas cinco larguras.
- Preexistente, teste atualizado: E2E esperava links Gerar (PDF), `.heranca` e
  `#folha-termo`, substituídos antes desta missão pelo editor por documento.
  Reprodução em `logs/termos-browser-baseline.log`: 1 falha, 1 verde. Teste mantém
  criação/herança, contagem exata de páginas, autosave, conteúdo da folha e PDF real.
- Erro do ajuste de teste, corrigido: Ofício usa viajantes, não `.servidores`.
  Contagem agora usa `termos.efetivo`; log anterior preservado.
- Dívida de desempenho anterior: cenário de Termo vinculado registrou 40 consultas
  contra limite 25 já antes da migração. Não aumentado budget nem alteradas queries.
- Validação da segunda iteração: 69 HTTP/domínio/documentos verdes; 2 E2E verdes.
  Aviso HarfBuzz preexistente. Houve aviso de encerramento do banco TEST por uma
  conexão assíncrona ainda ativa; não foi falha de assertiva. Próximas execuções
  esperam networkidle ao encerrar e usam banco único, sem compartilhar testes.
- Baixar: seletor antigo `.pagina-cabecalho__acoes` substituído pelo hero canônico
  no teste, preservando seleção, PDF único, download e memória da escolha. Log da
  falha anterior preservado; reteste de três fluxos passou.
- Aviso de conexão TEST ainda ocorreu no fechamento da suíte documental mesmo
  após networkidle: geração assíncrona/teardown permanece uma investigação do
  harness. Não houve falha funcional; isolamento impede reaproveitar esse banco.

## Compatibilidade e limpeza

`campo_destinos(..., operacional=True)` é uma variante optativa: Termos migra;
OS, Planos/eventos e Viagens continuam explicitamente na composição anterior até
sua rodada. Mapa anterior não pode ser removido enquanto esses consumidores existem.
`_campo_viatura(cartao=True, envolvido=False)` inclui o cartão dentro de seu próprio
pc-transporte; Ofícios, já envolvido e com cartão externo, não duplica a peça.
`_campo_equipe(compacta=True)` é optativo; outros contextos mantêm a composição vigente.
Títulos completos dos cartões estáticos e inseridos por JS permanecem acessíveis.

UI Lab e lista foram os consumidores comprovados de `registro__meta--termo`.
Migrados ambos; removidas quatro regras exclusivas e a participação no seletor
agrupado. As bases `registro__*`, ainda usadas por outras listas, permanecem.

## Evidências e desempenho

Galeria existente: `../evidencias/migracao-identidade-20261010/index.html`, 15 pares
Termos em 360/768/1440, mais capturas finais em 390/1024. Dados DEMO e estados
iguais; capturas integrais reais. Componentes/menu/UI Lab conferidos nas cinco
larguras. Todos os 25 cenários finais: HTTP 200, axe zero, console zero, sem overflow.

SQL antes/depois: lista 7 registros 22 consultas; 1 registro 20; vazio 16;
folha avulsa 36 e vinculada 39, incluindo sessão/autorização. Zero mutações nas
medições; sem N+1 introduzido. A folha excede budget preexistente, sem aumentá-lo.
HTML lista 65.417 → 67.985 bytes; folha 151.021 → 158.221. CSS gzip combinado
components/listas +117 bytes; multiescolha +18 bytes, apenas títulos completos.
Controladores de destino/editor e demais recursos medidos iguais.

Requisições no viewport inicial 1440×900: lista 23 → 22, folha 116 → 50. Na folha,
a composição mantém os iframes documentais lazy fora do viewport inicial; as
folhas continuam carregando ao navegar ao editor. Isso não mede o custo total
da jornada nem comprova ganho de latência. Sem nova dependência ou budget maior.

## Estado

Concluída tecnicamente; avaliação visual do usuário pendente. Checkpoint em fechamento. Já verdes: 69 HTTP
pós-limpeza, 8 E2E de compatibilidade, 3 documentais, 3 de geometria após correção; 2 adicionais de paginação (21 registros), consulta sem edição/folha e anexo assinado real pelo editor;
72 focados adicionais (4 assinados HTTP + 68 tokens); ruff, mypy (303 fontes gestao/config), TypeScript. Teclado: menus/Enter/Escape/foco devolvido,
calendário e busca HTMX; axe automatizado não representa conformidade completa.
As falhas dos dois testes adicionais eram seletores: Playwright não considera fieldset como controle desabilitado e o editor usa display: contents. Reteste verifica atributo disabled, campo realmente desabilitado, documento oculto para consulta e controles visíveis do editor. Log anterior preservado. Nenhuma aprovação estética automática. Resultado adicional e SHA no manifesto
`candidato-termos.json`/`commit-termos.json` quando finalizados.

O gate integral de Roteiros (2295 testes) continua associado a 9963f71. O fechamento global exigirá um novo gate sobre o candidato consolidado; estes resultados focados não são apresentados como um gate integral de Termos.
