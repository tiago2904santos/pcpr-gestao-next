# AGENTS.md — como trabalhar neste repositório

Vale para qualquer agente (Claude Code, Codex, Copilot…) e para pessoas.

## Ciclo obrigatório
OBSERVAR → ENTENDER → PROJETAR → IMPLEMENTAR → TESTAR → COMPARAR → CRITICAR → CORRIGIR → VALIDAR.
Nenhuma fase é "concluída" sem evidência (teste, captura, medição) registrada em `docs/`.

## Antes de codar
1. Ache a regra em `docs/product/*.md`. Se não existir, descubra no sistema de referência
   (somente leitura) e **documente primeiro**.
2. Se a decisão for estrutural, escreva um ADR em `docs/adr/` (modelo em `docs/adr/0000-modelo.md`).

## Ao codar
- Domínio puro primeiro, com testes; depois serviço; depois tela.
- Tela nasce de um arquétipo (`templates/arquetipos/`) e de componentes do Design System.
- Mensagens ao usuário em português claro, dizendo como resolver.

## Antes de entregar
`scripts/verificar.sh` verde + testes de navegador das telas tocadas + capturas 360/1440
revisadas + paridade atualizada em `docs/parity/` quando a funcionalidade existir na referência.

## Ambientes
| Ambiente | Dados | Agente pode |
|---|---|---|
| LAB | sintéticos, descartáveis | tudo, inclusive auditorias destrutivas e carga |
| DEV | fictícios locais | tudo exceto apontar para bancos remotos |
| STAGING | anonimizados | ler; escrever só via fluxos da aplicação |
| PRODUCTION | reais | **somente leitura** |

## Ferramentas do agente
- `.claude/agents/` — revisores especializados (UX, acessibilidade, desempenho, segurança, cético).
- `.claude/skills/` — receitas (novo componente, nova tela, comparar com referência).
- `.mcp.json` — Playwright (navegador) e PostgreSQL somente leitura.
- `scripts/` — `capturar.py`, `verificar.sh`, `contraste.py`, `vendor_assets.py`, `referencia/`.
