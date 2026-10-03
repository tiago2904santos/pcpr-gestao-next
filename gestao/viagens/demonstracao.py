"""Dataset DEMO do ambiente PREVIEW: populoso, 100% fictício e determinístico (ADR 0011).

Tudo passa pelos **serviços reais** (criar, salvar, equipe, emitir, reabrir, cancelar,
excluir): numeração, diárias, prazos, assunto, histórico, documentos e auditoria saem
coerentes por construção. Só os carimbos de data/hora são ajustados depois, para a linha do
tempo parecer de um sistema em uso (o banco audita esses ajustes como qualquer UPDATE).

Determinismo: `random.Random(SEMENTE)`, listas em ordem fixa, sequências reiniciadas e datas
relativas a `hoje` — o mesmo dia produz exatamente o mesmo dataset.

Fictício por construção:
- nomes combinados de listas de prenomes e sobrenomes comuns;
- CPFs com **dígito verificador propositalmente inválido** (nunca coincidem com um CPF real);
- placas da série `ZZ*` e protocolos começando por `00` (padrões reservados aos dados DEMO);
- e-mails no domínio reservado `.invalid` (RFC 2606).
"""

from __future__ import annotations

import contextlib
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import connection, transaction
from django.utils import timezone

from gestao.cadastros.carga import garantir_municipios
from gestao.cadastros.models import (
    Cargo,
    Combustivel,
    ConfiguracaoInstitucional,
    Lotacao,
    ModeloTexto,
    Municipio,
    Servidor,
    TabelaDiaria,
    Unidade,
    Viatura,
)
from gestao.identidade.backends import LOGIN_DEMO
from gestao.identidade.models import Usuario
from gestao.identidade.papeis import sincronizar_papeis

from . import rotas, services
from .models import Documento, Historico, Oficio, Roteiro, Trecho, Viajante

SEMENTE = 20_261_001
OFICIOS_BASE = 260
SERVIDORES_BASE = 170
VIATURAS_BASE = 48

TABELAS = (
    "viagens_historico", "viagens_documento", "viagens_edicaodocumento", "viagens_trecho",
    "viagens_viajante",
    "viagens_oficio", "viagens_trechoroteiro", "viagens_roteiro", "viagens_numeracaoanual",
    "viagens_lacunanumeracao",
    "cadastros_lotacao", "cadastros_configuracaoinstitucional", "cadastros_servidor",
    "cadastros_viatura", "cadastros_cargo", "cadastros_combustivel", "cadastros_tabeladiaria",
    "cadastros_modelotexto", "cadastros_unidade", "plataforma_outbox",
    "identidade_tentativaacesso", "identidade_usuario_groups",
    "identidade_usuario_user_permissions", "identidade_usuario",
)

PRENOMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elaine", "Fábio", "Gabriela", "Henrique", "Isabela",
    "João", "Karen", "Leonardo", "Mariana", "Nelson", "Olívia", "Paulo", "Quésia", "Rafael",
    "Sabrina", "Tiago", "Úrsula", "Vinícius", "Wesley", "Yasmin", "Alessandra", "Beatriz",
    "Caio", "Débora", "Eduardo", "Fernanda", "Gustavo", "Helena", "Igor", "Juliana", "Lucas",
    "Marcelo", "Natália", "Otávio", "Patrícia", "Renata", "Samuel", "Tatiane", "Valéria",
    "Wagner", "Adriana", "Bernardo", "Cecília", "Danilo", "Estela", "Felipe", "Giovana",
    "Heitor", "Ingrid", "Jonas", "Larissa", "Murilo", "Nádia", "Priscila", "Rodrigo", "Simone",
]
SOBRENOMES = [
    "Almeida", "Barbosa", "Cardoso", "Duarte", "Esteves", "Ferraz", "Gouveia", "Holanda",
    "Ilha", "Jardim", "Lacerda", "Macedo", "Nogueira", "Oliveira", "Pacheco", "Quintela",
    "Rezende", "Sampaio", "Tavares", "Uchôa", "Vasconcelos", "Xavier", "Zanella", "Arruda",
    "Bittencourt", "Campos", "Dornelles", "Escobar", "Fontana", "Guimarães", "Hoffmann",
    "Iwamoto", "Junqueira", "Klein", "Lemos", "Moraes", "Nascimento", "Ortega", "Prado",
    "Queiroz", "Ribeiro", "Siqueira", "Teixeira", "Valente", "Werneck", "Yamamoto",
]
# (sigla, nome, sede, peso na distribuição de ofícios)
UNIDADES = [
    ("ASCOM", "Assessoria de Comunicação Social", "Curitiba", 22),
    ("DPC", "Divisão de Polícia da Capital", "Curitiba", 7),
    ("DPI", "Divisão de Polícia do Interior", "Curitiba", 7),
    ("DEIC", "Divisão Estadual de Investigações Criminais", "Curitiba", 6),
    ("DHPP", "Divisão de Homicídios e Proteção à Pessoa", "Curitiba", 5),
    ("ESPC", "Escola Superior de Polícia Civil", "Curitiba", 6),
    ("GDG", "Gabinete do Delegado-Geral", "Curitiba", 4),
    ("COPE", "Centro de Operações Policiais Especiais", "Curitiba", 4),
    ("NUCRIA", "Núcleo de Proteção à Criança e ao Adolescente Vítimas de Crimes — Coordenação "
               "Estadual de Atendimento Integrado", "Curitiba", 3),
    ("SDP-LDA", "Subdivisão Policial de Londrina", "Londrina", 4),
    ("SDP-MGA", "Subdivisão Policial de Maringá", "Maringá", 4),
    ("SDP-PGO", "Subdivisão Policial de Ponta Grossa", "Ponta Grossa", 3),
    ("SDP-CVL", "Subdivisão Policial de Cascavel", "Cascavel", 3),
    ("SDP-FOZ", "Subdivisão Policial de Foz do Iguaçu", "Foz do Iguaçu", 3),
    ("SDP-GPV", "Subdivisão Policial de Guarapuava", "Guarapuava", 2),
    ("SDP-UMU", "Subdivisão Policial de Umuarama", "Umuarama", 2),
    ("SDP-PBO", "Subdivisão Policial de Pato Branco", "Pato Branco", 2),
    ("SDP-APU", "Subdivisão Policial de Apucarana", "Apucarana", 2),
    ("SDP-CMO", "Subdivisão Policial de Campo Mourão", "Campo Mourão", 2),
    ("SDP-PNG", "Subdivisão Policial de Paranaguá", "Paranaguá", 2),
    ("SDP-TOL", "Subdivisão Policial de Toledo", "Toledo", 2),
    ("SDP-FBE", "Subdivisão Policial de Francisco Beltrão", "Francisco Beltrão", 2),
    ("SDP-UVA", "Subdivisão Policial de União da Vitória", "União da Vitória", 1),
    ("SDP-JAC", "Subdivisão Policial de Jacarezinho", "Jacarezinho", 1),
    ("SDP-TEL", "Subdivisão Policial de Telêmaco Borba", "Telêmaco Borba", 1),
]
CARGOS = ["Delegado de Polícia", "Escrivão de Polícia", "Investigador de Polícia",
          "Agente de Polícia Judiciária", "Papiloscopista", "Assessor de Comunicação"]
MODELOS_VIATURA = [
    ("Renault Master (Unidade Móvel)", "Diesel"), ("Chevrolet S10", "Diesel"),
    ("Toyota Hilux", "Diesel"), ("Mitsubishi L200 Triton", "Diesel"),
    ("Fiat Cronos", "Flex"), ("Volkswagen Gol", "Flex"), ("Renault Duster", "Flex"),
    ("Jeep Compass", "Flex"), ("Fiat Ducato Furgão", "Diesel"), ("Chevrolet Spin", "Flex"),
]
CAPITAIS = [("São Paulo", "SP"), ("Florianópolis", "SC"), ("Porto Alegre", "RS"),
            ("Rio de Janeiro", "RJ"), ("Campo Grande", "MS"), ("Belo Horizonte", "MG")]
MOTIVOS = [
    "Apoio e condução da Unidade Móvel no evento {evento} em {destino}.",
    "Cobertura jornalística de operação policial em {destino}.",
    "Participação em reunião de alinhamento operacional em {destino}.",
    "Realização de palestra de prevenção à violência em escolas de {destino}.",
    "Capacitação de equipes de atendimento em {destino}.",
    "Apoio às diligências da investigação em andamento em {destino}.",
    "Participação no {evento}, representando a Polícia Civil, em {destino}.",
    "Entrega de equipamentos e vistoria das instalações da delegacia de {destino}.",
    "Atendimento itinerante de emissão de documentos durante o {evento} em {destino}.",
]
EVENTOS = ["Festival de Inverno", "Feira Agropecuária Regional", "Seminário de Segurança "
           "Pública", "Encontro Estadual de Comunicação", "Congresso de Investigação Criminal",
           "Mutirão de Cidadania", "Expo Paraná Rural", "Semana de Prevenção às Drogas"]
MOTIVO_LONGO = (
    "Participação de equipe multidisciplinar no ciclo regional de capacitação em atendimento "
    "humanizado a vítimas de violência doméstica, com oficinas práticas, reuniões com a rede "
    "municipal de proteção (conselhos tutelares, assistência social, saúde e educação), "
    "visitas técnicas às unidades de atendimento e apresentação dos novos fluxos de registro "
    "e encaminhamento de ocorrências, conforme o plano anual de trabalho aprovado pela "
    "coordenação, com relatório circunstanciado a ser entregue em até cinco dias úteis após o "
    "retorno da equipe à sede."
)
TEXTOS_PRONTOS = [
    ("Pedido de urgência", "Solicito que o presente seja apreciado em regime de urgência, "
                           "em razão da proximidade da data do deslocamento."),
    ("Agradecimento", "Agradeço antecipadamente a atenção dispensada e coloco-me à disposição "
                      "para quaisquer esclarecimentos."),
    ("Observação sobre hospedagem", "Informo que a hospedagem será custeada pela organização "
                                    "do evento, cabendo a esta unidade apenas as despesas de "
                                    "alimentação e deslocamento."),
]
JUSTIFICATIVAS = [
    "A convocação para o evento foi recebida com antecedência inferior ao prazo regulamentar, "
    "inviabilizando o encaminhamento no prazo de 10 dias, sem prejuízo do interesse público.",
    "A diligência decorreu de fato novo na investigação, que exigiu deslocamento imediato da "
    "equipe para preservar provas e cumprir determinação judicial.",
    "A agenda foi confirmada pela organização do evento somente nesta semana; a participação "
    "institucional foi determinada pela Delegacia-Geral.",
]
INSTITUICOES = ["Prefeitura Municipal de {destino}", "Secretaria de Estado da Segurança "
                "Pública", "Comissão organizadora do {evento}"]
MEIOS = ["Ônibus de linha", "Veículo cedido pela Prefeitura de {destino}",
         "Aeronave comercial (ida e volta)", "Veículo da instituição organizadora"]


@dataclass
class Resultado:
    contagens: dict[str, int] = field(default_factory=dict)
    por_situacao: dict[str, int] = field(default_factory=dict)
    por_unidade: dict[str, int] = field(default_factory=dict)
    por_ano: dict[int, int] = field(default_factory=dict)
    documentos_pendentes: int = 0


def cpf_invalido(base: int) -> str:
    """11 dígitos com o 2º dígito verificador errado: nunca é um CPF real."""
    digitos = [int(d) for d in f"{base:09d}"]
    for peso_inicial in (10, 11):
        soma = sum(d * p for d, p in zip(digitos, range(peso_inicial, 1, -1), strict=False))
        resto = soma % 11
        digitos.append(0 if resto < 2 else 11 - resto)
    digitos[-1] = (digitos[-1] + 1) % 10
    return "".join(map(str, digitos))


def _aware(dia: date, hora: int, minuto: int = 0) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class _Gerador:
    def __init__(self, hoje: date, escala: float):
        self.rng = random.Random(SEMENTE)  # noqa: S311  # nosec B311 — determinismo, não criptografia
        self.hoje = hoje
        # Decisões usam só o início do dia (determinismo por dia); `agora` só limita os
        # carimbos de data/hora para nada ficar no futuro.
        self.referencia = _aware(hoje, 0)
        self.agora = timezone.now()
        self.escala = escala
        self.unidades: list[Unidade] = []
        self.pesos: list[int] = []
        self.sedes: dict[int, Municipio] = {}
        self.servidores_por_unidade: dict[int, list[Servidor]] = {}
        self.viaturas_por_unidade: dict[int, list[Viatura]] = {}
        self.operadores: dict[int, Usuario] = {}
        self.gestores: list[Usuario] = []
        self.demo: Usuario | None = None
        self.modelos_justificativa: list[ModeloTexto] = []
        self.ultimo_historico = 0

    # ------------------------------------------------------------- cadastros
    def cadastros(self) -> None:
        rng = self.rng
        garantir_municipios()
        sincronizar_papeis()
        pr = list(Municipio.objects.filter(uf="PR").order_by("nome"))
        self.municipios_pr = pr
        self.municipios_longos = sorted(pr, key=lambda m: (-len(m.nome), m.nome))[:12]
        self.capitais = [Municipio.objects.get(nome=n, uf=uf) for n, uf in CAPITAIS]
        self.brasilia = Municipio.objects.get(nome="Brasília", uf="DF")
        por_nome = {m.nome: m for m in pr}
        for faixa, valor in ((TabelaDiaria.Faixa.INTERIOR, "290.55"),
                             (TabelaDiaria.Faixa.CAPITAL, "371.26"),
                             (TabelaDiaria.Faixa.BRASILIA, "468.12")):
            TabelaDiaria.objects.create(faixa=faixa, vigente_desde=date(2000, 1, 1),
                                        valor_24h=Decimal(valor),
                                        norma="Tabela de diárias vigente (dados DEMO)")
        cargos = [Cargo.objects.create(nome=n) for n in CARGOS]
        combustiveis = {n: Combustivel.objects.create(nome=n)
                        for n in ("Diesel", "Flex", "Gasolina")}
        ModeloTexto.objects.create(tipo=ModeloTexto.Tipo.MOTIVO, nome="Unidade móvel em evento",
                                   texto="Apoio e condução da Unidade Móvel no evento.")
        # Trechos prontos para o editor do documento (ADR 0018); os do sistema não se apagam.
        for nome, texto in TEXTOS_PRONTOS:
            ModeloTexto.objects.create(tipo=ModeloTexto.Tipo.OFICIO, nome=nome, texto=texto,
                                       padrao_sistema=True)
        self.modelos_justificativa = [
            ModeloTexto.objects.create(tipo=ModeloTexto.Tipo.JUSTIFICATIVA,
                                       nome=f"Justificativa {i + 1}", texto=t)
            for i, t in enumerate(JUSTIFICATIVAS)
        ]
        destinatario = "Dra. Helena Vasconcelos Prado"
        for i, (sigla, nome, sede, peso) in enumerate(UNIDADES):
            unidade = Unidade.objects.create(sigla=sigla, nome=nome)
            self.unidades.append(unidade)
            self.pesos.append(peso)
            self.sedes[unidade.pk] = por_nome[sede]
            chefe = f"{PRENOMES[(i * 7) % len(PRENOMES)]} {SOBRENOMES[(i * 5) % len(SOBRENOMES)]}"
            ConfiguracaoInstitucional.objects.create(
                unidade=unidade, nome_extenso=nome, sede=por_nome[sede],
                endereco_rodape=f"{nome} - Rua Fictícia, {100 + i} - Centro - {sede}/PR - "
                                f"CEP 80000-{i:03d} - (41) 3000-{i:04d}",
                chefia_nome=chefe, chefia_cargo=f"Chefe da unidade ({sigla})",
                destinatario_nome=destinatario,
                destinatario_cargo="MD. Delegada-Geral Adjunta Administrativa",
                destinatario_orgao="Gabinete da Delegacia-Geral Adjunta Administrativa",
            )
            self.servidores_por_unidade[unidade.pk] = []
            self.viaturas_por_unidade[unidade.pk] = []
        # Servidores: no mínimo 2 por unidade, o resto proporcional ao peso.
        total = max(2 * len(self.unidades), round(SERVIDORES_BASE * self.escala))
        distribuicao = [2] * len(self.unidades)
        for _ in range(total - sum(distribuicao)):
            distribuicao[rng.choices(range(len(self.unidades)), self.pesos)[0]] += 1
        usados: set[str] = set()
        n = 0
        for unidade, quantidade in zip(self.unidades, distribuicao, strict=True):
            for _ in range(quantidade):
                while True:
                    nome = (f"{rng.choice(PRENOMES)} {rng.choice(SOBRENOMES)} "
                            f"{rng.choice(SOBRENOMES)}")
                    if nome not in usados:
                        usados.add(nome)
                        break
                n += 1
                self.servidores_por_unidade[unidade.pk].append(Servidor.objects.create(
                    nome=nome, cpf=cpf_invalido(900_000_000 + n * 7919),
                    rg=f"{20_000_000 + n * 37}-{n % 9}", cargo=rng.choice(cargos),
                    unidade=unidade, telefone=f"419{n:08d}"[:11],
                ))
        # Viaturas (série ZZ*): unidades com mais peso têm mais.
        for i in range(max(len(self.unidades) // 2, round(VIATURAS_BASE * self.escala))):
            unidade = self.unidades[i % len(self.unidades)] if i < len(self.unidades) else \
                rng.choices(self.unidades, self.pesos)[0]
            modelo, combustivel = MODELOS_VIATURA[i % len(MODELOS_VIATURA)]
            placa = f"ZZ{chr(65 + i % 26)}{i % 10}{chr(65 + (i * 7) % 26)}{(i * 13) % 100:02d}"
            viatura = Viatura.objects.create(
                placa=placa, modelo=modelo, combustivel=combustiveis[combustivel],
                tipo=Viatura.Tipo.CARACTERIZADA if i % 3 else Viatura.Tipo.DESCARACTERIZADA,
                unidade=unidade,
            )
            # Motoristas habituais: a maioria das viaturas tem um ou dois da própria unidade.
            proprios = self.servidores_por_unidade[unidade.pk]
            if proprios and rng.random() < 0.7:
                quantos = min(len(proprios), rng.choice([1, 1, 2]))
                viatura.motoristas.set(rng.sample(proprios, quantos))
            self.viaturas_por_unidade[unidade.pk].append(viatura)
        self._usuarios()

    def _usuarios(self) -> None:
        gestor = Group.objects.get(name="GESTOR_VIAGENS")
        operador = Group.objects.get(name="OPERADOR_VIAGENS")

        def criar(login: str, nome: str, grupo: Group, unidade: Unidade | None) -> Usuario:
            u = Usuario.objects.create_user(login, f"{login}@demo.invalid", None, nome=nome,
                                            unidade_sigla=unidade.sigla if unidade else "")
            u.groups.add(grupo)
            if unidade:
                Lotacao.objects.create(usuario=u, unidade=unidade)
            return u

        ascom = self.unidades[0]
        self.demo = criar(LOGIN_DEMO, "Operador de Demonstração", gestor, ascom)
        self.demo.groups.add(operador)
        for i, unidade in enumerate(self.unidades):
            nome = f"{PRENOMES[(i * 11 + 3) % len(PRENOMES)]} {SOBRENOMES[(i * 3 + 1) % 46]}"
            self.operadores[unidade.pk] = criar(f"op.{unidade.sigla.lower()}", nome, operador,
                                                unidade)
        for i in range(4):
            nome = f"{PRENOMES[(i * 13 + 5) % len(PRENOMES)]} {SOBRENOMES[(i * 9 + 4) % 46]}"
            self.gestores.append(criar(f"gestor.{i + 1}", nome, gestor, self.unidades[i]))
        criar("consulta.demo", "Consulta de Demonstração", Group.objects.get(name="CONSULTA"),
              None)

    # ------------------------------------------------------------- ofícios
    def _carimbar(self, oficio: Oficio, quando: datetime) -> None:
        """Dá aos eventos de histórico recém-criados a data/hora planejada."""
        novos = Historico.objects.filter(oficio=oficio, pk__gt=self.ultimo_historico)
        ultimo = max(novos.values_list("pk", flat=True), default=self.ultimo_historico)
        novos.update(em=min(quando, self.agora))
        self.ultimo_historico = ultimo

    def _data_oficio(self) -> date:
        r = self.rng.random()
        if r < 0.12:
            dias = self.rng.randint(0, 7)
        elif r < 0.35:
            dias = self.rng.randint(8, 45)
        elif r < 0.70:
            dias = self.rng.randint(46, 365)
        else:
            dias = self.rng.randint(366, 900)
        return max(self.hoje - timedelta(days=dias), date(self.hoje.year - 2, 1, 1))

    def _destino(self, sede: Municipio) -> Municipio:
        r = self.rng.random()
        if r < 0.04:
            return self.brasilia
        if r < 0.14:
            return self.rng.choice(self.capitais)
        if r < 0.18:
            return self.rng.choice(self.municipios_longos)
        while True:
            m = self.rng.choice(self.municipios_pr)
            if m.pk != sede.pk:
                return m

    def _roteiro(self, sede: Municipio, saida: datetime, tipo: str
                 ) -> tuple[list[services.TrechoInformado], list[Municipio]]:
        rng = self.rng

        def perna(origem: Municipio, destino: Municipio, saida: datetime
                  ) -> services.TrechoInformado:
            # Tempos como o itinerário 2.0 sugere: estimativa offline (sem rede no seed).
            e = rotas.estimar(origem, destino)
            return services.TrechoInformado(
                origem.pk, destino.pk, saida,
                saida + timedelta(minutes=e.minutos + e.adicional_sugerido),
                e.km or None, e.minutos, e.adicional_sugerido)

        trechos: list[services.TrechoInformado] = []
        destinos: list[Municipio] = []
        atual, t = sede, saida
        if tipo == "bate_volta":
            destino = self._destino(sede)
            destinos = [destino]
            for dia in range(rng.randint(2, 3)):
                inicio = saida + timedelta(days=dia)
                if trechos:  # destino longe: o dia seguinte começa depois de voltar
                    inicio = max(inicio, trechos[-1].chegada_em + timedelta(hours=8))
                ida = perna(sede, destino, inicio)
                trechos.append(ida)
                volta = ida.chegada_em + timedelta(hours=rng.randint(3, 8))
                trechos.append(perna(destino, sede, volta))
            return trechos, destinos
        quantidade = {"simples": 1, "mesmo_dia": 1, "varios": rng.randint(2, 4),
                      "muitos": 8}[tipo]
        for _ in range(quantidade):
            destino = self._destino(atual if atual.pk != sede.pk else sede)
            while destino.pk in (atual.pk, sede.pk) or destino in destinos:
                destino = self._destino(sede)
            trecho = perna(atual, destino, t)
            trechos.append(trecho)
            chegada = trecho.chegada_em
            destinos.append(destino)
            permanencia = (timedelta(hours=rng.randint(2, 5)) if tipo == "mesmo_dia" else
                           timedelta(hours=rng.choice([6, 10, 20, 26, 30, 44, 50, 70, 96])))
            t = chegada + permanencia
            atual = destino
        trechos.append(perna(atual, sede, t))
        return trechos, destinos

    def oficios(self) -> list[Oficio]:
        rng = self.rng
        planos = sorted(
            ((self._data_oficio(), rng.choices(self.unidades, self.pesos)[0], i)
             for i in range(max(12, round(OFICIOS_BASE * self.escala)))),
            key=lambda p: (p[0], p[2]),
        )
        criados: list[Oficio] = []
        for indice, (data_oficio, unidade, _) in enumerate(planos):
            criados.append(self._oficio(indice, data_oficio, unidade, len(planos)))
        # Dois rascunhos vazios excluídos: os números viram lacunas reaproveitáveis (D5).
        vazios = [o for o in criados if o.situacao == Oficio.Situacao.RASCUNHO
                  and not o.trechos.exists() and o.ano == self.hoje.year]
        for oficio in vazios[-2:]:
            services.excluir_rascunho(oficio, self.operadores[oficio.unidade_id])
            criados.remove(oficio)
        return criados

    def _oficio(self, indice: int, data_oficio: date, unidade: Unidade, total: int) -> Oficio:
        rng = self.rng
        demo = self.demo
        autor = (demo if demo is not None and unidade.pk == self.unidades[0].pk
                 and rng.random() < 0.5 else self.operadores[unidade.pk])
        gestor = rng.choice(self.gestores)
        sede = self.sedes[unidade.pk]
        # Nada no futuro: o ofício de hoje nasce no início do expediente ou 3 h atrás.
        minuto = rng.randint(0, 59)
        t = min(_aware(data_oficio, 8, minuto), self.agora - timedelta(hours=3))
        self.ultimo_historico = Historico.objects.order_by("-pk").values_list(
            "pk", flat=True).first() or 0
        oficio = services.criar_rascunho(autor, data_oficio=data_oficio)
        self._carimbar(oficio, t)
        inicio = t

        # Antecedência: 70% no prazo, 20% fora do prazo, 10% retroativo (convalidação).
        r = rng.random()
        antecedencia = (rng.randint(11, 45) if r < 0.70 else rng.randint(2, 10) if r < 0.90
                        else -rng.randint(1, 12))
        saida = _aware(data_oficio + timedelta(days=antecedencia), rng.choice([6, 7, 8, 9]),
                       rng.choice([0, 15, 30, 45]))
        tipo = rng.choices(["simples", "varios", "bate_volta", "mesmo_dia"], [50, 25, 10, 15])[0]
        especial = {total // 3: "muitos_destinos", total // 2: "muitos_viajantes",
                    (2 * total) // 3: "motivo_longo", total - 5: "valor_alto"}.get(indice)
        if especial == "muitos_destinos":
            tipo = "muitos"
        trechos, destinos = self._roteiro(sede, saida, tipo)
        if especial == "valor_alto":
            destinos = [self.brasilia]
            volta = saida + timedelta(days=18, hours=6)
            trechos = [services.TrechoInformado(sede.pk, self.brasilia.pk, saida,
                                                saida + timedelta(hours=2)),
                       services.TrechoInformado(self.brasilia.pk, sede.pk, volta,
                                                volta + timedelta(hours=2))]
        fim_viagem = trechos[-1].chegada_em
        viagem_passou = fim_viagem < self.referencia

        # Situação final.
        r = rng.random()
        if viagem_passou:
            alvo = "emitido" if r < 0.82 else "cancelado" if r < 0.92 else "rascunho"
        else:
            alvo = "emitido" if r < 0.45 else "cancelado" if r < 0.55 else "rascunho"
        estagio = "completo"
        if alvo == "rascunho":
            estagio = rng.choices(["vazio", "parcial", "sem_protocolo", "sem_justificativa",
                                   "pronto"], [15, 25, 20, 15, 25])[0]
        if estagio == "vazio":
            return self._fechar(oficio, inicio, t)

        destino_txt = destinos[0].nome
        evento = rng.choice(EVENTOS)
        motivo = (MOTIVO_LONGO if especial == "motivo_longo" else
                  rng.choice(MOTIVOS).format(evento=evento, destino=destino_txt))
        custeio = rng.choices(list(Oficio.Custeio), [80, 12, 8])[0]
        viaturas = self.viaturas_por_unidade[unidade.pk] or [
            v for vs in self.viaturas_por_unidade.values() for v in vs]
        usa_viatura = rng.random() < 0.7 and bool(viaturas)
        dados: dict = {
            "protocolo": "" if estagio == "sem_protocolo" else f"00{rng.randint(0, 9_999_999):07d}",
            "motivo": motivo,
            "custeio": custeio,
            "custeio_instituicao": (rng.choice(INSTITUICOES).format(destino=destino_txt,
                                                                     evento=evento)
                                    if custeio == Oficio.Custeio.OUTRA_INSTITUICAO else ""),
            "tipo_transporte": (Oficio.TipoTransporte.VIATURA if usa_viatura
                                else Oficio.TipoTransporte.OUTRO),
            "viatura": rng.choice(viaturas) if usa_viatura else None,
            "transporte_descricao": "" if usa_viatura else rng.choice(MEIOS).format(
                destino=destino_txt),
            "porte_arma": rng.random() < 0.8,
            "marcador": rng.choices(["", "retificado", "complementar"], [92, 4, 4])[0],
        }
        t += timedelta(minutes=rng.randint(5, 40))
        oficio = services.salvar_edicao(oficio, autor, dados,
                                        None if estagio == "parcial" else trechos)
        self._carimbar(oficio, t)

        # Equipe: maioria da unidade; às vezes alguém de outra unidade.
        tamanho = 12 if especial in ("muitos_viajantes", "valor_alto") else rng.choices(
            [1, 2, 3, 4, 5, 6, 8], [25, 30, 20, 12, 6, 4, 3])[0]
        proprios = list(self.servidores_por_unidade[unidade.pk])
        rng.shuffle(proprios)
        equipe = proprios[:tamanho]
        while len(equipe) < tamanho:
            outro = rng.choice(rng.choice(list(self.servidores_por_unidade.values())))
            if outro not in equipe:
                equipe.append(outro)
        for servidor in equipe:
            t += timedelta(minutes=rng.randint(1, 6))
            services.adicionar_viajante(oficio, autor, servidor)
            self._carimbar(oficio, t)
        if usa_viatura:
            viajante = oficio.viajantes.order_by("ordem")[rng.randrange(len(equipe))]
            services.definir_motorista(oficio, autor, viajante.pk)
            self._carimbar(oficio, t)
        oficio.refresh_from_db()

        if estagio == "parcial":
            return self._fechar(oficio, inicio, t)
        prazo = services.avaliar_prazo_do_oficio(oficio)
        if prazo.justificativa_obrigatoria and estagio != "sem_justificativa":
            modelo = rng.choice(self.modelos_justificativa)
            t += timedelta(minutes=rng.randint(3, 20))
            oficio = services.salvar_dados(oficio, autor, {"justificativa": modelo.texto,
                                                            "justificativa_modelo": modelo})
            self._carimbar(oficio, t)

        # Em parte dos ofícios a redação foi ajustada no editor do documento (ADR 0018).
        if estagio in ("completo", "pronto") and rng.random() < 0.18:
            t += timedelta(minutes=rng.randint(2, 15))
            self._editar_texto(oficio, autor, rng)
            self._carimbar(oficio, t)

        emissao = None
        pronto = services.verificar_prontidao(oficio).pode_emitir
        if pronto and (alvo == "emitido" or (alvo == "cancelado" and rng.random() < 0.5)):
            t = self._depois(t, max(t + timedelta(minutes=rng.randint(5, 30)),
                                    _aware(data_oficio, 10, rng.randint(0, 59))))
            self._emitir(oficio, autor, t)
            emissao = t
            oficio.refresh_from_db()
            if alvo == "emitido" and rng.random() < 0.08:
                oficio, t, emissao = self._reabrir(oficio, autor, gestor, t, emissao)
        if alvo == "cancelado":
            t = self._depois(t, t + timedelta(hours=rng.randint(2, 72)))
            services.cancelar(oficio, gestor, rng.choice([
                "Evento adiado pela organização.", "Missão cancelada pela chefia.",
                "Deslocamento substituído por reunião por videoconferência.",
                "Ofício emitido em duplicidade."]))
            self._carimbar(oficio, t)
        return self._fechar(oficio, inicio, t, emissao)

    def _reabrir(self, oficio: Oficio, autor: Usuario, gestor: Usuario, t: datetime,
                 emissao: datetime) -> tuple[Oficio, datetime, datetime | None]:
        rng = self.rng
        t = self._depois(t, t + timedelta(hours=rng.randint(1, 30)))
        oficio = services.reabrir(oficio, gestor, rng.choice([
            "Correção do horário de retorno informado pela equipe.",
            "Inclusão de servidor convocado posteriormente.",
            "Ajuste do protocolo após conferência."]))
        self._carimbar(oficio, t)
        if rng.random() < 0.7:  # corrigido e emitido de novo (versão 2 dos documentos)
            t = self._depois(t, t + timedelta(minutes=rng.randint(10, 90)))
            oficio = services.salvar_dados(oficio, autor,
                                           {"protocolo": f"00{rng.randint(0, 9_999_999):07d}"})
            self._carimbar(oficio, t)
            self._emitir(oficio, autor, t)
            oficio.refresh_from_db()
            return oficio, t, t
        return oficio, t, None

    # ------------------------------------------------------------- roteiros
    def roteiros(self, oficios: list[Oficio]) -> None:
        """Roteiros cadastrados (tela de roteiros e "usar roteiro" no ofício): um a cada
        quatro ofícios com trechos vira roteiro de origem; mais roteiros futuros avulsos na
        unidade do operador DEMO e um cancelado. Gerador próprio: não altera os ofícios."""
        rng = random.Random(SEMENTE + 2)  # noqa: S311  # nosec B311 — determinismo
        for indice, oficio in enumerate(oficios):
            if indice % 4 or oficio.situacao == Oficio.Situacao.CANCELADO:
                continue
            trechos = services.trechos_informados_do_roteiro_de(oficio)
            if not trechos:
                continue
            autor = self.operadores[oficio.unidade_id]
            roteiro = services.salvar_roteiro(autor, None, {
                "quantidade_servidores": max(1, oficio.viajantes.count()),
                "observacoes": oficio.motivo[:120]}, trechos)
            Oficio.objects.filter(pk=oficio.pk).update(roteiro=roteiro)
            Roteiro.objects.filter(pk=roteiro.pk).update(criado_em=oficio.criado_em,
                                                         atualizado_em=oficio.criado_em)
        ascom = self.unidades[0]
        autor = self.demo or self.operadores[ascom.pk]
        sede = self.sedes[ascom.pk]
        avulsos = []
        for i in range(max(4, round(12 * self.escala))):
            saida = _aware(self.hoje + timedelta(days=rng.randint(6, 75)), rng.choice([6, 7, 8]),
                           rng.choice([0, 30]))
            tipo = rng.choice(["simples", "simples", "varios", "bate_volta"])
            trechos, destinos = self._roteiro(sede, saida, tipo)
            evento = rng.choice(EVENTOS)
            avulsos.append(services.salvar_roteiro(autor, None, {
                "quantidade_servidores": rng.choice([1, 2, 3, 4, 6, 8, 10]),
                "observacoes": f"Unidade Móvel no evento {evento} ({destinos[0].nome})."},
                trechos))
            if i == 1:  # um sem trechos ainda: "rascunho" de planejamento
                avulsos.append(services.salvar_roteiro(autor, None, {
                    "quantidade_servidores": 4, "observacoes": "Planejamento: destino a definir."},
                    []))
        services.cancelar_roteiro(autor, avulsos[-1])

    def _depois(self, anterior: datetime, desejado: datetime) -> datetime:
        """Próximo instante da linha do tempo: depois do anterior e nunca no futuro."""
        return max(anterior + timedelta(seconds=30), min(desejado, self.agora))

    def _emitir(self, oficio: Oficio, autor: Usuario, quando: datetime) -> None:
        primeiro = services.emitir(oficio, autor)
        self._carimbar(oficio, quando)
        Documento.objects.filter(oficio=oficio, pk__gte=primeiro.pk).update(emitido_em=quando)

    def _editar_texto(self, oficio: Oficio, autor: Usuario, rng: random.Random) -> None:
        """Uma edição típica: um aposto na saudação e, às vezes, um parágrafo de texto pronto."""
        from .documentos.dados import dados_do_oficio
        from .documentos.pdf import regioes_do_modelo

        original = regioes_do_modelo("oficio", dados_do_oficio(oficio))
        corpo = original["corpo"].replace(
            "conforme cronograma abaixo:",
            rng.choice(["conforme cronograma abaixo, com a urgência que o caso requer:",
                        "conforme o cronograma a seguir, já alinhado com a organização do evento:",
                        "conforme cronograma abaixo, em continuidade às tratativas anteriores:"]))
        if rng.random() < 0.5:
            texto = rng.choice(TEXTOS_PRONTOS)[1]
            marca = '<table data-bloco="equipe"'
            corpo = corpo.replace(marca, f"<p>{texto}</p>{marca}", 1)
        # Texto igual ao modelo não é guardado (RegraViolada): nada a fazer nesse caso.
        with contextlib.suppress(services.RegraViolada):
            services.salvar_texto_do_documento(oficio, autor, "oficio", {"corpo": corpo})

    def _fechar(self, oficio: Oficio, inicio: datetime, fim: datetime,
                emissao: datetime | None = None) -> Oficio:
        oficio.refresh_from_db()
        campos = {"criado_em": inicio, "atualizado_em": min(fim, self.agora)}
        if oficio.situacao == Oficio.Situacao.EMITIDO and emissao:
            campos["emitido_em"] = emissao
        if oficio.situacao == Oficio.Situacao.CANCELADO:
            campos["cancelado_em"] = min(fim, self.agora)
        Oficio.objects.filter(pk=oficio.pk).update(**campos)
        oficio.refresh_from_db()
        return oficio


def limpar() -> None:
    with connection.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(TABELAS)} RESTART IDENTITY CASCADE")


def atualizar_estatisticas() -> None:
    """ANALYZE dentro da transação do seed. A transação trava as tabelas, então o autovacuum
    não consegue analisá-las; com estatísticas velhas (ex.: "municípios = 1 linha") o
    planejador escolheu laços aninhados de ~37 s por consulta de trechos e o seed nunca
    terminava (CI travado). O ANALYZE da própria transação enxerga as linhas recém-inseridas."""
    with connection.cursor() as cur:
        cur.execute(f"ANALYZE {', '.join((*TABELAS, 'cadastros_municipio'))}")


@transaction.atomic
def semear(hoje: date | None = None, escala: float = 1.0) -> Resultado:
    """Apaga os dados de negócio e recria o dataset DEMO (idempotente)."""
    limpar()
    gerador = _Gerador(hoje or timezone.localdate(), escala)
    gerador.cadastros()
    atualizar_estatisticas()
    oficios = gerador.oficios()
    gerador.roteiros(oficios)
    return resumo(len(oficios))


def acertar_datas_dos_documentos() -> None:
    """Depois da geração dos PDFs: gerado_em e o evento "documento gerado" logo após a
    emissão (o worker roda agora, mas a linha do tempo deve parecer a real)."""
    rng = random.Random(SEMENTE + 1)  # noqa: S311  # nosec B311 — determinismo
    for doc in Documento.objects.filter(situacao=Documento.Situacao.PRONTO).order_by("pk"):
        gerado = doc.emitido_em + timedelta(seconds=rng.randint(4, 40))
        Documento.objects.filter(pk=doc.pk).update(gerado_em=gerado)
        evento = (Historico.objects.filter(oficio_id=doc.oficio_id, acao=Historico.Acao.DOCUMENTO,
                                           descricao__startswith=doc.get_tipo_display(),
                                           descricao__contains=f"versão {doc.versao} ")
                  .order_by("pk").first())
        if evento:
            Historico.objects.filter(pk=evento.pk).update(em=gerado)


def resumo(total_oficios: int | None = None) -> Resultado:
    r = Resultado()
    r.contagens = {
        "unidades": Unidade.objects.count(), "servidores": Servidor.objects.count(),
        "viaturas": Viatura.objects.count(), "usuarios": Usuario.objects.count(),
        "oficios": total_oficios if total_oficios is not None else Oficio.objects.count(),
        "viajantes": Viajante.objects.count(), "trechos": Trecho.objects.count(),
        "documentos": Documento.objects.count(), "historico": Historico.objects.count(),
        "municipios": Municipio.objects.count(), "roteiros": Roteiro.objects.count(),
    }
    r.por_situacao = dict(Counter(Oficio.objects.values_list("situacao", flat=True)))
    r.por_unidade = dict(Counter(Oficio.objects.values_list("unidade__sigla", flat=True)))
    r.por_ano = dict(sorted(Counter(Oficio.objects.values_list("ano", flat=True)).items()))
    r.documentos_pendentes = Documento.objects.filter(
        situacao=Documento.Situacao.GERANDO).count()
    return r


def impressao_digital() -> list[tuple]:
    """Resumo estável do dataset (para provar determinismo)."""
    return list(Oficio.objects.order_by("ano", "numero").values_list(
        "ano", "numero", "situacao", "unidade__sigla", "diarias_total", "diarias_resumo",
        "protocolo", "motivo", "custeio", "tipo_transporte", "data_oficio",
    )) + list(Servidor.objects.order_by("pk").values_list("nome", "cpf", "unidade__sigla")) + list(
        Roteiro.objects.order_by("pk").values_list("unidade__sigla", "situacao",
                                                   "quantidade_servidores", "diarias_total"))
