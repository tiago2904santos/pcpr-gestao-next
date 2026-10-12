# PR01 — Lista de Prestação de Contas

Base do candidato: `d27329c`, branch `codex/oficios-transporte-cartoes`, alterações
locais delimitadas de Lista/consulta/componente de identidade/UI Lab. A aprovação
visual do usuário não é presumida. PR01 concluída tecnicamente; homologação visual pendente. Gate integral em andamento, registrado separadamente.

## Implementação e revisão

Cabeçalho e coleção canônicos; duas dimensões de filtros horizontais; identificação
documental compacta; equipe com campos proporcionais; rodapé no fluxo. No celular,
número de solicitação ocupa a linha e as duas datas compartilham a seguinte. Ações
continuam presentes. Componentes compartilhados: `registro_hero`, `identidade_documental`
(variante `placa`), abas, campos, calendário, menus, paginação, estado vazio e barra.

Após a primeira passagem, a barra fixa foi substituída pela variante de coleção:
não deve sobrepor a última linha. A segunda revisão independente do candidato
atual não encontrou bloqueante nas capturas de 360/768/1440, estados liberadas,
finalizadas e vazio. Observação do UI Lab: rótulos de datas podem truncar na largura
interna da vitrine; os nomes acessíveis permanecem completos. Não há corte equivalente
na Lista real. Isso deve ser tratado na revisão própria do UI Lab (UL01).

## Limpeza comprovada

Removidas seis regras `.atalhos-atencao*` de `static/css/listas.css`. Substituto:
`.abas .abas--conteudo`. Inspeção de templates, HTMX, JS, configuração e documentos,
mais revisão independente, não encontrou consumidores das classes removidas.
Os nomes homônimos usados como IDs, `aria-labelledby` e `hx-select-oob` permanecem.
As classes-base de equipe/servidor permanecem: possuem consumidores reais em Anexos
e UI Lab. A composição com placa usa variante, sem impor placa aos anexos por pessoa.

## Evidências e testes

- `evidencias/migracao-identidade-20261010/antes-prestacoes-lista-*` e `depois-*`:
  quatro estados × cinco larguras (360/390/768/1024/1440), mesmos dados DEMO.
- `depois-prestacoes-lista-qa.json`: 20 HTTP 200, axe sem violações, console limpo,
  sem transbordamento horizontal. Recapturado depois da remoção das seis regras.
- `logs/prestacoes-lista-prova*.log`: falhas anteriores e correções das três regressões.
- `logs/prestacoes-lista-http.log`: 96 testes verdes de HTTP/domínio/tokens.
- `logs/prestacoes-lista-browser.log`: nove E2E verdes; autosave, calendário,
  menus/foco, consulta, filtros combinados, exportação e envio após HTMX.
- Em `evidencias/migracao-identidade-20261012/`, `prestacao-poslimpeza-compat.json`
  e PNGs correspondentes: Enter/Escape e foco de calendário/menu; Anexos e UI Lab
  em 360/768/1440; axe zero em Anexos e console limpo, sem gravação de formulário.
- Tokens depois da remoção: `pytest tests/test_design_tokens.py --override-ini addopts= -q`:
  68 verdes. Não houve alteração de budgets nem exclusão de regras do axe.
- Regressão final pós-limpeza: `logs/prestacoes-poslimpeza.log`, dez verdes em
  276,24 s. Banco e mídia de teste isolados do gate e do DEMO. Fontes associadas
  por SHA-256 em `prestacao-candidato.json`; terminações de linha dos dois CSS
  normalizadas para LF, sem alteração semântica de regras após essa execução.

## Desempenho e limites

`evidencias/migracao-identidade-20261012/prestacao-comparacao-view.json`: mesma base
DEMO e usuário; view+render anterior e candidato; transação somente leitura;
três repetições; limites de 1/25 equipes; busca e filtros combinados/vazio.
Quantidade SQL idêntica antes/depois: 16–26 por cenário. Não é contagem de requisições
HTTP nem inclui middlewares. HTML: 513.074 → 524.987 bytes com 25 equipes sem filtro
(+2,3%); busca Estela com 12 equipes: 127.395 → 133.279 (+4,6%). Tempos concorrentes
com o gate não sustentam ganho de latência. JS/dependências não foram adicionados.
Avisos SQL existentes são registrados; a medição equivalente não demonstra novo N+1.
CSS do candidato, com LF igual à base: `components.css` +571 bytes e `listas.css`
+349 bytes, já descontada a remoção das seis regras; total +920 bytes.

Ainda não encerra o submódulo: Diário, Relatório e Documentos conservam composições
anteriores e têm entradas próprias na matriz. O gate global e sua revisão exata
devem ser registrados ao terminar; não inferir sucesso a partir do progresso parcial.

Paginação final: `prestacao-paginacao.json` e `prestacao-unica-*.png`; 25 equipes, próxima página e volta por teclado preservam filtro; busca156/2026 resulta em uma equipe, sem overflow em360/768/1440. Ruff dos arquivos Python alterados verde.
