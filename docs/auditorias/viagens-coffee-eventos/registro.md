# Registro da missão — auditoria visual e de paridade (Coffee Break e Eventos Sociais)

Registro persistente para retomar o trabalho: o que foi inventariado, analisado, corrigido e
validado, o que falta e o próximo passo.

## Situação inicial (17/10/2026)

| Item | Valor |
|---|---|
| Sistema novo | `pcpr-gestao-next`, branch `ccr-fefbaf91-facwfi` (PR #21, rascunho), commit `183d642` sobre `main` `af5d204` |
| Alterações locais | nenhuma (árvore limpa) |
| Sistema antigo (referência funcional) | `tiago2904santos/Sistema-de-Gest-o-de-Eventos-Sociais`, branch `main`, commit `53dbf3f`, checkout só de leitura em `/home/user/tiago2904santos/sistema-de-gest-o-de-eventos-sociais` |
| Execução do legado | não executado (sem ambiente do legado): as conclusões de paridade vêm da leitura do código; o sistema novo é verificado executando |
| Ambiente de teste | PREVIEW local (`scripts/preview.sh local`, PostgreSQL `pcpr_preview`, `DEMO_MODE`, dados sintéticos de `semear_demo`); nenhum deploy, dado real, numeração oficial ou e-mail real |
| Referência visual | módulo de Viagens como está no commit acima (listas de ofícios e prestações, folha do ofício, resumo, painel, cadastros) |

## Andamento

- [x] Estado inicial registrado.
- [ ] Inventário de páginas (Coffee e Eventos) com a referência de Viagens de cada uma.
- [ ] Inventário funcional do legado e matriz de paridade (Eventos, Coffee).
- [ ] Capturas ANTES (`scripts/auditoria_coffee_eventos.py capturar antes`).
- [ ] Auditoria visual e correções por família (listas, detalhes, cadastro/edição, painéis).
- [ ] Lacunas funcionais e defeitos.
- [ ] Desempenho medido antes/depois.
- [ ] Capturas DEPOIS, regressão de Viagens, gates do repositório.
- [ ] Matrizes e relatório final.

## Próximo passo

Consolidar os inventários (páginas e legado) nas matrizes e começar pelos achados de maior impacto.
