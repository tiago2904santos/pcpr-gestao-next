"""Palestras e eventos da ASCOM (paridade com a planilha "Palestras e Eventos ASCOM" da
referência, app `demandas_eventos`).

Cada palestra é o pedido de um solicitante (escola, empresa, associação) para a PCPR falar
de um tema: quando e onde, quem fala, quanto público. O status anda pelo registro de
andamento (`Andamento`), que pode completar o que o status pede (data, palestrante,
público); as respostas enviadas ao solicitante ficam em `RespostaEnviada`; as edições dos
campos ficam na trilha de auditoria do banco. Temas, palestrantes e respostas padrão são
cadastros de apoio.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from . import dominio


class Tema(models.Model):
    nome = models.CharField("nome", max_length=200)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "tema"
        verbose_name_plural = "temas"
        constraints = [models.UniqueConstraint(Lower("nome"), name="palestras_tema_nome")]

    def __str__(self) -> str:
        return self.nome


class Palestrante(models.Model):
    nome = models.CharField("nome", max_length=200)
    # Ligado ao cadastro de servidores, a mesma pessoa numa viagem e numa palestra no mesmo
    # dia pode virar aviso de choque de agenda (Agenda A2).
    servidor = models.ForeignKey("cadastros.Servidor", verbose_name="servidor no cadastro",
                                 on_delete=models.SET_NULL, related_name="palestrantes",
                                 null=True, blank=True)
    municipio = models.ForeignKey("cadastros.Municipio", verbose_name="município",
                                  on_delete=models.PROTECT, related_name="palestrantes",
                                  null=True, blank=True)
    divisao = models.CharField("divisão", max_length=100, blank=True)
    lotacao = models.CharField("lotação", max_length=150, blank=True)
    contato = models.CharField("contato", max_length=100, blank=True)
    email = models.EmailField("e-mail", blank=True)
    tema_abordagem = models.CharField("tema de abordagem", max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "palestrante"
        verbose_name_plural = "palestrantes"
        constraints = [models.UniqueConstraint(Lower("nome"), Lower("lotacao"),
                                               name="palestras_palestrante_nome_lotacao")]

    def __str__(self) -> str:
        return f"{self.nome} ({self.lotacao})" if self.lotacao else self.nome

    @property
    def descricao(self) -> str:  # a linha de baixo na busca (EscolhaMultiplaRemota)
        return " · ".join(p for p in (self.divisao, self.lotacao, self.tema_abordagem) if p)


class RespostaPadrao(models.Model):
    """Mensagem pronta para o solicitante; aceita {solicitante}, {data}, {horario},
    {municipio}, {palestrante} e {tema}."""

    tipo = models.CharField("tipo", max_length=200)
    mensagem = models.TextField("mensagem")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo"]
        verbose_name = "resposta padrão"
        verbose_name_plural = "respostas padrão"
        constraints = [models.UniqueConstraint(Lower("tipo"), name="palestras_resposta_tipo")]

    def __str__(self) -> str:
        return self.tipo


class Palestra(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", dominio.ROTULOS["pendente"]
        EM_ANDAMENTO = "em_andamento", dominio.ROTULOS["em_andamento"]
        AGUARDANDO_RETORNO = "aguardando_retorno", dominio.ROTULOS["aguardando_retorno"]
        AGENDADA = "agendada", dominio.ROTULOS["agendada"]
        ATENDIDA = "atendida", dominio.ROTULOS["atendida"]
        CANCELADA = "cancelada", dominio.ROTULOS["cancelada"]

    class Evento(models.TextChoices):
        PALESTRA = "palestra", "Palestra"
        PCPR_NA_COMUNIDADE = "pcpr_na_comunidade", "PCPR na Comunidade"
        EVENTO = "evento", "Evento"

    class Canal(models.TextChoices):
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"
        PROTOCOLO = "protocolo", "Protocolo"
        TELEFONE = "telefone", "Telefone"
        PRESENCIAL = "presencial", "Presencial"
        OUTRO = "outro", "Outro"

    # Pedido
    data_solicitacao = models.DateField("data da solicitação")
    canal_solicitacao = models.CharField("foi solicitado via", max_length=20,
                                         choices=Canal.choices, blank=True)
    protocolo = models.CharField("nº do protocolo", max_length=20, blank=True)
    solicitante = models.CharField("solicitante", max_length=300)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    assunto_email = models.CharField("assunto do e-mail", max_length=300, blank=True)
    pedido_contato = models.TextField("pedido/contato", blank=True)
    informacoes_previas = models.TextField("informações prévias", blank=True)
    descricao = models.TextField("descrição", blank=True)
    # Evento
    evento = models.CharField("evento", max_length=25, choices=Evento.choices,
                              default=Evento.PALESTRA)
    data_inicio_evento = models.DateField("data do evento", null=True, blank=True)
    data_fim_evento = models.DateField("fim do evento", null=True, blank=True)
    hora_inicio = models.TimeField("horário", null=True, blank=True)
    periodo_evento_texto = models.CharField("observação do período", max_length=200,
                                            blank=True)
    municipio = models.ForeignKey("cadastros.Municipio", verbose_name="município",
                                  on_delete=models.PROTECT, related_name="palestras",
                                  null=True, blank=True)
    local = models.CharField("local do evento", max_length=255, blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    bairro = models.CharField("bairro", max_length=120, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)
    quantidade_publico = models.PositiveIntegerField("quantidade de público", null=True,
                                                     blank=True)
    # Palestra
    temas = models.ManyToManyField(Tema, verbose_name="temas", related_name="palestras",
                                   blank=True)
    palestrantes = models.ManyToManyField(Palestrante, verbose_name="palestrantes",
                                          related_name="palestras", blank=True)
    # Andamento
    status = models.CharField("status", max_length=25, choices=Status.choices,
                              default=Status.PENDENTE)
    andamento = models.TextField("andamento", blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="palestras")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_solicitacao", "-pk"]
        verbose_name = "palestra ou evento"
        verbose_name_plural = "palestras e eventos"
        indexes = [
            models.Index(fields=["status", "data_solicitacao"], name="palestras_status_data"),
            models.Index(fields=["data_inicio_evento"], name="palestras_data_evento"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(data_inicio_evento__isnull=True)
                           | models.Q(data_fim_evento__isnull=True)
                           | models.Q(data_fim_evento__gte=models.F("data_inicio_evento"))),
                name="palestras_periodo_valido"),
        ]

    def __str__(self) -> str:
        return f"{self.get_evento_display()} #{self.pk}"

    @property
    def aberta(self) -> bool:
        return self.status in dominio.ABERTOS

    @property
    def tom(self) -> str:
        return dominio.TONS.get(self.status, "neutro")

    @property
    def titulo(self) -> str:
        municipio = self.municipio.nome if self.municipio_id and self.municipio else ""
        return f"{self.get_evento_display()} · {municipio}" if municipio \
            else self.get_evento_display()

    @property
    def periodo(self) -> str:
        return dominio.periodo_do_evento(self.data_inicio_evento, self.data_fim_evento,
                                         self.hora_inicio, self.periodo_evento_texto)

    @property
    def canal_texto(self) -> str:
        canal = self.get_canal_solicitacao_display() if self.canal_solicitacao else ""
        if self.canal_solicitacao == dominio.PROTOCOLO and self.protocolo:
            return f"{canal} nº {self.protocolo}"
        return canal

    @property
    def contato_texto(self) -> str:
        return " / ".join(p for p in (self.telefone, self.email) if p)


class Andamento(models.Model):
    """Uma mudança de status, com a anotação de quem registrou."""

    palestra = models.ForeignKey(Palestra, on_delete=models.CASCADE, related_name="andamentos")
    status_anterior = models.CharField(max_length=25, choices=Palestra.Status.choices)
    status_novo = models.CharField(max_length=25, choices=Palestra.Status.choices)
    anotacao = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-em", "-pk"]
        verbose_name = "andamento da palestra"
        verbose_name_plural = "andamentos das palestras"

    def __str__(self) -> str:
        return f"{self.palestra} → {self.get_status_novo_display()}"


class RespostaEnviada(models.Model):
    """O texto que a ASCOM mandou ao solicitante (a partir de uma resposta padrão)."""

    palestra = models.ForeignKey(Palestra, on_delete=models.CASCADE, related_name="respostas")
    tipo = models.CharField(max_length=200)
    texto = models.TextField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-em", "-pk"]
        verbose_name = "resposta enviada"
        verbose_name_plural = "respostas enviadas"

    def __str__(self) -> str:
        return f"{self.palestra} — {self.tipo}"
