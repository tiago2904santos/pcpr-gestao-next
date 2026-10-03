# Agente operacional de IA — arquitetura proposta

Objetivo de longo prazo: uma IA que **lê, entende, planeja, executa, verifica, corrige e
relata** trabalho operacional (preparar ofício, consultar protocolo, conferir prestação,
acompanhar prazos), **sem poder irrestrito**. Proposta de 03/10/2026; decisão estrutural em
ADR 0020.

> Dois loops que **não se misturam**: o *loop de desenvolvimento* (esta migração, agentes de
> código, `docs/migration/`) e o *loop operacional* (o produto em uso, ferramentas de negócio,
> este documento). Agentes de código nunca usam as ferramentas operacionais em produção; o
> agente operacional nunca altera código, esquema ou infraestrutura.

## Camadas

```
Usuário ──> Assistente (conversa, painel "o que a IA fez/pretende fazer")
              │
              ▼
           Planner (LLM) ── memória/contexto (ver memoria.md)
              │  chama ferramentas, nunca o banco
              ▼
     Registro de ferramentas + políticas  (gestao/automacao/, código Django)
       ├─ tipagem (entrada/saída validadas)
       ├─ autorização = mesmas policies.py do usuário em nome de quem age
       ├─ classe de risco (leitura | preparação | reversível | irreversível)
       ├─ portão de aprovação (irreversível → pedido de aprovação humana)
       ├─ idempotência (chave por pedido), timeout, limites
       └─ auditoria (quem pediu, qual ferramenta, entrada, saída, aprovação)
              │
              ▼
     Execução: services.py dos contextos (as mesmas escritas da tela)
              │
              ├── PCPR Gestão (ofícios, roteiros, diárias, documentos…)
              └── gestao/integracoes/ (eProtocolo, Central de Viagens*, WhatsApp, e-mail)
```

\* só com API oficial.

## Classes de risco

| Classe | Exemplos | Regra |
|---|---|---|
| Leitura | consultar ofício, protocolo, conflitos, diárias calculadas | automática quando o usuário autorizou o assistente; sempre escopada à unidade do usuário |
| Preparação | criar **rascunho** de ofício, montar roteiro, propor justificativa, relatório de pendências | automática; resultado marcado "preparado pela IA" e revisável |
| Reversível | editar rascunho, adicionar viajante, aplicar roteiro | permitida por política; registrada; desfazível |
| **Irreversível / crítica** | emitir, cancelar, retificar emitido, abrir protocolo oficial, assinar, encaminhar, excluir | **sempre** para no portão de aprovação; executa só com aprovação explícita de humano com permissão |

## Fluxo human-in-the-loop

```
IA prepara → IA verifica (regras do domínio, pendências) → apresenta: o que fez, dados usados,
ferramentas chamadas, o que pretende fazer → humano aprova (por ação) → IA executa → confere
o resultado → relata
```

## MCP é apropriado?

Sim, **como transporte** das ferramentas para clientes de IA (assistente próprio, n8n via
*MCP Client Tool*, Claude etc.), desde que o servidor MCP seja uma fachada fina sobre o
registro de ferramentas — autenticação por token de serviço com escopo **e** identidade do
usuário em nome de quem age; nenhuma ferramenta irreversível executa sem o portão. Aprovação
humana não cabe dentro de uma chamada MCP (o n8n documenta essa limitação), por isso o
portão é **do PCPR**: a ferramenta crítica devolve "aprovação pendente #id" e a execução
acontece quando um humano aprova na tela.

## Primeiras ferramentas (fase A — leitura)

`oficios.buscar`, `oficios.resumo`, `oficios.pendencias`, `roteiros.buscar`,
`diarias.simular`, `conflitos.verificar`, `protocolo.consultar` (eProtocolo, quando houver
credencial). Fase B (preparação): `oficios.preparar_rascunho`, `justificativa.sugerir`.
Fase C (críticas, com portão): `oficios.emitir`, `protocolo.abrir`.

Mais: [ferramentas.md](ferramentas.md) (contrato), [memoria.md](memoria.md) (contexto).
