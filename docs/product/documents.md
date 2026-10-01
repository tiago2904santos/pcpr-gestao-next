# Documentos gerados

## Catálogo

| Documento | Módulo | Referência | Novo |
|---|---|---|---|
| **Ofício de viagem** | Viagens | DOCX + PDF, editor na página, marcas retificado/complementar | **Implementado**: PDF/A-2a versionado |
| **Justificativa** (1:1 com ofício) | Viagens | DOCX + PDF, gerada quando exigida | **Implementado**: PDF/A-2a, gerada sempre que há texto (decisão pendente) |
| Termo de autorização | Viagens | individual, genérico (sem servidor), por viatura, lote ZIP ou PDF único | Planejado |
| Ordem de serviço (OS) | Viagens | DOCX/PDF, numeração anual com lacunas, assinante | Planejado |
| Plano de trabalho (PT) | Viagens | simples/multievento, numeração anual + sufixo | Planejado |
| Relatório técnico (RT) | Prestação | DOCX/PDF; volta assinado | Planejado |
| Diário de bordo | Prestação | XLSX/PDF; volta assinado | Planejado |
| PDF consolidado da prestação | Prestação | ordem: ofício → despachos → RTs → diários → comprovantes; prefere assinado; carimbo do nº de solicitação sobre o ofício assinado | Planejado |
| OS do Coffee Break, Ofício ao GAF, Certifico | Coffee Break | PDF (HTML→WeasyPrint) com prévia A4 | Planejado |
| Anexo do protocolo CB | Coffee Break | PDF único ou ZIP: ofício, NF, certifico, certidões, aditivo, contrato; só com certidões vigentes | Planejado |
| Certificado da solicitação CB | Coffee Break | PDF recalculado a cada acesso (não armazenado) | Planejado |
| Pauta semanal | Agenda | PDF, enviada por e-mail às segundas | Planejado |
| Exportações | vários | CSV (eventos, CB, demandas, publicações, imprensa, ofícios), XLSX (consolidado, prestações) | Planejado |

## Ofício — conteúdo (novo)

Cabeçalho institucional (brasão, "SECRETARIA DE ESTADO DA SEGURANÇA PÚBLICA", "POLÍCIA CIVIL
DO PARANÁ", unidade) → quadro com **número + rótulo do assunto**, data, origem, órgão de
destino, protocolo, linha de assunto → frase "solicito {autorização|convalidação} e medidas
para a concessão de diárias e recursos para combustível" → tabela da equipe (nome, CPF,
cargo, coluna "Nº solicitação (Central de Viagens)" em branco) → destinos, resumo de diárias
por servidor e valor total → **roteiro de ida** e **de retorno** → transporte (meio, placa,
motorista, combustível, tipo de viatura, porte/trânsito de arma) → custeio (três opções
marcadas com X) → motivo → declaração sobre cartão corporativo → assinatura da chefia →
destinatário. Rodapé com endereço da unidade.

Todos os textos institucionais vêm da **configuração institucional da unidade**.

### Assunto: Autorização × Convalidação (`dominio/assunto.py`)

| Situação | Natureza | Rótulo | Frase |
|---|---|---|---|
| data do ofício **anterior** à data (local) da 1ª saída, ou sem saída | Autorização | "(Autorização)" | "solicito autorização…" |
| data do ofício **igual ou posterior** à 1ª saída | Convalidação | "(Convalidação)" | "solicito convalidação…" |
| marcador **Retificado** + Autorização | Autorização | "(Retificado)" | inalterada |
| marcador Retificado + Convalidação | Convalidação | "(Convalidação)" (marcador ignorado) | inalterada |
| marcador **Complementar** | qualquer | "(Complementar)" | inalterada |

Linha de assunto: "Solicitação de {autorização|convalidação} e concessão de diárias." — nunca
texto livre. Marcadores são mutuamente exclusivos.

## Justificativa — quando é obrigatória (`dominio/prazos.py`)

`antecedência = data (local) da 1ª saída − data do ofício`, em dias; `N` = antecedência
mínima da unidade (**padrão 10**, configurável por unidade).

| Situação | Condição | Justificativa |
|---|---|---|
| Indefinida | sem trecho | — (aviso "informe a data de saída") |
| No prazo | antecedência **> N** | dispensada |
| Fora do prazo | 0 ≤ antecedência **≤ N** | **obrigatória** |
| Retroativa | saída **antes** da data do ofício | **obrigatória** |

Documento de justificativa: título "JUSTIFICATIVA — OFÍCIO Nº …", protocolo, destinos, data
de saída, antecedência × prazo mínimo, texto, cidade e data, assinatura da chefia.
A docstring do domínio cita o Decreto nº 6.358/2024 como base — **a confirmar** com o
dono do produto.

## Diárias (`dominio/diarias.py`)

1. **Períodos por destino, pela chegada**: o período de um destino vai da chegada nele até a
   chegada no seguinte; o 1º começa na **saída da sede**; o último termina na **chegada de
   volta à sede**. O tempo de estrada é cobrado na faixa de onde o servidor partiu.
2. **Passar pela sede** no meio do roteiro não gera diária; a volta final prolonga o último
   destino. Parada instantânea (chegada = saída) é ignorada.
3. **Trecho tarifário** = períodos contíguos da mesma faixa, fundidos; cada um vira dias
   inteiros + resto.
4. **Escada do resto** (por duração, não por calendário):

   | Resto | Percentual |
   |---|---|
   | ≤ 6 h | 0% |
   | > 6 h e ≤ 8 h | 15% |
   | > 8 h e ≤ 12 h | 30% |
   | > 12 h | 100% |

5. **Faixas**: Brasília (DF), Capital (capitais das 27 UFs, comparação sem acento) e
   Interior. **Valores de 24 h** usados nos testes e no cenário de desenvolvimento:

   | Faixa | 24 h | 15% | 30% |
   |---|---|---|---|
   | Interior | R$ 290,55 | R$ 43,58 | R$ 87,17 |
   | Capital | R$ 371,26 | R$ 55,69 | R$ 111,38 |
   | Brasília | R$ 468,12 | R$ 70,22 | R$ 140,44 |

   15%/30% = percentual do valor de 24 h, ao centavo, meio para cima (derivados, não
   digitados). Data de vigência e norma oficial desses valores: **a confirmar**.
6. **Vigência**: uma tabela por cálculo, pela data local da 1ª saída; precisa haver
   vigência para **as três faixas**; sem ela → erro visível ("Cadastre a vigência…"), nunca
   valor embutido no código.
7. **Total** = Σ (24 h × dias + parcial) × nº de servidores (no novo, todos os viajantes,
   **inclusive o motorista**). Resumo "2 x 100% + 1 x 30%" e valor por extenso.

Exemplos fictícios (sede Curitiba/PR):
- Maringá/PR, saída 10/03 08:00, volta à sede 12/03 18:00, 2 servidores → 58 h = 2 dias + 10 h
  (30%) → **R$ 1.336,54** (R$ 668,27 por servidor), "2 x 100% + 1 x 30%".
- Maringá/PR (saída 10/03 08:00) → São Paulo/SP (chegada 11/03 16:00) → sede (12/03 20:00),
  1 servidor → Interior 32 h (1 dia + 15%) + Capital 28 h (1 dia + 0%) → **R$ 705,39**.
- Demonstrativos de caracterização reproduzidos nos testes: R$ 773,19 e R$ 1.144,45.

## Formato

| | Referência | Novo (ADR 0008) |
|---|---|---|
| Motor | DOCX (modelos binários) → PDF via Word/LibreOffice/WeasyPrint | HTML + CSS de impressão → **WeasyPrint**, `pdf/a-2a` |
| Arquivamento | PDF comum | **PDF/A-2a**: fontes embutidas, sRGB, estrutura marcada, XMP |
| Versões | artefato com snapshot, hash, cache; nova versão sob demanda | `Documento` imutável por (ofício, tipo, versão), **instantâneo** dos dados, SHA-256; nova versão só ao reabrir e emitir de novo |
| Geração | síncrona | **assíncrona** via outbox, idempotente (versão pronta não é refeita) |
| Prévia | preview do artefato | **minuta** PDF com marca d'água "MINUTA", não arquivada |
| Edição do texto | editor na página + DOCX baixável | não há (planejado/decisão pendente) |
| Assinatura | externa (eProtocolo/gov.br) + upload do assinado, conferência, revogação ao reabrir | não há (planejado) |

## Numeração

| Regra | Novo | Referência |
|---|---|---|
| Escopo | anual, global (único por ano) | anual, global; livro compartilhado com ofícios do Coffee Break |
| Quando | **reservado ao criar o rascunho** | reserva transacional |
| Próximo número | **menor número livre ≥ piso** entre os ocupados; sem buraco, `max + 1` | menor **lacuna registrada** (criada só por exclusão) ≥ piso, senão `max + 1` |
| Piso | `NumeracaoAnual.piso` (sem tela; via carga) | configurável em tela |
| Cancelado | **mantém o número** (rastreabilidade do protocolo) | mantém |
| Excluir rascunho | **libera o número** (só rascunho sem documento) | exclusão cria lacuna reaproveitável |
| Concorrência | `select_for_update` na linha do ano + constraint única | advisory lock + repetição |
| Formato | `NNN/AAAA` (`005/2026`) | `NN/AAAA` (`05/2026`) — **decisão pendente** |
| Data × ano | data do ofício **deve** estar no ano do número (erro) | aviso ao finalizar — **decisão pendente** |

Nome do arquivo (novo): `oficio-005-2026-v1.pdf`, `justificativa-005-2026-v1.pdf`.
