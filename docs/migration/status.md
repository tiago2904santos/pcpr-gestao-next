# Status da migração

Atualizado em 03/10/2026 (ramo `migracao/loop-continuo`).

## Agora

**Módulo 1 — Ofícios (fechamento).** Ficha: [oficios.md](oficios.md).

| Item | Situação |
|---|---|
| Revisão antes de emitir na janela de resumo (página "Revisar e emitir" apagada) | ✅ feito — `?revisar=1` abre a janela sobre a folha; rodapé fixo com Emitir |
| Catálogo de textos prontos (motivo, justificativa, trechos) + seletor na folha + "Guardar como texto pronto" + motivo padrão no ofício novo | ✅ feito — `gestao/cadastros/textos.py`, tela `/cadastros/textos-prontos/`, componente `componentes/texto_pronto.html` + `texto-pronto.js` |
| Testes de navegador defasados (crachá, faixa de progresso, detalhe, Documentos) | ✅ atualizados — conferir rodada completa |
| Origem do protocolo (manual/simulado/treinamento/oficial) + camada `gestao/integracoes/eprotocolo` simulada (E1/E2) | ✅ feito — `gestao/integracoes/`, `manage.py eprotocolo_check`, `Oficio.protocolo_origem` |
| Revisão de UX e de segurança (agentes revisores) e correções | ✅ feito — laço de confirmação, avisos na revisão, emissão sem JS, permissão de gestor para o padrão, cliente HTTP sem redirecionar/só HTTPS, trava explícita |
| Falso conflito autosave × Salvar; menus sob a barra flutuante | ✅ corrigidos (achados pelos testes de navegador) |
| Orçamentos de peso (CSS/JS/requisições) | ✅ peso e tempo no orçamento (minificação + editor sob demanda); requisições das folhas: ADR 0021 (proposto) |
| Exportar a lista em planilha (.xlsx, 14 colunas, como a referência) | ✅ feito — `gestao/viagens/exportacao.py`, botão na barra da lista; 268 ofícios do DEMO em 0,76 s com 11 consultas |
| Tela do piso da numeração (gestor) | pendente |
| Arquivar / reativar / complementar / motorista externo / DOCX | **decisões pendentes** D-OF-1..4 (ver ficha) |
| Comparação com a referência em execução | **bloqueada**: precisa de `REF_USER`/`REF_PASS` no ambiente ou sessão aberta pelo usuário |

## Feito nesta rodada (fase 0 — descoberta)

- Inventário cruzado ([inventario.md](inventario.md)), paridade por módulo ([parity.md](parity.md)),
  roadmap ([roadmap.md](roadmap.md)), catálogo de componentes ([componentes.md](componentes.md)),
  aprendizados ([lessons.md](lessons.md)), backlog ([improvements.md](improvements.md)).
- Estudos: [eProtocolo](../integrations/eprotocolo.md), [Central de Viagens](../integrations/central-de-viagens.md),
  [Hostinger](../integrations/hostinger.md), [orquestração/n8n](../integrations/orquestracao.md),
  [agente de IA](../ai/README.md). ADR 0019 (integrações) e ADR 0020 (automação).

## Bloqueios que dependem do dono do produto

1. Credenciais da referência em execução (variáveis de ambiente) para a comparação visual lado a lado.
2. Decisões D-OF-1..7 da ficha de Ofícios.
3. eProtocolo real: credenciamento no PDS Mantis, usuário de sistema com CPF, `consumerId`,
   IP fixo da VPS, escopos — só então o adaptador HTTP sai do modo simulado.
4. Dados da VPS Hostinger (plano, uso, IP fixo, backups) para dimensionar n8n.

## Próximo passo

Fechar os itens "próximo/pendente" de Ofícios, rodar a regressão completa (rápida + navegador),
registrar paridade e só então abrir o módulo 2 (Cadastros — CRUD), que promove o padrão de
"cadastro em janela" já usado nos textos prontos.
