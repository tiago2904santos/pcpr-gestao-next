# Cores

Fonte única: [`static/css/tokens.css`](../../static/css/tokens.css). Contrastes abaixo são
**calculados** a partir desse arquivo por `python3 scripts/contraste.py` e verificados em
`tests/test_design_tokens.py` (o teste falha se algum par cair abaixo do mínimo).

## Paleta institucional
| Família | Tokens | Papel |
|---|---|---|
| Grafite | `--grafite-950 … 600` | Cabeçalho, botão primário, selo "forte", texto sobre dourado |
| Dourado | `--dourado-50 … 800` | Assinatura: filete, item ativo, botão de marca, valores de atenção |
| Neutros quentes | `--neutro-0 … 900` | Fundos, bordas, textos |
| Semânticas | `--verde`, `--ambar`, `--vermelho`, `--azul`, `--violeta` | Status e mensagens |

## Tokens semânticos (use estes nos componentes)
| Token | Uso |
|---|---|
| `--cor-fundo` | Fundo da página |
| `--cor-superficie`, `--cor-superficie-sutil`, `--cor-superficie-realce` | Cartões, cabeçalhos de tabela, hover |
| `--cor-borda`, `--cor-borda-forte`, `--cor-borda-campo` | Divisores, cartões, campos (3:1) |
| `--cor-texto`, `--cor-texto-secundario`, `--cor-texto-terciario` | Hierarquia de texto (todos ≥ 4,5:1) |
| `--cor-marca`, `--cor-marca-texto`, `--cor-marca-fundo`, `--cor-marca-borda` | Indicador ativo, texto dourado legível, realces |
| `--cor-primaria(-hover/-texto)` | Botão primário grafite |
| `--foco-cor`, `--foco-contraste`, `--foco-cor-inverso`, `--foco-contraste-inverso`, `--foco-espessura`, `--foco-offset` | Foco próprio: anel grafite com halo claro; dourado sobre o grafite (`--cor-foco` é alias) |
| `--cor-{sucesso,aviso,perigo,info}(-fundo/-borda)` | Selos, alertas, toasts |

## Tokens translúcidos (profundidade sem cor nova)
| Token | Uso |
|---|---|
| `--tinta-04 … 28` | sombras e anéis de 1px (grafite com alfa) — substituem bordas cinzas |
| `--luz-10 … 28` | superfícies sobre o grafite (busca global, botões do cabeçalho) |
| `--brilho-dourado-08 … 45` | brilho do fundo da página, anéis do login, halo do passo atual, sombra do botão de marca |
| `--sombra-cartao`, `--sombra-cartao-hover`, `--sombra-flutuante`, `--sombra-marca` | cartões, barra de ações flutuante, botão dourado |

Regra: alfa só sobre a mesma família (tinta = grafite, luz = branco, brilho = dourado).
Nunca texto sobre token translúcido sem medir o contraste do resultado composto.

## Tema
**Somente claro — sem modo escuro** (decisão do dono do produto). Não criar variantes
`prefers-color-scheme: dark` nem alternador de tema; os testes reprovam.

## Regras
1. **Dourado como texto** só `--cor-marca-texto` (`--dourado-700`).
2. **Dourado como indicador** (barra/sublinhado ativo) `--cor-marca` (`--dourado-600`, 3,75:1).
3. **Status nunca só por cor**: selo sempre tem texto; ícone quando o espaço permite.
4. **Foco é azul**, não dourado: o dourado já significa "ativo/selecionado".
5. Fundo da página levemente quente (`--neutro-50`) e cartões brancos: separação sem sombras pesadas.

## Mapa de status (domínio Viagens)
| Situação | Tom | Por quê |
|---|---|---|
| Rascunho | neutro | Ainda não tem efeito |
| Pronto para emitir | marca | Próxima ação institucional |
| Emitido | sucesso | Documento oficial gerado |
| Justificativa pendente | aviso | Bloqueia a emissão |
| Cancelado | perigo | Encerrado sem efeito |
| Motorista | forte (grafite) | Papel, não status |

## Contraste medido
| Primeiro plano | Fundo | Contraste | Mínimo | Uso |
|---|---|---:|---:|---|
| `--neutro-900` | `--neutro-0` | 16.67:1 ✅ | 4.5:1 | Texto principal sobre superfície |
| `--neutro-900` | `--neutro-50` | 15.29:1 ✅ | 4.5:1 | Texto principal sobre fundo da página |
| `--neutro-600` | `--neutro-0` | 6.75:1 ✅ | 4.5:1 | Texto secundário sobre superfície |
| `--neutro-600` | `--neutro-50` | 6.19:1 ✅ | 4.5:1 | Texto secundário sobre fundo |
| `--neutro-500` | `--neutro-0` | 5.30:1 ✅ | 4.5:1 | Texto terciário (placeholder) sobre superfície |
| `--neutro-500` | `--neutro-50` | 4.86:1 ✅ | 4.5:1 | Texto terciário sobre fundo |
| `--neutro-600` | `--neutro-100` | 5.72:1 ✅ | 4.5:1 | Texto secundário sobre fundo do login/realce |
| `--neutro-300` | `--grafite-800` | 7.58:1 ✅ | 4.5:1 | Texto sutil do cabeçalho (busca, subtítulo) |
| `--neutro-0` | `--grafite-900` | 14.92:1 ✅ | 4.5:1 | Texto do cabeçalho / botão primário |
| `--grafite-950` | `--dourado-500` | 6.43:1 ✅ | 4.5:1 | Texto do botão de marca |
| `--dourado-700` | `--neutro-0` | 5.84:1 ✅ | 4.5:1 | Texto dourado sobre branco |
| `--dourado-700` | `--dourado-50` | 5.46:1 ✅ | 4.5:1 | Texto dourado sobre fundo de marca |
| `--dourado-300` | `--grafite-900` | 8.55:1 ✅ | 4.5:1 | Papel do usuário no cabeçalho |
| `--verde-700` | `--verde-50` | 6.92:1 ✅ | 4.5:1 | Selo/alerta de sucesso |
| `--ambar-700` | `--ambar-50` | 6.61:1 ✅ | 4.5:1 | Selo/alerta de aviso |
| `--vermelho-700` | `--vermelho-50` | 6.59:1 ✅ | 4.5:1 | Selo/alerta de perigo |
| `--azul-700` | `--azul-50` | 6.87:1 ✅ | 4.5:1 | Selo/alerta de informação |
| `--azul-700` | `--neutro-0` | 7.61:1 ✅ | 4.5:1 | Links |
| `--neutro-0` | `--vermelho-600` | 6.57:1 ✅ | 4.5:1 | Botão de perigo |
| `--neutro-400` | `--neutro-0` | 3.43:1 ✅ | 3.0:1 | Borda de campo (componente, 1.4.11) |
| `--grafite-900` | `--neutro-0` | 14.92:1 ✅ | 3.0:1 | Anel de foco sobre superfícies claras (2.4.11/1.4.11) |
| `--grafite-900` | `--neutro-50` | 13.68:1 ✅ | 3.0:1 | Anel de foco sobre o fundo da página |
| `--dourado-300` | `--grafite-900` | 8.55:1 ✅ | 3.0:1 | Anel de foco sobre o cabeçalho |
| `--grafite-800` | `--neutro-0` | 12.79:1 ✅ | 3.0:1 | Borda do campo em foco |
| `--dourado-600` | `--neutro-0` | 3.75:1 ✅ | 3.0:1 | Indicador dourado de item ativo (não textual) |
| `--dourado-600` | `--dourado-50` | 3.51:1 ✅ | 3.0:1 | Indicador ativo sobre fundo de marca |
| `--neutro-400` | `--neutro-50` | 3.15:1 ✅ | 3.0:1 | Borda de campo sobre fundo |
| `--dourado-500` | `--grafite-900` | 5.63:1 ✅ | 3.0:1 | Filete dourado sob o cabeçalho |
