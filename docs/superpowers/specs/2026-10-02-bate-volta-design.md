# Bate-volta: viagens que voltam à sede todo dia

## Problema

Há viagens em que a equipe sai da sede de manhã, trabalha num destino próximo e volta no
mesmo dia, repetindo isso por vários dias — e dormindo em casa entre eles. O caso que
originou esta especificação: um evento em São José dos Pinhais, com saída de Curitiba de
manhã e volta à tarde, todo dia, durante três dias.

O sistema **já suporta a forma desses dados**: são trechos alternados sede → destino → sede.
O cálculo de diárias trata passagem pela sede (não gera diária), a reedição preserva voltas
intermediárias (lição R3) e o documento, nesse caso, sai como "ROTEIRO POR TRECHOS"
numerados (decisão D7).

O que falta é **montar isso na tela**. Hoje seria preciso digitar a própria sede como destino
no meio da lista, uma vez por dia — seis destinos para um evento de três dias, e o
formulário aceita no máximo dez.

## Decisão

Guardar os blocos de bate-volta no banco e expandi-los em trechos ao salvar.

Foram consideradas duas alternativas:

- **Só expandir, e reconhecer o padrão ao reabrir.** Não mexeria no banco, mas remontar os
  blocos a partir dos trechos é adivinhação: qualquer ajuste manual desfaz o agrupamento.
  É a mesma família do bug R3 (bate-volta perdia voltas intermediárias ao reeditar), que já
  custou caro neste produto.
- **Gerador em vez de modo.** Um atalho que escreve os trechos uma vez e some. Não exige
  migração, mas reeditar um bate-volta longo volta a ser trecho por trecho.

Bate-volta não é exceção nestas viagens — é rotina, e vai ser reeditado. Guardar os blocos é
a única opção em que reabrir e mudar uma data continua barato.

## Modelo de dados

Ofício e roteiro já têm tabelas de trecho separadas (`Trecho` e `TrechoRoteiro`). Os blocos
seguem o mesmo par, em `gestao/viagens/models.py`:

| Campo | Tipo | Observações |
|---|---|---|
| `oficio` / `roteiro` | FK, `related_name="bate_voltas"` | cascata, como os trechos |
| `ordem` | PositiveSmallIntegerField | única por ofício/roteiro |
| `destino` | FK Municipio, PROTECT | a sede vem do ofício/roteiro |
| `dia_inicial`, `dia_final` | DateField | dias corridos, extremos inclusive |
| `hora_saida`, `hora_volta` | TimeField | iguais em todos os dias do bloco |

Travas no banco:

- `ordem` única por ofício/roteiro;
- `dia_final >= dia_inicial`;
- `hora_volta > hora_saida` — é isso que faz o dia ser "bate e volta".

Vai junto um campo `bate_volta` (BooleanField, default False) no `Oficio` e no `Roteiro`.
Sem ele, "nenhum bloco" seria ambíguo entre *modo desligado* e *modo ligado, ainda vazio* — e
o segundo estado precisa sobreviver a um salvamento recusado na validação.

Desligar o modo apaga os blocos. É explícito e evita dados órfãos que voltariam a aparecer
se o modo fosse religado.

## Expansão em trechos

Função pura em `gestao/viagens/dominio/bate_volta.py` — sem Django, como exige a arquitetura
(`gestao/viagens/dominio/` é Python puro).

```
expandir(blocos, sede) -> list[Perna]
```

Para cada bloco, na ordem, e para cada dia de `dia_inicial` até `dia_final`:

1. sede → destino, saindo em `dia + hora_saida`;
2. destino → sede, saindo em `dia + hora_volta`.

A quilometragem, o tempo de estrada e o tempo adicional continuam vindo da rota
(`itinerario._perna`), como em qualquer trecho. A chegada segue sendo saída + estrada +
adicional. Os trechos gravados são os mesmos de hoje: **diárias, documento e conflitos não
precisam saber que bate-volta existe**.

Ordem final: blocos por `ordem`, dias em ordem crescente dentro de cada bloco.

## Telas

Com o interruptor ligado, a etapa 1 ("Origem e destinos") troca a lista de destinos pela
lista de blocos. Cada bloco pede destino (o mesmo combobox de UF + cidade), primeiro dia,
último dia, hora de saída e hora de volta, com "Adicionar bate-volta" para o segundo caso
(SJP dias 1 a 3, Rio Branco dias 4 e 5).

A etapa 2 ("Trechos") passa a ser **só conferência** no modo bate-volta: mostra as pernas
geradas com quilometragem e chegada, sem campos. Como os blocos mandam, editar a saída de um
trecho contradiria o bloco. Para mudar um horário, muda-se o bloco.

O preenchimento sem JavaScript continua valendo: os blocos são um formset comum, e
"Adicionar bate-volta" é um submit, como "Adicionar destino" já é hoje.

## Limites

- **40 trechos** gravados por ofício ou roteiro (vinte dias de bate-volta). É um teto novo,
  sobre os trechos que chegam ao banco, valendo nos dois modos.
- **10 destinos digitados à mão** permanece como está. É outro problema: quarenta destinos
  distintos numa viagem seria um roteiro ilegível.

## Validações

Além das travas de banco:

- blocos não podem ter períodos sobrepostos entre si;
- a sequência final de trechos continua passando por `services._validar_sequencia` (nenhum
  trecho sai antes da chegada do anterior), o que também cobre blocos fora de ordem;
- a expansão não pode passar de 40 trechos — a mensagem diz quantos dias cabem ainda.

Se a volta de um dia chegar depois da meia-noite (destino distante demais para bate-volta),
o roteiro é aceito — o cálculo lida com isso — mas a tela avisa, porque quase sempre indica
erro de digitação na hora ou destino errado.

## O que não muda

- **Diárias.** Voltar para casa toda noite faz cada dia virar um período curto e entrar
  sozinho na escada do resto (até 6h não gera diária; até 8h, 15%; até 12h, 30%; acima,
  inteira). O domínio já trata passagem pela sede. Será confirmado por teste com o caso de
  São José dos Pinhais antes de se confiar nisso.
- **Documento.** Com volta intermediária à sede, já sai "ROTEIRO POR TRECHOS" numerados
  (decisão D7). Nada a fazer.
- **Conflitos de agenda.** Comparam intervalos de trechos; seguem valendo.

## Migração

Uma migração cria as duas tabelas e os dois campos booleanos. Nenhum dado existente muda:
ofícios e roteiros atuais nascem com `bate_volta = False` e sem blocos, e continuam sendo
editados pela lista de destinos.

Roteiros que hoje já têm voltas intermediárias digitadas à mão **não** são convertidos em
blocos. Converter exigiria a adivinhação que a decisão descartou; eles continuam válidos como
trechos manuais.

## Testes

- **Domínio** (`dominio/bate_volta.py`): bloco de um dia; bloco de vários dias corridos; dois
  blocos em sequência; ordem das pernas.
- **Diárias**: o caso de São José dos Pinhais (três dias, saída 08:00, volta 18:00) com o
  valor esperado conferido à mão.
- **Serviço**: salvar liga o modo, grava os blocos e grava os trechos expandidos; desligar
  apaga os blocos; o teto de 40 recusa com mensagem clara.
- **Tela (E2E)**: ligar o modo, preencher dois blocos, salvar, reabrir e conferir que os
  blocos voltam como foram digitados — a regressão que o R3 ensinou a vigiar.
- **Documento**: ofício em bate-volta sai como "ROTEIRO POR TRECHOS".

## Fora de escopo

- Ajustar o horário de um dia específico sem mexer no bloco.
- Pular dias dentro do período (fins de semana).
- Horários diferentes por dia.
- Converter roteiros manuais existentes em blocos.
