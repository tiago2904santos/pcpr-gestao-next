# CD01 — índice de Cadastros

Base352b3fb. Contrato em product/propagacao-identidade.md. Capturas reais em
evidencias/migracao-identidade-20261012/cadastros-indice-{antes,depois}-{360,768,1440}.png.
DEMO existente preservado, navegação GET/HEAD. Nenhuma gravação ou seed.

## Composição e componentes

Antes: cabeçalho de geração anterior e três listas estendidas à largura inteira,
com 1477px de altura no desktop. Depois: registro_hero compacto e grade--2
canônicos, com listas principais à esquerda e plano/configuração à direita;
934px no mesmo viewport/dados. Mobile continua com ordem semântica dos grupos,
sem comprimir textos. Tablet768 revisado integralmente, incluindo textos longos.

Extraído templates/componentes/lista_catalogo.html: titulo, identificador único,
itens com titulo/url/icone/texto, resumo e pendencia opcionais. Três consumidores
no índice. Mantidos os componentes registro, metadados, links expandidos e foco.
Nenhum CSS/JS novo. Bases antigas pagina_cabecalho/cartao/registro têm outros
consumidores e não foram apagadas. Removida a duplicação de três loops no consumidor.

## Validação

Capturas HTTP200, console vazio e sem overflow nas três larguras. Links e contadores
antes/depois registrados em JSON para comparação. Ruff verde. Suíte isolada
cadastros-indice-final em execução: navegador para operador/consulta nas três
larguras, permissões HTTP, catálogos do plano e tokens. Revisão independente solicitada.
Página ainda EM VALIDAÇÃO; não aprovada automaticamente pelo usuário.

Não se alterou query/view, recurso carregado, documento ou regra. Não se declara
ganho de latência; redução da altura é composição, não medição de desempenho.

## Fechamento

Suíte12084 terminou: **96 aprovados em112,58s**, incluindo seis cenários reais
de navegador. Revisão independente favorável ao candidato atual; sem bloqueante
novo. Links e contadores idênticos antes/depois nas três larguras.
Gate global e homologação visual do usuário permanecem pendentes.
