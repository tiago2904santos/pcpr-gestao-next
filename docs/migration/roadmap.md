# Roadmap de migração

Ordem decidida pelo inventário ([inventario.md](inventario.md)) e pelas dependências, não pela
ordem do menu. Cada módulo só fecha com a definição de "concluído" do fim desta página.

## Ordem

| # | Módulo | Por que nesta posição | Depende de |
|---|---|---|---|
| 0 | **Fundação de integrações e automação** (`gestao/integracoes/`, contrato de ferramentas, ADR 0019/0020) | Sem fronteira clara, a primeira integração espalharia chamadas externas pelas views | Plataforma (outbox, auditoria) |
| 1 | **Ofícios — fechamento** | 80% pronto, é o piloto e o centro do domínio; os módulos seguintes consomem ofício, equipe, roteiro e documento | Cadastros (já semeados), Roteiros |
| 2 | **Cadastros de Viagens — CRUD** (servidores, viaturas, unidades, cargos, combustíveis, tabela de diárias, configuração institucional, assinaturas, catálogos de texto) | Hoje só por seed; Termos, OS e PT precisam de cadastros mantidos em tela | Plataforma |
| 3 | **Roteiros — fechamento** (detalhe, estimar trecho/km, "finalizados") | Base de PT, OS e prestação (diário de bordo) | Cadastros |
| 4 | **Termos de autorização** | Saem do ofício (por servidor, lote, viatura); menor e de alto uso | Ofícios, Cadastros |
| 5 | **Ordens de serviço** | Saem de ofícios; reaproveitam equipe, destinos e numeração anual | Ofícios |
| 6 | **Planos de trabalho** | Mais complexo (multievento, efetivo, atividades, diárias combinadas) | Cadastros, Roteiros, diárias |
| 7 | **Documentos — núcleo** (modelos por tipo, conferência de assinado, versões assinadas) | Transversal; promovido a partir do editor do ofício quando Termos/OS/PT precisarem | 1, 4–6 |
| 8 | **Viagem (assistente)** | Agrega roteiros → ofícios → PT/OS → termos; só faz sentido com todos prontos | 1–7 |
| 9 | **Prestação de contas** (+ diário de bordo no celular) | Consome ofício emitido e documentos; integra eProtocolo (importar processo) | 1, 7, 8 |
| 10 | **Plataforma** (usuários e setores em tela, recuperação de senha, notificações por e-mail, agenda, relatórios) | Pode avançar em paralelo quando um módulo pedir | — |
| 11 | **Eventos Sociais** | Gera Viagem; precisa do assistente | 8 |
| 12 | **ASCOM** (palestras, publicações, imprensa) | Independente, menor prioridade operacional de Viagens | 10 |
| 13 | **Coffee Break** | Ciclo financeiro próprio; compartilha numeração de ofícios (decisão pendente) | 1, 10 |
| 14 | **Migração de dados (ETL) e virada** | Depois que os modelos estabilizam | todos os migrados |

Integrações entram **dentro** dos módulos que as usam, sempre pela camada de integrações:
eProtocolo consulta (1), abertura de protocolo (1, atrás de trava), importação de processo (9);
Central de Viagens só com canal oficial (ver `docs/integrations/central-de-viagens.md`).

O agente operacional de IA ([`docs/ai/`](../ai/README.md)) começa com **ferramentas de
leitura** assim que a fundação (0) existir e cresce módulo a módulo.

## Definição de "concluído"

Paridade funcional comprovada (ficha + testes) · melhoria de UX registrada · visual no Design
System · componentes reutilizados (nenhuma cópia) · testes rápidos e de navegador verdes ·
axe sem violações · 360–1440 sem rolagem horizontal · orçamento de consultas/tempo dentro do
`docs/quality/performance-budgets.md` com DEMO populoso · dados DEMO para a tela · documentos
gerados conferidos · integrações analisadas · pendências e decisões documentadas.
