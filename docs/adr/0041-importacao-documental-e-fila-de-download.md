# ADR 0041 — Importação persistente e downloads concorrentes

- Status: aceito pelo pedido de 16/10/2026
- Data: 2026-10-16

## Contexto

O envio precisa distribuir documentos de vários registros sem bloquear a tela.
OCR e conversão têm duração variável. A outbox atual mantém uma transação durante
o assinante; não é adequada para segurar conversões longas e progresso intermediário.

## Decisão

Fila no PostgreSQL com arquivos/partes, claim curto com skip_locked e lease.
Worker dedicado com concorrência limitada; extração/conversão fora de transação,
aplicação curta com locks e revalidação dos serviços existentes. Original privado
e hash; resultados idempotentes e rastreáveis. Classificador puro com evidências
determinísticas, OCR local seletivo e revisão explícita para ambiguidades.
Conversores locais com limites, sem depender de serviço externo de IA ou enviar
documentos a terceiros. Não prometer compreensão universal de formatos desconhecidos.

Downloads usam manifestos de itens autorizados e o endpoint original para cada
arquivo; cliente mantém três requisições simultâneas e links para repetir falhas.
PDF único permanece. Remover ZIP das ações de download de todos os módulos.

## Consequências

Acrescenta worker e dependências nativas de conversão/OCR. Deploy deve iniciá-lo.
O original preserva assinaturas; extratos de páginas são derivados e não são
apresentados como PDFs com assinatura criptográfica preservada.
Confiança deve ser medida em corpus, com erros de vínculo como falha prioritária.

A prévia nativa de PDF ficou vazia no navegador de teste. A revisão usa PDF.js
6.4.299 (build de compatibilidade) vendorizado, sem CDN, em worker do navegador e sem execução de JavaScript
do documento. Renderiza apenas a página escolhida, com limite de pixels; mantém
o PDF original acessível e controles do Design System. Fontes padrão e CMaps são
locais. Avaliação dinâmica de código e WebAssembly ficam desabilitados no leitor.
