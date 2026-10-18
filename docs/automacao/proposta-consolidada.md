# Proposta consolidada (AUT-14) — primeira entrega

> "Proposta consolidada: selecionar o evento, informar quem vai, revisar antes de criar
> rascunhos. A prévia não reserva número oficial." (pedido do dono do produto)

Desenho completo em [11-3 §4–§5.4](fluxos/11-3-autonomia-progressiva.md) e na
[ficha AUT-14](fichas/comunicacao-e-viagens.md#aut-14). Esta página registra o que foi
construído agora, as decisões e o que ficou de fora.

## O que faz

Tela `/viagens/proposta/` (entrada também pelo menu "⋮" da folha da viagem: **Preparar com
prévia**).

1. **Escolher a viagem** (visível para quem pede e não cancelada) e **informar quem vai**:
   servidores, quem dirige (opcional) e viatura (opcional), com o mesmo componente de equipe do
   lote. A tela **não sugere** ninguém.
2. **Ver prévia** (GET — nada é gravado, nenhum número é reservado) mostra numa página:
   viagem, período, unidade, destinos, a solicitação de origem quando houver; o roteiro de
   referência e os trechos; quem vai (com "de outra unidade", "dirige a viatura", "cadastro
   incompleto"); as **diárias estimadas** por servidor e do ofício; os **documentos** que seriam
   criados (ofício, termos, OS, plano) e os que já existem e não mudam; os **conflitos de agenda**
   (aviso, não bloqueio); os avisos e **o que falta depois** (protocolo, quem dirige, meio de
   transporte, justificativa pelo prazo, conferir OS e plano).
3. **Criar rascunhos** (POST com a assinatura da prévia) cria tudo de uma vez, em rascunho e
   vinculado à viagem.

## Como funciona

- `gestao/viagens/proposta.py`
  - `montar(usuario, Entrada) -> Proposta` — leitura pura. Usa as mesmas peças da criação:
    `viagem_lote.validar`, `services.trechos_informados_do_roteiro` +
    `services.calcular_informados` (domínio `dominio/diarias.py` com a tabela vigente) e
    `plataforma.conflitos`. As diárias levam o rótulo "Estimativa para conferência — o valor
    oficial sai no documento."
  - A `Proposta` tem uma **assinatura** (SHA-256 de tudo o que a pessoa vê: entradas, versão da
    viagem e do roteiro, documentos previstos, diárias, conflitos, bloqueios e avisos; sem o
    horário do cálculo).
  - `aplicar(usuario, Entrada, assinatura)` — numa transação: trava a viagem, **remonta** a
    proposta com a mesma função e compara a assinatura. Diferente (equipe, viatura, roteiro,
    viagem, documentos existentes ou agenda mudaram) → `PropostaDesatualizada`, nada gravado; a
    tela responde 409 com a prévia nova. Com bloqueio → `PropostaBloqueada`. Igual → cria pelo
    serviço existente `viagem_lote.gerar` (que usa `services`, `termos`, `ordens`, `planos`, com
    histórico e policies de cada um).
- `gestao/viagens/views_proposta.py` e `templates/viagens/proposta/proposta.html` (arquétipo
  DETAIL, componentes existentes, sem estilo nem script inline).
- Autorização: `proposta.pode_propor` compõe as policies do contexto (`policies.pode_criar` e
  `policies.pode_editar_viagem`); viagem fora do escopo (`policies.viagens_visiveis`) → 404; sem
  permissão → 403.

## Decisões

1. **Origem = viagem existente.** A solicitação deferida já vira viagem pelo botão atual
   (`de_eventos.gerar`); a proposta parte dessa viagem e mostra "Solicitação #N" como origem.
   Montar direto da solicitação (sem a viagem) fica para a entrega seguinte (AUT-15/semente).
2. **Um ofício por proposta** (uma equipe). Vários ofícios de uma vez continuam no lote atual.
3. **Numeração.** A prévia não reserva número (provado em teste: contagens de todas as tabelas
   de numeração e da auditoria iguais antes e depois, e o "próximo número" igual). Mas o
   rascunho de ofício, de OS e de plano **recebe o número oficial ao ser criado**: é a regra
   atual de `services.criar_rascunho` (`services.py`), `ordens.salvar` e `planos.salvar`, e o
   campo `numero` é obrigatório nesses modelos. Logo, "Criar rascunhos" consome números — como
   o lote e o "Novo ofício" de hoje —, e a tela diz isso. Deixar o rascunho sem número até a
   emissão exige mudar o modelo e `services.py` (fora do escopo desta entrega; ver riscos).
4. **IA só lê.** A ferramenta tipada `viagens.proposta_previa` (risco `leitura`, ADR 0020)
   monta a prévia para os ids **informados por uma pessoa** e devolve JSON. Não há ferramenta
   que crie os rascunhos: criar é clique humano na tela.
5. **Conflito é aviso** (regra da plataforma): aparece na prévia e não impede criar.

## Registro da ferramenta (no `ready` do app Viagens)

```python
from . import proposta
proposta.registrar_ferramentas()
```

## O que não está feito

- `PropostaViagem` persistida (estados pronta/obsoleta/aplicada, "salvar e continuar depois",
  idempotência por chave, marcação de obsoleta quando a solicitação cai): a prévia é recalculada
  a cada pedido e a assinatura cobre a mudança entre prévia e criação.
- Proposta a partir da solicitação sem viagem; vários ofícios; sugestões de equipe (AUT-17);
  roteiro proposto (AUT-64); selos de origem por valor.
- Reservar o número só na emissão (precisa mudar modelo e serviços).
- Dados próprios em `gestao/viagens/demonstracao.py` (a tela usa as viagens do DEMO que já
  existem), componente no UI Lab, item na navegação, testes de navegador (axe, 360–1440 px).
