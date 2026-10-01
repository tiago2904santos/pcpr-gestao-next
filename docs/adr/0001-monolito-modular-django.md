# ADR 0001 — Monólito modular em Django, contextos com fronteiras verificadas

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
A Missão 4 escolheu "monólito modular Python". O sistema de referência é um projeto Django
com ~30 apps acopladas (views importando modelos de outras apps, regras espalhadas em
views/forms/templates, 5 gerações de CSS). Equipe pequena, uso interno, volume baixo.

## Decisão
Django 6.1 (LTS seguinte ao 5.2; requer Python ≥ 3.12; usamos 3.13), um único deploy,
código organizado por **contexto delimitado**:

| Contexto | Responsabilidade | Pode depender de |
|---|---|---|
| `plataforma` | auditoria, outbox, navegação, UI, erros, saúde | Django |
| `identidade` | usuário, login, papéis | plataforma |
| `cadastros` | servidores, viaturas, unidades, cargos, municípios, tabela de diárias, configuração institucional | plataforma, identidade |
| `viagens` | ofícios (domínio, serviços, documentos, telas) | plataforma, identidade, cadastros |
| `painel` | composição: central de módulos, painel, busca | todos (só leitura) |

Dentro de cada contexto: `dominio/` (Python puro, sem Django), `models.py`, `services.py`
(comandos transacionais), `queries.py` (leitura), `policies.py` (autorização), `views.py`,
`forms.py`, `templates/`, `tests/`. **import-linter** quebra o CI se uma fronteira for violada.

## Alternativas
| Alternativa | Por que não |
|---|---|
| Microsserviços | Complexidade operacional sem ganho para o volume |
| FastAPI + SPA | Duplica validação/estado; contraria HTML no servidor (ADR 0002) |
| Continuar o código de referência | Proibido pela missão; e o acoplamento atual é o problema |

## Consequências
Regras de diárias e prazos testáveis sem banco; contexto novo (Eventos Sociais, Coffee
Break, ASCOM) entra como outro pacote em `gestao/` sem tocar Viagens.
