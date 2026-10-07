# RS-01 — cópia para eProtocolo na Folha e no Resumo

## Observar, entender e projetar

Fonte e regra: `docs/product/oficios-eprotocolo.md`, domínio puro já validado e
adaptador `gestao/viagens/eprotocolo.py`. A referência local compõe cinco campos
com nomes, assunto, número, protocolo e detalhamento; a cópia não abre protocolo.
Emissão deve usar o snapshot da maior versão, mesmo gerando/falhou, e não promover
um PDF antigo pronto. Rascunho usa dados salvos. A revisão D13 identifica dados
para a emissão revisada. Não projetar CPF/RG como campos da cópia.

## Implementar

Folha/resumo usam um componente readonly, IDs distintos e `copiar.js` sob demanda.
Contextos reutilizam listas carregadas. Formulário bound/prévia orienta salvar
antes da cópia. Autosave/OOB de equipe atualizam os dados e preservam divulgação
e foco. Clipboard indisponível revela, foca e seleciona o texto com orientação
Ctrl+C. Rotas continuam aplicando leitura/escopo existentes antes da projeção.

## Testar, comparar, criticar e corrigir — LAB local, 07/10/2026

Banco próprio `pcpr_lab_rotas`, PostgreSQL 127.0.0.1:55432; nenhum banco remoto.
Execução pelo principal, no worktree, com Python/venv do checkout original.
Logs citados abaixo ficam em `var/` do checkout original.

- HTTP/orçamentos: **25 passaram e 1 falhou em 249,21 s**,
  `eprotocolo-http-orcamentos.log`. A falha tentou renomear todos os servidores
  para o mesmo nome, violando uma restrição única da fixture. A fixture passou
  a usar nome distinto por PK; **o caso passou em 9,98 s**,
  `eprotocolo-snapshot-final.log`. Não foi alteração de regra ou produto.
- HTTP cobre três perfis de leitura, outra unidade 404, ausência de edição 403,
  GET sem escrita de negócio, revisão D13, snapshot após mudar cadastro,
  última v2 gerando/falhou, snapshot inválido, erros/prévias e OOB de equipe.
  Cada chamada da projeção recebe listas explícitas e executa zero SQL.
  Sete testes de orçamento existentes passaram com os tetos originais.
- Rodada conjunta com editor: **11 passaram e 3 falharam em 241,94 s**,
  `eprotocolo-editor-navegador.log`. Passaram fallback da cópia no resumo,
  atualização real por autosave e preservação real de foco após OOB da equipe,
  além dos cinco casos de carga adiada e três casos anteriores do editor.
- Duas falhas de Clipboard: texto era idêntico, com CRLF devolvido pelo Windows
  e LF no DOM. Teste normaliza somente CRLF, preserva espaços/demais caracteres.
  **Os dois casos passaram**, junto de uma falha de teclado ainda em investigação,
  em **79,57 s**, `eprotocolo-editor-correcoes.log`. Cópia individual e Copiar tudo
  conferidos em 360 e 1440 px; cinco larguras sem overflow da página.
- A investigação da barra mostrou três tabstops após inserção dos controles.
  Reprodução, correção e teste verde em `editor-documental-acessibilidade.md`;
  último caso passou em 32,25 s, `editor-teclado-correcao.log`.

## Evidências e limites

Capturas duráveis em `docs/visual-agents/evidencias/eprotocolo-editor/`:
Folha 360/390/768/1024/1440 e editor 360/1440. Principal revisou 360/1440:
rótulos e botões da cópia legíveis, sem sobreposição nova dentro do componente;
campos longos permitem seleção/cópia completa. O editor estreito ainda mostra
o documento largo com recorte e, com índice aberto, fica muito estreito; isso
continua sendo uma questão do visualizador, não aprovação de seu acabamento.
Datas do itinerário ainda truncam o ano no celular, como já registrado no Lote H.
Topo/rodapé fixos no meio da captura full_page não são uma comparação de foco.

Há capturas anteriores do Lote H, com outros dados; não são um par idêntico de
antes/depois desta nova seção. Resumo expandido com fallback: **1 passou em
32,38 s**, `eprotocolo-resumo-capturas.log`; capturas nas cinco larguras copiadas
para a mesma pasta e 360/1440 revisadas. Corpo longo permite rolagem própria;
o rodapé permanece fixo. Axe sem violações sérias/críticas e console limpo.

Medição posterior: **3 falharam em 62,47 s**,
`viagens-perf-lazy-eprotocolo.log`, coleta sem erros. Folha passou de 52 para
36 requisições e CSS de 161,8 para 139,5 KB; o HTML agora soma 139,9 KB, JS
155,3 KB (gzip 54,7), SQL 26 e DB mediano 106,8 ms, acima de seus tetos.
TTFB mediano 234 ms, FCP 404, LCP 892, CLS zero e INP aproximado 16 ms.
Lista CSS 149,5 KB/28 requisições; resumo 149,5/29, também acima dos tetos.
Medição antiga durante disputa de recursos não permite concluir ganho de latência.
Nenhum orçamento alterado; permanecem correções de desempenho e verificador geral.
Não há aprovação estética do usuário inferida destes resultados.
