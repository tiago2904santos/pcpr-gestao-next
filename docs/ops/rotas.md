# Rotas e mapa (ADR 0016)

| Variável | Padrão | Uso |
|---|---|---|
| `ROTAS_PROVEDOR` | `estimativa` (dev/preview: `osrm`) | `osrm`, `openrouteservice` ou `estimativa` (offline: linha reta × 1,3 a 70 km/h). |
| `ROTAS_URL` | — (dev/preview: `https://router.project-osrm.org`) | Base do provedor. Para OSRM próprio, aponte para a sua instância. |
| `ROTAS_CHAVE` | — | Chave do OpenRouteService. **Só por variável de ambiente; nunca no Git.** |
| `ROTAS_TIMEOUT` | `6` | Segundos por consulta ao provedor. |
| `MAPA_TILES_URL` | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | Mosaicos do mapa (origem entra no CSP `img-src`). Vazio desliga o mapa de fundo (teste). |
| `MAPA_ATRIBUICAO` | `© OpenStreetMap` | Texto de atribuição exibido no mapa. |

- Falha do provedor (rede, cota, formato) cai na estimativa e registra `WARNING` no log:
  o formulário nunca depende da rede.
- Resultados do provedor ficam em `viagens_distanciamunicipios` (origem, destino, km,
  minutos, traçado simplificado ≤ 250 pontos). A estimativa não entra no cache.
- Em produção, o servidor OSRM público tem política de uso justo: prefira uma instância
  própria ou o OpenRouteService com chave.
- Coordenadas dos municípios: `gestao/cadastros/dados/municipios_coordenadas.csv`
  (`LEIA-ME.md` explica a origem); carregadas na migração `cadastros.0003`.
