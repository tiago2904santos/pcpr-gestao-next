# Justificativas — retomada de 12/10/2026

Base: `3aa3462`, branch `codex/oficios-transporte-cartoes`. JU01 permanece
em validação; aprovação visual do usuário não presumida.

## Diagnóstico e intervenção

A lista preenchida com paginação aplicava `barra-acoes--acompanha` a uma
barra contendo somente contagem e nota informativa. Nas larguras 360, 768
e 1440, tanto no topo quanto após rolar 600 px, ela intersectava um registro.
Evidência: `../evidencias/migracao-identidade-20261012/justificativas-barra-antes.json`.

Retirada somente a aplicação condicional dessa variante no template de
Justificativas. A implementação canônica `barra-acoes--colecao` já mantém
a barra no fluxo. Nenhum CSS, script, documento ou regra foi alterado.
Outros consumidores com ações conservam sua variante aderente.

Depois: seis medições com `position: static` e zero interseções, registradas
em `justificativas-barra-depois.json`. As capturas dessa medição inicial
pegam a animação de entrada; não servem como aprovação de contraste.
Capturas finais aguardam fontes e animações finitas, em arquivos separados
`justificativas-refinado-*`, preservando o antes `justificativas-retomada-*`.

## Funcionalidade e verificação

A suíte anterior à intervenção terminou com **14 aprovados**, um aviso de
HarfBuzz, em 231,86 s (`logs/justificativas-retomada.log`). Abrange busca,
filtros, paginação, erro 422, conflito de versão, gravação manual, exclusão,
permissões, download PDF, foco e axe. Respostas 422/403 foram esperadas.

O teste de paginação após erro passou a exigir que a barra seja estática e
fique depois dos registros. Suíte posterior ativa: sessão **96068**, sete
casos de navegador incluindo compatibilidade com paginação de Planos,
banco e mídia isolados; resultado ainda pendente. Ruff aprovado.

Revisor independente `/root/descoberta_consumidores` confirmou a adequação
da mudança e preservação dos contratos; pede resultado e revisão da captura
paginada final antes do fechamento. Não encontrou outro bloqueante ou
implementação exclusiva cuja exclusão pudesse ser comprovada segura.

## Fechamento verificado

Sessão 96068 terminou com **7 aprovados, 1 aviso HarfBuzz, 190,05 s**.
Log `logs/justificativas-browser.log`; cenário reforçado de paginação e
compatibilidade de Planos passaram. As 12 capturas finais têm HTTP 200,
console sem erros e ausência de overflow nas três larguras. Inspeção própria
e revisão independente confirmaram último registro, paginação e barra em
sequência, além de ações e rodapé acessíveis no diálogo móvel.

Medições pós-alteração foram refeitas após aguardar as animações finitas;
mantêm zero sobreposição. Galeria ampliada para 734 imagens e validada em
360/1440, com PNGs e ZIPs íntegros. A página usa os componentes canônicos
existentes; não foi necessário criar CSS nem manter compatibilidade nova.

Desempenho: a mudança remove condição/classe no HTML e não acrescenta CSS,
JS, consulta ou requisição. Não se alega ganho de latência. O teste integrado
de consultas fixas passou na base, sem alteração posterior do backend.

JU01 concluída tecnicamente; homologação visual do usuário e gate global
permanecem pendentes. Próxima página VI01 — Lista de Viagens.
