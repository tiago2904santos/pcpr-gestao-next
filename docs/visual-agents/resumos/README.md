# Resumos — revisão e padronização (14/10/2026)

Registro da missão de transformar as janelas de resumo em uma família coerente.
Baseline e evidências: `docs/visual-agents/evidencias/resumos-padronizacao-20261014/`
(capturas do diálogo inteiro, dados sintéticos do PREVIEW local, 1440 / 1024 / 390 px).
Roteiro de captura reproduzível: `scripts/capturar_resumos.py`.

## 1. Inventário

Todos os resumos vivem em Viagens e abrem como janela (`dialog#dialogo-resumo`, HTMX)
sobre a lista do próprio documento. Não há página de detalhe (ADR 0017).

| Página | Rota do fragmento | Lista que abre | Template | Montagem |
|---|---|---|---|---|
| Ofício | `/viagens/oficios/<pk>/resumo/` (+ `?resumo=<pk>` e revisão `?revisar=1`) | Ofícios, Roteiros (vínculos), folha | `oficios/_resumo.html` + 12 parciais | `views._contexto_resumo` |
| Ordem de serviço | `/viagens/ordens/<pk>/resumo/` | OS | `componentes/resumo_documento.html` | `resumo_listas.da_ordem` |
| Termo de autorização | `/viagens/termos/<pk>/resumo/` | Termos | `componentes/resumo_documento.html` | `resumo_listas.do_termo` |
| Plano de trabalho | `/viagens/planos/<pk>/resumo/` | Planos | `componentes/resumo_documento.html` | `resumo_listas.do_plano` |
| Viagem | `/viagens/viagens/<pk>/resumo/` | Viagens | `componentes/resumo_documento.html` | `resumo_listas.da_viagem` |
| Roteiro | `/viagens/roteiros/<pk>/resumo/` | Roteiros | `componentes/resumo_documento.html` (antes `roteiros/_resumo.html` + 4 parciais) | `resumo_listas.do_roteiro` |

Fora do escopo, com motivo:
- **Justificativas** não têm resumo próprio: a justificativa é parte do ofício e aparece
  na narrativa do resumo do ofício; a tela delas é um diálogo de edição de texto.
- **Eventos, Coffee, Imprensa, Palestras e Publicações**: as rotas `<pk>/` são folhas de
  edição (`folha.html`), equivalentes ao cadastro, não resumos.
- **UI Lab** (`_dossie.html`, `oficio_direcoes.html`): vitrines históricas do piloto.

Estados que mudam a apresentação, cobertos nas capturas:

| Página | Estados capturados |
|---|---|
| Ofício | rascunho com pendência (260), emitido (258), emitido com via assinada (255), cancelado (221) |
| OS | gerada e assinada (5), rascunho com 8 servidores (2), cancelada (4) |
| Termo | 1 de 6 assinados (1), rascunho sem servidor (7), cancelado (6) |
| Plano | gerado (1), vazio (4), cancelado (3) |
| Viagem | em preparação com documentos (1), vazia (5), cancelada (3) |
| Roteiro | com ofício (1), 6 trechos (60), cancelado (71) |

Permissões que mudam a apresentação: documentos (PDF, DOCX, via) só para quem edita o
registro (`pode_ver_documento_*` = `pode_editar_*`; cancelado nunca); histórico para quem vê
(`pode_ver_historico_*`); cancelar/reativar/excluir conforme `pode_cancelar_*`/`pode_excluir_*`;
roteiro: `change_roteiro`.

## 2. Matriz comparativa (antes)

Legenda: **A** existe e está adequado · **M** existe, precisa melhorar · **F** ausente,
embora aplicável · **—** não se aplica. Entre parênteses, a posição.

| Componente | Ofício | OS | Termo | Plano | Viagem | Roteiro |
|---|---|---|---|---|---|---|
| Identidade (rótulo + número) | A | A | A | A | A | A |
| Contexto do cabeçalho | M ("Resumo da viagem" — colide com o resumo da Viagem) | A | A | A | A | A |
| Selo de situação com forma (○ ✓ ✕) | A | M (ponto genérico; "Assinada" repete a via) | M (ponto genérico) | M (ponto genérico) | M (ponto; "Documentos gerados" sem ✓) | M (sem selo de situação; cancelado sem ✕) |
| Complemento (ícone + período · contagem · protocolo) | A | M (texto solto, data curta) | M (texto solto, data curta) | M (texto solto) | M (só destinos; período fora do cabeçalho) | A |
| Formato de data | A (dd/mm/aaaa — dd/mm/aaaa) | M (26/10 a 27/10/2026) | M (idem) | M (26/10/2026 a 27/10/2026) | M (idem) | A |
| Alerta de cancelamento (data + motivo) | A (topo) | F (dados existem) | F | F | F | — (sem motivo no modelo) |
| Conferência / pendências | A (topo, só quando bloqueia) | M (fim; "Pronta para gerar" até na cancelada) | M (fim; "Pronto" na cancelada) | M (fim) | M (fim) | — |
| Documentos (estação documental) | A (topo do corpo) | F (PDF/DOCX/via só no menu) | F (6 termos e vias só no menu/registro) | F (PDF/DOCX só no menu) | — (não emite; vínculos cobrem) | — |
| Via assinada na peça | A | F (selo "Assinada" solto no cabeçalho) | F (contagem como dado) | — (plano não tem via) | — | — |
| Registro (dados) | M (título "Registro institucional"; ok) | M (repete período e "gerado em" do cabeçalho) | M (repete período, destinos e contagem de documentos; viatura como texto) | M (repete período) | M (período fora do cabeçalho) | F (sede, servidores, observações existem; observações cortadas no rodapé) |
| Equipe / efetivo (01) | A (equipe + transporte) | A | M (viatura fora dos cartões) | A (efetivo) | A (destinos, equipe da OS) | — |
| Percurso (02) + Diárias | A | — | — | — (sem trechos; diárias como dado) | — | A |
| Vínculos | F (OS/termos/planos só no menu) | A | A | A | A (documentos da viagem) | A (mas como 01, antes do percurso) |
| Cartão de vínculo clicável inteiro | — | A | A | A | M (não clicável) | A |
| Rodapé: ler o documento (esquerda) | A (Ver o PDF / Ver minuta) | F | F | F | — | — (observações no lugar) |
| Rodapé: Mais ações (⋮ da lista) | A (sem o que está à vista) | M (repete Abrir e PDF) | M (repete Abrir) | M (repete Abrir e PDF) | M (repete Abrir) | F (o menu da lista existe) |
| Ação principal | A (Abrir/Revisar e emitir/Editar; nada se não edita) | M (lápis e "Abrir" até na cancelada e sem permissão) | M (idem) | M (idem) | M (idem) | A |
| Histórico | A (Histórico de documentos, no menu) | F (a folha tem; o menu não leva) | F | F | A (menu → folha) | — |
| Grade do corpo | M (áreas nomeadas, faixas vazias; DOM fora da ordem visual) | M (margem negativa para desfazer faixa vazia) | M | M | M | M |
| Rodapé no celular | A | M (Mais ações sozinho à direita) | M | M | M | M (observações ocupam o rodapé) |

## 3. Contrato de organização

Ordem fixa das regiões; seção que não se aplica não é renderizada e não deixa vão.

1. **Cabeçalho** (fora da rolagem): identidade · contexto "Resumo do/da <documento>"
   (revisão do ofício: "Revisar antes de emitir") · título (destinos; viagem: título) ·
   selos — o primeiro é a situação documental com forma (○ rascunho, ✓ emitido/gerado,
   ✕ cancelado); os seguintes são circunstâncias (tipo, prazo, tempo) como texto ·
   **faixa de fatos** (revisão de 14/10, no lugar do antigo cartão Registro): rótulo em
   caixa-alta com ícone, valor numa linha e nota opcional, separados por filetes — o
   período primeiro (nota: trechos, horário ou a origem do período) e, por tipo: ofício
   equipe, data e protocolo; OS equipe e necessidade; termo equipe e evento; plano efetivo,
   programa e coordenação; viagem destino (quando o título não o diz) e documentos;
   roteiro sede, servidores no cálculo e "bate-volta" quando for.
2. **Avisos** (topo do corpo, só quando existem): revisão (ofício), conferência com o que
   falta (cada item leva à folha, na seção), cancelamento com data e motivo.
3. **Documentos** (quando o registro emite e quem vê pode abri-lo): peças correntes, cada
   uma com PDF e via assinada na própria peça (várias peças: o estado da via alinhado numa
   coluna); sem documento, o estado "minuta disponível" (`?previa=1`, não fixa a geração).
   Cancelado ou quem só lê: a seção não existe (a OS assinada mostra "Assinada" no cabeçalho
   para quem não vê os documentos).
4. **Narrativa** (entre os avisos e os documentos): o porquê em texto corrido e maior,
   sem cartão, com o filete dourado — motivo e justificativa (ofício; na revisão, também o
   estado da justificativa, quem assina e o destinatário), motivo (OS, viagem), observações (roteiro),
   atividades como fichas (plano). Custeio e porte de arma saíram do resumo (estão na folha
   e no documento).
5. **01, 02, 03…**: blocos numerados do conteúdo próprio — pessoas e recursos, percurso
   com diárias (ofício e roteiro ao lado do percurso; plano no mesmo painel, depois do
   efetivo — as diárias não contam na numeração), e por último os **vínculos**.
6. **Rodapé** (fora da rolagem): à esquerda, ler o documento atual (Ver o PDF / Ver minuta —
   a via assinada abre na peça); à direita, Mais ações (o ⋮ da lista menos o que já está à
   vista) e a ação principal (Abrir/Editar com lápis só para quem edita; para quem só lê,
   Abrir com olho, secundário). Sem nada a fazer, não há rodapé.

Exceções legítimas (mantidas de propósito):
- **Ofício**: continua com template próprio (`oficios/_resumo.html`) porque tem revisão antes
  de emitir, retificação, regeneração com polling, justificativa e histórico de documentos;
  mas usa as mesmas peças comuns (aviso de cancelamento, conferência, complemento, diárias,
  cartões de vínculo) e a mesma ordem.
- **Roteiro**: não emite documento (sem Documentos nem "ler" no rodapé); o cancelado não
  guarda data nem motivo (o aviso diz o efeito) e não tem botão de abrir, porque a folha do
  roteiro cancelado redireciona — reativa-se pelo Mais ações.
- **Viagem**: não emite documento próprio; o bloco final agrupa os documentos dos outros
  módulos por tipo (cartões não clicáveis: não há lista filtrada por viagem para onde levar).
- **Plano**: sem via assinada (o modelo não prevê).
- **Termo**: várias peças (uma por servidor, genérico, viatura), cada uma com a sua via;
  "ler" abre todos em um PDF.
- **Percurso longo** (6+ trechos, ofício e roteiro): Diárias ao lado do percurso, na altura
  dele; com menos trechos, Diárias abaixo, na largura toda.

## 4. Andamento por página

Estados: Descoberta · Comparada · Implementada · Validada visualmente · Validada funcionalmente.

| Página | Estado | Observações |
|---|---|---|
| Ofício | Validada funcionalmente | contexto "Resumo do ofício"; ordem do DOM = ordem visual; conferência e cancelamento nas peças comuns; novo bloco 03 "Documentos vinculados" (antes só no menu) |
| OS | Validada funcionalmente | estação documental com via na peça; minuta por `?previa=1` (não fixa a geração); cancelamento com motivo; histórico no menu; motivo em linha única (aprovado) |
| Termo | Validada funcionalmente | uma peça por termo, cada uma com a sua via; viatura entre os cartões ("Equipe e transporte"); origem do período como nota do período |
| Plano | Validada funcionalmente | peça do plano / minuta; cancelamento; histórico no menu |
| Viagem | Validada funcionalmente | período no cabeçalho; contagens no singular/plural corretos; conferência no topo |
| Roteiro | Validada funcionalmente | migrado para a casca comum; sede e servidores no cabeçalho, observações na narrativa; percurso 01 antes dos ofícios 02; menu da lista no rodapé; aviso de cancelado |

"Validada funcionalmente" = fragmento 200 nos 19 casos, sem erro de console nem rolagem
horizontal em 1440/1024/390 (`relatorio.json`), permissões conferidas com o gestor (`demo`)
e com o perfil CONSULTA (`consulta.demo`), 11–20 consultas SQL por resumo (orçamento 25),
testes das telas afetadas verdes e `gestao/viagens/tests/test_resumos_padrao.py` (documentos
só para quem edita, lápis × olho, minuta sem fixar a geração, cancelamento, formulários do
menu existentes na lista, roteiro cancelado sem folha, vínculos do ofício).

## 6. Revisão independente (resumo)

Três revisores (UX, cético, acessibilidade; axe sem violações nos 16 estados testados).
Corrigido: `mark_safe` na tag do complemento (bandit, quebraria o CI); falta de testes;
orçamento de consultas do ofício (vínculos numa consulta só, UNION); rodapé da OS lendo a
via desatualizada; viagem cancelada pedindo para gerar documentos; contagens "0 …";
"documentos" invisíveis contados no termo cancelado; DOCX da OS não gerada no menu do
resumo (fixaria a geração); peças do termo desalinhadas; "·" solto na quebra do
complemento; complemento lido sem separação pelo leitor de tela; nome da janela só
"Resumo" (agora o título com o número); `role="status"` na conferência (agora seção com
título); animação infinita no aviso (agora para); links de nova aba sem aviso e
"Ver minuta" com nome diferente do texto (ofício); "Anexar via assinada" repetido sem
contexto; "Carregando o resumo do ofício" em todo tipo; `aside` redundante em Diárias;
rodapé vazio do roteiro para quem só lê; regra de quebra do percurso vazando para outras
telas; componentes novos fora do UI Lab.

Mantido de propósito (decisão do usuário ou fora do escopo):
- "Ver minuta" no cartão e no rodapé: desenho aprovado do ofício, referência da família.
- Ofício cancelado sem botão de abrir; selo do termo pela contagem de vias (o termo não tem
  estado "gerado"); roteiro ativo sem selo de situação (a lista também não tem).
- "Excluir roteiro" no menu sem checar `delete_roteiro` (igual à lista; o serviço confere).

## 5. Componentes consolidados

| Peça | Usada por | Substitui |
|---|---|---|
| `componentes/resumo_documento.html` (casca) | OS, termo, plano, viagem, roteiro | grade de áreas nomeadas + margem negativa; `roteiros/_resumo*.html` |
| `componentes/resumo_cancelamento.html` | todos | alerta próprio do ofício; ausência nos demais |
| `componentes/resumo_conferencia.html` | todos | `oficios/_resumo_conferencia.html`, `roteiros/_resumo_conferencia.html`, `componentes/resumo_pendencias.html` |
| `componentes/resumo_fatos.html` + `resumo_fato.html` (ofício: `oficios/_resumo_fatos.html`) | todos | cartão Registro (`componentes/resumo_dados.html`, `oficios/_resumo_registro.html`), `oficios/_resumo_periodo.html`, `roteiros/_resumo_periodo.html` |
| `componentes/resumo_narrativa.html` + `resumo_narrativa_item.html` | todos | motivo/justificativa/observações cortados dentro do Registro |
| `componentes/resumo_documentos.html` + `peca_documental.html` | OS, termo, plano | PDF/DOCX/via só no menu |
| `componentes/resumo_diarias.html` | ofício, roteiro, plano | dois blocos de diárias quase iguais; "Diárias: R$ …" solto no Registro do plano |
| `componentes/resumo_rodape.html` | OS, termo, plano, viagem, roteiro | rodapés com "Abrir" duplicado no menu |
| filtro `periodo_resumo` / `periodo_do_resumo` | todos | quatro formatos de período |
| UI Lab: "Resumo (casca comum)" (`ui_lab/_resumo_comum.html`) | vitrine | — |

Removidos depois de conferir que não há consumidores (templates, Python, testes, UI Lab):
`oficios/_resumo_conferencia.html`, `roteiros/_resumo.html`, `roteiros/_resumo_conferencia.html`,
`roteiros/_resumo_oficios.html`, `roteiros/_resumo_periodo.html`, `roteiros/_resumo_situacao.html`,
`componentes/resumo_pendencias.html` e a regra CSS `.prontidao-documental--resumo-neutro`.
