# Paridade — Documentos do ofício (ofício, justificativa, termos)

> Agente 1 — Legacy/Parity Analyst · 07/10/2026 · complementa `oficios-resumo.md` (onde os
> documentos aparecem) e `oficios-inventario.md` §1.4. Escopo: gerar, visualizar, baixar
> (PDF/DOCX, pacote), versões emitidas, minuta, vias assinadas, editor de documento, modelos de
> texto, conteúdo impresso e desempenho.
>
> **Privacidade:** comparação feita com um ofício de teste do backup (LEG) e um fictício do
> PREVIEW (NOVO); nenhum dado real é transcrito. PDFs/PNGs em
> `/tmp/claude-0/…/scratchpad/pdf/` e `/home/claude/caps/res-doc/` (fora do repositório).

Caminhos abreviados:
- **LEG** = `/home/claude/legado`: `viagens_oficios/views.py` (`preview_artefato` 35,
  `assinatura_artefato` 48-86, `baixar` 296-345, `visualizar` 775, `visualizar_termo` 791,
  `gerar` 878, `documento` 893, `documento_folha` 903, `termos_todos_pdf` 919, `termos` 941),
  `viagens_oficios/document_generation.py` (19-55), `documentos/services/emissao.py`
  (`registrar_emissao` 109, `documento_alterado_depois` 151, `emitir` 177),
  `documentos/services/{facade,assinados,conferencia_assinado,persistence}.py`,
  `documentos/editor/{api,completo,modelos,blocos,campos,pagina,vinculos}.py`, `documentos/urls.py`,
  `templates/documentos/pdf/{oficio,justificativa}.html`, `templates/components/v32/{dialogo_baixar,dialogo_assinado}.html`.
- **NOVO** = `gestao/viagens/`: `views.py` (`documentos_parcial` 935, `baixar_documento` 944,
  `previa` 968, `baixar_docx` 993), `services.py` (`emitir` 805, `reabrir` 850, `retificar` 869),
  `assinantes.py` (`gerar_documento` 15-40), `documentos/{pdf,docx,dados,campos,regioes,leitura}.py`,
  `views_editor.py`, `views_pacotes.py`, `pacotes.py`, `views_assinados.py`, `assinados.py`,
  templates `viagens/documentos/{oficio,justificativa}.html`, `viagens/oficios/{editar,_editor,_documentos}.html`,
  `templates/componentes/{dialogo_baixar,dialogo_assinado}.html`, `static/js/componentes/{editores,editor-documento}.js`,
  `static/js/app.js`, `gestao/plataforma/outbox.py`.

Legenda: ✅ paridade · ⚠️ parcial/diferente · ❌ falta no NOVO · ➕ só no NOVO · 🐞 defeito.

---

## 1. LEGADO

### 1.1 Modelo de emissão: "via emitida" (m113/m140)
- Geração **síncrona** na requisição (`gerar_documento`, `document_generation.py:19-55`):
  exige ofício não cancelado e **sem pendências**; reserva o número; fixa a data da justificativa na
  1ª emissão; motor `html_weasyprint` (template HTML → PDF/A-2a) para o PDF; DOCX por **docxtpl** a
  partir do `.docx` oficial.
- O **primeiro PDF** pedido (por visualizar, baixar, o iframe ou o ZIP) vira a **via emitida v1**
  e o status passa de Rascunho a **Gerado** (`document_generation.py:50-53`, `emissao.py:109-148`).
  Pedidos seguintes devolvem a mesma via (cache por chave de dados+modelo: 60–80 ms).
- **Emitir nova versão** (`nova_versao=1`) refaz com os dados de hoje → v2, v3…; se nada mudou,
  mantém a via (medido: "nova versão" sem mudança devolve a mesma via em 178 ms).
- Mudou o próprio documento (ofício, blocos, versão editada) depois da via → a próxima geração faz
  a versão seguinte **sozinha** (`documento_alterado_depois`, `emissao.py:151-174`); mudança "de
  fora" (chefe que assina, endereço da unidade) não muda a via.
- Via **assinada** anexada vale por cima de tudo (`documento_assinado`, `facade.py`).

### 1.2 Onde e como
| Ação | Rota / UI | Regra |
|---|---|---|
| Visualizar (iframe/nova aba) | `GET <pk>/visualizar/<tipo>/` (`views.py:775`), cartão do documento | operador; 409 texto com a pendência |
| Gerar/baixar | `POST <pk>/gerar/<tipo>/<pdf|docx>/` (`views.py:878`) | `nova_versao=1` = nova versão |
| Folha do editor | `GET <pk>/documento/folha/`, `documentos/editor/<tipo>/<pk>/…` | ver §1.4 |
| Termos | `visualizar/termo/<servidor>/`, `termos/<servidor>/<fmt>/`, `termos/<fmt>/` (ZIP), `termos/todos/pdf/` (PDF único) | por servidor marcado "Com termo" |
| Baixar documentos (modal) | `POST <pk>/baixar/` (`views.py:296-345`) | itens ofício/justificativa/termo-N; PDF/DOCX; assinado/original; separados (ZIP)/um PDF |
| Abrir artefato | `documentos/<uuid>/preview/`, `documentos/<uuid>/abrir|baixar/` | `no-store` |
| Assinado | `documentos/<uuid>/assinatura/` (GET/POST; `acao=remover`), `documentos/<uuid>/conferir-assinado/` (prévia JSON) | operador |

### 1.3 Assinados (m109/m112)
- Modal único (`dialogo_assinado.html`): escolher documento (seletor quando há vários), PDF,
  **conferência antes de enviar** — o modal envia o arquivo a `conferir-assinado` e mostra "quem
  assinou"/avisos (campos `/Sig`, CN do certificado ICP-Brasil, carimbo do eProtocolo; número,
  protocolo e nomes esperados) **antes** de confirmar; depois do envio, as mesmas mensagens.
- Remover a versão assinada: botão no próprio modal ("O PDF gerado volta a valer").
- Selo "Assinado, mas os dados mudaram" com a lista das mudanças (`mudancas_desde_a_assinatura`,
  `assinados.py:131`).
- PDF assinado → ofício **fechado** (somente leitura) até "Reabrir para correção", que revoga a via.

### 1.4 Editor de documento e modelos
- Folha A4 editável embutida no cartão do documento (abre um por vez), barra com Desfazer/Refazer,
  estilo de parágrafo, N/I/S/tachado, alinhamentos, listas, recuo, **tabela** (+linha/+coluna/−),
  linha horizontal, **quebra de página antes do parágrafo**, **zoom**, "Editar por campos",
  "Imprimir" (PDF em nova aba), estado "Acompanhando os dados" e **Histórico** (capturado em
  `rd_legado.py`).
- **Campos vinculados** (~22 para ofício/justificativa — `documentos/editor/campos.py`): data,
  protocolo, motivo, custeio, viajantes, **nome/CPF/cargo do servidor**, **nº da solicitação
  (Central de Viagens)**, porte, tipo, transporte, motorista, roteiro, órgão, unidade emissora,
  destino, destinatário, assinante, endereço, **data e assinante da justificativa**… — editar na
  folha grava na origem (inclusive no cadastro do servidor e na configuração).
- **Blocos documentais** com texto padrão (`blocos.py:46-76`) — o texto alterado vale só para o
  documento; **pontos de quebra** controlados (após equipe, após roteiro, após transporte, antes da
  assinatura) e **parágrafos extras** (após a abertura, antes da assinatura).
- **Editor completo** (m057): documento inteiro editado à mão, versões com autor/data, restaurar
  e "voltar ao modelo" (`completo.py:188-246`); **presença** (`api.py:284`), **páginas** do PDF
  (`api.py:354`), **textos prontos** por campo (`api.py:394`).
- **Modelos de texto** (`/documentos/modelos/`, `editor/modelos.py`): o **gestor de Viagens** edita
  os textos-base de cada tipo (ofício, justificativa, termo, OS, plano, relatório…), que valem para
  os próximos documentos.

### 1.5 Conteúdo impresso (template `documentos/pdf/oficio.html`)
Brasão; SESP / PCPR / unidade; tabela Ofício Nº (tipo) · Data · Origem · Destino · Protocolo ·
Assunto; abertura **"Senhor Delegado, através deste, solicito {assunto} e medidas para a concessão de
diárias e recursos para combustível, conforme cronograma abaixo:"**; equipe (Nome, CPF, Cargo, **Nº
solicitação (Central de Viagens)** preenchido da prestação); destino · nº de diárias · valor total;
roteiro de ida e de retorno; transporte (meio, placa oficial, **motorista + "Ofício do Motorista: N/AAAA"
+ "Protocolo do Motorista: …"** quando é de fora; combustível; tipo de viatura); porte; custos (3
opções); motivo; declaração **"…estão cientes da necessidade de estar na posse de cartão corporativo
vigente e apto para uso, no período do deslocamento."**; "Respeitosamente," + assinante; destinatário
no pé (Exmo. Sr / DR. / MD. / cidade – Pr.); marca PCPR + rodapé da unidade.
Justificativa (`justificativa.html`): **"<sede>, <data por extenso>"** à direita (data fixada na 1ª
emissão), título "Justificativa", texto em parágrafos, assinante; folha ASCOM (sans).
Sem numeração de páginas; sem marca d'água (não existe "minuta": a 1ª visualização já é a via).

### 1.6 Medições (LEG, ofício de teste, 2 servidores)
| Medida | Valor |
|---|---|
| 1º PDF do ofício (frio) | 4,2 s; sem cache, quente: 1,9–2,4 s; via guardada: 60 ms |
| PDF da justificativa | 0,9–1,2 s; via: 76 ms |
| DOCX ofício / justificativa | 1,2 s / 0,3 s (cache 0,1–0,2 s) |
| PDF | **PDF/A-2a** (pdfaid part 2, conformance A; OutputIntent), *tagged*, `/Lang pt-BR`, 1 página, 57 KB |
| `visualizar` (via) | 29–38 consultas, 81–86 ms |
| Página de edição (cartões) | 199 consultas, 712 ms, 385 KB |

---

## 2. NOVO

### 2.1 Modelo de emissão: rascunho → minuta; emissão → PDF/A imutável
- Rascunho: **minuta** gerada na hora (`previa`, `views.py:968-990`) com marca d'água "MINUTA",
  texto editado incluído (`regioes_vigentes`), `?tipo=oficio|justificativa|todos` (um PDF só).
  Não é arquivada nem é PDF/A (e não é *tagged*).
- **Emitir** (`services.emitir`, `services.py:805-846`): valida prontidão, muda para Emitido,
  grava o **instantâneo** dos dados (`dados_do_oficio` + texto editado em `dados["edicao"]`) num
  `Documento` por tipo (ofício; justificativa só se houver texto), versão = última + 1, e publica
  `viagens.documento.gerar` na **outbox**. O worker (`assinantes.py:15-40`) gera **PDF/A-2a**
  (`documentos/pdf.py:gerar_pdf`, identificador estável, *tagged*, metadados título/assunto/autor/
  palavras-chave), grava SHA-256/tamanho e registra no histórico.
- Emitido é **imutável**: não há "emitir nova versão"; corrigir = **retificar** (volta a rascunho
  marcado, revoga a via) e emitir de novo (v2). `reabrir` (gestor) existe só no serviço (ver
  `oficios-resumo.md` RF1).
- DOCX (`baixar_docx`, `views.py:993-1016`): emitido → a via (instantâneo, `oficio-NN-AAAA-vN.docx`);
  rascunho → minuta (`minuta-oficio-NN-AAAA.docx`); conversor HTML→DOCX próprio (`documentos/docx.py`).
- Abrir/baixar PDF emitido: `GET documentos/<id>/` (`views.py:944`; via assinada vigente por
  padrão, `?versao=original`, `?baixar=1`; `X-Content-SHA256`).

### 2.2 Baixar documentos (`views_pacotes.baixar_oficio`, `pacotes.py:52-132`)
GET devolve a lista em JSON ao abrir a janela; itens Ofício, Justificativa (se há texto), termos
ativos ligados (um por documento do termo); estados "Minuta" / "PDF emitido · vN" / "Assinado" /
"Gerado na hora"; PDF/DOCX; assinado/original; separados (ZIP) / um PDF (pikepdf). Cancelado →
"Reative o ofício antes de baixar documentos." (paridade). Medido: JSON 18–186 ms (9–11 consultas);
pacote do emitido 54 ms (ZIP) / 152 ms (PDF único); do rascunho ~1 s (minutas).

### 2.3 Vias assinadas (`assinados.py`, `views_assinados.py`)
Anexar (`assinados/<tipo>/<pk>/`) por janela própria (arrastar/soltar, nome e tamanho), validação
(.pdf, ≤ 15 MB, `%PDF-`), **conferência após o envio** (leitura de assinatura, CN, carimbo,
número/protocolo — `documentos/leitura.py`) mostrada em mensagens e guardada na via; trocar
(anterior revogada, nunca apagada); remover (`assinados/via/<id>/remover/`); abrir
(`assinados/via/<id>/`). Histórico de negócio registra anexada/removida. Retificar/reabrir revoga.

### 2.4 Editor (ADR 0018, `views_editor.py`, `_editor.html`, `editor-documento.js`, `editores.js`)
Bloco único na seção Documentos da folha do rascunho: índice com **miniaturas** (ofício e
justificativa), folhas inteiras empilhadas, barra comum (Atualizar, Baixar, Texto/PDF; N/I/S,
limpar, tamanho 8–18 pt, cor, listas, alinhamentos, **quebra de página**, **tabela** com largura e
altura de linha, **Texto pronto** (+ guardar seleção), desfazer/refazer, voltar o **bloco** ao
original, voltar ao **modelo**, **Histórico do texto** com restaurar — cada restauração é nova
versão). Estado (`estado/`): versões, regiões "desatualizadas" em relação ao modelo, pendências,
**presença** (cache, 90 s), contagem de **páginas** (`paginas/`, WeasyPrint). 5 **campos
vinculados** (data, protocolo, motivo, instituição do custeio, justificativa — `documentos/campos.py`).
Emitido/leitor: somente leitura.

### 2.5 Conteúdo impresso (`viagens/documentos/oficio.html`, `justificativa.html`)
Mesma estrutura do ofício legado (tabelas, roteiro de ida/retorno ou **por trechos** no
bate-volta, transporte, custos, motivo, declaração, assinatura, destinatário, rodapé), com
diferenças em §3 (D20–D29). Justificativa: título **"JUSTIFICATIVA — OFÍCIO Nº N/AAAA"**, linha de
referência (protocolo · destinos · saída), texto, **"<cidade do destinatário>, <data do ofício>."**,
assinante.

### 2.6 Medições (NOVO, PREVIEW)
| Medida | Valor |
|---|---|
| `gerar_pdf` ofício (frio / quente) | 4,7 s / 2,8 s (12 servidores; 2 páginas) |
| `gerar_pdf` justificativa | 1,2 s |
| Minuta via HTTP: ofício / justificativa / todos | 1,7–6,2 s (frio) / 0,6–1,0 s / 1,6–1,8 s — **sem cache**: cada clique em "PDF" refaz |
| DOCX rascunho / emitido | 0,41–0,47 s / 0,2–0,28 s |
| Folha do editor / estado / páginas | 94 ms (708 frio) / 61 ms / **0,4–2,1 s** |
| Abrir PDF emitido | 27–47 ms, 8 consultas |
| Emissão → PDF pronto | assíncrono (worker); no semeio, mediana 24,5 s com 4 workers em lote |
| PDF emitido | **PDF/A-2a** (pdfaid 2/A, OutputIntent), *tagged*, `/Lang pt-BR`, metadados completos, ~165 KB (fontes Liberation Serif subconjunto via fontTools) |
| Folha de edição do rascunho | 33 consultas (o próprio middleware avisa "Orçamento SQL excedido: 29/25"), 468–793 ms, 184 KB |

---

## 3. Matriz LEGADO × NOVO

| # | Item | LEGADO (evidência) | NOVO (evidência) | Status |
|---|---|---|---|---|
| D1 | Ver o documento antes de emitir | folha no cartão; PDF só sem pendência | folha editável + **minuta** PDF com marca d'água a qualquer momento (`views.py:968`) | ✅ ➕ |
| D2 | Ler não muda estado | 1ª visualização **emite** v1 e muda status (🐞 `document_generation.py:50`) | minuta não grava; emitir é ação explícita com revisão | ➕ |
| D3 | Emissão | síncrona, por visualizar/baixar | "Revisar e emitir" → outbox/worker (`services.py:805`) | ✅ ➕ |
| D4 | PDF/A-2a | sim | sim + metadados (assunto, palavras-chave, autor) | ✅ ➕ |
| D5 | Instantâneo imutável | via guardada; "dados de fora" congelados; mudança do documento gera nova via sozinha | instantâneo de **todos** os dados (`dados.py`), inclusive texto editado | ✅ ➕ |
| D6 | Versões | v1, v2… por "Emitir nova versão" ou mudança | v1, v2… por retificação + nova emissão | ⚠️ (semântica diferente; ver D14) |
| D7 | Data/autor da versão | "Versão N emitida em dd/mm" (e `emitida_por`) | gravados (`emitido_em`, `emitido_por`), **não exibidos** no resumo; só na `_documentos.html` órfã | ⚠️ |
| D8 | Formatos | PDF e DOCX (docxtpl do `.docx` oficial) | PDF e DOCX (HTML→DOCX próprio) | ✅ (🐞 F4 fidelidade) |
| D9 | Justificativa | PDF/DOCX; data fixada na 1ª emissão | PDF/DOCX; só se há texto; data = data do ofício | ⚠️ (F3) |
| D10 | Termos dentro do ofício | por servidor (PDF/DOCX/ZIP/PDF único) na página do ofício | módulo Termos; pacote do ofício inclui termos ativos | ⚠️ (decisão de modelo) |
| D11 | Baixar documentos (modal) | `dialogo_baixar` (`views.py:296`) | mesmo comportamento + lista em JSON ao abrir (`views_pacotes.py`) | ✅ ➕ |
| D12 | Baixar documentos com ofício cancelado | bloqueado ("Reative…") | idem (`views_pacotes.py:68-70`); mas **"Baixar em Word" e "Ver minuta" funcionam** no cancelado | ⚠️ |
| D13 | Nome dos arquivos | `oficio_01-2026_<carimbo>.pdf` | `oficio-NN-AAAA-vN.docx`, `minuta-oficio-…`; **minuta da justificativa sai como `minuta-156-2026.pdf`** (igual à do ofício, `views.py:988`) | ⚠️ 🐞 baixa |
| D14 | **Emitir nova versão** sem mudar o ofício (chefe/destinatário/modelo corrigidos) | sim (`_documento_inline.html:30-33`) | não há; só retificando (marca "Retificado" no papel) | ❌ (decidir) |
| D15 | Falha de geração | erro na hora (409 / mensagem) | 🐞 **documento fica "gerando" para sempre**: o `FALHOU` é gravado dentro do *savepoint* que a exceção desfaz (`assinantes.py:27-31` × `outbox.py:91`); sem ação "Gerar de novo" | 🐞 ❌ |
| D16 | Acompanhar a geração | — (síncrono) | `_documentos.html` com *polling* 2 s existe mas **não é incluída** em tela alguma; resumo estático | 🐞 |
| D17 | Assinado: anexar/trocar/remover/abrir | modal + página | janela + página + registro com ações | ✅ |
| D18 | Conferência do PDF assinado **antes** de anexar | prévia no modal (`documentos/views.py:93`) | só depois do envio (mensagens + nota no registro) | ⚠️ |
| D19 | "Assinado, mas os dados mudaram" | lista das mudanças | ofício congelado → nunca dispara (correto); texto da janela diz "Gerar o PDF continua gerando o documento atualizado" (falso para ofício, `dialogo_assinado.html:43`) | ✅ (⚠️ texto) |
| D20 | Abertura do ofício | "…através deste, solicito {assunto} e **medidas para** a concessão de diárias e **recursos para combustível**…" (`blocos.py:52-56`) | "…solicito {assunto} e a concessão de diárias e combustível…" — **texto oficial encurtado** por decisão de UI (`oficio.html:83-84`) | ⚠️ (decisão do dono) |
| D21 | Declaração do cartão | "…cientes da **necessidade de estar na posse** de cartão corporativo vigente **e apto para uso, no período do deslocamento**." (`blocos.py:64-68`) | "…cientes de que devem portar cartão corporativo vigente no deslocamento." (`oficio.html:164`) | ⚠️ (decisão do dono) |
| D22 | **Nº solicitação (Central de Viagens)** | preenchido da prestação (`docxtpl_context.py:524, 614`) | coluna **sempre vazia** (`oficio.html:92`); o campo existe (`models.py:1301`) | ❌ |
| D23 | **Ofício e protocolo do motorista** de fora | "Ofício do Motorista: N/AAAA" + "Protocolo do Motorista: …" (`docxtpl_context.py:431-442`) | **não impressos**, embora obrigatórios para emitir (`services.py:548-551`); `dados.py` só leva o nome | ❌ |
| D24 | Linhas vazias do transporte | sempre impressas (placa, motorista, combustível, viatura) | omitidas quando vazias; meio não oficial com detalhe entre parênteses | ✅ ➕ |
| D25 | Roteiro por trechos (bate-volta) | ida/retorno | "ROTEIRO POR TRECHOS" numerados | ➕ |
| D26 | Valor por extenso | só no DOCX | não impresso em nenhum formato; **a janela de revisão o anuncia como "o que vai no papel"** (`_resumo.html:61-64`) | 🐞 |
| D27 | Justificativa: local e data | "<sede da unidade>, <data por extenso>" | "**<cidade do destinatário>**, <data do ofício>." (`justificativa.html:49`) — unidade de Cascavel sai "CURITIBA – Pr." | 🐞 |
| D28 | Justificativa: título/referência | "Justificativa" | "JUSTIFICATIVA — OFÍCIO Nº …" + protocolo · destinos · saída | ➕ |
| D29 | Numeração de páginas | não | não; ofício de 2 páginas: a 2ª só tem assinatura + destinatário, sem identificação | ⚠️ (ambos) |
| D30 | Marca d'água de minuta | não existe | "MINUTA" diagonal — 🐞 **pintada por cima** da tabela da equipe: cobre dígitos de CPF e cargos (`oficio.html:32`, `justificativa.html:28`, sem `z-index`) | ➕ 🐞 |
| D31 | Minuta acessível | — | minuta **não marcada** (Tagged: no) | ⚠️ baixa |
| D32 | DOCX fiel ao PDF | DOCX do modelo oficial, 1 página | DOCX do emitido 144/2026 vira **2 páginas** (o PDF tem 1): margens/espaçamentos perdidos, destinatário órfão na 2ª página (LibreOffice) | 🐞 |
| D33 | Editor: formatação | barra completa + zoom + tachado + recuo | barra completa + tamanho/cor de fonte + texto pronto; sem zoom/tachado/recuo | ✅ |
| D34 | Editor: versões / restaurar / voltar ao modelo / bloco ao original | sim (editor completo) | sim (por região; restaurar cria versão) | ✅ |
| D35 | Editor: presença | sim (`api.py:284`) | sim (`views_editor.py:78`, 90 s) | ✅ |
| D36 | Editor: páginas | sim | sim (0,4–2,1 s por pedido) | ✅ |
| D37 | Editor: textos prontos | por campo (`api.py:394`) | menu + "guardar seleção" | ✅ ➕ |
| D38 | Editor: quebras e parágrafos extras **controlados** | pontos registrados + parágrafo extra | quebra livre (`data-acao=quebra`) + pontos `antes-roteiro`/`antes-assinatura` | ⚠️ |
| D39 | Editor: **campos vinculados** | ~22 (servidor, configuração, solicitação, datas, assinantes) | 5 (`documentos/campos.py`) | ⚠️ |
| D40 | **Modelos de texto** (textos-base por tipo, gestor) | `/documentos/modelos/` (`editor/modelos.py`) | inexistente; só textos prontos (`/cadastros/textos-prontos/`) e "voltar ao modelo" do código | ❌ |
| D41 | Editor no emitido | somente leitura até reabrir | somente leitura (a folha não é aberta: emitido não entra em `editar`) | ✅ |
| D42 | Desempenho da geração | síncrona 1–2,4 s (via em cache 60 ms) | worker assíncrono 1,2–2,8 s por documento; minuta **sem cache** 0,6–1,8 s por clique | ✅ (⚠️ minuta) |
| D43 | Desempenho da página | 199 consultas / 385 KB | 33 consultas (acima do orçamento 25) / 184 KB | ✅ (🐞 orçamento) |
| D44 | Miniaturas/folhas da seção 4 em captura de página inteira | — | miniaturas carregam (≈0,4 s) em ≥ 768; **as folhas não**: `pc-editor-documento` só é importado quando o bloco chega a 400 px da tela (`app.js:70-85`) — sem rolar, área cinza vazia sem barra | ⚠️ (não é defeito funcional; falta esqueleto) |

**Lacunas ❌:** D14 nova versão sem retificar (decidir) · D15 recuperação de falha · D22 nº de
solicitação · D23 ofício/protocolo do motorista · D40 modelos de texto.

---

## 4. Defeitos (NOVO) com reprodução

| ID | Defeito | Reprodução / evidência |
|---|---|---|
| F1 | **Geração que falha deixa o documento "gerando" para sempre** e sem erro | Numa transação desfeita: `Documento` com `dados` incompletos + `outbox.publicar` + `processar_lote(1)` → `documento.situacao = gerando`, `erro = ''`, outbox `pendente` (tentativa 1, `KeyError`). Após 8 tentativas a outbox vira `falhou`, o documento continua "gerando". Causa: `assinantes.py:27-31` grava `FALHOU` e relança; o *savepoint* de `outbox.py:91` desfaz a gravação |
| F2 | Marca "MINUTA" cobre o texto da tabela | `/viagens/oficios/256/minuta.pdf` (12 servidores): CPFs e "Assessor de Comunicação" cortados pela marca (captura `caps/res-doc/mm-zoom-1.png`) |
| F3 | Local da justificativa = cidade do **destinatário** e data do ofício | 144/2026 (unidade de Cascavel) imprime "CURITIBA – Pr., 02/10/2026." (`justificativa.html:49`) |
| F4 | DOCX perde a paginação do PDF | `oficio/244` DOCX → LibreOffice: 2 páginas, destinatário isolado; PDF: 1 página (`caps/res-doc/cmp-docx.png`) |
| F5 | Ofício/protocolo do motorista de fora exigidos mas não impressos | `services.py:548-551` × `dados.py` / `oficio.html:136-139` |
| F6 | "Valor por extenso" anunciado na revisão como impresso e não impresso | `_resumo.html:61-64` × `oficio.html` (nenhum `extenso`) |
| F7 | `_documentos.html` órfã: a única tela com *polling* da geração não é usada | `views.py:935`; nenhum `include` |
| F8 | Minuta da justificativa com o mesmo nome do ofício | `views.py:988` |
| F9 | Texto da janela de anexar diz que gerar continua "atualizado" (ofício é congelado) | `templates/componentes/dialogo_assinado.html:43` |
| F10 | Folha de edição acima do orçamento SQL (29–33/25) | log do middleware ao abrir `/viagens/oficios/256/editar/` |

### 4.1 Achado visual anterior — miniaturas vazias em captura de página inteira
**Diagnóstico:** em 1440, as miniaturas do índice **carregam** (2 pedidos `…/folha/?miniatura=…`,
~0,3–0,4 s; após `networkidle` o iframe tem corpo e `scale(0.131)`); durante o carregamento a
miniatura nova fica `visibility:hidden` (`editores.js:36-58`), então uma captura feita no
`DOMContentLoaded` a mostra vazia. Abaixo de 768 o índice começa **fechado por desenho**
(`editores.js:185`). O que aparece **realmente vazio** numa captura `full_page` sem rolagem são
as **folhas** dos editores: `pc-editor-documento` é importado só quando `[data-editores]` chega a
400 px da janela (`app.js:70-85`); sem rolar, o iframe fica `hidden`, sem `src`, e a barra não
existe — sobra uma área cinza com "Página 1 Ofício…" e "Página 2 Justificativa…". Ao rolar até
`#minuta`, as duas folhas carregam (1464 px e 1167 px de altura, "Como o modelo").
**Conclusão:** lazy-load, não defeito funcional. Mas há uma fragilidade de UX: não há esqueleto
nem altura reservada (a página "pula" ao carregar; numa conexão lenta a pessoa vê um quadro cinza
vazio). Proposta em P2-14. Para QA: capturas da seção 4 devem rolar até `#minuta` e esperar
`[data-salvo]` ≠ "Carregando…" (`/home/claude/tools/rd_novo_folhas.py`).

---

## 5. Propostas de superação

### P0
1. **Falha de geração visível e recuperável** (F1/D15/D16): o assinante grava `FALHOU` fora do
   *savepoint* (ou a outbox chama um `ao_falhar` depois do rollback) e só relança para o
   *backoff*; a seção Documentos (resumo e folha) mostra "Falhou: <motivo curto>" com **"Gerar de
   novo"** (serviço idempotente, publica nova mensagem); `gerando` faz *polling* (reaproveitar
   `_documentos.html`) até pronto. Teste: assinante que lança → documento `falhou` com `erro`.
2. **Conteúdo obrigatório do papel** (D22/D23/F5): imprimir "Ofício do motorista: N/AAAA ·
   Protocolo: …" no bloco de transporte e o **nº da solicitação** por servidor quando houver
   (na emissão ainda não há prestação: decidir com o dono se a solicitação entra na v2 ou se a
   coluna sai do modelo).
3. **Marca d'água atrás do conteúdo** (F2): `z-index:-1` (ou cor com transparência) e teste
   visual que compara o texto extraído da minuta com o do emitido (mesmas palavras).
4. **Justificativa com local/data corretos** (F3): sede da unidade emissora + data por extenso
   da emissão (como o legado), com a data fixada no instantâneo.
5. **Textos oficiais** (D20/D21): voltar aos textos do modelo oficial **ou** registrar a
   decisão do dono em `decisions.md`; hoje é mudança de conteúdo de documento oficial sem decisão
   registrada.

### P1
6. **Modelos de texto do gestor** (D40): tela para os textos-base (abertura, declaração, fecho,
   título da justificativa) com prévia, versão e quem alterou; o instantâneo da emissão guarda o
   texto usado.
7. **Nova via sem retificar** (D14): para mudanças "de fora" (assinante substituto, destinatário,
   correção de modelo), ação do gestor "Emitir nova via (v2) com os mesmos dados" que **não**
   marca "Retificado" — ou decisão explícita de não oferecer.
8. **Conferência antes de anexar** (D18): a janela lê o PDF no envio do arquivo (endpoint de
   prévia) e mostra assinantes/avisos antes de "Anexar"; ajustar o texto F9.
9. **DOCX fiel** (F4/D32): teste que converte o DOCX (LibreOffice) e exige o mesmo número de
   páginas do PDF para os ofícios de demonstração; ajustar margens/espaçamentos do conversor.
10. **Versão com data e autor** (D7): "v1 · emitido em 02/10/2026 às 10:24 por Fulano · SHA-256
    …" no resumo e na folha.
11. **Minuta com cache** (D42): cache por impressão dos dados + regiões (a chave já existe:
    `assinados.impressao`) — o botão PDF deixa de custar 0,6–1,8 s a cada clique.

### P2
12. **Páginas numeradas e cabeçalho de continuação** (D29): "Ofício nº 156/2026 — página 2 de 2"
    a partir da 2ª página; evitar página só com assinatura (`break-inside: avoid` no bloco final
    junto da declaração).
13. Valor por extenso (F6/D26): imprimir (como o DOCX legado) ou tirar da revisão.
14. **Esqueleto das folhas** (D44): altura A4 reservada + "Carregando o documento…" no lugar da
    folha até o editor importar; barra visível desde o início (desligada).
15. Minuta *tagged* (D31) e nome de arquivo por tipo (F8); orçamento SQL da folha ≤ 25 (F10).
16. Campos vinculados extras (D39) só se o dono quiser editar cadastro pela folha (o legado
    permitia mudar CPF/cargo do servidor pelo documento — risco de efeito colateral).

---

## 6. Critérios de aceite (QA)
- Emitir um rascunho de demonstração com worker ligado: PDF/A-2a pronto em ≤ 10 s; `pdfinfo`
  Tagged=yes; XMP `pdfaid:part=2`, `conformance=A`; título "Ofício N/AAAA".
- Assinante forçado a falhar → documento `falhou` com mensagem; "Gerar de novo" leva a `pronto`.
- Texto extraído (`pdftotext`) do PDF emitido contém: ofício/protocolo do motorista quando de fora;
  nº de solicitação (se decidido); local da justificativa = sede da unidade; textos de abertura e
  declaração conforme decisão registrada.
- Minuta: texto extraído igual ao do emitido (menos "MINUTA"); marca não cobre texto (teste visual
  de recorte da tabela).
- DOCX do emitido convertido tem o mesmo número de páginas do PDF (ofícios de 1 e 2 páginas).
- Baixar documentos: PDF/DOCX × assinado/original × separados/único com 1, 2 e 3+ itens; cancelado
  bloqueia **todos** os downloads de forma coerente (ou nenhum).
- Anexar via: prévia da conferência antes de confirmar; trocar mantém a anterior revogada; remover
  volta ao original; retificar revoga.
- Capturas da seção 4 roladas até `#minuta`: barra, miniaturas e folhas visíveis em 1440; índice
  fechado e folhas visíveis em 390; sem rolagem horizontal; axe sem violações.

## 7. Evidências desta análise
- Geração e medição: shell do LEG (`gerar_documento` com e sem cache) e do NOVO (`gerar_pdf`,
  test client em `minuta.pdf`, `documento/*.docx`, `baixar/`, `folha/`, `estado/`, `paginas/`);
  falha do assinante reproduzida dentro de transação desfeita (nada gravado no PREVIEW).
- PDFs/DOCX comparados com `pdfinfo`, `pdffonts`, `qpdf --qdf` (XMP), `pdftotext -layout`,
  LibreOffice (DOCX→PDF) e `pdftoppm`.
- Scripts: `/home/claude/tools/rd_legado.py`, `rd_novo_miniaturas.py`, `rd_novo_folhas.py`.
- Capturas: `/home/claude/caps/res-doc/{legado-cartao-oficio,novo-minuta-256-1440,crop-semrolar,cmp-docx,cmp-minuta,mm-zoom-1}.png`.
- Efeito no LEGADO (cópia descartável): a geração do ofício de teste criou a via v1 e artefatos
  (comportamento do próprio legado); recriável de `/tmp/legado.sql`.
