# Ofícios — dados copiáveis para o eProtocolo (RS-01)

Fonte funcional consultada somente por leitura de código local em 07/10/2026:
`C:/Users/tiago/OneDrive/Documentos/Solicitações de eventos/viagens_oficios/services.py`,
função `dados_eprotocolo` (linhas 409–448). Complementos: `campos_modelo.py`, funções
`_periodo` e `valores_do_oficio`; `presenters.py`, `destinos_resumidos`; template
`templates/components/v32/copiaveis.html`. Nenhum banco ou sistema publicado foi consultado.
Direção aprovada: D18 em `docs/visual-agents/visual/oficios-detalhe-plano.md`.

O domínio puro recebe valores já selecionados pelo chamador, sem consultar Django,
cadastros, documentos ou integrações. Produz cinco campos, nesta ordem:

1. **Interessados:** nomes em ordem alfabética, separados por vírgula e espaço.
2. **Assunto:** linha do assunto seguida do rótulo, separadas por um espaço.
3. **Nº/Ano do ofício:** número já formatado pelo sistema, por exemplo `01/2026`.
4. **Protocolo:** nove dígitos recebem a máscara `12.345.678-9`; valores já formatados
   permanecem iguais. Valor vazio fica vazio. Validação institucional pertence ao serviço.
5. **Detalhamento:** `OFÍCIO Nº <número> - <LINHA DO ASSUNTO EM MAIÚSCULAS>`, seguido,
   quando presentes, de `DESTINO: …`, `PERÍODO: …` e `SERVIDORES: …`, separados por
   ` - `. Sem número, começa por `OFÍCIO`. O motivo segue em uma nova linha quando presente.

O rótulo do assunto, como `(Autorização)`, integra o campo Assunto, mas não a linha
do assunto usada no Detalhamento. A pontuação final `.` da linha é retirada somente
no Detalhamento. A regra que decide autorização/convalidação permanece no domínio
existente de assunto; esta função não toma essa decisão novamente.

Destinos chegam como rótulos `Cidade/UF`, na ordem do roteiro, sem o retorno à sede.
O domínio usa maiúsculas, até 100 rótulos, e acrescenta ` +N` quando excedidos,
como a fonte local. Não remove destinos repetidos nem nomes homônimos. Nomes vazios
são ignorados e espaços externos são retirados. A ordenação determinística de nomes
usa a ordem Unicode do Python; não promete reproduzir uma collation PostgreSQL específica.

Datas são `date` já convertidas para o dia local pelo chamador. Saída ausente produz
período vazio. Sem retorno, ou com retorno no mesmo dia, usa `dd/mm/aaaa`; nos demais
casos, `dd/mm/aaaa a dd/mm/aaaa`, inclusive quando muda o ano. O domínio não converte fuso,
não valida cronologia e não considera uma data de retorno isolada como período completo.

O retorno imutável contém os cinco pares de rótulo/valor e **Copiar tudo**, composto
pelos mesmos valores, cada um precedido por seu rótulo, separados por quebras de linha.
Copiar tudo é a melhoria prevista em D18; não existia na função legada consultada.

Limites desta etapa: sem serviço, tela, área de transferência ou chamada ao eProtocolo.
A montagem dos dados de rascunho versus snapshot emitido, autorização e aviso sobre
protocolo simulado/treinamento ficam para a integração com a aplicação.

## Evidência da base pura — 07/10/2026

Implementação: `gestao/viagens/dominio/eprotocolo.py`; testes:
`gestao/viagens/tests/test_eprotocolo.py`. Workspace sobre HEAD `8d1d77e`, arquivos
novos ainda sem commit. Ruff dos dois arquivos: verde. Testes: **17 passaram em 0,15 s**.
Execução: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest --noconftest
-o addopts='' gestao/viagens/tests/test_eprotocolo.py -q`. Sem plugin Django, conftest,
fixtures de aplicação ou acesso ao banco. O aviso de configuração desconhecida
`DJANGO_SETTINGS_MODULE` é consequência da desativação deliberada do plugin Django.

Cobertura: cinco campos comparados integralmente com o formato da fonte, data única,
período entre anos, saída ausente, ordenação/homônimos, máscara do protocolo, texto e
quebras de linha do motivo, ausência de dados, assunto complementar, ordem/limite de
destinos e consistência de Copiar tudo. Integração visual e Clipboard não testados aqui.
