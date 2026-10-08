# Ofícios · Resumo — lapidação final (08/10/2026)

Rodada de acabamento sobre a mesa operacional já aprovada. Sem redesenho: densidade,
hierarquia, alvos de toque e validação.

## O que mudou

| Área | Antes | Depois |
| --- | --- | --- |
| Cabeçalho | selos em linha própria, com filete acima e pastilha clara no fundo escuro | selos ao lado do título; só a situação tem contorno, o resto é texto com ícone |
| Motivo | faixa inteira, texto limitado à largura de leitura | coluna do roteiro, ocupando a linha toda |
| Conferência | painel na linha do roteiro, podendo cobrir a área de cópia ao rolar | painel cobre motivo + roteiro, preso à própria célula, com o mesmo respiro parado e grudado |
| Documentos | peça alta, estado da via em rodapé separado, histórico em cartões soltos | peça em uma linha (documento · estado · ações), detalhes e notas abaixo; histórico fora da janela |
| Equipe | lista em uma coluna, rótulo "Equipe · N servidores" dentro do conteúdo | cartões em duas colunas acima de 768 px, contagem no cabeçalho do bloco |
| eProtocolo | fechado por padrão, campos com cara de input | aberto por padrão, ficha de dados com filete por linha e detalhamento como bloco de texto |
| Registro institucional | trazia tipo e prazo por escrito | só data, protocolo, custeio e porte (tipo é selo; prazo pendente é alerta) |

## Validação

Banco de teste `pcpr-testdb-opa` (55434); navegador sobe no próprio pytest.

| Suíte | Resultado |
| --- | --- |
| `tests/test_design_tokens.py` | 68 passaram |
| `tests/e2e/test_resumo_visual.py` | passou (axe, teclado, 360→1440, UI Lab cheio e vazio) |
| `tests/e2e/test_resumo_versoes_documentais.py` | passou (polling real, via sem original, anexar/revogar, reaberto) |
| `tests/e2e/test_eprotocolo_copia.py` | passou (clipboard, fallback sem Clipboard, foco) |
| `tests/e2e/test_assinados.py` | passou |

Correções que a validação exigiu:

- `a.selo` recebeu `min-height: var(--alvo-minimo)`: o selo clicável ficava abaixo de 24px
  (axe `target-size`, WCAG 2.5.8) em 360 px.
- O corpo do dossiê do UI Lab ganhou `tabindex="0"` + `role="region"`: é exemplo só de
  leitura, então a área que rola não tinha como receber foco (axe `scrollable-region-focusable`).
- Dois testes partiam do bloco de eProtocolo fechado; agora ele nasce aberto e eles só
  clicam no `summary` se alguém o tiver fechado.

## Evidências

`artifacts/lapidacao/antes/` × `artifacts/lapidacao/depois/`, em 360, 768 e 1440 px:

- `viagens-oficios-resumo-261.png` — rascunho com pendências, sem documento;
- `viagens-oficios-resumo-258.png` — emitido, com via assinada e eProtocolo;
- `viagens-oficios-resumo-250.png` — emitido com v2 e emissão anterior (só no "depois").

## Pendências

- `tests/e2e/test_preview_demo.py::test_fluxo_demo_com_base_populosa` falha em 768/1024/
  1280/1440: o combobox "Ordenar por" não fica visível ao abrir "Mais filtros". **Falha
  preexistente** — reproduzida com `git stash`, antes desta rodada. É da tela de lista,
  não do resumo.
- Histórico de documentos saiu da janela a pedido do usuário. As versões e vias anteriores
  continuam gravadas, mas o único caminho visível hoje é "Mais ações → Baixar documentos…".
  Se a rastreabilidade precisar de um caminho próprio, falta criá-lo.
- Dívida preexistente de carga: a página serve 6 folhas CSS e ~15 módulos JS, e o
  `sprite.svg` é pedido várias vezes (todas com 304). Nada novo foi acrescentado aqui; o
  resumo não faz polling quando não há documento em geração (confirmado na rede).
