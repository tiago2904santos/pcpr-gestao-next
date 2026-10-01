# Histórico do Git — limpeza de dados sensíveis (decisão D8)

Decisão do dono do produto (01/10/2026): **reescrever o histórico** para remover o que
nunca deveria ter sido versionado. Este documento não reproduz os valores removidos.

## O que estava no histórico
| Categoria | Onde aparecia | Substituído por |
|---|---|---|
| Nomes reais de servidores (vindos das telas da referência) | UI Lab, cenários de teste, exemplos | nomes fictícios já usados no código atual |
| Placa real de viatura | UI Lab, testes de validação | `ABC-1234` / `ABC1234` |
| Protocolo real do eProtocolo | formulário, máscara, testes, docs | `12.345.678-9` / `123456789` |
| Login do sistema de referência | docstring de `identidade/models.py` | `ana.lima` |
| Senha do Postgres descartável do CI (alerta GitGuardian 37792816 e 37793132) | `.github/workflows/ci.yml` | `POSTGRES_HOST_AUTH_METHOD: trust` |

Imagens, mensagens de commit e o CSV do IBGE foram verificados: nada a remover (nomes de
municípios parecidos com sobrenomes ficam intactos — a substituição é por nome completo).

## Como foi feito
1. Backup completo (`git bundle create … --all`) antes de qualquer mudança.
2. Clone novo do GitHub com `main` e o branch do PR aberto.
3. `git filter-repo --replace-text <arquivo>` — o arquivo de substituições fica **fora**
   do repositório (contém os valores originais).
4. Verificação: nenhum termo sensível em nenhum commit; a árvore do commit mais recente é
   idêntica à de antes (o código atual não muda); mesmo número de commits.
5. Envio com `git push --force-with-lease=<ref>:<sha esperado>` para `main` e o branch do
   PR — recusado se alguém tiver enviado algo no meio-tempo.

## Limites (o que a reescrita não alcança)
- **`refs/pull/*` do GitHub**: os commits antigos continuam acessíveis pelas páginas dos PRs
  (inclusive o PR 1, já mergeado) até o **GitHub Support** removê-los a pedido do dono do
  repositório ("remove cached views / dangling commits").
- **Clones e forks** feitos antes da reescrita mantêm o histórico antigo: quem tiver um
  clone deve apagá-lo e clonar de novo (não fazer `pull` por cima).
- **GitGuardian**: os incidentes antigos ficam registrados; depois da reescrita, marque-os
  como resolvidos no painel.
- Depois da reescrita todos os SHAs mudam; referências a commits antigos em comentários e
  documentos deixam de apontar para o lugar certo.

## Situação
- Histórico reescrito e verificado em clone local; **envio pendente de autorização** da
  ação destrutiva (`push --force-with-lease` em `main` e no branch do PR).
- O código atual já não contém nenhum desses dados (`tests/` e varredura de 01/10/2026).
