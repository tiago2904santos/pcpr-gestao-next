# CD08–CD15 — Catálogos compartilhados

## Candidato validado tecnicamente

Base: 0ec18f8, branch codex/oficios-transporte-cartoes. Nenhuma mudança no backend,
permissões, documentos ou dados DEMO. Testes usam banco e mídia isolados do runner.

Rotas: Unidades, Cargos, Combustíveis, Tipos de viagem, Programas, Horários,
Atividades e Conjuntos. Template único catalogo.html, com parciais específicas
para Horários, Atividades e Conjuntos. Contrato em product/propagacao-identidade.md.

## Observação e implementação

48 capturas anteriores e 48 candidatas em 360/768/1440. Cabeçalho anterior
substituído por registro_hero. Registros usam registro--catalogo: não reservam
no mobile a linha da placa documental, inexistente nestes catálogos. Ação de
criação extraída para _catalogo_criar.html e reutilizada no topo e rodapé.
Nota de padrão em um span, evitando fragmentação no contêiner flex. Nome/Sigla
de Unidade passam à grade canônica, empilhando no celular.

147 capturas finais de apresentação incluem lista integral, novo, edição,
menu, busca sem resultado, inativos e inferior do conjunto. Mesmos dados DEMO
e viewports das capturas anteriores. Nenhum POST usado nas capturas DEMO.

## Segunda revisão

Inspeção própria e independente: listas das oito rotas e formulários distintos.
Horários continua com horas legíveis; Atividades mantém código imutável,
Meta e Recursos; Conjuntos mantém escolhas e padrão, com rolagem até Salvar.
Sem bloqueante identificado no candidato visual. Homologação do usuário pendente.

## Limpeza e desempenho

Removida a duplicação da ação Novo e os blocos de cabeçalho substituídos.
Sem CSS/JS novo e sem novas dependências. Classes antigas globais permanecem
porque têm outros consumidores: sua exclusão neste lote não seria segura.
Sem alteração de consulta ou carregamento de recurso pesado. Suíte inclui os
budgets existentes de consultas; não se declara ganho de latência.

Aviso de 33 consultas em exclusão de Servidor é preexistente e fora deste diff:
logs/servidores-identidade.log de 12/10, linha51, já registra 33/25 na mesma
operação. Não foi aumentado budget nem alterada a exclusão nesta rodada.

## Validação em andamento

Primeira suíte catalogos-identidade: expectativa de nome em uppercase no novo
teste não respeitava a normalização vigente de Unidade/Cargo/Combustível/Tipo/
Atividade. Evidência no log preservada; expectativa corrigida. Programas e
Conjuntos continuam uppercase conforme contrato. Produto não foi adaptado ao teste.

Suíte corrigida `catalogos-final.log`: **143 passed in 632.29s**. Inclui 32 E2E:
24 casos de criação/erro/edição/menu/Escape/busca/desativação/reativação nas três
larguras e oito casos de vazio/paginação/consulta sem escrita. Axe nas telas e
diálogos desses cenários; não equivale a conformidade completa de acessibilidade.
HTTP cobre regras específicas, exclusão/vínculos, perfis e consultas sem N+1.
Ruff integral e 16 contratos de arquitetura verdes. Sem mudança de CSS/JS para
compilar. Gate global permanece obrigatório no fechamento da missão inteira.

150 capturas DEMO mais 72 capturas LAB dos testes (erro, salvo, vazio, página2
e consulta). Aprovação visual pelo usuário pendente. As oito páginas são
concluídas tecnicamente por essas verificações individuais, não por herança.

Segunda revisão independente pós-testes conferiu os 24 PNGs de vazio, paginação
e consulta das oito rotas. Sem bloqueante, ação perdida ou remoção insegura.
Consulta preserva leitura e elimina os controles sem permissão; paginação
preserva o termo e não encobre o último registro. Fontes testadas registradas
com SHA256 normalizado em catalogos-fontes-validadas.json.
