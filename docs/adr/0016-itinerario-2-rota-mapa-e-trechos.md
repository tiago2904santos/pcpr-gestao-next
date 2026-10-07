# ADR 0016 — Itinerário 2.0: rota automática, mapa e trechos com chegada calculada

**Status:** aceita · **Data:** 2026-10-02 · **Paridade:** R13 (rota/distâncias/mapa/tempo sugerido)

## Contexto
O itinerário do ofício e do roteiro cadastrado (ADR 0015) pedia saída **e** chegada de cada
trecho, não deixava trocar a sede, não filtrava municípios por UF e só reordenava destinos
recarregando a página. O sistema de referência traça a rota num mapa, sugere tempo de viagem
e tempo adicional, separa "origem e destinos" dos "trechos" e preenche as datas de saída em
um calendário só.

## Decisão
1. **Três blocos, como no modelo:** *Sede e destinos* (lista de paradas com UF + município,
   ordem por arrastar e soltar), *Rota* (mapa Leaflet e resumo: km, tempo de estrada,
   tempo adicional, volta à sede) e *Trechos* (um card por trecho: só a **saída** é informada;
   a chegada = saída + tempo de viagem + tempo adicional).
2. **Rota no servidor** (`gestao/viagens/rotas.py`): provedor configurável
   (`ROTAS_PROVEDOR` = `osrm` | `openrouteservice` | `estimativa`), cache em
   `DistanciaMunicipios`, e **estimativa offline** (linha reta × 1,3 a 70 km/h) sempre que o
   provedor falhar — o formulário nunca depende da rede. Tempo de viagem arredondado para
   cima em 15 min; tempo adicional sugerido = 15 min a cada 2 h de estrada.
   API: `GET /viagens/api/rota/?p=Cidade/UF&p=...` (exige ver ofícios ou roteiros).
3. **Coordenadas dos municípios** (`cadastros.Municipio.latitude/longitude`) vêm de dado
   público (ver `gestao/cadastros/dados/LEIA-ME.md`) e são carregadas na migração.
4. **Formulários:** `FormularioSede` (uf, cidade), `FormularioDestino` (uf, cidade, saida,
   tempo_viagem, tempo_adicional, ORDER, DELETE) e `FormularioRetorno`. A UF confere o
   município escolhido. `gestao/viagens/itinerario.py` monta/lê os formulários e calcula
   os trechos (`TrechoInformado` com km e tempos gravados em `Trecho`/`TrechoRoteiro`).
5. **Sem JavaScript** tudo continua funcionando (adicionar destino por POST, chegada
   calculada ao salvar). Com JavaScript (`pc-itinerario`): UF filtra a busca, arrastar e
   soltar (ponteiro e setas), chegada ao vivo, rota com debounce, mapa carregado sob
   demanda, calendário único das saídas. O servidor recalcula tudo ao salvar.
6. **Orçamento de desempenho próprio** para os recursos do itinerário (Leaflet,
   `itinerario.css/js`, API de rota): `itinerario_gzip_kb ≤ 64`, `itinerario_requisicoes ≤ 6`
   em `tests/e2e/test_desempenho.py`, separado do orçamento comum da página. O CSS da
   página pública (login/erro) saiu para `static/css/publica.css`.
7. **Segurança:** a chave do provedor (`ROTAS_CHAVE`) só por variável de ambiente; o
   servidor valida o esquema da URL; os mosaicos do mapa entram no CSP (`img-src`) pela
   origem de `MAPA_TILES_URL`; em testes não há mosaicos nem provedor de rede.

## Consequências
- Trechos antigos (sem tempos gravados) são reexibidos com tempo de viagem = chegada − saída.
- Roteiro cadastrado com outra sede serve ao ofício: a sede vai junto com os trechos
  (`exigir_roteiro_compativel` só confere se o roteiro está ativo).
- O seed DEMO usa a estimativa offline para km e tempos coerentes.
- Operação: ver `docs/ops/rotas.md`.

## Revisão da regra de tempo — 07/10/2026

Tiago confirmou neste chat: **“pode copiar a regra do legado”**, após explicação
da diferença entre tempo de estrada, adicional sugerido e efeito nas chegadas/diárias.
Esta decisão substitui somente as fórmulas de tempo do item 2; mapa, provedores,
estimativa offline, edição dos tempos e orçamento próprio permanecem vigentes.

Fonte consultada somente por leitura: `Solicitações de eventos/viagens_roteiros/services/rota.py`,
constantes e funções `arredondar_a_15`, `tempo_de_viagem`, `tempo_adicional_sugerido`.

- Tempo calibrado: `((km + 12) / 74 × 60) × 0,85 + duração_api_min × 0,15`.
- Arredondamento: converter para minuto inteiro com `round` como a referência;
  múltiplos de 15, resto até 5 arredonda para baixo, acima de 5 para cima.
- Adicional sugerido: zero para viagem menor que 30 minutos; nos demais casos,
  `max(15, arredondar_a_15(tempo_viagem_min / 6))`.
- Exemplo confirmado por código: 240 minutos de viagem → 45 adicionais, em vez
  dos 30 adicionais da implementação anterior do novo sistema.

Domínio puro e testes vêm primeiro. A integração deve distinguir o tempo já
  calibrado de uma duração bruta do provedor: recalibrar um valor de cache já
  calibrado aplicaria a fórmula duas vezes. A cache anterior não guarda a duração
  bruta e será tratada como versão antiga, sem converter silenciosamente seu valor.
  O mecanismo concreto de versão será documentado antes da mudança estrutural.

Não recalcular trechos salvos, snapshots ou documentos emitidos automaticamente.
O operador continua podendo ajustar os tempos no fluxo da aplicação; novas
sugestões seguirão a fórmula aprovada. Ainda não implementado no serviço neste
checkpoint: a validação H está em execução sobre o código anterior.
