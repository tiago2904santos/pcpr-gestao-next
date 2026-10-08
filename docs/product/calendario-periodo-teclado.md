# Calendário de período — continuidade do foco

Regra documentada antes da correção em 07/10/2026. O componente compartilhado
`seletor-data.js` define que Enter/Espaço escolhem a data e que o primeiro dia
mantém o calendário aberto para escolher a segunda ponta. Recriar as células
após essa primeira escolha deve preservar o foco no dia ativo, para as setas e
Enter seguintes continuarem operando a grade.

Evidência: `var/cadastro-filtros-diagnostico.log`, cenário real da Lista de Ofícios
em 360 px, falha em `td[tabindex=0]` focado após o primeiro Enter. O método
`escolher` renderiza a grade e remove a célula focada sem focar sua substituta.
O teste anterior também falhava em fechar o período nos dois tamanhos.

Correção deve usar o método `focarInicial` existente após renderizar a primeira
ponta. Preserva eventos dos valores/HTMX, escolha invertida, clique, navegação de
mês e Escape. Validar filtro por teclado e consumidores compartilhados.

Validação posterior: seis cenários da gaveta passaram na rodada conjunta de
121s (outros dois casos de cadastro falharam no axe inicial, não no calendário).
O teste mantém asserção de foco na célula ativa após primeiro Enter, duas datas
diferentes, URL atualizada, Escape/retorno de foco e uma carga por módulo.
Log: `var/cadastro-filtros-foco-salvamento.log`. Regressões transversais pendentes.
