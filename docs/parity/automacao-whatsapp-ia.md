# Automação, WhatsApp e IA — acompanhamento, 18/10/2026

Funcionalidade **nova**: não existe no sistema de referência, então não há paridade a
conferir. Esta página registra o que mudou nas telas que **já tinham** paridade e o que foi
acrescentado, para a próxima conferência não confundir acréscimo com regressão.

Escopo: piloto de testes com dados fictícios (ADR 0046). Decisões: ADR 0047 (automação e
transporte) e ADR 0048 (IA). A situação item a item está em
[implementacao-piloto.md](../automacao/implementacao-piloto.md).

## Telas novas (sem equivalente na referência)

| Tela | Caminho | Estados conferidos |
|---|---|---|
| Painel da automação | `/automacao/` | vazio, com dados, chave geral desligada, fluxos desligados |
| Comunicações (abas: aguardando aprovação, a sair, com problema, enviadas, não saíram) e detalhe | `/automacao/comunicacoes/` | vazio, busca sem resultado, aprovação em lote |
| Recebidos, exceções, contatos, testadores | `/automacao/recebidos/` etc. | vazio, quarentena, descartado |
| Canal e chaves, credenciais, aprovações, histórico, links, delegação | `/automacao/canal/` etc. | só administração; confirmações nas ações irreversíveis |
| Página de km sem login (offline) | `/p/<token>/` | vazio, salvo neste aparelho, enviado, conflito, recusado, somente leitura, indisponível |
| Central de ajuda e Minha situação | `/ajuda/` | rascunho do sistema de testes, sem resultado |
| Sugestões de IA | `/assistencia/` | sem sugestão, pendente, obsoleta, aplicada, recusada |
| Proposta consolidada | `/viagens/proposta/` | sem viagens, prévia, bloqueios, recusa por mudança (409) |

Evidência visual: `artifacts/capturas/piloto-whatsapp-ia/{360,1440}/` (não versionado; gerar
com `scripts/capturar.py`, ver o roteiro do LAB). Navegador: `tests/e2e/test_automacao.py`
(fluxo ponta a ponta, axe, sem rolagem horizontal) e `tests/e2e/test_km_offline.py`.

## Acréscimos em telas que já tinham paridade

- **Prestação de contas (lista):** quando existe aviso automático para o servidor, o menu do
  cartão ganha um item com a situação dele (leva à comunicação). Nada do que existia mudou de
  lugar; o "Avisar por WhatsApp" manual continua igual.
- **Prestação — registrar liberação:** salvar a solicitação com a liberação agenda o aviso ao
  servidor na mesma transação. A regra da liberação é a mesma.
- **Diário de bordo:** o km também pode chegar pelo link pessoal. Grava pela mesma regra do
  diário (`diario.gravar_linha`, km final ≥ inicial, prestação aberta); o histórico e a
  auditoria registram quem o link representa.
- **Ofício emitido/cancelado e diário:** emitir, cancelar, remarcar ou trocar a equipe agenda os
  avisos de viagem; com as chaves desligadas eles ficam registrados e nada sai.
- **Viagem:** ação "Proposta consolidada" no menu de ações da viagem.
- **Relatório técnico, ofício, plano, importação, comprovante, catálogo e relatórios do painel:**
  um cartão ou link "Sugestão de IA" (simulada por padrão), sempre com revisão humana.

## O que não foi feito

- Envio de documentos como mídia, DB/RT para assinatura e resumos de outros módulos.
- AUT-92 e AUT-171 (dependem do leitor por regras e da consulta real ao eProtocolo).
- Validação com a Meta ou a Anthropic reais: nada foi ligado (roteiro em
  `docs/ops/lab-whatsapp-ia.md`).
