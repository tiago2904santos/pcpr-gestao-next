# ADR 0028 — Carregue o download na primeira ação

- **Status:** aceito (recorte autorizado pelo coordenador)
- **Data:** 2026-10-07

## Contexto

Baseline fresco da folha: JS 155,3 KB / gzip 54,7 KB, acima de 130 / 45 KB.
`baixar.js` entra pela presença de `#dialogo-baixar`, mesmo fechado. Fonte local
minificada: aproximadamente 6,6 KB. O diálogo atende Ofícios (lista, resumo,
editor), Termos, OS, planos/viagens, justificativas e UI Lab. O endpoint GET só
deve ser solicitado ao abrir, e o POST somente ao enviar escolhas.

Regra existente: `docs/product/documents.md`,
`templates/componentes/dialogo_baixar.html`, `viagens/views_pacotes.py` e
`viagens/pacotes.py`. Os testes existentes verificam seleção inicial, PDF único,
versão assinada/original, preferências, permissão e arquivo entregue.

## Decisão

Complemento após E2E em 07/10: POST fetch de pacote inválido retorna 422 JSON
com erro, exibido no alerta existente. O redirect antigo consumia a mensagem
durante fetch e depois navegava sem orientação. POST normal conserva redirect.
Essa correção fecha a recusa de pacote incompleto já prevista em RS02.

Retire somente o registro de import inicial por `#dialogo-baixar` do app.
Um listener delegado único do app recebe o clique de `[data-baixar-documentos]`,
incluindo cliques nativos produzidos por Enter/Espaço, importa o módulo e chama
sua função exportada `abrirDialogo(botao)`. Não reenviar eventos nem simular o
primeiro clique. O ramo de abertura sai do listener de baixar.js; marcar todos,
change e submit permanecem nele, registrados uma vez pelo cache de módulos ES.

Deduplicar uma abertura enquanto o import está pendente. Usar aria-busy na
origem e limpar assim que a abertura for entregue ao módulo. Escape antes de o módulo chegar cancela a ação
pendente, sem impedir os handlers existentes do menu/diálogo. Botão removido não
abre janela depois. Falha de import anuncia mensagem em português pelo toast do
DS, indicando recarregar a página e tentar de novo; preservar o foco na origem
disponível, sem roubar foco de uma interação posterior. Não fingir arquivo gerado.

Cada abertura tem geração e AbortController próprio para o GET. Fechar a janela
cancela a leitura pendente; reabrir pode iniciar uma nova leitura imediatamente.
Resposta antiga, abortada ou pertencente a janela removida não redesenha nem
mostra erro ou muda foco. Aborto deliberado de leitura não é falha para o usuário.

O corpo da abertura mantém reset, escolhas lembradas, URL, GET, desenho,
regras/estados e redirecionamento existentes. Foco final não deve sair de outra
interação quando o usuário já tiver fechado a janela durante o GET. Os endpoints,
policies, geração de arquivo, CSRF, sessão, formatos e envio permanecem iguais.

## Alternativas consideradas

- Pré-carregar por hover/foco: o menu usado pela medição já poderia pagar o custo,
  sem que o usuário pedisse download. A ação explícita é menor e verificável.
- Re-dispatch de clique depois de importar: pode duplicar abertura e outros
  handlers; a função exportada preserva o primeiro comando diretamente.
- Alterar diálogos/endpoints ou lazy de HTML neste recorte: desnecessário para
  retirar somente o módulo inicial.
- Aumentar teto ou excluir recurso do coletor: contradiz o orçamento.

## Consequências

O custo do módulo passa à primeira abertura e a abertura fria tem latência de
import. App cresce um pouco; não anunciar subtração líquida ou teto atendido
antes de coletar recursos reais. Cache de módulos mantém handlers únicos em
reabertura e HTML reposto. A interação adiada ainda precisa funcionar e seu
custo não desaparece da aplicação.

Obrigatórios: TypeScript/lint, ausência inicial nas rotas com diálogo, abertura
por teclado/clique, deduplicação, cancelamento/removal durante import, erro de
import anunciado, fechar durante GET, reabertura, preferências/seleções/versão,
download real, foco de menu, resposta antiga divergente após fechar/reabrir,
resumo sobreposto, HTMX, axe/capturas 360/1440 e
nova medição. Banco/navegador serão executados sequencialmente pelo coordenador.
