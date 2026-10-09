# Transporte em cartões — 09/10/2026

Base `671c3a9`, branch `codex/oficios-transporte-cartoes`. Pedido do usuário:
selecionar viatura pela busca, cartão equivalente à equipe com metadados,
confirmação animada da escolha pelo motorista, motorista de outro ofício abaixo
da viatura e opção oculta quando a equipe já tem motorista; servidores sem quebra.

## Implementação

- Variante compartilhada `pc-combobox[data-escolha-em-cartao]`: valor no select,
  busca livre depois da seleção, consulta abandonada não remove a viatura.
  Reselecionar a mesma opção não dispara alteração fantasma; leitura assistiva
  anuncia seleção e remoção. Cadastro rápido mantém os metadados da nova viatura.
- `recurso_selecionado.html`: avatar, identificação, combustível/tipo/unidade já
  disponíveis no cadastro e remoção com foco devolvido à busca. Usa a mesma
  superfície dos servidores; corrigida a exceção antiga de `.documento .pessoa`
  que removia superfície/raio e acrescentava divisor ao novo cartão.
- A escolha automática existente realça o cartão por 640ms e mostra sua origem.
  Movimento reduzido preserva o texto e desliga a animação. Sem nova dependência.
- Cartão externo com nome e ofício/protocolo de origem, mantendo campos e
  disclosure nativo. A marcação de motorista na equipe oculta/desabilita a opção;
  desmarcar a disponibiliza novamente. Serviço de substituição já existente.
- `pc-select` acompanha o atributo `disabled` do select nativo. Corrige o botão
  visual que permanecia desabilitado ao reabrir os campos externos.
- Nome e descrição dos servidores em uma linha cada, reticências e título
  completo. Não esconder as ações nem alterar nomes acessíveis.
- UI Lab, contrato de produto e Design System atualizados. Sem alterações em
  modelos, serviços, views de negócio, consultas, permissões ou documentos oficiais.

## Evidência visual

Galeria: `../evidencias/oficios-transporte-cartoes/index.html`, dez pares reais
em 360, 390, 768, 1024 e 1440px, equipe/transporte e motorista externo.
Capturas da aplicação PREVIEW com banco e mídia LAB isolados, dados fictícios.
Matriz final: 15 estados (duas folhas e UI Lab em cinco larguras), zero violações
axe WCAG 2/2.1/2.2 A/AA, zero erros de console e zero overflow horizontal.

Primeira medição do UI Lab em 768px acusou alvo parcialmente coberto pelo header
ao ancorar a seção no topo. `diagnostico/ui-lab-768-posicoes.json` reproduz 1
violação nessa posição e zero centralizando a seção, sem desativar regras/nós.
As capturas do diagnóstico foram preservadas. A matriz final usa a seção
centralizada no UI Lab; não equivale a aprovação de toda posição de rolagem.

## Iterações e falhas preservadas

1. Bateria inicial: 80 passaram, cinco falhas ao esperar autosave de uma opção já
   selecionada. Eliminado o evento fantasma da variante; teste passa a selecionar
   outra viatura e verificar gravação real no banco.
2. Reteste: nove passaram, cinco falhas por tentar selecionar o select nativo
   oculto. Teste corrigido para o controle visual por teclado; sem forçar elemento.
3. Fallback sem JavaScript: um passou (64,41s), seleção nativa e salvamento no banco.
4. Fluxo por teclado revelou botão visual ainda desabilitado após reabrir o bloco.
   Correção compartilhada em `seletor.js`; diagnóstico e logs mantidos.
5. Retorno por clique não enviou o pedido de marcar motorista. Diagnóstico registrou
   somente autosave/GET, sem erro de console; validação de retorno por teclado
   foi seguida de diagnóstico geométrico: aviso superior saía do fluxo no mobile,
   deslocando o cartão entre pressionar e soltar. Resolvido na barra final da Folha,
   preservando o cartão inteiro clicável e o volante do usuário. Oito E2E finais
   passaram: clique/teclado nas cinco larguras, fallback sem JS e escolha automática
   normal/reduzida (364,55s). Não usar somente teclado como prova do clique.
6. Reposição da minuta expôs clone do seletor com marca de inicialização herdada
   mas referências/eventos ausentes. Corrigido na origem com cobertura de clone,
   reconexão e disabled. Bateria consolidada do editor/tokens/carga: 80 verdes.
7. Digitação remota antes do import não iniciava consulta. Retomada segura da
   consulta focada sem apagar identificação existente; caso de carga retida passou
   com seleção, cartão e gravação (62,35s). Jornada de criação/emissão/PDF passou.

## Validação final

Commit local de código/testes/evidências: `5140533`, junto da metade inferior
da Folha. Checkpoint posterior registra o fechamento somente em documentação.

Fonte congelada com a missão inferior da Folha; **gate integral verde: 2.281
aprovados, zero falhas, nove avisos preexistentes, 52min18s e exit 0**. Os 47
arquivos de fonte/testes não divergiram do congelamento após o gate.
Ruff, arquitetura, mypy, Bandit, migrações e tipos JS passaram. Log bruto e
registro em `../evidencias/oficios-cadastro-inferior/logs/cadastro-inferior-verificar-integral.log`
e `../evidencias/oficios-cadastro-inferior/gate-integral.json`.
Gate da rodada anterior (2.251 aprovados) é histórico e compara somente os avisos.
Capturas depois recapturadas em PREVIEW 8016 para refletir os ajustes do usuário;
15 estados verdes. O índice do UI Lab foi corrigido na missão inferior; a página
integral passou axe/console/overflow nas cinco larguras. Fechamento técnico
aprovado com ressalvas; revisão estética permanece com o usuário.
Relatório combinado: `oficios-cadastro-inferior-2026-10-09.md`.

## Limites

Revisão estética pertence ao usuário. Sem expansão para outros módulos. Não há
nova consulta, biblioteca, endpoint ou editor antecipado nesta mudança.
Incidente anterior dos dois PDFs DEV continua separado e pendente de autorização;
não substituir arquivos, hashes ou histórico. Esta rodada usa somente LAB isolado.
