# OS — propagação da identidade, 10/10/2026

Base `34f0d7d`, branch `codex/oficios-transporte-cartoes`. Contrato em
`product/propagacao-identidade.md`; descoberta independente somente leitura.

## Observação anterior

15 capturas integrais em 360/768/1440: lista, filtro, vazio, folha OS 005/2026 e nova.
DEMO existente; nenhum reset/seed/salvamento. Console zero/sem overflow.
Em 360, axe target-size na lista (link/menu OS 2) e no novo (Adicionar destino):
controles encobertos pela barra inferior. Demais cenários automatizados sem violações.
Fonte: `evidencias/migracao-identidade-20261010/antes-ordens-qa.json`.

## Composição escolhida

Reutilizar coleção/hero, registros de relações sem coluna financeira, preparação,
destinos/mapa, equipe compacta, editor operacional, histórico e ações no fluxo.
Funções da equipe permanecem junto à seleção, motivo e assinante agrupados sem
cards adicionais. Número anual e status documental distintos do indicador temporal.

Sem mudança de regras/documentos. Pendências são informativas, inclusive na geração.
Número manual e aviso de conflito de agenda continuam lacunas explicitamente registradas.

## Limpeza

Nenhum estilo exclusivo de OS comprovado. Bases antigas ainda usadas por Planos,
Viagens e outras listas permanecem. Não excluir `_acoes`, criação avulsa/vinculada
ou documento oficial: são consumidores funcionais reais.

## Estado

Concluída tecnicamente; avaliação visual do usuário pendente. Baseline E2E falhou antes de editar ao procurar botão Salvar
já oculto; teste agora usa Ctrl+S existente. Seletor Motivo também nomeava tanto
o grupo aria-labelledby quanto a textarea: corrigido para textbox, sem retirar
assertivas de salvamento. Logs anteriores preservados.

Regressão desta implementação, corrigida: faltava load viagens na lista, causando
Invalid filter resumir/HTTP 500 e três falhas focadas. Correção retestada: 81 verdes.
Seis E2E verdes: criação do Ofício/tipo/funções, autosave/pendências/PDF, três
larguras com filtros/menu/calendário/axe, download/cancelar/reativar/consulta e anexo
assinado real no editor. Avisos HarfBuzz e conexão assíncrona no teardown TEST
preexistem; banco e mídia únicos por suíte, investigação do harness registrada.

Segunda crítica: número/agenda/recursos e ações alinhados pelo grid canônico;
identificação separada da equipe/redação; funções permanecem próximas da equipe;
nenhuma coluna financeira vazia. Navegação em cinco larguras, menus Enter/Escape,
foco devolvido, busca HTMX/calendário e mapa/editor inspecionados. Sem CSS/JS novo.

SQL antes/depois: lista cinco registros 20, um 20, vazio 16; folha avulsa 39,
folha com funções 48, incluindo sessão/permissões; zero mutações. Orçamento da
folha excedido antes e depois: dívida anterior, sem ampliar budget. Lista remove
somente preload de seletor sem consumidor. Não declarar ganho de latência.
Não representa aprovação visual do usuário.

25 capturas finais em 360/390/768/1024/1440, cinco estados: HTTP 200, console zero,
overflow ausente e axe zero. Funções por servidor revisadas em imagens reais
360/768/1440; nomes e cargos preservados. Roteiro/mapa/editor em cinco larguras.

Performance: HTML lista 39.887 → 46.257 bytes, folha 94.420 → 97.025 bytes.
CSS e JS idênticos. Requisições iniciais da folha atual: 48, mapa visível, editor
ainda não carregado. A reprodução do template anterior em :8023 apresentou
destinos com altura zero, tornando a comparação controlada de HTTP inconclusiva.
Não usar seus 58 requests para afirmar redução; não afirmar ganho de latência.
A evidência original anterior e os ensaios permanecem disponíveis, sem alterar
o produto nem os budgets para corrigir uma medição. SQL é comparável e inalterado.

Falhas classificadas: load viagens ausente foi regressão desta rodada, corrigida;
seletores antigos Salvar/Motivo são falhas de teste anteriores/ambíguas, adaptadas
sem remover assertivas; orçamento SQL da folha e avisos do harness são dívidas
preexistentes. Nenhuma regressão funcional bloqueante conhecida após seis E2E.
Gate integral anterior 2295 em 9963f71; novo gate necessário no fechamento global.
