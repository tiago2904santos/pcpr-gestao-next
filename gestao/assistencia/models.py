"""Modelos da assistência por IA (ADR 0048): configuração por uso, orçamento mensal com
reserva, pedidos (a fila do worker) e sugestões com a decisão humana.

Trilha: as tabelas de ESTADO são auditadas pelo banco (trigger). O CONTEÚDO — o que a pessoa
escreveu para orientar o pedido, o texto sugerido, os avisos do validador e o texto aplicado —
fica em tabelas à parte, sem trigger e com prazo de retenção (`purgar`): a trilha é imutável
e guardaria para sempre o que só deve viver o prazo. O texto aplicado também está no próprio
registro de negócio (RT, ofício, plano), com a trilha dele.

Os usos (`UsoIA`) não são tabela: são código, registrados pelos contextos (`ganchos.py`).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


class ConfiguracaoUso(models.Model):
    """Liga/desliga, modo e limites de um uso. Sem linha = valores do código (modo regra)."""

    class Modo(models.TextChoices):
        REGRA = "regra", "Só regra (sem IA)"
        IA = "ia", "IA, com a regra como alternativa"

    uso = models.CharField(max_length=80, unique=True)
    ligado = models.BooleanField(default=True)
    modo = models.CharField(max_length=8, choices=Modo.choices, default=Modo.REGRA)
    max_chamadas_dia = models.PositiveIntegerField("chamadas de IA por dia (todas as pessoas)",
                                                   default=50)
    max_pedidos_pessoa_dia = models.PositiveIntegerField("pedidos por pessoa por dia", default=20)
    max_tokens_saida = models.PositiveIntegerField("tokens de saída por chamada", default=1500)
    max_entrada_caracteres = models.PositiveIntegerField("caracteres de entrada por chamada",
                                                         default=16_000)
    tempo_limite_s = models.PositiveSmallIntegerField("tempo-limite por chamada (s)", default=30)
    max_tentativas = models.PositiveSmallIntegerField("tentativas por pedido", default=2)
    motivo = models.CharField(max_length=255, blank=True)
    alterada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    alterada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["uso"]
        permissions = [
            ("administrar_ia", "Administrar usos, limites e orçamento de IA"),
            ("ver_painel_ia", "Ver uso, tokens e custo estimado da IA"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(max_tentativas__gte=1, max_tentativas__lte=3),
                                   name="assist_uso_tentativas_1_a_3"),
            models.CheckConstraint(condition=Q(tempo_limite_s__gte=1, tempo_limite_s__lte=120),
                                   name="assist_uso_tempo_limite"),
        ]

    def __str__(self) -> str:
        return f"{self.uso}: {'ligado' if self.ligado else 'desligado'} ({self.modo})"


class OrcamentoIA(models.Model):
    """Teto mensal de custo ESTIMADO, global (`escopo="global"`) ou de um uso.

    A reserva trava a linha (`select_for_update`), soma o pior caso da chamada a `reservado`
    antes de chamar e, depois, troca a reserva pelo estimado da resposta (`gasto_estimado`).
    Passou do teto: a chamada não sai e vale o caminho determinístico. Teto nulo = sem teto
    próprio (vale o global)."""

    escopo = models.CharField(max_length=80)
    mes = models.DateField()  # primeiro dia do mês (America/Sao_Paulo)
    teto_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    reservado_usd = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal(0))
    gasto_estimado_usd = models.DecimalField(max_digits=12, decimal_places=6,
                                             default=Decimal(0))
    chamadas = models.PositiveIntegerField(default=0)
    bloqueadas = models.PositiveIntegerField(default=0)
    tokens_entrada = models.PositiveBigIntegerField(default=0)
    tokens_saida = models.PositiveBigIntegerField(default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-mes", "escopo"]
        constraints = [
            models.UniqueConstraint(fields=["escopo", "mes"], name="assist_orcamento_unico"),
            models.CheckConstraint(condition=Q(reservado_usd__gte=0),
                                   name="assist_orcamento_reserva_nao_negativa"),
            models.CheckConstraint(condition=Q(teto_usd__isnull=True) | Q(teto_usd__gte=0),
                                   name="assist_orcamento_teto_nao_negativo"),
        ]

    def __str__(self) -> str:
        return f"Orçamento {self.escopo} {self.mes:%m/%Y}"

    @property
    def comprometido(self) -> Decimal:
        return self.reservado_usd + self.gasto_estimado_usd

    @property
    def chamadas_texto(self) -> str:
        return f"{self.chamadas} / {self.bloqueadas}"

    @property
    def percentual(self) -> int:
        if not self.teto_usd:
            return 100 if self.teto_usd == 0 and self.comprometido > 0 else 0
        return min(100, int(self.comprometido * 100 / self.teto_usd))


class PedidoSugestao(models.Model):
    """Um pedido de sugestão: é a própria fila do worker `processar_ia` (lease)."""

    class Estado(models.TextChoices):
        PENDENTE = "pendente", "Na fila"
        PROCESSANDO = "processando", "Redigindo"
        CONCLUIDO = "concluido", "Concluído"
        FALHOU = "falhou", "Falhou"
        CANCELADO = "cancelado", "Cancelado"

    uso = models.CharField(max_length=80)
    recurso_id = models.CharField(max_length=40)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDENTE)
    modo = models.CharField(max_length=8, choices=ConfiguracaoUso.Modo.choices,
                            default=ConfiguracaoUso.Modo.REGRA)
    versao_fonte = models.CharField(max_length=64)
    versao_prompt = models.CharField(max_length=40)
    chave = models.CharField(max_length=200, unique=True)  # idempotência do pedido
    tentativas = models.PositiveSmallIntegerField(default=0)
    reservado_ate = models.DateTimeField(null=True, blank=True)
    # Orçamento reservado para a chamada em curso (zerado ao liquidar ou ao liberar a reserva
    # presa de um worker que morreu no meio — `orcamento.liberar_reservas_presas`).
    reserva_usd = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal(0))
    reserva_mes = models.DateField(null=True, blank=True)
    #: Vagas do teto diário de chamadas tomadas por este pedido enquanto a chamada está em voo
    #: (zera ao concluir/encerrar): outros workers descontam estas vagas antes de admitir.
    tentativas_admitidas = models.PositiveSmallIntegerField(default=0)
    motivo = models.CharField(max_length=255, blank=True)  # código/mensagem, sem conteúdo
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["estado", "criado_em"], name="assist_pedido_fila_idx"),
                   models.Index(fields=["uso", "recurso_id"], name="assist_pedido_recurso_idx")]

    def __str__(self) -> str:
        return f"Pedido #{self.pk} ({self.uso})"


class ConteudoPedido(models.Model):
    """O que a pessoa escreveu para orientar o pedido (já mascarado). Sem trilha; retenção."""

    pedido = models.OneToOneField(PedidoSugestao, on_delete=models.CASCADE,
                                  related_name="conteudo")
    opcoes = models.JSONField(default=dict, blank=True)
    expira_em = models.DateTimeField()

    def __str__(self) -> str:
        return f"Orientação do pedido #{self.pedido_id}"


class Sugestao(models.Model):
    """O resultado de um pedido: sempre mostrado antes de aplicar, com as fontes e as lacunas;
    a decisão é humana (aceitar, editar e aceitar, descartar)."""

    class Estado(models.TextChoices):
        PRONTA = "pronta", "Pronta para revisão"
        ACEITA = "aceita", "Aceita"
        EDITADA = "editada", "Editada e aceita"
        DESCARTADA = "descartada", "Descartada"
        OBSOLETA = "obsoleta", "Obsoleta (os dados mudaram)"

    class Origem(models.TextChoices):
        REGRA = "regra", "Regra do sistema (sem IA)"
        SIMULADO = "simulado", "IA simulada (sem rede)"
        GRAVADO = "gravado", "IA gravada (teste)"
        ANTHROPIC = "anthropic", "IA · Anthropic"

    class MotivoDescarte(models.TextChoices):
        NENHUM = "", "—"
        GENERICO = "generico", "Texto genérico"
        FATO_ERRADO = "fato_errado", "Fato errado ou inventado"
        TOM = "tom", "Tom inadequado"
        DESNECESSARIO = "desnecessario", "Não precisava"
        OUTRO = "outro", "Outro"

    DECIDIDAS = (Estado.ACEITA, Estado.EDITADA, Estado.DESCARTADA)

    pedido = models.OneToOneField(PedidoSugestao, on_delete=models.PROTECT,
                                  related_name="sugestao")
    uso = models.CharField(max_length=80)
    recurso_id = models.CharField(max_length=40)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PRONTA)
    origem = models.CharField(max_length=12, choices=Origem.choices, default=Origem.REGRA)
    fallback = models.BooleanField("caiu no caminho determinístico", default=False)
    motivo_fallback = models.CharField(max_length=40, blank=True)
    modelo = models.CharField(max_length=60, blank=True)
    versao_prompt = models.CharField(max_length=40)
    versao_fonte = models.CharField(max_length=64)
    hash_contexto = models.CharField(max_length=64, blank=True)
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)
    tokens_estimados = models.BooleanField(default=False)
    custo_estimado_usd = models.DecimalField(max_digits=10, decimal_places=6,
                                             default=Decimal(0))
    duracao_ms = models.PositiveIntegerField(default=0)
    tentativas_ia = models.PositiveSmallIntegerField("chamadas à porta de IA", default=0)
    fontes = models.JSONField(default=list, blank=True)    # rótulos dos campos usados
    lacunas = models.JSONField(default=list, blank=True)   # códigos
    erros_validacao = models.JSONField(default=list, blank=True)  # só códigos
    decidida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    decidida_em = models.DateTimeField(null=True, blank=True)
    motivo_descarte = models.CharField(max_length=14, choices=MotivoDescarte.choices,
                                       blank=True)
    aplicada = models.BooleanField("gravada no registro", default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em", "-id"]
        indexes = [models.Index(fields=["uso", "recurso_id", "estado"],
                                name="assist_sugestao_recurso_idx")]
        constraints = [
            models.CheckConstraint(
                condition=~Q(estado__in=["aceita", "editada", "descartada"])
                | Q(decidida_por__isnull=False, decidida_em__isnull=False),
                name="assist_sugestao_decisao_tem_autor"),
        ]

    def __str__(self) -> str:
        return f"Sugestão #{self.pk} ({self.uso})"

    @property
    def tom(self) -> str:
        tons: dict[str, str] = {
            self.Estado.PRONTA: "info", self.Estado.ACEITA: "sucesso",
            self.Estado.EDITADA: "sucesso", self.Estado.DESCARTADA: "neutro",
            self.Estado.OBSOLETA: "aviso"}
        return tons.get(self.estado, "neutro")

    @property
    def tokens_texto(self) -> str:
        local = " (contagem local)" if self.tokens_estimados else ""
        return f"{self.tokens_entrada} + {self.tokens_saida}{local}"

    @property
    def custo_texto(self) -> str:
        return f"US$ {self.custo_estimado_usd:.6f} (estimado)"

    @property
    def decisao_texto(self) -> str:
        if not self.decidida_por_id:
            return ""
        from django.utils import timezone
        quando = timezone.localtime(self.decidida_em)
        return f"{self.get_estado_display()} por {self.decidida_por} em {quando:%d/%m/%Y %H:%M}"

    @property
    def com_ia(self) -> bool:
        return self.origem != self.Origem.REGRA and not self.fallback


class ConteudoSugestao(models.Model):
    """Os textos sugeridos, os avisos do validador e o texto aplicado. Sem trilha; retenção."""

    sugestao = models.OneToOneField(Sugestao, on_delete=models.CASCADE, related_name="conteudo")
    itens = models.JSONField(default=list)   # [{campo, rotulo, valor, fontes, aplicavel}]
    avisos = models.JSONField(default=list, blank=True)
    texto_aplicado = models.JSONField(default=dict, blank=True)  # campo -> texto gravado
    expira_em = models.DateTimeField()

    def __str__(self) -> str:
        return f"Conteúdo da sugestão #{self.sugestao_id}"
