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
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.carga import garantir_catalogos_do_plano, garantir_municipios
from gestao.cadastros.models import (
    Cargo,
    Combustivel,
    ConfiguracaoInstitucional,
    Lotacao,
    ModeloTexto,
    Municipio,
    Servidor,
    SubstituicaoAssinante,
    TabelaDiaria,
    Unidade,
    Viatura,
)
from gestao.cadastros.validacoes import RG_NAO_POSSUI
from gestao.identidade.backends import LOGIN_DEMO
from gestao.identidade.models import Usuario
from gestao.identidade.papeis import sincronizar_papeis

from . import rotas, services
from .models import (
    Documento,
    Historico,
    Oficio,
    OrdemServico,
    OrdemServicoDestino,
    Roteiro,
    Trecho,
    Viajante,
)

SEMENTE = 20_261_001
OFICIOS_BASE = 260
SERVIDORES_BASE = 170
VIATURAS_BASE = 48

TABELAS = (
    "coffee_certidao", "coffee_via", "coffee_movimento", "coffee_solicitacao",
    "coffee_lote_municipios", "coffee_lote",
    "coffee_termoaditivo", "coffee_contrato",
    "coffee_fornecedor", "coffee_configuracaooficio",
    "eventos_movimento", "eventos_anexosolicitacao", "eventos_solicitacaoequipe",
    "eventos_solicitacaoservico", "eventos_solicitacao",
    "imprensa_andamento", "imprensa_atendimento", "imprensa_integrante", "imprensa_veiculo",
    "publicacoes_andamento", "publicacoes_publicacao", "publicacoes_integrante",
    "publicacoes_unidaderesponsavel",
    "palestras_respostaenviada", "palestras_andamento", "palestras_palestra_temas",
    "palestras_palestra_palestrantes", "palestras_palestra", "palestras_palestrante",
    "palestras_tema", "palestras_respostapadrao",
    "plataforma_notificacao", "viagens_trechorealizado", "viagens_anexoprestacao",
    "viagens_relatoriotecnico",
    "viagens_diariobordotrecho", "viagens_diariobordo",
    "viagens_prestacaoservidor", "viagens_prestacaocontas",
    "viagens_viagemdestino", "viagens_viagem",
    "cadastros_tipoviagem", "viagens_viaassinada", "viagens_historico", "viagens_documento",
    "viagens_edicaodocumento", "viagens_trecho",
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
MOTIVOS_PRONTOS = [
    ("Unidade móvel em evento", "Apoio e condução da Unidade Móvel no evento.", True, True),
    ("Polícia Civil itinerante",
     "Atendimento à população com emissão de documentos no programa Polícia Civil "
     "Itinerante, com a equipe da unidade.", False, True),
    ("Cerimonial e apoio institucional",
     "Apoio ao cerimonial e à organização de solenidade institucional da Polícia Civil do "
     "Paraná.", False, True),
    ("Capacitação de servidores",
     "Participação de servidores em curso de capacitação promovido pela Escola Superior de "
     "Polícia Civil.", False, True),
    ("Escolta e transporte de material de grande porte para exposição agropecuária regional",
     "Escolta e transporte do material expositivo da Polícia Civil para a exposição "
     "agropecuária regional, com montagem e desmontagem do estande.", False, True),
    ("Feira antiga (não usar)", "Texto antigo mantido apenas para consulta.", False, False),
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
        garantir_catalogos_do_plano()
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
        # Catálogo de motivos (textos prontos): um é o padrão do ofício novo, um está inativo
        # e os nomes longos testam a escolha na folha.
        for ordem, (nome, texto, padrao, ativo) in enumerate(MOTIVOS_PRONTOS, start=1):
            ModeloTexto.objects.create(tipo=ModeloTexto.Tipo.MOTIVO, nome=nome, texto=texto,
                                       ordem=ordem * 10, padrao=padrao, ativo=ativo)
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
                    rg=f"{20_000_000 + n * 37}{n % 9}", cargo=rng.choice(cargos),
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
        # No PREVIEW o demo também administra usuários (dados fictícios), para a tela de
        # usuários e perfis poder ser avaliada.
        self.demo.groups.add(Group.objects.get(name="ADMINISTRADOR"))
        # E atende a imprensa (módulo da ASCOM), para as telas dele poderem ser avaliadas.
        self.demo.groups.add(Group.objects.get(name="ASCOM_IMPRENSA"))
        self.demo.groups.add(Group.objects.get(name="ASCOM_PUBLICACOES"))
        self.demo.groups.add(Group.objects.get(name="ASCOM_PALESTRAS"))
        # E despacha as solicitações de evento social (Diretoria-Geral).
        self.demo.groups.add(Group.objects.get(name="GESTOR_DG"))
        # E opera o Coffee Break (com ADMINISTRADOR, é o administrador do módulo).
        self.demo.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
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

    def ciclo_de_vida(self, oficios: list[Oficio]) -> None:
        """Telas das decisões D1–D3 com o que avaliar no PREVIEW: arquivados, um cancelado
        reativado e motoristas de fora da equipe (servidor de outro ofício e não cadastrado).
        Tudo pelos serviços reais (histórico e auditoria iguais aos da operação)."""
        gestor = self.gestores[0]
        emitidos = sorted((o for o in oficios if o.situacao == Oficio.Situacao.EMITIDO),
                          key=lambda o: (o.ano, o.numero))
        for oficio in emitidos[:3]:  # os mais antigos vão para Arquivados
            services.arquivar(oficio, self.operadores[oficio.unidade_id])
        cancelados = [o for o in oficios if o.situacao == Oficio.Situacao.CANCELADO]
        if cancelados:
            alvo = Oficio.objects.get(pk=cancelados[0].pk)
            services.reativar(alvo, gestor, "Evento remarcado para a mesma data; a viagem "
                                            "voltou a ser necessária.")
        rascunhos = [o for o in oficios if o.situacao == Oficio.Situacao.RASCUNHO
                     and o.tipo_transporte == Oficio.TipoTransporte.VIATURA
                     and o.viajantes.exists()][:2]
        for i, oficio in enumerate(rascunhos):
            atual = Oficio.objects.get(pk=oficio.pk)
            autor = self.operadores[atual.unidade_id]
            dados: dict[str, object]
            if i == 0:
                equipe = set(atual.viajantes.values_list("servidor_id", flat=True))
                fora = (Servidor.objects.filter(ativo=True).exclude(pk__in=equipe)
                        .order_by("pk").first())
                dados = {"motorista_externo": Oficio.MotoristaExterno.SERVIDOR,
                         "motorista_externo_servidor": fora}
            else:
                dados = {"motorista_externo": Oficio.MotoristaExterno.MANUAL,
                         "motorista_externo_nome": "Rogério Antunes Vasconcellos",
                         "motorista_externo_cargo": "Motorista terceirizado",
                         "motorista_externo_unidade": "Prefeitura Municipal (cedido)"}
            dados.update(motorista_oficio_origem=f"{40 + i}/{atual.ano}",
                         motorista_protocolo_origem=f"22233344{i}")
            services.salvar_dados(atual, autor, dados, versao=atual.versao)

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

    def cadastros_para_avaliar(self) -> None:
        """Estados do módulo de Cadastros que a base gerada não teria sozinha (feito depois
        dos ofícios, para não mudar o que já foi sorteado): cargo e combustível padrão,
        cadastros incompletos (referência: só o nome / a placa são obrigatórios) e inativos."""
        Cargo.objects.filter(nome="Agente de Polícia Judiciária").update(padrao=True)
        Combustivel.objects.filter(nome="Flex").update(padrao=True)
        ascom = self.unidades[0]
        for nome, extra in (("Ronaldo Teixeira Brandão", {}),
                            ("Vera Lúcia Andrade", {"unidade": ascom}),
                            ("Márcio Fontana Leite",
                             {"cargo": Cargo.objects.get(nome="Papiloscopista"),
                              "rg": RG_NAO_POSSUI})):
            Servidor.objects.create(nome=nome, **extra)  # sem CPF (e sem cargo): incompletos
        Servidor.objects.create(nome="Joana Prates Vieira", ativo=False, unidade=ascom,
                                cargo=Cargo.objects.get(nome="Escrivão de Polícia"))
        Viatura.objects.create(placa="ZZQ7B20", unidade=ascom)  # só a placa: incompleta
        Combustivel.objects.create(nome="Etanol", ativo=False)
        Cargo.objects.create(nome="Auxiliar Administrativo", ativo=False)
        # Assinantes por tipo e substituição (ASCOM): a justificativa tem titular próprio e
        # há um substituto valendo hoje para os ofícios; o endereço vem em campos.
        config = ConfiguracaoInstitucional.objects.get(unidade=ascom)
        equipe = Servidor.objects.filter(unidade=ascom, ativo=True,
                                         cargo__isnull=False).order_by("pk")
        titular, substituto = equipe[0], equipe[1]
        ConfiguracaoInstitucional.objects.filter(pk=config.pk).update(
            assina_justificativa=titular, cep="80230020", logradouro="Avenida Fictícia",
            numero="470", bairro="Centro", cidade_endereco="Curitiba", uf="PR",
            telefone="4130000000", email="ascom.demo@exemplo.invalid")
        SubstituicaoAssinante.objects.create(
            configuracao=config, tipo=SubstituicaoAssinante.Tipo.OFICIO, servidor=substituto,
            inicio=self.hoje - timedelta(days=3), fim=self.hoje + timedelta(days=12),
            motivo="Férias do titular (DEMO)")

    def termos_para_avaliar(self) -> None:
        """Termos de autorização (módulo 4): dos ofícios mais recentes de cada situação, um
        avulso com destinos próprios, um com viatura própria e um cancelado."""
        from .models import TermoAutorizacao, TermoDestino
        ascom = self.unidades[0]
        autor = Usuario.objects.filter(lotacao__unidade=ascom).order_by("pk").first()
        if autor is None:
            return
        recentes = list(Oficio.objects.filter(unidade=ascom).exclude(
            situacao=Oficio.Situacao.CANCELADO).order_by("-ano", "-numero")[:6])
        criados = [TermoAutorizacao.objects.create(unidade=ascom, oficio=o, criado_por=autor)
                   for o in recentes]
        avulso = TermoAutorizacao.objects.create(
            unidade=ascom, criado_por=autor, evento="Feira de Profissões (DEMO)",
            data_inicio=self.hoje + timedelta(days=20), data_fim=self.hoje + timedelta(days=21))
        for ordem, nome in enumerate(("Londrina", "Maringá")):
            TermoDestino.objects.create(termo=avulso, ordem=ordem,
                                        municipio=Municipio.objects.get(nome=nome, uf="PR"))
        avulso.servidores.set(self.servidores_por_unidade[ascom.pk][:3])
        if criados and self.viaturas_por_unidade[ascom.pk]:
            TermoAutorizacao.objects.filter(pk=criados[0].pk).update(
                viatura=self.viaturas_por_unidade[ascom.pk][0])
        if len(criados) > 1:
            TermoAutorizacao.objects.filter(pk=criados[-1].pk).update(
                situacao=TermoAutorizacao.Situacao.CANCELADO, cancelado_em=timezone.now(),
                motivo_cancelamento="Evento adiado pela organização (DEMO).")

    def ordens_para_avaliar(self) -> None:
        """Ordens de serviço (módulo 5): das últimas viagens da ASCOM (uma de caminhão, com as
        funções da equipe), uma avulsa e uma cancelada; nome do Delegado-Geral fictício."""
        from . import ordens
        ConfiguracaoInstitucional.objects.update(delegado_geral_nome="Delegado-Geral (DEMO)")
        ascom = self.unidades[0]
        autor = Usuario.objects.filter(lotacao__unidade=ascom).order_by("pk").first()
        if autor is None:
            return
        recentes = list(Oficio.objects.filter(unidade=ascom, trechos__isnull=False).exclude(
            situacao=Oficio.Situacao.CANCELADO).distinct().order_by("-ano", "-numero")[:4])
        criadas = []
        for i, o in enumerate(recentes):
            dados = ordens.dados_dos_oficios([o])
            ano = self.hoje.year
            ordem = OrdemServico.objects.create(
                unidade=ascom, ano=ano, numero=ordens.reservar_numero(ano), criado_por=autor,
                tipo="caminhao" if i == 0 else "padrao", data_inicio=dados["inicio"],
                data_fim=dados["fim"], motivo=dados["motivo"])
            ordem.oficios.set([o])
            ordem.servidores.set(dados["servidores"])
            for posicao, m in enumerate(dados["destinos"]):
                OrdemServicoDestino.objects.create(ordem=ordem, municipio=m, posicao=posicao)
            if i == 0:
                funcoes = ("conducao", "apoio", "tecnico")
                ordem.funcoes = {str(s.pk): funcoes[k % 3]
                                 for k, s in enumerate(dados["servidores"])}
                ordem.save(update_fields=["funcoes"])
            criadas.append(ordem)
        if len(criadas) > 1:
            OrdemServico.objects.filter(pk=criadas[-1].pk).update(
                situacao=OrdemServico.Situacao.CANCELADA, cancelado_em=timezone.now(),
                motivo_cancelamento="Viagem cancelada pela organização (DEMO).")
        avulsa = OrdemServico.objects.create(
            unidade=ascom, ano=self.hoje.year, numero=ordens.reservar_numero(self.hoje.year),
            criado_por=autor, tipo="operacao_retorno_posterior",
            data_inicio=self.hoje + timedelta(days=12), data_fim=self.hoje + timedelta(days=13),
            motivo="cobertura da operação (DEMO)")
        avulsa.servidores.set(self.servidores_por_unidade[ascom.pk][:2])
        OrdemServicoDestino.objects.create(ordem=avulsa, posicao=0,
                                           municipio=Municipio.objects.get(nome="Cascavel",
                                                                           uf="PR"))

    def viagens_para_avaliar(self) -> None:
        """Viagens (módulo 8): tipos de exemplo; uma viagem que junta o ofício mais recente
        da ASCOM, a OS e o plano dele; uma futura só com dados; uma cancelada."""
        from gestao.cadastros.models import TipoViagem

        from .models import PlanoTrabalho, Viagem, ViagemDestino
        tipos = [TipoViagem.objects.get_or_create(nome=n)[0]
                 for n in ("PCPR na Comunidade", "Unidade Móvel", "Operação (DEMO)")]
        ascom = self.unidades[0]
        autor = Usuario.objects.filter(lotacao__unidade=ascom).order_by("pk").first()
        oficio = (Oficio.objects.filter(unidade=ascom, trechos__isnull=False)
                  .exclude(situacao=Oficio.Situacao.CANCELADO).distinct()
                  .order_by("-ano", "-numero").first())
        if autor is None or oficio is None:
            return
        trechos = list(oficio.trechos.select_related("destino").order_by("ordem"))
        inicio = (timezone.localtime(trechos[0].saida_em).date() if trechos
                  else self.hoje + timedelta(days=10))
        cheia = Viagem.objects.create(unidade=ascom, criado_por=autor,
                                      titulo=f"{tipos[0].nome} / {tipos[1].nome}",
                                      motivo=oficio.motivo, data_inicio=inicio,
                                      data_fim=inicio + timedelta(days=2),
                                      situacao=Viagem.Situacao.PREPARACAO)
        cheia.tipos.set(tipos[:2])
        destinos = list(dict.fromkeys(t.destino for t in trechos if t.destino != oficio.sede))
        for i, m in enumerate(destinos[:3]):
            ViagemDestino.objects.create(viagem=cheia, municipio=m, ordem=i)
        Oficio.objects.filter(pk=oficio.pk).update(viagem=cheia)
        OrdemServico.objects.filter(oficios=oficio, viagem__isnull=True).update(viagem=cheia)
        PlanoTrabalho.objects.filter(oficios=oficio, viagem__isnull=True).update(viagem=cheia)
        futura = Viagem.objects.create(unidade=ascom, criado_por=autor, titulo=tipos[1].nome,
                                       motivo="Atendimento itinerante (DEMO)",
                                       data_inicio=self.hoje + timedelta(days=30))
        futura.tipos.set([tipos[1]])
        ViagemDestino.objects.create(viagem=futura, ordem=0,
                                     municipio=Municipio.objects.get(nome="Cascavel", uf="PR"))
        cancelada = Viagem.objects.create(
            unidade=ascom, criado_por=autor, titulo=tipos[2].nome,
            data_inicio=self.hoje + timedelta(days=15), situacao=Viagem.Situacao.CANCELADA,
            motivo_cancelamento="Ação adiada pela organização (DEMO).",
            cancelado_em=timezone.now())
        cancelada.tipos.set([tipos[2]])

    def prestacoes_para_avaliar(self) -> None:
        """Prestação de contas (módulo 9a): as prestações nascem sozinhas na emissão; aqui
        as seis mais recentes da ASCOM ganham estados para avaliar cada aba — saque
        vencendo, prestação vencida, equipe finalizada, enviada, devolvida e arquivada."""
        from django.core.exceptions import PermissionDenied
        from weasyprint import HTML

        from . import anexos, diario, prestacao, realizado, relatorio
        from .models import AnexoPrestacao, PrestacaoServidor

        def pdf_demo(titulo):
            return HTML(string=f"<h1>{titulo}</h1><p>Documento fictício do preview "
                               "(DEMO) — não tem valor.</p>").write_pdf()

        ascom = self.unidades[0]
        autor = (Usuario.objects.filter(lotacao__unidade=ascom, groups__name="OPERADOR_VIAGENS")
                 .order_by("pk").first())
        if autor is None:
            return
        equipes: dict[int, list[PrestacaoServidor]] = {}
        for ps in (prestacao.ativos().filter(prestacao__oficio__unidade=ascom)
                   .exclude(prestacao__oficio__situacao=Oficio.Situacao.CANCELADO)
                   .select_related("servidor")
                   .order_by("-prestacao__oficio__ano", "-prestacao__oficio__numero",
                             "servidor__nome")):
            if len(equipes) == 6 and ps.prestacao_id not in equipes:
                break
            equipes.setdefault(ps.prestacao_id, []).append(ps)
        h = self.hoje

        def lancar(ps, n, liberacao, prazo):
            prestacao.salvar_solicitacao(autor, ps.pk, numero=f"{h.year}/{n:04d}",
                                         liberacao=liberacao, prazo=prazo)

        def diario_preenchido(ps, inicio):
            d = diario.obter(ps.prestacao)
            km = inicio
            valores = {}
            for linha in diario.linhas(d):
                rodado = diario.prevista(linha) or 120
                valores[linha.pk] = {"km_inicial": km, "km_final": km + rodado}
                km += rodado + 4
            diario.salvar_linhas(autor, d.pk, valores)

        try:
            for i, linhas in enumerate(equipes.values()):
                if i == 2:  # viagem realizada: a volta atrasou um dia (diárias recalculadas)
                    realizado.ajustar(autor, linhas[0].prestacao_id)
                    volta = realizado.trechos(linhas[0].prestacao)[-1]
                    realizado.salvar(autor, linhas[0].prestacao_id, {volta.pk: (
                        volta.saida_em + timedelta(days=1), volta.chegada_em + timedelta(days=1))})
                if i in (0, 2, 3, 4):  # despacho, comprovantes, diário e RT (finalizar exige)
                    anexos.anexar(autor, linhas[0].prestacao_id, AnexoPrestacao.Tipo.DESPACHO,
                                  nome="despacho-DEMO.pdf", conteudo=pdf_demo("Despacho"))
                    for ps in linhas:
                        # Relida: com a viagem ajustada, a diária liberada é a recalculada.
                        ps = PrestacaoServidor.objects.select_related("prestacao__oficio").get(
                            pk=ps.pk)
                        anexos.anexar(autor, ps.prestacao_id, AnexoPrestacao.Tipo.COMPROVANTE,
                                      servidor_pk=ps.pk, nome="comprovante-DEMO.pdf",
                                      conteudo=pdf_demo("Comprovante de saque"),
                                      valor=prestacao.diaria_liberada(ps),
                                      data_operacao=h - timedelta(days=13),
                                      operacao=AnexoPrestacao.Operacao.SAQUE)
                    diario_preenchido(linhas[0], 40_000 + i * 3_000)
                    rt = relatorio.obter(linhas[0].prestacao)
                    sugestao = relatorio.sugestoes(linhas[0].prestacao)
                    relatorio.salvar(autor, rt.pk, {
                        "motivo": sugestao.get("motivo") or "Apoio ao evento (DEMO).",
                        "atividade": sugestao.get("atividade")
                        or "Atendimento ao público e apoio à equipe local (DEMO).",
                        "conclusao": sugestao.get("conclusao")
                        or "A ação foi realizada conforme o planejado (DEMO)."})
                for j, ps in enumerate(linhas):
                    n = 100 + i * 10 + j
                    if i == 0:  # saque vencendo
                        lancar(ps, n, h - timedelta(days=1), h + timedelta(days=2))
                    elif i == 1:  # prestação vencida
                        lancar(ps, n, h - timedelta(days=20), h - timedelta(days=10))
                    elif i in (2, 3, 4):  # finalizadas (3 enviada, 4 devolvida)
                        lancar(ps, n, h - timedelta(days=15), h - timedelta(days=12))
                        prestacao.finalizar(autor, ps.pk)
                    elif i == 5 and j == 0:
                        prestacao.arquivar(autor, ps.pk)
                if i in (3, 4):
                    prestacao.enviar(autor, linhas[0].pk, enviada_em=h - timedelta(days=5),
                                     protocolo=f"DEMO-{h.year}-{i}", equipe=True)
                if i == 4:
                    prestacao.devolver(autor, linhas[0].pk,
                                       "Comprovante do saque ilegível; anexe de novo (DEMO).")
        except (PermissionDenied, prestacao.PrestacaoInvalida, diario.DiarioInvalido,
                relatorio.RelatorioInvalido, anexos.AnexoInvalido, realizado.AjusteInvalido):
            return  # base sem os papéis (testes de unidade)

    def planos_para_avaliar(self) -> None:
        """Planos de trabalho (módulo 6): um completo a partir da viagem mais recente da
        ASCOM (com atividades, efetivo e diárias), um finalizado, um avulso incompleto e um
        cancelado. Coordenador padrão e assinante dos planos na configuração da ASCOM."""
        from django.core.exceptions import PermissionDenied

        from gestao.cadastros.models import AtividadePlano, PresetAtividades, ProgramaSolicitante

        from . import planos
        ascom = self.unidades[0]
        equipe = self.servidores_por_unidade[ascom.pk]
        autor = Usuario.objects.filter(lotacao__unidade=ascom, groups__name="OPERADOR_VIAGENS"
                                       ).order_by("pk").first()
        if autor is None or not equipe:
            return
        # Nomes fictícios: o tratamento do coordenador padrão segue o primeiro nome.
        primeiro_nome = equipe[0].nome.split()[0].lower()
        ConfiguracaoInstitucional.objects.filter(unidade=ascom).update(
            coordenador_plano=equipe[0], assina_plano=equipe[-1],
            coordenador_plano_genero="F" if primeiro_nome.endswith("a") else "M")
        basicas = list(AtividadePlano.objects.filter(codigo__in=["CIN", "BO", "AAC", "PALESTRAS"]))
        if basicas and not PresetAtividades.objects.exists():
            conjunto = PresetAtividades.objects.create(nome="ATENDIMENTO BÁSICO", padrao=True,
                                                       descricao="Documentos e orientação.")
            conjunto.atividades.set(basicas)
        programa = ProgramaSolicitante.objects.filter(nome__icontains="PARANÁ EM AÇÃO").first()
        recentes = list(Oficio.objects.filter(unidade=ascom, trechos__isnull=False).exclude(
            situacao=Oficio.Situacao.CANCELADO).distinct().order_by("-ano", "-numero")[:3])
        import uuid

        from gestao.plataforma.auditoria import contexto

        def acao():
            # Cada ação numa "requisição" própria da trilha (senão a linha do tempo junta tudo
            # num passo só — a semeadura inteira roda com a mesma identificação).
            return contexto(autor.pk, requisicao_id=uuid.uuid4().hex)

        try:
            criados = []
            for i, o in enumerate(recentes):
                with acao():
                    plano, _ = planos.salvar(
                        autor, oficios=[o], programa=programa if i != 1 else None,
                        programa_outros="Feira de serviços (DEMO)" if i == 1 else "",
                        atividades=basicas + list(AtividadePlano.objects.filter(
                            codigo="UNIDADE_MOVEL")) if i == 0 else basicas)
                criados.append(plano)
            if criados and not planos.pendencias(criados[0]):
                with acao():
                    planos.finalizar(autor, criados[0].pk)
                from . import resultados  # o gerado já tem resultados lançados
                feitos = {a.pk: (str(40 + 15 * i), "atendimentos registrados (DEMO)")
                          for i, a in enumerate(basicas[:3])}
                with acao():
                    resultados.salvar(autor, criados[0].pk, feitos)
            if len(criados) > 1:  # o segundo vira um plano de vários eventos
                segundo = criados[1]
                inicio = (segundo.data_fim or self.hoje) + timedelta(days=1)
                with acao():
                    planos.salvar_evento(
                        autor, segundo.pk, programa=programa, data_inicio=inicio,
                        destinos=list(Municipio.objects.filter(nome="Cascavel", uf="PR")),
                        atividades=basicas[:2])
            if len(criados) > 2:
                with acao():
                    planos.cancelar(autor, criados[-1].pk, "Ação adiada pelo município (DEMO).")
            with acao():
                planos.salvar(autor, programa_outros="Ação itinerante a definir (DEMO)",
                              data_inicio=self.hoje + timedelta(days=40))
        except (PermissionDenied, planos.PlanoInvalido):
            return  # base sem os papéis (testes de unidade): os planos ficam de fora

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
    gerador.ciclo_de_vida(oficios)
    gerador.cadastros_para_avaliar()
    gerador.termos_para_avaliar()
    gerador.ordens_para_avaliar()
    gerador.planos_para_avaliar()
    gerador.viagens_para_avaliar()
    gerador.prestacoes_para_avaliar()
    from gestao.imprensa import demonstracao as imprensa_demo
    imprensa_demo.semear(gerador.demo, gerador.hoje)
    from gestao.publicacoes import demonstracao as publicacoes_demo
    publicacoes_demo.semear(gerador.demo, gerador.hoje)
    from gestao.palestras import demonstracao as palestras_demo
    palestras_demo.semear(gerador.demo, gerador.hoje)
    from gestao.coffee import demonstracao as coffee_demo
    coffee_demo.semear(gerador.hoje, gerador.demo)
    from gestao.eventos import demonstracao as eventos_demo
    eventos_demo.semear(gerador.demo, gerador.hoje, tuple(gerador.operadores.values())[:3])
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


def notificacoes_para_avaliar() -> None:
    """Avisos de exemplo no sino do usuário demo (o mecanismo é real; os eventos que os
    geram chegam com a prestação de contas e as solicitações)."""
    from gestao.plataforma.models import Notificacao
    from gestao.plataforma.notificacoes import notificar

    demo = Usuario.objects.filter(login=LOGIN_DEMO).first()
    oficio = Oficio.objects.filter(situacao=Oficio.Situacao.EMITIDO).order_by("-ano",
                                                                              "-numero").first()
    if demo is None or oficio is None:
        return
    lista = reverse("viagens:oficios")
    notificar([demo], f"Ofício {oficio.numero_formatado} emitido (DEMO)",
              "Aviso de exemplo do preview: abra para ver o ofício.",
              f"{lista}?resumo={oficio.pk}")
    notificar([demo], "Bem-vindo ao preview (DEMO)",
              "Os avisos do sistema aparecem aqui; abrir leva ao registro e marca como lido.")
    [lido] = notificar([demo], "Aviso já lido (DEMO)", "Exemplo de aviso lido.")
    Notificacao.objects.filter(pk=lido.pk).update(lida=True)


def vias_assinadas_para_avaliar() -> None:
    """Vias assinadas (módulo 7), depois dos PDFs gerados: a do ofício emitido mais recente
    da ASCOM, a do termo genérico desse ofício e a de uma OS cujos dados mudaram depois
    (selo "Assinado, mas os dados mudaram"). O "assinado" é o próprio PDF gerado — no DEMO
    não há assinatura de verdade."""
    from . import assinados, ordens, termos
    from .models import TermoAutorizacao

    autor = (Usuario.objects.filter(lotacao__unidade__sigla="ASCOM",
                                    groups__name="OPERADOR_VIAGENS").order_by("pk").first())
    oficio = (Oficio.objects.filter(unidade__sigla="ASCOM", situacao=Oficio.Situacao.EMITIDO,
                                    arquivado_em__isnull=True,
                                    documentos__situacao=Documento.Situacao.PRONTO)
              .order_by("-ano", "-numero").first())
    if autor is None or oficio is None:
        return
    doc = assinados.documento_emitido(oficio, Documento.Tipo.OFICIO)
    if doc is not None:
        with doc.arquivo.open("rb") as f:
            assinados.anexar(autor, assinados.Alvo("oficio", oficio),
                             nome=f"oficio-{oficio.numero}-assinado-DEMO.pdf", conteudo=f.read())
    termo = TermoAutorizacao.objects.filter(oficio=oficio, situacao="ativo").first()
    if termo is not None:
        dados = termos.dados_do_documento(termo, termos.GENERICO)
        assinados.anexar(autor, assinados.Alvo("termo", termo, termos.GENERICO),
                         nome="termo-generico-assinado-DEMO.pdf",
                         conteudo=termos.pdf_do_documento(dados))
    ordem = (OrdemServico.objects.filter(unidade__sigla="ASCOM", situacao="ativa")
             .order_by("-ano", "-numero").first())
    if ordem is not None:
        conteudo = ordens.pdf_do_documento(ordens.dados_do_documento(ordem, fixar=True))
        ordem.refresh_from_db()
        assinados.anexar(autor, assinados.Alvo("ordem", ordem), nome="os-assinada-DEMO.pdf",
                         conteudo=conteudo)
        OrdemServico.objects.filter(pk=ordem.pk).update(
            motivo=f"{ordem.motivo} (ajustado depois da assinatura)")


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
