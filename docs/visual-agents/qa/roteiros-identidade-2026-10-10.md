# Roteiros — propagação da identidade, 10/10/2026

## Candidato e referência

Referência consolidada: `a675739`, branch `codex/oficios-transporte-cartoes`.
Snapshot original/index: `var/migracao-visual-20261010-baseline/`.
Contrato: `docs/product/propagacao-identidade.md`, ADR 0034.
Lista, cadastro e edição são um conjunto relacionado; não há detalhe ou documento
oficial próprio do Roteiro. Nenhum banco/mídia foi resetado; DEMO somente navegado.

## Implementação e segunda revisão

- Lista: hero proporcional, abas horizontais, placa canônica, registros no mesmo
  grid, percurso/período separados de uso/observações e estimativa financeira.
- Rodapé dentro de `#resultados`: contagem e comportamento estático/sticky acompanham
  a busca HTMX e paginação. Vazio mantém a ação; sem conteúdo inventado.
- Folha: identidade grafite, metadados com contraste inverso, itinerário operacional,
  mapa/trechos/chegada calculada e Diárias horizontais compartilhadas.
- Estado de salvamento usa a variante sem emissão, mantendo os atributos reais do
  autosave. Campos/formulários/management forms e permissões preservados.
- Segunda revisão: corrigiu metadados no grafite, grid herdado do popover e alinhamento
  da seção de Diárias atualizada. Revisão independente encontrou corte financeiro
  interno no mobile, apesar de axe/overflow global verdes: removida contenção de
  largura desnecessária e reservadas duas colunas proporcionais no componente.
  Teste acrescenta valor alto/composição extensa e mede o conteúdo interno.

## Limpeza comprovada

- Lista antiga: consumidores Roteiros e exemplo do UI Lab migrados. Removidos seis
  blocos exclusivos de `.registro__meta--roteiro` e sua participação em duas regras
  agrupadas. Outros seletores da lista ainda têm consumidores e foram mantidos.
- Mapa alternativo de `_itinerario.html`: os consumidores Ofícios, Roteiros e UI Lab
  usam `painel_rota` operacional. Busca de render/include, DOM dinâmico, JS/data-* e
  estados foi cruzada com testes de itinerário e compatibilidade; mapa antigo removido.
- CSS base de itinerário e campos de destinos permanece: `_destinos.html` atende
  Termos, OS, Planos e Viagens. Não removido por simples ausência na captura atual.

## Evidências e testes

Galeria `evidencias/migracao-identidade-20261010/index.html`: 25 pares integrais,
mesmo DEMO/rotas/viewport, 360/390/768/1024/1440. Estados de busca/vazio, novo e seis
trechos. Capturas adicionais de menu, vínculo, UI Lab e referência de Ofícios.

- Focados HTTP/domínio + tokens: 89 verdes; testes de permissão, criação, ações,
  sequência inválida, cópia, prévia e budget de 18 consultas preservado.
- Navegador de Roteiros/itinerário: 7 verdes (antes da remoção); compatibilidade
  após remoção: 8 verdes. Após detectar corte interno, reexecução ampliada: 9 verdes
  em 676,40s, incluindo valor de R$ 999.999,99 e consumidores Ofícios.
  Os 7 fluxos de criação, mapa, reordenação, bate-volta e uso no Ofício foram
  repetidos após remoção/correção: 7 verdes em 304,50s, mídia/banco próprios.
- Tokens reexecutados após correção financeira: 68 verdes; ruff e diff-check verdes.
- 25 cenários renderizados antes e após primeira revisão: HTTP 200, axe 0, console 0,
  sem overflow global. As 25 capturas finais foram repetidas após correção financeira.
- Manual automatizado pelo navegador: Enter/Escape/devolução de foco no menu,
  foco/busca HTMX, popover de vínculos em 360/390/768/1024/1440; UI Lab axe 0 nesses tamanhos.
  Conferência interna sem corte em todas as cinco larguras. Revisão independente
  mede textos visíveis com Range em Ofício 157, Roteiro 58 e UI Lab: nenhum corte.
  Cores conferidas pelo computedStyle correspondem aos tokens grafite/cinza/dourado.
- Referência de Ofícios após alterações compartilhadas: 360/768/1440, axe/console 0,
  sem overflow, Motivo→Roteiro 22,375px e painel financeiro 238,281px.
- Gate integral em execução. Primeira tentativa falhou no harness de log por
  codificação CP1252, antes dos checks; corrigido UTF-8, log preservado. A execução
  atual registrou aviso de base nominal ausente no check de migrações; testes usam
  bases TEST isoladas. Check repetido sobre LAB existente: `No changes detected`,
  código 0, sem alteração de dados. Arquitetura: 16 contratos; mypy: 303 arquivos.
- Galeria conferida no navegador: 25 pares/50 imagens íntegros, filtro funcionando,
  console sem erros. Último registro fica acima da barra de ações em cinco larguras
  e alturas de 500/900px (não encoberto).
- Prévia LAB :8017 reiniciada com fontes atuais. POST apenas de cálculo de Diárias
  retornou 200 com variante operacional; nenhum formulário de salvamento foi enviado.

## Desempenho

Sem JS/dependência novos; app/itinerário JS idênticos ao snapshot. CSS gzip combinado
final: +90 bytes. Lista:
22→21 requisições, sem seletor antecipado; HTML 130.786→138.772 bytes. Folha:
39→43 requisições, exclusivamente tiles do mapa com zoom/composição diferentes,
sem editor antecipado; HTML 87.977→90.228. Sem inferência de ganho de latência.
Query/prefetch não alterados; teste de consultas passou sem aumentar budget.
Medição equivalente no DEMO: 18 consultas com 1 ou 20 registros, 16 com zero,
antes/depois; nenhuma mutação SQL durante a medição. `sql-roteiros.json`.
O CSS bruto de listas cresceu por normalização CRLF; gzip caiu 5 bytes. Não declarar
redução bruta com base na quantidade de regras removidas.

## Pendências

Concluído tecnicamente; aprovação visual é do usuário. Checkpoint Git contém
manifesto de fontes e logs desta rodada. Lacunas preexistentes: formulário atual não edita efetivo/observações;
docs históricas os descreviam como editáveis. Não adicionados durante migração.
Acabamento opcional: composição longa pode quebrar entre “1 ×” e “30%”, preservando
todos os dados. Aviso HarfBuzz do WeasyPrint é preexistente; geração testada funciona.

## Ambiente e retomada

Suítes executadas em bancos TEST diferentes no PostgreSQL LAB :55432, mídia TEST
do projeto separada da mídia DEMO. Não houve reset/seed. Runner das próximas suítes
também separa a mídia por execução/worker em `var/test-media-migracao/`.
Prévia :8017 e galeria :8021 são processos locais desta missão; comparação de
templates :8023 encerrada após medições para liberar memória. Snapshot/capturas
preservados; servidor legado :8000 preservado. Comandos temporários registrados
em `var/migracao_visual_testar.py` e `var/migracao_visual_capturar.py`.

## Gate final

`scripts/verificar.sh`: código 0, 2.295 testes em 2.857,91s; ruff, 16 contratos
de arquitetura, mypy (303 fontes), Bandit e tipos JS verdes. Migrações reconfirmadas:
nenhuma alteração detectada. Nove avisos preexistentes de HarfBuzz/pypdf, sem falha
de geração. Resultado associado a `candidato-roteiros.json` e `commit-roteiros.json`.
