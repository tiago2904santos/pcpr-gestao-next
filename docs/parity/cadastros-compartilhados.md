# Cadastros compartilhados — 17/10/2026

Base de comparação: contratos existentes em `docs/product/`, inventário do código,
identidade aprovada das telas de Viagens e capturas locais anteriores à implementação.
Não foi realizada escrita nem nova inspeção em produção/referência nesta missão.

## Preservado

- Identidades de servidores, veículos, unidades, cargos, contas e vínculos; escopos
  institucionais documentados e autorização dos módulos consumidores.
- Manutenção por modal nos cadastros de Viagens/Coffee e por formulário incorporado
  nos catálogos simples de Eventos/ASCOM. Sem transformar catálogo pequeno em fluxo longo.
- Regras de campos obrigatórios, formatos, padrões, inativação e proteção por uso.
- Titulares por finalidade, substituições por período e fallbacks documentais da unidade.
- Instantâneos e arquivos emitidos; quantidades, observações e resultados continuam nos usos.

## Mudanças intencionais solicitadas

- Atividades/Serviços usam `AtividadePlano`, com proxy contextual de Eventos, mapa
  conservador de origens e preservação das permissões existentes. O nome original do
  serviço permanece no uso histórico e na exportação.
- Dados da unidade passa ao menu da conta, imediatamente após Alterar senha. A rota
  antiga e os links de orientação dos documentos continuam válidos.
- Hierarquia, tokens, cabeçalhos, largura útil, agrupamento, rolagem e ações dos
  cadastros seguem a linguagem de Viagens. Nomes/cargos/unidades recebem espaço de leitura.
- Uma etapa auxiliar substitui visualmente o modal anterior e retorna ao mesmo
  formulário com valores/foco preservados. “Cadastrar e incluir outro” conserva a etapa.
- Os sete catálogos ASCOM ganham busca/paginação e edição de palestrante sob demanda.
  Seletores de assinantes, vínculo de palestrante e motorista de Eventos usam busca
  limitada e preservam o atual, inclusive inativo já vinculado.
- Uma fonte dedicada poderá alimentar o espelho local por identidade externa e
  responsabilidade explícita por campo; não há integração externa instalada.

## Evidências

Inventário e relatórios: `../auditorias/cadastros-compartilhados/`.
Capturas completas: `evidencias/antes`, `evidencias/depois`, `ascom-capturas` e `unidade`.
Resultados dos comandos e fluxos são registrados nos logs dessa pasta; execuções
interrompidas ou com falhas permanecem identificadas e não equivalem à validação final.

Aceite de 17/10/2026: verificador completo verde no snapshot da missão, com 2.816
aprovados, cinco avisos e saída zero; código/testes/script intactos e hashes
conferidos. Capturas finais de 32 listas e 18 modais em 360/1440 foram revisadas,
além dos fluxos de unidade, ASCOM e consumidores. A preparação da origem externa
foi validada localmente; conexão real, migração operacional e deploy não fazem parte
deste aceite. Detalhes e limites no relatório da auditoria.
