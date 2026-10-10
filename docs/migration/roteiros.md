# Módulo 3 — Roteiros (ficha)

Atualizado em 10/10/2026. Situação: **paridade documentada, incluindo Finalizados**.
Comparado por leitura com `viagens_roteiros/{urls,views,
models,abas}.py` e `docs/paridade/roteiros-{lista,editor}.md` da referência.

| Função da referência | Situação | Aqui | Prova |
|---|---|---|---|
| Lista com busca (sede, destino, observações) | ✅ | `/viagens/roteiros/` | `test_roteiros.py::TestTelasDeRoteiros` |
| Abas "Que vão acontecer", "Em andamento e realizados", "Cancelados" | ✅ ↔ | uma aba por vez (lá: combináveis por caixa de seleção) | idem |
| Aba "Finalizados" (prestação de contas encerrada) | ✅ | pelos ofícios do roteiro; exclusiva com as abas de quando | `gestao/viagens/tests/test_prestacao.py::test_contas_prestadas_nos_outros_modulos`, `test_abas_de_quando_excluem_as_contas_prestadas` |
| Selos de tempo ("faltam N dias", "em andamento"…), período, trechos, valor | ✅ | | captura `roteiros-lista` |
| Novo/editar numa tela só (sem detalhe; o endereço antigo de detalhe não existe aqui) | ✅ | | e2e `test_roteiros.py` |
| Gravação automática do rascunho | ✅ | `autosave` cria na primeira gravação | `TestServicosDoRoteiro` |
| Prévia das diárias e recálculo | ✅ | `previa_diarias` | idem |
| Estimativa de trecho (distância e tempo) | ✅ | `previa_trechos` | idem |
| Rota no mapa | ✅ | `viagens:rota` + cache `DistanciaMunicipios` | e2e `test_itinerario.py` |
| Bate-volta | ✅ | | idem |
| Cancelar, reativar, excluir (com confirmação) | ✅ | excluir só sem ofícios | `TestServicosDoRoteiro` |
| Reaproveitar sede e destinos no ofício ("dados" do roteiro) | ✅ | "Usar um roteiro cadastrado" na folha do ofício | `TestOficioUsaRoteiro`, e2e `test_oficio_usa_roteiro_cadastrado` |
| — | ↔ MELHORADO | "Criar ofício" a partir do roteiro; "usado em N ofícios" | `TestTelasDeRoteiros` |
| Status Rascunho/Finalizado do roteiro | ↔ | sem estado: o autosave grava e "Salvar roteiro" volta à lista (a referência usa o status só para a aba de finalização) | — |
| Tipo Avulso × De solicitação de evento | ⛔ | chega com Eventos Sociais (módulo 11) | — |

Pendências: tipo do roteiro (Eventos Sociais), comparação com a referência em execução
(dependência externa). A aba Finalizados já está implementada e coberta pelos testes acima.

## Propagação visual — 10/10/2026

Lista e folha migradas para a identidade vigente de Ofícios: hero grafite, filtros
horizontais, registros operacionais, mapa/trechos/chegada e Diárias compartilhados.
Rotas, ações, permissões, autosave e regra de cálculo preservados. Evidência e testes:
`docs/visual-agents/qa/roteiros-identidade-2026-10-10.md`.
O formulário atual edita somente itinerário (`Meta.fields=[]`): efetivo e observações
persistidos aparecem na consulta, mas não possuem controles na folha. Lacuna preexistente
registrada, sem adicionar comportamento nesta missão visual. Aprovação estética pelo
usuário permanece separada da validação técnica.
