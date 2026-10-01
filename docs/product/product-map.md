# Mapa do produto

## O que é

Sistema interno da PCPR que reúne, em um só lugar, a **gestão de eventos sociais e de
comunicação (ASCOM)** e a **Central de Viagens** (ofícios de viagem, diárias, termos, ordens
de serviço, planos de trabalho e prestação de contas). A referência nasceu da unificação de
dois sistemas: "Eventos" (base) e o "Gerenciador de Viagens / Central de Viagens" (portado em
fases).

Objetivos do produto (derivados do inventário):
- Registrar pedidos (eventos, palestras, coffee break, viagens) e conduzi-los por um fluxo com
  responsáveis, decisões e histórico.
- Gerar **documentos oficiais** corretos (ofício, justificativa, termos, OS, PT, RT…) com
  numeração anual e regras de prazo e diárias.
- Dar visão de agenda, conflitos, pendências e indicadores.
- Integrar-se ao **eProtocolo/PR** para protocolo e acompanhamento.

## Usuários e papéis

| Público | Exemplos de tarefa | Papel no sistema novo |
|---|---|---|
| Operador de viagens (unidade) | Monta ofício, equipe, roteiro, emite documentos | `OPERADOR_VIAGENS` |
| Gestor de viagens | Tudo do operador + cancelar, reabrir, numeração, tabelas e cadastros | `GESTOR_VIAGENS` |
| Consulta | Lê ofícios e cadastros de todas as unidades | `CONSULTA` |
| Administrador | Usuários, papéis, configuração institucional, trilha de auditoria | `ADMINISTRADOR` |
| Solicitante de eventos | Cria e envia pedido de evento social | Planejado (ref.: `SOLICITANTE`) |
| Diretoria-Geral (DG) | Despacha pedidos de evento | Planejado (ref.: `GESTOR_DG`) |
| Equipes ASCOM | Palestras, publicações, imprensa, coffee break | Planejado (ref.: acesso por módulo + admin do módulo) |
| Público externo por token | Pedido de palestra, fornecedor, motorista (diário de campo), feed ICS | Planejado |

Detalhes em [permissions.md](permissions.md).

## Mapa de módulos

| Módulo (referência) | Propósito | Situação no novo |
|---|---|---|
| Central de módulos / painel | Cartões por módulo com métricas, busca | **Implementado no piloto** (`painel`, busca de ofícios) |
| Conta / usuários | Login, senha, usuários, setores | **Parcial**: login, sair, alterar senha (`identidade`); gestão de usuários em tela: planejado |
| Viagens — Ofícios | Ofício de viagem, justificativa, numeração | **Implementado no piloto** (`viagens`) |
| Viagens — Roteiros / diárias | Trechos, cálculo de diárias, mapa | **Parcial**: trechos embutidos no ofício + cálculo; roteiro reutilizável e mapa: planejado |
| Viagens — Cadastros | Servidor, viatura, unidade, cargo, combustível, tabela de diárias | **Parcial**: modelos + telas de consulta (servidores, viaturas, diárias) |
| Viagens — Viagem (assistente) | Agrega solicitação → roteiro → ofício → termos | Planejado |
| Viagens — Termos de autorização | Termo por servidor/lote/viatura | Planejado |
| Viagens — Ordens de serviço (OS) | OS de viagem | Planejado |
| Viagens — Planos de trabalho (PT) | PT simples/multievento, resultados | Planejado |
| Viagens — Prestação de contas | Diário de bordo, RT, comprovantes, consolidado | Planejado |
| Eventos Sociais (solicitações) | Pedido de apoio a evento + despacho DG | Planejado |
| Coffee Break | Pedidos contra lotes/contratos e ciclo financeiro | Planejado |
| ASCOM — Palestras e Eventos | Demandas de palestra, pedido público | Planejado |
| ASCOM — Publicações | Pautas de publicação | Planejado |
| ASCOM — Atendimento à imprensa | Atendimentos a jornalistas | Planejado |
| Agenda / conflitos | Calendário unificado, escala, pauta, ICS | **Parcial**: só aviso de conflito entre ofícios |
| Relatórios / exportações | Consolidado, CSV/XLSX | Planejado |
| Documentos (núcleo) | Geração, versões, assinatura, editor | **Parcial**: PDF/A-2a versionado e imutável; assinatura e editor: planejado |
| Auditoria | Trilha imutável | **Implementado no piloto** (trigger no banco com cadeia de hash) |
| UI Lab | Vitrine do Design System | **Implementado** (novo, sem equivalente na referência) |

Detalhes por módulo em [modules.md](modules.md).

## Glossário

| Termo | Significado |
|---|---|
| **Ofício (de viagem)** | Documento que solicita autorização (ou convalidação) da viagem e a concessão de diárias; numerado por ano (`NNN/AAAA` no novo). |
| **Unidade emissora** | Unidade da PCPR que emite o ofício; no novo, é a lotação do usuário e define o escopo de visibilidade. |
| **Sede** | Cidade de onde a equipe parte e para onde volta; vem da configuração institucional da unidade. |
| **Viajante** | Servidor que integra a equipe do ofício. |
| **Motorista** | Servidor que conduz a viatura. No novo, é um viajante marcado (no máximo um por ofício); na referência podia ser externo à equipe. |
| **Servidor** | Cadastro da pessoa (nome, cargo, CPF, RG, unidade). Entidade-pessoa única: o motorista também é servidor. |
| **Viatura** | Veículo oficial (placa, modelo, combustível, caracterizada/descaracterizada). |
| **Trecho** | Deslocamento origem → destino com saída e chegada (horário local). |
| **Roteiro** | Sequência de trechos de ida e volta (na referência, entidade própria e reutilizável). |
| **Bate-volta** | Roteiro que passa pela sede no meio (sede → destino → sede → destino → sede). |
| **Diária** | Valor pago por período fora da sede, conforme faixa (Interior, Capital, Brasília) e tabela vigente. |
| **Faixa** | Classe do destino para diária: Brasília/DF, capital de UF ou interior. |
| **Tabela de diárias** | Valor de 24h por faixa, com data de vigência; 15% e 30% derivados. |
| **Justificativa** | Texto (e documento) exigido quando a antecedência é ≤ prazo configurado ou a viagem começou antes da data do ofício. |
| **Autorização / Convalidação** | Natureza do pedido: autorização se a data do ofício é anterior à 1ª saída; convalidação caso contrário. |
| **Retificado / Complementar** | Marcadores do documento: corrige ofício anterior / acrescenta a ofício já enviado. |
| **Custeio** | Quem paga: a unidade, outra instituição (informar qual) ou ônus limitado aos vencimentos. |
| **eProtocolo** | Sistema estadual de protocolo (PR). O protocolo tem 9 dígitos (ex. fictício `12.345.678-9`). |
| **Termo de autorização** | Documento por servidor (ou lote/viatura) autorizando a viagem; relevante para servidores de outras unidades. |
| **OS (Ordem de Serviço)** | Documento de viagem com tipo de necessidade e funções (motorista, técnico, apoio…). No Coffee Break, OS é a ordem ao fornecedor. |
| **PT (Plano de Trabalho)** | Plano com eventos, atividades, metas, efetivo e resultados. |
| **RT (Relatório Técnico)** | Relatório da viagem na prestação de contas. |
| **Diário de bordo** | Registro de trechos com km e abastecimento, preenchível no celular do motorista. |
| **Prestação de contas** | Comprovação da viagem por servidor (diário, RT, comprovantes, PDF consolidado). |
| **Despacho DG** | Decisão da Diretoria-Geral sobre pedido de evento (atender, não atender, devolver). |
| **Lacuna / piso** | Número liberado reaproveitável / número inicial do ano na numeração. |
| **Minuta** | Prévia em PDF com marca d'água, não arquivada. |
| **Outbox** | Fila transacional de efeitos colaterais (PDF, notificações, integrações). |
