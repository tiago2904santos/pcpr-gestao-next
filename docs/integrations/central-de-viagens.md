# Central de Viagens (Estado do PR) — estudo

Estudo de 03/10/2026. Fontes: <https://www.administracao.pr.gov.br/DETO/Central_de_Viagens>
e o comportamento público de <https://www.centraldeviagens.pr.gov.br/ncv/>.

## O que se sabe

- Sistema estadual de gestão de viagens de servidores civis e militares da administração
  direta e autárquica, instituído pelo **Decreto Estadual nº 2.428/2019 (art. 4º)**; cobre
  deslocamentos, transporte oficial e diárias (alimentação e pousada), com controle de
  despesas. Gestão pelo DETO/SEAP.
- **Autenticação pela Central de Segurança** (identidade digital do PR): o acesso a `/ncv/`
  redireciona para `auth-cs.identidadedigital.pr.gov.br/centralautenticacao/api/v1/authorize/jwt`
  com fluxo `authorization_code` e escopo `central.seguranca.autenticado` — o mesmo provedor
  de identidade do eProtocolo.
- Manuais e guias na página oficial constam como **"em construção"**.
- **Nenhuma API, webservice ou mecanismo de interoperabilidade é documentado publicamente.**

## Conclusão

Não existe API pública documentada. Portanto:
- **não** fazer scraping, automação de navegador ou uso de sessão de usuário como substituto
  de integração (viola o acesso protegido e seria frágil);
- registrar a necessidade e buscar o canal institucional: DETO/SEAP (gestão da Central) e
  Celepar (provedora), perguntando por serviços no API Gateway estadual (o mesmo modelo
  `consumerId` + Central de Segurança do eProtocolo é o caminho provável);
- preparar no sistema novo apenas uma **porta** (`gestao/integracoes/central_viagens/`) com
  adaptador **nulo** e um **exportador** de dados no formato que o operador digita hoje
  (painel "dados para a Central de Viagens" com botões de copiar), que já reduz retrabalho
  sem depender de API.

## Perguntas ao canal institucional

1. Existe API no API Gateway para solicitação de viagem/diárias? Quais escopos?
2. É possível consultar a situação de uma solicitação por número?
3. Há ambiente de treinamento/homologação?
4. Quais dados mínimos uma solicitação exige (para alinhar o modelo do ofício)?
