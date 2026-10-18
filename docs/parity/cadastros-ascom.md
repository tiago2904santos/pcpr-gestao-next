# Cadastros de apoio ASCOM — 17/10/2026

Abrange C29–C35 do [inventário](../auditorias/cadastros-compartilhados/inventario.md): palestrantes, temas, respostas padrão, equipe/veículos da Imprensa e equipe/unidades responsáveis de Publicações.

A comparação funcional parte das regras já documentadas em `docs/product/permissions.md`, dos modelos e serviços locais e dos testes dos três módulos. Não houve escrita na referência nem em produção. Os cadastros continuam específicos do domínio: parceiro da ASCOM não vira conta ou servidor automaticamente; veículo jornalístico não é viatura; unidade editorial não define lotação institucional.

- URLs de manutenção e seletores consumidores preservadas. Acrescentada busca, contagem filtrada, paginação de 25 e estado sem resultados. Filtros seguem após salvar e ao paginar.
- Criação incorporada e edição por registro mantidas. Para o cadastro completo de palestrante, Editar abre apenas o formulário solicitado por GET; funciona sem JavaScript e evita carregar todos os servidores por registro da lista. Erros mantêm os valores e o registro aberto; Cancelar volta sem gravar.
- As mesmas policies protegem GET e POST. IDs inválidos agora retornam 404, inclusive Unicode incompatível, texto ou valores excessivamente longos; não caem em inclusão nem erro interno.
- Exclusão em uso continua recusada; contagens por documento preservam a regra de uma pessoa em duas/três funções contar uma vez. O PostgreSQL faz a agregação somente para os registros da página.
- Palestrante conserva servidor atual inativo; novo vínculo arbitrário a outro inativo é recusado. A edição não altera a conta de usuário nem concede privilégios.
- A busca de servidor em Palestrantes é remota e limitada a 15, com endpoint autorizado pelo próprio módulo e fonte canônica local. Não acrescenta exigência de permissão de Viagens; o vínculo atual é renderizado mesmo fora dos resultados ou inativo.
- Identidade visual usa `registro_hero`, tokens e `colecao-operacional` de Viagens. Campos longos de palestrante ocupam a linha, contatos/localidade têm agrupamento proporcional; formulário simples continua direto. Não foram criadas novas telas ou regras de inativação para entidades sem campo ativo.

Evidências funcionais e visuais, cenários e limites: [ascom-validacao.md](../auditorias/cadastros-compartilhados/ascom-validacao.md), [capturas e cobertura por rota](../auditorias/cadastros-compartilhados/ascom-capturas/cobertura-360.json), [cobertura desktop](../auditorias/cadastros-compartilhados/ascom-capturas/cobertura-1440.json).
