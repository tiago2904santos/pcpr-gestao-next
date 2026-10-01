# Documentação de produto — PCPR Gestão de Eventos e Viagens

Esta pasta descreve **o que o produto faz** — usuários, módulos, fluxos, regras, documentos e
integrações — para orientar a nova implementação (greenfield) do sistema de Gestão de Eventos
Sociais / Central de Viagens da Polícia Civil do Paraná. É a primeira parada antes de codar
(ver `AGENTS.md`, "Antes de codar"): se uma regra não estiver aqui, ela é descoberta,
**documentada primeiro** e só depois implementada.

> **O sistema antigo é REFERÊNCIA, nunca código-base.** Dele aproveitamos *regras de negócio
> e comportamentos observados*, não código, templates, CSS ou JS. Quando a referência e o
> sistema novo divergem, a divergência é registrada aqui (como melhoria, regressão ou
> decisão pendente), nunca resolvida copiando a implementação antiga.

## Índice

| Documento | Conteúdo |
|---|---|
| [product-map.md](product-map.md) | O que é o produto, usuários e papéis, mapa de módulos (antigo × novo), glossário |
| [modules.md](modules.md) | Cada módulo: propósito, telas, entidades e situação no sistema novo |
| [workflows.md](workflows.md) | Fluxos passo a passo e máquinas de estado (ofício, eventos, coffee break, ASCOM, prestação…) |
| [permissions.md](permissions.md) | Papéis, matriz de permissões, escopo por unidade, auditoria |
| [entities.md](entities.md) | Entidades, campos-chave, relacionamentos e invariantes |
| [documents.md](documents.md) | Documentos gerados, regras de conteúdo (assunto, justificativa, diárias), formato e numeração |
| [integrations.md](integrations.md) | Integrações externas (eProtocolo, IBGE, e-mail, rotas, assinatura) e abordagem planejada |
| [legacy-lessons.md](legacy-lessons.md) | Problemas observados na referência, como o novo os trata e decisões pendentes |

## Convenções

- **Situação no sistema novo**: `Implementado no piloto` (existe em `gestao/`), `Parcial`,
  `Planejado` (fora do recorte atual) ou `A confirmar`.
- **"A confirmar"** marca qualquer ponto sem evidência suficiente nas fontes; não é regra.
- Exemplos usam **dados fictícios** (ex.: "Ana Beatriz Correia Lima", placa `ABC1D23`,
  protocolo `12.345.678-9`). Nunca registre aqui dados pessoais reais, credenciais ou
  endereços de acesso ao sistema de referência.

## Fontes

- Inventário do sistema de referência (módulos, rotas, entidades, fluxos, papéis, documentos,
  integrações) e matriz de paridade do Ofício de viagem, produzidos por leitura somente
  leitura da referência.
- Código novo: `gestao/` (em especial `gestao/viagens/dominio/`, `gestao/viagens/services.py`,
  `gestao/viagens/policies.py`, `gestao/identidade/papeis.py`) e `docs/adr/`.

## Escopo do piloto

O piloto do sistema novo cobre o **Ofício de viagem** de ponta a ponta (rascunho → equipe →
transporte → roteiro → diárias → justificativa → emissão em PDF/A → reabrir/cancelar), os
cadastros de apoio necessários (servidores, viaturas, municípios IBGE, tabela de diárias,
configuração institucional), identidade/papéis e a plataforma (auditoria, outbox, navegação,
Design System). Os demais módulos estão mapeados aqui como **Planejado**.
