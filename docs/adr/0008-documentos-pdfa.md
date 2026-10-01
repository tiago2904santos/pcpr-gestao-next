# ADR 0008 — Documentos oficiais em PDF/A-2a com WeasyPrint, versionados e imutáveis

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
A referência gera DOCX (docxtpl) e converte para PDF (Word/`docx2pdf` no Windows, outros
caminhos no Linux), com editor de "documento completo" e reemissão. Conversão dependente de
Office é frágil e não garante arquivamento de longo prazo.

## Decisão
- Documento = **template HTML + CSS de impressão** (`@page`, cabeçalho/rodapé corridos),
  renderizado pelo **WeasyPrint 70** com `pdf_variant="pdf/a-2a"`: fontes embutidas
  (Liberation Serif, OFL), perfil sRGB, estrutura marcada (tags) e metadados XMP.
- Cada emissão gera uma **versão** (`Documento`: número da versão, SHA-256 do arquivo,
  quem/quando, dados usados — "snapshot" JSON). Versões emitidas nunca são alteradas;
  corrigir = reabrir e emitir nova versão (registrado).
- Geração assíncrona via outbox (`oficio.emitido` → gera PDF); a prévia na tela usa o mesmo
  template em HTML (o que se vê é o que se imprime).
- Validação: teste verifica `pdfaid:part=2`/`conformance=A`, fontes embutidas e árvore de
  estrutura (pikepdf); veraPDF no CI quando disponível.

## Alternativas
| Alternativa | Por que não |
|---|---|
| DOCX + LibreOffice headless | Pesado, não determinístico, PDF/A-2a incerto |
| ReportLab | Layout programático difícil de manter por não-desenvolvedores |
| Chromium print-to-PDF | Não gera PDF/A |

## Consequências
Textos institucionais (cabeçalho, rodapé, destinatário) vêm da configuração institucional;
o leiaute é versionado no Git e revisado como código.
