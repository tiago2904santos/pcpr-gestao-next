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
| `--cor-foco`, `--anel-foco` | Foco (azul — contrasta com grafite e com dourado) |
| `--cor-{sucesso,aviso,perigo,info}(-fundo/-borda)` | Selos, alertas, toasts |

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
| `--azul-600` | `--neutro-0` | 6.04:1 ✅ | 3.0:1 | Anel de foco (2.4.11/1.4.11) |
| `--dourado-600` | `--neutro-0` | 3.75:1 ✅ | 3.0:1 | Indicador dourado de item ativo (não textual) |
| `--dourado-600` | `--dourado-50` | 3.51:1 ✅ | 3.0:1 | Indicador ativo sobre fundo de marca |
| `--neutro-400` | `--neutro-50` | 3.15:1 ✅ | 3.0:1 | Borda de campo sobre fundo |
| `--dourado-500` | `--grafite-900` | 5.63:1 ✅ | 3.0:1 | Filete dourado sob o cabeçalho |
