# Formulários

## Estrutura
1. **Resumo de erros** no topo após envio inválido (`componentes/resumo_erros.html`), com
   links para cada campo e foco programático (WCAG 3.3.1).
2. **Seções numeradas** em cartões (`.cartao__numero`), na ordem em que a informação existe
   no mundo real (ex.: Ofício → Dados e viajantes → Roteiro → Diárias → Justificativa →
   Documentos).
3. **Índice lateral** fixo em formulários longos, com estado de cada etapa
   (concluída / pendente / atual).
4. **Barra de ações fixa** (`.barra-acoes`) no rodapé: status do salvamento à esquerda,
   ações à direita ("Salvar rascunho", "Emitir").

## Campos
- Rótulo acima, sempre visível; placeholder só como exemplo de formato.
- Obrigatório marcado com `*` (vermelho, `aria-hidden`) **e** atributo `required`;
  opcionais dizem "(opcional)" — reduz ambiguidade.
- Ajuda curta abaixo do campo (`.campo__ajuda`) ligada por `aria-describedby`.
- Erro abaixo, com ícone, em linguagem de solução: "Informe 9 dígitos (ex.: 26.655.434-6)".
- Máscaras leves (`data-mascara="protocolo|cpf"`) apenas como conforto: o servidor
  normaliza e valida de novo.
- Datas/horas nativas (`type="date"`/`"time"`).
- Seleções curtas (< 7 opções) → rádio; longas → `<select>` aprimorado por `<pc-combobox>`;
  buscas em cadastro grande (servidores, viaturas) → combobox remoto.

## Validação
- Fonte da verdade no **servidor** (formulário Django + regras de domínio).
- HTMX valida trechos sem recarregar (ex.: recálculo de diárias ao mudar trechos).
- Avisos não bloqueantes (conflito de agenda) usam `.alerta--aviso` com o texto
  "É só um aviso…"; bloqueios usam `.alerta--perigo`.

## Envio
- Botão mostra "carregando" e evita envio duplo (`app.js`).
- Sucesso: redireciona (POST/Redirect/GET) e mostra toast.
- Ações destrutivas pedem confirmação com consequência explícita.
