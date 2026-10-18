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

## Linha de base dos testes de navegador (antes da missão)

A rodada E2E do CI sobre `d7bf7e5` (último commit do PR #20, já em `main`) terminou com
**100 falhas e 644 aprovados** (job 117239906690). As falhas são anteriores a esta missão e
quase todas em telas de Viagens e Cadastros: `test_responsivo` (elementos sobrepostos em
360/390 px), `target-size` do axe (WCAG 2.5.8), `test_desempenho` (CSS acima do orçamento:
~325–354 KB para 228–252 KB), além de esperas e seletores do diário, relatório técnico e
prestação. Servem de comparação para a regressão de Viagens: o que esta missão introduzir
precisa ser separado dessa base.

O PR #21 (etapas 1 a 4 de Coffee e Eventos) foi mesclado em `main` (`ef66a4b`); a missão
segue na mesma branch, recriada sobre esse `main`.

## Andamento

- [x] Estado inicial registrado.
- [x] Inventário de páginas (Coffee e Eventos) com a referência de Viagens de cada uma — `matriz-visual.md`.
- [x] Inventário funcional do legado e matrizes de paridade — `matriz-paridade-eventos.md` (96), `matriz-paridade-coffee.md` (111).
- [x] Capturas ANTES (40 cenários × 360/768/1440).
- [x] Desempenho: folhas e catálogo com menos consultas (`a855caa`).
- [x] Defeitos funcionais: Eventos 9/9 (`4fde584`, `a552f07`), Coffee 6/6 (`74093e6`).
- [x] Visual por família: catálogo (`a552f07`), barras de rodapé (`1414d55`), listas e lotes
  (`b8fec11`), folhas, histórico, painel e cadastros (`aa0d81b`), ⋮ e textos prontos (`69c032a`).
- [x] Capturas DEPOIS, medidas e comparação (`compor`).
- [x] Gates: ruff, fronteiras, mypy, bandit, migrações, tipos JS — verdes.
- [x] Suíte rápida completa: 2786 aprovados, 5 falhas anteriores à missão (falham igual em
  `origin/main`: 2 de OCR sem conversor; prestação, texto da prestação e diário).
- [x] Navegador (Coffee, Eventos e acessibilidade deles): 26 aprovados; Coffee + Eventos +
  integração: 182 aprovados na rodada final.
- [x] Matrizes com situação final em todas as linhas; `relatorio.md`.

## Decisões tomadas durante a execução

- O preview roda com gunicorn sem recarga: depois de mudar modelos/código, reiniciar antes de
  capturar (uma captura de e-mail deu 500 com o processo antigo; refeita depois do reinício).
- Testes que mudaram de expectativa só onde o comportamento passou a ser o da referência
  (EV-F35, EV-F65, CB-F93) ou a interface mudou (catálogo de Eventos, e2e).
- O lembrete diário de Eventos (`eventos_lembrete`) fica sem trilha do banco, como o modelo
  documenta; o teste novo de cobertura da trilha o exclui com essa justificativa.
- Duas rodadas de pytest em paralelo colidem nos bancos `test_pcpr_gestao_gwN`: rodar uma
  de cada vez.

## Próximo passo

Decisões do usuário listadas no relatório (numeração compartilhada, importações, visões SQL) e
as pendências parciais/ausentes, em lotes, com a mesma matriz.
