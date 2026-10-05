# Busca global (paleta de comandos)

A referência não tem busca global; aqui a paleta (Ctrl+K ou "/") já existia só com
ofícios. Ela passa a juntar as fontes que cada módulo registra em
`gestao/plataforma/busca.py` (mesmo desenho da agenda e do menu: a plataforma não conhece
os contextos).

| Fonte | Grupo na paleta | Procura em | Quem vê |
|---|---|---|---|
| `oficios` (Viagens) | Ofícios | número (131/2026), protocolo, motivo, destino, servidor | quem lista ofícios (escopo da unidade) |
| `viagens` (Viagens) | Viagens | título, motivo | quem vê viagens (escopo da unidade) |
| `imprensa` | Atendimentos à imprensa | jornalista, veículo, pedido, contato | papel ASCOM_IMPRENSA |
| `pautas` (Publicações) | Pautas | título, fonte, unidade | papel ASCOM_PUBLICACOES |
| `palestras` | Palestras e eventos | solicitante, local, município, palestrante | papel ASCOM_PALESTRAS |

Regras: no mínimo 2 caracteres; até 6 resultados por fonte; acentos não contam (unaccent);
a fonte fora do acesso nem entra. Os atalhos de navegação continuam vindo do menu (no
navegador).

Testes: `gestao/painel/tests/test_busca_global.py`, `gestao/viagens/tests/test_views.py`
(`test_busca_global_json`).
