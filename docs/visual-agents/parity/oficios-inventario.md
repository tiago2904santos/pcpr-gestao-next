# Inventário — área de Ofícios (LEGADO × NOVO)

> Agente 1 — Legacy/Parity Analyst · 06/10/2026. Complementa `oficios-lista.md` (detalhe da
> lista) e `docs/parity/oficio.md` (regras do recorte vertical — parte das regressões listadas lá
> já foi resolvida no NOVO; esta tabela reflete o código de hoje).
> Sem dados reais: exemplos fictícios.

Legenda: ✅ equivalente · ⚠️ parcial/diferente · ❌ falta no NOVO · ➕ só no NOVO ·
— não se aplica.

Caminhos: **LEG** `viagens_oficios/urls.py` (montado em `/viagens/oficios/`), salvo indicação;
**NOVO** `gestao/viagens/urls.py` (montado em `/viagens/`).

## 1. Páginas e rotas

### 1.1 Lista, criação e leitura
| Página / rota LEGADO | Função | NOVO | Situação |
|---|---|---|---|
| `GET /viagens/oficios/` (`lista`) | lista com situações, busca, filtros, menu ⋮ | `GET /viagens/oficios/` (`views.lista`) | ⚠️ ver `oficios-lista.md` |
| `GET /viagens/oficios/exportar/` | XLSX do recorte | `GET /viagens/oficios/exportar/` | ✅ (situação "Arquivado" falta) |
| `POST /viagens/oficios/criar/` (+ `next`, + viagem) | cria rascunho numerado e abre o cadastro | `POST /viagens/oficios/novo/` | ✅ (sem reaproveitar rascunho vazio) |
| `GET\|POST /viagens/oficios/novo/` | GET volta à lista; POST cria e edita | idem (GET → lista) | ✅ |
| — (a leitura era a própria edição) | — | `GET /viagens/oficios/<pk>/resumo/` (janela de resumo, HTMX) e `?resumo=<pk>` na lista | ➕ |
| — | — | `GET /viagens/` painel (pendentes, próximos, indicadores) | ➕ |
| `GET /viagens/oficios/<pk>/documento/` | endereço antigo → `editar#documento-oficio` | — | — (redirecionamento histórico) |

### 1.2 Cadastro / edição (uma página com seções)
| LEGADO (`editar`, `form.html`) | NOVO (`editar`, `oficios/editar.html`) | Situação |
|---|---|---|
| Seção **Dados e viajantes**: número (editável), data, protocolo, origem do protocolo, motivo + modelo (com marcadores `{destino}`, `{periodo}`… substituídos), custeio (+ instituição), equipe (picker com unidade), motorista (servidor da equipe **ou** manual com ofício nº/ano e protocolo de origem — `oficios-do-motorista` sugere), viatura cadastrada ou placa/modelo/combustível/tipo manuais, porte de arma, servidores do **termo de autorização** | Seção **1 Identificação** (dados, equipe, transporte): número, data, protocolo, origem, marcador (Retificado/Complementar), motivo + texto pronto, custeio, equipe (HTMX adicionar/remover/definir motorista), motorista externo (servidor ou manual com RG/CPF/cargo/unidade), viatura sugerida pela equipe ou "outro transporte", porte | ⚠️ falta "ofício/protocolo de origem do motorista" e a sugestão `oficios-do-motorista`; termos saíram para o módulo Termos |
| Seção **Roteiro e diárias**: editor de roteiros embutido; vincular roteiro existente (busca dos 200 mais recentes); diárias do ofício | Seção **2 Roteiro**: itinerário (sede, destinos, trechos, bate-volta, rota/mapa), "usar um roteiro cadastrado" (cópia), diárias (`secao_diarias`) | ⚠️ cópia em vez de vínculo (ADR 0015) |
| Seção **Justificativa**: modelo + texto; obrigatória ao finalizar se dentro do prazo | Seção **3 Justificativa de prazo** (só quando exigida/preenchida) | ✅ |
| Seção **Documentos**: ofício e justificativa em visualizador embutido (PDF/editor), termos por servidor (PDF/DOCX, ZIP, PDF único), painel **"Dados para o eProtocolo"** (campos com Copiar) | Seção **4 Documentos**: conferência/prontidão, editores do ofício e da justificativa no visualizador (ADR 0018), minuta, DOCX, emissão | ⚠️ painel do eProtocolo ❌; termos ⚠️ (módulo próprio) |
| Botões: Voltar · **Salvar rascunho** · **Finalizar Ofício** (data final = hoje se não mudou; pendências viram mensagens) | Salvar · **Revisar e emitir** (`?revisar=1` abre a janela de revisão com destinatário, assinante, valor por extenso) · menu (ver minuta, histórico, duplicar, excluir) | ✅ ➕ |
| **Autosave** do rascunho (`POST <pk>/autosalvar/`, não finaliza, não mexe em número/data, não abre protocolo) | `POST oficios/<pk>/autosave/` (concorrência por `versao`) | ✅ |
| Avisos pós-salvar: protocolo repetido em outro ofício, motorista não condutor autorizado da viatura, conflitos de agenda (5 + "e mais N"), diárias "R$ … para N servidores" | conflitos de agenda como pendência não bloqueante (`services.py:507`); sem aviso de protocolo repetido nem de condutor | ⚠️ |
| Abertura automática do protocolo no eProtocolo ao salvar (`protocolo_services`) | ponto de extensão apenas (`assinantes.notificar_emissao`) | ❌ (decisão pendente) |
| Histórico (auditoria do ofício e dos blocos) no formulário | histórico de negócio na folha ("Ver o histórico") | ✅ |
| Ofício fechado (finalizado ou com PDF assinado) → somente leitura + **Reabrir para correção** (motivo; revoga assinatura) | emitido não é editável; **Editar (retificar)** (qualquer editor) ou **Reabrir** (gestor, motivo) | ✅ ➕ |

### 1.3 Ciclo de vida (ações)
| LEGADO (`POST <pk>/acao/<acao>/`) | NOVO | Situação |
|---|---|---|
| `finalizar` (via botão do formulário) | `POST oficios/<pk>/emitir/confirmar/` (gera PDFs pela outbox) | ✅ (Gerado+Finalizado = Emitido) |
| `reabrir` (motivo) | `POST oficios/<pk>/reabrir/` (gestor, motivo) | ✅ |
| `retificar` (liga/desliga marca) | `POST oficios/<pk>/retificar/` (emitido → rascunho retificado) | ⚠️ semântica diferente, melhor |
| `complementar` (liga/desliga marca) | campo `marcador` na folha | ⚠️ sem ação no menu |
| `cancelar` (motivo opcional) | `POST oficios/<pk>/cancelar/` (motivo obrigatório) | ✅ ➕ |
| `reativar` | `POST oficios/<pk>/reativar/` (gestor, justificativa) | ✅ ➕ |
| `arquivar` (rota sem UI) | `POST oficios/<pk>/arquivar/` e `/desarquivar/` + aba | ➕ |
| `excluir` (qualquer, protegido) | `POST oficios/<pk>/excluir/` (rascunho sem documento) | ✅ ➕ |
| — | `POST oficios/<pk>/duplicar/` | ➕ |

### 1.4 Documentos, assinatura e visualização
| LEGADO | NOVO | Situação |
|---|---|---|
| `POST <pk>/gerar/<tipo>/<formato>/` (ofício/justificativa, PDF/DOCX, `nova_versao`) | emissão gera PDF/A versionado; `GET oficios/<pk>/documento/<tipo>.docx` (D4) | ✅ |
| `GET <pk>/visualizar/<tipo>/` (PDF no cartão) | `GET oficios/<pk>/minuta.pdf` (marca d'água) e `GET documentos/<id>/` | ✅ |
| `GET <pk>/documento/folha/` (iframe do editor) | `GET oficios/<pk>/documento/<tipo>/folha/` + estado/salvar/restaurar/modelo/campos/original/páginas/presença/textos | ✅ ➕ |
| `documentos:editor_pagina 'oficio' <pk>` (página do editor; ícone da lista) | editor só dentro da folha | ⚠️ |
| `GET documentos/<uuid>/preview/` | `GET documentos/<id>/` | ✅ |
| `GET\|POST documentos/<uuid>/assinatura/` (anexar/remover PDF assinado; leitura de quem assinou) | `assinados/<tipo>/<pk>/[<chave>/]`, `assinados/via/<id>/` e `/remover/` | ✅ |
| `POST <pk>/baixar/` (modal Baixar documentos: itens, PDF/DOCX, assinado/original, separados/único) | `GET\|POST oficios/<pk>/baixar/` (mesmo modal, via resumo/folha) | ✅ |
| `GET <pk>/visualizar/termo/<servidor>/`, `POST <pk>/termos/<formato>/`, `<pk>/termos/<servidor>/<formato>/`, `<pk>/termos/todos/pdf/` | módulo Termos: `termos/do-oficio/<oficio>/`, `termos/<pk>/documento/<chave>.<fmt>`, `termos/<pk>/todos.<fmt>` | ⚠️ outra organização (termo é registro próprio) |
| `GET <pk>/oficios-do-motorista/?motorista=` (JSON) | — | ❌ |

### 1.5 Páginas secundárias
| LEGADO | NOVO | Situação |
|---|---|---|
| `GET\|POST /viagens/oficios/numeracao/` (gestor; piso por ano) | serviço `definir_piso` sem tela | ❌ |
| `GET /viagens/oficios/justificativas/` (lista por situação, modal de cadastro/edição com busca de ofício, excluir texto, baixar) + `nova/`, `<pk>/editar/`, `<pk>/excluir/`, `<pk>/baixar/` | `GET /viagens/justificativas/` (abas Pendentes/Preenchidas), `POST justificativas/<pk>/salvar/`, `justificativas/<pk>/baixar/` | ⚠️ sem "excluir texto" dedicado e sem criar a partir da lista (a justificativa é do ofício) |
| `GET\|POST /viagens/oficios/institucional/` (configuração: unidade, endereço, destinatário, assinantes de ofício/justificativa/OS/plano) | `/cadastros/configuracao/` (+ substituições do assinante por período) | ✅ ➕ |
| `/viagens/oficios/catalogos/<tipo>/…` (redireciona para institucional#assinaturas) | — | — |
| Cadastros `motivos-oficio` e `modelos-justificativa` (`viagens_cadastros`, padrão, busca) | `/cadastros/textos-prontos/` (tipos motivo, justificativa…; padrão, ativo) | ✅ (conferir marcadores `{…}`) |
| Importação do processo eProtocolo (`viagens_prestacoes`: `importar/`, `importar/oficio/<pk>/`, conferência `importacao/<pk>/` aplicar/descartar/desfazer/arquivo) | — | ❌ |
| Viagem (agrupador) etapa 3 → "Novo ofício" herdando motivo/unidade | `viagens/<pk>/novo/<tipo>/` | ✅ |
| Roteiro → criar ofício | `roteiros/<pk>/criar-oficio/`, `roteiros/<pk>/oficios/` | ✅ |
| Busca de ofícios para seletores (`api_buscar_oficios` dos termos) | `GET api/oficios/` (+ irmãos), `api/oficios/<pk>/para-termo/` | ✅ |

## 2. Modais e diálogos
| LEGADO | NOVO | Situação |
|---|---|---|
| Baixar documentos (`components/v32/dialogo_baixar.html`) | `componentes/dialogo_baixar.html` | ✅ |
| Anexar documento assinado (`components/v32/dialogo_assinado.html`) | `componentes/dialogo_assinado.html` | ✅ |
| Importar processo do eProtocolo (`viagens_prestacoes/_importar_dialogo.html`) + faixa de soltar | — | ❌ |
| Justificativa (cadastro/edição) na lista de justificativas (`_justificativa_modal.html`) | edição na própria lista de justificativas | ⚠️ |
| Confirmação em 2 cliques no próprio item (cancelar, excluir) | diálogo de confirmação (`data-confirmar`) e diálogo de motivo (`dialogo_motivo.html`) | ✅ ➕ |
| — | Janela de resumo do ofício; janela "Revisar e emitir" | ➕ |
| — | Paleta de comandos (Ctrl+K / "/") | ➕ |

## 3. Fluxos ponta a ponta (para o QA)
1. **Criar → preencher → finalizar/emitir**: LEG cria numerado, salva (autosave), "Finalizar"
   valida pendências (dados, motorista, transporte, roteiro, justificativa) e marca Finalizado;
   NOVO cria numerado, autosave, "Revisar e emitir" mostra prontidão e emite PDF/A.
2. **Corrigir emitido**: LEG "Reabrir para correção" (revoga assinado) / NOVO "Editar (retificar)"
   ou "Reabrir" (gestor).
3. **Assinatura**: anexar PDF assinado; remover; baixar versão assinada × original. ✅ nos dois.
4. **Processo no eProtocolo**: LEG painel "Dados para o eProtocolo" + abertura automática +
   importação do PDF do processo. NOVO: só o pacote do processo para subir (`views_pacotes`). ❌.
5. **Cancelar/reativar/arquivar/excluir**: ver §1.3.
6. **Justificativas**: lista própria em ambos; NOVO lê dos ofícios (nada copiado).
7. **Exportar**: ✅ (ver lista).

## 4. Lacunas da área, por prioridade
| Prioridade | Lacuna | Onde está no LEG |
|---|---|---|
| Alta | Tela de **Numeração** (piso anual, lacunas, próximo número) | `views.py:972-991` |
| Alta | Painel **"Dados para o eProtocolo"** (interessados, assunto, nº/ano, protocolo, detalhamento, com Copiar) — componente "Copiar um texto" já existe no UI Lab e no Coffee | `services.py:409-448` |
| Média | **Importar processo do eProtocolo** (decisão de produto) | `viagens_prestacoes/importacao_views.py` |
| Média | Motorista de fora: **ofício nº/ano e protocolo de origem** + sugestão `oficios-do-motorista` | `views.py:757-769`, `services.py:368-406` |
| Média | Avisos de **protocolo repetido** e de **condutor não autorizado** | `views.py:639-651, 504-516` |
| Baixa | Página do editor do documento acessível pela lista | `documentos:editor_pagina` |
| Baixa | Ação "Complementar" fora do formulário | `views.py:841-847` |

## 5. Observações de método
- Nada foi gravado intencionalmente no LEGADO; ressalva: abrir `GET /viagens/oficios/<pk>/editar/`
  no legado **atualiza** o snapshot da justificativa (efeito colateral do próprio legado,
  `justificativas_services.py:143-168`) — evitar navegar para a edição do legado nas próximas
  rodadas ou fazê-lo só em cópia do banco.
- Contagens e pesos medidos com `CaptureQueriesContext` (só GET) nos dois sistemas.
