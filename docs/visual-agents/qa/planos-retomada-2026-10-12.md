# Planos PT01–PT04 — revisão do candidato atual

Base 9b3ccae. Contratos em product/propagacao-identidade.md e evidências
anteriores em planos-lista, planos-folha e planos-resultados-identidade-2026-10-10.
Dados DEMO preservados; suíte mutável com banco/mídia isolados.

21 capturas atuais: lista, novo, incompleto, multievento, gerado, diálogo de
evento e resultados nas larguras360/768/1440. Capturas complementares mostram
destinos, efetivo, diárias, atividades, eventos e editor em tamanho legível;
diálogo com topo e rodapé nas três larguras. Ações finais acessíveis por rolagem,
sem extrapolar a janela. Não usar apenas screenshot integral para aprovar modal.

Falhas dos scripts de captura, sem alteração do produto: iframe lazy ainda
invisível; wrapper display:contents sem caixa; espera networkidle impedida por
requisições em segundo plano. Corrigido para rolar #previa e aguardar conteúdo e
fontes; diálogo aguarda estado visível. Não ocultados controles nem substituído
documento oficial.

Revisão independente favorável aos contratos: filtros/querystring/OOB,
autosave/version/data-vivo, efetivo por evento, diárias e bloqueio de geração;
Resultados mantém salvamento manual, zero/digitado/atividade retirada e relatório
dos salvos. Limpeza anterior tabela--resultados/relatorio-final permanece válida;
substitutos lancamento_quantitativo/leitura-textual com consumidores no UI Lab.
Classes programa-plano/coordenador/atividades/linhas/evento-plano são legítimas.

Defeito visual identificado na segunda passada: controles de coordenação dividem
linha móvel e truncam origem e rótulo de tratamento. Ajuste planejado na variante
canônica, sem mudar campos/regras. Suíte34447 ainda em execução sobre a base;
aguardar antes de editar CSS e associar seus resultados à revisão correta.

Dívidas históricas: SQL acima do budget na Folha, número manual ausente e
controles globais parcialmente recortados em scroll. Nenhum budget aumentado.
Homologação do usuário e gate global continuam pendentes.

## Correção de coordenação

34447 terminou:62 passed,1 warning,415,61s antes do ajuste CSS. Prova de largura
planos-coordenacao-antes.json: origem precisa138px no celular e dispõe100px;
desktop dispõe86px para121px. Não era apenas percepção da captura.

Variante corrigida na origem: uma coluna mobile, duas tablet e colunas desktop
com4,5 unidades esp-12 para origem/tratamento. Campos condicionais mantidos.
planos-coordenacao-depois.json comprova textos visíveis sem truncamento em
360/390/768/1024/1440. Imagens antes/depois do mesmo Plano2 preservadas.
Teste existente ganhou assertiva de leitura integral dos valores visíveis.
Ruff aprovado. Reteste67345 ativo: preparação/quantitativos/autosave/calendário,
evento/validação/PDF e tokens. Não declarar resultado até término.

## Fechamento

67345 terminou:72 passed,2 warnings,310,57s. Avisos: HarfBuzz e conexão residual
no teardown do banco TEST isolado. Houve diagnóstico de consulta da fixture
demorada: pg_stat_activity mostrou SELECT ativo sem wait_event; a mesma execução
progrediu até o resultado terminal, sem reinício nem alteração de timeout.

Origem manual também exercitada no formulário novo por controles reais, sem
salvar DEMO: campos cadastrais desaparecem, nome/cargo manuais aparecem e valores
cabem nas cinco larguras. Evidência planos-coordenacao-manual.json e PNGs.
Revisor confirmou correção e diálogo com rodapé visível; captura inicial incompleta
não foi usada para aprovar o modal.21capturas finais sem console/overflow externo.

PT01–PT04 concluídas tecnicamente,19/100. Galeria722imagens validada em360/1440,
ZIPs e originais íntegros. Hashes e custo CSS em planos-refinado-candidato.json.
Sem JS, HTML, consulta ou dependência nova nesta correção; não alegar ganho de
latência. Remoções anteriores revalidadas, nenhuma exclusão adicional sem prova.
Homologação visual do usuário pendente. Próxima página JU01 Justificativas.
