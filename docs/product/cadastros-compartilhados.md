# Cadastros compartilhados — missão de 17/10/2026

Fonte: solicitação integral do usuário nesta missão; complementa entities.md e permissions.md.

- Atividades do Plano de Trabalho e Serviços de Eventos Sociais são um catálogo único. Quantidades, ordem, observações e instantâneos pertencem ao uso, não ao catálogo. A migração mantém identidades existentes e mapeia explicitamente as origens; nome igual não basta para mesclar entidades.
- Pessoa/servidor, conta, lotação, cargo e assinante permanecem conceitos separados. Compartilhar não concede permissões; conservam-se os escopos vigentes documentados em permissions.md (inclusive cadastros institucionais globais).
- Dados da unidade aparece imediatamente após Alterar senha no menu da conta. Identifica a unidade atual, conserva autorização por objeto e as funções documentais/assinantes/substituições existentes. A rota antiga continua compatível.
- A fonte atual continua local. Uma futura origem dedicada deve mapear identidade externa para identidade interna estável e declarar responsabilidade por campo. Alterações locais válidas não podem ser sobrescritas silenciosamente.
- Cadastros seguem os tokens/arquétipos de Viagens: nomes/cargos/unidades com largura de leitura; erros e ajuda sem desalinhamento; listas com busca, situação e paginação quando aplicável. Modais extensos têm ações acessíveis e uma só área principal de rolagem; no celular os campos longos ocupam uma linha.
- Cadastro rápido preserva o formulário de origem, atualiza e seleciona o novo registro, e retorna o foco. Apenas uma superfície de cadastro deve permanecer ativa por vez.
- Validação mantém os valores digitados e mostra a orientação na superfície ativa. No anexo de certidões, o erro de PDF aparece dentro do modal e a validade informada permanece preenchida ao reabrir após erro.
- Seleção remota individual reutiliza `pc-combobox`: o HTML contém somente o registro atual, mesmo inativo, e a busca devolve até 15 opções autorizadas. Digitar outro nome limpa o ID anterior; selecionar acrescenta a opção ao controle enviado. Sem JavaScript o vínculo atual permanece legível e preservado, e a interface informa que é necessário ativá-lo para buscar outro. O backend valida a escolha pelo queryset completo autorizado, independentemente das opções desenhadas.
- Documentos emitidos e versões arquivadas mantêm seus instantâneos; inativação retira a opção de usos futuros sem apagar vínculos históricos. Exclusão segue proteção por uso.

## Evidência e execução

Motoristas em Eventos seguem a mesma fonte local canônica de servidores. A busca
de seleção é limitada a 15 ativos e autorizada pelo contexto da solicitação (ou
criação de solicitação), sem conceder consulta administrativa/CRUD de servidores.
Nome, cargo e unidade identificam a escolha. Somente o vínculo atual pode conservar
um servidor inativo; nenhum inativo novo é aceito. A opção atual aparece no HTML
mesmo fora da primeira página de busca. O campo continua pertencendo ao formulário
da solicitação, inclusive no combobox remoto.

Na lista central, os usos do catálogo apresentam separadamente conjuntos, planos e
solicitações. As contagens são subconsultas independentes para não multiplicar linhas
por joins nem executar uma consulta por registro.

Particularidade do catálogo: meta/recurso são complementos do Plano e podem estar
vazios em serviços vindos de Eventos. O formulário de atividade do Plano pede meta.
A regra documental existente permite atividades/metas em branco mediante aviso;
serviços selecionados sem meta recebem aviso específico para completar o complemento
em Atividades e serviços, preservando rascunho e emissão conforme essa regra.

Inventário e acompanhamento: `docs/auditorias/cadastros-compartilhados/`. Verificação em bases PostgreSQL LAB locais distintas, com fixtures sintéticas. Não aplicar migrações na base de operação nem fazer deploy.
