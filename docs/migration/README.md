# Migração contínua — como esta pasta funciona

Esta pasta é a **memória de trabalho** do loop de migração e evolução. Uma sessão nova
(pessoa ou agente) deve conseguir continuar daqui sem redescobrir nada.

## Ordem de leitura

1. [status.md](status.md) — onde paramos, o que está em andamento, o próximo passo.
2. [roadmap.md](roadmap.md) — ordem dos módulos e por quê (dependências).
3. [lessons.md](lessons.md) — decisões de padrão já tomadas. **Consulte antes de desenhar
   qualquer tela.**
4. [componentes.md](componentes.md) — o que já existe para reutilizar e o que precisa ser
   promovido ao Design System.
5. A ficha do módulo em andamento (`<modulo>.md`, ex.: [oficios.md](oficios.md)).

Referência permanente: [inventario.md](inventario.md) (mapa referência × novo),
[parity.md](parity.md) (paridade por módulo), [improvements.md](improvements.md) (backlog
transversal), `docs/integrations/` e `docs/ai/`.

## O loop

```
DESCOBRIR → INVENTARIAR → ENTENDER → ESPECIFICAR (ficha) → MODELAR → IMPLEMENTAR
→ REUTILIZAR → TESTAR → COMPARAR COM A REFERÊNCIA → CORRIGIR → MELHORAR
→ AUDITAR UX/UI → AUDITAR PERFORMANCE → REGISTRAR APRENDIZADOS → ATUALIZAR COMPONENTES
→ REGRESSÃO COMPLETA → MARCAR CONCLUÍDO → PRÓXIMO MÓDULO
```

É a extensão do ciclo do `AGENTS.md` (OBSERVAR → … → VALIDAR) para o sistema inteiro.

## Fontes da referência (somente leitura)

| Fonte | Como acessar | Para quê |
|---|---|---|
| Código da referência | `gh repo clone tiago2904santos/Sistema-de-Gest-o-de-Eventos-Sociais <scratchpad>/ref -- --depth 1` (fora do repositório) | Rotas, modelos, regras, mensagens, estados. **Ler, nunca copiar.** |
| Referência em execução | `scripts/referencia/capturar_referencia.py` com `REF_USER`/`REF_PASS` **no ambiente** | Capturas de tela e comportamento observável (só GET) |
| Documentação da referência | `docs/` do clone (ex.: `EPROTOCOLO_PROTOCOLO_AUTOMATICO.md`, `FASE_4_*`) | Intenção e decisões da época |
| "Gerenciador de Viagens" (pasta irmã) | leitura local | Sistema anterior que foi portado para a referência; útil para entender a origem de Viagens |

`docs/product/` continua sendo a especificação; esta pasta registra **o andamento** e o que
foi aprendido.

## Classificação de paridade

`IGUAL` · `MELHORADO` · `DIFERENÇA INTENCIONAL` · `LEGADO` · `PENDENTE` · `DESCONHECIDO`.
"Não descobri ainda" é `DESCONHECIDO`, nunca "não existe".
