"""Modelos da automação (ADR 0047): chaves de liga/desliga, contatos verificados com opt-in,
lista fechada de testadores, comunicações com tentativas e status de entrega, entradas de
webhook, recebimentos e a fila de exceções.

Trilha: as tabelas de estado são auditadas pelo banco (trigger). O **conteúdo** das mensagens
(texto enviado e recebido, nome de perfil, payload bruto do webhook) fica em tabelas à parte,
sem trigger e com prazo de retenção — a trilha é imutável e guardaria para sempre o que só
deve viver alguns dias (`purgar_automacao`).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

CANAL_WHATSAPP = "whatsapp"
CANAIS = [(CANAL_WHATSAPP, "WhatsApp")]


class ChaveAutomacao(models.Model):
    """Liga/desliga: `geral`, `canal:<canal>` e `fluxo:<fluxo>`. Sem linha = desligada.

    Desligar bloqueia efeitos novos (reserva de envio, associação automática); resultados
    que já aconteceram (status, mensagens recebidas) continuam sendo registrados."""

    class Estado(models.TextChoices):
        DESLIGADA = "desligada", "Desligada"
        LIGADA = "ligada", "Ligada"
        BLOQUEADA = "bloqueada", "Bloqueada (impedimento identificado)"

    class Modo(models.TextChoices):
        SOMBRA = "sombra", "Sombra (prepara e registra, não envia)"
        ASSISTIDO = "assistido", "Assistido (uma pessoa aprova cada envio)"
        AUTOMATICO = "automatico", "Automático"

    nome = models.CharField(max_length=80, unique=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.DESLIGADA)
    modo = models.CharField(max_length=12, choices=Modo.choices, default=Modo.ASSISTIDO)
    motivo = models.CharField(max_length=255, blank=True)
    alterada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    alterada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        permissions = [
            ("operar_automacao", "Operar a automação (contatos, aprovações, exceções)"),
            ("administrar_automacao", "Administrar canais, chaves e testadores"),
            ("ver_todas_unidades_automacao", "Ver comunicações de todas as unidades"),
        ]

    def __str__(self) -> str:
        return f"{self.nome}: {self.get_estado_display()}"


class ContatoVerificado(models.Model):
    """O número de WhatsApp de um servidor, com verificação e opt-in revogáveis.

    Ativo = verificado, com opt-in e não revogado. O endereço é conferido de novo com o
    telefone do cadastro a cada envio: se o cadastro mudou, o contato não vale até ser
    verificado de novo."""

    class Metodo(models.TextChoices):
        MENSAGEM = "mensagem", "A pessoa mandou mensagem deste número"
        OPERADOR = "operador", "Confirmado pelo operador com a pessoa"
        SIMULADO = "simulado", "Simulação (dados de demonstração)"

    class OrigemOptin(models.TextChoices):
        MENSAGEM = "mensagem", "Respondeu ACEITO pelo WhatsApp"
        FORMULARIO = "formulario", "Termo de participação assinado"
        PRESENCIAL = "presencial", "Concordou pessoalmente (registrado pelo operador)"
        SIMULADO = "simulado", "Simulação (dados de demonstração)"

    servidor = models.ForeignKey("cadastros.Servidor", on_delete=models.PROTECT,
                                 related_name="contatos_automacao")
    canal = models.CharField(max_length=20, choices=CANAIS, default=CANAL_WHATSAPP)
    endereco = models.CharField("número (E.164)", max_length=15)
    usuario_canal = models.CharField("BSUID", max_length=140, blank=True)
    wa_id = models.CharField(max_length=20, blank=True)
    verificado_em = models.DateTimeField(null=True, blank=True)
    verificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                       null=True, blank=True, related_name="+")
    metodo = models.CharField(max_length=12, choices=Metodo.choices, blank=True)
    optin_em = models.DateTimeField(null=True, blank=True)
    optin_origem = models.CharField(max_length=12, choices=OrigemOptin.choices, blank=True)
    optin_versao = models.CharField("versão do termo", max_length=20, blank=True)
    optin_registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                             null=True, blank=True, related_name="+")
    revogado_em = models.DateTimeField(null=True, blank=True)
    revogado_motivo = models.CharField(max_length=120, blank=True)
    ultima_mensagem_em = models.DateTimeField("última mensagem recebida", null=True, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["servidor__nome"]
        constraints = [
            models.UniqueConstraint(fields=["canal", "endereco"],
                                    condition=Q(revogado_em__isnull=True),
                                    name="contato_endereco_vigente_unico"),
            models.UniqueConstraint(fields=["servidor", "canal"],
                                    condition=Q(revogado_em__isnull=True),
                                    name="contato_servidor_vigente_unico"),
            models.CheckConstraint(condition=Q(endereco__regex=r"^\d{10,15}$"),
                                   name="contato_endereco_e164"),
        ]

    def __str__(self) -> str:
        return f"{self.servidor} ({self.get_canal_display()})"

    @property
    def ativo(self) -> bool:
        return bool(self.verificado_em and self.optin_em and not self.revogado_em)

    @property
    def situacao(self) -> tuple[str, str]:
        """(rótulo, tom) para a tela."""
        if self.revogado_em:
            return "Revogado", "neutro"
        if not self.verificado_em:
            return "Número não verificado", "aviso"
        if not self.optin_em:
            return "Sem opt-in", "aviso"
        return "Ativo", "sucesso"


class DestinatarioAutorizado(models.Model):
    """Lista fechada de testadores do LAB: fora de produção, só estes números recebem."""

    endereco = models.CharField("número (E.164)", max_length=15)
    descricao = models.CharField("quem é", max_length=120)
    valido_ate = models.DateField("vale até", null=True, blank=True)
    adicionado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                       related_name="+")
    adicionado_em = models.DateTimeField(auto_now_add=True)
    removido_em = models.DateTimeField(null=True, blank=True)
    removido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["descricao"]
        constraints = [
            models.UniqueConstraint(fields=["endereco"], condition=Q(removido_em__isnull=True),
                                    name="destinatario_vigente_unico"),
            models.CheckConstraint(condition=Q(endereco__regex=r"^\d{10,15}$"),
                                   name="destinatario_endereco_e164"),
        ]

    def __str__(self) -> str:
        return self.descricao

    def vigente(self, hoje=None) -> bool:
        hoje = hoje or timezone.localdate()
        return self.removido_em is None and (self.valido_ate is None or self.valido_ate >= hoje)


class EventoContato(models.Model):
    """O histórico auditado de um contato ou testador — sem o número. As tabelas de contato e
    de testadores ficam fora da trilha (a trilha é imutável e guardaria o telefone para
    sempre); quem fez o quê fica aqui, com os 4 últimos dígitos para a pessoa se situar."""

    class Acao(models.TextChoices):
        CADASTRADO = "cadastrado", "Contato cadastrado"
        VERIFICADO = "verificado", "Número verificado"
        OPTIN = "optin", "Opt-in registrado"
        REVOGADO = "revogado", "Contato revogado"
        TESTADOR_INCLUIDO = "testador_incluido", "Testador incluído"
        TESTADOR_REMOVIDO = "testador_removido", "Testador removido"

    acao = models.CharField(max_length=20, choices=Acao.choices)
    contato = models.ForeignKey(ContatoVerificado, on_delete=models.PROTECT, null=True,
                                blank=True, related_name="eventos")
    destinatario = models.ForeignKey(DestinatarioAutorizado, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="eventos")
    servidor = models.ForeignKey("cadastros.Servidor", on_delete=models.PROTECT, null=True,
                                 blank=True, related_name="+")
    origem = models.CharField(max_length=20, blank=True)  # operador | mensagem | simulador…
    final = models.CharField(max_length=4, blank=True)
    por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                            blank=True, related_name="+")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-em", "-id"]

    def __str__(self) -> str:
        return f"{self.get_acao_display()} (final {self.final})"


def registrar_evento_contato(acao: str, *, contato=None, destinatario=None, por=None,
                             origem: str = "") -> EventoContato:
    endereco = getattr(contato, "endereco", "") or getattr(destinatario, "endereco", "")
    return EventoContato.objects.create(
        acao=acao, contato=contato, destinatario=destinatario,
        servidor_id=getattr(contato, "servidor_id", None), origem=origem[:20],
        final=endereco[-4:], por=por if getattr(por, "pk", None) else None)


class Comunicacao(models.Model):
    """Uma mensagem que o sistema decidiu mandar a alguém, do agendamento ao resultado.

    É a própria fila: nasce na transação da mudança de negócio (o "evento transacional"),
    o worker a reserva com prazo (lease), revalida tudo e só então chama o canal — fora de
    qualquer transação. Resultado desconhecido nunca reenvia sozinho (vira exceção)."""

    class Situacao(models.TextChoices):
        AGUARDANDO_APROVACAO = "aguardando_aprovacao", "Aguardando aprovação"
        AGENDADA = "agendada", "Agendada"
        RESERVADA = "reservada", "Enviando"
        ENVIADA = "enviada", "Enviada"
        MANUAL = "manual", "Enviada à mão (contingência)"
        SOMBRA = "sombra", "Registrada em sombra (não enviada)"
        FALHOU = "falhou", "Falhou"
        INCERTA = "incerta", "Resultado desconhecido"
        RECUSADA = "recusada", "Não enviada (bloqueio)"
        OBSOLETA = "obsoleta", "Obsoleta (o assunto mudou)"
        EXPIRADA = "expirada", "Expirada"
        CANCELADA = "cancelada", "Cancelada"

    class Entrega(models.TextChoices):
        NENHUMA = "", "—"
        ACEITA = "aceita", "Aceita pelo WhatsApp"
        ENVIADA = "enviada", "Enviada"
        ENTREGUE = "entregue", "Entregue"
        LIDA = "lida", "Lida"
        FALHOU = "falhou", "Falhou na entrega"

    PENDENTES = (Situacao.AGUARDANDO_APROVACAO, Situacao.AGENDADA, Situacao.RESERVADA)
    PROBLEMAS = (Situacao.FALHOU, Situacao.INCERTA, Situacao.RECUSADA)

    tipo = models.CharField(max_length=80)
    fluxo = models.CharField(max_length=80)
    canal = models.CharField(max_length=20, choices=CANAIS, default=CANAL_WHATSAPP)
    servidor = models.ForeignKey("cadastros.Servidor", on_delete=models.PROTECT, null=True,
                                 blank=True, related_name="comunicacoes_automacao")
    contato = models.ForeignKey(ContatoVerificado, on_delete=models.PROTECT, null=True,
                                blank=True, related_name="comunicacoes")
    unidade = models.ForeignKey("cadastros.Unidade", on_delete=models.PROTECT, null=True,
                                blank=True, related_name="+")
    recurso = models.CharField("assunto", max_length=80, blank=True)  # "tipo.modelo:pk"
    versao = models.CharField(max_length=64, blank=True)
    contexto = models.JSONField(default=dict, blank=True)  # ids, nunca dado pessoal
    chave = models.CharField(max_length=200, unique=True)
    revisao = models.PositiveIntegerField("versão", default=1)  # muda a cada decisão humana
    situacao = models.CharField(max_length=24, choices=Situacao.choices,
                                default=Situacao.AGENDADA)
    entrega = models.CharField(max_length=10, choices=Entrega.choices, blank=True, default="")
    motivo = models.CharField(max_length=255, blank=True)
    agendada_para = models.DateTimeField(default=timezone.now)
    expira_em = models.DateTimeField(null=True, blank=True)
    proxima_tentativa_em = models.DateTimeField(default=timezone.now)
    tentativas = models.PositiveSmallIntegerField(default=0)
    reservada_ate = models.DateTimeField(null=True, blank=True)
    mensagem_id = models.CharField("id no provedor", max_length=300, blank=True)
    origem_envio = models.CharField(max_length=20, blank=True)  # simulado | cloud_api | manual
    enviada_em = models.DateTimeField(null=True, blank=True)
    entregue_em = models.DateTimeField(null=True, blank=True)
    lida_em = models.DateTimeField(null=True, blank=True)
    aceita_resposta = models.CharField(max_length=80, blank=True)  # destino de recebimento
    resposta_ate = models.DateTimeField(null=True, blank=True)
    em_resposta_a = models.ForeignKey("Recebimento", on_delete=models.PROTECT, null=True,
                                      blank=True, related_name="respostas")
    simular = models.CharField(max_length=12, blank=True)  # só o adaptador simulado lê
    aprovada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    aprovada_em = models.DateTimeField(null=True, blank=True)
    criada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name="+")
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["canal", "mensagem_id"],
                                    condition=~Q(mensagem_id=""),
                                    name="comunicacao_mensagem_unica"),
        ]
        indexes = [
            models.Index(fields=["situacao", "proxima_tentativa_em"],
                         name="comunicacao_fila_idx"),
            models.Index(fields=["recurso", "tipo"], name="comunicacao_recurso_idx"),
        ]

    def __str__(self) -> str:
        return f"Comunicação #{self.pk}"

    @property
    def tom(self) -> str:
        if self.situacao in (self.Situacao.FALHOU, self.Situacao.INCERTA,
                             self.Situacao.RECUSADA):
            return "perigo" if self.situacao != self.Situacao.RECUSADA else "aviso"
        if self.situacao in (self.Situacao.ENVIADA, self.Situacao.MANUAL):
            return "sucesso"
        if self.situacao in self.PENDENTES:
            return "info"
        return "neutro"


class ConteudoComunicacao(models.Model):
    """O texto que saiu (ou sairia). Sem trilha e com retenção: depois do prazo fica só o
    registro de que houve a mensagem."""

    comunicacao = models.OneToOneField(Comunicacao, on_delete=models.CASCADE,
                                       related_name="conteudo")
    texto = models.TextField(max_length=4096)
    modelo = models.CharField(max_length=120, blank=True)
    parametros = models.JSONField(default=list, blank=True)
    expira_em = models.DateTimeField(db_index=True)  # limpeza

    def __str__(self) -> str:
        return f"Conteúdo da comunicação #{self.comunicacao_id}"


class TentativaEntrega(models.Model):
    """Uma ida ao canal. A chave é única por tentativa: repetir o registro do resultado não
    duplica nada; uma tentativa nova sempre tem chave nova."""

    class Resultado(models.TextChoices):
        EM_CURSO = "", "Em curso"
        ACEITA = "aceita", "Aceita"
        TEMPORARIA = "temporaria", "Falha temporária"
        DEFINITIVA = "definitiva", "Falha definitiva"
        INCERTA = "incerta", "Resultado desconhecido"

    comunicacao = models.ForeignKey(Comunicacao, on_delete=models.PROTECT,
                                    related_name="tentativas_entrega")
    numero = models.PositiveSmallIntegerField()
    chave = models.CharField(max_length=200, unique=True)
    reserva_token_hash = models.CharField(max_length=64, blank=True)  # reserva pela API (n8n)
    reservas_anteriores = models.JSONField(default=list, blank=True)  # repetições da reserva
    adaptador = models.CharField(max_length=20)
    iniciada_em = models.DateTimeField(default=timezone.now, db_index=True)  # limite/h
    terminada_em = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(max_length=12, choices=Resultado.choices, blank=True,
                                 default="")
    codigo_erro = models.CharField(max_length=40, blank=True)
    detalhe = models.CharField(max_length=255, blank=True)
    duracao_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["comunicacao_id", "numero"]
        constraints = [models.UniqueConstraint(fields=["comunicacao", "numero"],
                                               name="tentativa_numero_unico")]

    def __str__(self) -> str:
        return f"Tentativa {self.numero} da comunicação #{self.comunicacao_id}"


class StatusEntrega(models.Model):
    """Cada status que o provedor informou, deduplicado por (mensagem, status). O que vale
    para a tela é `Comunicacao.entrega`, que nunca regride."""

    canal = models.CharField(max_length=20, choices=CANAIS, default=CANAL_WHATSAPP)
    mensagem_id = models.CharField(max_length=300)
    status = models.CharField(max_length=12)
    comunicacao = models.ForeignKey(Comunicacao, on_delete=models.PROTECT, null=True,
                                    blank=True, related_name="status_entrega")
    ocorrido_em = models.DateTimeField(null=True, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)
    codigo_erro = models.CharField(max_length=40, blank=True)
    detalhe = models.CharField(max_length=255, blank=True)
    categoria_preco = models.CharField(max_length=40, blank=True)
    tipo_preco = models.CharField(max_length=40, blank=True)
    cobravel = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["ocorrido_em", "id"]
        constraints = [models.UniqueConstraint(fields=["canal", "mensagem_id", "status"],
                                               name="status_entrega_unico")]

    def __str__(self) -> str:
        return f"{self.status} ({self.mensagem_id})"


class EntradaWebhook(models.Model):
    """O corpo bruto que chegou (a Meta não tem histórico de webhooks): gravado antes do
    200, processado depois pelo worker. Sem trilha; o corpo é apagado após a retenção."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PROCESSANDO = "processando", "Processando"
        PROCESSADA = "processada", "Processada"
        ERRO = "erro", "Erro"

    canal = models.CharField(max_length=20, choices=CANAIS, default=CANAL_WHATSAPP)
    sha256 = models.CharField(max_length=64)
    corpo = models.BinaryField()
    origem = models.CharField(max_length=12, default="meta")  # meta | simulador
    situacao = models.CharField(max_length=12, choices=Situacao.choices,
                                default=Situacao.PENDENTE)
    tentativas = models.PositiveSmallIntegerField(default=0)
    recebida_em = models.DateTimeField(auto_now_add=True)
    iniciada_em = models.DateTimeField(null=True, blank=True)
    processada_em = models.DateTimeField(null=True, blank=True)
    erro = models.CharField(max_length=255, blank=True)
    resumo = models.CharField(max_length=120, blank=True)  # "2 status, 1 mensagem"

    class Meta:
        ordering = ["-recebida_em", "-id"]
        constraints = [models.UniqueConstraint(fields=["canal", "sha256"],
                                               name="entrada_webhook_unica")]
        indexes = [models.Index(fields=["situacao", "recebida_em"], name="entrada_fila_idx")]

    def __str__(self) -> str:
        return f"Entrada de webhook #{self.pk}"


class Recebimento(models.Model):
    """Uma mensagem (ou arquivo) que chegou pelo canal. Os estados são distintos de
    propósito: recebido ≠ identificado ≠ associado ≠ conferido — e nada disso é a prestação
    finalizada, que continua sendo um ato de uma pessoa em Viagens."""

    class Situacao(models.TextChoices):
        RECEBIDO = "recebido", "Recebido"
        IDENTIFICADO = "identificado", "Remetente identificado"
        ASSOCIADO = "associado", "Associado ao registro"
        CONFERIDO = "conferido", "Conferido por uma pessoa"
        ENCAMINHADO = "encaminhado", "Encaminhado à equipe"
        QUARENTENA = "quarentena", "Em quarentena"
        RECUSADO = "recusado", "Recusado"
        DESCARTADO = "descartado", "Descartado"
        RESPONDIDO = "respondido", "Respondido automaticamente"

    class Tipo(models.TextChoices):
        TEXTO = "texto", "Texto"
        DOCUMENTO = "documento", "Documento"
        IMAGEM = "imagem", "Imagem"
        BOTAO = "botao", "Botão de resposta"
        OUTRO = "outro", "Outro (não tratado)"

    canal = models.CharField(max_length=20, choices=CANAIS, default=CANAL_WHATSAPP)
    mensagem_id = models.CharField(max_length=300)
    indice = models.PositiveSmallIntegerField(default=0)
    chave = models.CharField(max_length=200, unique=True)  # receb:<canal>:<wamid>:<indice>
    entrada = models.ForeignKey(EntradaWebhook, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="recebimentos")
    remetente_hash = models.CharField(max_length=64, blank=True)
    remetente_final = models.CharField(max_length=4, blank=True)
    contato = models.ForeignKey(ContatoVerificado, on_delete=models.PROTECT, null=True,
                                blank=True, related_name="recebimentos")
    servidor = models.ForeignKey("cadastros.Servidor", on_delete=models.PROTECT, null=True,
                                 blank=True, related_name="recebimentos_automacao")
    unidade = models.ForeignKey("cadastros.Unidade", on_delete=models.PROTECT, null=True,
                                blank=True, related_name="+")
    comunicacao = models.ForeignKey(Comunicacao, on_delete=models.PROTECT, null=True,
                                    blank=True, related_name="recebimentos")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    intencao = models.CharField(max_length=12, blank=True)  # sair | aceito | ajuda
    midia_id = models.CharField(max_length=128, blank=True)
    mime = models.CharField(max_length=100, blank=True)
    tamanho = models.PositiveIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    nome_arquivo = models.CharField(max_length=120, blank=True)
    arquivo = models.FileField(upload_to="automacao/recebidos/%Y/%m/", blank=True)
    situacao = models.CharField(max_length=14, choices=Situacao.choices,
                                default=Situacao.RECEBIDO)
    motivo = models.CharField(max_length=255, blank=True)
    destino = models.CharField(max_length=80, blank=True)     # "viagens.comprovante"
    referencia = models.CharField(max_length=80, blank=True)  # "viagens.anexoprestacao:77"
    em_resposta_a = models.CharField(max_length=300, blank=True)  # context.id (nosso wamid)
    tentativas = models.PositiveSmallIntegerField(default=0)
    reservado_ate = models.DateTimeField(null=True, blank=True)  # lease do download
    recebido_em = models.DateTimeField(null=True, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)
    identificado_em = models.DateTimeField(null=True, blank=True)
    associado_em = models.DateTimeField(null=True, blank=True)
    associado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      null=True, blank=True, related_name="+")
    assinatura_detectada_em = models.DateTimeField(null=True, blank=True)
    conferido_em = models.DateTimeField(null=True, blank=True)
    conferido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-registrado_em", "-id"]
        indexes = [models.Index(fields=["situacao", "registrado_em"],
                                name="recebimento_situacao_idx")]

    def __str__(self) -> str:
        return f"Recebimento #{self.pk}"

    @property
    def tom(self) -> str:
        if self.situacao in (self.Situacao.QUARENTENA, self.Situacao.RECUSADO):
            return "perigo"
        if self.situacao in (self.Situacao.ASSOCIADO, self.Situacao.CONFERIDO,
                             self.Situacao.RESPONDIDO):
            return "sucesso"
        if self.situacao == self.Situacao.ENCAMINHADO:
            return "aviso"
        return "info" if self.situacao != self.Situacao.DESCARTADO else "neutro"


class ConteudoRecebimento(models.Model):
    """Texto/legenda, nome de perfil e nome original do arquivo (escolhido por quem mandou):
    sem trilha, com retenção."""

    recebimento = models.OneToOneField(Recebimento, on_delete=models.CASCADE,
                                       related_name="conteudo")
    texto = models.TextField(max_length=4096, blank=True)
    nome_original = models.CharField(max_length=255, blank=True)
    nome_perfil = models.CharField(max_length=120, blank=True)
    expira_em = models.DateTimeField(db_index=True)  # limpeza

    def __str__(self) -> str:
        return f"Conteúdo do recebimento #{self.recebimento_id}"


class ExcecaoAutomacao(models.Model):
    """O que a automação não resolve sozinha: vai para uma pessoa, com as ações possíveis."""

    class Tipo(models.TextChoices):
        RESULTADO_INCERTO = "resultado_incerto", "Não se sabe se a mensagem saiu"
        FALHA_DEFINITIVA = "falha_definitiva", "Mensagem não saiu"
        CONTATO = "contato", "Contato sem verificação, opt-in ou fora da lista"
        CANAL = "canal", "Problema na conta ou na credencial do canal"
        REMETENTE_DESCONHECIDO = "remetente_desconhecido", "Mensagem de número desconhecido"
        ARQUIVO_RECUSADO = "arquivo_recusado", "Arquivo recusado"
        ASSOCIACAO = "associacao", "Arquivo sem destino certo"
        PERMISSAO = "permissao", "Quem originou a comunicação não pode mais agir"
        ATENDIMENTO = "atendimento", "Mensagem para a equipe responder"
        STATUS_ORFAO = "status_orfao", "Status de mensagem desconhecida"

    class Situacao(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        RESOLVIDA = "resolvida", "Resolvida"
        DESCARTADA = "descartada", "Descartada"

    tipo = models.CharField(max_length=24, choices=Tipo.choices)
    chave = models.CharField(max_length=200, unique=True)
    situacao = models.CharField(max_length=12, choices=Situacao.choices,
                                default=Situacao.ABERTA)
    resumo = models.CharField(max_length=255)
    comunicacao = models.ForeignKey(Comunicacao, on_delete=models.PROTECT, null=True,
                                    blank=True, related_name="excecoes")
    recebimento = models.ForeignKey(Recebimento, on_delete=models.PROTECT, null=True,
                                    blank=True, related_name="excecoes")
    unidade = models.ForeignKey("cadastros.Unidade", on_delete=models.PROTECT, null=True,
                                blank=True, related_name="+")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name="+")
    assumida_em = models.DateTimeField(null=True, blank=True)
    resolucao = models.CharField(max_length=255, blank=True)
    resolvida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      null=True, blank=True, related_name="+")
    resolvida_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em", "-id"]
        indexes = [models.Index(fields=["situacao", "criada_em"], name="excecao_fila_idx")]

    def __str__(self) -> str:
        return f"Exceção #{self.pk}"


class LinkAcesso(models.Model):
    """Link pessoal sem login (km na véspera, documentos, assinatura, relato, situação):
    escopo e recurso fixos, token só em hash, validade curta, revogável (ver links.py)."""

    class Escopo(models.TextChoices):
        KM = "km", "Lançar a quilometragem"
        DOCUMENTOS = "documentos", "Documentos disponíveis"
        ASSINATURA = "assinatura", "Documentos para assinatura"
        RELATO = "relato", "Relato da viagem"
        SITUACAO = "situacao", "Minha situação"

    class Origem(models.TextChoices):
        AUTOMATICA = "automatica", "Automática"
        MANUAL = "manual", "Manual"

    class Motivo(models.TextChoices):
        LINK_NOVO = "link_novo", "Um link novo substituiu este"
        RESPONSAVEL_TROCADO = "responsavel_trocado", "O responsável mudou"
        OFICIO_CANCELADO = "oficio_cancelado", "O ofício foi cancelado"
        VAZAMENTO = "vazamento", "Incidente (revogação em massa)"
        MANUAL = "manual", "Revogado por uma pessoa"

    escopo = models.CharField(max_length=12, choices=Escopo.choices)
    recurso = models.CharField(max_length=80)  # "viagens.diario:204"
    servidor = models.ForeignKey("cadastros.Servidor", on_delete=models.PROTECT,
                                 related_name="links_acesso")
    contato = models.ForeignKey(ContatoVerificado, on_delete=models.PROTECT, null=True,
                                blank=True, related_name="links")
    comunicacao = models.ForeignKey(Comunicacao, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="links")
    token_hash = models.CharField(max_length=64, unique=True)
    origem = models.CharField(max_length=12, choices=Origem.choices)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    revogado_em = models.DateTimeField(null=True, blank=True)
    revogado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    motivo_revogacao = models.CharField(max_length=20, choices=Motivo.choices, blank=True)
    exibido_em = models.DateTimeField(null=True, blank=True)
    usado_em = models.DateTimeField(null=True, blank=True)
    primeiro_lancamento_em = models.DateTimeField(null=True, blank=True)
    ultimo_lancamento_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["recurso", "escopo"], name="link_recurso_idx")]

    def __str__(self) -> str:
        return f"Link #{self.pk} ({self.get_escopo_display()})"

    @property
    def vigente(self) -> bool:
        return self.revogado_em is None and self.expira_em > timezone.now()


class ContadorDeLimite(models.Model):
    """Janela fixa de um limite de uso das páginas públicas (ex.: gravações por link de km),
    no banco: vale entre os workers do gunicorn e as réplicas (o cache local de cada processo
    não valia). Atualizado só por `limites.exceder` (upsert atômico); sem trilha de auditoria
    (é contador, não estado de negócio) e apagado pela retenção."""

    chave = models.CharField(max_length=120, unique=True)
    inicio = models.DateTimeField()
    total = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.chave}: {self.total}"


from .models_api import (  # noqa: E402, F401  (os modelos da API entram no app)
    CredencialIntegracao,
    Delegacao,
    EventoIntegracao,
    ExecucaoFerramenta,
    PedidoAprovacao,
    RegistroIdempotencia,
)
