# eProtocolo/PR — estudo e plano de integração

Estudo de 03/10/2026. Fontes: documentação pública oficial do serviço
(<https://treinamento.api.eprotocolo.pr.gov.br/spi-servicos/inicial.html> e
`documentacao/centralseguranca.html`), página institucional
(<https://www.administracao.pr.gov.br/eProtocolo>) e a integração já existente na referência
(`integracoes/eprotocolo/`, `viagens_oficios/protocolo_services.py`,
`docs/EPROTOCOLO_PROTOCOLO_AUTOMATICO.md` — lidos, não copiados).

## O que a documentação oficial pública confirma

### Ambientes (API Gateway, serviço `spi-servicos`)

| Ambiente | Internet (`pr.gov.br`) | Intranet (`celepar.parana`) |
|---|---|---|
| Desenvolvimento | — | `https://hml-apigateway.paas.celepar.parana/seap/spi-servicos/api-des` |
| Homologação | `https://hml-apigateway.paas.pr.gov.br/seap/spi-servicos/api-hml` | `…celepar.parana/seap/spi-servicos/api-hml` |
| Treinamento | `https://hml-apigateway.paas.pr.gov.br/seap/spi-servicos/api-tre` | `…celepar.parana/seap/spi-servicos/api-tre` |
| Produção | `https://apigateway.paas.pr.gov.br/seap/spi-servicos/api` | `https://apigateway.paas.celepar.parana/seap/spi-servicos/api` |

Regra oficial: servidor na intranet usa a rota de intranet; na internet, a de internet.
Composição de URL de exemplo: `<base>/v3/protocolos/{protocolo}`.

### Autenticação (Central de Segurança, JWT)

- Token: `POST <central>/centralautenticacao/api/v1/token/jwt`
  - homologação/treinamento: `https://auth-cs-hml.identidadedigital.pr.gov.br/…`
  - produção: `https://auth-cs.identidadedigital.pr.gov.br/…`
- **client_credentials** (sistema sem login na Central de Segurança — nosso caso):
  `Authorization: Basic base64(clientId:secretId)`,
  `Content-Type: application/x-www-form-urlencoded`, `grant_type=client_credentials`,
  `scope=<escopos separados por espaço>` (exemplos oficiais: `spiserv.protocolos.consultar`,
  `spiserv.protocolos.validar`).
- **authorization_code**: só para sistemas cujo login já é a Central de Segurança (token no
  cookie `THE_TOKEN`). Não é o nosso caso hoje.
- Além do token, o **API Gateway exige um `consumerId`** (roteamento, limitação de taxa,
  bilhetagem).

### Requisitos de credenciamento (institucionais)

- Pedido pelo **PDS Mantis** (projeto "e-Protocolo – Integrações"): sigla e nome do sistema,
  cliente, descrição, contatos; se usa Central de Segurança; `consumerId`; cadastro GOP;
  **IPs das estações e servidores por ambiente**; **escopos** pedidos.
- Toda ação roda sob o **CPF de um usuário**; integração sistema-a-sistema usa um usuário de
  sistema com CPF, vinculado a local/setor, com permissões dadas pelo gestor de acesso do órgão.
- **IP autorizado**: produção só a partir de IPs de servidor previamente autorizados; testes
  podem usar VPN.

### O que a documentação pública NÃO traz

Lista de endpoints com método, esquemas de requisição/resposta, formato de erro, limites de
taxa e catálogo de escopos. A referência usa `/v3/protocolos` e afins e **ela mesma registra
que os caminhos precisam ser conferidos na documentação oficial antes de produção**. Esses
detalhes vêm com o credenciamento (documentação restrita). Até lá: `DESCONHECIDO`.

## O que a referência já fazia (comportamento a preservar)

| Situação | Comportamento |
|---|---|
| Protocolo vazio ao **gravar** (não ao criar o rascunho) | abre protocolo e preenche o campo |
| Credencial de treinamento/homologação | abre de verdade no barramento de teste, aviso "NÃO vale como protocolo oficial" |
| Número digitado à mão | preservado; origem `MANUAL` |
| Sem credencial | número **simulado** no formato certo, origem `SIMULADO`, aviso amarelo |
| Barramento fora do ar, credencial vencida, código institucional faltando | o ofício **é salvo assim mesmo**; falha vira aviso; a conferência continua cobrando o protocolo |
| Trava `REAL_READONLY` (padrão ligado) | modo real só consulta; abrir protocolo é recusado com mensagem |
| Códigos institucionais obrigatórios para abrir | órgão, local de origem, assunto "viagem", espécie "ofício" |
| Diagnóstico | `eprotocolo_check` (config, sem rede), `--escopos`, `eprotocolo_ping` (autentica e lê) |
| Fora de escopo lá também | enviar PDF ao processo, tramitar, acompanhar situação |

Origem do número: `MANUAL` · `EPROTOCOLO` (produção, oficial) · `TREINAMENTO` (teste, não
vale) · `SIMULADO` (sem rede, não vale).

## Arquitetura no sistema novo

```
viagens (services.py)  ──>  integracoes.eprotocolo.servico  (casos de uso: consultar, abrir)
                                     │  porta (Protocol tipado)
                                     ▼
                          adaptadores: Simulado | Http (urllib/httpx) | Gravado (testes)
                                     │
                                     ▼
                       Central de Segurança (token) + API Gateway (consumerId)
```

- O domínio (`gestao/viagens/dominio/`) **não conhece** o eProtocolo; recebe um número e uma
  origem.
- Escritas que dependem da rede **não** acontecem dentro da transação do ofício: o serviço
  publica na outbox (`integracoes.eprotocolo.abrir`) e o assinante grava o número com
  `versao` (sem sobrescrever número digitado no meio do caminho).
- Leituras (consultar situação/andamento) podem ser síncronas com timeout curto e cache.
- Trava de somente leitura **ligada por padrão**; produção só com `EPROTOCOLO_AMBIENTE=producao`
  **e** trava aberta explicitamente; nenhum segredo fora de variáveis de ambiente.

## Fases

| Fase | Entrega | Precisa de credencial? |
|---|---|---|
| E1 ✅ | Camada `gestao/integracoes/eprotocolo/` com porta, adaptador **simulado**, adaptador HTTP conforme a doc oficial (Basic + `scope` no token, Bearer + `consumerId`, `GET /v3/protocolos/{n}`), configuração, mascaramento, diagnóstico (`manage.py eprotocolo_check [--ping]`), testes sem rede (`gestao/integracoes/tests/test_eprotocolo.py`) | Não |
| E2 | Campo `protocolo_origem` no ofício + avisos na tela (manual/simulado/treinamento) | Não |
| E3 | Adaptador HTTP real em **treinamento**: token, `consumerId`, consulta | **Sim** (treinamento) + IP |
| E4 | Abrir protocolo ao gravar, via outbox, atrás da trava | Sim + escopo de criação + decisão do dono do produto |
| E5 | Consultar andamento (ofício, prestação, eventos); importar processo (prestação) | Sim |
| E6 | Anexar PDF/assinatura ao processo, tramitar | Sim + autorização institucional |

**Bloqueios institucionais (não dependem de código):** credenciamento no PDS Mantis, usuário
de sistema com CPF, `consumerId`, IP fixo do servidor autorizado (a VPS precisa de IP estável
— ver [hostinger.md](hostinger.md)), lista de escopos aprovada.

## Diferenças em relação à referência (registradas)

| Ponto | Referência | Novo | Classificação |
|---|---|---|---|
| Credenciais no token | `client_id`/`client_secret` no corpo do POST | `Authorization: Basic base64(clientId:secretId)` + `scope`, como a documentação oficial pede | DIFERENÇA INTENCIONAL (conformidade com a doc) |
| Abrir protocolo sem credencial | gera número **simulado** ao gravar e grava no campo | não abre automaticamente; abertura automática só na fase E4, atrás de configuração e decisão | DIFERENÇA INTENCIONAL — evita número falso em ofício (decisão do dono pendente) |
| Cabeçalho do `consumerId` | `consumerId` | `consumerId` (a confirmar na doc restrita) | DESCONHECIDO |
| Caminho de abertura e formato das respostas | `/v3/protocolos` (a referência pede conferência) | não implementado até o treinamento | PENDENTE |
