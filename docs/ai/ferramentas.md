# Contrato das ferramentas operacionais

Toda ferramenta que uma IA (ou o n8n) pode chamar é declarada no registro
(`gestao/automacao/`, a criar na fundação) com:

| Campo | Descrição |
|---|---|
| `nome` | `contexto.verbo` (`oficios.resumo`) |
| `descricao` | uma frase para o planner |
| `entrada` / `saida` | esquemas validados (dataclasses/pydantic → JSON Schema para MCP) |
| `risco` | `leitura` · `preparacao` · `reversivel` · `irreversivel` |
| `politica` | função de `policies.py` avaliada com o **usuário em nome de quem age** e o objeto |
| `idempotente` | se repetir com a mesma chave devolve o mesmo resultado |
| `timeout` | limite de execução |
| `executa` | chama `services.py`/`queries.py` do contexto — nunca ORM solto na ferramenta |

## Execução

1. Autentica o chamador (token de serviço com escopos) e resolve o usuário representado.
2. Valida a entrada.
3. Avalia a política; negada → erro tipado, auditado.
4. `irreversivel` → cria `PedidoAprovacao` (ferramenta, entrada, resumo legível, quem pediu)
   e devolve `aprovacao_pendente`; nada é executado.
5. Executa dentro de transação (escritas via serviço, com outbox para efeitos).
6. Grava `ExecucaoFerramenta` (entrada mascarada, saída resumida, duração, resultado,
   aprovação vinculada). A trilha imutável continua sendo o trigger de auditoria do banco.

## Erros

`EntradaInvalida`, `Negado`, `AprovacaoPendente`, `ConflitoDeVersao`, `RegraViolada`,
`IntegracaoIndisponivel`, `TempoEsgotado` — sempre com mensagem em português dizendo como
resolver (mesma regra das telas).
