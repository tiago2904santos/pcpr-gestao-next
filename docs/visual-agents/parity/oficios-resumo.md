# Paridade — Resumo / detalhes do ofício

> Agente 1 — Legacy/Parity Analyst · 07/10/2026 · complementa `oficios-lista.md` (L48: clique →
> resumo) e `oficios-inventario.md` (§1.1/§1.2). Escopo: **o que a pessoa consegue saber e
> fazer sobre um ofício sem editá-lo**. Os documentos em si (geração, conteúdo, assinados,
> editor) estão em `oficios-documentos.md`.
>
> **Privacidade:** o LEGADO roda com backup real. Nada de nome, CPF, placa ou protocolo real
> aqui; exemplos fictícios (`01/2026`, `12.345.678-9`, "Fulano"). As capturas ficam em
> `/home/claude/caps/res-doc/` (fora do repositório).

Caminhos abreviados:
- **LEG** = `/home/claude/legado` (somente leitura): `viagens_oficios/views.py` (`editar`
  559-716, `acao` 806-860), `viagens_oficios/form_context.py` (`contexto_conferencia` 147-204,
  `ajuda_do_protocolo` 207-237), `viagens_oficios/services.py` (`dados_eprotocolo` 409-448,
  `fechamento_do_oficio` 454, `reabrir_oficio` 466), `viagens_oficios/presenters.py`
  (`tipo_do_oficio` 99), `templates/pages/viagens_oficios/form.html`,
  `templates/pages/viagens_oficios/_documento_inline.html`, `templates/components/v32/copiaveis.html`.
- **NOVO** = `gestao/viagens/`: `views.py` (`_resumo_pedido` 75, `_contexto_resumo` 842,
  `_registros_do_oficio` 886, `_vias_do_oficio` 904, `resumo` 927, `editar` 464),
  `policies.py` (`acoes_do_oficio` 126, `menu_do_oficio` 233), templates
  `viagens/oficios/{_resumo,_dialogo_resumo,_resumo_carregando,_menu_oficio,_acoes_ciclo}.html`,
  `viagens/assinados/_registro.html`.

Legenda: ✅ paridade · ⚠️ parcial/diferente · ❌ falta no NOVO · ➕ só no NOVO · 🐞 defeito.

---

## 1. O que o LEGADO faz

### 1.1 Não há tela de leitura
O legado **não tem resumo, "visualizar" nem página de detalhes**. Tudo o que se sabe de um
ofício está na **página de cadastro/edição** (`/viagens/oficios/<pk>/editar/`, `form.html`), que:

- **exige operador** (`exigir_operador`, `views.py:575`): o leitor (módulo sem grupo) recebe
  **403** — não há como um leitor ver um ofício além da linha da lista;
- **grava no GET**: `get_or_create_justificativa_oficio` + snapshot da justificativa
  (`justificativas_services.py:143-168`) — abrir para "só olhar" altera o banco;
- é pesada: **199 consultas, 712 ms, 385 KB** (quente; a frio 469 consultas / 3,1 s; medido com o
  test client, ofício completo de 2 servidores); no navegador ~3,7 s até `networkidle`.

### 1.2 O que a página de edição mostra (sem editar)
| Bloco | Conteúdo | Evidência |
|---|---|---|
| Cabeçalho | "Cadastro de ofício **01/2026**", status (Rascunho/Gerado/Finalizado/Arquivado ou Cancelado), selo **Tipo** (Autorização/Convalidação · Retificado/Complementar) com a explicação por escrito embaixo; estado do autosave | `form.html:45-62`, `presenters.py:99` |
| Cancelado | aviso com motivo (ou "Sem motivo registrado.") e **data · hora** | `form.html:65-69` |
| Fechado (finalizado ou com PDF assinado) | aviso "somente leitura" + formulário **Reabrir para correção** (motivo obrigatório; revoga o assinado) | `form.html:71-84`, `services.py:454-504` |
| 1 Dados e viajantes | número, data, protocolo **com a origem** (aberto no eProtocolo em dd/mm, treinamento, simulado — `ajuda_do_protocolo`), custeio (+ instituição), motivo/modelo, equipe com chip "Motorista" e **"Com termo / Sem termo"** por servidor, viatura (cadastrada ou manual: placa, modelo, combustível, tipo), motorista (da equipe ou de fora, com **ofício nº/ano e protocolo de origem**), porte de arma; **avisos de conflito de agenda** | `form.html:110-248`, `form_context.py:207-237` |
| 2–5 Roteiro e diárias | o editor de roteiro embutido (trechos, mapa, diárias por servidor) | `form.html:252` |
| 6 Justificativa | modelo + texto | `form.html:255-273` |
| 7 Documentos | cartões "Documento original (Ofício)", "Justificativa", "Termos de Autorização" (um por servidor + "Baixar PDFs"), **"Dados para o eProtocolo"** | `form.html:276-325` |

Cada cartão de documento (`_documento_inline.html:22-50`): título + selos **"Assinado"** /
**"Assinado, mas os dados mudaram"** (tooltip com a lista do que mudou) / **"Versão N emitida em
dd/mm/aaaa"**; menu (ícone de documento) com **Visualizar documento** (PDF em nova aba),
**Baixar PDF** (a via emitida), **Emitir nova versão** (versão N+1 com os dados de hoje) e
**Anexar/Trocar assinado** (modal). Abrir o cartão mostra o **editor/folha embutido** (o mesmo
documento, editável) — ou "Complete o ofício para gerar e consultar os documentos." quando há
pendência (`form_context.py:153-155`).

**Dados para o eProtocolo** (`services.py:409-448`, `copiaveis.html`): Interessados (servidores
por ordem alfabética), Assunto (linha de autorização/convalidação), Nº/Ano do ofício, Protocolo —
cada um com botão **Copiar** — e a caixa **Detalhamento** ("OFÍCIO Nº 01/2026 - SOLICITAÇÃO DE
… - DESTINO: … - PERÍODO: … - SERVIDORES: …" + motivo na linha seguinte) com **Copiar**.
Medido: 4 rótulos + 1 caixa, 5 botões de copiar (`rd_legado.py`).

### 1.3 O que se faz sem editar (LEG)
Pela própria página: visualizar/baixar PDF, emitir nova versão, anexar/trocar/remover assinado,
baixar termos (PDF único), copiar os dados do eProtocolo, reabrir para correção. Pelo ⋮ da lista:
reativar, baixar documentos, anexar assinado, importar processo, retificar/complementar (liga/
desliga), cancelar, excluir (ver `oficios-lista.md` §1.6). **Histórico**: a função
`historico_do_oficio` existe (`views.py:373`) mas **não é desenhada** na página.

### 1.4 Defeitos do LEGADO nesta área
- 🐞 **LG-R1** Leitor não lê o ofício (403) e o GET de leitura grava (`views.py:575`; snapshot).
- 🐞 **LG-R2** Ofício **Finalizado** que passa a ter pendência (ex.: transporte incompleto depois de
  uma mudança de cadastro) **perde o acesso aos documentos**: `disponivel = not pendencias`
  (`form_context.py:153-162`) esconde Visualizar/Baixar mesmo da via já emitida. Reproduzido no
  backup local: um ofício Finalizado com "Complete o transporte…" (1 pendência).
- 🐞 **LG-R3** "Visualizar documento" **emite**: a primeira visualização registra a via v1 e muda o
  status para "Gerado" (`document_generation.py:50-53`, `emissao.py:177-213`) — ler muda estado.

---

## 2. O que o NOVO faz

**Janela de resumo** (`<dialog id="dialogo-resumo">`): aberta pelo clique no título da linha
(HTMX `viagens:resumo`, esqueleto `_resumo_carregando.html` enquanto chega), pelo ⋮ "Ver resumo",
ou já desenhada pelo servidor com `?resumo=<pk>` (`views.py:75`, `_dialogo_resumo.html:11`; sem
JS ela aparece aberta). A mesma janela, com `revisao=True`, é o "Revisar e emitir" da folha
(`views.py:642`).

Conteúdo (`_resumo.html`), na ordem:
1. **Cabeçalho**: placa "OFÍCIO 155/2026", título = destinos (ou "Sem destino"), selos situação
   (Rascunho/Emitido/Cancelado), **Arquivado**, **Tipo** (Convalidação; Autorização só aparece com
   marca) e tempo ("faltam 11 dias", "em andamento · até 15/10").
2. **Alertas**: pendências bloqueantes (rascunho); **Cancelado em dd/mm/aaaa** + motivo; na revisão,
   avisos não bloqueantes (conflitos).
3. **Definições**: Data, Protocolo, Custeio (+ instituição), Porte de arma, **Tipo** (completo +
   porquê por escrito), **Prazo** (antecedência × prazo, justificativa escrita/pendente), Motivo; na
   revisão também Destinatário, Assina, Valor por extenso, Justificativa (incluída/dispensada).
4. **Roteiro** (dia, semana, origem → destino, horários) e **Diárias** (valor total + por servidor,
   tipo de destino, quantidade).
5. **Equipe e transporte**: cartões (nome, cargo ou "Motorista"), cartão do transporte (modelo,
   placa · tipo; "Motorista: … (de outro ofício)"; ou transporte informado; ou "Sem transporte").
6. **Documentos**: cada versão ("Ofício v1", "Justificativa v1" — link para o PDF) ou
   "(gerando)/(falhou)"; abaixo, **vias assinadas** por documento emitido (registro com selo
   "Assinado"/"Sem via assinada", quem anexou, quando, arquivo, o que a conferência leu; menu Ações:
   abrir, baixar original, trocar, remover).
7. **Rodapé**: "Ver o PDF" (emitido) ou "Ver minuta"; **Mais ações** (o ⋮ canônico D7 +
   "Ver minuta" e "Baixar em Word"); "Abrir o ofício" (rascunho editável) ou "Editar ofício"
   (emitido → retificação com confirmação).

Itens de "Mais ações" medidos (`rd_novo_resumo.py`, gestor):
| Situação | Itens |
|---|---|
| Rascunho | Baixar em Word · Baixar documentos… · Anexar assinado… (inativo: "Emita o ofício primeiro") · Criar a partir deste ofício ▸ (Novo termo, Duplicar) · Retificado ou complementar ▸ (Marcar como complementar) · Cancelar ofício… · Arquivar · Excluir rascunho |
| Emitido + justificativa | Ver minuta · Baixar em Word · Baixar documentos… · Anexar ofício assinado… · Anexar justificativa assinada… · Criar a partir ▸ · Cancelar ofício… · Arquivar |
| Emitido com via assinada, OS e plano | … Trocar via assinada… · Criar ▸ (termo, OS, plano, duplicar) · Termos/Ordens/Planos deste ofício · Cancelar · Arquivar |
| Cancelado | Baixar em Word · Duplicar · Arquivar · Reativar ofício… |
| Arquivado | Ver minuta · Baixar em Word · Baixar documentos… · Anexar assinado… (inativo) · Criar ▸ · Desarquivar |
| Leitor (qualquer) | Ver minuta (se emitido) · Baixar em Word · (Termos/Ordens/Planos deste ofício) |

Permissões: `pode_ver` com escopo por unidade (operador.l3 não abre ofícios de outra unidade:
a janela não abre — 404); leitor lê tudo da própria visibilidade (CONSULTA vê todos no preview).

Desempenho (test client, gestor, PREVIEW): **16–22 consultas, ~110 ms (397 ms a frio), 18–21 KB**
por fragmento. Janela 749 px em 1440; folha de baixo em 390.

---

## 3. Matriz LEGADO × NOVO

| # | Item | LEGADO (evidência) | NOVO (evidência) | Status |
|---|---|---|---|---|
| R1 | Tela de leitura sem editar | inexistente; só `editar` (`views.py:561`) | janela de resumo (`views.py:927`, `_resumo.html`) | ➕ |
| R2 | Leitor lê o ofício | 403 (`views.py:575`) | sim, com menu reduzido | ➕ |
| R3 | Ler não grava | GET grava snapshot (🐞 LG-R1); visualizar emite v1 (🐞 LG-R3) | GET puro | ➕ |
| R4 | Endereço compartilhável | `/editar/` (só operador) | `?resumo=<pk>` abre a janela pronta (`views.py:75`) | ✅ ➕ |
| R5 | Número + situação | título + status (`form.html:51-52`) | placa + selo + "Arquivado" (`_resumo.html:9-20`) | ✅ |
| R6 | Tipo + marca + porquê | selo + explicação (`form.html:54-55`) | selo + "Tipo" por extenso (`_resumo.html:51-52`) | ✅ |
| R7 | Prazo / justificativa obrigatória | dentro da explicação do tipo | linha "Prazo" + "Pendente: ainda não foi escrita" (`_resumo.html:58`) | ✅ ➕ |
| R8 | Selo de tempo (faltam N dias / em andamento) | só na lista | no cabeçalho (`alerta_oficio`) | ➕ |
| R9 | Pendências para emitir | mensagens só depois de "Finalizar"; cartões dizem "Complete o ofício…" | alerta com a lista (`_resumo.html:24-29`) | ✅ ➕ |
| R10 | Cancelado: motivo e quando | motivo + data · hora (`form.html:67`) | motivo + data, **sem hora** (`_resumo.html:31-34`) | ✅ (hora ⚠️ baixa) |
| R11 | Data, protocolo, custeio, porte, motivo | campos (`form.html:120-147`) | definições (`_resumo.html:46-60`) | ✅ |
| R12 | **Origem do protocolo** (eProtocolo em dd/mm, treinamento, simulado) | ajuda do campo (`form_context.py:207-237`) | campo `protocolo_origem` existe (`models.py:155`) mas **não aparece** | ❌ |
| R13 | Roteiro | editor embutido (`form.html:252`) | lista de trechos (`_resumo.html:80-96`) | ✅ |
| R14 | Diárias | diárias da tela | 3 indicadores (`_resumo.html:99-114`) | ✅ |
| R15 | Equipe e motorista da equipe | lista + chip Motorista (`form.html:180-190`) | cartões (`_resumo.html:127-136`) | ✅ |
| R16 | Servidores **com termo** | "Com termo/Sem termo" por servidor (`form.html:184`) | termo é registro próprio; só link "Termos deste ofício" quando existem | ⚠️ (decisão de modelo) |
| R17 | Motorista de fora: **ofício nº/ano e protocolo de origem** | campos do cartão (`form.html:218-240`) | só "Motorista: Fulano (de outro ofício)" (`_resumo.html:144`); campos existem (`models.py:235`) | ⚠️ |
| R18 | Viatura: combustível e tipo | sim | placa · tipo; **combustível omitido** | ⚠️ baixa |
| R19 | Conflitos de agenda | avisos na página (`form.html:246`) | só na revisão (`_resumo.html:36-41`); resumo comum não mostra | ⚠️ |
| R20 | Destinatário / quem assina / valor por extenso | não aparecem (só no PDF) | só na revisão (`_resumo.html:61-67`) | ➕ (🐞 extenso, ver D-docs F6) |
| R21 | Documentos: versão + **data/autor da emissão** | "Versão N emitida em dd/mm" (`_documento_inline.html:22`) | "Ofício v1" sem data nem autor (`_resumo.html:157-170`) | ⚠️ |
| R22 | Ver o PDF | "Visualizar documento" (nova aba) + folha no cartão | "Ver o PDF" (nova aba) no rodapé; sem pré-visualização na janela | ✅ (⚠️ sem miniatura) |
| R23 | Baixar PDF / Word / pacote | "Baixar PDF" no cartão; pacote no ⋮ da lista | Mais ações: Baixar em Word, Baixar documentos… | ✅ |
| R24 | **Emitir nova versão** sem mudar o ofício | menu do cartão (`_documento_inline.html:30-33`) | inexistente: emitido é imutável; corrige-se por retificação | ⚠️ (decisão; ver D-docs D14) |
| R25 | Selo Assinado / "Assinado, mas os dados mudaram" | `_documento_inline.html:22` | selo + notas da conferência (`assinados/_registro.html`); "mudou" nunca vale p/ ofício (congelado) | ✅ |
| R26 | Anexar / trocar / remover assinado | cartão + modal | Mais ações + Ações da via | ✅ |
| R27 | Termos do ofício (por servidor, PDF único) | details "Termos de Autorização" + Baixar PDFs (`form.html:286-303`) | link "Termos deste ofício" + pacote "Baixar documentos" inclui termos ativos | ⚠️ |
| R28 | **Dados para o eProtocolo** com Copiar | `form.html:305-311`, `services.py:409-448` | **inexistente** (nenhum template cita eProtocolo) | ❌ |
| R29 | Histórico | não desenhado (`views.py:373` sem uso) | só na folha do **rascunho**; emitido/cancelado/arquivado: **nenhum lugar** mostra o histórico | ⚠️ (ambos) |
| R30 | Reabrir para correção (motivo, gestor) | formulário no aviso "somente leitura" (`form.html:76-82`) | view `reabrir` + serviço existem, **nenhuma tela chama** (`acoes_do_oficio` não tem "reabrir", `policies.py:126-138`) | ❌ 🐞 |
| R31 | Editar emitido | reabrir | "Editar ofício" = retificar com confirmação (`_resumo.html:232-244`) | ✅ ➕ |
| R32 | Criar termo/OS/plano/duplicar a partir | — | Mais ações ▸ Criar | ➕ |
| R33 | Ciclo (cancelar, reativar, arquivar, excluir, marcas) | ⋮ da lista | Mais ações (mesmo ⋮ D7) | ✅ ➕ |
| R34 | Ordem dos documentos | ofício, justificativa, termos | **Justificativa antes do Ofício** na lista (order_by `tipo`, `views.py:850`); vias com o ofício primeiro (`views.py:918`) | 🐞 |
| R35 | Documento listado uma vez | cartão único por documento | aparece duas vezes (lista "Documentos" + registro da via) | ⚠️ redundante |
| R36 | Estado "gerando" | síncrono (não existe) | "(gerando)" estático, sem atualização; rodapé mostra "Ver minuta" para um emitido sem PDF pronto | ⚠️ 🐞 |
| R37 | Rascunho retificado com PDF antigo | — | rodapé "Ver o PDF" aponta a **v1 superada** e "Baixar em Word" diz "A via emitida (v1)" mas devolve a minuta (`views.py:851-852` não olha a situação; `_resumo.html:205-221`; `views.py:1003-1005`) | 🐞 (por leitura de código; captura falhou — banco do PREVIEW sem conexões livres) |
| R38 | Leitor e downloads | nada | PDF e Word individuais liberados (`pode_ver`), pacote negado (`edita_oficios`, `views_pacotes.py:55-60`) — mesmo conteúdo, regras diferentes | ⚠️ |
| R39 | Documentos visíveis sem rolar (1440×900) | cartões no fim de uma página longa | seção Documentos/vias abaixo da dobra; pede rolagem dentro da janela | ⚠️ |
| R40 | Sem JavaScript | página normal | janela aberta pelo servidor (`_dialogo_resumo.html:11`) | ✅ |
| R41 | Escopo por unidade | não há | `pode_ver` (404 para outra unidade) | ➕ |
| R42 | Desempenho | 199 consultas / 712 ms / 385 KB | 16–22 consultas / ~110 ms / 18–21 KB | ➕ |

**Lacunas ❌:** R12 origem do protocolo · R28 Dados para o eProtocolo · R30 Reabrir (sem UI).
**Defeitos 🐞 do NOVO:** R30, R34, R36, R37.

---

## 4. Defeitos e fragilidades (NOVO)

| ID | Defeito | Evidência / reprodução |
|---|---|---|
| RF1 | **Reabrir (gestor, com motivo) inalcançável**: rota, view e serviço existem; nenhum template a usa; o inventário anterior a dava como ✅ | `grep viagens:reabrir` só acha testes; `policies.py:126-138` |
| RF2 | Rascunho retificado com PDF antigo: "Ver o PDF" abre a v1 superada como se valesse; descrição do Word promete a via emitida e entrega a minuta | `views.py:851` escolhe o 1º PDF pronto sem olhar `situacao`; `_resumo.html:205-221`; `baixar_docx` (`views.py:1003`) |
| RF3 | Ordem inconsistente: "Justificativa v1, Ofício v1" na lista e "Ofício, Justificativa" nas vias | `views.py:850` vs `views.py:918`; medido no 144/2026 |
| RF4 | Logo após emitir, a janela não acompanha a geração: "(gerando)" parado, rodapé "Ver minuta" (o PDF de agora com marca d'água) num ofício já emitido; `_documentos.html` (com *polling* de 2 s) ficou órfão — só a view `documentos_parcial` o usa | `_resumo.html:160-168, 209`; `views.py:935`; nenhum `include` de `_documentos.html` |
| RF5 | Mesmo documento listado duas vezes (Documentos + vias) | `_resumo.html:153-176` |
| RF6 | Leitor baixa PDF/Word (RG/CPF) individualmente mas não o pacote "por conter dados pessoais" | `views.py:944,993` × `views_pacotes.py:55-60` |
| RF7 | Emitido/cancelado sem histórico visível em lugar nenhum | `editar` redireciona não editáveis (`views.py:466-473`); resumo não traz histórico |

---

## 5. Propostas de superação

### P0
1. **Dados para o eProtocolo na janela** (R28): seção "Para o eProtocolo" (emitido e rascunho
   pronto) com Interessados, Assunto, Nº/Ano, Protocolo e Detalhamento, cada um com **Copiar** (o
   componente "Copiar um texto" do UI Lab), gerados por uma função de domínio pura
   (`dominio/eprotocolo.py`) testada contra o formato do legado. Melhor que o legado: "Copiar tudo"
   (texto já na ordem do formulário do eProtocolo) e confirmação acessível (`role=status`).
2. **Reabrir para correção** (RF1/R30): item "Reabrir para correção…" no ⋮ do emitido para quem tem
   `reabrir_oficio`, com `dialogo_motivo` (motivo obrigatório; aviso "a via assinada sai de uso"),
   ao lado de "Editar (retificar)" — ou decisão registrada de remover a rota.
3. **PDF que vale x minuta** (RF2/RF4): `pdf_oficio` só quando `situacao != rascunho`; rascunho
   retificado mostra "Ver minuta" e, em Documentos, "v1 (substituída — retificação em curso)".
   Enquanto houver documento `gerando`, a seção Documentos faz *polling* (reaproveitar
   `_documentos.html`/`documentos_parcial`) e o rodapé diz "PDF em geração…" com indicador;
   `falhou` mostra o erro e "Gerar de novo" (ver D-docs F1).
4. **Uma lista de documentos** (RF3/RF5): um registro por documento emitido, na ordem ofício →
   justificativa → termos, com versão, **emitido em dd/mm às hh:mm por Fulano**, selo
   Assinado/Sem via e as ações da via no mesmo registro; versões anteriores recolhidas
   ("2 versões anteriores").

### P1
5. **Origem do protocolo e do motorista** (R12/R17): "Protocolo 12.345.678-9 · aberto no
   eProtocolo em 02/10" (ou "simulado — confirme o número real", em tom de aviso); motorista de
   fora com "pelo Ofício 12/2026 · protocolo …".
6. **Conflitos e avisos fora da revisão** (R19): os avisos não bloqueantes também no resumo
   comum (recolhidos, com contagem).
7. **Histórico no resumo** (R29/RF7): aba ou seção recolhida "Histórico (N)" com as 6 últimas
   linhas e "ver tudo" — sobretudo para emitido/cancelado/arquivado, hoje sem lugar.
8. **Regras de download coerentes** (RF6): uma política só (`pode_baixar_documentos`) para PDF,
   Word e pacote — decidir com o dono se o leitor baixa documentos com CPF.
9. **Termos do ofício na janela** (R27): lista curta dos termos ligados (servidor, situação,
   assinado) em vez de só o link.

### P2
10. Hora do cancelamento (R10) e combustível da viatura (R18).
11. Documentos acima da dobra (R39): em 1440×900 levar "Documentos" para logo após as
    definições, ou um resumo de 1 linha no cabeçalho ("PDF v1 · assinado").
12. Miniatura da 1ª página do PDF emitido na própria janela (o legado mostrava a folha no
    cartão), carregada sob demanda.

---

## 6. Critérios de aceite (QA)
- Janela abre por clique, ⋮ e `?resumo=` para rascunho, emitido, emitido com via, cancelado,
  arquivado, **rascunho retificado com PDF antigo**; em cada um, os itens de §2 e a tabela de
  "Mais ações" conferem (teste de view por situação × papel: gestor, operador, leitor; outra
  unidade → 404).
- Seção eProtocolo: textos iguais ao formato do legado para um ofício fictício (teste de domínio)
  e botões Copiar com retorno anunciado.
- "Reabrir para correção…" alcançável pelo gestor e ausente para operador/leitor; revoga a via.
- Rascunho retificado: rodapé "Ver minuta"; Word "a minuta como está agora".
- Após emitir: a janela passa de "gerando" a "PDF v1" sozinha em ≤ 10 s com o worker ligado;
  `falhou` mostra mensagem e ação.
- Ordem ofício → justificativa → termos em todo lugar; cada documento listado uma vez.
- Consultas da janela ≤ 25 constantes; axe sem violações em 1440 e 390; sem rolagem horizontal.

## 7. Evidências desta análise
- Scripts (somente leitura/GET): `/home/claude/tools/rd_legado.py`, `rd_novo_resumo.py`,
  `rd_novo_resumo_ret.py`; medições com `CaptureQueriesContext` pelo shell de cada sistema.
- Capturas: `/home/claude/caps/res-doc/legado-editar-full.png`, `legado-cartao-oficio.png`,
  `legado-eprotocolo.png`, `novo-resumo-{rascunho,emitido+just,via-assinada,cancelado,arquivado}-{1440,390}.png`.
- Ambiente: durante a rodada o PREVIEW passou a responder 500 por "too many clients" no
  PostgreSQL (suíte paralela de outro agente); a verificação de R37 ficou por leitura de código.
