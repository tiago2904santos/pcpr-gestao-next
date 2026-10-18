# Desempenho e custos — automação com n8n e IA (seção 12)

Avaliação de **17/10/2026**. Base técnica: [arquitetura.md](arquitetura.md), [contratos](contratos/) e
[plano de implantação](plano-implantacao.md). Os fluxos detalhados ([`fluxos/`](fluxos/)) definem como medir
cada ganho; aqui ficam os números de desempenho, de recursos e de custo, separados por tema.

**Marcação usada**

| Marca | Significado |
|---|---|
| **[medido]** | número coletado em 17/10/2026 (VPS, PREVIEW publicado ou protótipo local) |
| **[fonte oficial]** | preço, limite ou comportamento publicado pelo fornecedor (URL e data em [Fontes](#fontes)) |
| **[estimativa]** | conta feita aqui a partir de premissas declaradas; precisa de medição |
| **[hipótese]** | volume ou tempo suposto só para dimensionar; **o usuário precisa confirmar** |
| EXISTENTE · PARCIAL · PLANEJADA | capacidade que o código executa hoje · verificada só em parte · só no papel |

## 1. Conclusões

1. **O n8n cabe na VPS atual (KVM 2), em modo normal, sem custo de hospedagem adicional** [medido + estimativa].
   O gargalo é memória (3,8 GB disponíveis no pior momento medido), não CPU; swap e limite de memória por
   contêiner são pré-requisitos. Queue mode não melhora nada neste volume e custa memória.
2. **"Instalar o n8n" não é custo zero.** O custo real está no desenvolvimento da fundação no PCPR
   (API, eventos, `Comunicacao`, fila de exceções: etapa 1 do plano), na operação mensal, no tratamento
   de exceções e na cópia externa do backup.
3. **No cenário básico o gasto mensal adicional fica entre R$ 0 e ~R$ 10** com 200 viagens/mês (até
   ~R$ 50 com 500 viagens e 5.000 perguntas ao assistente) [estimativa]: e-mail institucional, rotas pela
   estimativa ou pelo OpenRouteService gratuito e IA desligada ou com orçamento mínimo (Claude Haiku 5.5).
   **No cenário ampliado**, entre ~R$ 100 e ~R$ 1.050 por mês, mais o backup externo, conforme o volume e o
   modelo de IA (tabelas da seção 15).
4. **IA local na VPS é inviável.** Um rascunho de plano levaria ~7,6 min de CPU com as duas vCPUs ocupadas,
   e uma pergunta ao assistente, ~18 min [estimativa sobre benchmark oficial]. A qualidade em português dos
   modelos pequenos é baixa.
5. **WhatsApp: custo da plataforma oficial apenas informativo.** A ativação está **bloqueada** pela política
   da Meta (autoridades policiais são usuários proibidos do WhatsApp Business Platform). O WhatsApp é
   prioridade do usuário (frentes WA-1 a WA-3 do [plano](plano-implantacao.md)): o envio assistido com
   registro (WA-1) não tem custo de mensagem (sai do aparelho institucional) e a integração oficial (WA-3)
   só custaria depois do portão de ativação. Ver [whatsapp-viabilidade.md](whatsapp-viabilidade.md).
6. **Os volumes reais não são conhecidos.** Tudo o que depende de volume está em três cenários (50, 200 e
   500 viagens por mês) com hipóteses explícitas (seção 3). **Pedido ao usuário: confirmar os volumes.**

## 2. Base de medição

| Origem | O que mediu | Limites |
|---|---|---|
| VPS de produção (sysstat a cada 10 min, 09–17/10/2026; `docker stats`; memória por serviço) — [capacidade-vps.md](../ops/mudanca-hospedagem/capacidade-vps.md) | CPU, memória, disco, rede, com e sem o PREVIEW | Sem n8n instalado; sem o sistema novo em produção |
| PREVIEW publicado, 17/10/2026 ~06:10 UTC: `curl` da estação do usuário, 8 GETs por URL, sessão DEMO, nada gravado | Tempo até o 1º byte (TTFB) e tempo total das telas | Servidor de desenvolvimento (runserver) em Docker, não gunicorn; RTT de rede 0,12–0,17 s incluído |
| Protótipo local ([`prototipo/`](prototipo/README.md), imagem `n8nio/n8n:2.43.7`): **execução final de 17/10/2026, 03:53–03:59 (horário de Brasília)**, T1–T12 e medição de latência na mesma bateria — [`prototipo/README.md`](prototipo/README.md) (seção "Métricas") e [`resultados.json`](prototipo/resultados/resultados.json) | Latência evento → envio, memória do contêiner, tamanho do banco, tempo de subida, cenários de falha | Docker Desktop no Windows (notebook compartilhado), banco **SQLite**, runner de código interno, PCPR e canal **simulados**, sem SMTP real. **Não representa a VPS.** As faixas citadas juntam as rodadas de desenvolvimento na mesma máquina. As métricas da execução final continuam válidas; as rodadas posteriores (21:47–22:05) acrescentaram o T13 (seção 12) |

## 3. Hipóteses de volume (confirmar)

**O que se sabe [medido]:** o Gerenciador de Viagens (GV) tem ~22 mil linhas em 85 tabelas; o Eventos
Sociais (EV), ~23 mil linhas em 137 tabelas; há 1.181 + 740 arquivos de mídia. Não se sabe por quanto tempo
esses dados se acumularam nem quantas viagens há por mês. Uma conta de ordem de grandeza: com 5–15 arquivos
por viagem, os 1.921 arquivos correspondem a ~130–380 viagens no histórico dos dois sistemas.
**Isso sugere que o cenário de 50 viagens/mês está mais perto da realidade do que o de 500**, mas é só uma
hipótese.

| # | Hipótese de dimensionamento | Valor usado | Origem |
|---|---|---|---|
| H1 | Viagens por mês | **50 / 200 / 500** (três cenários) | hipótese |
| H2 | Servidores por viagem | 4 | hipótese ("equipe de 4" do fluxo [10-5](fluxos/10-5-db-e-rt-para-assinatura.md)) |
| H3 | Viagens com viatura (diário de bordo, DB) | 80 % | hipótese |
| H4 | Viagens com retificação de documento já enviado | 10 % (aviso a todos) | hipótese |
| H5 | Lembretes | 1 por servidor (saque) e 1 por assinante (DB/RT); 50 % dos links de KM | hipótese |
| H6 | Arquivos devolvidos por viagem | 4 RT + 0,8 DB + 4 comprovantes = 8,8 | hipótese |
| H7 | Rotas | 1 roteiro por viagem; 1 par de municípios novo (fora do cache) por viagem após o aquecimento | hipótese |
| H8 | Tarefas de IA por viagem | 1 rascunho de plano, 1 de RT, 0,3 de justificativa, 0,5 leitura de programação; +30 % de retrabalho | hipótese |
| H9 | Exceções | 5 % das comunicações, 10 min cada; revisão nova em 10 % dos recebimentos, 3 min cada | hipótese |
| H10 | Dias úteis por mês | 22 | convenção |

**Volumes derivados por viagem** [estimativa]:

| Fluxo | Comunicações por viagem | Conta |
|---|---:|---|
| [10-2](fluxos/10-2-envio-de-documentos.md) envio de documentos | 4,4 | 4 servidores, 1 e-mail por pessoa (agregação) + 10 % × 4 avisos de substituição |
| [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) aviso de saque e lembretes | 8,0 | 4 avisos + 4 lembretes |
| [10-4](fluxos/10-4-link-de-km-na-vespera.md) link de KM | 1,2 | 0,8 link + 0,4 lembrete |
| [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) DB/RT para assinatura | 9,6 | 4,8 assinantes + 4,8 lembretes |
| **Total** | **23,2** | |
| [10-6](fluxos/10-6-recebimento-de-documentos.md) arquivos recebidos | 8,8 | H6 |
| Execuções do n8n | ~55 | 2 por comunicação (entrada do evento + entrega) + 1 por arquivo recebido |

Execuções **fixas** do n8n, independentes do volume: reconciliação a cada 15 min (2.880/mês), varredura da
caixa postal a cada 15 min (2.880/mês), monitor de filas a cada 15 min (2.880/mês) e resumo diário (30/mês):
**~8.670 por mês** [estimativa].

**Pedido ao usuário:** informar (ou autorizar uma consulta somente leitura que conte) ofícios emitidos por
mês nos últimos 12 meses, servidores por ofício, viagens com viatura, número de unidades/sedes e documentos
devolvidos por prestação. Com isso as tabelas das seções 8, 10, 11 e 15 passam de hipótese a estimativa.

## 4. Tempo de resposta da interface

**Medido no PREVIEW** (servidor de desenvolvimento, VPS compartilhada; tempo de servidor ≈ TTFB − ~0,13 s):

| URL | Tamanho | TTFB mediana | TTFB pior | Total mediana |
|---|---:|---:|---:|---:|
| `/saude/` (linha de base de rede) | 31 B | 0,15 s | 0,17 s | 0,15 s |
| `/viagens/viagens/` (lista) | 58 KB | 0,29 s | 0,35 s | 0,31 s |
| `/viagens/planos/` (lista) | 60 KB | 0,28 s | 0,39 s | 0,30 s |
| `/viagens/oficios/` (lista) | 141 KB | 0,40 s | 0,49 s | 0,46 s |
| `/viagens/oficios/260/editar/` (folha) | 172 KB | 0,43 s | 0,60 s | 0,49 s |
| `/viagens/oficios/260/minuta.pdf` (PDF gerado na hora) | 158 KB | 0,48 s | 0,52 s | 0,55 s |
| `/viagens/prestacoes/` (lista) | **848 KB** | 0,65 s | **1,43 s** | 0,80 s |

Leitura: telas em 0,15–0,35 s de servidor; minuta em PDF em ~0,35 s; a lista de prestações é a mais pesada
(até ~1,3 s de servidor). Ela deve ser paginada **antes** de servir de fonte a automações ou ao assistente.

**Efeito da automação na interface**

| Ponto | Situação | Regra |
|---|---|---|
| Carga do n8n sobre o PCPR | ~11–36 mil execuções/mês, ou seja, média de 0,004–0,014 requisição/s [estimativa] | Desprezível na média. O risco é a **rajada**: o fluxo [11-1](fluxos/11-1-rotas-e-roteiros.md) registra 3 workers web; se o n8n abrir 5 chamadas simultâneas à API, pode ocupar todos. Limitar a concorrência do n8n a 2–3 execuções simultâneas que chamam o PCPR, ou atender a API de automação por workers próprios |
| Rotas | EXISTENTE: cálculo **síncrono na view**, com `ROTAS_TIMEOUT` padrão de 4 s por chamada (`config/settings/base.py:227`; `gestao/viagens/rotas.py:122-158`) | Com provedor externo, cada perna fora do cache pode prender um worker web por até 4 s; um roteiro de 3 pernas, ~12 s. O fluxo 11-1 já prevê o cálculo no worker quando há perna sem cache (PLANEJADA) |
| IA | PLANEJADA | Nunca dentro da requisição web: a chamada ao modelo vai para um worker, e a tela mostra "gerando". O fluxo [10-1](fluxos/10-1-assistente-dos-servidores.md) fixa o tempo máximo de 30 s por chamada |
| API de automação (`/api/automacao/v1`) | PLANEJADA | Meta proposta: p95 < 300 ms no servidor para reservar, registrar resultado e consultar `devidas` (consultas indexadas). Medir no PREVIEW antes de ligar |
| Webhook de entrada do n8n | [medido no protótipo, execução final] evento → resposta 202 (verificação do HMAC incluída): p50 128 ms, p95 151 ms em série; p50 1,4 s, p95 2,4 s em rajada de 20 | Responder 202 logo e processar depois; quem envia é o worker de entregas do PCPR, fora da requisição do usuário |

## 5. Tempo completo do processo

Todos os fluxos abaixo estão **PLANEJADOS**. Os tempos são metas ou estimativas, não medições de produção.

| Fluxo | Do gatilho até... | Componentes do tempo | Esperado |
|---|---|---|---|
| 10-2 envio de documentos | emissão → e-mail aceito pelo servidor de e-mail | PDF no worker da outbox (segundos) + janela de agregação de 10 min + entrega pelo n8n (< 1 s no protótipo) + SMTP (segundos, não medido) | p95 < 15 min (meta do fluxo); pior caso com evento perdido ≈ 25–30 min (agregação + reconciliação de 15 min) |
| 10-3 aviso de saque | liberação registrada → aviso enviado | evento + reserva + envio | p95 ≤ 20 min (meta do fluxo) |
| 10-4 link de KM na véspera | horário agendado → link enviado | agendamento (seção 6) + envio | atraso ≤ 30 s com agendamento pela outbox; ≤ 15 min só com a reconciliação |
| 10-5 DB/RT para assinatura | conclusão da prestação → link entregue a cada assinante | geração de DB/RT + `LinkAcesso` + envio | minutos; depende da janela de envio do fluxo |
| 10-6 recebimento | e-mail recebido → item em revisão | IMAP IDLE (segundos) ou varredura de 15 min + fila de importação (concorrência 2 em produção) + conversão/OCR (**não medido**) | segundos a minutos por arquivo [estimativa]; medir o OCR por página |
| 11-1 rotas e roteiros | pedido → proposta pronta | cache → provedor → estimativa | p95 < 30 s com cache; < 2 min sem cache (meta do fluxo) |
| 10-1 assistente | pergunta → resposta | 2 chamadas ao modelo + ferramentas de leitura | não medido; teto de 30 s por chamada |

O processo administrativo completo (viagem → prestação aprovada) leva semanas e continua dependendo de
pessoas, da assinatura no eProtocolo e da tramitação oficial. As automações tiram espera e retrabalho das
bordas, mas **não substituem a tramitação oficial** (Decreto estadual 7.304/2021 — ponto a confirmar).

## 6. Atraso de agendamento: push × pull de 15 min

| Mecanismo | Atraso | Situação | Custo |
|---|---|---|---|
| **Push** (evento da outbox → worker de entregas → webhook do n8n) | [medido no protótipo] evento → envio no canal simulado, 20 em série: **p50 314 ms, p95 403 ms** na execução final (até o 202 do n8n: p50 128 ms, p95 151 ms; faixa nas rodadas: p50 166–361 ms, p95 214–490 ms) | PLANEJADO no PCPR; mecanismo validado no protótipo | 1 POST por evento |
| **Push agendado** (`outbox.publicar(disponivel_em=...)`) | ≤ 30 s depois do horário: o worker acorda por NOTIFY ou a cada `--intervalo` (padrão 30 s, `processar_outbox.py:18,36`) | **Depende de desenvolvimento** (item X10 do fluxo 10-2): hoje `publicar` grava sempre o horário atual | nenhum adicional |
| **Pull** (`GET /comunicacoes/devidas` a cada 15 min) | 0–15 min (média 7,5 min) | PLANEJADO; validado no protótipo (T5, T8) | 2.880 consultas/mês, indexadas: custo desprezível |
| Rajada de 20 eventos simultâneos | [medido no protótipo] **p50 5,1 s, p95 6,6 s** na execução final (até o 202: p50 1,4 s, p95 2,4 s; até a reserva chegar ao PCPR: p50 4,9 s; faixa nas rodadas: p50 2,5–6,1 s, p95 3,4–13,7 s) | Fila **no próprio n8n**, não nos simuladores: um processo `main` com SQLite e runner de código interno processando W1 + W2 de 20 eventos ao mesmo tempo ([`prototipo/README.md`](prototipo/README.md), "Métricas") | Para dezenas de comunicações por dia sobra; não extrapolar para a VPS; medir lá com PostgreSQL e runner externo |
| Reinício do n8n | [medido no protótipo] subida até o webhook responder: 15,8 s; depois de `docker kill`, 30,5 s até voltar e 40,5 s entre a queda e a volta (T10; faixa nas rodadas: 15,8–19,8 s e 27,6–30,5 s) | Eventos ficam pendentes no PCPR; a reconciliação recupera | Envios em curso viram exceção "resultado desconhecido" (seção 13) |

**Leitura:** o push dá a latência; o pull de 15 min é **rede de segurança**, não o caminho normal. Diminuir
o intervalo do pull para 1 min multiplicaria as execuções fixas por 15 (43 mil/mês só de reconciliação), o
que pesa na retenção e em qualquer plano cobrado por execução, sem ganho para o caminho normal. Enquanto o
agendamento pela outbox (X10) não existir, a precisão de horário dos envios agendados é de 15 min.

## 7. Tempo para disponibilizar documentos

| Situação | Como é | Tempo |
|---|---|---|
| GV em produção (referência) | Assinatura eletrônica simples de RT/DB por link público (token cifrado + hash, CPF, expiração); o documento abre por link temporário de 15 min; o link chega ao servidor pelo WhatsApp **aberto à mão pelo operador** | depende do operador |
| Sistema novo hoje (EXISTENTE) | PDF/A do ofício gerado pelo worker da outbox (`viagens.documento.gerar`); minuta gerada na hora | [medido] minuta em ~0,35 s de servidor no PREVIEW; PDF/A final no worker não medido na VPS |
| Sistema novo hoje (lacuna) | Nenhum evento avisa quando o PDF fica pronto; servidores viajantes não são usuários e não têm e-mail no cadastro | — |
| Planejado (10-2) | Disponível no portal assim que o PDF fica pronto (`viagens.documento.pronto`, a desenvolver); e-mail com link autenticado após a janela de agregação | portal: segundos [estimativa]; e-mail: p95 < 15 min (meta) |
| Planejado (10-5) | `LinkAcesso` com escopo e validade para assinatura; documento por URL de curta duração | minutos [estimativa] |

O canal de e-mail depende de `ContatoVerificado` (PLANEJADO) e da autorização do e-mail institucional pela
TI responsável. Sem contato verificado, o documento fica no portal e a entrega volta a ser manual.

## 8. Tempo humano economizado por fluxo

Nenhum desses tempos foi cronometrado. Os valores por unidade vêm das hipóteses escritas em cada fluxo,
quando existem; os que faltavam estão marcados como hipótese deste documento. **Cada fluxo define a
medição de antes e depois; só o número medido deve ser publicado.**

| Fluxo | Tempo manual por unidade | Unidades por viagem | Min por viagem | Origem do tempo |
|---|---|---:|---:|---|
| 10-2 envio de documentos | 2 min por destinatário (documento coletivo); 3 min por termo individual | 4 + 4 | 20 | hipótese do fluxo 10-2 |
| 10-3 aviso de saque e cobrança | 1,5 min por aviso ou cobrança | 4 + 4 | 12 | **hipótese deste documento** (o 10-3 manda medir) |
| 10-4 link de KM | 5 min por diário (pedir, esperar, digitar, corrigir) | 0,8 | 4 | hipótese ("alguns minutos" no 10-4) |
| 10-5 DB/RT para assinatura | ~8 min por documento (3 envio + 2 × 1,5 cobrança + 2 anexar) | 5 docs | 40 | hipótese do fluxo 10-5 |
| 10-6 recebimento (só comprovantes; DB/RT já contados no 10-5) | 2–4 min por arquivo (usado: 3) | 4 | 12 | hipótese do fluxo 10-6 |
| 11-1 rotas e roteiros | 5–10 min por roteiro de um destino (usado: 7,5) | 1 | 7,5 | hipótese do fluxo 11-1 |
| 10-1 assistente | sem linha de base | — | — | não estimado |
| **Bruto** | | | **95,5** | |
| Desconto: exceções (H9) | 23,2 comunicações × 5 % × 10 min + 8,8 recebimentos × 10 % × 3 min | | −14,2 | hipótese |
| **Líquido** | | | **~81** | |

**Sensibilidade** [hipótese]:

| | 50 viagens/mês | 200 viagens/mês | 500 viagens/mês |
|---|---:|---:|---:|
| Bruto | 80 h | 318 h | 796 h |
| Líquido (contato verificado para 100 % dos servidores) | 68 h | 271 h | 677 h |
| Líquido com contato verificado para 60 % dos servidores (fator aplicado a todos os fluxos menos o 11-1) | 43 h | 173 h | 431 h |

Cuidados de leitura:

- O ganho só aparece para quem tem **contato verificado**. Hoje os servidores viajantes não têm e-mail no
  cadastro nem acesso ao sistema; a cobertura real precisa ser medida antes de qualquer previsão.
- Tempo economizado é tempo **liberado** para outras tarefas, não despesa cortada.
- A troca do WhatsApp manual pelo e-mail/portal muda o canal que o servidor usa hoje. Se ele não abrir o
  e-mail, a cobrança volta para o operador. A adesão também precisa ser medida. O WhatsApp assistido com
  registro (frente WA-1) mantém o canal conhecido, mas com um envio manual por servidor: o ganho é de
  trilha e de texto pronto, não de tempo de envio.
- Assinatura, decisão de despacho, aprovação da prestação e tramitação no eProtocolo continuam humanas e
  **não** entram na conta.

## 9. CPU, memória, disco e conexões

### 9.1 O que a VPS tem e usa [medido]

| Recurso | Total | Uso 09–13/10 (só GV e EV) | Uso 14–17/10 (com o PREVIEW) |
|---|---|---|---|
| CPU | 2 vCPU (AMD EPYC 9354P) | média 1,5–2,4 %, pico 18 % | média 12–14 %, pico 45 % |
| Memória | 7,8 GiB | pico 30 %; mínimo disponível 5,2 GB | pico 46 %; **mínimo disponível 3,8 GB** |
| Disco | 96 GB NVMe | 52 GB livres após o backup; ~21 IOPS; ~0,9 MB/s leitura e ~0,8 MB/s escrita | |
| Rede | — | ~8 kB/s | |

### 9.2 O que o n8n acrescenta

| Item | Valor | Marca |
|---|---|---|
| Memória do n8n em repouso | **391 MiB** antes dos testes (45 s parado; inclui o runner JS interno) e 407 MiB depois; `docker stats` (faixa nas rodadas com a mesma espera: 390–400 MiB antes e 382–632 MiB depois; 450–781 MiB nas rodadas que mediam só 20 s após subir) | [medido no protótipo, execução final, SQLite] |
| Pico durante os testes | **884 MiB** na rajada de 20 simultâneos (mediana 472 MiB; T10 713 MiB); faixa nas rodadas: 670–1.036 MiB | [medido no protótipo] |
| Requisito oficial mínimo | não publicado. A tabela ilustrativa das páginas de pré-requisitos do n8n embutido (OEM), "baseada no n8n Cloud", traz 320 MB–2 GB de RAM e 512 MB–4 GB de SSD para o banco; o guia Hetzner diz que o CPX11 basta para a maioria dos usos e pede ≥ 4 GB e 2 vCPU só se o n8n Assistant for usado | [fonte oficial] |
| Capacidade de referência | página oficial de medição de desempenho: até 220 execuções/s numa instância única; o exemplo de referência roda numa c5a.large de 4 GB, **em modo main e com PostgreSQL** (o protótipo usou SQLite). O volume da PCPR (≤ 0,02/s em média) está 4 ordens de grandeza abaixo | [fonte oficial] |
| Banco do n8n | protótipo, depois da bateria completa: `database.sqlite` 4,8 MiB + WAL 4,0 MiB ≈ **8,8 MiB** (faixa nas rodadas: 7,9–8,9 MiB), com 5 fluxos importados e todas as execuções salvas | [medido] |
| Banco do n8n em produção, sem salvar execuções de mensagem | < 1 GB por ano | [estimativa] |

**Consequência:** o orçamento de memória do n8n fica em **1,5 GB no total**: `mem_limit` de **1 GB** no
contêiner principal e **0,5 GB** no runner de código externo (`n8nio/runners`, que substitui o runner
interno obsoleto), mais o banco do n8n (seção 14.2). O 1 GB do principal se justifica assim: o pico da
execução final (884 MiB) e o pior caso das rodadas (1.036 MiB) foram medidos com o runner **dentro** do
mesmo contêiner e com 20 eventos simultâneos sem limite de concorrência; em produção o runner sai do
contêiner e a concorrência fica limitada (seção 14.3). Os 0,5 GB do runner são [estimativa]. **Revisar os
dois valores depois de medir na VPS com PostgreSQL** (o mesmo valor vale para
[arquitetura.md](arquitetura.md) §5, [hospedagem-n8n.md](../ops/mudanca-hospedagem/hospedagem-n8n.md) e a
ficha de AUT-99). Com o n8n ocupando 0,4–1,5 GB, a memória disponível mínima cairia de 3,8 GB para
~2,3–3,4 GB. Ainda cabem os picos de 300–500 MB por PDF (WeasyPrint/LibreOffice), mas **swap de 2–4 GB e
limite de memória por contêiner são pré-requisitos** ([hospedagem-n8n.md](../ops/mudanca-hospedagem/hospedagem-n8n.md)).

**Gatilho objetivo para o upgrade KVM 2 → KVM 4** (proposta): memória disponível mínima < 1,5 GB em 7 dias
de medição, qualquer acionamento do OOM killer, ou a entrada do sistema novo em produção ao lado dos dois
antigos. Sem isso, o upgrade não se justifica.

### 9.3 CPU

| Carga | Situação | Observação |
|---|---|---|
| n8n (entregas, reconciliação, leitura de caixa) | PLANEJADA | Majoritariamente espera de rede; CPU desprezível neste volume [estimativa] |
| Conversão e OCR dos recebimentos | EXISTENTE (importador com LibreOffice, Poppler e Tesseract; concorrência 2 em produção) | 440–4.400 arquivos/mês nos cenários; tempo por página **não medido**. A fila já limita a concorrência; medir antes do cenário 500 |
| PDFs do worker | EXISTENTE | picos de 300–500 MB de memória por PDF |
| IA local | não recomendada | ver 11.4 |

### 9.4 Disco

| Item | Volume | Marca |
|---|---|---|
| Execuções do n8n | sem salvar execuções nos fluxos de mensagem e de arquivo, e só erros nos demais: centenas por mês. Salvando tudo: 11–36 mil por mês | [estimativa] |
| Binários no n8n | só os anexos que passam pela caixa postal (IMAP → `POST /recebimentos`), apagados ao fim da execução; documentos do PCPR **não** passam pelo n8n | desenho |
| Documentos recebidos | 440–4.400 arquivos/mês; a 0,3–1 MB cada, ~0,1–4,4 GB/mês | [estimativa]: crescimento dos documentos em si, que existiria também com envio manual |
| Folga | 52 GB livres | [medido] |

### 9.5 Conexões

| Conexão | Quantidade | Regra |
|---|---|---|
| n8n → API do PCPR | ≤ limite de concorrência do n8n | 2–3 simultâneas no máximo (seção 4) |
| PCPR → webhook do n8n | 1 por vez por worker de entregas (lease) | já serializado pelo desenho; pela rede Docker interna, sem rota pública |
| n8n → PostgreSQL próprio | pool pequeno | contêiner PostgreSQL próprio do n8n (seção 14.2); não usa o cluster de produção nem o `max_connections` dele, e não tem acesso aos bancos dos sistemas |
| n8n → caixa postal | 1 IMAP persistente (IDLE) + varredura | depende de credencial institucional |
| n8n → SMTP | 1 por envio (ou reaproveitada) | limites do provedor na seção 10 |

## 10. Chamadas externas

| Destino | 50 viagens/mês | 200 | 500 | Limite publicado | Folga |
|---|---:|---:|---:|---|---|
| SMTP (e-mails) | 1.160 (~53 por dia útil) | 4.640 (~211/dia) | 11.600 (~527/dia) | Google Workspace: 2.000 mensagens/dia por usuário, 10.000 destinatários/dia, 3.000 externos/dia; SMTP relay: 10.000 mensagens/usuário/dia, 100 destinatários por transação [fonte oficial] | Folgada mesmo com pico de 3× a média no cenário 500 (~1.580/dia). **Não está confirmado que a PCPR use Workspace** (Celepar) |
| IMAP (recebimento) | 440 arquivos | 1.760 | 4.400 | — | — |
| Rotas: uso contínuo (pares novos) | ~50 | ~200 | ~500 | OpenRouteService gratuito, **no host `api.heigit.org`**: Directions 2.000/dia e 40/min (o host antigo `api.openrouteservice.org` opera com 10 % da cota desde 27/08/2026 e será desligado em 02–06/11/2026; seção 14.6); Google Routes Essentials: 10.000 grátis/mês [fonte oficial] | Folgada no host novo |
| Rotas: aquecimento único | 796 chamadas por sede (399 municípios do PR × 2 sentidos; o cache é direcional) | | | ORS: ~20 min por sede a 40/min; ~2 sedes por noite com a cota diária | Cabe na janela 02:00–05:00 do fluxo 11-1 |
| IA (rascunhos: 2,8 tarefas por viagem + 30 % de retrabalho) | ~180 chamadas | ~730 | ~1.820 | limites por conta do provedor (não pesquisados) | — |
| IA (assistente 10-1) | 2 por pergunta | | | idem | — |
| eProtocolo | 0 até haver credencial e autorização institucional | | | — | — |

## 11. Chamadas e consumo de IA

### 11.1 Uso seletivo

A IA só entra onde lê ou redige texto livre e devolve uma **proposta estruturada** que o sistema valida
([arquitetura.md](arquitetura.md), §1). Classificação das opções avaliadas neste documento:

| Uso | Classificação | Maturidade |
|---|---|---|
| Rascunho de contextualização e considerações do Plano | assistência por IA indicada | 3 |
| Rascunho narrativo do RT a partir dos números lançados | assistência por IA indicada | 3 |
| Rascunho de justificativa de antecedência | assistência por IA indicada | 3 |
| Leitura da programação em anexos da solicitação (fluxo 11-1) | assistência por IA indicada | 3, e precisa de decisão: o [ADR 0041](../adr/0041-importacao-documental-e-fila-de-download.md) veda enviar documentos da importação a IA externa |
| Assistente dos servidores (fluxo 10-1) | assistência por IA indicada (camada de IA); a base sem IA é dependente de desenvolvimento | 3 (IA) / 2 (base) |
| Classificação dos documentos importados | melhor execução pelo próprio sistema (classificador local existente, sem IA externa — ADR 0041) | 1 |
| Diárias, distâncias, KM, escolha de equipe, emissão | inadequada ou inviável atualmente: cálculo determinístico ou decisão humana; a IA não pode inventar esses dados | 5 |
| Modelo de IA local na VPS | inadequada ou inviável atualmente: ver 11.4 | 5 |
| Aquecimento do cache de rotas | automação determinística suficiente | 2 |
| Rotas pelo Google Routes | dependente de integração externa | 3 |

### 11.2 Tokens e custo por tarefa [estimativa]

Preços oficiais em US$ por milhão de tokens (entrada/saída), consultados em 17/10/2026: Claude Haiku 5.5
0,10/0,50 (prompts até 100 mil tokens); Claude Sonnet 5.5 2/10; Claude Opus 5.5 4/20; Gemini 3.5 Flash-Lite
0,30/2,50. Leitura de cache: Haiku 5.5 US$ 0,01 (0,1× a entrada); Sonnet 5.5 US$ 0,10 e Opus 5.5 US$ 0,20
(0,05×). A saída inclui o raciocínio do modelo, cobrado como saída; usar esforço baixo nos rascunhos.

**Ressalva sobre as contagens de tokens:** os números abaixo são estimativas e não dizem com qual
tokenizador foram feitos. A página oficial de preços informa que os modelos Claude 4.7 em diante (o que
inclui os três 5.5) usam um tokenizador novo que gera cerca de 30 % mais tokens para o mesmo texto. Os
custos podem estar subestimados em até ~30 %; contar com a API de contagem de tokens, no modelo escolhido,
antes de orçar.

| Tarefa | Entrada | Saída | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Gemini 3.5 Flash-Lite |
|---|---:|---:|---:|---:|---:|---:|
| Rascunho do Plano (instruções + dados do plano e da solicitação) | 4.000 | 1.000 | US$ 0,0009 | 0,018 | 0,036 | 0,0037 |
| Rascunho do RT | 5.000 | 1.500 | 0,0013 | 0,025 | 0,050 | 0,0053 |
| Rascunho de justificativa | 3.000 | 600 | 0,0006 | 0,012 | 0,024 | 0,0024 |
| Leitura de programação (≤ 20.000 caracteres por fonte) | 8.000 | 1.000 | 0,0013 | 0,026 | 0,052 | 0,0049 |
| Pergunta ao assistente (premissas do fluxo 10-1, com cache) | ~12.100 | 1.000 | 0,0012–0,0016 | 0,023–0,030 | 0,046–0,061 | ~0,006 (sem cache) |
| **Por viagem** (H8, com +30 % de retrabalho) | 18.070 | 4.134 | **0,0039** | **0,077** | **0,155** | **0,016** |

**Custo mensal só dos rascunhos** [estimativa]:

| | 50 viagens | 200 viagens | 500 viagens |
|---|---:|---:|---:|
| Haiku 5.5 | US$ 0,19 | US$ 0,77 | US$ 1,94 |
| Sonnet 5.5 | US$ 3,87 | US$ 15,50 | US$ 38,74 |
| Opus 5.5 | US$ 7,75 | US$ 30,99 | US$ 77,48 |
| Gemini 3.5 Flash-Lite | US$ 0,79 | US$ 3,15 | US$ 7,88 |

Somar o assistente (fluxo 10-1), que independe do número de viagens: 500 perguntas/mês ≈ US$ 0,8 (Haiku),
US$ 15 (Sonnet) ou US$ 30 (Opus); 5.000 perguntas/mês ≈ US$ 8, US$ 152 ou US$ 300. A avaliação também
custa: um gabarito de 200 perguntas rodado 3 vezes sai por ~US$ 2 (Haiku) a ~US$ 37 (Opus) por modelo e
por rodada (10-1).

### 11.3 Controles de consumo

- **Teto mensal no PCPR**: soma tokens × tabela de preços configurada; ao atingir o teto, o fluxo desliga
  com o motivo "orçamento" e avisa o administrador (desenho do 10-1). Limite por identidade (proposta:
  20 perguntas/hora, 60/dia).
- **A chamada ao modelo sai do PCPR, não do n8n**: mascaramento, política do usuário, registro de tokens e
  custo ficam num lugar só. No protótipo os recursos de IA do n8n estão desligados.
- **Cache de prompt**: só vale com prefixo estável acima do mínimo do modelo (512–4.096 tokens, conforme o
  modelo); instruções curtas podem não entrar no cache. Medir `cache_read_input_tokens`.
- **Lote (−50 %)** só para tarefas sem pressa (reavaliação do gabarito, não rascunho pedido na tela).
- **Retenção e uso dos dados**: pela API da Anthropic, entradas e saídas são apagadas em até 30 dias por
  padrão (política comercial de retenção) e não são usadas para treino sem permissão expressa; **conteúdo sinalizado por violação da
  política de uso pode ser retido por até 2 anos**, o que entra na análise de LGPD. ZDR só por acordo
  comercial; o lote (Batch) guarda os pedidos por 29 dias e a Files API guarda arquivos até serem apagados,
  ambos fora do ZDR. No Gemini, o nível **gratuito** usa o conteúdo para melhorar produtos e pode ter
  leitura humana: **proibido** para dados da PCPR. Mandar ao modelo só o necessário (sem CPF/RG).
- **Leitura de cache conferida na página oficial** (17/10/2026): Haiku 5.5 US$ 0,01 (0,1×); Sonnet 5.5
  US$ 0,10 e Opus 5.5 US$ 0,20 (0,05×). Os US$ 0,20 que apareciam para o Sonnet são do Sonnet 5, não do 5.5.

### 11.4 Modelo local na VPS: inviável

Base: README oficial do `llama-bench` — modelo de 7 B em Q4_0 (3,56 GiB), CPU com 2 threads: ~12,3 tokens/s
para ler o prompt e ~7,8 tokens/s para gerar (hardware não informado; vCPU compartilhada tende a render
menos). O Ollama indica ≥ 8 GB de RAM para modelos de 7 B.

| Tarefa | Conta | Tempo com as 2 vCPUs ocupadas |
|---|---|---|
| Rascunho do Plano | 4.000 / 12,3 + 1.000 / 7,8 | ~7,6 min |
| Pergunta ao assistente | 12.100 / 12,3 + 1.000 / 7,8 | ~18 min |
| Todos os rascunhos de uma viagem | 18.070 / 12,3 + 4.134 / 7,8 | ~33 min |
| 200 viagens/mês | | ~111 h/mês de CPU saturada |

Além do tempo, o modelo ocuparia 4–6 GB de memória numa máquina que tem 3,8 GB disponíveis no pior momento.
A qualidade também não ajuda: no artigo Tucano 2, a média em benchmarks de português foi 57,86 para
Qwen3-4B-Base, 44,48 para Qwen3-1.7B-Base e 40,50 para Llama-3.2-3B, e ~20–22 para modelos instruct de
~1 B. Nem o upgrade para KVM 4 (4 vCPU, sem GPU) muda a conclusão. **Classificação: inadequada ou inviável
atualmente (5).**

## 12. Taxa de falhas

**Não há medição de produção**: nada disto está implantado. O que existe:

| Evidência | Resultado |
|---|---|
| Protótipo, execução final (17/10/2026, 03:53–03:59, horário de Brasília) | **12 de 12 cenários passaram** (T1–T12, saída 0; [`resultados.json`](prototipo/resultados/resultados.json)). Nas rodadas de desenvolvimento, o T9 falhou uma vez (422 porque o *boundary* do multipart muda a cada reenvio) e passou depois da correção da impressão da requisição. As métricas desta execução continuam válidas |
| Protótipo, rodadas posteriores (17/10/2026, 21:47–22:05) | Repetiram T1–T12 com sucesso e introduziram o **T13** (busca, no banco do n8n, de destino, link-credencial, token de reserva e telefone retidos em execuções). Na última rodada o T13 **falhou**: 2 ocorrências do telefone do remetente em execuções de webhook do W4 (recebimento) com status `running`, mesmo com `saveData*` = `none`; zero ocorrências de destino, link e token do W2. **Achado em tratamento** (seção 14.7) |
| T6 — canal falha 1× e aceita | 1 envio efetivo, 1 resultado; 1,03 s entre as tentativas |
| T7 — canal sempre falha | 3 tentativas, exceção `limite_tentativas`, sem laço |
| T12 — erro inesperado num fluxo | o fluxo de erros abre exceção no PCPR |
| Outbox atual (EXISTENTE) | 8 tentativas com backoff 10 s → 640 s; ~21 min até `falhou` (`gestao/plataforma/outbox.py:34,72-73`). O ADR 0005 diz "5 s → 1 h" |

**Fontes de falha esperadas e resposta**

| Causa | Efeito | Resposta no desenho |
|---|---|---|
| SMTP fora do ar ou recusando | comunicação volta a `agendada` | Até 3 tentativas curtas no n8n, de segundos e **dentro da reserva de 10 min** (o W2 do protótipo usa ~1 s entre tentativas; a retentativa nativa do n8n aceita no máximo 5 s); depois `falha_temporaria`, e o PCPR reagenda com nova reserva e backoff até 4 h entre tentativas, por no máximo 24 h; depois exceção ([10-2 §8](fluxos/10-2-envio-de-documentos.md)) |
| n8n parado | eventos pendentes | Os ~21 min da outbox atual **não bastam**: o worker de entregas com lease (PLANEJADO) tenta por horas; a reconciliação recupera |
| Cota do provedor de rotas (ORS 403/429) | perna cai na estimativa com selo "km estimado" | "Recalcular rotas" quando a cota voltar |
| IA: tempo esgotado, recusa ou validação reprovada | rascunho não sai | Tela segue manual; retrabalho já está no +30 % de H8 |
| E-mail devolvido (bounce) | `entrega: falhou` | Exceção com o motivo; contato marcado para conferência |

**Metas propostas para ligar cada fluxo** (a confirmar): exceções < 2 % das comunicações depois do 1º mês;
zero duplicidade no canal; zero comunicação perdida (toda `devida` é enviada ou vira exceção em até 24 h).
Monitorar a fila é obrigatório: uma das referências já teve fila parada por semanas sem alerta (decisão
D3 do [plano](plano-implantacao.md)).

## 13. Duplicidades e reprocessamentos

| Mecanismo | Situação | Evidência |
|---|---|---|
| `id` estável do evento + deduplicação no n8n | PLANEJADO; validado no protótipo | T2: evento reenviado 2× → 1 envio, 0 chamadas novas ao PCPR; 5 entregas simultâneas → 1 envio |
| Reserva com `Idempotency-Key` única por tentativa e versão no PCPR | PLANEJADO; validado | T1 (1 envio, 1 resultado, 1 reserva); T2c (evento com outro id para a mesma comunicação → reservar 409 `ja_processada`); T4 (reagendada/versão antiga → 409, 0 envio) |
| Chave geral desligada | PLANEJADO; validado antes da reserva | T5: desligada antes → o W2 encerra, 0 reservas; desligada entre `/estado` e `reservar` → 423, nada enviado, comunicação segue `agendada`; religada, a reconciliação envia 1×. **Não testado:** desligar entre `reservar` e `resultado` (o `resultado` precisa ser aceito; cenário T5d proposto em [arquitetura.md](arquitetura.md) §3.10) |
| Evento perdido | PLANEJADO; validado | T8: a reconciliação envia 1 vez |
| Reinício do n8n no meio | PLANEJADO; validado | T10: 0 duplicados no canal; **as 4 comunicações em curso viraram exceção "resultado desconhecido"** (o canal tinha recebido 1 vez cada); as 2 cujos eventos se perderam com o n8n fora saíram pela reconciliação |
| Recebimento duplicado | PLANEJADO; validado | T9: 2 webhooks do canal com o mesmo id → 2 `POST /recebimentos` com a mesma chave (no protótipo, `recebimento:<canal>:<id>`; no contrato rascunho 3, `receb:<canal>:<mensagem_id_canal>:<anexo_indice>`) → 1 recebimento (a 2ª chamada é repetição idempotente, `Idempotency-Replayed: true`), SHA-256 conferido. Limite: o canal do T9 é fictício, no formato de webhook; a leitura por IMAP e o envio por SMTP reais só estão desenhados |

**Custo de reprocessar:** quando o resultado é desconhecido, o PCPR não reenvia às cegas e abre exceção para
uma pessoa conferir. Cada reinício do n8n durante envios gera trabalho humano (no T10, 4 conferências).
Regra operacional: atualizar ou reiniciar o n8n fora da janela de envios agendados, com aviso prévio.

**Reprocessar a partir de onde:** os fluxos de mensagem e de arquivo não guardam execuções (nem de sucesso
nem de erro; seção 14.7), então não há o que repetir no n8n. Isso é intencional: **a fonte de
reprocessamento é o PCPR** (comunicações `devidas`, exceções com "repetir"), não o histórico do n8n.

## 14. Arquitetura proporcional

### 14.1 Instalação simples × queue mode

| Critério | Modo normal (um processo `main`) | Queue mode |
|---|---|---|
| Componentes | n8n + PostgreSQL | n8n `main` + workers + **Redis** + PostgreSQL compartilhado |
| Dados binários | em disco (`filesystem`, padrão do modo normal na 2.x) | **no banco**: o modo em disco não é suportado em queue mode [fonte oficial] |
| Memória | 391 MiB em repouso e pico de 884 MiB na execução final do protótipo (faixa nas rodadas: 670–1.036 MiB), com SQLite e runner interno | + Redis + cada worker (outro processo Node; ~0,2–0,5 GB cada [estimativa]); o template da Hostinger sobe 3 workers |
| Latência | p50 ~0,31 s do evento ao envio, em série, no protótipo | **não é menor**: os fluxos esperam APIs externas, e a fila acrescenta um salto |
| Quando faz sentido | volume da PCPR (≤ 0,02 execução/s em média) | centenas de execuções simultâneas medidas, ou isolamento de carga pesada |
| Edição | Community | Community (queue mode incluído); multi-main só Enterprise |
| **Decisão** | **adotar** | descartado neste porte |

### 14.2 Compatibilidade modo × banco × binários × edição

| Modo | Banco do n8n | Binários | Edição | Situação |
|---|---|---|---|---|
| Normal | PostgreSQL 17 ou 18 em **contêiner próprio do n8n** | disco | Community | **recomendado**: rede Docker do n8n, sem porta publicada, dump próprio no backup ([hospedagem-n8n.md](../ops/mudanca-hospedagem/hospedagem-n8n.md)) |
| Normal | PostgreSQL 16 do cluster existente | disco | Community | **não recomendado**: o 16 é aceito só "por compatibilidade" e a faixa suportada muda todo novembro (o PostgreSQL 19 tem lançamento previsto para 19/11/2026); o contêiner também não alcança o `127.0.0.1` do host sem abrir o cluster de produção à rede Docker |
| Normal | SQLite (padrão do n8n) | disco | Community | usado no protótipo local; em produção, preferir PostgreSQL |
| Queue | PostgreSQL + Redis | banco | Community | suportado; não recomendado aqui |
| Queue | SQLite | — | — | não recomendado nem suportado em configuração distribuída |
| Qualquer | — | S3/Azure | Business/Enterprise | fora: sem licença o n8n não inicia em modo S3 |
| Multi-main | — | — | Enterprise | fora |

Não foi confirmado se o modo "binários no banco" pode ser escolhido no modo normal; não é necessário.

### 14.3 Concorrência limitada

Limitar as execuções de produção simultâneas a 2–3 nos fluxos que chamam o PCPR (seção 4) e a ≤ 5 no total
([arquitetura.md](arquitetura.md)). O modo normal tem controle de concorrência próprio, a variável
`N8N_CONCURRENCY_PRODUCTION_LIMIT`, mas ele vem **desligado por padrão**: sem configuração explícita não há
limite nenhum. Ela só conta execuções de produção iniciadas por webhook ou gatilho; ficam de fora as
execuções manuais, os sub-workflows (Execute Workflow), o workflow de erro e as execuções pela CLI. Por
isso o limite de chamadas ao PCPR depende também do desenho: o W3 chama o W2 em série (Loop Over Items, lote
1), e o W2 chamado como sub-workflow não entra na conta. O importador já roda com concorrência 2.

### 14.4 Eventos em vez de polling excessivo

- O caminho normal é o **evento** (push). Ficam três consultas periódicas, todas de 15 min: reconciliação
  (`devidas`), varredura da caixa postal e monitor de filas.
- O n8n **nunca** varre listas de tela (por exemplo `/viagens/prestacoes/`, 848 KB) para descobrir
  mudanças; consulta só endpoints indexados da API de automação.
- O "polling" para a vida do servidor (agenda da véspera, prazos de saque) é **agendamento no PCPR**
  (outbox com `disponivel_em` e rotinas diárias), não laço no n8n.

### 14.5 Limites e retentativas por provedor

| Provedor | Limite publicado [fonte oficial] | Retentativa proposta |
|---|---|---|
| OpenRouteService (gratuito) | No host `api.heigit.org`: Directions 2.000/dia e 40/min; estouro diário → 403, por minuto → 429; o diário vence 24 h após a 1ª requisição; atribuição HeiGIT/OpenStreetMap obrigatória. O host antigo tem só 10 % da cota desde 27/08/2026 (seção 14.6) | Sem retentativa na tela (cai na estimativa); aquecimento noturno a ≤ 30/min; parar no 1º 403 |
| Google Routes (Essentials) | US$ 5,00 por mil, com 10.000 grátis por mês (Pro: US$ 10 com 5.000; Enterprise: US$ 15 com 1.000) | Mesma regra; alerta de faturamento |
| SMTP (Workspace, se for o caso) | 2.000 mensagens/dia por usuário; relay 10.000/dia; 100 destinatários por transação | Até 3 curtas (segundos) no n8n, dentro da reserva de 10 min; depois o PCPR reagenda com backoff até 4 h (seção 12) |
| Anthropic / Gemini | limites por conta (não pesquisados) | 2 tentativas em erro 429/5xx, depois exceção; teto de custo no PCPR |
| Outbox → n8n | — | worker de entregas com lease, backoff por horas (PLANEJADO), em vez dos ~21 min atuais |

### 14.6 Cache de rotas existente

- EXISTENTE: `DistanciaMunicipios` (`gestao/viagens/models.py:537-555`), par direcional, versionado pela
  fórmula de tempo ([ADR 0024](../adr/0024-versionar-formula-no-cache-de-rotas.md)), **sem expiração**.
  A estimativa (linha reta × 1,3) **não** é cacheada. Hoje a configuração padrão é `estimativa`, e o PREVIEW
  usa o servidor público de demonstração do OSRM, que não serve para produção (uso justo, sem garantia).
- Achado: o adaptador do ORS usa por padrão `https://api.openrouteservice.org` (`gestao/viagens/rotas.py:110`).
  Esse host está **oficialmente depreciado desde 28/04/2026**, opera com **10 % da cota** dos planos desde
  27/08/2026 (cerca de 200 rotas/dia em vez de 2.000; o anúncio de abril previa a redução para 24/08) e
  será **desligado em 02–06/11/2026**. O host novo inclui o nome do serviço no caminho
  (`api.heigit.org/openrouteservice/v2/directions`), e a chave atual já vale nele. Como `rotas.py:110`
  concatena `/v2/directions/...` à base, a configuração correta é
  `ROTAS_URL=https://api.heigit.org/openrouteservice`; `ROTAS_URL=https://api.heigit.org` faria a chamada
  falhar. Trocar também o padrão de `rotas.py:110`. As duas referências em produção têm o host antigo fixo no
  código e perdem o ORS no desligamento ([inventário](inventario-processos.md), GV-ROTEIRO-DIARIAS e
  EV-ROTA-DISTANCIA).
- Com o cache aquecido para as sedes, o consumo contínuo fica em dezenas a centenas de chamadas por mês —
  bem abaixo das cotas gratuitas.
- **Não pesquisado:** os termos do Google Maps Platform sobre armazenamento de resultados. Uma tabela
  permanente de distâncias pode conflitar com eles; confirmar antes de usar o Google com o cache atual.
- OSRM próprio para a região Sul: ~1–3 GB de RAM para servir (extrapolação linear, não confirmada) mais o
  pré-processamento; disputaria memória com os sistemas. Só se as APIs não servirem.

### 14.7 Retenção de execuções

| Configuração | Padrão do n8n [fonte oficial] | Proposta |
|---|---|---|
| Poda | ligada; 336 h (14 dias) ou 10.000 execuções, o que vier primeiro; buffer de exclusão de 1 h | manter ligada; 168 h (como no protótipo) |
| Salvar sucesso | sim | **não** em nenhum fluxo (`EXECUTIONS_DATA_SAVE_ON_SUCCESS=none`) |
| Salvar erro | sim | **não** nos fluxos de mensagem e de arquivo (ajuste do fluxo: `saveDataErrorExecution: none`), porque a resposta do `reservar` traz destino e link, que é credencial; sim nos demais. O diagnóstico dos fluxos de mensagem sai pelo fluxo de erros, só com metadados (nó, código, id da execução) |
| Salvar progresso e execuções manuais | progresso não; manuais sim | não (`EXECUTIONS_DATA_SAVE_ON_PROGRESS=false`; `saveManualExecutions: false`) |
| Execuções anotadas | não são podadas | evitar anotar execuções com dados pessoais |

Se tudo fosse salvo, o limite de 10.000 cortaria o histórico antes dos 14 dias no cenário 500 (~1.200
execuções/dia → ~8 dias). Sem salvar as execuções de mensagem, a questão desaparece, e links e contatos não
se acumulam no n8n nem nos backups dele. "Só erros" não bastaria: qualquer falha de SMTP guardaria o link.
Na primeira rodada o protótipo salvou tudo (padrão da imagem); desde a segunda, W2 e W4 não guardam
execução e W1/W3 só guardam erros, e o T13 confere a retenção.

**Achado do T13 (em tratamento).** No n8n 2.43.7, execuções disparadas por webhook do W4 ficaram no banco
com status `running` e o número do remetente **mesmo com** `saveData*` = `none` (2 ocorrências na última
rodada; zero para destino, link e token do W2). "Não salvar execução" não basta, portanto, para entradas
por webhook com dado pessoal: o recebimento deve preferir a entrada direta no PCPR (portal) ou prever a
limpeza dessas execuções. A escolha sai do resultado do protótipo da frente WA-3, em andamento.

### 14.8 Arquivos por referência

- O n8n recebe **ids e URLs** (portal autenticado ou URL assinada de curta duração), nunca o PDF do PCPR.
- A única passagem de binário pelo n8n é o anexo lido da caixa postal a caminho de `POST /recebimentos`:
  em disco, no modo normal, apagado com a execução. Limite de payload do webhook: 16 MiB.
- Documentos ficam no armazenamento privado do PCPR, com hash (versão congelada).

### 14.9 Hostinger: o que cada operação faz

| Operação | Efeito [fonte oficial] | Uso |
|---|---|---|
| Aplicar o template "Ubuntu 24.04 with n8n" | é reinstalar o sistema operacional: **apaga todos os dados da VPS, inclusive o snapshot**; Docker Compose com rótulos do Traefik (que ocuparia 80/443 é inferência a partir da imagem do artigo, não texto da página); a variante queue mode sobe Redis e 3 workers | **não usar** na VPS atual |
| Upgrade de plano (KVM 2 → KVM 4) | preserva arquivos e configurações; leva até 10 min; não se aumenta só RAM ou disco | só com o gatilho da seção 9.2 |
| Managed n8n ("AI Automation apps") | servidor gerenciado pela Hostinger; a página lista só quatro aplicações (Hermes Agent, OpenClaw, n8n e Paperclip) e não menciona hospedar aplicação própria; CPU/RAM, SSH e limites **não informados** | opcional; testar antes. Não hospeda os sistemas Django/PostgreSQL (não verificado; nenhuma indicação de que aceite). Com o n8n fora da VPS, a API do PCPR precisaria ficar acessível pela internet para ele |
| Backup | semanal gratuito (VPS inteira); diário pago, sem preço público; até 4 retidos; 1 snapshot manual que expira em 1 dia | não substitui `pg_dump` com cópia externa ([backup-e-recuperacao.md](../ops/mudanca-hospedagem/backup-e-recuperacao.md)) |

## 15. Custos

### 15.1 Premissas

- Preços de vitrine consultados em 17/10/2026. **O contrato atual da VPS (preço e prazo) não foi visto**; o
  valor de renovação vale como referência. O prazo exato das promoções não está claro nas páginas.
- Câmbio de referência **R$ 5,15 por US$** [estimativa]: é a razão entre as tarifas em BRL e em USD da
  calculadora oficial da Meta (R$ 0,0350 / US$ 0,0068). Impostos e IOF de compra internacional **não**
  incluídos. A forma de contratar e pagar serviço estrangeiro (cartão corporativo, empenho, revenda
  nacional) é questão institucional a confirmar.
- Mão de obra fica fora dos valores em reais e aparece em horas.

### 15.2 Cenário básico (VPS atual, n8n Community, e-mail institucional, IA desligada ou mínima)

| Item | Escolha | Custo mensal adicional | Limitações explícitas |
|---|---|---|---|
| Hospedagem | KVM 2 atual (vitrine R$ 43,99 promocional; R$ 77,99 na renovação) | **R$ 0** (já contratado) | Memória justa: swap e limites antes de instalar |
| n8n | Community auto-hospedado, modo normal | **R$ 0** de licença | Sem SSO (login separado), sem compartilhamento de fluxos (conta técnica única), sem log streaming nem armazenamento externo de binários; uso interno permitido pela licença (sem posição oficial sobre órgão público) |
| Mensageria | e-mail institucional + portal | **R$ 0** se o e-mail institucional estiver liberado | Depende da TI institucional (Workspace via Celepar **não confirmado** para a PCPR); servidores sem e-mail cadastrado; sem SMTP institucional, o envio automático não existe |
| WhatsApp | assistido com registro (WA-1), pelo aparelho institucional | **R$ 0** de mensagem | Plataforma oficial **bloqueada** pela política da Meta; integração pronta e desligada (WA-3) só gera custo após a ativação; ver 15.5 |
| IA | desligada, ou Haiku 5.5 com teto | R$ 0 a ~R$ 10 (rascunhos de 200 viagens + 500 perguntas ≈ US$ 1,6); ~R$ 50 com 500 viagens e 5.000 perguntas (≈ US$ 9,9) | Sem IA não há rascunho nem assistente; com Haiku, qualidade a avaliar no gabarito |
| Mapas | estimativa (linha reta × 1,3) ou ORS gratuito com cache | **R$ 0** | Estimativa é imprecisa; ORS exige atribuição e confirmação de uso institucional (licença dos resultados CC-BY ou CC-BY-SA, divergente nas páginas) |
| Armazenamento | disco da VPS (52 GB livres) | **R$ 0** | Crescimento dos documentos (seção 9.4) |
| Backup | semanal da Hostinger + cópia externa em HD local (decisão D1) | **R$ 0** em serviço; custo do HD não orçado | Cópia externa manual; risco de esquecer |
| Operação | atualizar a imagem fixada, conferir alertas, tratar exceções técnicas | — | **2–4 h/mês** [estimativa] |
| Desenvolvimento | fundação no PCPR (etapa 1) e fluxos | — | Maior custo do plano, em horas (tamanhos M/G nos fluxos) |
| **Total em dinheiro** | | **R$ 0 a ~R$ 10/mês** (200 viagens); até ~R$ 50 (500 viagens) | |

### 15.3 Cenário ampliado

| Item | Escolha | Custo mensal adicional | Observação |
|---|---|---|---|
| Hospedagem | upgrade para KVM 4 **se medido** (R$ 59,99 promocional; R$ 149,99 na renovação) | **+R$ 16 a +R$ 72** sobre o KVM 2 | Preço de upgrade para contrato existente não confirmado |
| n8n gerenciado (opcional) | Hostinger "AI Automation apps" | R$ 29,99 (24 meses) / R$ 39,99 (12 meses) / R$ 54,99 (mensal); renovação R$ 59,99, sem impostos | Recursos não informados; não substitui a VPS; n8n Business (667 EUR/mês, 40 mil execuções) fica fora de alcance |
| IA paga | Sonnet 5.5 nos rascunhos e no assistente | ~US$ 4–191 (≈ R$ 20–980), conforme volume (tabela 15.4) | Teto mensal no PCPR; avaliação antes de ligar |
| Mapas | Google Routes Essentials | **US$ 0** dentro de 10.000 chamadas/mês; US$ 5 por mil acima | Exige conta de faturamento com cartão; termos de cache não pesquisados |
| Backup externo pago | armazenamento externo para o `restic` (já implementado em `deploy/vps/backup.sh`) | **a orçar** (não pesquisado) | Backup diário da Hostinger: preço não público |
| Mensageria | e-mail institucional | R$ 0 | Plataforma oficial do WhatsApp continua bloqueada; WA-1 assistido sem custo de mensagem |
| **Total em dinheiro** | | **~R$ 100 a ~R$ 1.050/mês** + backup externo (+ R$ 30–60 se o n8n gerenciado for contratado) | Faixa baixa: 50 viagens, sem upgrade, Sonnet nos rascunhos e 500 perguntas (US$ 18,87 ≈ R$ 97); faixa alta: 500 viagens, KVM 4 na renovação (+R$ 72), Sonnet nos rascunhos e 5.000 perguntas (US$ 190,74 ≈ R$ 982) |

### 15.4 Sensibilidade (50 / 200 / 500 viagens por mês)

| | 50 | 200 | 500 |
|---|---:|---:|---:|
| Comunicações/mês | 1.160 | 4.640 | 11.600 |
| E-mails por dia útil (média) | 53 | 211 | 527 |
| Arquivos recebidos/mês | 440 | 1.760 | 4.400 |
| Execuções do n8n/mês (8.670 fixas + 55 por viagem) | 11.430 | 19.710 | 36.270 |
| Rotas: chamadas novas/mês (após o aquecimento) | ~50 | ~200 | ~500 |
| IA rascunhos — Haiku 5.5 | US$ 0,19 | US$ 0,77 | US$ 1,94 |
| IA rascunhos — Sonnet 5.5 | US$ 3,87 | US$ 15,50 | US$ 38,74 |
| IA rascunhos — Opus 5.5 | US$ 7,75 | US$ 30,99 | US$ 77,48 |
| Assistente (500 ou 5.000 perguntas) — Sonnet 5.5 | US$ 15–152 | US$ 15–152 | US$ 15–152 |
| Mapas — ORS gratuito / Google Essentials | R$ 0 / US$ 0 | R$ 0 / US$ 0 | R$ 0 / US$ 0 |
| Hospedagem adicional | R$ 0 | R$ 0 (KVM 4 só com gatilho) | provável gatilho → +R$ 16–72 |
| WhatsApp (informativo; **bloqueado**) | R$ 40,60 | R$ 162,40 | R$ 406,00 |
| Tempo humano líquido (100 % / 60 % de cobertura) | 68 h / 43 h | 271 h / 173 h | 677 h / 431 h |
| Operação técnica | 2–4 h | 2–4 h | 3–6 h [estimativa] |

No cenário 500, as execuções do n8n chegam perto das 40 mil incluídas no plano Business. Isso só importaria
num plano cobrado por execução (supondo que cada disparo agendado conte como execução, o que não foi
confirmado), e é mais uma razão para não reduzir o intervalo do pull.

### 15.5 Custo informativo do WhatsApp oficial (não aplicável enquanto bloqueado)

Tarifas oficiais para destinatário no Brasil, por mensagem entregue (tabela vigente desde 01/07/2026):
utility R$ 0,0350 (até 250 mil/mês); authentication R$ 0,0350; marketing R$ 0,3217; service (mensagem livre
na janela de 24 h) R$ 0,0350, cobrada desde 01/10/2026 segundo a página de mensagens não-template e a
calculadora — a página principal ainda diz que é grátis. A linha de 15.4 multiplica as comunicações pela
tarifa utility. **Não se aplica**: a política oficial (seção de uso governamental, atualizada em 23/09/2026)
lista autoridades policiais entre os usuários proibidos do WhatsApp Business Platform, sem processo de
exceção, e provedores de solução também recusam polícia. Não há integração WhatsApp ativa em produção:
os sistemas usam links click-to-chat abertos à mão pelo operador. Com a prioridade definida pelo usuário
(17/10/2026), esse link vira o envio assistido com registro (WA-1), sem custo de mensagem; a tabela acima só
passa a valer se a integração oficial, pronta e desligada (WA-3), passar pelo portão de ativação (autorização
escrita da Meta, pedida pela consulta formal WA-2).

### 15.6 O que impede chamar de "custo zero"

1. Desenvolvimento da fundação no PCPR (API, eventos, comunicações, exceções, links) antes de qualquer fluxo.
2. Operação: atualizações com backup prévio, alertas, conferência de execuções com erro.
3. Exceções de negócio: cada "resultado desconhecido", contato inválido ou recusa vira trabalho humano
   (descontado na seção 8).
4. Cópia externa do backup, incluindo a chave de criptografia do n8n guardada fora da VPS.
5. Renovação da VPS: o KVM 2 passa de R$ 43,99 para R$ 77,99 na vitrine.
6. Aumento de memória se o sistema novo entrar em produção ao lado dos antigos.

## 16. Decisões a confirmar e pendências

| # | Decisão ou pendência | Quem |
|---|---|---|
| 1 | Volumes reais (seção 3): viagens/mês, servidores por viagem, % com viatura, sedes, documentos devolvidos | usuário |
| 2 | Provedor de rotas em produção (estimativa, ORS gratuito ou Google Routes) e aceitação dos termos | usuário |
| 3 | Provedor de IA, modelo e teto mensal (decisão "provedor de IA" do [plano](plano-implantacao.md), hoje D8); forma de contratação por órgão público; ZDR | usuário / instituição |
| 4 | IA externa em anexos de solicitação diante do ADR 0041 | usuário |
| 5 | Conferir o orçamento de memória do n8n (1 GB no principal + 0,5 GB no runner externo, seção 9.2) medindo na VPS com PostgreSQL | técnico |
| 6 | Retenção de execuções: 7 dias; nenhuma execução salva nos fluxos de mensagem e de arquivo (seção 14.7). Tratar o achado do T13 (execuções de webhook do W4 retidas como `running` com o telefone do remetente): entrada direta no PCPR ou limpeza dessas execuções, com o resultado do protótipo da WA-3 | técnico |
| 7 | Backup externo: HD local (D1) ou armazenamento pago | usuário |
| 8 | E-mail institucional: Workspace/Celepar, SMTP relay, IMAP e limites aplicáveis | TI institucional |
| 9 | Cobertura de contato verificado dos servidores viajantes | usuário |
| 10 | Medir no PREVIEW: tempo do PDF/A no worker, OCR por página, latência real de IA e SMTP | técnico |
| 11 | Protótipo: rodar o cenário T5d (chave desligada entre `reservar` e `resultado`) e o recebimento com `canal=email` (chave do contrato `receb:email:<mensagem_id_canal>:<anexo_indice>`); a execução final (12/12) e o README com as métricas já existem; o T13 falhou nas rodadas de 21:47–22:05 (item 6) | técnico |
| 12 | Trocar o host do ORS antes de 02–06/11/2026, se o ORS for adotado (seção 14.6) | técnico |

## Fontes

Consultadas em **17/10/2026**, salvo indicação.

**Medições do projeto**

- Capacidade da VPS, 09–17/10/2026: [`../ops/mudanca-hospedagem/capacidade-vps.md`](../ops/mudanca-hospedagem/capacidade-vps.md)
- Hospedagem do n8n: [`../ops/mudanca-hospedagem/hospedagem-n8n.md`](../ops/mudanca-hospedagem/hospedagem-n8n.md)
- Tempos do PREVIEW: medição por `curl` em 17/10/2026 ~06:10 UTC (tabela da seção 4)
- Protótipo: [`prototipo/README.md`](prototipo/README.md) (seções "Resultados" e "Métricas") e [`prototipo/resultados/resultados.json`](prototipo/resultados/resultados.json), execução final de 17/10/2026, 03:53–03:59 (horário de Brasília); rodadas posteriores de 21:47–22:05, com o T13

**n8n**

- Versão estável 2.43.7 (16/10/2026): https://github.com/n8n-io/n8n/releases
- Queue mode: https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode.md
- Bancos suportados (PostgreSQL 17 e 18 "as of July 2026"; 16 por compatibilidade; a faixa muda todo novembro): https://docs.n8n.io/deploy/host-n8n/configure-n8n/choose-n8ns-database.md
- Controle de concorrência (desligado por padrão; não conta sub-workflows, erros, manuais nem CLI): https://docs.n8n.io/hosting/scaling/concurrency-control/
- Mudanças da 2.0 (binários em disco no modo normal e no banco em queue mode; S3 só com licença): https://docs.n8n.io/2-0-breaking-changes/
- Poda e dados de execução: https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/manage-execution-data.md
- Recursos da edição Community: https://docs.n8n.io/deploy/host-n8n/community-edition-features.md
- Licença (FAQ): https://docs.n8n.io/n8n-community-license/community-license/license-faq
- Preços (Business 667 EUR/mês, 40 mil execuções): https://n8n.io/pricing/
- Webhook (payload de 16 MiB, autenticação): https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook.md
- Backup e restauração: https://docs.n8n.io/deploy/host-n8n/keep-n8n-running/backup-and-restore.md
- Guia Hetzner (CPX11 basta para a maioria dos usos; ≥ 4 GB e 2 vCPU com o n8n Assistant): https://docs.n8n.io/deploy/host-n8n/install-options/use-a-cloud-provider/deploy-to-hetzner
- Tabela ilustrativa de recursos (320 MB–2 GB de RAM; 512 MB–4 GB de SSD para o banco), pré-requisitos do n8n embutido: https://docs.n8n.io/deploy/host-n8n/deploy-as-an-oem-integration/prerequisites
- Medição de desempenho (até 220 execuções/s numa instância; exemplo c5a.large de 4 GB, modo main, PostgreSQL): https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/measure-performance.md

**Hostinger**

- Trocar o sistema operacional apaga a VPS (inclui template): https://www.hostinger.com/support/4965922-how-to-change-the-operating-system-of-your-vps-at-hostinger/
- Template n8n (Docker Compose; rótulos do Traefik só na legenda de uma imagem; variante queue mode com Redis e 3 workers): https://www.hostinger.com/support/10473267-how-to-use-the-n8n-vps-template-at-hostinger/
- Upgrade preserva os dados (até 10 min): https://www.hostinger.com/support/1583229-how-to-upgrade-a-vps-server
- Backups e snapshots: https://www.hostinger.com/support/1583232-how-to-back-up-or-restore-a-vps-at-hostinger/
- Managed n8n: https://www.hostinger.com/support/hostinger-managed-n8n-overview-and-setup/
- Preços VPS (KVM 1 R$ 29,99→59,99; KVM 2 R$ 43,99→77,99; KVM 4 R$ 59,99→149,99; KVM 8 R$ 119,99→259,99): https://www.hostinger.com/br/servidor-vps
- Preços da VPS com n8n (mesmos planos): https://www.hostinger.com/br/vps/n8n-hosting
- AI Automation apps (R$ 29,99 a 54,99; renovação R$ 59,99; lista Hermes Agent, OpenClaw, n8n e Paperclip): https://www.hostinger.com/br/ai-automation-apps

**IA**

- Anthropic, preços (Haiku 5.5 0,10/0,50; Sonnet 5.5 2/10; Opus 5.5 4/20; leitura de cache 0,01/0,10/0,20; lote −50 %; tokenizador dos modelos 4.7+ com ~30 % mais tokens): https://platform.claude.com/docs/en/about-claude/pricing
- Anthropic, retenção comercial (30 dias; conteúdo sinalizado por violação de política até 2 anos): https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data
- Anthropic, API e retenção de dados (ZDR; lote 29 dias; Files API): https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
- Google Gemini, preços e termos (página atualizada em 16/10/2026): https://ai.google.dev/gemini-api/docs/pricing
- llama-bench (7 B Q4_0, 2 threads): https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md
- Tucano 2, qualidade em português de modelos pequenos (artigo acadêmico, não fonte oficial dos modelos): https://arxiv.org/html/2603.03543v1

**Mapas**

- OpenRouteService, cotas e códigos 403/429: https://giscience.github.io/openrouteservice/frequently-asked-questions.html
- OpenRouteService, depreciação do host antigo (28/04/2026; formato `api.heigit.org/openrouteservice/v2/...`; chaves válidas no host novo): https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912
- OpenRouteService, cota de 10 % desde 27/08/2026 e desligamento em 02–06/11/2026: https://ask.openrouteservice.org/t/reducing-the-quota-of-deprecated-api-api-openrouteservice-org/8013
- PostgreSQL 19 RC 1 (lançamento previsto para 19/11/2026): https://www.postgresql.org/about/news/postgresql-19-rc-1-released-3409/
- Google Maps Platform, preços por SKU: https://developers.google.com/maps/billing-and-pricing/pricing
- Google Maps Platform, assinaturas: https://developers.google.com/maps/billing-and-pricing/overview
- GraphHopper (informativo; plano gratuito não comercial): https://www.graphhopper.com/pricing/
- Extratos OSM (Brasil 2,0 GB; Sul 407 MB): https://download.geofabrik.de/south-america/brazil.html

**E-mail**

- Limites de envio do Google Workspace: https://knowledge.workspace.google.com/admin/gmail/gmail-sending-limits-in-google-workspace?hl=en
- SMTP relay do Workspace: https://knowledge.workspace.google.com/admin/gmail/advanced/route-outgoing-smtp-relay-messages-through-google
- Requisitos de remetente do Gmail: https://support.google.com/mail/answer/81126?hl=en
- Governo do PR e Google Workspace (notícia de 01/12/2025): https://www.parana.pr.gov.br/aen/Noticia/Governo-do-Estado-amplia-uso-do-Google-Workspace-e-ativa-60-mil-contas-corporativas

**WhatsApp e norma estadual**

- Política do WhatsApp Business (uso governamental, atualizada em 23/09/2026): https://whatsappbusiness.com/policy/
- Provedor de solução recusa polícia: https://docs.360dialog.com/docs/resources/government-agencies
- Modelo de preços: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
- Cobrança de mensagens não-template desde 01/10/2026: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/non-template-messages
- Calculadora oficial, Brasil (utility, em BRL): https://whatsappbusiness.com/wp-json/wab/v1/pricing?market=BR&currency=BRL&category=Utility
- Decreto estadual 7.304/2021 (eProtocolo): https://www.administracao.pr.gov.br/sites/default/arquivos_restritos/files/documento/2021-04/decreto_7304_-_2021_-_eprotocolo_-_com_anexos_0.pdf
