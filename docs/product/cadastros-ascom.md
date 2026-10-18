# Cadastros de apoio da ASCOM

Regra de refinamento autorizada pela missão de cadastros em 17/10/2026; observação do código em `docs/auditorias/cadastros-compartilhados/inventario.md`, C29–C35.

Os sete catálogos de Palestras, Imprensa e Publicações mantêm suas identidades e permissões atuais. São cadastros pequenos de domínio e podem usar criação e edição incorporadas, com a identidade visual de Viagens. A navegação oferece busca, contagem total filtrada, estado sem resultados e até 25 registros por página, conservando filtros na paginação e após salvar. Busca em palestrantes considera nome, lotação e divisão; respostas padrão considera tipo e mensagem; demais catálogos considera nome. Um termo sem resultados não esconde o formulário de inclusão.

O cadastro completo de palestrante pode vincular um servidor institucional ou permanecer sem vínculo (pessoa externa). A escolha usa busca remota do próprio contexto Palestras, com as mesmas permissões de manutenção do formulário, máximo de 15 servidores ativos e identificação por nome/cargo/unidade. Não exige nova permissão de cadastro de Viagens. A edição conserva o servidor atual mesmo inativo e sua identificação no HTML, independentemente da página de busca; novos vínculos só usam servidores ativos. A inatividade não apaga vínculo nem autoriza mudança nos documentos anteriores. Sem JavaScript o vínculo atual é preservado; escolher outro requer a busca.

Formulários completos de edição de palestrantes são montados apenas para o registro cuja edição foi solicitada. O link Editar funciona sem JavaScript; salvar com erro preserva campos e mantém aberto o registro. A página não deve gerar um seletor de todos os servidores por palestrante apenas para mostrar a lista. Todos os seletores continuam sujeitos à validação no backend.

Consulta e manutenção permanecem nas policies existentes; filtro ou paginação não concedem acesso. Identificadores adulterados, inclusive números Unicode incompatíveis ou excessivamente longos, devem ser rejeitados sem erro interno. Exclusão continua protegida quando há uso histórico.
