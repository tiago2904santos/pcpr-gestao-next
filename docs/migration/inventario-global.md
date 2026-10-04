# Inventário global de lacunas (referência × sistema novo)

Levantado em 05/10/2026 por leitura das `urls.py` de todas as apps da referência e do
código novo. Classe das lacunas: **(a)** implementável agora · **(b)** depende de outro
módulo · **(c)** depende de decisão de negócio · **(d)** depende de credencial ou integração
externa · **(e)** legado/ferramenta (não migra).

## Resumo

- Referência ≈ 420 rotas; novo ≈ 117 rotas de negócio (Viagens, Cadastros, Identidade,
  Painel). Módulos 1–6 (Ofícios, Cadastros, Roteiros, Termos, OS, Planos) com paridade quase
  total.
- **Ausentes por completo:** `viagens_viagem` (13), `viagens_prestacoes` (68), `solicitacoes`
  (19), `demandas_eventos` (16 + públicas), `atendimento_imprensa` (12), `publicacoes` (12),
  `coffee_break` (60 + pública), `agenda` (7), `relatorios` (2), `dashboard` (1), cadastros
  de Eventos Sociais (8).
- **Achado estrutural (módulo 7):** `Documento` só guarda versões do ofício e da
  justificativa; termo, OS e plano geram na hora sem guardar → anexar assinado, via efetiva e
  "baixar assinado" pedem um artefato documental guardado.
- **Bibliotecas:** não há leitor de PDF para conferir o assinado (só `pikepdf`, que lê a
  estrutura — campos de assinatura —, não o texto). Precisa de ADR para extração de texto.
- **E-mail:** sem SMTP; a outbox existe (`gestao/plataforma/outbox.py`).

## Por app (situação · classe das lacunas)

| App da referência | Situação no novo | Lacunas e classe |
|---|---|---|
| core | PARCIAL | central de módulos só com Viagens (b); notificações: tela vazia (a); marcar lidas/abrir (a); página de conflitos (a para Viagens, b para os demais); triagem de e-mail (b); busca de endereço (d) |
| accounts | PARCIAL | esqueci a senha (d SMTP); gestão de usuários em tela (a); setor/módulo (c) |
| config / admin | — | admin (e); feriados e setores (c) |
| dashboard | AUSENTE | painel de Eventos Sociais (b solicitações) |
| agenda | AUSENTE | painel, eventos JSON, detalhe, escala, pauta PDF, feed ICS e assinatura (a com fontes de Viagens; b para as demais); envio semanal (d) |
| relatorios | AUSENTE | consolidado anual e XLSX (b; seção Viagens a) |
| cadastros (eventos) | AUSENTE | tipos de evento, serviços, equipes, órgãos, unidades móveis, textos de despacho (a — o motor genérico de catálogos serve); municípios (e, IBGE) |
| viagens_cadastros | EXISTE | consulta de CEP (d) |
| viagens_oficios | EXISTE | anexar/remover assinado (a, módulo 7); modal de baixar marcados/ZIP/PDF único (a; "assinado" b-7); reabrir sem botão (c) |
| viagens_roteiros | EXISTE | "Finalizados" (b prestação); tipo avulso × solicitação (b eventos) |
| viagens_termos | EXISTE | baixar marcados (a); anexar assinado (b-7); "Finalizados" (b prestação) |
| viagens_ordens | EXISTE | anexar assinado (b-7); conflito de agenda (a); "Finalizadas" (b prestação) |
| viagens_planos | EXISTE | vínculo com a viagem (b-8); "Finalizados" (b prestação) |
| viagens_viagem | AUSENTE | lista, criar, etapas 1–5, ações em cascata, repetir, gerar documentos em lote, coerência, baixar tudo, anexos da solicitação (a; partes b-7, b-eventos; conversão DOCX→PDF pede LibreOffice) |
| viagens_prestacoes | AUSENTE | base (abrir, lista com abas incl. **Finalizados**, lote, arquivar/finalizar, envio/aprovação/devolução, XLSX) (a); diário de bordo (a; PWA de campo c+d); RT + modelos + sugestão (a); documentos, assinados, carimbo, consolidado, pacotes (b-7); protocolo (d); importação do processo (b-7 + leitor de PDF/OCR) |
| documentos | PARCIAL | baixar/abrir privados genéricos (a); conferir assinado (a + ADR); editor para termo/OS/plano (a); quebra manual e parágrafo extra (a); modelos editáveis pelo usuário (c) |
| solicitacoes | AUSENTE | tudo (b cadastros de eventos); ler e-mail (b leitor); gerar viagem (b-8); protocolo (d) |
| demandas_eventos | AUSENTE | CRUD, andamento, responder, cadastros (a); pedido público (a código; c+d); encaminhar à DG (b) |
| atendimento_imprensa | AUSENTE | tudo (a), exceto ler e-mail (b) e importadores (e) |
| publicacoes | AUSENTE | tudo (a), exceto ler e-mail (b) e importadores (e) |
| coffee_break | AUSENTE | cadastros, contratos, lotes, solicitações, pagamento, certidões (a); documentos e assinados (b-7); e-mails e portal do fornecedor (d + c); importação do processo (b leitor); numeração compartilhada (c) |

## Transversais

| Funcionalidade | Novo | Situação · classe |
|---|---|---|
| Notificações (sino) | tela vazia; outbox pronta | PARCIAL · (a) sistema, (d) e-mail |
| Rotinas diárias (lembretes, resumo, pauta) | só `processar_outbox` | AUSENTE · (b) |
| Busca global | paleta só com ofícios | EXISTE limitado · (a) estender |
| Exportações XLSX/CSV | só ofícios | PARCIAL · (b) por módulo |
| Importação (planilha, PDF de processo, e-mail) | — | AUSENTE · leitor (a + ADR); comandos (e) |
| Auditoria | trigger + cadeia de hash; histórico em ofício, termo, OS, plano | PARCIAL (mais robusto) · histórico de roteiros (a) |
| Conflitos de agenda | só no ofício | PARCIAL · (a) |
| Feriados | — | AUSENTE · (c) |
| Links públicos por token | — | AUSENTE · (c) + (d) |
| ETL dos dados legados | — | AUSENTE · (d) |

## Fila por dependência (atualizada em [continuous-work.md](continuous-work.md))

1. Artefato documental guardado para termo, OS e plano (L) →
2. Anexar/remover via assinada com histórico (M) →
3. Conferência do assinado + ADR de leitura de PDF (M) →
4. Modal "Baixar documentos" reaproveitável (M) →
5. Notificações no sistema (M, paralelo) →
6. Gestão de usuários em tela (M, paralelo) →
7. Viagem: base e etapas (L) → 8. gerar em lote e baixar tudo (L) → 9. coerência, repetir,
   anexos (M) →
10. Prestação: base (L) → 11. diário (L) → 12. RT (M) → 13. documentos e assinados (L) →
14. Abas "Finalizados" (S) → 15. Agenda com fontes de Viagens (L).

Trilhas paralelas sem dependência: catálogos de Eventos Sociais; ASCOM (Imprensa e
Publicações); busca global estendida; histórico de roteiros.
