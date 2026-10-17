# Matriz visual — Coffee Break e Eventos Sociais × Viagens (referência aprovada)

Inventário por rotas, views e templates (não só pelo menu). Capturas em
`artifacts/auditoria-coffee-eventos/{antes,depois}/<ID>-<largura>.png` (larguras 360, 768,
1440), gerados por `scripts/auditoria_coffee_eventos.py`; as medidas (rolagem horizontal,
erros de console, axe WCAG 2.2 AA) ficam em `medidas.json` de cada rodada.

## Referências de Viagens usadas

| Ref | Família | Rota | Template | Componentes que definem o padrão |
|---|---|---|---|---|
| VR-01 | Painel | `/viagens/` | viagens/painel.html | `registro_hero`; `grade--kpi`; `colecao-operacional` + `registros--operacionais`; lateral em `pilha` |
| VR-02 | Lista | `/viagens/oficios/` | viagens/oficios/lista.html | hero; `filtro-conjunto` (abas `abas--conteudo` + `filtros--barra`); gaveta `filtros__avancados--rodape--organizados` com "Ordenar por"; fichas; `registros--operacionais`; ⋮ `menu__painel--descrito`; barra `barra-acoes--registro--colecao` com paginação e "Mais" |
| VR-03 | Resumo (janela) | `/viagens/oficios/<pk>/resumo/` | oficios/_resumo.html | a linha abre o resumo numa janela |
| VR-04 | Cadastro/edição | `/viagens/oficios/<pk>/editar/` | oficios/editar.html | hero com situação/contexto/ações; autosave; `documento--preparacao`; seções numeradas; `secao__bloco`; `historico_folha.html`; barra `--documental--registro--fluxo--preparacao` com `estado_salvamento` + `barra-acoes__acoes` + `rodape_documento` |
| VR-08 | Lista | `/viagens/prestacoes/` | prestacao/lista.html | como VR-02 |
| VR-09 | Fluxo | `/viagens/prestacoes/equipe/<pk>/` | prestacao/equipe.html | `etapas-progresso` |
| VR-10 | Leitura | `.../leitura/` | prestacao/leitura.html | `documento--preparacao` só leitura |
| VR-14 | Índice de cadastros | `/cadastros/` | cadastros/indice.html | hero + `lista_catalogo` |
| VR-15 | Catálogo | `/cadastros/unidades/` | cadastros/catalogo.html | hero com "Novo"; abas ativos/inativos; `registro--catalogo`; ⋮; barra com paginação; janela de cadastro/edição |
| VR-17 | Configuração (registro único) | `/cadastros/configuracao/` | cadastros/configuracao.html | `documento--preparacao`; barra `--rodape--preparacao--confirmacao` |

## Páginas auditadas

Situação final: **Alinhada** (segue a referência), **Alinhada com diferença de domínio**
(justificada), **Corrigida** (estava divergente; evidência antes/depois), **Pendente**.

### Coffee Break

| ID | Página / rota | Ref. | Inconsistências encontradas (antes) | Correção | Situação final |
|---|---|---|---|---|---|
| CB-P01 | Painel `/coffee/painel/` | VR-01 | lateral em grade de 3 colunas (referência: pilha); listas de lotes e certidões em `lista-simples` | | |
| CB-P02 | Lista `/coffee/` | VR-02 | sem "Ordenar por"; `filtros__acoes` fora de `filtros__lado`; linha não abre resumo em janela || "Ordenar por" na gaveta "Filtros e ordem"; `filtros__acoes` dentro de `filtros__lado` | Corrigida (a linha abrir o resumo numa janela fica pendente) |
| CB-P03/04 | Nova OS `/coffee/nova/` (+ preencher com e-mail) | VR-04 | barra com status escrito à mão, sem `barra-acoes__acoes` || barra no padrão: status com ícone + `barra-acoes__acoes` (Voltar à esquerda) | Corrigida |
| CB-P05 | Folha da OS `/coffee/solicitacoes/<pk>/` | VR-04 + VR-09 | numeração das seções quebrada (seções com ícone no lugar do número; "3" depois de seção sem número); histórico feito à mão (não `historico_folha`); status da barra à mão; sem autosave; dois formulários com botão de salvar no meio; anexos em `<details>` | | |
| CB-P06 | Protocolo `/coffee/solicitacoes/<pk>/protocolo/` | VR-04 | sem barra de rodapé ("Baixar" no meio da página, "Voltar" no hero) || barra de rodapé com status, Voltar e Baixar (`form=`); Baixar saiu do meio da página | Corrigida |
| CB-P07 | E-mail ao fornecedor | VR-04 | status da barra à mão, sem `barra-acoes__acoes` || barra no padrão (status com ícone + `barra-acoes__acoes`) | Corrigida |
| CB-P08 | Documentos (PDF/prévia) | VR-18 | — | — | Alinhada |
| CB-P09 | Lotes `/coffee/lotes/` | VR-02 | abas sem contagem; status da barra some para quem não administra || abas com contagem do recorte; busca + gaveta (ordem, exercício); paginação na barra (status aparece para todos) | Corrigida |
| CB-P10 | Lote `/coffee/lotes/<pk>/` | VR-10 | sem barra de rodapé/Voltar | | |
| CB-P11 | Relatório do contrato | VR-01/VR-10 | painel com cartões e tabelas (sem equivalente direto em Viagens) | — | Alinhada com diferença de domínio (relatório tabular) |
| CB-P12 | Abrir exercício | VR-07 | `campos` + `campo--md`; enviar em `linha` (sem barra) || barra `--preparacao` com status, Voltar e Abrir | Corrigida |
| CB-P13/14 | Certidões + janela de anexo | VR-10 | quadro por fornecedor (adequado); janela com `campo--md` | | |
| CB-P15/16 | Cadastros (fornecedores, contratos, aditivos, lotes) + janela | VR-15 | linhas sem `registro--catalogo`; "Novo" só na barra | | |
| CB-P17 | Ofício e protocolo (configuração) | VR-17 | abas fora do `filtro-conjunto`; salvar em `linha` em vez da barra de confirmação || salvar na barra `--rodape--confirmacao` (como VR-17); abas fora do `filtro-conjunto` mantidas (atalhos entre as tabelas do módulo) | Corrigida (barra) · diferença de domínio (abas) |
| CB-P18 | Lote do município (fragmento) | — | — | — | Alinhada |
| CB-P19/20 | Página pública do fornecedor / indisponível | VR-04 | — | — | Alinhada |

### Eventos Sociais

| ID | Página / rota | Ref. | Inconsistências encontradas (antes) | Correção | Situação final |
|---|---|---|---|---|---|
| EV-P01 | Painel `/eventos/` | VR-01 | — | — | Alinhada |
| EV-P02 | Lista `/eventos/solicitacoes/` | VR-02 | sem "Ordenar por"; `filtros__acoes` fora de `filtros__lado`; linha não abre resumo em janela || "Ordenar por" na gaveta "Filtros e ordem"; `filtros__acoes` dentro de `filtros__lado` | Corrigida (a linha abrir o resumo numa janela fica pendente) |
| EV-P03/04 | Nova solicitação (+ preencher com e-mail) | VR-04 | status da barra à mão, sem `barra-acoes__acoes`; classes `campo--md/lg` sem efeito dentro de `campos-folha` | | |
| EV-P05/06 | Folha da solicitação (+ alterar após envio) | VR-04 + VR-09 | despacho e transferência na grade antiga `campos`; histórico à mão; placa da viagem à mão; numeração das seções muda conforme a viagem aparece | | |
| EV-P07 | Cadastros — índice | VR-14 | — | — | Alinhada |
| EV-P08 | Catálogo `/eventos/cadastros/<slug>/` | VR-15 | **paginação nunca aparece** (bloco inexistente); "Incluir" em cartão no topo; edição inline em `<details>`; botões fixos em vez de ⋮; sem `registro--catalogo`; sem barra | `arquetipos/lista.html`: abas Ativos/Inativos com contagem, busca, `registro--catalogo` com ⋮ (editar, modelo, desativar, excluir), novo/editar numa janela, barra `--colecao` com paginação e "Novo" | Corrigida |
| EV-P09 | Modelo do tipo | VR-17 | `documento--cartoes`; `campos` + `campo--*`; salvar em `linha` || `documento--preparacao` e barra `--preparacao` com Voltar e Salvar; `campos` + `campo--*` é o mesmo de VR-17 | Corrigida |
| EV-P10..12 | JSON, arquivos, janela de motivo | — | — | — | Alinhada |
