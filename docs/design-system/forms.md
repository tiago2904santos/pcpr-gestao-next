# Formulários

## Estrutura
1. **Resumo de erros** no topo após envio inválido (`componentes/resumo_erros.html`), com
   links para cada campo e foco programático (WCAG 3.3.1).
2. **Seções numeradas** em cartões (`.cartao__numero`), na ordem em que a informação existe
   no mundo real (ex.: Ofício → Dados e viajantes → Roteiro → Diárias → Justificativa →
   Documentos).
3. **Faixa de progresso** fixa sob o topo em formulários longos (`nav.progresso--fixo`),
   com o estado de cada seção; o índice lateral ficou só como arquétipo.
4. **Barra de ações fixa** (`.barra-acoes`) no rodapé: status do salvamento à esquerda,
   ações à direita ("Salvar rascunho", "Emitir"). No celular a barra é uma linha só de
   botões; o aviso "Alterações não salvas" flutua **acima** dela (chip âmbar) para que os
   botões nunca mudem de lugar no instante do toque.

## Campos
- Rótulo acima, sempre visível; placeholder só como exemplo de formato.
- Obrigatório marcado com `*` (dourado, `aria-hidden`) **e** atributo `required`. Opcional
  **não leva sufixo**: marcar os dois lados era ruído em todo rótulo (refinamento V2).
  O único sufixo é "(necessário para emitir)": campo livre no rascunho, exigido para emitir.
- Senhas usam `componentes/campo_senha.html`: botão "mostrar/ocultar" dentro da caixa
  (`aria-pressed`, `aria-controls`; sem JavaScript não aparece).
- Ajuda curta abaixo do campo (`.campo__ajuda`) ligada por `aria-describedby`.
- Erro abaixo, com ícone, em linguagem de solução: "Informe 9 dígitos (ex.: 12.345.678-9)".
- Máscaras leves (`data-mascara="protocolo|cpf"`) apenas como conforto: o servidor
  normaliza e valida de novo.
- Datas e horas com os seletores próprios (`<pc-data>`, `<pc-hora>`, ADR 0014); nunca os do navegador.
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
