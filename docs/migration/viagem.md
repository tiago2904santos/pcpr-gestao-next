# Módulo 8 — Viagem (o agrupador dos documentos)

Ficha levantada em 05/10/2026 da referência (`viagens_viagem/`, `solicitacoes/integracao_viagens.py`).
A referência é fonte de comportamento, não de código.

## O que é

A viagem é um **hub**: agrupa roteiro, ofícios (com justificativa e termos), OS e plano de
uma mesma ação. Não tem numeração própria (o título nasce dos tipos), nem autosave (a etapa
1 grava ao avançar). Cinco etapas sempre navegáveis: 1 Dados · 2 Roteiros · 3 Ofícios /
Justificativas · 4 PT / OS · 5 Termos. Quadro de prontidão, coerência entre documentos,
gerar documentos em lote, baixar documentos / baixar tudo (ZIP com LEIA-ME), repetir em
outra data, cancelar/reativar em cascata, excluir.

## Modelo (referência → aqui)

- `TipoViagem` (catálogo: nome único; "uma viagem pode ter mais de um, e o título nasce deles").
- `Viagem`: título, descrição, destino principal + extras (aqui: linhas `ViagemDestino`
  ordenadas, como `PlanoDestino`/`TermoDestino`), período e horários, unidade responsável,
  responsável, tipos (M2M), motivo, situação (rascunho, em preparação, documentos gerados,
  cancelada — "em execução" e "finalizado" nunca eram gravados: são calculados),
  cancelamento. **Aqui também `unidade`** (escopo, como todo documento).
- `EquipePrevista` e anexos de solicitação: dependem do módulo Solicitações → depois.
- Cada documento ganha `viagem` (FK opcional). Referência: CASCADE; **aqui PROTECT/SET_NULL e
  "excluir leva os só dela" no serviço** (integridade, auditoria).
- Roteiros e termos contam como "da viagem" também quando chegam por um ofício dela.

## Regras principais (mensagens exatas na referência)

- Lista: abas Que vão acontecer / Em andamento e realizados / Contas prestadas (depende da
  prestação) / Cancelados; busca por título, destino, servidor, placa, ofício N/AAAA,
  protocolo; 25 por página; selos de situação, de quando, de equipe e de coerência.
- Criar: reaproveita a viagem vazia esquecida (> 30 min sem nada).
- Etapa 1: tipos, motivo (modelo copia o texto), período, destinos em linhas, documentos
  vinculados (marcar/desmarcar, por aba); "A data final não pode ser anterior à data
  inicial."; título = tipos unidos por " / " ou "Nova viagem"; termo automático vazio.
- Prontidão (9 etapas: dados, roteiro, ofícios, equipe, ordem, plano, termos, assinaturas,
  protocolo) com link para onde se resolve.
- Coerência (OS, plano, termo, roteiro × viagem: período, destinos, equipe, viatura, saída,
  volta) e "Aplicar em todos" — pula documento com via assinada.
- Gerar em lote: um ofício por equipe (1–20), motorista entra na equipe, validações de
  servidor/viatura repetidos, termos menos a unidade emissora, OS e plano se não houver;
  tudo em rascunho.
- Repetir: desloca datas, troca cidade, números novos, sem protocolo/assinatura.
- Cancelar/reativar em cascata: "Viagem cancelada: {motivo}" nos documentos; reativar só
  os cancelados junto. **Decisão a tomar aqui**: o ofício novo exige `reativar_oficio` com
  justificativa — a cascata precisa de uma marca própria e da regra de permissão.

## Estado

- **8a feito**: `Viagem`, `ViagemDestino`, `TipoViagem` (catálogo em Cadastros), FK `viagem`
  (PROTECT) nos cinco documentos; lista (abas, busca por título/destino/servidor/placa/ofício);
  nova viagem (reaproveita a vazia esquecida); folha com tipos e motivo, período e destinos,
  vínculos (marcar/desmarcar) — gravação automática —, documentos da viagem por tipo com
  "Novo" já vinculado e semeado, histórico da trilha; DEMO com 3 viagens.
  Diferença intencional: as etapas 2–5 da referência são um cartão "Documentos da viagem"
  na mesma folha (padrão das folhas); a etapa 1 grava sozinha (a referência gravava ao avançar).

## Ordem de implementação (sub-módulos)

- **8a** modelo `Viagem` + `TipoViagem` + `ViagemDestino` + FK `viagem` nos documentos;
  migração de dados (planos/OS ligados a ofícios); lista; criar; etapa 1 (dados e vínculos);
  painel com as 5 etapas (2–5 listando os documentos da viagem e criando já vinculados).
- **8b** prontidão e coerência (+ aplicar).
- **8c** gerar documentos em lote; baixar documentos / baixar tudo (reaproveita `pacotes.py`).
- **8d** repetir; cancelar/reativar/excluir em cascata.
- Depois: anexos e integração com Solicitações (módulo próprio); aba "Contas prestadas" e
  entregas ao RT com a Prestação (módulo 9).
