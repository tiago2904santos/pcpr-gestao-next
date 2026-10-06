# Refinamento visual do módulo Viagens — progresso

Missão: deixar todo o módulo de Viagens no padrão visual aprovado (Roteiros e Termos de
Autorização), reaproveitando componentes do design system e as soluções do Sistema de Gestão
de Eventos Sociais (`../Solicitações de eventos`, só consulta). Só visual: nenhuma regra de
negócio, permissão, cálculo ou fluxo muda.

Retomar daqui: ler "Em andamento" e "Próximos passos".

## Referências aprovadas
- `roteiros/lista.html`, `roteiros/editar.html`
- `termos/lista.html`, `termos/editar.html`

## Inventário

### Listas e painéis
| Tela | Template | Situação |
|---|---|---|
| Painel de Viagens | `viagens/painel.html` | revisado — já no padrão |
| Viagens | `viagem/lista.html` | concluída |
| Ofícios | `oficios/lista.html` | revisada — já no padrão (busca, ordem, filtros, barra) |
| Justificativas | `justificativas/lista.html` | concluída |
| Numeração | `numeracao.html` | concluída |
| Prestação de contas | `prestacao/lista.html` | concluída |
| Termos de autorização | `termos/lista.html` | referência — alinhada a Roteiros |
| Ordens de serviço | `ordens/lista.html` | concluída |
| Planos de trabalho | `planos/lista.html` | revisado (rodada anterior) |
| Roteiros | `roteiros/lista.html` | referência |

### Folhas (cadastro/edição)
| Tela | Template | Situação |
|---|---|---|
| Viagem | `viagem/editar.html` (+ `_form_novo`, `_bloco`, `_conferencia`, `_leitura`) | a fazer |
| Gerar documentos em lote | `viagem/lote.html` | a fazer |
| Ofício | `oficios/editar.html` (+ `_equipe`, `_diarias`, `_resumo`…) | a fazer |
| Roteiro | `roteiros/editar.html` | referência |
| Termo | `termos/editar.html` | referência |
| Ordem de serviço | `ordens/editar.html` | a fazer |
| Plano de trabalho | `planos/editar.html` | revisado (rodada anterior) |
| Resultados do plano | `planos/resultados.html` | a fazer |
| Diário de bordo | `diario/folha.html` | a fazer |
| Relatório técnico | `relatorio/folha.html` | a fazer |
| Documentos da prestação | `anexos/folha.html` | a fazer |
| Anexar via assinada | `assinados/anexar.html` | a fazer |

### Janelas e partes compartilhadas
- Resumo do ofício (`oficios/_dialogo_resumo`), evento do plano, conjunto, horário, baixar,
  motivo (cancelar), cadastro rápido (servidor, viatura, cargo), via assinada.
- Rodapé de documento (`componentes/rodape_documento.html`), editor de documento
  (`oficios/_editor.html`), destinos/rota (`pc-destinos`), equipe (`pc-multiescolha`).

## Concluídas
- **Listas — padrão único (o de Roteiros):** "Novo" só na barra do rodapé (saiu do cabeçalho
  de Termos, OS e Viagens); busca ao vivo com HTMX (`#resultados` + `hx-select-oob` das abas)
  em Termos, OS, Viagens, Justificativas e Prestação; "Aplicar" só sem JavaScript.
- **Viagens:** a linha usa a placa (VIAGEM dd/mm) como as outras listas, no lugar do ícone.
- **Prestação de contas:** cartão do servidor numa linha (quem · 3 campos · ações), diária em
  destaque, pendências recolhidas ("N pendências para finalizar", com o "finalizar mesmo
  assim" dentro), "Exportar planilha" na barra do rodapé; 360/768/1440 sem rolagem lateral.
- **Numeração:** Ano, Piso e Salvar numa linha (`.campo--acao`, novo, compartilhado).

## Em andamento
- Folhas: Viagem → Ofício → OS → Resultados → Diário → Relatório → Anexos → Via assinada.

## Do Sistema de Gestão de Eventos Sociais (o que vale trazer)
- Linha inteira clicável, números tabulares, fichas de filtro ativo removíveis, cabeçalho de
  seção numerado, resumo de erros com âncoras, menu de linha com descrição por item,
  cartões de escolha com `:has()`. O foco sem contorno de lá NÃO vem (acessibilidade); só
  alertas ficam sem contorno de foco (pedido do usuário).

## Componentes compartilhados melhorados
- `.alerta:focus` sem contorno (qualquer alerta, não só `tabindex=-1`).
- `.campos > .campo--acao` (botão na linha dos campos, alinhado à base).
- (rodada anterior) `pc-escolhas` (várias escolhas num campo), `campo--escolhas`,
  `entrada-composta__meta`, botão Atualizar do editor, cadastro rápido com `data-sem-escolher`.

## Problemas encontrados (não visuais — registrar, não mudar)
- (nenhum ainda)

## Próximos passos
1. Comparar cada lista com Roteiros/Termos (1440 e 360 px).
2. Folhas, na ordem: Viagem, Ofício, OS, Resultados, Diário, Relatório, Anexos, Via assinada.
3. Revisão cruzada e auditoria global.
