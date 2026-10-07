# ADR 0024 — Versionar a fórmula no cache de rotas

- **Status:** aceito
- **Data:** 2026-10-07

## Contexto

Tiago determinou reproduzir a fórmula de tempo da referência, substituindo as
fórmulas anteriores do ADR 0016. `DistanciaMunicipios.minutos` guarda o resultado
já arredondado; não guarda a duração bruta do provedor. As linhas existentes foram
calculadas com a regra anterior. Aplicar a calibração nova sobre esses resultados
seria aplicar uma segunda fórmula sem os dados originais necessários.

Fonte verificada: `gestao/viagens/rotas.py`, `calcular`, e modelo
`gestao/viagens/models.py`, `DistanciaMunicipios`. Trata-se de cache não auditado,
distinto dos tempos de `Trecho`/`TrechoRoteiro` e dos snapshots emitidos.

## Decisão

Adicionar `regra_tempo`, inteiro com default **0**, ao cache. A nova fórmula usa
versão **1**. A leitura de cache exige versão 1 e o provedor configurado. Linhas
anteriores permanecem versão 0 e só serão atualizadas ao obter nova resposta do
provedor pelo fluxo normal. A duração em segundos recebida é convertida para
minuto inteiro como na referência antes da calibração por distância.

Sem cache compatível, consultar o provedor; em falha, manter a estimativa offline
identificada como estimativa. Sua distância continua linha reta × 1,3, com duração
bruta estimada a 70 km/h; essa duração e distância entram na fórmula aprovada,
sem fingir uma duração real de API. Sem coordenadas, manter a sugestão mínima
existente identificada como estimativa. Mesma cidade continua zero.

Nenhum trecho salvo, tempo editado manualmente, diário, snapshot ou documento
emitido é regravado por essa mudança. Não remover caches em bancos remotos.

## Alternativas consideradas

- **Apagar todas as linhas:** perde geometria/distância, exige ação operacional
  destrutiva e não distingue futuras mudanças de fórmula.
- **Recalibrar minutos antigos:** duração bruta não existe; produziria cálculo
  diferente da referência e poderia calibrar novamente resultados novos.
- **Usar data de atualização como versão:** mistura relógio/deploy com regra de
  domínio e não permite reproduzir a decisão de forma determinística.
- **Guardar duração bruta agora:** evolução possível para recalibrações futuras,
  mas não recupera duração das linhas existentes e amplia o schema sem necessidade
  para corrigir esta regra.

## Consequências

Uma coluna e uma migração aditiva; caches antigos ficam inválidos para novas
sugestões, sem apagar as linhas. O primeiro pedido de cada par pode consultar o
provedor novamente. Testes devem demonstrar cache antigo ignorado, cache novo
reutilizado uma vez, provedor diferente não reutilizado, falha offline, chegada
e diárias correspondentes à duração informada, e preservação de trechos salvos.

Este ADR antecede a integração. No momento do registro, existem apenas a decisão
humana e os contratos; resultados de execução serão registrados em
`docs/product/tempos-de-rota.md` e no relatório QA após os testes.
