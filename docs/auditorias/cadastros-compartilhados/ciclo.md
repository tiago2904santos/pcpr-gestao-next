# Registro do ciclo obrigatório

## Observar

- 17/10/2026: Git inicial limpo (`git status --short`, saída vazia).
- Stack observada: Django, HTML/HTMX/Web Components, PostgreSQL; arquétipos e tokens existentes.
- `manage.py doctor`: DEV, PostgreSQL local 127.0.0.1; 15 migrações preexistentes pendentes. A base atual não será migrada; execução de testes em bases LAB separadas.
- Evidência de código: `dialogo_servidor.html` divide nome e cargo em duas colunas a 44rem; `components.css` limita modais comuns a 32rem e deixa todo conteúdo/ações rolarem juntos; cadastros rápidos podem manter dois dialogs modais abertos.

## Entender / projetar

- Regras documentadas em `docs/product/cadastros-compartilhados.md`; decisões estruturais em ADR 0044/0045.
- Inventário, catálogo e unidade investigados em paralelo conforme autorização explícita da missão. Alterações em componentes compartilhados sob responsabilidade do agente principal.
- Refinar componentes existentes, sem trocar identidade visual. Campos textuais longos em linha própria; rolagem de corpo com ações fixas em cadastros, preservando seletores flutuantes e retorno ao fluxo.

## Implementar / testar / comparar / criticar / corrigir / validar

Registro incremental nos relatórios e logs desta pasta. Uma etapa só será considerada concluída após seu resultado registrado; capturas e testes pendentes não equivalem a aprovação.

- **Implementar:** catálogo comum e fonte local em [catalogo.md](catalogo.md), navegação e contexto em [unidade.md](unidade.md), sete cadastros editoriais em [ascom-validacao.md](ascom-validacao.md). Componentes compartilhados mantêm tokens/arquétipos existentes e suspendem o modal de origem durante cadastro auxiliar.
- **Testar:** cenários de domínio, migração, permissões e integração no verificador; navegador para manutenção, cadastros rápidos e consumidores. Os comandos e resultados por rodada ficam no [relatório](relatorio.md), sem somar execuções sobrepostas.
- **Comparar:** 32 listas e 18 modais por largura têm [índice antes/depois](evidencias.md), além das capturas de unidade e ASCOM. Consultas e HTML de volume foram medidos com dados sintéticos; não se atribui ganho de latência a caches diferentes.
- **Criticar:** [revisão independente](revisao-final.md) verificou fronteiras de permissão, migração de ContentType, conservação histórica, propriedade de campos e seleção remota. A inspeção visual percorreu composições desktop/mobile e PNGs individuais.
- **Corrigir:** propagação de disabled para busca gerada; campo inicial preservado fora dos resultados; referências de choices reconectadas no widget remoto; guard de documento desmontado após carregamento assíncrono; espaçamento entre fieldsets e mensagens vazias em português. Testes passam a interagir com o checkbox customizado por teclado e auditam o documento no topo, sem relaxar regras de acessibilidade.
- **Validar:** `scripts/verificar.sh` integral verde no LAB Linux, com 2.816 testes aprovados, cinco avisos e saída zero; sem filtros adicionais ou skips. As 35 entidades têm estados finais e evidências no inventário. Navegador, capturas 360/1440, revisão visual e paridade estão nos relatórios dos lotes. O manifesto e as conferências de hashes comprovam a mesma versão do código. Nenhuma escrita ocorreu na base operacional nem em produção.

No fechamento, a inspeção detectou sobreposição real no efetivo móvel do Plano,
causada pela especificidade de `nth-child` genérico. Cargo/Unidade passaram à linha
completa e remover acompanha a quantidade; teste existente e axe foram aprovados.
O cabeçalho do evento reserva espaço para fechar. No anexo de certidões, o erro foi
trazido para o modal e a validade informada preservada; quatro testes de backend e
dois de navegador passaram. A medição do calendário usa estabilização de layout,
sem alterar posicionamento da aplicação para satisfazer uma captura transitória.

O fechamento integral corrigiu somente a infraestrutura de validação: a rodada
Windows encontrou três conversores indisponíveis; o LAB Linux usou os conversores
reais da imagem local, dependências pelo lock e PostgreSQL próprio. Arquivos não
versionados de outras tarefas foram preservados fora do snapshot; o `noexec` das
dependências temporárias foi resolvido usando a instalação da imagem. O script e
os testes permaneceram intactos. [Resultado final](verificar.log) e
[ambiente](ambiente-linux.md) registram as tentativas e o aceite.
