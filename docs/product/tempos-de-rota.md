# Tempos de rota — regra da referência confirmada pelo usuário

Em 07/10/2026, o usuário confirmou no chat: **“pode copiar a regra do legado”**,
para tempos de viagem e adicional relacionados ao ADR 0016. Este documento registra
o contrato do domínio puro; a integração com provedores/cache e a revisão do ADR
pertencem ao agente principal. Esta etapa não altera roteiros ou documentos existentes.

Fonte consultada por leitura local, sem banco ou rede:
`C:/Users/tiago/OneDrive/Documentos/Solicitações de eventos/viagens_roteiros/services/rota.py`.
Constantes nas linhas 37–41; `_minutos` na 136; `arredondar_a_15` na 140;
`tempo_de_viagem` na 148; `tempo_adicional_sugerido` na 155. Os fluxos
`calcular_rota` e `estimar_trecho` mostram as unidades de entrada e a ordem das operações.

## Contrato de cálculo

- A duração bruta do provedor chega em **segundos**. Primeiro, converter a minutos
  com `max(0, int(round(float(segundos or 0) / 60.0)))`. A mistura recebe esses
  minutos já arredondados, não os segundos brutos nem minutos fracionários da rede.
- Arredondamento a passos de 15: primeiro aplicar `max(0, int(round(minutos)))`;
  depois calcular resto da divisão por 15. Resto **até 5**, inclusive, desce ao
  múltiplo anterior; resto **acima de 5** sobe ao próximo. `round` segue o empate
  para inteiro par do Python. Não substituir por ceil, ROUND_HALF_UP ou pelo
  múltiplo mais próximo. Resultado zero é possível e faz parte da regra.
- Viagem: calibrado = `(distancia_km + 12) / 74 * 60`; combinado =
  `0.85 * calibrado + 0.15 * duracao_api_min`; aplicar o arredondamento acima.
  Distância em quilômetros; duração da API em minutos. Aritmética usa float,
  como a referência. API ausente é zero nesta função; o fallback de estimativa
  que substitui ausência por duração calibrada pertence ao adaptador de rotas.
- Adicional: se viagem < 30 minutos, zero. Caso contrário,
  `max(15, arredondar_a_15(viagem / 6.0))`. Não acrescentar esse adicional à duração
  da estrada dentro da função: chegada combina os campos na camada de aplicação.

Os contratos são implementados em `gestao/viagens/dominio/tempos_rota.py`, sem
Django, settings, modelos, consultas ou rede. A API expõe `minutos_da_api`,
`arredondar_a_15`, `tempo_de_viagem` e `tempo_adicional_sugerido`.

Entradas numéricas finitas int/float reproduzem os resultados da referência.
`Decimal` é aceito: distância/duração da API são convertidas a float como no legado;
o adicional converte explicitamente a float apenas na divisão por 6. A função legada
falha com Decimal >= 30 por dividir Decimal por float; aceitar esse tipo é a única
diferença deliberada de tipo, autorizada pelo responsável pela implementação nesta
sessão. Valores usuais em Decimal produzem o mesmo resultado dos valores float
correspondentes. Nenhuma validação institucional nova é introduzida aqui.

## Exemplos e fronteiras

- 5 → 0; 6 → 15; 20 → 15; 21 → 30.
- 5,5 → 15, porque round(5,5) = 6. Já 20,5 → 15, porque round(20,5) = 20.
- 62 km e API de 60 min → viagem 60 min, adicional 15 min.
- 136 km e API de 120 min → viagem 120 min, adicional 15 min.
- 300 km e API de 180 min → viagem 240 min, adicional **45 min**.
- Viagem 29 min → adicional 0; 30 min → adicional 15.
- **4 horas → adicional 45 min**; a implementação anterior do novo sistema em
  `gestao/viagens/rotas.py` propõe 30 min (`(minutos // 120) * 15`). A confirmação
  humana exige substituir essa regra na integração; o domínio novo sozinho ainda
  não altera o comportamento da aplicação.

## Limites da entrega

Não alterados nesta etapa: `rotas.py`, modelos, migrações, cache de distâncias,
fluxos de chegada, ADR 0016 ou testes de integração existentes. A semântica de cache
antigo/calculado e fallback sem duração da API deve ser examinada na integração.
Testes do domínio isolado não validam os provedores, a folha ou o recálculo de roteiros.

## Evidência do domínio independente — 07/10/2026

Arquivos novos sobre checkpoint `b0829d6`, ainda sem commit nesta entrega:
`gestao/viagens/dominio/tempos_rota.py` e
`gestao/viagens/tests/test_tempos_rota.py`. Ruff focado: **verde**.
Execução final isolada: **68 testes passaram em 0,21 s**, com
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest --noconftest
-o addopts='' gestao/viagens/tests/test_tempos_rota.py -q`.
Sem conftest, plugin Django, fixtures, rede ou banco. O único aviso informa
`DJANGO_SETTINGS_MODULE` desconhecido, esperado porque o plugin Django foi desativado.

Comparação adicional isolada: leitura do AST do arquivo local de referência,
seleção somente das cinco constantes e quatro funções numéricas, sem executar
imports ou outras funções do módulo. **8.069 resultados iguais**: arredondamento
e adicional para passos de 0,25 min de -250 a 750; 56 pares distância/API;
11 conversões de segundos. A comparação confirmou 240 min → adicional 45 min.

A primeira execução dos testes teve três expectativas incorretas para 62 km sem
API (esperavam 45 min). A função da referência, carregada isoladamente, confirmou
60 min: calibrado 60, combinado 51, resto 6, portanto sobe a 60. Corrigidas essas
expectativas, acrescentando a asserção explícita de resto 6. A fórmula do domínio
não foi alterada para satisfazer os casos.

Não executada nem alegada: validação da aplicação com a regra nova, integração
de cache/provedores, navegador ou suíte geral. `scripts/verificar.sh` do agente
principal continua referido ao código congelado; estes testes validam somente
os novos arquivos de domínio, sem sobrescrever seu checkpoint.

## Integração isolada — 07/10/2026 17:05

No worktree gerenciado `viagens-tempo-legado`, sobre `36d4acd`, o serviço `rotas.py`
passou a usar o domínio. Cache recebeu `regra_tempo`, com default 0 para registros
antigos e versão 1 para a nova fórmula; somente o mesmo provedor/versão vale na
leitura. Migração aditiva 0050, conforme ADR 0024. Nenhum banco remoto consultado
ou alterado; dados sintéticos em `pcpr_lab_rotas`, PostgreSQL próprio porta 55432.

**101 testes passaram em 98,08 s**: 68 puros + integração do itinerário.
Log no checkout original: `var/rota-legado-integracao.log`. Cache anterior é
ignorado, uma resposta nova é reutilizada sem dupla calibração, cache de outro
provedor é substituído; falha de rede usa estimativa sem regravar cache antigo.
API preservou tempos salvos, versão, diárias e snapshots da emissão anterior.

Caso com provedor sintético: 300 km/180 min de API → 240 +45 min; saída 06:00,
chegada 10:45. Retorno no dia seguinte às 08:00 → chegada 12:45; período total
30h45 gera uma diária de 24h +15%, **R$ 334,13** pela tabela fictícia de teste
R$ 290,55, para um servidor. Não são valores ou dados de produção.

Tempos preenchidos manualmente continuam preservados ao salvar/reabrir a folha.
Makemigrations --check: sem diferenças; ruff e mypy verdes (2 arquivos de produto).
Navegador e incorporação ao checkout original ainda pendentes. Esta integração
não altera o código em execução na suíte H original, nem o servidor aberto em :8000.

## Validação da folha — 07/10/2026 17:37

Chromium: **2 testes passaram em 29,70 s** em 360 e 1440 px,
`var/rota-legado-layout-valores.log` no checkout original. Sugestões 04:00/00:45
foram salvas e recarregadas; ajuste manual 02:00/00:30 permaneceu no banco e na
folha. A resposta POST e o redirecionamento de salvamento são aguardados
explicitamente antes de recarregar, evitando confundir a mensagem de um
salvamento anterior com o envio atual.

A revisão de capturas encontrou corte do último dígito dos dois tempos no
celular. Contêineres estreitos agora exibem cada duração em sua própria linha,
preservando fonte e comandos. O navegador mede o texto do valor e exige que
caiba no input em **360, 390, 768, 1024 e 1440 px**. Capturas antes/depois estão
em `docs/visual-agents/evidencias/rota-legado/`; o antes refere-se ao ajuste de
layout, já com a fórmula nova. Revisão direta em 360 confirmou ambos os valores
completos. O corte anterior do ano no campo de saída permanece um achado
separado, fora dessa correção de duração.

Rodada intermediária: um caso passou e outro recebeu 422 ao salvar; log
`var/rota-legado-layout-final.log` preservado. A rodada posterior aguardou
explicitamente a resposta e passou. A causa do 422 intermitente não foi
demonstrada; não atribuí-la ao CSS nem afirmar que o diagnóstico de concorrência
está encerrado. A suíte integral H anterior terminou com uma falha de assinantes;
os checks verdes focados aqui não tornam `scripts/verificar.sh` verde.
