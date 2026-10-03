# ADR 0018 — Editor de documento dentro do visualizador

**Status:** aceita · **Data:** 2026-10-03 · **Paridade:** R6 (editor de documento completo,
overrides de parágrafo, quebras, modelos de texto)

## Contexto
O sistema de referência tem um editor de documento completo: regiões do HTML editáveis no
navegador, versões append-only com restauração e "voltar ao modelo", override por bloco
(parágrafo e quebra de página), modelos de texto reutilizáveis, campos editáveis pela origem,
concorrência por versão, presença, pendências navegáveis e indicador de páginas
(`docs/parity/oficio.md`, linha "Editor de documento completo": **regressão**). Aqui só havia
a minuta em PDF: um ofício com redação a corrigir não tinha saída dentro do sistema.

O dono do produto decidiu: o editor fica **dentro do visualizador**, no cartão Documentos da
folha do ofício — não numa página separada — e **não pode ter menos recursos** do que o da
referência (pode ter mais). O código da referência é só referência: nada foi copiado.

## Decisão
1. **A folha é o documento.** O mesmo HTML que vira PDF (`viagens/documentos/*.html`) é servido
   em modo *folha* (`/viagens/oficios/<pk>/documento/<tipo>/folha/`) dentro de um iframe da
   própria origem. `folha.css` dá o aspecto de papel, as marcas de edição e as páginas; o
   estilo de impressão é o mesmo do PDF (entra com o *nonce* da requisição). O componente
   `<pc-editor-documento>` (fora do iframe) torna as regiões editáveis e opera a barra.
2. **Marcação no modelo**, com tags próprias (`viagens/templatetags/documentos.py`):
   `{% regiao "corpo" "Corpo do ofício" %}…{% endregiao %}` delimita o que pode ser escrito;
   `data-bloco="chave" data-rotulo="…"` nomeia as peças (histórico legível, "voltar ao
   original" por bloco, página de cada bloco); `{% campo_vinculado "motivo" d.motivo %}`
   marca um **campo vivo**: o valor vem do cadastro em toda renderização, mesmo quando a
   região em volta foi editada, e escrever nele grava no ofício; `{% ponto_de_quebra %}` é
   uma quebra de página que se liga e desliga (e o editor insere quebras livres).
3. **Versões append-only** (`EdicaoDocumento`): uma linha por salvamento, restauração
   (`restaurada_de`) ou "voltar ao modelo" (`regioes == {}`); a vigente é a de maior
   `numero`. Só regiões que diferem do modelo são guardadas, já **saneadas** no servidor
   (`documentos/regioes.py`: lista branca de tags, atributos e classes; `style` só com
   `text-align`). Salvamentos seguidos da mesma pessoa em 10 min atualizam a mesma versão
   (histórico legível; a trilha do banco guarda cada UPDATE — ADR 0004). A versão guarda a
   **impressão** (sha256) de cada região como o modelo a gerava: se o cadastro mudar depois,
   a folha avisa que o texto editado ficou para trás.
4. **Emissão** congela também o texto: `Documento.dados["edicao"]` leva as regiões em vigor e
   `Documento.edicao` aponta a versão; o PDF/A sai do instantâneo (ADR 0008 continua valendo).
5. **Concorrência**: salvar envia `versao_base` (número da versão vigente ao começar) → 409
   `ConflitoDeEdicao` se outra pessoa salvou antes; campos vinculados usam a mesma `versao`
   otimista do formulário (o formulário da folha acompanha o valor e a versão). Presença
   (quem mais está na folha) fica no cache por 90 s.
6. **Autorização** em `policies.py`: `pode_editar_texto` = `pode_editar` (só rascunho);
   `pode_gerir_textos_prontos` = `cadastros.add_modelotexto` (operador e gestor). Toda escrita
   passa por `services.py`: `salvar_texto_do_documento`, `restaurar_texto_do_documento`,
   `voltar_texto_ao_modelo`, `salvar_campo_do_documento`, `criar_texto_pronto`,
   `desativar_texto_pronto`.
7. **Textos prontos** reutilizam `cadastros.ModeloTexto` (tipo novo `oficio` para trechos do
   editor; `motivo`/`justificativa` também entram), com `padrao_sistema` para os que vêm com
   o sistema (nunca apagados pelo editor).
8. **Páginas** calculadas pelo mesmo motor do PDF (`paginas_do_documento`: WeasyPrint
   renderiza e devolve em que página cada bloco começa) — sem pdf.js no cliente.

### Recursos (paridade com a referência, e a mais)
| Referência | Aqui |
|---|---|
| Regiões editáveis (cabeçalho/corpo/rodapé) | idem, marcadas no modelo |
| Barra `execCommand` | negrito, itálico, sublinhado, limpar, listas, 4 alinhamentos, desfazer/refazer, Ctrl+S |
| Saneamento no servidor | lista branca (`sanear_html`) |
| Versões append-only, restaurar, voltar ao modelo | idem + coalescência de 10 min + impressão por região (aviso de texto desatualizado) |
| Blocos: override por parágrafo, quebra de página | blocos nomeados; **voltar ao original por bloco**; pontos de quebra do modelo + quebras livres; destaque dos blocos alterados |
| Modelos de texto + gestão | textos prontos no editor: inserir, **guardar a seleção como texto pronto**, remover (exceto padrão do sistema) |
| Campos editáveis pela origem, com conflito 409 | campos vinculados vivos dentro do documento; 409; o formulário da folha acompanha |
| Presença | idem (cache, 30 s) |
| Histórico legível | versões com blocos alterados, autor, hora; **ver** qualquer versão na própria folha; `Historico` do ofício registra cada versão |
| Pendências navegáveis | aviso com atalho para o campo na folha (ou para o cartão) |
| Indicador de páginas (pdf.js) | contagem e **marca de página por bloco**, pelo motor do PDF |
| Colar como texto puro, tabelas, quebra | idem (tabela com linhas × colunas) |
| Editor embutido | o editor **é** o visualizador; modo PDF ao lado (minuta com marca d'água) |
| DOCX | fora deste ADR (decisão pendente em `docs/parity/oficio.md`, linha "Documentos — formatos") |

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Página separada de edição (como na referência) | Decisão do dono: a função de editar fica no visualizador. Menos navegação, um só lugar para ver e corrigir. |
| Editor de blocos próprio (ProseMirror, ADR 0007) | Peso e dependência; o documento é curto e tabular, `contenteditable` + saneamento no servidor bastam. Reavaliar se a redação virar o centro do produto. |
| Guardar o HTML inteiro do documento | Congela tudo, inclusive dados do cadastro. Regiões + campos vivos mantêm o que vem do cadastro sempre atual. |
| Nova versão a cada tecla | Histórico ilegível. A coalescência de 10 min por pessoa resolve; a trilha do banco continua completa. |
| Contar páginas no cliente (pdf.js) | Dependência pesada no front; o servidor já tem o motor. |

## Consequências
- Positivas: redação corrigível sem sair do sistema; paridade com a referência e mais;
  nenhuma dependência nova no front; segurança (CSP com nonce e `frame-ancestors 'self'`
  só nesta resposta; saneamento no servidor; escrita só por serviços; auditoria no banco).
- Negativas / cuidados: uma região editada **congela** o texto gerado em volta (equipe,
  roteiro, diárias dentro do corpo): a folha avisa quando o cadastro muda e oferece "voltar
  ao modelo". `contenteditable` varia entre navegadores; o saneador normaliza. Presença em
  cache local não atravessa processos (basta para um `web` só; com vários, trocar o cache).
- Obrigatório: modelo novo de documento marca regiões, blocos e campos vinculados; campo
  novo que apareça no documento entra em `documentos/campos.py`; componente novo nasce no
  UI Lab (`/ui-lab/#editor`).
