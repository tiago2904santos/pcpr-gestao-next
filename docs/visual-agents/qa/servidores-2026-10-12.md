# CD02 — Servidores

Base0cbe620, contrato product/propagacao-identidade.md. Antes:15 capturas reais
de lista, incompletos, sem resultados, novo e editar360/768/1440. DEMO só GET/HEAD.
Hero compacto aplicado sem alterar registros, rotas, contadores ou permissões.
Diálogo compartilhado usava campos--iguais: CPF e cargo cortados em360. Grade2/3
canônica dá uma coluna no celular e mantém proporção no desktop. Sem CSS/JS novo.

## Segunda revisão

Revisor encontrou regressão da candidata filtros--barra: order1 deslocava busca
abaixo de Cargo/Buscar em360. Retirada a variante, preservando filtro simples e
ordem DOM/visual. Não mudar regra global de Ofícios. Capturas depois iniciais
incluem a candidata rejeitada; recaptura final terá prefixo final.
Teste passa a verificar posição de busca antes de cargo. Suíte8028 em andamento
foi iniciada antes dessa correção; exigir focused final após término.

Captura de diálogo auxiliar falhou por nome esperado Novo cargo; template usa
outro nome. Automação corrigida para ID real dialogo-cargo, sem alteração do produto.
Consumidores do diálogo: Servidores, Termos, OS, lote e Ofícios sob demanda.
Suite inclui cadastro/edição/máscaras, permissões HTTP e cadastro adiado em Ofícios.
Ainda faltam controles dos demais consumidores e resultado terminal.

Limpeza: três blocos antigos de cabeçalho removidos deste consumidor; campos--iguais
substituído somente no diálogo. Bases ainda usadas legitimamente: não excluir.
Não concluir CD02 nem invalidar testes anteriores silenciosamente.

## Resultado integrado

8028 terminou:151 aprovados,1 aviso HarfBuzz em313,71s. SQL de exclusão/adicionar
equipe permanece dívida anterior; budgets não alterados. Foco/Escape e largura
do diálogo também conferidos em Termos, OS e lote360/1440 (servidores-compat.json).
Scripts de captura ajustados a controles reais: dois botões de cadastro no lote
e submit homônimo no diálogo exigiam seletor do disparador, sem falha de produto.
Capturas finais da página preservam ordem Busca/Cargo/Buscar.
Focused final com a asserção de ordem deve terminar antes de fechar CD02.

Focused57117:2 aprovados,1 falha104,26s. Falha em1440 demonstrou diferença
de0,086px entre busca/cargo na mesma linha, não reorder. Log preservado em
servidores-focused-subpixel.log. Teste corrigido: aguarda fontes/animações,
exige busca inteiramente antes de cargo em360 e alinhamento até1px em768/1440.
Não remove a intenção da verificação. Reexecução45948 em andamento.
Galeria recebeu30capturas finais/componentes abertos/consumidores, ainda como
candidato em validação. Descoberta da próxima página limitada a leitura e15
capturas antes de Viaturas; nenhuma implementação concorrente nessa página.

## Fechamento técnico

Focused45948 terminou:3 aprovados99,88s, sem falha. Revisão independente
confirmou correção dos filtros e compatibilidade. Capturas e galeria824 validadas.
Ruff verde. Homologação visual do usuário e gate global ainda pendentes.
