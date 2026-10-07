# Paridade — Folha do ofício (cadastro/edição, `/viagens/oficios/<pk>/editar/`)

> Agente 1 — Legacy/Parity Analyst · 07/10/2026 · ponto de partida: `oficios-inventario.md` §1.2
> e `docs/parity/oficio.md` (matriz do recorte vertical; várias regressões de lá já foram
> resolvidas — esta especificação reflete o código de hoje, branch `viagens/reconstrucao`).
>
> **Privacidade:** o LEGADO roda com backup de dados reais. Nenhum nome, CPF, RG, placa ou
> protocolo real aparece aqui; exemplos são fictícios (`05/2026`, `12.345.678-9`, `ABC1D23`).
> Capturas em `/home/claude/caps/{novo,legado}/…/viagens-oficios-*-editar.png` e
> `/home/claude/caps/folha/` — fora do repositório.

Caminhos abreviados:
- **LEG** = `/home/claude/legado` (somente leitura). Principais: `viagens_oficios/views.py`
  (`criar` 348, `editar` 559-716, `autosalvar` 719-754, `oficios_do_motorista` 757-769, `acao`
  806-860, `_aviso_de_condutor` 504, `_avisos_de_conflito` 536, `_data_final_do_oficio` 546),
  `forms.py` (`OficioForm`, `JustificativaForm`), `form_context.py`, `services.py`
  (`validar_oficio_para_documento`, `oficios_do_motorista` 368, `dados_eprotocolo` 409,
  `reabrir_oficio`), `justificativas_services.py`, `assunto_oficio.py`, `campos_modelo.py`,
  `protocolo_services.py`, `viagens_roteiros/services/rota.py`, templates
  `pages/viagens_oficios/form.html` e `pages/viagens_roteiros/_editor.html`, JS
  `static/js/{viagens-oficios,autosave-rascunho,roteiro-editor,conflitos,lista-escolha}.js`.
- **NOVO** = `gestao/viagens/` deste repositório: `views.py` (`novo` 348, `_contexto_edicao` 394,
  `editar` 464, `_usar_roteiro` 547, equipe 586-630, `secao_diarias` 632, `_revisao_pedida` 642,
  `emitir` 662, `autosave` 678, `retificar` 716, `reabrir` 731, `duplicar` 822, `rota` 1043),
  `forms.py` (`FormularioOficio` 225-450), `services.py` (`criar_rascunho` 152, `CAMPOS_EDITAVEIS`
  175, `_normalizar_motorista_externo` 193, `salvar_edicao` 229, `_aplicar_dados` 245,
  `definir_motorista` 309, `verificar_prontidao` 481, `emitir` 805, `retificar` 869,
  `duplicar_oficio` 997), `rotas.py`, `conflitos.py`, `dominio/{prazos,assunto,diarias}.py`,
  templates `viagens/oficios/{editar,_equipe,_diarias,_diarias_corpo,_acoes}.html`,
  `viagens/{_itinerario,_destinos,_trecho_campos,_bate_volta,_duracao,_sede}.html`,
  `templates/componentes/rodape_documento.html`, JS `static/js/componentes/{autosave,transporte,
  itinerario,mapa-rota,texto-pronto,combobox}.js`.

Legenda: ✅ paridade · ⚠️ parcial/diferente · ❌ falta no NOVO · ➕ só no NOVO (ou melhor) ·
🐞 defeito (em qualquer um dos dois).

---

## 0. Resumo executivo

- **G1 (🐞 P0, causa confirmada)**: no NOVO, **qualquer gravação da folha desmarca o motorista
  da equipe** — o `<select name="motorista_externo">` não tem opção vazia, então o navegador
  envia `servidor` mesmo com o bloco "Motorista de fora da equipe" fechado; o serviço entende
  "há motorista de fora" e apaga a marca da equipe. Reproduzido no navegador (PREVIEW, ofício
  novo) e no serviço (POST de autosave com o formulário como o navegador o envia). É a causa da
  falha do e2e `test_operador_cria_preenche_e_emite_um_oficio`. Ver §5.
- O NOVO é **muito mais leve** (30-33 consultas / 0,26-0,39 s / 159-184 KB contra 169-203 / 1,0-1,5 s
  / 218-375 KB no legado), sem rolagem horizontal e com axe limpo no documento principal.
- Lacunas funcionais de maior peso: **data do ofício = hoje ao emitir** (E10), **prévia ao vivo
  das diárias** e "Como foi calculado" (E52-E54), **indicador visível do autosave** (E70), avisos
  de **protocolo repetido** e **condutor não autorizado** (E33, E30), **sugestão do ofício de
  origem do motorista** (E28), **marcadores `{destino}`/`{periodo}`…** nos textos prontos (E17),
  painel **"Dados para o eProtocolo"** (E64), regra de **tempo de viagem/adicional** diferente da
  referência (E44-E45).
- e2e da folha: 6 vermelhos — 1 defeito de produto (G1), 1 defeito de produto mascarado por
  seletor velho (G3 transporte), 4 testes desatualizados (um deles expõe a lacuna E70). §6.

---

## 1. O que o LEGADO faz (fonte de verdade)

### 1.1 Entrada, estrutura e cabeçalho
- **Criar**: "Novo ofício" na lista faz `POST criar/` → `criar_oficio_rascunho` (numera na hora;
  **reaproveita rascunho vazio** com mais de 30 min, `services.py:63-106`; com `?viagem=` herda
  motivo e unidade solicitante) e abre `editar/?next=`. Medido: 3,6 s criar+abrir. `GET novo/` volta
  à lista.
- Permissão: `exigir_operador` (leitor recebe 403 — F13 da lista). **O GET grava** o snapshot da
  justificativa (`get_or_create_justificativa_oficio`, `justificativas_services.py:143-168`).
- Página única `form.html` com **7 cartões numerados**: 1 Dados e viajantes · 2 Roteiro e diárias ·
  3 Bate-volta diário e cálculo · 4 Trechos · 5 Diárias · 6 Justificativa · 7 Documentos.
- Cabeçalho: "Cadastro de ofício NN/AAAA", selo da situação (Rascunho/Gerado/Finalizado ou
  Cancelado), **selo do tipo** (Autorização/Convalidação · Retificado/Complementar) com a
  **explicação em texto** ("Sem data de saída no roteiro: por enquanto vale Autorização."),
  indicador do autosave ("Rascunho salvo às HH:MM", visível) e **Salvar ofício** (salva e volta à
  lista).
- Cancelado: faixa "Ofício cancelado" com motivo e data. **Fechado** (finalizado ou com PDF
  assinado, `fechamento_do_oficio`): faixa "…: somente leitura" com campo **Motivo da reabertura**
  e botão **Reabrir para correção** (revoga o assinado); todos os campos `disabled` exceto o
  cartão Documentos (`viagens-oficios.js:23-31`).

### 1.2 Cartão 1 — Dados e viajantes (`OficioForm`, `form_context.contexto_dados_viajantes`)
| Campo | Regra / validação / mensagem | Evidência |
|---|---|---|
| N° do Ofício | número + "/ AAAA"; em branco mantém o reservado; número ocupado → erro (`conferir_numero_digitado`, inclui numeração do Coffee) | `forms.py:83-89`, `form.html:119-126` |
| Protocolo | máscara `00.000.000-0` (JS); 9 dígitos ou erro "Informe um protocolo válido com 9 dígitos."; **ajuda dinâmica** pela origem (vazio: "Deixe em branco: ao salvar, o sistema abre o protocolo no eProtocolo…"; simulado/treinamento avisam que não vale); digitar troca a origem para manual | `forms.py:95-99`, `form_context.py:210-237`, `viagens-oficios.js:72-87` |
| Custeio | Unidade DPC / Outra instituição / Ônus limitado; vazio vira Unidade DPC | `forms.py:101-102` |
| Nome da Instituição | só com "Outra instituição" (JS mostra/esconde) | `form.html:130-132` |
| Data do ofício | `type=date` nativo; vazio mantém; **autosave não grava a data**; ao **Finalizar**, vira **hoje** se não foi mudada (decide Autorização × Convalidação e justificativa); volta à antiga se a finalização falhar | `views.py:546-556, 619-626, 687-695` |
| Modelo de motivo + Descrição | escolher o modelo **substitui o texto já com os marcadores aplicados** (`modelos_texto` JSON); padrão do catálogo pré-escolhido quando o motivo está vazio; engrenagem leva ao catálogo | `forms.py:61-73`, `views.py:709-713`, `viagens-oficios.js:48-61` |
| Servidores (equipe) | busca local (todas as pessoas renderizadas na página); cada pessoa com **Com termo/Sem termo** (marcado por padrão, exceto quem é da unidade emissora) e ×; **clicar na linha define/desfaz o motorista** (chip "Motorista"); "+" abre cadastro em outra aba | `form.html:152-193`, `viagens-oficios.js:207-282` |
| Viatura | lista com busca; sugeridas no topo com chip ("Unidade X", "Motorista: FULANO"); clicar de novo desfaz; "+" cadastro em outra aba | `form_context.py:68-93`, `viagens-oficios.js:324-378` |
| Cartão **Motorista** | só aparece com viatura escolhida e ninguém da equipe ao volante; "No sistema" (lista de servidores, **condutores autorizados da viatura no topo com selo**) / "Manual" (nome em MAIÚSCULAS); **Ofício de origem**: N° (aceita "15" → "15/ano") e Protocolo; ao escolher o motorista, `GET oficios-do-motorista/` sugere os ofícios em que ele viaja (mesma viagem › período sobreposto › recentes) e **preenche sozinho** quando há um provável | `form.html:205-244`, `forms.py:107-116`, `services.py:368-406`, `viagens-oficios.js:380-475` |
| Conflitos de agenda | caixa amarela **ao vivo** (pergunta ao servidor a cada escolha, sem salvar) | `form.html:246`, `conflitos.js` |

Fora do formulário do cadastro (só no editor documental `OficioDocumentoForm`): porte de armas,
viatura não cadastrada (placa/modelo/combustível/tipo), RG/CPF/cargo do motorista manual.

### 1.3 Cartões 2-5 — Roteiro e diárias (editor de roteiros embutido)
- **Vincular a um roteiro existente** (interruptor): busca entre os **200 mais recentes** não
  cancelados; escolher preenche o editor por `fetch` e **vincula** (o roteiro passa a ser do
  ofício; editar aqui altera o roteiro). Desligado: **Sede** (UF + município) e **Destinos**
  (UF + município, arrastar para ordenar, + e lixeira).
- **Bate-volta diário** (interruptor) com ida/volta (hora de saída e tempo) e calendário de datas.
- **Mapa** (Leaflet + OSM) com **Calcular rota** manual, "Ver rota inteira", métricas Distância/
  Tempo (ida e volta) e aviso "A ordem dos destinos mudou. Recalcule a rota…". Sem chave
  `OPENROUTESERVICE_API_KEY` → erro "Cálculo de rota não configurado" (sem estimativa offline);
  401/403, 429 e queda têm mensagens próprias (`rota.py:86-133`). Distâncias guardadas em
  `DistanciaMunicipios` valem antes da API.
- **Regra de tempo** (`rota.py:30-46, 140-165`): ETA = 85% × (km + 12) / 74 km/h + 15% × duração
  da API, em passos de 15 min (resto ≤ 5 cai, > 5 sobe); **tempo adicional sugerido = 1/6 da viagem,
  mínimo 15 min, zero abaixo de 30 min**.
- **Trechos**: tabela Origem · Destino · Data · Hora · Tempo de viagem · Tempo adicional · Tempo
  total · Chegada; **Preencher datas de saída** (calendário sequencial, uma data por trecho).
- **Diárias**: prévia ao vivo (`previa_diarias`) com selo Aguardando dados → calculando →
  atualizado / desatualizado / falha; Valor total, Tipo de destino, Quantidade, **Por extenso** e
  **"Como foi calculado"** (parcelas, faixa, período, %, valor unitário, subtotal, vigência). A
  quantidade de servidores acompanha a equipe na tela.
- Autosave do roteiro **desligado** no ofício (`data-autosave="0"`): o roteiro só grava no envio.

### 1.4 Cartão 6 — Justificativa
Sempre visível: Modelo (com marcadores aplicados) + texto. Obrigatória **só ao Finalizar** e só se
`oficio_exige_justificativa` (antecedência ≤ prazo, ou saída antes da data; prazo da
`ConfiguracaoSistema`, padrão 10). Mensagem: "Informe o texto da justificativa."

### 1.5 Cartão 7 — Documentos
Ofício e Justificativa (editor A4 embutido, carregado ao abrir), **Termos de Autorização** (um
por servidor marcado + "Baixar PDFs"), **Dados para o eProtocolo** (Interessados, Assunto,
Nº/Ano, Protocolo com Copiar + Detalhamento). Sem completar: "Complete o ofício para gerar e
consultar os documentos." Selos "Versão N emitida em", "Assinado", "Assinado, mas os dados
mudaram"; ações Visualizar, Baixar PDF, Emitir nova versão, Anexar/Trocar assinado.
**Não há lista de pendências na tela**: o botão do fim é "Salvar rascunho" enquanto houver
pendência e "Finalizar Ofício" quando não houver (`form.html:315-323`).

### 1.6 Salvar, finalizar, autosave e avisos
- **Salvar ofício / Salvar rascunho**: valida `OficioForm` + `JustificativaForm`; grava; vincula
  ou grava o roteiro; aplica **marcadores** (`preencher_marcadores_do_oficio`); **abre o protocolo
  no eProtocolo** se vazio (fora da transação); mensagens: **"O protocolo X também está no ofício
  N"** (medido), **condutor não autorizado** da viatura, **conflitos de agenda (5 + "E mais N")**,
  "Diárias: R$ … (resumo) para N servidores", "Rascunho salvo." → volta à lista.
- **Finalizar Ofício**: data final = hoje (ou a digitada), valida pendências
  (`validar_oficio_para_documento`: protocolo, motivo, custeio/observação, viajante, motorista de
  fora com ofício N/AAAA e protocolo, transporte viatura+motorista, roteiro com sede/saída/destinos,
  justificativa) → status FINALIZADO; aviso se o ano do número ≠ ano da data.
- **Autosave** (`autosave-rascunho.js`, 900 ms): envia o formulário inteiro em JSON; o servidor
  passa pelo mesmo `OficioForm` **sem** número, data, roteiro, finalização ou protocolo; inválido
  → nada é gravado e o indicador lista os erros ("Rascunho não salvo: revise os campos
  indicados. Informe um protocolo válido com 9 dígitos." — medido); sem controle de concorrência
  (última gravação vence). Só em Rascunho/Gerado.
- **Motorista sobrevive ao autosave** (medido: marcado → autosave → recarga → continua marcado;
  segundo autosave → continua).

### 1.7 Medições (LEGADO, `ref_local`, test client, GET; cópia descartável)
| Medida | Valor |
|---|---|
| GET editar (rascunho novo / com equipe / finalizado) | **169 / 183 / 203 consultas**, 1,0-1,5 s (5,7 s a frio, 443 consultas), **218 / 241 / 375 KB** |
| POST autosalvar | 53 consultas, 157 ms |
| Rolagem horizontal 1440 / 768 / 390 | **108 / 780 / 0 px** |
| axe (wcag2a/aa + best-practice) | 5× `color-contrast`, `link-in-text-block`, `nested-interactive` (sérios) em 1440 e 390 |

---

## 2. O que o NOVO faz hoje

- **Criar**: `POST novo/` → `criar_rascunho` (número reservado, data de hoje, sede da unidade,
  motivo padrão do catálogo; **não reaproveita rascunho vazio**) → toast "Ofício N criado.
  Preencha e salve." → folha.
- **Cabeçalho**: placa "OFÍCIO NNN/AAAA" (h1 só para leitor de tela), frase com selo da situação,
  "Fora do prazo", nº de servidores, destinos, período, viatura/transporte, valor das diárias;
  "Ver minuta" e ⋮ (Ver minuta, Ver o histórico, Excluir rascunho).
- **4 cartões**: 1 Identificação (Dados · Equipe · Transporte) · 2 Roteiro (usar roteiro
  cadastrado · itinerário · diárias) · 3 Justificativa de prazo (só quando exigida ou com texto) ·
  3/4 Documentos (conferência + editor/visualizador + histórico). "Assunto calculado: Solicitação
  de autorização… (Autorização)" na nota do cartão 1.
- **Dados**: Número do ofício, Data do ofício* (calendário próprio, máscara), Protocolo (para
  emitir; máscara; "O protocolo tem 9 dígitos; você informou N."), **Tipo de documento**
  (Autorização/Retificado/Complementar), Custeio* (Unidade/Outra instituição/Ônus limitados),
  Instituição que custeia (condicional por `:has()`), Texto pronto do motivo (+ "Guardar texto",
  engrenagem), Motivo da viagem (para emitir).
- **Equipe** (HTMX, "salva na hora"): combobox remoto (≥ 2 letras, nome/CPF/RG, exclui quem já
  está), "+" abre o diálogo de cadastro de servidor e o novo entra direto; cartões com avatar,
  cargo·unidade; botões Marcar/Desmarcar motorista (`aria-pressed`) e Remover; avisos de cadastro
  incompleto e de conflito de agenda (não bloqueiam).
- **Transporte** (`<pc-transporte>`): Meio de transporte (Viatura oficial / Outro meio);
  Viatura (combobox, sugeridas pela equipe com chips, "+" cadastro rápido); **marcar motorista
  escolhe a viatura que ele dirige** com toast; Outro meio → Meio de transporte* + "Detalhe
  (opcional)"; interruptor **Porte/trânsito de arma**; bloco **Motorista de fora da equipe**
  (Quem dirige: Servidor de outro ofício / Pessoa não cadastrada; servidor via combobox; nome;
  Ofício de origem N/AAAA; Protocolo do motorista).
- **Roteiro**: "Usar um roteiro cadastrado" (combobox dos roteiros compatíveis com a sede, botão
  "Usar este roteiro" — **cópia**, nada gravado até salvar, prévia das diárias mostrada; ADR 0015)
  ou link "Preenchido a partir do roteiro #N"; itinerário 2.0 (ADR 0016): Sede → destinos
  (UF + cidade, arrastar, + Adicionar destino) → volta à sede; **Bate-volta**; **Rota** automática
  (provedor OSRM/ORS com **estimativa offline** linha reta × 1,3 a 70 km/h e aviso); mapa;
  Trechos com só a **saída** informada (Tempo de viagem e adicional com −/+; chegada calculada) e
  **Preencher datas de saída**; Diárias (Valor total, por servidor, Tipo de destino, Quantidade
  por servidor; selo "Calculado para N servidores").
- **Documentos**: conferência ("N itens faltam para emitir", cada pendência é link para o
  bloco; avisos marcados "não impede a emissão"; ou "Tudo pronto para emitir"); **Revisar e
  emitir** (só sem pendências) → `?revisar=1` abre a janela de resumo em modo revisão com
  "Emitir ofício"; editor/visualizador ADR 0018 com miniaturas e modo PDF; Histórico (6 +
  "Ver histórico completo").
- **Barra do rodapé**: Voltar · (status só para leitor de tela) · **Finalizar** (salva e volta
  à lista) · Ações (Duplicar, Excluir). Enter em campo e **Ctrl+S** salvam e ficam na folha
  (`?salvo=1`).
- **Autosave** (`autosave.js`, 1,2 s): grava o que for válido (campo inválido fica de fora),
  trechos só quando o itinerário fecha, **controle de versão** (conflito: "Outra pessoa salvou
  este ofício enquanto você editava…"), fila de gravações, `sendBeacon` ao sair, não escreve no
  histórico.
- **Estados**: rascunho editável; emitido/cancelado/arquivado → `GET editar` redireciona à lista
  com mensagem (leitura na janela de resumo, ADR 0017); **Editar (retificar)** (qualquer editor;
  emitido → rascunho marcado Retificado, revoga assinado) e **Reabrir** (gestor, motivo).
- **Medido** (PREVIEW, gestor, test client): GET editar **30-33 consultas** (acima do orçamento
  de 25 do middleware), 260-390 ms (1,1 s a frio), 159-184 KB; autosave **26 consultas**, 80-93 ms.
  Rolagem horizontal **0/0/0 px** em 1440/768/390. axe sem violações no documento principal
  (ver E78 sobre o iframe).

---

## 3. Matriz LEGADO × NOVO

### 3.1 Entrada, estrutura, cabeçalho e estados
| # | Item | LEGADO (evidência) | NOVO (evidência) | Status |
|---|---|---|---|---|
| E1 | Criar = POST que numera e abre a folha | `views.py:348-360` | `views.py:348-361`, `services.py:152-171` | ✅ |
| E2 | Reaproveitar rascunho vazio (> 30 min) | `services.py:63-106` | sempre cria (rascunho vazio se exclui e libera o número) | ⚠️ (decisão anterior) |
| E3 | Criar a partir de viagem herdando motivo/unidade | `services.py:80-96` | `viagens/<pk>/novo/<tipo>/` | ✅ |
| E4 | Leitor abre a folha | 403 | redireciona à lista: "Seu perfil permite consultar, mas não editar ofícios." (`views.py:466-468`) | ➕ |
| E5 | GET sem efeito colateral | 🐞 grava snapshot da justificativa | GET puro | ➕ |
| E6 | Título e situação | "Cadastro de ofício NN/AAAA" + selo | placa + h1 sr-only + frase-resumo (`editar.html:19-47`) | ✅ ➕ |
| E7 | Tipo Autorização/Convalidação **com o porquê** | selo + explicação em texto (`form.html:53-55`) | "Assunto calculado: … (Autorização)" na nota do cartão; **sem o porquê** (dias × prazo) | ⚠️ |
| E8 | Fechado (finalizado/assinado) → somente leitura com "Reabrir para correção" na própria folha | `form.html:71-84`, `viagens-oficios.js:23-31` | emitido não abre a folha: volta à lista com mensagem; Retificar/Reabrir pelo ⋮/resumo | ⚠️ (decisão ADR 0017; perde o contexto ao seguir link direto) |
| E9 | Cancelado: faixa com motivo e data na folha | `form.html:65-69` | redireciona à lista | ⚠️ |
| E10 | **Data do ofício = hoje ao finalizar** (se não foi mudada; desfeita se a finalização falha) | `views.py:546-556, 619-626, 687-695` | `services.emitir` (805-848) **não toca `data_oficio`**: rascunho criado dias antes sai com a data antiga (afeta Autorização × Convalidação e a justificativa) | ❌ |
| E11 | Ano do número ≠ ano da data | aviso após finalizar (`views.py:697-701`) | **bloqueia** ao salvar: "A data do ofício deve estar em AAAA…" (`services.py:246-250`) | ⚠️ |
| E12 | Atalhos | Enter envia "Salvar ofício" (vai à lista) | Enter e **Ctrl+S** salvam e ficam; `Esc` nos seletores; Ctrl+K global | ➕ |

### 3.2 Identificação — dados
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E13 | Número editável com lacuna | `conferir_numero_digitado` | `forms.py:374-389`, `services.py:262-266` (lacuna D5) | ✅ |
| E14 | Protocolo: máscara, 9 dígitos | "Informe um protocolo válido com 9 dígitos." | "O protocolo tem 9 dígitos; você informou N." (`forms.py:391-396`) | ✅ ➕ |
| E15 | Ajuda do protocolo pela origem (eProtocolo/treinamento/simulado) + abertura automática | `form_context.py:210-237`, `protocolo_services.py` | ajuda fixa; sem abertura automática | ❌ (decisão pendente, já no inventário) |
| E16 | Custeio + instituição condicional | JS | `:has()` sem JS; obrigatório para emitir | ✅ ➕ |
| E17 | **Marcadores** `{destino}`, `{periodo}`, `{data_saida}`, `{data_retorno}`, `{dias_antecedencia}`, `{prazo}`, `{evento}`, `{servidores}`, `{data_oficio}`, `{numero_oficio}` nos textos prontos (aplicados ao escolher e na gravação) | `campos_modelo.py` | não existem: o texto pronto entra literal (`texto-pronto.js`) | ❌ |
| E18 | Texto pronto do motivo / padrão do catálogo | modelo pré-escolhido | motivo padrão na criação; "Guardar texto" para o catálogo; confirma antes de substituir | ✅ ➕ |
| E19 | Tipo de documento (Retificado/Complementar) | ação ⋮ (liga/desliga) | campo na folha + ⋮ (exclusão mútua no domínio) | ✅ |

### 3.3 Identificação — equipe e motorista
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E20 | Adicionar à equipe | lista local com todas as pessoas (peso) | combobox remoto (`views.py:1020-1039`), grava na hora | ✅ ➕ |
| E21 | Cadastrar pessoa sem sair | "+" em outra aba | diálogo de cadastro; entra direto na equipe | ➕ |
| E22 | Termo de autorização por pessoa (Com/Sem termo) | `form.html:184` | módulo Termos (`termos/do-oficio/`) | ⚠️ (decisão) |
| E23 | Definir motorista | clique na linha (`role=button`) | botão Marcar/Desmarcar com `aria-pressed` (HTMX) | ✅ |
| E24 | **Motorista persiste após salvar/autosave** | sim (medido) | **🐞 não: desmarcado em toda gravação** (G1) | 🐞 |
| E25 | Motorista escolhe a viatura | não (sugere viatura pela unidade do motorista) | escolhe a viatura que ele dirige + toast (`transporte.js:133-160`) | ➕ |
| E26 | Motorista de fora: quando aparece | só com viatura e ninguém da equipe ao volante | `<details>` sempre disponível no bloco Transporte | ⚠️ |
| E27 | Motorista de fora: modos | No sistema / Manual (nome em maiúsculas) | Servidor de outro ofício / Pessoa não cadastrada | ✅ |
| E28 | **Sugestão do ofício de origem** (`oficios-do-motorista`, preenche N° e protocolo) | `services.py:368-406`, `viagens-oficios.js:413-475` | inexistente | ❌ |
| E29 | N° do ofício de origem "15" → "15/AAAA" | `forms.py:107-116` | exige N/AAAA (`forms.py:405-406` só tira espaços) | ⚠️ |
| E30 | **Aviso: motorista não é condutor autorizado da viatura** | `views.py:504-516` | inexistente | ❌ |
| E31 | Condutores autorizados no topo da lista de motoristas | `viagens-oficios.js:380-411` | sugestão é viatura ← motorista (inverso) | ⚠️ |
| E32 | Conflito de agenda (servidor/motorista/viatura em outro ofício/termo/OS/palestra) | caixa ao vivo + 5 avisos após salvar | pendência não bloqueante; equipe ao vivo (HTMX); viatura só após gravar; todos listados sob o título "N servidores também estão em outro ofício" (inclui viatura) | ⚠️ (título errado p/ viatura) |
| E33 | **Aviso: protocolo repetido em outro ofício** | `views.py:639-651` (medido) | inexistente | ❌ |

### 3.4 Identificação — transporte
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E34 | Viatura cadastrada com sugestões e chips | `form_context.py:68-93` | `SelecaoDeViatura` + `transporte.js:73-110` | ✅ |
| E35 | Viatura não cadastrada (placa/modelo/combustível/tipo) | só no editor documental | "Outro meio": Meio de transporte + Detalhe | ⚠️ |
| E36 | Pendência de "outro meio" coerente com a tela | — | 🐞 serviço exige **descrição** (`services.py:501-502` "Descreva o meio de transporte.") enquanto a tela marca **Meio** como exigido e Detalhe como "(opcional)" (`editar.html:129-130`) (G3) | 🐞 |
| E37 | Porte de arma | só no editor documental | interruptor no bloco | ➕ |

### 3.5 Roteiro, trechos e diárias
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E38 | Roteiro existente | **vínculo** (200 recentes; editar altera o roteiro) | **cópia** dos roteiros compatíveis com a sede; prévia das diárias; "Mudanças aqui não alteram o roteiro" (`views.py:547-583`) | ⚠️ (ADR 0015) |
| E39 | Sede e destinos (UF + município, arrastar) | `_editor.html` | `_itinerario.html`, `_destinos.html` | ✅ |
| E40 | Bate-volta diário | interruptor + calendário | interruptor + blocos (`_bate_volta.html`) | ✅ |
| E41 | Preencher datas de saída | `date_multi` | botão "Preencher datas de saída" | ✅ |
| E42 | Trechos: entrada | data, hora, tempo, adicional; chegada mostrada | só a saída; tempos com −/+; chegada calculada na tela e no servidor | ✅ ➕ |
| E43 | Rota: cálculo | manual ("Calcular rota"), aviso "ordem mudou" | automático; total ida / ida e volta | ✅ ➕ |
| E44 | **Tempo de viagem** | (km+12)/74 km/h com 15% da API, passos de 15 (resto ≤ 5 cai) (`rota.py:140-152`) | duração do provedor arredondada **para cima** a 15 min (`rotas.py:45-47`); estimativa 70 km/h × 1,3 | ⚠️ (ADR 0016; muda chegadas e pode mudar diárias) |
| E45 | **Tempo adicional sugerido** | 1/6 da viagem, mín. 15, 0 abaixo de 30 min | 15 min a cada 2 h completas (`rotas.py:41-43`) | ⚠️ (idem) |
| E46 | Sem provedor / falha | erro e nada calculado | **estimativa offline** com aviso | ➕ |
| E47 | Mapa sem traçado (estimativa) | — | placa "O mapa traça a rota assim que houver a sede e um destino." mesmo com sede e destinos (`_itinerario.html:65`) | 🐞 menor (G7) |
| E48 | Limite de trechos | — | 40 com mensagem (`services.py:354-370`) | ➕ |
| E49 | Sequência (saída antes da chegada anterior; origem = destino anterior) | formset do roteiro | `_validar_sequencia` com mensagens | ✅ |
| E50 | Autosave do roteiro | desligado no ofício | grava quando o itinerário fecha | ➕ |
| E51 | Diárias: valor, tipo de destino, quantidade | ✅ | ✅ + valor por servidor | ✅ ➕ |
| E52 | **Prévia ao vivo** das diárias com selo (aguardando/calculando/desatualizado/falha) | `roteiro-editor.js` + `previa_diarias` | o ofício **não** tem `data-previa-diarias` (só a folha do roteiro); diárias só mudam ao gravar a equipe (`hx-trigger="equipe-alterada"`) — **após autosave dos trechos o cartão fica velho sem aviso** | ❌ |
| E53 | Diárias **por extenso** na folha | cartão "Por extenso" | só na janela de resumo/revisão | ⚠️ |
| E54 | **"Como foi calculado"** (parcelas, %, valor unitário, vigência) | `_como_calculado.html` | inexistente na folha | ❌ |
| E55 | Mensagem duplicada sem trechos | — | 🐞 "Informe os trechos de ida e de volta." **e** "Informe os trechos (ida e volta)." na conferência (`services.py:503-506` + `386`) (G4) | 🐞 |

### 3.6 Justificativa
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E56 | Regra do prazo (≤ prazo ou retroativa) | `justificativas_services.py` | `dominio/prazos.py:53-65` | ✅ |
| E57 | Prazo configurável | `ConfiguracaoSistema` (10) | configuração da unidade | ✅ |
| E58 | Cartão visível | sempre | só quando exigida ou com texto (`views.py:379-391`); "Justificativa incluída mesmo dispensada" | ➕ |
| E59 | Obrigatória para emitir | só ao finalizar | pendência bloqueante com a mensagem do prazo | ✅ |
| E60 | Texto pronto da justificativa (com marcadores) | ✅ | ✅ sem marcadores (E17) | ⚠️ |

### 3.7 Documentos, emissão e histórico
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E61 | **Lista de pendências visível** | ❌ (só o botão muda) | conferência com links por seção, avisos não bloqueantes | ➕ |
| E62 | Emitir | "Finalizar Ofício" | "Revisar e emitir" → janela de revisão → "Emitir ofício" (PDF/A pela outbox) | ✅ ➕ |
| E63 | Editor/visualizador dos documentos | cartões que abrem o editor | editores unidos com miniaturas e modo PDF (ADR 0018) | ✅ ➕ |
| E64 | **Dados para o eProtocolo** (Copiar) | `services.py:409-448` | inexistente | ❌ |
| E65 | Termos de autorização na folha | cartão com um por servidor | módulo Termos | ⚠️ |
| E66 | Baixar / anexar assinado | por documento | `dialogo_baixar` (via Ações/resumo) | ✅ |
| E67 | Histórico | só no editor documental | bloco Histórico na folha | ➕ |

### 3.8 Salvar, autosave, barra de ações
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E68 | Salvar e voltar à lista | "Salvar ofício"/"Salvar rascunho" | "Finalizar" ("Ofício N salvo.") | ✅ |
| E69 | Salvar e ficar | — | Enter / Ctrl+S (`?salvo=1`) — **sem botão visível** (o "Salvar rascunho" é `sr-only aria-hidden`, `editar.html:65`) | ⚠️ |
| E70 | **Indicador do autosave visível** | "Rascunho salvo às HH:MM" ao lado de Salvar | `[data-status-salvamento]` é **`sr-only`** (`editar.html:343`): quem enxerga não vê "Salvo automaticamente às…", "Salvando…", erro de conflito nem "Alterações não salvas" | ❌ |
| E71 | Autosave: o que grava | form inteiro menos número/data/roteiro | tudo que for válido, inclusive data e trechos | ⚠️ (data: ver E10) |
| E72 | Autosave inválido | nada gravado + erros no indicador | grava o resto, campo inválido fica de fora, sem aviso | ⚠️ |
| E73 | Concorrência | última gravação vence | `versao` + "Outra pessoa salvou…" | ➕ |
| E74 | Proteção de saída com alterações | não | `beforeunload` (`data-proteger`) | ➕ |
| E75 | Toast pós-salvar com diárias | "Diárias: R$ … para N servidores" | selo no cartão Diárias | ✅ |
| E76 | Duplicar | — | ⋮ Ações → novo rascunho com dados, equipe, motorista, trechos, texto editado (`services.py:997-1030`) — **copia também o marcador** (Retificado/Complementar) e a justificativa | ➕ ⚠️ (G6) |
| E77 | Excluir rascunho | ⋮ (sempre, falha por proteção) | Ações/⋮ só sem documento, com confirmação | ✅ ➕ |

### 3.9 Responsivo, acessibilidade, desempenho
| # | Item | LEGADO | NOVO | Status |
|---|---|---|---|---|
| E78 | axe | 7 nós sérios (contraste, link em bloco, interativo aninhado) | 0 no documento principal; com o iframe da folha carregado (390 px) o axe acusa `document-title`, `html-has-lang`, `landmark-one-main`, `page-has-heading-one`, `region` **dentro do iframe** do editor | ➕ (⚠️ iframe — conferir no QA) |
| E79 | Rolagem horizontal 1440/768/390 | 108/780/0 px | 0/0/0 px | ➕ |
| E80 | Consultas GET | 169-203 | 30-33 (acima do orçamento de 25 → aviso no log) | ➕ ⚠️ |
| E81 | Tempo GET (quente) | 1,0-1,5 s | 0,26-0,39 s | ➕ |
| E82 | Peso HTML | 218-375 KB | 159-184 KB | ➕ |
| E83 | Autosave | 53 consultas / 157 ms | 26 consultas / 80-93 ms | ➕ |
| E84 | Campo focado sob topo/barra (WCAG 2.4.11) | — | e2e verde em 360/768/1440 | ➕ |
| E85 | Seletores próprios (data, hora, listas) | nativos | design system, teclado completo (e2e verdes) | ➕ |

**Lacunas ❌**: E10 data = hoje ao emitir · E15 protocolo automático · E17 marcadores · E28
sugestão do ofício de origem · E30 condutor não autorizado · E33 protocolo repetido · E52 prévia
ao vivo das diárias · E54 "Como foi calculado" · E64 Dados para o eProtocolo · E70 indicador
visível do autosave.

---

## 4. Fluxos testados nos dois sistemas

| Fluxo | LEGADO (medido) | NOVO (medido) |
|---|---|---|
| Criar → abrir | 3,6 s; número reservado; motivo padrão preenchido | 5,2 s (dev server, 1ª vez); número; motivo padrão |
| Autosave do motivo | 1 POST; "Rascunho salvo às HH:MM" visível | 1 POST; "Salvo automaticamente às HH:MM" só no leitor de tela |
| Autosave com protocolo inválido | não grava; indicador com o erro | grava o resto; protocolo fica de fora, sem aviso |
| Equipe → motorista → autosave → recarregar | motorista **continua** marcado | motorista **desmarcado**; bloco "Motorista de fora · Servidor de outro ofício" aberto; pendência "Escolha o servidor que vai dirigir." (G1) |
| Salvar com pendências | volta à lista; avisos de protocolo repetido / conflitos; "Rascunho salvo." | Finalizar → lista "Ofício N salvo."; Enter/Ctrl+S → fica, conferência atualizada |
| Emitir | Finalizar (só sem pendências) → data = hoje | Revisar e emitir → janela → Emitir; data **não** muda (E10) |
| Corrigir emitido | Reabrir para correção (motivo) na folha | Editar (retificar) / Reabrir (gestor, motivo) pelo ⋮/resumo |
| Usar roteiro cadastrado | vincula e recarrega | copia, prévia das diárias, salva ao confirmar |

Scripts (fora do repositório): `/home/claude/tools/folha_legado.py`, `folha_legado2.py`,
`folha_novo.py`, `axe_folha.py`; medições de consultas com `CaptureQueriesContext` (autosave
dentro de transação revertida).

---

## 5. Defeitos

| ID | Onde | Defeito | Causa / evidência |
|---|---|---|---|
| **G1** | NOVO | **Salvar a folha desmarca o motorista da equipe** (autosave, Enter, Ctrl+S, Finalizar, `sendBeacon` ao sair) e liga um "motorista de fora" fantasma (`motorista_externo='servidor'`), que vira pendência bloqueante "Escolha o servidor que vai dirigir." | `forms.py:327-330` tira a opção vazia de `motorista_externo` → o `<select>` (oculto, `editar.html:141`, dentro de `<details>` fechado `:138`) fica com a 1ª opção selecionada pelo navegador (`value="servidor"`, medido); `transporte.js:119-131` só zera o valor no evento `toggle` (nunca no carregamento); `autosave.js` envia `FormData` do formulário inteiro; `services.py:269-275` (`_aplicar_dados` → `_normalizar_motorista_externo`, `:193-205`) com modo `servidor` executa `viajantes.filter(motorista=True).update(motorista=False)`. A tela não percebe no autosave (o `#equipe` não é região viva) e só mostra após recarregar. Introduzido em `afcf0dd` (06/10). No PREVIEW, rascunhos 247, 260 e 262 já estão com `motorista_externo='servidor'` (prováveis vítimas). |
| G2 | NOVO | Ao emitir, a data do ofício continua a da criação: Autorização/Convalidação e a obrigatoriedade da justificativa podem sair erradas | `services.py:805-848` (E10) × LEG `views.py:546-556` |
| G3 | NOVO | "Outro meio" com Meio escolhido e sem Detalhe fica bloqueado por "Descreva o meio de transporte." enquanto a tela diz "Detalhe (opcional)" e marca Meio como exigido; Meio vazio não gera pendência | `services.py:500-502` × `editar.html:129-130` |
| G4 | NOVO | Duas pendências para a mesma falta (sem trechos) | `services.py:503-506` + `386` |
| G5 | NOVO | Indicador do autosave invisível para quem enxerga (inclui erro de conflito de versão e "não foi possível salvar") | `editar.html:343` (`sr-only`) |
| G6 | NOVO | Duplicar copia o marcador Retificado/Complementar (o novo rascunho nasce "Retificado" de nada) | `services.py:1004-1006` (`CAMPOS_EDITAVEIS` inclui `marcador`, `justificativa`) |
| G7 | NOVO | Com a estimativa offline o mapa mostra "O mapa traça a rota assim que houver a sede e um destino." com sede e destinos preenchidos | `_itinerario.html:65`, `mapa-rota.js` (sem `tracado` não desenha nem troca a mensagem) |
| G8 | NOVO | Diárias do cartão ficam velhas após o autosave gravar trechos novos (sem selo "desatualizado") | `editar.html:202` (só `equipe-alterada`), sem `data-previa-diarias` |
| G9 | NOVO | Conflito de **viatura** aparece sob o título "N servidores também estão em outro ofício" | `_equipe.html` (`so_avisos` de `pendencias_da_secao:"equipe"`), `services.py:510-511` (todos os conflitos com seção "equipe") |
| G10 | NOVO | `definir_motorista` com `viajante` não numérico → 500 (`int()` sem validação) | `views.py:625-626` |
| G11 | NOVO | GET da folha estoura o orçamento SQL do middleware (30-33 > 25) | log `Orçamento SQL excedido` |
| G12 | LEG | GET grava; sem lista de pendências; rolagem horizontal 108/780 px; contraste | §1.7 |

---

## 6. e2e da folha (`uv run pytest tests/e2e/test_fluxo_oficio.py -q -p no:cacheprovider`)

Resultado: **6 falharam, 20 passaram** (640 s).

| Teste | Falha | Classificação |
|---|---|---|
| `test_operador_cria_preenche_e_emite_um_oficio` (`:66`) | depois do Enter, o botão "Desmarcar Isabela… como motorista" não existe (motorista desmarcado) | **Defeito de produto (G1)**. Depois de corrigir, rodar de novo: os passos seguintes (diárias "2 x 100% + 1 x 15%", R$ 624,68, Revisar e emitir) não foram exercitados |
| `test_emissao_bloqueada_sem_justificativa_mostra_o_motivo` (`:100`) | `.barra-acoes__status` não existe | **Teste desatualizado** (o status virou `[data-status-salvamento]` sr-only), mas aponta a lacuna real **E70/G5** — corrigir o produto (indicador visível) e o seletor juntos |
| `test_formulario_do_oficio_escolhas_itinerario_e_conferencia` (`:348`) | rótulo "Descrição do transporte" não existe | **Teste desatualizado** (agora "Meio de transporte" + "Detalhe (opcional)"); a mudança expôs **G3** (pendência incoerente) |
| `test_relogio_e_lista_propria` (`:455`) | combobox "Combustível" não existe em "Outro meio" | **Teste desatualizado** (placa/combustível saíram de "Outro meio"); trocar pela lista "Meio de transporte" |
| `test_folha_mostra_a_minuta_emoldurada` (`:476`) | `#editor-oficio` "não visível" | **Teste desatualizado**: o `<pc-editor-documento>` é `display: contents` (caixa 0×0) nos editores unidos; a folha carrega (200) e o iframe tem 1295 px. Rolar até `#minuta`/o iframe |
| `test_marcar_motorista_escolhe_a_viatura_dele` (`:513`) | botão "Salvar rascunho" não existe | **Teste desatualizado** (o botão é `sr-only aria-hidden`; usar Ctrl+S/Enter ou "Finalizar"). Atenção: ao salvar, G1 também desmarcaria a motorista — acrescentar a asserção |

---

## 7. Propostas de superação (priorizadas)

### P0 — defeitos e regras
1. **G1 — motorista**: devolver a opção vazia ao campo ou, melhor, separar "há motorista de
   fora" (o `<details>`) do "quem" — p.ex. `motorista_externo` só é enviado quando o bloco está
   aberto (`disabled` nos campos do bloco fechado, como manda o HTML) **e** o serviço só normaliza
   quando o modo **mudou** (`"motorista_externo" in alterados`). Teste de serviço: autosave com
   o formulário renderizado (todas as entradas `form=form-oficio`) preserva `motorista=True`;
   e2e: marcar → digitar → esperar autosave → recarregar → continua marcado. Saneamento: limpar
   `motorista_externo='servidor'` sem `motorista_externo_servidor` nos rascunhos (migração de
   dados ou comando) — no PREVIEW, 247/260/262.
2. **G2/E10 — data do ofício na emissão**: na revisão, mostrar "Data do ofício: 01/10 → hoje
   (07/10)" com a consequência ("vira Convalidação; justificativa passa a ser obrigatória") e
   emitir com hoje salvo se a pessoa tiver mudado a data à mão (`data_oficio` alterada pelo
   usuário ≠ data da criação). Domínio puro decide; teste por fronteira (prazo).
3. **E70/G5 — indicador visível**: "Salvando… / Salvo às HH:MM / Não salvo: <motivo> /
   Alterações não salvas" à vista na barra (com `role=status`), erro de conflito com ação
   "Recarregar". Corrigir o e2e junto.
4. **G3 — Outro meio**: pendência = Meio obrigatório; Detalhe opcional (ou exigir Detalhe só
   para "Outro"). Uma regra no serviço, a mesma na tela.
5. **E33 + E30 — avisos que evitam erro de digitação**: protocolo repetido (com link para o
   outro ofício) e condutor não autorizado, como **avisos não bloqueantes da conferência**
   (melhor que o legado, que só avisava depois de sair da tela).
6. **G4/G9** — uma pendência por falta; avisos de viatura no bloco Transporte com título próprio.

### P1 — paridade de produtividade
7. **E52/G8 — prévia ao vivo das diárias** no ofício (reusar `previa_diarias_roteiro` com a
   equipe atual), selo Aguardando/Calculando/Atualizado/Desatualizado; + **Por extenso** (E53) e
   **"Como foi calculado"** (E54) em `<details>`.
8. **E28 — ofício de origem do motorista**: ao escolher o servidor de fora, sugerir os ofícios
   em que ele viaja (mesma viagem › período sobreposto › recentes), preencher quando houver um
   provável; aceitar "15" → "15/AAAA" (E29).
9. **E17 — marcadores** nos textos prontos (motivo e justificativa), aplicados ao escolher e
   resolvidos na gravação; legenda dos marcadores no catálogo (`/cadastros/textos-prontos/`).
10. **E7 — o porquê do tipo**: "Convalidação — a viagem começa 3 dias depois da data do ofício
    (prazo 10)" na nota do cartão e na revisão.
11. **E44/E45 — tempos**: decidir com o dono do produto (ADR 0016 × referência). Se a regra do
    legado valer, implementar no domínio (`tempo_de_viagem`, `adicional = max(15, 1/6)`) com
    testes de caracterização; se não, registrar a divergência e o impacto nas diárias.
12. **E64 — "Dados para o eProtocolo"** no cartão Documentos (componente Copiar já existe).
13. **E8/E9 — link direto para um emitido/cancelado**: em vez de jogar na lista, abrir a lista
    já com o resumo (`?resumo=<pk>`) — hoje a mensagem pede para "abrir o resumo na lista".

### P2 — acabamento
14. G6 — Duplicar sem marcador (e sem justificativa quando dispensada no novo período).
15. G7 — mensagem do mapa coerente com a estimativa ("Rota estimada; o traçado aparece quando o
    serviço responder").
16. G11 — reduzir as consultas do GET (≤ 25): `historico` e `documentos` já em cache; conferir
    `verificar_prontidao` + `conflitos` + `avaliar_prazo` (trechos lidos várias vezes).
17. G10 — validar `viajante` em `definir_motorista` (400, não 500).
18. E69 — botão visível "Salvar" (sem sair) ao lado de "Finalizar", ou dica "Ctrl+S salva".
19. E78 — `lang`/`title` na folha do editor servida no iframe (ou `title` no iframe e axe com
    `iframes:false` justificado).

---

## 8. Critérios de aceite (QA)

- **G1**: teste de serviço + e2e (marcar motorista → autosave → Enter → Finalizar → recarregar:
  `aria-pressed="true"`; `motorista_externo == ""`); `test_operador_cria_preenche_e_emite_um_oficio`
  verde até "Emitir ofício"; nenhum rascunho do PREVIEW com `motorista_externo` sem dados.
- Os 6 e2e de `test_fluxo_oficio.py` verdes, com os seletores atualizados descritos em §6 e
  as asserções novas de G1/G3/E70.
- E10: emissão de rascunho criado em data anterior sai com a data de hoje (ou a escolhida) e a
  revisão anuncia a mudança; teste de domínio nas fronteiras do prazo (dias = prazo, prazo+1, < 0).
- E70: indicador visível em 360-1440 com os quatro estados; erro de conflito com ação.
- E33/E30: avisos na conferência ("não impede a emissão") com link; teste de serviço.
- E52-E54: diárias do cartão iguais às gravadas após cada autosave de trechos; prévia marcada
  como prévia; "Como foi calculado" bate com `diarias_calculo`.
- Consultas do GET ≤ 25 constantes (com 1, 12 e 40 trechos); autosave ≤ 30.
- 360-1440 sem rolagem horizontal; axe sem violações com o iframe carregado; foco nunca sob
  topo/barra (e2e existente).
- Benchmark com o legado: criar → preencher → emitir em menos passos e menos tempo; mesmos
  valores de diárias para os mesmos trechos (após a decisão E44/E45).
