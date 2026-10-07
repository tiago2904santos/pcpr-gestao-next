# ADR 0025 — Centralizar a seleção de versões documentais em domínio puro

- **Status:** aceito (integração incremental em validação)
- **Data:** 2026-10-07

## Contexto

O resumo, menu, anotações de lista, anexação, DOCX e pacote escolhem primeiro a
última versão pronta. Com ofício v1 pronto e v2 gerando/falhou, promovem v1 ao
lugar corrente. O resumo também pode oferecer PDF histórico como ação principal
de um rascunho reaberto. RS-01 já usa o snapshot da maior versão sem esse filtro.
Fontes exatas e comparação local em `docs/product/oficios-documentos-versoes.md`.

`Documento.versao` cresce por tipo, sem ID de lote de emissão; uma nova emissão
sem justificativa deixa as anteriores armazenadas. `ViaAssinada.documento_id`
identifica a versão assinada. Estado do ofício, geração do arquivo e assinatura
precisam permanecer separados. A referência gera sincronamente e preserva vias
emitidas/assinadas; não define os estados assíncronos do novo.

## Decisão

Selecionar uma única identidade documental por tipo no domínio puro, mantendo
disponibilidade de arquivo, assinatura e histórico como dimensões separadas.

A base independente recebe metadados imutáveis mínimos, sem Django, consultas,
I/O, usuário ou URLs. Escolhe maior versão sem filtrar pronto. Emitido possui
corrente; rascunho/cancelado conservam as emissões como históricas. Arquivamento
não muda a identidade. PDF/DOCX correntes só ficam disponíveis para a identidade
atual pronta. A via corrente precisa ser não revogada e corresponder ao ID/tipo
exatos. Ambiguidade deve aparecer em aviso, sem desempate inventado.

O coordenador aprovou a classificação de justificativa a partir do campo do
snapshot do último ofício. Vazio retira justificativas anteriores da corrente;
presente permite selecionar a última justificativa sob a invariante transacional
de `emitir`; inválido/ausente é indeterminado e não permite promover uma antiga.
Essa escolha não adiciona vínculo de emissão ao modelo e não prova correspondência
de registros importados que violem a invariante.

A integração usa a mesma projeção no resumo/menu/downloads/pacotes e anotações
equivalentes nas listas. Os consumers são conectados gradualmente conforme a
aprovação do coordenador; budgets e políticas precisam de validação em LAB.
Não implementa novas emissões, alteração de modelos ou reabertura; D17 continua
fora do escopo.

## Alternativas consideradas

- Manter `first(PRONTO)`: esconde falha/espera da versão atual e diverge do snapshot.
- Reconstituir de cadastros atuais: viola o congelamento documental.
- Decidir em cada template/serviço: perpetua seleções divergentes e regras repetidas.
- Unificar emissão por timestamps ou versões iguais: não há vínculo estrutural que
  sustente essa correspondência; números crescem por tipo.
- Criar ID de lote de emissão agora: exige modelo/migração e tratamento de históricos,
  acima do escopo autorizado desta correção.
- Expor modelos, autores, datas e URLs ao domínio: amplia a API sem ajudar a seleção;
  pertencem ao adaptador/apresentação futuros.

## Consequências

Testes puros podem verificar seleção, falha, histórico e assinatura sem banco.
Downloads históricos autorizados de cancelados e vias revogadas permanecem
possíveis nas rotas existentes. A projeção não decide permissão de leitura ou escrita.

Consumidores precisarão adaptar seus metadados e parar de promover versões prontas
antigas. Lista deve manter consultas constantes; resumo reaproveita suas listas.
Nenhum resultado de teste puro comprova integração HTTP, SQL, arquivos ou navegador.
A classificação pelo snapshot exige aviso em dados inconsistentes; uma solução
estrutural para emissão importada incompleta pode precisar de ADR próprio.

## Aprovação e implantação incremental

Em 07/10/2026 o coordenador autorizou a integração da projeção existente em listas,
menu, anexação, DOCX e pacotes, preservando os budgets e políticas. A aplicação
continua sem emissão automática. A base técnica passa a ser usada gradualmente;
os consumidores da tela e a medição SQL/browser são conduzidos pelo coordenador.
Minuta fica restrita ao rascunho e o DOCX pronto conserva a independência do arquivo
PDF, conforme contrato descrito no produto antes desta implementação.

## Resumo e atualização parcial

A integração do resumo usa a projeção uma vez com documentos e todas as vias já
materializados. Divide apresentação corrente/histórica sem modificar políticas de
leitura por ID. Mantém o endpoint existente; HTMX atualiza o bloco documental e
rodapé/cópia por select-oob com IDs estáveis. O hook de fechamento pertence ao
coordenador (dialogo.js), sem filtros avaliados no markup sob allowEval=false.
Não altera a cópia RS-01: texto válido da maior emissão é copiável independentemente
da prontidão do PDF. A disponibilidade PDF/DOCX/anexação permanece separada.
