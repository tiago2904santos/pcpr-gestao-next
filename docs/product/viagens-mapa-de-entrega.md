# Viagens — mapa de entrega, melhorias e implementações

Revisão de 26–27/10/2026, feita sobre o ramo que roda na produção
(`release/producao-2026-10-26`). Ela teve três frentes:

- **Rastreio automático:** 1.330 páginas visitadas com o usuário de todos os papéis. Nenhuma
  deu erro 500.
- **Auditoria do código:** quatro frentes — ofício e viagem, documentos, prestação de contas e
  telas (JavaScript) — com 52 achados.
- **Testes de regressão:** um teste para cada defeito corrigido, em
  `gestao/viagens/tests/test_correcoes_entrega.py`.

## 1. O que foi corrigido nesta entrega

### Ofício e viagem
| Defeito | Efeito para o usuário | Correção |
|---|---|---|
| Trocar o número de um ofício já emitido (retificado/reaberto) devolvia o número antigo à fila | Dois ofícios com o mesmo número no papel | O número antigo só volta à fila se o ofício nunca foi emitido; a troca usa a mesma trava da reserva |
| Remover o mesmo servidor duas vezes (clique duplo, outra aba) | Erro 500 | Mensagem "já não está na equipe" |
| `id`/motorista adulterados no formulário da equipe | Erro 500 | Mensagem na própria seção |
| "Duplicar" copiava a data digitada e o marcador "Retificado" | Cópia com data velha (prazo/justificativa errados) e impressa como retificada | A cópia nasce com a data de hoje e sem marcador |
| Renomear destinos pelo texto ("B, B") | Trecho de uma cidade para ela mesma, diárias erradas | Recusado com explicação |
| Gerar documentos em lote com quem dirige em outra equipe | Erro 500 (KeyError) | Mensagem junto das outras validações; motorista sem viatura vira aviso |
| Gerar/Repetir com servidor inativo, unidade sem configuração ou sem permissão de termo/OS/plano | Erro 500/403 | Mensagem na tela; servidor inativo fica de fora ao repetir |
| Repetir viagem sem período: data-base em UTC | Toda a viagem repetida um dia antes | Data local |
| Documentos criados numa viagem de outra unidade | Ofícios invisíveis para a unidade da viagem | Só na viagem da própria unidade (política `pode_gerar_documentos_da_viagem`) |
| Viagem com o pedido (e-mail/ofício) anexado contava como "vazia" | "Excluir as vazias" apagava o pedido; outra pessoa reaproveitava a viagem | O anexo, o termo e o roteiro tiram a viagem de "vazia" (lista, resumo e exclusão) |
| Busca de viagens por ofício ("15/2026") | Contagem de ofícios errada na linha | Busca por subconsulta |
| Exportar a lista de ofícios ignorava a ficha "Atenção" | Planilha com a aba inteira | Mesmo recorte da tela |
| Cancelar/reativar viagem com ofício arquivado | Cancelamento inteiro falhava | O arquivado fica como está; erros dos documentos viram mensagem |

### Prestação de contas
| Defeito | Efeito | Correção |
|---|---|---|
| Texto editado do diário de bordo e do RT congelava os dados | km lançados depois, troca de motorista ou viatura não chegavam ao PDF nem ao pacote | Fusão a três (como no ofício e no termo): a edição fica e os dados acompanham |
| Reemitir ofício depois de tirar da equipe quem já tinha anexo | Erro 500 (ProtectedError) e emissão desfeita | A linha com anexo só sai da equipe |
| Diário "motorista de outro ofício" aceitava ofício de outra unidade | Vazamento de nome, CPF, placa e km de outra unidade | Só ofício visível e não cancelado; também impede encadear diários |
| Comprovante importado sem valor | A conferência "os comprovantes somam R$ X" nunca disparava | Data e operação lidas do PDF; valor só quando rotulado ("Valor: R$ …") |
| "Usar no comprovante" com Transferência/Depósito | Apagava a operação | Aceita o rótulo com ou sem acento |
| Imagem corrompida ou gigante no pacote | Erro 500 no PDF do pacote | Mensagem dizendo qual arquivo substituir |
| km "45678,9" no diário | Gravado como 456789; número enorme dava erro 500 | Mesma regra do link de km (até 7 dígitos; o décimo cai) |
| Autosave do RT | Uma pendência de envio nova a cada pausa na digitação | A pendência só se refaz quando muda o que ela leva (RT pronto, diária, custeio) |
| Gravar o diário acertava as linhas antes de conferir a permissão | Quem não podia gravar ainda mexia nas linhas | Confere a permissão antes |
| Valor gigante em comprovante/diária | Erro 500 (DataError) | Recusado com mensagem |

### Documentos (ofício, justificativa, OS, plano, termo)
| Defeito | Efeito | Correção |
|---|---|---|
| "Aplicar" da conferência da viagem mudava o período da OS sem o do evento | Folha, PDF e "baixar tudo" da OS com erro 500 | O evento é recortado ao período novo (e a folha corrige dados antigos) |
| Word de ofício migrado do sistema anterior | Ofício em branco | Mensagem: baixar o PDF original |
| Texto editado da OS e do plano congelava equipe, datas, destinos e quem assina | Documento com dados antigos (e dois signatários) | Fusão a três, com o modelo guardado (migração `0064`) |
| Cor/tamanho aplicados em parte de um campo amarelo | O valor saía repetido no PDF | O campo nunca se parte (JS) e o servidor tira marcação de dentro do campo |
| Motivo/justificativa com quebra do Windows | "Voltar ao original" de um bloco devolvia um pedaço errado | Quebras normalizadas e posições contadas só por `\n` |
| Estilos salvos pelo editor não apareciam na tela (CSP) | Tela diferente do PDF | Reaplicados pelo CSSOM, sem afrouxar a CSP |
| "Sem diárias diárias" no ofício | Texto errado no documento oficial | Corrigido |
| Editores de termo/OS/plano marcavam regiões já fundidas como desatualizadas | Aviso falso | Mesmo critério do ofício |
| Texto padrão da OS sem cargo/sem período | "O deslocamento Fulano…", ", ," | "O deslocamento de Fulano…"; vírgulas certas |
| "zero real" | Português | "zero reais" |

### Telas (JavaScript)
| Defeito | Correção |
|---|---|
| Campo amarelo do documento dava "outra pessoa salvou" depois de qualquer autosave do formulário | Usa a versão mais nova (formulário ou editor) e grava um campo por vez |
| Duas gravações do texto ao mesmo tempo conflitavam entre si | Uma por vez; o que mudou no meio grava em seguida |
| A folha recarregava por cima de um campo sendo digitado | Espera o campo gravar |
| Termo com mais de 10 destinos travava a aba (laço infinito) | Respeita o teto e avisa; respostas fora de ordem ignoradas |
| "Preencher pelas distâncias" lia "12.345" como 12 | Lê como o servidor |
| Aviso de rota estimada/indisponível nunca aparecia | Elemento de aviso de volta na rota |
| Tempos preenchidos pela rota não eram gravados | Avisam o autosave |
| Sair da página sem mexer gravava (versão subindo à toa) | Ponto de partida refeito depois que os componentes montam e depois de cada gravação |
| Calendário de período lembrava meio período ao reabrir | Cada abertura começa um período novo |
| Lista do combobox reabria depois de sair do campo | Busca cancelada ao sair |
| Duas confirmações ao mesmo tempo quebravam o diálogo | Fila de confirmações |

## 2. Depende de decisão ou de terceiros (não é código)

| Item | O que destrava |
|---|---|
| eProtocolo real (consulta e envio) | Credenciamento na Celepar (PDS Mantis), usuário de sistema, `consumerId`, IP fixo |
| WhatsApp oficial (envios automáticos) | Conta Meta Business da instituição; hoje os envios são manuais (aba Pendências) |
| E-mail (esqueci a senha, avisos) | SMTP institucional |
| IA e automações | Ligadas por chave (`IA_HABILITADA`, `AUTOMACAO_HABILITADA`); hoje desligadas por decisão |
| Backup fora da VPS | Destino externo (restic/S3); hoje só backup local + pacote cifrado |
| DNS `n8n.` | Registro `A` no domínio |
| Credencial de transporte do n8n | Vence por volta de 17/04/2027: renovar |
| Nome da unidade na configuração | Corrigir "Comunicaçãosocial" → "Comunicação" (Cadastros › Configuração da unidade) |
| Ramo `main` | Tem marcas de conflito de um merge antigo e trabalho de outra sessão sem commit; a produção roda o ramo `release/…`. Unificar antes de qualquer nova frente |

## 3. Melhorias recomendadas (em ordem)

### Alta — confiabilidade
1. **Diário de bordo casar km com o trecho pela rota, não pela posição.** Inserir ou tirar um
   trecho no meio (retificação) pode deslocar km para o trecho errado. Casar por
   (origem, destino, ordem).
2. **Visualizador da viagem mostrar o ofício emitido congelado** (o PDF arquivado), não
   reconstruído com os dados de hoje.
3. **Avisar quando a fusão do texto editado não conseguiu levar uma edição** (hoje a edição
   em conflito some sem aviso): listar os blocos e oferecer "reaplicar".
4. **Saída da página com gravação a caminho:** o envio de última hora (beacon) vai com a
   versão anterior e é recusado; enviar marcado como "saída" e aceitar pelo número da versão.
5. **Lentidão:** a pauta da agenda leva de 3 a 10 s e a exportação de ofícios 7 s com os dados
   de demonstração. Medir com os dados reais e otimizar as consultas.

### Média — uso diário
6. Aprovar/devolver prestação com permissão própria (quem prepara não aprova).
7. "Os comprovantes somam…" abrir o comprovante certo para corrigir, e "comprovante sem
   valor" virar pendência.
8. Mostrar "texto editado desatualizado" também na folha e antes de baixar PDF/Word.
9. Desfazer depois de arquivar (e tirar a confirmação).
10. Lote: esconder termos/OS/plano que o usuário não pode criar; avisar motorista sem viatura
    já na tela.
11. Calendário do itinerário: o foco do teclado se perde ao trocar de mês.
12. Textos prontos: falha de rede aparece como "nenhum texto" e não tenta de novo.
13. Mapa do itinerário traçar só a primeira rota (pedido antigo).

### Baixa — acabamento
14. Categoria da viatura (ônibus, caminhão, unidade móvel) como campo do cadastro.
15. Número de ofício: confirmar quando o piso pula muito acima do maior usado.
16. Ajuda de digitação nos campos de hora (setas gravam cada hora intermediária).
17. Os módulos JS carregam por endereço sem hash: depois de uma implantação, o navegador pode
    misturar arquivo velho e novo. Ativar a reescrita de `import` no `collectstatic`.

## 4. Implementações novas sugeridas

| Ideia | Valor |
|---|---|
| Assinantes por tipo de documento e substituição por período (férias do titular) | Hoje há um signatário por unidade |
| Endereço da configuração em campos, com consulta de CEP | Rodapé sempre bem formatado (evita "Comunicaçãosocial") |
| Painel "dados para a Central de Viagens / eProtocolo" com botões de copiar | Alívio imediato enquanto a integração não existe |
| Revisão página a página do pacote da prestação (ordem, giro, ocultar) | Pacote pronto para o eProtocolo sem editar PDF fora |
| Carimbo automático do número de solicitação no ofício assinado | Menos passos manuais na prestação |
| Ofícios do motorista de outra unidade: sugerir os do mesmo período | Diário de bordo mais rápido |
| Relatórios gerenciais (diárias por período, por servidor, por unidade) | Prestação de contas institucional |

## 5. Como conferir

- Testes rápidos de Viagens:
  `uv run pytest gestao/viagens -m "not e2e and not visual and not a11y and not perf" -n auto`.
- Regressões desta entrega: `uv run pytest gestao/viagens/tests/test_correcoes_entrega.py`.
- Migração nova: `0064_modelos_da_edicao_os_e_plano` (só acrescenta colunas; sem perda de
  dados). A implantação aplica sozinha.
