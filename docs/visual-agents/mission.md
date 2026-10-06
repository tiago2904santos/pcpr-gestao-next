# Missão — Reconstrução excepcional do módulo de Viagens

> Documento-âncora do processo. Se a conversa for interrompida, recomece por aqui,
> depois `current-page.md`, depois `inventory.md`.

## Objetivo
Reconstruir o módulo **Viagens** do sistema novo (`pcpr-gestao-next`) tomando o sistema
antigo (`Sistema-de-Gest-o-de-Eventos-Sociais`, apps `viagens_*`) como **fonte de verdade
funcional**, para que o novo seja substancialmente superior em funcionalidade, organização,
UX, UI, eficiência, desempenho, acessibilidade e consistência — **sem nenhuma regressão**.
Paridade não basta: a meta é **superação**. "OK", "bom" e "melhor que o antigo" não bastam.

## Repositórios
| Papel | Repositório | Pasta local (Windows) |
|---|---|---|
| **NOVO** (alvo) | `tiago2904santos/pcpr-gestao-next` | `Documentos\pcpr-gestao-next` |
| **LEGADO** (referência funcional, somente leitura) | `tiago2904santos/Sistema-de-Gest-o-de-Eventos-Sociais` | `Documentos\Solicitações de eventos` |

Regras herdadas do `CLAUDE.md`/`AGENTS.md` do NOVO continuam valendo: o legado é
**referência, nunca código-base** (não copiar código/template/CSS/JS), valores visuais só
por tokens, sem inline style/script (CSP), domínio puro → serviço → tela, autorização em
`policies.py`, escrita por `services.py`.

Identidade visual aprovada: **Roteiros** e **Termos de Autorização** do NOVO.
Fonte de componentes/soluções: UI Lab do NOVO (`/ui-lab/`) e o próprio LEGADO.

## Equipe (coordenada pelo orquestrador)
| Agente | Papel | Entrega |
|---|---|---|
| 1 — Legacy/Parity Analyst | descobre TUDO o que a página faz no legado e no novo | `parity/<pagina>.md` |
| 2 — UI/UX Design Lead | projeta e implementa; faz autocrítica dupla antes do QA | código + `visual/<pagina>.md` |
| 3 — QA/Benchmark | testa legado × novo, mede, critica, aprova ou devolve | `qa/<pagina>.md` |

Fluxo: Analyst → especificação → Designer → implementação + 2 autocríticas → QA →
APROVADO? não → Designer; sim → próxima página.

## Loop por página
INVENTÁRIO → ANÁLISE DO LEGADO → COMPARAÇÃO → PLANEJAMENTO → IMPLEMENTAÇÃO → TESTES →
BENCHMARK → AUTOCRÍTICA → CORREÇÃO → NOVOS TESTES → APROVAÇÃO → PRÓXIMA PÁGINA.

## Ordem
1. **Ofícios**: lista → resumo/detalhes → cadastro → edição → páginas secundárias → modais →
   estados → ações → documentos → demais fluxos → auditoria Ofícios (legado × novo e
   Ofícios × Roteiros × Termos).
2. **Termos de autorização**.
3. Demais submódulos de Viagens (ver `inventory.md`).

## Prioridades
1 funcionalidade · 2 dados · 3 regras · 4 UX · 5 UI · 6 eficiência · 7 desempenho ·
8 acessibilidade · 9 responsividade · 10 consistência global.

## Definição de concluído
Paridade funcional com o legado · melhorias planejadas aplicadas · revisão visual ·
testes (funcional, visual 360–1440, a11y, desempenho) · benchmark com o legado ·
comparação com Roteiros e Termos · aprovação do QA · sem regressão conhecida ·
autocrítica · documentado em `completed-pages.md`.

## Ambiente de trabalho (sessão Cowork na nuvem)
- NOVO em PREVIEW: `APP_ENV=preview DEMO_MODE=true`, banco `pcpr_preview` semeado com
  `semear_demo` (~260 ofícios), servidor em `http://127.0.0.1:8000` (entrada DEMO sem senha).
  Rodar com `DJANGO_SETTINGS_MODULE=config.settings.preview PREVIEW_ESTATICOS_AO_VIVO=true`.
- LEGADO em `http://127.0.0.1:8001`, restaurado de um backup do próprio sistema (somente
  para observação; **nenhum dado real é copiado para docs, testes ou capturas versionadas**).
- Capturas comparativas: script local `cap.py novo|legado ROTA --larguras 1440,768,390`.
- Trabalho versionado no branch `viagens/reconstrucao`, levado ao repositório local do
  usuário por bundle (sem tocar no `main`).
