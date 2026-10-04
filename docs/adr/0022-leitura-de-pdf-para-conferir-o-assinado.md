# ADR 0022 — Leitura de PDF para conferir a via assinada

- **Status:** aceito (decisão técnica do agente, dentro da autonomia dada; reversível)
- **Data:** 2026-10-04

## Contexto
A via assinada (módulo 7a) aceita qualquer PDF que passe nas três conferências de arquivo
da referência (`.pdf`, até 15 MB, começa com `%PDF-`). A referência vai além (m112): ao
anexar, **lê** o PDF e avisa — sem bloquear — se há assinatura digital, quem assinou e
quando, e se o PDF é do documento certo (número do ofício/OS, protocolo, nomes do termo).

O projeto tem `pikepdf` (lê a estrutura: campos `/Sig`, `/Contents` do PKCS#7) e
`weasyprint` (só escreve). Nenhum dos dois extrai o texto das páginas, que é onde estão o
número do documento, os nomes e os carimbos de assinatura desenhados (eProtocolo, ICP,
gov.br).

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A. `pypdf` (BSD-3, Python puro) para texto e campos | sem dependência nativa; a referência usa a mesma; extração boa o bastante para conferir números e nomes | mais lenta que as nativas; PDF malicioso pode custar CPU |
| B. `pdfminer.six` | extração mais fiel de layout | mais lenta; API mais pesada; sem ganho para procurar números e nomes |
| C. `PyMuPDF` | rápida e completa | licença AGPL (incompatível com o uso institucional sem análise jurídica) |
| D. Só `pikepdf` (campos `/Sig`) | nenhuma dependência nova | não confere número, nomes nem carimbos desenhados — metade do aviso some |

## Decisão
**A — `pypdf`**, com limites: só as 4 primeiras páginas (como a referência), qualquer
exceção vira o aviso "Não foi possível conferir o PDF assinado." (nunca derruba o anexo), e
os campos de assinatura são lidos sem validar a cadeia de certificados (o resultado é
**aviso**, não prova jurídica de assinatura). A leitura fica em
`gestao/viagens/documentos/leitura.py` (infraestrutura); a interpretação do texto (carimbos,
números, nomes) é Python puro em `gestao/viagens/dominio/conferencia.py`, testável sem PDF.

## Consequências
- Dependência nova no `pyproject.toml`/`uv.lock` (a imagem do preview precisa de
  `up --build`).
- O resultado fica na via (`ViaAssinada.conferencia`, JSON) e aparece na tela depois de
  anexar e no registro da via.
- Validação real de assinatura ICP-Brasil (cadeia, revogação) fica fora: exigiria o
  repositório de ACs e é decisão institucional — registrada em `decisoes.md`.
