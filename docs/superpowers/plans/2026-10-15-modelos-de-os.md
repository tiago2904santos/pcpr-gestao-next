# Modelos de Ordem de Serviço — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tipos de OS viram modelos cadastráveis (funções + texto por etapa), com o documento
no formato `DETERMINO` + itens I, II, III… distribuídos nos dias da viagem e do evento.

**Architecture:** Domínio puro (`dominio/modelo_os.py`) distribui etapas nos dias e monta os
itens a partir de um `Modelo` (dataclass). `ModeloOS`/`FuncaoOS` (Django) guardam os modelos; a
OS aponta para um modelo (nulo = padrão, que não muda). `ordens.py` converte modelo + OS em
`DadosOS` e escolhe `itens_da_os` ou `textos_da_os`. Cadastro do gestor em
`/viagens/ordens/modelos/`, na receita de Textos prontos.

**Tech Stack:** Django 5, PostgreSQL, HTMX/web components existentes (`pc-multiescolha`,
`pc-data`), WeasyPrint/DOCX via o HTML do documento, pytest + Playwright.

**Spec:** `docs/superpowers/specs/2026-10-15-modelos-de-os-design.md`

## Global Constraints

- `gestao/viagens/dominio/` é Python puro (import-linter): nada de Django lá.
- Escritas de negócio em módulos de serviço (`ordens.py`, `modelos_os.py`) com `transaction.atomic`;
  autorização só em `policies.py`.
- Sem estilos/scripts inline; valores visuais só via tokens; sem código do sistema de referência.
- Testes rápidos: `POSTGRES_PASSWORD=local uv run pytest -q -p no:cacheprovider <alvo>`; lint:
  `uv run ruff check gestao tests scripts`; tipos: `uv run mypy gestao`; fronteiras:
  `uv run lint-imports`.
- Commits pequenos, com o rodapé de atribuição da sessão.

## Review Focus

1. Evento com um dia só e viagem de um dia só (saída = chegada = evento): só o item `evento`,
   sem "deslocamento" nem "retorno" duplicados → Task 1.
2. Evento começa antes da saída ou termina depois da chegada → erro de validação com mensagem
   ("O período do evento precisa caber no período da OS"), nunca um documento errado → Task 4.
3. Modelo desativado em OS existente: o documento continua saindo e a opção continua selecionada
   no formulário (queryset inclui o modelo atual) → Task 5.
4. Texto do modelo com marcador fora do permitido (`{servidores}` numa etapa, `{data}` numa
   função, `{hora}` sem OS com hora): erro ao salvar o modelo; `{hora}` sem hora na OS sai vazio
   e vira pendência, nunca "às None" → Tasks 2 e 6.
5. Excluir modelo com OS ligada: recusado com mensagem; o modelo do sistema nunca se exclui
   → Task 6.

---

### Task 1: Domínio — distribuir etapas nos dias

**Files:**
- Create: `gestao/viagens/dominio/modelo_os.py`
- Test: `gestao/viagens/tests/test_dominio_modelo_os.py`

**Interfaces:**
- Produces:
  - `ETAPAS = ("ida", "ida_e_antes", "antes", "evento", "depois", "depois_e_volta", "volta")`
  - `@dataclass(frozen=True) class Etapa: nome: str; inicio: date; fim: date`
  - `distribuir_etapas(saida: date, chegada: date, evento_inicio: date | None = None, evento_fim: date | None = None, *, combinados: frozenset[str] = frozenset()) -> list[Etapa]`
    — `combinados` diz quais textos combinados o modelo tem (`"ida_e_antes"`, `"depois_e_volta"`).

- [ ] **Step 1: Escrever os testes**

```python
from datetime import date
import pytest
from gestao.viagens.dominio import modelo_os as m

d = lambda dia: date(2026, 5, dia)
AMBOS = frozenset({"ida_e_antes", "depois_e_volta"})

def nomes(etapas): return [(e.nome, e.inicio.day, e.fim.day) for e in etapas]

class TestDistribuirEtapas:
    def test_viagem_3_a_8_com_evento_5_a_6(self):
        assert nomes(m.distribuir_etapas(d(3), d(8), d(5), d(6), combinados=AMBOS)) == [
            ("ida", 3, 3), ("antes", 4, 4), ("evento", 5, 6), ("depois", 7, 7), ("volta", 8, 8)]

    def test_vespera_e_dia_seguinte_usam_os_combinados(self):
        assert nomes(m.distribuir_etapas(d(4), d(7), d(5), d(6), combinados=AMBOS)) == [
            ("ida_e_antes", 4, 4), ("evento", 5, 6), ("depois_e_volta", 7, 7)]

    def test_sem_texto_combinado_saem_ida_e_volta_simples(self):
        assert nomes(m.distribuir_etapas(d(4), d(7), d(5), d(6))) == [
            ("ida", 4, 4), ("evento", 5, 6), ("volta", 7, 7)]

    def test_operacao_policial_17_18_19(self):
        assert nomes(m.distribuir_etapas(d(17), d(19), d(18), d(18))) == [
            ("ida", 17, 17), ("evento", 18, 18), ("volta", 19, 19)]

    def test_tudo_no_mesmo_dia_so_evento(self):
        assert nomes(m.distribuir_etapas(d(18), d(18), d(18), d(18), combinados=AMBOS)) == [
            ("evento", 18, 18)]

    def test_saida_no_dia_do_evento_nao_tem_ida(self):
        assert nomes(m.distribuir_etapas(d(5), d(7), d(5), d(6))) == [
            ("evento", 5, 6), ("volta", 7, 7)]

    def test_sem_evento_a_viagem_inteira_e_evento(self):
        assert nomes(m.distribuir_etapas(d(3), d(8))) == [("evento", 3, 8)]

    def test_evento_com_fim_vazio_e_de_um_dia(self):
        assert nomes(m.distribuir_etapas(d(3), d(5), d(4))) == [
            ("ida", 3, 3), ("evento", 4, 4), ("volta", 5, 5)]

    def test_evento_fora_da_viagem_e_erro(self):
        with pytest.raises(ValueError):
            m.distribuir_etapas(d(4), d(7), d(2), d(3))
```

- [ ] **Step 2: Rodar e ver falhar** — `pytest gestao/viagens/tests/test_dominio_modelo_os.py -q` → ImportError.

- [ ] **Step 3: Implementar `distribuir_etapas`** em `dominio/modelo_os.py` (docstring: a tabela
  da spec). Regras: evento ausente → `(saida, chegada)`; `evento_fim` ausente → `evento_inicio`;
  evento fora de `[saida, chegada]` → `ValueError`. `antes` = `saida+1 … evento_inicio-1` se não
  vazio; `ida` existe se `saida < evento_inicio`; ida sem `antes` e `evento_inicio == saida + 1`
  com `"ida_e_antes" in combinados` → `ida_e_antes`. Simétrico para `depois`/`volta`/
  `depois_e_volta`. **Atenção:** `ida` sem `antes` com `evento_inicio == saida + 1` e sem o
  combinado vira `ida` simples (não `antes`).

- [ ] **Step 4: Rodar e ver passar.** Também `uv run ruff check gestao/viagens/dominio` e
  `uv run lint-imports`.

- [ ] **Step 5: Commit** — `git add gestao/viagens/dominio/modelo_os.py gestao/viagens/tests/test_dominio_modelo_os.py && git commit -m "Domínio: distribui as etapas da OS nos dias da viagem e do evento"`.

---

### Task 2: Domínio — marcadores, itens e pendências

**Files:**
- Modify: `gestao/viagens/dominio/modelo_os.py`
- Modify: `gestao/viagens/dominio/ordem_servico.py` (`DadosOS` ganha `evento_inicio`, `evento_fim`, `hora: time | None`, `sede: str`)
- Test: `gestao/viagens/tests/test_dominio_modelo_os.py`

**Interfaces:**
- Consumes: `DadosOS`, `Pessoa`, `equipe_no_texto`, `municipios_no_texto`, `motivo_no_texto`, `periodo_por_extenso` de `dominio/ordem_servico.py`; `lista_com_e`, `MESES` de `dominio/escrita.py`.
- Produces:
  - `MARCADORES_ETAPA = frozenset({"equipe", "destino", "data", "motivo", "hora", "sede"})`
  - `MARCADORES_FUNCAO = frozenset({"servidores", "destino", "motivo", "sede"})`
  - `@dataclass(frozen=True) class Funcao: codigo: str; nome: str; texto: str; icone: str = ""`
  - `@dataclass(frozen=True) class Modelo: nome: str; referencia: str; textos: Mapping[str, str]; funcoes: tuple[Funcao, ...] = (); justificativas: tuple[str, ...] = (); finalidade: str = ""` com propriedades `usa_hora -> bool` e `combinados -> frozenset[str]` (etapas combinadas com texto não vazio).
  - `@dataclass(frozen=True) class TextosModelo: referencia: str; itens: list[str]; justificativas: list[str]; finalidade: str`
  - `marcadores(texto: str) -> set[str]` (os nomes entre chaves), `marcadores_invalidos(texto: str, permitidos: frozenset[str]) -> set[str]`
  - `data_da_etapa(etapa: Etapa) -> str`: "no dia 4 de maio de 2026" / "nos dias 5 e 6 de maio de 2026" / "nos dias 5 a 7 de maio de 2026" (meses/anos diferentes: reaproveita `periodo_por_extenso`).
  - `hora_no_texto(hora: time | None) -> str`: `"às 05h00min"` ou `""`.
  - `romano(n: int) -> str` (1..50).
  - `itens_da_os(dados: DadosOS, modelo: Modelo) -> TextosModelo`
  - `faltam_para_o_modelo(dados: DadosOS, modelo: Modelo) -> list[str]` com os textos exatos `"função da equipe"`, `"horário do briefing"`, `"período"`.

- [ ] **Step 1: Testes**

```python
from datetime import time
from gestao.viagens.dominio import ordem_servico as os_

A = os_.Pessoa(1, "Ana Lima", "Agente de Polícia Judiciária")
B = os_.Pessoa(2, "Bruno Rocha", "Agente de Polícia Judiciária")
CAMINHAO = m.Modelo(
    nome="Caminhão", referencia="Deslocamento - Caminhão de apoio",
    textos={"ida": "O deslocamento {equipe} para {destino} {data}, para {motivo}.",
            "ida_e_antes": "", "antes": "Que a equipe faça a montagem {data}.",
            "evento": "Que a equipe permaneça em {destino} {data}{hora}.",
            "depois": "Que a equipe desmonte {data}.", "depois_e_volta": "",
            "volta": "Que a equipe retorne a {sede} {data}."},
    funcoes=(m.Funcao("conducao", "Condução", "Que {servidores} conduza o caminhão."),
             m.Funcao("apoio", "Apoio", "Que {servidores} preste apoio.")),
    justificativas=("Just. 1",), finalidade="Fim.")

def dados(**extra):
    base = dict(destinos=["Londrina/PR"], inicio=d(3), fim=d(8), evento_inicio=d(5),
                evento_fim=d(6), motivo="A Feira", equipe=[A, B],
                funcoes={1: "conducao", 2: "apoio"}, sede="Curitiba/PR")
    return os_.DadosOS(**{**base, **extra})

class TestMarcadores:
    def test_lista_os_marcadores(self):
        assert m.marcadores("x {equipe} y {data}") == {"equipe", "data"}
    def test_invalidos(self):
        assert m.marcadores_invalidos("{servidores} {foo}", m.MARCADORES_ETAPA) == {"servidores", "foo"}
    @pytest.mark.parametrize("ini,fim,texto", [
        (3, 3, "no dia 3 de maio de 2026"), (5, 6, "nos dias 5 e 6 de maio de 2026"),
        (5, 7, "nos dias 5 a 7 de maio de 2026")])
    def test_data_da_etapa(self, ini, fim, texto):
        assert m.data_da_etapa(m.Etapa("evento", d(ini), d(fim))) == texto
    def test_hora(self):
        assert m.hora_no_texto(time(5, 0)) == "às 05h00min" and m.hora_no_texto(None) == ""
    def test_romano(self):
        assert [m.romano(n) for n in (1, 4, 9, 14)] == ["I", "IV", "IX", "XIV"]

class TestItens:
    def test_funcoes_primeiro_depois_os_dias(self):
        t = m.itens_da_os(dados(), CAMINHAO)
        assert t.referencia == "Deslocamento - Caminhão de apoio"
        assert t.itens == [
            "Que Ana Lima conduza o caminhão.", "Que Bruno Rocha preste apoio.",
            "O deslocamento dos agentes de polícia judiciária Ana Lima e Bruno Rocha para o município de Londrina/PR no dia 3 de maio de 2026, para a Feira.",
            "Que a equipe faça a montagem no dia 4 de maio de 2026.",
            "Que a equipe permaneça em o município de Londrina/PR nos dias 5 e 6 de maio de 2026.",
            "Que a equipe desmonte no dia 7 de maio de 2026.",
            "Que a equipe retorne a Curitiba/PR no dia 8 de maio de 2026."]
        assert t.justificativas == ["Just. 1"] and t.finalidade == "Fim."
    def test_funcao_sem_ninguem_nao_sai_e_varios_nomes_juntam(self):
        t = m.itens_da_os(dados(funcoes={1: "apoio", 2: "apoio"}), CAMINHAO)
        assert t.itens[0] == "Que Ana Lima e Bruno Rocha preste apoio." and "conduza" not in " ".join(t.itens)
    def test_hora_entra_quando_existe(self):
        assert " às 05h00min." in m.itens_da_os(dados(hora=time(5, 0)), CAMINHAO).itens[4]
    def test_texto_combinado_quando_o_modelo_tem(self):
        modelo = m.Modelo(**{**CAMINHAO.__dict__, "textos": {**CAMINHAO.textos, "ida_e_antes": "Ida e montagem {data}."}})
        assert "Ida e montagem no dia 4 de maio de 2026." in m.itens_da_os(dados(inicio=d(4)), modelo).itens

class TestPendencias:
    def test_sem_funcao_sem_hora_sem_periodo(self):
        modelo = m.Modelo(**{**CAMINHAO.__dict__, "textos": {**CAMINHAO.textos, "evento": "{hora}"}})
        assert m.faltam_para_o_modelo(dados(funcoes={}, hora=None, inicio=None, fim=None), modelo) == ["período", "função da equipe", "horário do briefing"]
    def test_completo(self):
        assert m.faltam_para_o_modelo(dados(hora=time(5)), CAMINHAO) == []
```

Nota: `{destino}` sai "o município de Londrina/PR" (como `municipios_no_texto`); o texto de
exemplo "permaneça em o município" é só do teste. Os modelos do sistema escrevem "em {destino}"
com a preposição dentro do texto: "permaneça n{destino}"? Não — usar "permaneça em {destino}"
onde `{destino}` = "Londrina/PR" **sem** "o município de". Decisão: `{destino}` = nomes com "e"
("Londrina/PR" / "Londrina/PR e Maringá/PR"); `{municipio}` = "o município de Londrina/PR" / "os
municípios de A e B". Acrescente `"municipio"` a ambos os conjuntos de marcadores e corrija o
teste acima para `"permaneça em Londrina/PR"` e o modelo de teste para `"para {municipio}"`.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar.** `DadosOS` ganha os campos (valores padrão `None`/`""`).
  `itens_da_os`: monta o dicionário de valores (`equipe`, `destino`, `municipio`, `motivo`,
  `hora`, `sede`), funções primeiro (só as com alguém; `{servidores}` = `lista_com_e` dos nomes
  na ordem da equipe), depois `distribuir_etapas(dados.inicio, dados.fim, dados.evento_inicio,
  dados.evento_fim, combinados=modelo.combinados)` e `texto.format_map(valores | {"data": …})`
  para cada etapa com texto não vazio. Espaços duplos de marcadores vazios: `" ".join(s.split())`
  e `" ."` → `"."`.

- [ ] **Step 4: Rodar e ver passar; ruff; lint-imports.**

- [ ] **Step 5: Commit** — "Domínio: itens da OS por função e por etapa com marcadores".

---

### Task 3: Modelos, migração e ícones

**Files:**
- Modify: `gestao/viagens/models.py` (depois de `OrdemServico`… antes de `OrdemServicoDestino`)
- Create: `gestao/viagens/migrations/0053_modelos_de_os.py`
- Create: `gestao/viagens/modelos_do_sistema.py` (os 4 modelos semeados, usados pela migração e por `demonstracao`)
- Modify: `scripts/vendor_assets.py` (ICONES += `camera`, `mic`, `briefcase`, `hard-hat`, `clipboard-check`, `headset`, `video`, `star`) e `static/icons/sprite.svg` (regenerar com `python3 scripts/vendor_assets.py` — `node_modules` já instalado)
- Modify: `gestao/identidade/papeis.py` (OPERADOR: `viagens.view_modeloos`; GESTOR: view/add/change/delete)
- Test: `gestao/viagens/tests/test_modelos_os.py` (migração: `django_test_migrations` não existe — testar pelo estado final: os 4 modelos existem com `chave`, funções e textos; `OrdemServico.modelo` aponta certo num cenário criado via `ordens.salvar`)

**Interfaces:**
- Produces:
  - `class ModeloOS(models.Model)`: `chave = SlugField(40, unique=True, null=True, blank=True)` (só os do sistema: `"operacao_policial"`, `"caminhao"`, `"microonibus"`, `"cerimonial"`), `nome` (60, unique), `referencia` (120), `ida`, `ida_e_antes`, `antes`, `evento`, `depois`, `depois_e_volta`, `volta` (TextField blank), `justificativas` (TextField blank), `finalidade` (TextField blank), `ativo` (True), `ordem` (PositiveSmallIntegerField default 100), `padrao_sistema` (False), `criado_em`, `atualizado_em`. `Meta.ordering = ["ordem", "nome"]`; `verbose_name = "modelo de OS"`. Métodos: `textos() -> dict[str, str]`, `usa_hora -> bool` (property), `para_dominio() -> dominio_modelo.Modelo` (com as funções ordenadas).
  - `class FuncaoOS(models.Model)`: `modelo` FK cascade related_name `funcoes`, `codigo` SlugField(30), `nome` (40), `icone` (40, blank), `texto` TextField, `ordem` (default 0). `Meta.ordering = ["ordem", "id"]`, unique (modelo, codigo).
  - `OrdemServico`: remove `TIPOS` e `tipo`; adiciona `modelo = FK(ModeloOS, null, blank, PROTECT, related_name="ordens")`, `data_evento_inicio`, `data_evento_fim` (DateField null/blank), `hora = TimeField(null, blank, verbose_name="horário do briefing")`; constraint `os_evento_ordenado` (fim >= início quando ambos).
  - `modelos_do_sistema.MODELOS: list[dict]` — cada um com `chave`, `nome`, `referencia`, `ordem`, textos das 7 etapas, `justificativas`, `finalidade`, `funcoes: list[dict(codigo, nome, icone, texto)]`. Função `semear(ModeloOS, FuncaoOS) -> dict[str, int]` (chave → pk) que cria os que faltam (idempotente; recebe os modelos para servir à migração via `apps.get_model`).
  - `ICONES_DE_FUNCAO: list[tuple[str, str]]` em `modelos_do_sistema.py`: `[("car", "Carro"), ("truck", "Caminhão"), ("bus", "Micro-ônibus"), ("wrench", "Ferramenta"), ("hand-helping", "Apoio"), ("clipboard-list", "Prancheta"), ("package-check", "Caixa conferida"), ("camera", "Câmera"), ("video", "Filmadora"), ("mic", "Microfone"), ("headset", "Fone"), ("briefcase", "Maleta"), ("hard-hat", "Capacete"), ("clipboard-check", "Conferência"), ("shield-check", "Escudo"), ("star", "Estrela"), ("users", "Equipe"), ("map-pin", "Local"), ("monitor", "Monitor"), ("megaphone", "Megafone")]`.

Textos dos modelos do sistema (copiar da spec "Modelos do sistema" para caminhão; os demais):

- **Micro-ônibus** (`microonibus`, ref. "Deslocamento - Micro-ônibus", funções condução `bus`/técnico `wrench`/apoio `hand-helping` com os textos atuais de `textos_da_os` no formato "Que {servidores} conduza o micro-ônibus oficial…"): ida "O deslocamento {equipe} para {municipio} {data}, para apoio logístico com micro-ônibus em {motivo}."; antes "Que a equipe organize {data} os materiais e equipamentos no local da atividade."; evento "Que a equipe permaneça em {destino} {data} para o transporte e o apoio logístico de {motivo}."; depois "Que a equipe recolha {data} os materiais utilizados."; volta "Que a equipe efetue o retorno à sede de lotação em {sede} {data}."; combinados vazios; justificativa e finalidade atuais.
- **Cerimonial** (`cerimonial`, ref. "Deslocamento - Equipe de Cerimonial", funções coordenação `clipboard-list`/apoio `hand-helping`/preparação `package-check` com os textos atuais): ida "O deslocamento {equipe} para {municipio} {data}, para atuação na organização e realização de {motivo}."; antes "Que a equipe verifique {data} a estrutura do local, sonorização, palco, púlpito, bandeiras, acessos e demais aspectos logísticos da solenidade."; evento "Que a equipe atue em {destino} {data} na organização e realização de {motivo}."; depois "Que a equipe desmobilize {data} a estrutura e os materiais da solenidade."; volta como acima; ida_e_antes "O deslocamento {equipe} para {municipio} {data}, com a verificação da estrutura do local no mesmo dia, para atuação na organização e realização de {motivo}."; depois_e_volta "Que a equipe desmobilize {data} a estrutura da solenidade e efetue o retorno à sede de lotação em {sede}."; justificativas e finalidade atuais.
- **Operação policial** (`operacao_policial`, ref. "Deslocamento de Operação Policial", sem funções): ida "O deslocamento {equipe} para {municipio} {data}."; evento "Que {equipe} acompanhe o briefing da operação policial que será realizado na cidade de {destino}, {hora} {data}, e permaneça no município {data} para prestar assessoria de imprensa, conduzir o atendimento aos veículos de comunicação e prestar suporte de comunicação com relação à operação realizada."; depois "Que {equipe} permaneça em {destino} {data} para a assessoria de imprensa pós-operação."; volta "Que {equipe} efetue o retorno à sede de lotação em {sede} {data}."; combinados vazios; justificativa atual; finalidade atual.
  Atenção: `{equipe}` começa com "do/dos" (genitivo). Para "Que {equipe} acompanhe" fica errado. Acrescente o marcador `{servidores}` também às etapas (nomes com "e", sem cargo) e use "Que o policial {servidores} acompanhe…" nos textos da operação policial. `MARCADORES_ETAPA` passa a incluir `"servidores"`; corrija a Task 2 (`marcadores_invalidos` do teste usa `{foo}` apenas).

- [ ] **Step 1: Testes** (`test_modelos_os.py`, `pytestmark = django_db`):

```python
def test_modelos_do_sistema_semeados():
    chaves = set(ModeloOS.objects.values_list("chave", flat=True))
    assert {"operacao_policial", "caminhao", "microonibus", "cerimonial"} <= chaves
    caminhao = ModeloOS.objects.get(chave="caminhao")
    assert caminhao.padrao_sistema and [f.codigo for f in caminhao.funcoes.all()] == ["conducao", "tecnico", "apoio"]
    assert caminhao.para_dominio().combinados == {"ida_e_antes", "depois_e_volta"}
    assert ModeloOS.objects.get(chave="operacao_policial").usa_hora
```

- [ ] **Step 2: Escrever modelos, `modelos_do_sistema.py`, `makemigrations` → renomear para `0053_modelos_de_os.py`, acrescentar `RunPython` que (a) semeia via `semear`, (b) `UPDATE` `modelo_id` por `tipo` (`caminhao`→caminhao, `microonibus`→microonibus, `cerimonial_antecipado`→cerimonial, `operacao_retorno_posterior`→operacao_policial), e depois `RemoveField tipo`. Chamar `auditar_tabela` para as tabelas novas como faz 0052 (ver padrão lá).** Regenerar sprite; atualizar `papeis.py`.

- [ ] **Step 3: Rodar `uv run python manage.py migrate` (POSTGRES_PASSWORD=local), o teste, `makemigrations --check`.** Erros esperados neste ponto: `ordens.py`, `forms.py`, `demonstracao.py` ainda falam de `tipo` — só importações quebram testes; a Task 4 conserta. Rodar só `test_modelos_os.py`.

- [ ] **Step 4: Commit** — "Modelos de OS: tabelas, modelos do sistema e migração".

---

### Task 4: Serviço da OS e documento

**Files:**
- Modify: `gestao/viagens/ordens.py` (`dados_dos_oficios`, `_funcoes_validas`, `salvar`, `faltando`, `dados_do_dominio`, `dados_do_documento`, `duplicar`, `SECAO`…)
- Modify: `gestao/viagens/views_ordens.py` (`SECAO_DA_FALTA` += `"horário do briefing": "dados"`, `"período do evento": "dados"`; mensagem do `_gravar` "o modelo usa funções")
- Modify: `gestao/viagens/templates/viagens/documentos/ordem_servico.html`
- Modify: `gestao/viagens/linha_do_tempo.py:140` (`"modelo_id": "modelo"`, `"data_evento_inicio"/"data_evento_fim": "período do evento"`, `"hora": "horário do briefing"`)
- Modify: `gestao/viagens/templates/viagens/ordens/_cabecalho_contexto.html:11` e `lista.html:63` (`ordem.modelo` / `ordem.modelo.nome`)
- Modify: `gestao/viagens/demonstracao.py:800-830` (`modelo=ModeloOS.objects.get(chave=…)`, evento = `o.viagem.data_inicio/fim` quando houver; a avulsa: `operacao_policial` com `hora=time(5)` e evento = `data_inicio + 1`)
- Test: `gestao/viagens/tests/test_ordens.py` (trocar `tipo="x"` por `modelo=_modelo("x")`; `_modelo = lambda chave: ModeloOS.objects.get(chave=chave)`), `test_folha_termo_os.py` (`"tipo": "padrao"` → `"modelo": ""`; cerimonial → `str(pk)`), novos testes abaixo.

**Interfaces:**
- `ordens.salvar(usuario, *, pk=None, oficios=(), modelo: ModeloOS | None = None, destinos=(), data_inicio=None, data_fim=None, data_evento_inicio: date | None = None, data_evento_fim: date | None = None, hora: time | None = None, servidores=(), motivo="", funcoes=None, assinante=MANTER, data_documento=MANTER, versao="") -> tuple[OrdemServico, list[str]]`
  - modelo inativo só é aceito se já era o da OS (`pk` e `ordem.modelo_id == modelo.pk`), senão `OrdemInvalida("Este modelo de OS está desativado.")`.
  - evento fora de `[data_inicio, data_fim]` → `OrdemInvalida("O período do evento precisa caber no período da OS.")`; evento sem início → `"Informe o início do evento."`.
  - cópia dos ofícios: `dados_dos_oficios` devolve também `"evento_inicio"/"evento_fim"` (da `o.viagem` do primeiro ofício com viagem); ao ligar ofício novo e a OS sem evento, copia e acrescenta `"período do evento"` a `copiados`.
  - `_funcoes_validas(modelo: ModeloOS | None, funcoes, servidores)`: permitidas = códigos das `FuncaoOS` do modelo.
- `ordens.dados_do_dominio(ordem) -> DadosOS` preenche `evento_inicio`, `evento_fim`, `hora`, `sede` (`"Cidade/UF"` da configuração; `""` sem sede).
- `ordens.textos_do_documento(ordem) -> dict`: com modelo → `itens_da_os(...)` convertido em `{"referencia", "itens": [(romano, texto)], "justificativas", "finalidade", "determinacao": "", "competencias": []}`; sem → `textos_da_os` + `"itens": []`.
- `ordens.faltando(ordem)`: com modelo, `dominio.faltam_para_o_modelo` no lugar de `faltam_funcoes` (mantém "período", "destino", "equipe", "motivo" primeiro).

- [ ] **Step 1: Testes novos em `test_ordens.py`:**

```python
def test_copia_o_evento_da_viagem_do_oficio(self, c):  # ofício com viagem no cenário: criar Viagem(data_inicio=…, data_fim=…) e ligar ao oficio_emitido
    ...; ordem, copiados = ordens.salvar(op, oficios=[oficio], modelo=_modelo("caminhao"))
    assert "período do evento" in copiados and ordem.data_evento_inicio == viagem.data_inicio

def test_evento_fora_do_periodo_e_recusado(self, c):
    with pytest.raises(ordens.OrdemInvalida, match="caber"):
        ordens.salvar(op, modelo=_modelo("caminhao"), data_inicio=d(4), data_fim=d(7), data_evento_inicio=d(2), data_evento_fim=d(3))

def test_modelo_desativado_so_fica_em_quem_ja_tinha(self, c): ...

def test_documento_do_caminhao_sai_em_itens(self, c):
    ordem, _ = ordens.salvar(op, modelo=_modelo("caminhao"), destinos=[londrina], data_inicio=d(3), data_fim=d(8), data_evento_inicio=d(5), data_evento_fim=d(6), servidores=[um, dois], motivo="a Feira", funcoes={str(um.pk): "conducao", str(dois.pk): "apoio"})
    dados = ordens.dados_do_documento(ordem, fixar=False)
    assert dados["referencia"] == "Deslocamento - Caminhão de apoio"
    assert [n for n, _ in dados["itens"]] == ["I", "II", "III", "IV", "V", "VI", "VII"]
    assert "conduza a Unidade Móvel" in dados["itens"][0][1]
    html = ordens.html_do_modelo(dados)
    assert "<ol" in html and "I - " in html and "DETERMINO" in html

def test_operacao_policial_com_hora(self, c):  # 17/18/19, hora 5h → "às 05h00min" no item do evento; sem hora → "horário do briefing" em faltando
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar** serviço, documento (`{% if d.itens %}<ol class="itens">{% for n, t in d.itens %}<li data-bloco="item-{{ forloop.counter }}" data-rotulo="Item {{ n }}"><span class="itens__numero">{{ n }} - </span>{{ t }}</li>{% endfor %}</ol>{% else %}…atual…{% endif %}`; CSS do `<ol class="itens">` no `<style>` do documento: `list-style: none; padding: 0; margin: 0 0 4mm;` e `li { margin-bottom: 4mm; text-align: justify; }`), linha do tempo, cabeçalho/lista, demonstração.
  Em `dados_do_documento`, a chave `"referencia"` já existe; incluir `"itens"`.

- [ ] **Step 4: Rodar** `test_ordens.py test_folha_termo_os.py test_resumos_padrao.py test_dominio_ordem_servico.py test_modelos_os.py` e `uv run python manage.py semear_demo`-equivalente: `POSTGRES_PASSWORD=local DJANGO_SETTINGS_MODULE=config.settings.preview DEMO_MODE=true POSTGRES_DB=pcpr_preview uv run python manage.py resetar_demo` (ver `docs/ops/preview.md`) para conferir a demonstração.

- [ ] **Step 5: Commit** — "OS: modelo, período do evento e horário no serviço e no documento".

---

### Task 5: Formulário e tela da OS

**Files:**
- Modify: `gestao/viagens/forms.py` (`FormularioOrdem`, `CampoEquipe.get_context` e `APRESENTACAO_*` → removidos; `_opcao_de_funcao(f: FuncaoOS)`)
- Modify: `gestao/viagens/templates/viagens/ordens/editar.html:59-63`
- Modify: `gestao/viagens/templates/viagens/widgets/equipe.html:6` (`data-com-hora`)
- Modify: `static/js/componentes/funcoes-equipe.js` (toggle `[data-campo-evento]` e `[data-campo-hora]`)
- Modify: `gestao/ui_lab/views.py` (`lab_funcoes` continua estático — só nomes/ícones; nada a mudar além de manter)
- Modify: `tests/e2e/test_ordens.py` (combobox "Modelo", `ordem.modelo.chave == "cerimonial"`)
- Test: `test_ordens.py::test_funcao_se_escolhe_no_cartao_da_equipe`, `test_folha_termo_os.py::test_trocar_para_tipo_com_funcao…`, novos: `test_campos_de_evento_e_hora_so_com_modelo`, `test_modelo_inativo_continua_selecionado`.

**Interfaces:**
- `FormularioOrdem.modelo = ModelChoiceField(label="Modelo", queryset=ModeloOS.objects.none(), required=False, empty_label="Padrão / texto livre", widget=Selecao())`; no `__init__`, queryset = ativos ∪ o modelo atual da OS; help_text por modelo via `ajuda_do_modelo(modelo) -> str` ("Funções: Condução, Técnico e Apoio · pede o horário do briefing" / "Texto simples: quem vai, para onde, quando e para quê." no padrão).
- `data_evento_inicio`/`data_evento_fim`: `DateField(required=False, input_formats=FORMATOS_DATA, widget=HiddenInput(attrs={"data-periodo-de"/"data-periodo-ate": ""}))`; `hora = TimeField(label="Horário do briefing", required=False, input_formats=["%H:%M"], widget=TimeInput(attrs=_attrs("entrada", type="time")))`.
- `equipe.widget.funcoes = {"campo_tipo": self["modelo"].auto_id, "por_tipo": {str(m.pk): [_opcao_de_funcao(f) for f in m.funcoes.all()] for m in modelos}, "ativas": …, "escolhidas": …, "com_hora": [str(m.pk) for m in modelos if m.usa_hora]}`; `equipe.html` emite `data-com-hora="{{ widget.funcoes.com_hora_json }}"`.
- JS: no `change` do campo, `for el of form.querySelectorAll("[data-campo-evento]") el.hidden = !valor`; `[data-campo-hora]`: `hidden = !comHora.includes(valor)`.
- `clean`: evento fim < início → erro em `data_evento_fim`; `dados["modelo"]`, `dados["hora"]`.
- `FormularioOrdem.de(ordem)`: `initial["modelo"] = ordem.modelo_id`, evento, hora.

- [ ] **Step 1: Testes** (adaptar os existentes; novos):

```python
def test_campos_de_evento_e_hora_so_com_modelo(self, c):
    html = cli.get(reverse("viagens:editar_ordem", args=[ordem_padrao.pk])).content.decode()
    assert 'data-campo-evento hidden' in html and 'data-campo-hora hidden' in html
    html = cli.get(reverse("viagens:editar_ordem", args=[ordem_policial.pk])).content.decode()
    assert 'data-campo-evento>' in html and 'data-campo-hora>' in html and 'name="hora"' in html
```

- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar.** No `editar.html`, trocar `form.tipo` por `form.modelo`; depois do calendário da OS: `<div data-campo-evento{% if not form.modelo.value %} hidden{% endif %}>{% periodo_calendario form.data_evento_inicio form.data_evento_fim prefixo="evento" rotulo="Período do evento" natureza="evento" fonte="Da viagem do ofício" editavel=editavel compacto=True %}</div>` e `<div data-campo-hora{% if not form.usa_hora %} hidden{% endif %}>{% include "componentes/campo.html" with campo=form.hora classe="campo--sm" %}</div>` (`form.usa_hora` = propriedade que lê o modelo escolhido). Atualizar a nota da seção ("O modelo escolhe o texto do documento e as funções da equipe.").
- [ ] **Step 4: Rodar** os testes de OS, `tests/e2e/test_ordens.py` (servidor sobe sozinho), `uv run tsc` (ver `scripts/verificar.sh`), ruff, mypy.
- [ ] **Step 5: Commit** — "Cadastro da OS: modelo, período do evento e horário do briefing".

---

### Task 6: Cadastro dos modelos (gestor)

**Files:**
- Create: `gestao/viagens/modelos_os.py` (serviço), `gestao/viagens/views_modelos_os.py`, `gestao/viagens/templates/viagens/ordens/modelos.html`, `gestao/viagens/templates/viagens/ordens/_modelos_criar.html`
- Modify: `gestao/viagens/forms.py` (`FormularioModeloOS`), `gestao/viagens/policies.py`, `gestao/viagens/urls.py` (antes de `ordens/<int:pk>/`), `gestao/viagens/navegacao.py:53` (Item "Modelos de OS", rota `viagens:modelos_os`, ícone `layers`, `requer="viagens.view_modeloos"`), `gestao/cadastros/views_crud.py:265` (entrada em `apoio` se `usuario.has_perm("viagens.view_modeloos")`, url `reverse("viagens:modelos_os")`, texto "Funções e texto de cada tipo de ordem de serviço.")
- Test: `gestao/viagens/tests/test_modelos_os.py`

**Interfaces:**
- `policies.pode_ver_modelos_os(u)`, `pode_gerir_modelos_os(u)` (= `has_perm add+change modeloos`), `pode_excluir_modelo_os(u, m)` (= `delete_modeloos and not m.padrao_sistema and not m.ordens.exists()`).
- `modelos_os.ModeloInvalido(Exception)`; `salvar(usuario, *, pk=None, nome, referencia, textos: dict[str, str], justificativas: str, finalidade: str, funcoes: list[dict]) -> ModeloOS` — valida marcadores (`marcadores_invalidos`), nome único (iexact), funções: nome obrigatório, código = `slugify(nome).replace("-", "_")[:30]` quando novo, único no modelo; funções removidas só se nenhuma OS do modelo usa o código (`ordens.filter(funcoes__has_key=…)` → `ModeloInvalido("A função “X” está em uso em N OS; mantenha-a.")`); `alternar_ativo(usuario, pk)`; `excluir(usuario, pk) -> str`.
- `FormularioModeloOS`: `nome`, `referencia`, 7 textos (`Textarea rows=2`, help_text com exemplo), `justificativas`, `finalidade`; funções como 6 linhas `funcao_nome_N`, `funcao_icone_N` (ChoiceField `ICONES_DE_FUNCAO`), `funcao_texto_N`, `funcao_codigo_N` (hidden), N=1..6; `funcoes()` → lista de dicts não vazios; `de(modelo)`.
- Views: `lista` (GET; `?editar=<pk>`, `?novo=1`, `?q=`), `salvar` (POST), `ativo` (POST pk), `excluir` (POST pk); URLs `ordens/modelos/`, `ordens/modelos/salvar/`, `ordens/modelos/<int:pk>/ativo/`, `ordens/modelos/<int:pk>/excluir/` com nomes `modelos_os`, `salvar_modelo_os`, `modelo_os_ativo`, `modelo_os_excluir`.
- Template `modelos.html`: cópia estrutural de `cadastros/textos.html` sem abas; cada registro: nome, selos (Inativo, Do sistema, "pede horário"), chips das funções (`<span class="selo selo--neutro">{% icone f.icone %}{{ f.nome }}</span>`), "em uso por N OS"; janela com `fieldset`s "Identificação", "Texto por etapa" (legenda dos marcadores em `<details>`), "Funções" (6 linhas em `class="campos"`), "Justificativas e finalidade".

- [ ] **Step 1: Testes** (`test_modelos_os.py`):

```python
def test_gestor_cria_modelo_com_funcoes_e_operador_so_ve(self, c): POST salvar → 302; ModeloOS "Operação com foto" com funções ["motorista", "fotografo"]; operador POST → 403; operador GET lista → 200 sem "Novo modelo".
def test_marcador_invalido_e_erro_no_campo(self, c): POST com evento="{foo}" → 422 e "foo" no html.
def test_excluir_so_sem_os_e_nunca_do_sistema(self, c)
def test_desativar_some_das_opcoes_mas_a_os_antiga_continua(self, c): após desativar, FormularioOrdem de OS nova não lista; a OS antiga ainda gera documento.
def test_funcao_em_uso_nao_some(self, c)
```

- [ ] **Step 2: Rodar e ver falhar.** **Step 3: Implementar.** **Step 4: Rodar; ruff; mypy; lint-imports.**
- [ ] **Step 5: Commit** — "Cadastro de modelos de OS para o gestor".

---

### Task 7: "Ver exemplo" sem gravar

**Files:**
- Modify: `gestao/viagens/ordens.py` (`dados_de_exemplo(modelo: dominio_modelo.Modelo, unidade) -> dict`), `views_modelos_os.py` (`exemplo`, POST, `moldura_da_folha`), `urls.py` (`ordens/modelos/exemplo/` → `exemplo_modelo_os`), `modelos.html` (botão `formaction` + `formtarget="_blank"` no rodapé da janela)
- Test: `test_modelos_os.py::test_exemplo_mostra_a_folha_sem_gravar`

**Interfaces:**
- `dados_de_exemplo`: `DadosOS(destinos=["Londrina/PR"], inicio=hoje+3, fim=hoje+8, evento_inicio=hoje+5, evento_fim=hoje+6, hora=time(5), motivo="a Feira de Exemplo", equipe=[Pessoa(1,"Ana Exemplo","Agente de Polícia Judiciária"), Pessoa(2,"Bruno Exemplo","Investigador de Polícia"), Pessoa(3,"Carla Exemplo","Escrivã de Polícia")], funcoes={1: f0, 2: f1, 3: f2} (as funções do modelo, cíclicas), sede=…)`; o dicionário do documento com `"numero": "000/ANO"`, `"previa": True` e a configuração da unidade (ou os traços quando não há).
- View: valida com `FormularioModeloOS`; inválido → a mesma tela 422 com erros; válido → `resposta_de_folha(request, gerar)` como `folha`.

- [ ] Testes → falhar → implementar → passar → commit "Modelos de OS: ver exemplo da folha sem gravar".

---

### Task 8: Demonstração, E2E, documentação e evidências

**Files:**
- Modify: `gestao/viagens/demonstracao.py` (uma OS por modelo do sistema — caminhão 3–8/5–6, micro-ônibus, cerimonial 4–7/5–6, operação policial com hora), `docs/product/documents.md` (seção da OS: modelos, etapas, marcadores), `docs/product/entities.md:47`
- Create: `tests/e2e/test_modelos_os.py` (gestor abre `/viagens/ordens/modelos/`, cria "Operação com foto" com 2 funções, vê na lista; axe sem violações; 360 e 1440 sem rolagem horizontal)
- Test: `tests/e2e/test_ordens.py` (já na Task 5), `tests/e2e/test_preview_demo.py` se tocar OS.

- [ ] Rodar `scripts/verificar.sh`, os testes rápidos das áreas tocadas (`gestao/viagens/tests/test_ordens.py test_folha_termo_os.py test_modelos_os.py test_dominio_*`, `gestao/ui_lab`, `tests/test_design_tokens.py`), os E2E novos/alterados, `resetar_demo` no preview local e capturar a 1440: OS caminhão (`#dados` + `#equipe` + folha) e o cadastro de modelos (lista + janela).
- [ ] Commit "Modelos de OS: demonstração, E2E e documentação"; push; atualizar a descrição da PR.
