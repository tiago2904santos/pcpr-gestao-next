# Justificativas — identidade e contexto, 10/10/2026

Base9056835, branch codex/oficios-transporte-cartoes. Contrato em product.
DEMO e mídia preservados; gravações somente em TEST com banco/mídia por execução.

## Observar, implementar, comparar

20pares reais: pendentes, preenchidas, vazio e diálogo em360/390/768/1024/1440.
Hero grafite, abas compactas, busca integrada, identidade do Ofício, registro de
relações e prazo institucional. Texto em linha de largura útil, sem coluna fictícia
financeira. Contagem/barra dentro do fragmento HTMX, fluxo natural na lista curta.
Diálogo mantém gravação manual e textos prontos; data e destino têm metadados legíveis.
Estado do texto separado da situação documental, antecedência e obrigação do prazo.

## Correções comprovadas

Defeito anterior reproduzido pelo teste HTTP: após422 q era vazio, aba não recuperada
e links relativos iam à rota salvar/GET405. Contexto agora usa voltar; abas, cancelar,
edição e paginação informam rota explícita. Todas fica explícita no campo oculto para
não mudar para Pendentes durante a busca ao vivo. Paginação compartilhada recebe
prefixo opcional, preservando os consumidores antigos quando ausente.

Retorno de foco do Baixar foi verificado na aplicação atual: Escape já retorna ao
botão do menu. Nenhuma alteração de JS necessária; nova assertion protege contrato.

## Segunda revisão e limpeza

Capturas revistas: registros proporcionais no desktop, conteúdo sequencial no mobile;
diálogo não esmaga texto/datas. UI Lab prova segundo consumidor de abas--conteudo,
com axe real360/1440 zero e sem overflow. Não foi alterado CSSOM ou regra do axe.
Nenhum CSS/JS exclusivo comprovadamente obsoleto nesta unidade: bases antigas têm
outros consumidores. Substituição limitada ao markup da lista, sem excluir fallback.

## Desempenho

SQL14/14/10/19 antes/depois, zero mutações DEMO. HTML+2489/+17088/+530/+2761 bytes
nos quatro estados. components.css+190bytes LF/+73gzip; JS diálogo/registro iguais.
Nenhuma biblioteca/requisição nova por esta variante CSS. Não houve comparação de
latência nem contagem HTTP desta unidade; não alegar ganho de velocidade.

## Validação

108HTTP/documentos/tokens verdes456,85s; dois contratos de paginação verdes.
Ruff e tipos JS verdes.20capturas finais200/axe0/console0/sem overflow.
Rodadas diagnósticas interrompidas preservadas. Causa comprovada no UI Lab:
cronômetro toast-tempo finito de6s fica paused com hover/foco. O helper aguardava
sua promise finished indefinidamente. Corrigido somente o teste para aguardar
animações de entrada e não o cronômetro; nenhuma animação/axe desabilitados.
Diagnóstico JSON comprova paused. Busca agora aguarda URL HTMX filtrada antes
de agir, sem aceitar contagem já igual antes da resposta.

A navegação de paginação apresentou contraste transitório em todos os textos, mesmo
com load completo. Não era cor final nem CSS novo: a transição nativa entre documentos
renderiza snapshots após load. Diagnóstico real registra ready=complete/transicao=true,
as animações nativas -ua-view-transition e, após o encerramento, false/axe0. Helper
aguarda a transição real com requestAnimationFrame (evaluate/CDP), respeitando CSP;
wait_for_function com string foi descartado porque exigia unsafe-eval. Sem alterar
CSP, estilos, reduced-motion ou excluir regras/elementos do axe. Falhas anteriores
preservadas, não classificadas como regressão de cor nem simplesmente ignoradas.
Rodada final completa: sete E2E verdes171,35s, incluindo três larguras, PDF real,
Escape/foco, conflito, consulta, paginação após422 e compatibilidade Planos.

Avaliação visual pelo usuário pendente. Entidade/data/assinante próprios do legado
continuam lacunas preexistentes; a migração não declara paridade integral. Gate global
novo permanece obrigatório antes da entrega consolidada.


Revisão independente do candidato atual: nenhum defeito impeditivo concreto;
links/contexto, HTMX/OOB, permissões/corrente e variantes compartilhadas conferidos.
Mypy303fontes e Ruff verdes. PDF de TEST preservado como justificativas-download-testado.pdf.
UI Lab final: dois E2E verdes91,61s. Página concluída tecnicamente; aprovação estética
pelo usuário pendente. Nenhuma regressão funcional bloqueante conhecida.
