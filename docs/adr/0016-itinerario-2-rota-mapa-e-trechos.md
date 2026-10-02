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
