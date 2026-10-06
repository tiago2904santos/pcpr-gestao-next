# Identidade de referência — o padrão canônico (Roteiros e Termos)

> Agente 2 — UI/UX Design Lead · 2026-10-06 · etapa de estudo (nenhum código alterado).
> Fonte: código do NOVO (caminhos abaixo) + capturas do PREVIEW em 1440/1024/768/390
> (`/home/claude/caps/novo/…`, fora do repositório) + medições por Playwright
> (`/home/claude/tools/estados_oficios.py`, `sonda.py`).
> Páginas estudadas: `/viagens/roteiros/`, `/viagens/roteiros/5/editar/`, `/viagens/termos/`,
> `/viagens/termos/7/`. Observação: a edição do roteiro é `/viagens/roteiros/<id>/editar/`
> (não `/viagens/roteiros/<id>/`); a do termo é `/viagens/termos/<id>/`.

Este documento descreve **o que está aprovado** e deve ser copiado pelas demais páginas de
Viagens. Onde Roteiros e Termos divergem entre si, a seção 12 diz qual variante adotar.

---

## 1. Escala real (a raiz é 90%)

`static/css/base.css` define `html { font-size: 90% }`; todos os tokens em `rem` encolhem 10%.
Os valores em px **efetivos** medidos no navegador são os que valem para legibilidade:

| Token | Nominal | Efetivo | Uso no padrão |
|---|---|---|---|
| `--texto-display` | 32px | **28,8px** | `h1` da página ≥1024px |
| `--texto-3xl` | 28px | 25,2px | `h1` 768–1023px |
| `--texto-2xl` | 22px | 19,8px | `h1` <768px; número da `placa--grande` |
| `--texto-lg` | 16px | 14,4px | título de seção (`.secao__titulo`), h2 da lista |
| `--texto-md` | 14px | **12,6px** | corpo, título do registro, abas |
| `--texto-sm` | 13px | 11,7px | metadados do registro, frase do cabeçalho, nota de seção |
| `--texto-xs` | 12px | 10,8px | selos, contadores de aba, cabeçalho de mês, meta no celular |
| `0.5625rem` (literal) | 9px | **8,1px** | `.placa__rotulo` ("OFÍCIO", "ROTEIRO", "TERMO") |

Espaçamento (grade de 4px nominal → 3,6px efetivo): `--esp-1` 3,6 · `--esp-2` 7,2 · `--esp-3` 10,8 ·
`--esp-4` 14,4 · `--esp-5` 18 · `--esp-6` 21,6 · `--esp-8` 28,8. Alvos de toque usam
`--alvo-minimo: 24px` em px de propósito (não encolhe).

## 2. Shell (comum a todas as telas)
- Cabeçalho grafite 64px (`--altura-cabecalho`) + filete dourado 3px (`--filete`) + menu
  superior 52px com filete dourado sob o item ativo. `templates/base.html`,
  `templates/parciais/navegacao.html`, `static/css/layout.css`.
- Conteúdo em coluna de 1280px (`--largura-conteudo`), fundo "papel quente" (`--fundo-pagina`).
- Rodapé "Ambiente restrito e monitorado".

## 3. Cabeçalho da página de lista
Arquivo: `templates/arquetipos/lista.html` (blocos `titulo_lista`, `descricao_lista`,
`acoes_lista`, `abas_filtro`, `filtros`, `resultados`, `depois_lista`); CSS `layout.css`
`.pagina-cabecalho*` (l. 496–565).

| Peça | Regra | Medida |
|---|---|---|
| Migalhas | `componentes/migalhas.html`, "Início › Viagens › Roteiros" | texto-sm |
| `h1.pagina-cabecalho__titulo` | um por página, peso 600, `--rastreio-titulo` | 28,8px ≥1024 |
| `p.pagina-cabecalho__descricao` | uma frase do que a lista é; secundário; máx. `--largura-leitura` (42rem) | 12,6px |
| Fecho | **não há régua**: só um traço dourado de 3rem × 2px (`::after`) | `--filete-fino` |
| Ações no cabeçalho | **nenhuma** nas listas de Viagens: "Novo …" mora na barra fixa do rodapé (comentário em `roteiros/lista.html`) | — |

## 4. Abas de filtro com contadores
`components.css` l. 2626–2720 (`.abas`, `.aba`, `.aba__contagem`); parciais
`viagens/roteiros/_abas.html`, bloco `abas_filtro` de `termos/lista.html`.
- Links (`<a class="aba">`) com `aria-current="page"` na ativa, dentro de `nav[aria-label]`.
- Inativa: texto secundário, peso 500. Ativa: texto forte 600 + **filete dourado 3px** que
  cresce da esquerda (`filete-crescer`) + contador vira pílula grafite com texto branco.
- Contador: pílula `--cor-superficie-realce`, texto-xs 600, `tabular-nums`, min 1,5rem.
- Preservam a busca (`q`) ao trocar; na busca ao vivo são trocadas fora de banda (HTMX OOB).
- Altura medida: 40px. Sem rolagem até 768px (Roteiros/Termos têm 5 abas); a 390px rolam de lado.
- Vocabulário aprovado (Roteiros e Termos, igual ao legado): **Todos · Que vão acontecer ·
  Em andamento e realizados · Finalizados · Cancelados**.

## 5. Cartão da lista
```
section.cartao (raio-lg 12px, --sombra-cartao, sem borda)
├─ form.filtros[role=search]   fundo --cor-superficie-sutil, padding 16/20, cantos de cima
│   └─ .campo.filtros__busca   rótulo NA BORDA ("Buscar"), ícone lupa, placeholder com exemplos
│      .filtros__acoes[data-so-sem-js]  "Aplicar" só sem JavaScript (busca ao vivo, 350ms)
└─ .lista-resultados          clip-path no raio; .htmx-request → esmaece 60% + faixa dourada correndo
    └─ #resultados
        ├─ .lista-cabecalho   h2 texto-lg 600 ("Roteiros" | "Resultados para “x”") + total (role=status)
        ├─ ul.registros[aria-labelledby]  → linhas (seção 6)
        └─ componentes/paginacao.html  "Mostrando 1–20 de N" à esquerda, pílulas à direita (atual grafite)
```
Busca: um campo só, largura total do cartão em Roteiros/Termos (nenhum outro filtro visível).

## 6. Linha de registro (`li.registro`)
CSS `static/css/listas.css` l. 86–200 e 520–712; parciais `viagens/roteiros/_registro.html`
(e o laço em `termos/lista.html`).

```
grid: [placa auto] [corpo minmax(0,1fr)] [ações auto]   gap 7,2 / 14,4   padding 14,4 / 18
┌────────┐ Título (link esticado)  [selo de situação/tempo] [selo extra]            ⋮
│ROTEIRO │ 📅 14/12 a 17/12/2026   ⇄ 6 trechos   📄 Ainda não usado   💵 R$ 871,65 · 3 × 100%
│  #60   │
└────────┘
```
| Peça | Classe | Regra |
|---|---|---|
| Placa | `.placa` (`components.css` l. 1170–1227) | papel branco, anel 1px + sombra 1; rótulo caixa alta dourado-700 (8,1px, 0.1em) + número 12,6px 700 `tabular-nums`; `aria-hidden` (o link já diz o número); largura mínima 5,25rem na lista para alinhar títulos; `--cancelada` tacha em vermelho |
| Título | `.registro__titulo` + `a.registro__link` | 12,6px 600; `::after` estica o link sobre a linha toda; hover → dourado-700; `sr-only` "Roteiro #60 · " antes do texto. Sem permissão de edição: `registro__link--estatico` (sem `::after`) |
| Selos | `.selo` + tom (`--info/--sucesso/--aviso/--perigo/--forte`) | pílula texto-xs 600; **forma do marcador** diz o estado: anel vazio = rascunho, ✓ = emitido, × = cancelado, pulso = em andamento; `--sem-ponto` + ícone relógio para contagem ("faltam 69 dias") |
| Metadados | `.registro__meta` > `.registro__meta-item` | texto-sm secundário (6,75:1), gap 3,6/14,4, flex-wrap; ícone 16px em terciário; item ausente `--vazio` (terciário 5,3:1, itálico) — **o item ausente continua no lugar** ("Sem período", "Ainda não usado", "Sem diárias calculadas") |
| Item-ação | `.registro__meta-item--acao` dentro de `.menu--pousar` | "Usado em 1 ofício" em dourado-700: abre por hover/foco uma caixa carregada por HTMX |
| Ações | `.registro__acoes` > `<pc-menu>` | `botao--icone botao--sutil` 36×36 com ⋮ (`ellipsis-vertical`), `aria-label="Ações do roteiro #60"`; esmaecido (opacity .6) até hover/foco da linha |
| Hover | `.registro:hover/:focus-within` | fundo `--cor-superficie-sutil` + **trilho dourado** inset 3px à esquerda |
| Foco | `.registro:has(.registro__link:focus-visible)` | anel inset 2px grafite na linha inteira |
| Recém-salvo | `.registro--destaque` (registro.js + `data-destaque="roteiro:<pk>"`) | acende dourado e assenta em 2,4s |

Densidade medida a 1440: **72px** por linha com uma linha de metadados; 95px com duas.
Celular (<768, `listas.css` l. 693–712): a placa vira um selo em linha ("ROTEIRO #60") ao lado
do ⋮, o corpo ocupa a largura toda, metadados caem para texto-xs (10,8px).

## 7. Menu ⋮ da linha
`<pc-menu class="menu">` (`static/js/componentes/menu.js`, CSS `components.css` l. 1971–2122).
- Botão com `data-menu-botao aria-haspopup="menu"`; painel `role="menu" hidden`; itens
  `role="menuitem"` com ícone à esquerda (`.menu__item`), `.menu__separador`, perigo por último
  (`.menu__item--perigo`, vermelho).
- Ordem canônica (Roteiros): **abrir/editar → ação de criação derivada → ciclo de vida
  (cancelar/reativar) → separador → excluir**.
- Ações que gravam são `<form method=post hidden>` fora do menu, disparados por
  `button[form=…]`; confirmação por `data-confirmar*` (destrutiva com `data-confirmar-perigo`) ou
  janela de motivo (`data-pedir-motivo`, `componentes/dialogo_motivo.html`).
- Teclado verificado: Enter abre e foca o 1º item, ↓ percorre, Esc fecha e devolve o foco ao ⋮.
- Linha com menu aberto sobe de camada (`.registro:has([aria-expanded=true])`).

## 8. Barra de ações fixa no rodapé
`layout.css` l. 590–700 (`.barra-acoes`), usada nas listas (bloco `depois_lista`) e nas folhas.
- `position: sticky; bottom: 10,8px`, raio 16px, `--sombra-flutuante`, padding 10,8/10,8/10,8/18.
- **Lista**: status à esquerda (`.barra-acoes__status[role=status]`, "71 roteiros") e, à direita,
  o primário grafite "+ Novo roteiro" (e, se houver, secundário contornado antes dele).
- **Folha**: "Voltar" (`botao--texto`) à esquerda; à direita o primário ("Salvar roteiro"
  grafite com `aria-keyshortcuts="Control+S"`, ou "Finalizar" dourado `botao--marca` nos
  documentos — `componentes/rodape_documento.html`) e o menu de mais ações abrindo **para
  cima** (`menu__painel--acima`).
- Celular: uma linha só, status escondido (exceto "não salvo"/erro, que flutua acima),
  botões `flex: 1`. `html:has(.barra-acoes)` reserva `scroll-padding-bottom` (WCAG 2.4.11).

## 9. Estados vazios
`templates/componentes/vazio.html` (+ CSS `.vazio`, `components.css` l. 1658): ícone em
círculo dourado-claro, `h2` título, texto de orientação, ação.
Três casos distintos, sempre: **sem resultado** (ícone lupa + "Limpar filtros"),
**primeiro uso** (ícone do domínio + ação primária "Novo …"), **sem permissão/sem dados da
unidade** (ícone inbox, sem ação). Termos acrescenta o vazio contextual "Este ofício ainda não
tem termo" com ação própria (`acao_template`).

## 10. Folha de edição (Roteiro e Termo)
Arquivos: `viagens/roteiros/editar.html`, `viagens/termos/editar.html`;
CSS `documento.css` (l. 1–300), `formulario.css` (`.frase-oficio` l. 716–745), `itinerario.css`;
JS `guia.js`, `itinerario.js`, `autosave.js`, `protecao.js`.

| Região | Padrão |
|---|---|
| Cabeçalho | `placa--grande` (número 19,8px) à esquerda + `h1.sr-only` (a placa já diz o nome) + **frase** (`p.frase-oficio`): itens com ícone, texto-sm secundário, vazio em itálico terciário, valor em dourado-700 600 (`frase-oficio__valor`); ações à direita (secundário contornado + ⋮ contornado 40px). |
| Folha | `.documento` (uma folha, raio 16, sombra-cartao, padding 21,6/28,8 — Roteiro) ou `.documento--cartoes` (um cartão por seção, gap 18 — Termo, Ofício). Linha-guia dourada na margem esquerda até a etapa da vez (`guia.js`). |
| Seção numerada | `section.secao[aria-labelledby]` > `.secao__cabecalho` com `h2.secao__titulo` (14,4px 600) e `.secao__numero` (pílula 1,75rem, fundo dourado-50, borda dourado-200, texto dourado-700 700); `.secao__estado` à direita com selos de pendência ("Falta destino" anel vazio âmbar); `.secao__nota` em texto-sm logo abaixo. `--ok` quando concluída. |
| Bloco | `.secao__bloco` separado por fio sutil, cabeçalho `.secao__bloco-titulo` em caixa alta 10,8px 700 com ícone dourado ("EQUIPE", "TRANSPORTE", "HISTÓRICO"). |
| Campos | rótulo na borda (`.campo`, `.campo__rotulo`), largura pelo conteúdo (`.campos` + `campo--xs/sm/md/lg`, `campos--iguais`), seletores próprios (`pc-data`, `pc-hora`, `pc-select`, `pc-combobox`). |
| Itinerário | `<pc-itinerario>`: trilho vertical sede → destinos → volta, UF + cidade, "Adicionar destino" tracejado, mapa "Rota" ao lado (≥1024). |
| Alertas | `alerta--aviso` com checklist de pendências que são links para o bloco certo. |
| Rodapé | barra de ações (seção 8). |

## 11. Tokens usados pelo padrão (resumo)
Cor: `--cor-superficie`, `--cor-superficie-sutil`, `--cor-superficie-realce`, `--cor-borda-sutil`,
`--cor-texto`, `--cor-texto-secundario`, `--cor-texto-terciario`, `--cor-marca`
(trilho/filete), `--cor-marca-texto` (rótulo da placa, link em hover, valor), `--cor-marca-fundo/borda`
(número de seção), `--grafite-900` (contador ativo, paginação atual, primário), tons de selo
(`--cor-info/sucesso/aviso/perigo` + `-fundo` + `-borda`).
Forma: `--raio-lg` (cartão), `--raio-xl` (folha, barra), `--raio-sm` (placa), `--raio-pilula`
(selos, contadores, número de seção). Sombra: `--sombra-cartao`, `--sombra-flutuante`.
Movimento: `--duracao-rapida` (hover), `--duracao-media` (abas), `filete-crescer`, `brotar`.

## 12. Divergências internas Roteiros × Termos (a resolver antes de replicar)
| Tema | Roteiros | Termos | Adotar |
|---|---|---|---|
| Selo de tempo | "faltam N dias" (info/aviso ≤10d) · "em andamento" (pulso) · nada no passado | "Previsto" · "Em andamento" · "Realizado" (sem ponto) | **um** tag compartilhado (`selo_tempo`), ver `oficios-lista.md` P2 |
| Cancelado | placa tachada + selo com × (`selo--situacao-cancelado`) | selo sem forma (`selo--sem-ponto`), placa normal, `registro--inativo` | Roteiros |
| Título | "Sede → destinos"; período nos metadados | "Destinos · período"; período no título | decidir uma regra (proposta em `oficios-lista.md` P3) |
| Registro | parcial `_registro.html` | laço inline em `lista.html` | parcial |
| Folha | `.documento` (folha única) | `.documento--cartoes` | `--cartoes` (é o do ofício) |
| Primário do rodapé | "Salvar roteiro" grafite + ⋮ só ícone | "Finalizar" dourado + "⋮ Ações" com rótulo | regra: dourado só p/ concluir; menu sempre "Ações" com rótulo no rodapé |
| Barra da lista | "71 roteiros" | "7 termos" + "no filtro de agora" (mas usa a variável `termo`, que não existe — com busca o sufixo nunca aparece) | corrigir e padronizar texto ("7 de 7 termos") |

Defeito de CSS que já afeta Termos: em `listas.css` l. 596 o seletor
`.registro--inativo .registro__link,` ficou colado (sem regra própria) ao bloco `.registro__notas`;
o título de um registro inativo vira `display:grid` com `margin-top` 7,2px e **não recua** de cor
(medido no termo cancelado: título 4,5px abaixo do selo). Afeta 22 templates (ver `componentes.md`).
