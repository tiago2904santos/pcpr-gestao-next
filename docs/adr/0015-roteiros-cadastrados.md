# ADR 0015 — Roteiros cadastrados como modelo para ofícios

- **Status:** aceito · **Data:** 2026-10-02
- **Relacionado:** paridade R14 (`docs/parity/oficio.md`), ADR 0014 (campos de data e hora)

## Contexto
No sistema de referência, "Roteiros" é uma página própria: roteiros reutilizáveis com sede,
destinos, horários, efetivo e diárias. Na edição do ofício, "Vincular a um roteiro existente"
traz o roteiro para o ofício. O dono do produto pediu a migração da página de roteiros para
usar esse modelo na página de ofícios.

## Decisão
1. **Entidades** `Roteiro` (unidade, sede, quantidade de servidores, observações, situação
   ativo/cancelado, diárias estimadas) e `TrechoRoteiro` (mesmas regras do `Trecho` do
   ofício, garantidas por constraints). Auditadas pelo trigger do banco.
2. **Mesmas regras do ofício**: a sequência dos trechos é validada pela mesma função
   (`_validar_sequencia`) e as diárias pelo mesmo domínio (`_calcular_trechos`), usando o
   efetivo do roteiro.
3. **Copiar, não compartilhar.** "Usar um roteiro cadastrado" (edição do ofício) preenche o
   itinerário na tela, preservando o que foi digitado, e nada é gravado até salvar. "Criar
   ofício com este roteiro" cria o rascunho numerado já com os trechos. Em ambos, o ofício
   guarda `roteiro` como **origem**. Editar o roteiro depois não muda o ofício, e
   vice-versa. As diárias do ofício seguem a equipe do ofício.
4. **Sede da unidade**: como no ofício, a sede do roteiro é a da configuração da unidade; um
   roteiro só serve a ofícios com a mesma sede.
5. **Escopo e permissões** por unidade (`roteiros_visiveis`, `pode_*_roteiro` em
   `policies.py`); papéis em `papeis.py` (`view/add/change/delete_roteiro`).
6. **Exclusão** só de roteiro que ainda não serviu de modelo; usado → cancelar.
7. **Telas** reutilizam o itinerário do ofício (`viagens/_itinerario.html`), a lista de
   registros e as diárias; abas como na referência: todos, que vão acontecer, em andamento e
   realizados, cancelados.

## Fora desta decisão (pendente)
- Aba "Finalizados" e o estado FINALIZADO da referência: o significado precisa ser confirmado
  com o dono do produto.
- Mapa, cálculo de rota/distância e tempo de viagem sugerido (R13) e vínculo com Viagem.
- Escolha de sede diferente da unidade.
