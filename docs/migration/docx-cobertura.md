# D4 — Editor visual × DOCX editável: cobertura

Decisão D4 (03/10/2026): o editor visual é a experiência principal; o DOCX não sai antes de
se comprovar que os usos necessários estão cobertos (ou de as limitações serem aceitas).

## Como a referência usa o DOCX (comprovado no código)

| Uso | Onde | O que entrega |
|---|---|---|
| "Baixar DOCX · Arquivo editável" do ofício, da justificativa e dos termos | menus do cartão da lista (`docs/paridade/oficios-menus.md`) | modelo `.docx` preenchido pelo docxtpl |
| DOCX da **versão editada** (m057) | `documentos/services/html_docx.py` | conteúdo e formatação de texto (parágrafos, alinhamento, negrito/itálico/sublinhado/tachado, títulos, listas, tabelas, timbre, cabeçalho e rodapé editados); **sem a geometria** do PDF |
| PDF a partir do DOCX (caminho antigo) | `facade.py` | trocado pelo HTML→PDF na própria referência (arquitetura-documentos-editor.md, D1) |

## O que o editor visual daqui cobre (ADR 0018, testes em `test_editor*.py`)

Texto livre nas regiões (cabeçalho, corpo, rodapé), negrito, itálico, sublinhado, listas,
quatro alinhamentos, tabelas, colar como texto puro, quebras de página, textos prontos,
campos vivos ligados ao cadastro, versões com restaurar/voltar ao modelo, presença,
conferência de páginas pelo motor do PDF, e emissão que congela o texto editado no PDF/A.

## O que o DOCX permite e o editor não cobre

| Uso possível do Word | Situação aqui | Observação |
|---|---|---|
| Levar o documento para fora do sistema (anexar, enviar a outro órgão para ajuste) | **não coberto** | o PDF/A cobre envio e protocolo; ajuste fora do sistema não |
| Fonte, tamanho, cor, recuo e espaçamento livres | não coberto (intencional: o documento segue o padrão institucional) | a referência também perde isso no DOCX editado |
| Inserir imagens | não coberto | a referência só põe o timbre |
| Comentários / controle de alterações | não coberto | — |
| Termos, ordens de serviço, planos | ainda não migrados | entram com seus módulos, pelo mesmo editor |

## Conclusão e próximo passo

- **Paridade necessária (não bloqueante):** a referência oferece DOCX do documento (inclusive
  do editado). Até haver prova de que ninguém precisa levar o texto para fora, o sistema novo
  deve oferecer **"Baixar DOCX"** do documento como está (conteúdo + formatação de texto, sem a
  geometria do PDF), como a referência faz. Implementação planejada com `python-docx` sobre as
  mesmas regiões saneadas do editor — backlog `[MÓDULO][ALTA]`.
- **Evidência pendente (dependência do usuário):** quais desses usos acontecem na prática
  (ex.: o DOCX é editado e devolvido? anexado?). Com essa resposta, decide-se se o DOCX fica
  permanente ou sai quando o editor cobrir os usos reais.
