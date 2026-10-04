"""Cadastros de apoio ao módulo Viagens.

Redesenhados a partir do comportamento observado no sistema de referência
(docs/product/entities.md). Toda tabela é auditada por trigger (migração 0002).
"""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from .validacoes import (
    RG_NAO_POSSUI,
    formatar_cpf,
    formatar_placa,
    formatar_rg,
    formatar_telefone,
)


class Ativavel(models.Model):
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Unidade(Ativavel):
    # Sigla opcional e até 50 caracteres, como na referência; o nome é o que identifica.
    sigla = models.CharField("sigla", max_length=50, blank=True)
    nome = models.CharField("nome", max_length=255)

    class Meta:
        ordering = ["sigla"]
        constraints = [models.UniqueConstraint(Lower("nome"), name="unidade_nome_unico")]

    def __str__(self) -> str:
        return self.sigla or self.nome


class Cargo(Ativavel):
    nome = models.CharField("nome", max_length=120)
    # O cargo padrão já vem escolhido no servidor novo (referência: "cargo padrão"). Um só.
    padrao = models.BooleanField("padrão", default=False)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(Lower("nome"), name="cargo_nome_unico"),
            models.UniqueConstraint(fields=["padrao"], condition=models.Q(padrao=True),
                                    name="cargo_um_padrao"),
            models.CheckConstraint(condition=~models.Q(padrao=True, ativo=False),
                                   name="cargo_padrao_ativo"),
        ]

    def __str__(self) -> str:
        return self.nome


class Combustivel(Ativavel):
    nome = models.CharField("nome", max_length=120)
    # O combustível padrão já vem escolhido na viatura nova. Um só.
    padrao = models.BooleanField("padrão", default=False)

    class Meta:
        ordering = ["nome"]
        verbose_name = "combustível"
        verbose_name_plural = "combustíveis"
        constraints = [
            models.UniqueConstraint(Lower("nome"), name="combustivel_nome_unico"),
            models.UniqueConstraint(fields=["padrao"], condition=models.Q(padrao=True),
                                    name="combustivel_um_padrao"),
            models.CheckConstraint(condition=~models.Q(padrao=True, ativo=False),
                                   name="combustivel_padrao_ativo"),
        ]

    def __str__(self) -> str:
        return self.nome


class Servidor(Ativavel):
    """Servidor público que viaja (viajante, motorista ou signatário).

    Como na referência, só o nome é obrigatório: o cadastro pode nascer incompleto e ser
    completado depois (`faltando` diz o quê; as telas sinalizam). CPF e telefone são
    guardados só com dígitos, o RG só com letras e números; os três são únicos quando
    informados.
    """

    nome = models.CharField("nome completo", max_length=255)
    cpf = models.CharField("CPF", max_length=11, blank=True)
    # Vazio = não informado; a marca RG_NAO_POSSUI = a pessoa não tem RG.
    rg = models.CharField("RG", max_length=30, blank=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name="servidores",
                              null=True, blank=True)
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="servidores",
                                null=True, blank=True)
    telefone = models.CharField("telefone", max_length=11, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "servidores"
        constraints = [
            models.UniqueConstraint(Lower("nome"), name="servidor_nome_unico"),
            models.UniqueConstraint(
                fields=["cpf"], condition=~models.Q(cpf=""), name="servidor_cpf_unico"
            ),
            models.UniqueConstraint(
                fields=["rg"], condition=~models.Q(rg="") & ~models.Q(rg=RG_NAO_POSSUI),
                name="servidor_rg_unico",
            ),
            models.UniqueConstraint(
                fields=["telefone"], condition=~models.Q(telefone=""),
                name="servidor_telefone_unico",
            ),
            models.CheckConstraint(
                condition=models.Q(cpf="") | models.Q(cpf__regex=r"^\d{11}$"),
                name="servidor_cpf_11_digitos",
            ),
        ]
        indexes = [models.Index(Lower("nome"), name="servidor_nome_idx")]

    def __str__(self) -> str:
        return self.nome

    @property
    def cpf_formatado(self) -> str:
        return formatar_cpf(self.cpf)

    @property
    def rg_formatado(self) -> str:
        return "" if self.sem_rg else formatar_rg(self.rg)

    @property
    def sem_rg(self) -> bool:
        return self.rg == RG_NAO_POSSUI

    @property
    def telefone_formatado(self) -> str:
        return formatar_telefone(self.telefone)

    @property
    def faltando(self) -> list[str]:
        """O que falta para o cadastro sair completo num documento (regra da referência:
        nome, cargo e CPF com 11 dígitos). Não impede nada: só sinaliza."""
        falta = []
        if not self.cargo_id:
            falta.append("cargo")
        if len(self.cpf or "") != 11:
            falta.append("CPF")
        return falta

    @property
    def completo(self) -> bool:
        return not self.faltando

    @property
    def faltando_texto(self) -> str:
        """"modelo, combustível e tipo"."""
        f = self.faltando
        return " e ".join([", ".join(f[:-1]), f[-1]]) if len(f) > 1 else "".join(f)

    @property
    def descricao(self) -> str:
        """"Cargo · SIGLA" para as escolhas e cartões (sem o que não foi informado)."""
        u, c = self.unidade, self.cargo
        partes = (c.nome if c is not None else "", (u.sigla or u.nome) if u is not None else "")
        return " · ".join(p for p in partes if p)

    @property
    def iniciais(self) -> str:
        partes = [p for p in self.nome.split() if len(p) > 2] or self.nome.split()
        return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


class Viatura(Ativavel):
    class Tipo(models.TextChoices):
        CARACTERIZADA = "caracterizada", "Caracterizada"
        DESCARACTERIZADA = "descaracterizada", "Descaracterizada"

    # Como na referência, só a placa é obrigatória; o resto pode ser completado depois.
    placa = models.CharField("placa", max_length=7, unique=True)
    modelo = models.CharField("modelo", max_length=120, blank=True)
    combustivel = models.ForeignKey(Combustivel, on_delete=models.PROTECT, null=True,
                                    blank=True, related_name="viaturas")
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices, blank=True)
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, null=True, blank=True, related_name="viaturas"
    )
    # Quem costuma dirigi-la: na folha do ofício, marcar um deles como motorista escolhe a
    # viatura sozinha, e a lista de viaturas sugere as ligadas à equipe.
    motoristas = models.ManyToManyField(
        Servidor, verbose_name="motoristas habituais", blank=True,
        related_name="viaturas_que_dirige",
    )

    class Meta:
        ordering = ["placa"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(placa__regex=r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"),
                name="viatura_placa_formato",
            )
        ]

    def __str__(self) -> str:
        return f"{self.placa_formatada} · {self.modelo}" if self.modelo else self.placa_formatada

    @property
    def placa_formatada(self) -> str:
        return formatar_placa(self.placa)

    @property
    def faltando(self) -> list[str]:
        """O que falta para a viatura sair completa (referência: modelo, combustível, tipo)."""
        return [rotulo for rotulo, valor in (("modelo", self.modelo.strip()),
                                             ("combustível", self.combustivel_id),
                                             ("tipo", self.tipo)) if not valor]

    @property
    def completo(self) -> bool:
        return not self.faltando

    @property
    def faltando_texto(self) -> str:
        """"modelo, combustível e tipo"."""
        f = self.faltando
        return " e ".join([", ".join(f[:-1]), f[-1]]) if len(f) > 1 else "".join(f)


class Municipio(models.Model):
    """Município brasileiro (lista oficial do IBGE, dados/municipios_ibge.csv).

    A faixa de diária (capital/interior/Brasília) é regra do domínio de Viagens
    (`viagens.dominio.diarias.faixa_do_destino`), não um atributo cadastral.
    """

    codigo_ibge = models.CharField("código IBGE", max_length=7, unique=True)
    nome = models.CharField("nome", max_length=120)
    uf = models.CharField("UF", max_length=2)
    # Sede municipal (dados/municipios_coordenadas.csv): mapa e estimativa de distância.
    latitude = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    longitude = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["nome"]
        indexes = [models.Index(Lower("nome"), "uf", name="municipio_nome_uf_idx")]

    def __str__(self) -> str:
        return f"{self.nome}/{self.uf}"


class TabelaDiaria(models.Model):
    """Valor da diária de 24h por faixa de destino, com vigência.

    Os percentuais (15% e 30%) não são digitados: são derivados do valor de
    24h pela regra de domínio (`viagens.dominio.diarias.valor_percentual`).
    """

    class Faixa(models.TextChoices):
        INTERIOR = "interior", "Interior"
        CAPITAL = "capital", "Capital"
        BRASILIA = "brasilia", "Brasília"

    faixa = models.CharField("faixa", max_length=10, choices=Faixa.choices)
    vigente_desde = models.DateField("vigente a partir de")
    valor_24h = models.DecimalField(
        "diária de 24 horas", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    norma = models.CharField("norma de referência", max_length=200, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["faixa", "-vigente_desde"]
        verbose_name = "vigência de diária"
        verbose_name_plural = "tabela de diárias"
        constraints = [
            models.UniqueConstraint(
                fields=["faixa", "vigente_desde"], name="diaria_vigencia_unica"
            ),
            models.CheckConstraint(
                condition=models.Q(valor_24h__gt=0), name="diaria_valor_positivo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_faixa_display()} desde {self.vigente_desde:%d/%m/%Y}"


class Lotacao(models.Model):
    """Unidade em que o usuário do sistema trabalha (define o escopo dos ofícios)."""

    usuario = models.OneToOneField(
        "identidade.Usuario", on_delete=models.CASCADE, related_name="lotacao"
    )
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="lotacoes")

    class Meta:
        verbose_name = "lotação"
        verbose_name_plural = "lotações"

    def __str__(self) -> str:
        return f"{self.usuario} em {self.unidade}"


class ModeloTexto(Ativavel):
    """Textos prontos reutilizáveis (motivo da viagem, justificativa)."""

    class Tipo(models.TextChoices):
        MOTIVO = "motivo", "Motivo do ofício"
        JUSTIFICATIVA = "justificativa", "Justificativa de prazo"
        OFICIO = "oficio", "Trecho para o texto do ofício"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    nome = models.CharField("nome", max_length=120)
    texto = models.TextField("texto")
    # Ordem na lista de escolha (menor primeiro); empate, pelo nome. Como na referência.
    ordem = models.PositiveSmallIntegerField("ordem", default=100)
    # O texto que já vem escrito quando o campo nasce vazio (ex.: motivo do ofício novo).
    # No máximo um por tipo — o banco garante.
    padrao = models.BooleanField("padrão", default=False)
    # Texto que vem com o sistema: pode ser desativado, nunca apagado pelo editor.
    padrao_sistema = models.BooleanField("padrão do sistema", default=False)

    class Meta:
        ordering = ["tipo", "ordem", "nome"]
        verbose_name = "modelo de texto"
        verbose_name_plural = "modelos de texto"
        # O padrão vale para os ofícios novos de todas as unidades, e os textos do sistema
        # são de todos: mexer neles é do gestor.
        permissions = [("gerir_padrao_texto",
                        "Definir o texto padrão e alterar textos padrão ou do sistema")]
        constraints = [
            models.UniqueConstraint(fields=["tipo"], condition=models.Q(padrao=True),
                                    name="modelotexto_um_padrao_por_tipo"),
            models.CheckConstraint(condition=~models.Q(padrao=True, ativo=False),
                                   name="modelotexto_padrao_ativo"),
        ]

    def __str__(self) -> str:
        return self.nome


class ConfiguracaoInstitucional(models.Model):
    """Dados da unidade emissora usados nos ofícios (cabeçalho, rodapé, destinatário).

    Uma linha por unidade emissora; o operador emite pela configuração da sua unidade.
    """

    unidade = models.OneToOneField(Unidade, on_delete=models.PROTECT, related_name="configuracao")
    nome_extenso = models.CharField("nome da unidade no cabeçalho", max_length=160)
    sede = models.ForeignKey(Municipio, on_delete=models.PROTECT, verbose_name="cidade sede")
    endereco_rodape = models.CharField("endereço no rodapé", max_length=255, blank=True)
    chefia_nome = models.CharField("nome da chefia (signatário)", max_length=150)
    chefia_cargo = models.CharField("cargo da chefia", max_length=150)
    destinatario_tratamento = models.CharField("tratamento", max_length=40, default="Exmo. Sr")
    destinatario_nome = models.CharField("destinatário", max_length=150)
    destinatario_cargo = models.CharField("cargo do destinatário", max_length=150)
    destinatario_orgao = models.CharField("órgão de destino", max_length=160)
    destinatario_cidade = models.CharField("cidade do destinatário", max_length=80,
                                           default="CURITIBA – Pr.")
    prazo_justificativa_dias = models.PositiveSmallIntegerField(
        "antecedência mínima (dias)", default=10,
        help_text="Viagens com menos dias de antecedência exigem justificativa.",
    )
    # Nome que sai na Ordem de Serviço ("atribuições conferidas pelo Delegado-Geral …").
    # Na referência era texto da configuração (m115); vazio, a OS avisa e sai em branco.
    delegado_geral_nome = models.CharField("Delegado-Geral", max_length=120, blank=True)
    # Quem assina cada tipo de documento (referência: AssinaturaConfiguracao, um por tipo).
    # Vazio: assina a chefia (nome e cargo escritos acima). P01: PT e OS ficaram de fora.
    assina_oficio = models.ForeignKey(
        "Servidor", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="assina os ofícios")
    assina_justificativa = models.ForeignKey(
        "Servidor", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="assina as justificativas")
    # Plano de trabalho (referência: "Assina os planos de trabalho"; sem ele, o plano sai
    # sem nome — não cai na chefia), o coordenador administrativo sugerido em todo plano
    # novo e o sufixo da numeração ("07/2026/ASCOM"; vazio, vale a sigla da unidade).
    assina_plano = models.ForeignKey(
        "Servidor", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="assina os planos de trabalho")
    coordenador_plano = models.ForeignKey(
        "Servidor", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="coordenador administrativo padrão")
    # Como o coordenador padrão sai no documento ("M": o Coordenador, "F": a Coordenadora).
    coordenador_plano_genero = models.CharField("como sai no documento", max_length=1,
                                                blank=True)
    sufixo_plano = models.CharField("sufixo da numeração do plano", max_length=20, blank=True)
    # Endereço em campos (referência, P10: "alinhar, sem remover campos nossos"). O rodapé
    # continua sendo o texto impresso; vazio, é montado a partir destes campos.
    cep = models.CharField("CEP", max_length=8, blank=True)
    logradouro = models.CharField("logradouro", max_length=160, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    bairro = models.CharField("bairro", max_length=120, blank=True)
    cidade_endereco = models.CharField("cidade", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField("telefone", max_length=11, blank=True)
    ramal = models.CharField("ramal", max_length=20, blank=True)

    class Meta:
        verbose_name = "configuração institucional"
        verbose_name_plural = "configurações institucionais"

    def __str__(self) -> str:
        return f"Configuração de {self.unidade}"

    @property
    def rodape(self) -> str:
        """O texto do rodapé: o escrito, ou o montado do endereço em campos."""
        if self.endereco_rodape.strip():
            return self.endereco_rodape.strip()
        cep = f"CEP {self.cep[:5]}-{self.cep[5:]}" if len(self.cep) == 8 else ""
        rua = ", ".join(p for p in (self.logradouro, self.numero) if p)
        cidade = "/".join(p for p in (self.cidade_endereco, self.uf) if p)
        fone = formatar_telefone(self.telefone)
        if fone and self.ramal:
            fone += f" ramal {self.ramal}"
        partes = (self.nome_extenso, rua, self.bairro, cidade, cep, fone, self.email)
        return " - ".join(p for p in partes if p)


class SubstituicaoAssinante(models.Model):
    """Quem assina no lugar do titular num período (férias, afastamento). Os documentos
    datados dentro do período saem com o substituto, sem mexer na configuração (referência:
    AssinaturaSubstituicao). Fim vazio: até ser encerrada."""

    class Tipo(models.TextChoices):
        TODOS = "todos", "Todos os documentos"
        OFICIO = "oficio", "Ofício"
        JUSTIFICATIVA = "justificativa", "Justificativa"
        PLANO = "plano_trabalho", "Plano de trabalho"

    configuracao = models.ForeignKey(ConfiguracaoInstitucional, on_delete=models.CASCADE,
                                     related_name="substituicoes")
    tipo = models.CharField("documentos", max_length=20, choices=Tipo.choices,
                            default=Tipo.TODOS)
    servidor = models.ForeignKey(Servidor, on_delete=models.PROTECT, related_name="+",
                                 verbose_name="substituto")
    inicio = models.DateField("início")
    fim = models.DateField("fim", null=True, blank=True)
    motivo = models.CharField("motivo", max_length=120, blank=True)
    ativo = models.BooleanField("ativa", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inicio", "tipo"]
        verbose_name = "substituição de assinante"
        verbose_name_plural = "substituições de assinante"
        constraints = [models.CheckConstraint(
            condition=models.Q(fim__isnull=True) | models.Q(fim__gte=models.F("inicio")),
            name="substituicao_periodo_ordenado")]

    def __str__(self) -> str:
        return f"{self.servidor} — {self.periodo}"

    @property
    def periodo(self) -> str:
        if self.fim:
            return f"{self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y}"
        return f"a partir de {self.inicio:%d/%m/%Y}"

    def vale_em(self, tipo: str, data) -> bool:
        return (self.ativo and data is not None and self.tipo in (self.Tipo.TODOS, tipo)
                and self.inicio <= data and (self.fim is None or data <= self.fim))


# ---------------------------------------------------------------- plano de trabalho
# Catálogos do plano de trabalho (referência: viagens_planos). A mais que na referência:
# "ativo" — o que já foi usado sai das escolhas sem ser apagado (como cargos e combustíveis).
class TipoViagem(Ativavel):
    """Tipo de viagem (referência: "uma viagem pode ter mais de um, e o título dela nasce
    deles" — ex.: PCPR na Comunidade)."""

    nome = models.CharField("nome", max_length=120)

    class Meta:
        ordering = ["nome"]
        verbose_name = "tipo de viagem"
        verbose_name_plural = "tipos de viagem"
        constraints = [models.UniqueConstraint(Lower("nome"), name="tipo_viagem_nome_unico")]

    def __str__(self) -> str:
        return self.nome


class ProgramaSolicitante(Ativavel):
    """Quem pede a ação (sai na contextualização do plano: "solicitação formulada pelo …")."""

    nome = models.CharField("nome", max_length=200)

    class Meta:
        ordering = ["nome"]
        verbose_name = "programa solicitante"
        verbose_name_plural = "programas solicitantes"
        constraints = [models.UniqueConstraint(Lower("nome"), name="programa_nome_unico")]

    def __str__(self) -> str:
        return self.nome


class HorarioAtendimento(Ativavel):
    """Faixa de atendimento ao público no evento, no formato "09:00 até 17:00"."""

    nome = models.CharField("faixa", max_length=60)

    class Meta:
        ordering = ["nome"]
        verbose_name = "horário de atendimento"
        verbose_name_plural = "horários de atendimento"
        constraints = [models.UniqueConstraint(Lower("nome"), name="horario_nome_unico")]

    def __str__(self) -> str:
        return self.nome


class AtividadePlano(Ativavel):
    """Serviço oferecido na ação. A meta e o recurso de cada atividade marcada compõem as
    seções "Metas estabelecidas" e "Recursos necessários" do plano."""

    # Identificador estável, nascido do nome (sem acento, maiúsculas, "_"). UNIDADE_MOVEL tem
    # efeito no documento (estrutura de unidade móvel e o recurso associado).
    codigo = models.CharField("código", max_length=40, unique=True)
    nome = models.CharField("atividade", max_length=255)
    meta = models.TextField("meta")
    recurso = models.TextField("recursos necessários", blank=True)

    UNIDADE_MOVEL = "UNIDADE_MOVEL"

    class Meta:
        ordering = ["nome"]
        verbose_name = "atividade do plano"
        verbose_name_plural = "atividades do plano"

    def __str__(self) -> str:
        return self.nome


class PresetAtividades(Ativavel):
    """Conjunto de atividades aplicado de uma vez no plano; o padrão já vem marcado no novo."""

    nome = models.CharField("nome", max_length=200)
    descricao = models.CharField("descrição", max_length=255, blank=True)
    padrao = models.BooleanField("padrão", default=False)
    atividades = models.ManyToManyField(AtividadePlano, related_name="presets",
                                        verbose_name="atividades")

    class Meta:
        ordering = ["nome"]
        verbose_name = "conjunto de atividades"
        verbose_name_plural = "conjuntos de atividades"
        constraints = [
            models.UniqueConstraint(Lower("nome"), name="preset_nome_unico"),
            models.UniqueConstraint(fields=["padrao"], condition=models.Q(padrao=True),
                                    name="preset_um_padrao"),
            models.CheckConstraint(condition=~models.Q(padrao=True, ativo=False),
                                   name="preset_padrao_ativo"),
        ]

    def __str__(self) -> str:
        return self.nome
