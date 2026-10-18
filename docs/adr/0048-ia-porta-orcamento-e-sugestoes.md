# ADR 0048 — IA atrás de uma porta, com orçamento reservado e sugestões revisadas por pessoa

- **Status:** aceito
- **Data:** 2026-10-18

## Contexto
A matriz de oportunidades (`docs/automacao/matriz-oportunidades.md`) indica assistência por IA em
13 itens (AUT-50, 57, 58, 76, 80, 81, 86, 88, 89, 92, 93, 94, 171) e pede, antes deles, a porta
única (AUT-96), o gabarito (AUT-91), a Central de ajuda sem IA (AUT-97) e ferramentas de leitura
(AUT-105). Os fluxos 10-1 e 11-2 fixam o desenho: o PCPR chama o modelo (nunca o n8n), a IA só
redige ou lê, a saída é JSON validado pelo sistema, nada se grava sem uma pessoa. Fatos do código
(18/10/2026): o SDK `anthropic` e o `jsonschema` não estão instalados; a outbox segura a transação
durante o assinante; `gestao.integracoes` e `gestao.automacao` não importam contextos de negócio
(contratos de import-linter, ADR 0019 e 0047); a ADR 0041 veda mandar documentos da importação a
IA externa. O sistema é de testes, com dados fictícios (ADR 0046).

## Decisão
1. **Porta `gestao/integracoes/ia/`** (padrão ADR 0019): `config.py` (única leitura de `settings.IA`
   ou das variáveis `IA_*`; chave com `repr=False`), `porta.py` (`PedidoIA` → `RespostaIA`, só
   primitivos), `erros.py` (temporária, definitiva, recusa, saída inválida, bloqueio por política),
   `adaptadores.py`, `servico.py` e o diagnóstico `ia_check` (sem rede).
   - **Simulado** (padrão em todo ambiente): devolve o resultado determinístico do próprio uso,
     sem rede e sem custo, contando tokens localmente — o fluxo inteiro roda no PREVIEW.
   - **Gravado**: respostas gravadas, para testar o caminho de IA sem provedor.
   - **Anthropic**: Messages API por HTTPS (`POST /v1/messages`, `x-api-key`,
     `anthropic-version: 2023-06-01`), transporte injetável, saída estruturada por JSON Schema
     (`output_config.format`), esforço baixo, sem ferramentas, `fallbacks: "default"` (beta
     `server-side-fallback-2026-07-01`) desligável por `IA_FALLBACK_SERVIDOR=false`. Só carrega
     com `IA_MODO=anthropic` **e** `IA_API_KEY`; `APP_ENV=preview` força o simulado; texto de
     documento é recusado (ADR 0041). Modelo padrão `claude-opus-5-5` (`IA_MODELO`).
   - Validação local do esquema (subconjunto em Python puro, sem dependência nova); o que a API
     não aceita no esquema (tamanhos, limites) é retirado do envio e conferido aqui.
   - Limites por chamada: caracteres de entrada, tokens de saída, tempo-limite, tentativas (só
     para falha temporária). Custo **estimado** = tokens × tabela oficial (prompt ≤ 100 mil
     tokens): Opus 5.5 US$ 4/20, Sonnet 5.5 US$ 2/10, Haiku 5.5 US$ 0,10/0,50 por milhão; modelo
     fora da tabela estima pelo mais caro. Nunca chamado de "cobrado".
2. **Contexto `gestao/assistencia`** (app nova, label `assistencia`): `ConfiguracaoUso` (liga,
   modo `regra`/`ia`, limites), `OrcamentoIA` (teto mensal global e por uso, reserva com
   `select_for_update` antes da chamada e liquidação depois; estourou → regra), `PedidoSugestao`
   (a fila do worker, com lease), `Sugestao` (estado, origem, modelo, versão do prompt, versão da
   fonte, hash do contexto, tokens, custo estimado, queda na regra e motivo, fontes, lacunas,
   decisão humana). O **conteúdo** (orientação escrita no pedido, textos sugeridos, avisos do
   validador, texto aplicado) fica em `ConteudoPedido`/`ConteudoSugestao`, sem trilha e com
   retenção (`ASSISTENCIA_RETENCAO_DIAS`, padrão 30). As tabelas de estado têm trigger de auditoria.
3. **Usos são código, registrados pelos contextos** (`<app>/ia_usos.py`, descoberto pela
   assistência com `autodiscover_modules` no `ready()` dela — a assistência não importa nenhum
   contexto). Cada `UsoIA` declara campos permitidos e dados excluídos (conferidos a cada pedido),
   instruções fixas e versão do prompt, esquema fechado (`additionalProperties: false`, listas
   fechadas para campo, fonte e lacuna), `montar` (leitura com a política de quem pede),
   `deterministico` (a alternativa sem IA), `validar` (fatos), `itens` (o que a tela mostra) e,
   quando grava, `aplicar` pelo serviço do contexto, com trava, revalidação da versão e sem
   sobrescrever texto humano sem confirmação.
4. **A IA só roda no worker** `processar_ia` (LISTEN `assistencia`), fora da requisição web e fora
   de transação: reserva do pedido, reserva do orçamento, chamada, liquidação e registro são passos
   curtos e separados. A reserva de orçamento fica anotada no pedido (valor e mês) e o lease do
   pedido passa a cobrir a chamada inteira; reserva de worker que morreu é devolvida por
   `liberar_reservas_presas` (laço do worker e rotina diária) e ao retomar o pedido de lease
   vencido; liquidar depois de liberada não desconta de novo. No modo regra a sugestão sai na própria requisição (local, sem IA).
5. **Validador de fatos** (Python puro, `assistencia/dominio`): todo número na fonte; nada de
   dinheiro, diária, km, viatura, motorista, norma ou nome de pessoa sem estar nos fatos; nenhuma
   entidade do catálogo (município, atividade) fora dos fatos; nenhuma afirmação que exige dado
   ("ribeirinhos", "intercorrências") nem promessa; pelo menos uma fonte, e só fontes do pedido.
   Reprovou → vale a regra, e a tela diz por quê.
6. **Prompt injection**: anexos, mensagens, relatos e registros entram só em blocos
   `<dados>` com `<`/`>` neutralizados; as instruções dizem que nada ali é instrução; CPF,
   telefone, e-mail e links são mascarados antes de sair; a saída só tem campos do esquema.
7. **Nunca pela IA**: escolher equipe, motorista ou viatura; inventar km, pagamento, atividade ou
   valor; calcular diária; emitir, cancelar, assinar ou aprovar prestação; decidir despacho. Os
   esquemas não têm campo para isso e as ações não existem como ferramenta.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| SDK oficial `anthropic` | Não instalado no `.venv`; HTTPS direto com transporte injetável mantém os testes sem rede. Recomendado como dependência futura |
| Chamar o modelo pelo n8n | Política e validação fora do código testado; credencial em dois lugares; execuções com dados pessoais no n8n (10-1 §5.2, 11-2 §6.4) |
| Chamar o modelo no assinante da outbox | O worker da outbox segura a transação durante o assinante |
| Orçamento só somado depois da chamada | Chamadas concorrentes passariam do teto; a reserva prévia do pior caso, com a linha travada, não |
| Uma tabela por uso (`SugestaoTextoPlano`, `SugestaoRT`…) | Duplicaria fila, orçamento, retenção e telas; o gancho por uso mantém a regra no contexto dono |
| Mandar documentos da importação ao provedor real | Vedado pela ADR 0041; os usos 57/58 rodam com regra local, simulado e gravado |

## Consequências
Nova app em `INSTALLED_APPS`, duas inclusões de URL (`assistencia/` e `ajuda/`), permissões
`assistencia.administrar_ia` e `assistencia.ver_painel_ia`, contratos novos no import-linter
(assistência não importa contextos; domínio puro), worker `processar_ia` nos compose (PREVIEW com a
porta simulada) e rotina diária de retenção. Telas: painel, usos/limites/orçamento, lista e
revisão de sugestões, pedido, Central de ajuda. Ligar um provedor real exige: variáveis no servidor,
gabarito AUT-91 verde, teto definido e, para documentos, uma ADR nova.
