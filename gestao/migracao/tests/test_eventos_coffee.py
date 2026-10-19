"""Etapas de eventos e de coffee break com um banco legado FALSO (só dados sintéticos)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse

from gestao.cadastros.models import AtividadePlano, Municipio
from gestao.coffee import queries
from gestao.coffee.models import ConfiguracaoOficio, Lote
from gestao.coffee.models import Movimento as MovimentoCoffee
from gestao.coffee.models import Solicitacao as OS
from gestao.eventos.models import (
    Equipe,
    Lembrete,
    Movimento,
    ServicoLegado,
    Solicitacao,
    SolicitacaoEquipe,
    SolicitacaoServico,
)
from gestao.identidade.models import Usuario
from gestao.migracao.contexto import Contexto, Relatorio
from gestao.migracao.etapas import cadastros, coffee, eventos
from gestao.migracao.models import MapaLegado
from gestao.plataforma.models import Notificacao

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


class FonteFalsa:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def tabela(self, nome: str) -> list[dict]:
        return [dict(r) for r in self.tabelas.get(nome, [])]

    def tem_tabela(self, nome: str) -> bool:
        return nome in self.tabelas


def _mapear(tabela: str, pk: int, obj) -> None:
    MapaLegado.objects.create(sistema="ev", tabela=tabela, origem_pk=str(pk),
                              modelo=f"{obj._meta.app_label}.{obj.__class__.__name__}",
                              destino_pk=str(obj.pk), lote="cadastros")


def _municipio(nome: str, ibge: str) -> Municipio:
    m, _ = Municipio.objects.get_or_create(codigo_ibge=ibge, defaults={"nome": nome, "uf": "PR"})
    return m


@pytest.fixture
def base():
    """O que a etapa de cadastros deixaria: usuário, municípios, serviço e equipe mapeados."""
    u = Usuario.objects.create_user("legado.sintetico", "legado@teste.invalid", None,
                                    nome="Pessoa sintética")
    alfa = _municipio("Alfaville Sintética", "9900001")
    beta = _municipio("Betânia Sintética", "9900002")
    beta_sul = _municipio("Betânia Sintética do Sul", "9900003")
    atividade = AtividadePlano.objects.create(codigo="SINTETICA_A", nome="Serviço canônico")
    equipe = Equipe.objects.create(nome="Equipe sintética")
    for tabela, pk, obj in (("accounts_user", 1, u), ("cadastros_municipio", 501, alfa),
                            ("cadastros_municipio", 502, beta),
                            ("cadastros_municipio", 503, beta_sul),
                            ("cadastros_servico", 8, atividade), ("cadastros_equipe", 3, equipe)):
        _mapear(tabela, pk, obj)
    return {"u": u, "alfa": alfa, "beta": beta, "beta_sul": beta_sul, "atividade": atividade,
            "equipe": equipe}


def sol_evento(pk: int, status: str, decisao: str, **extra) -> dict:
    return {"id": pk, "status": status, "decisao_dg": decisao, "tipo_operacao": "DIARIA",
            "data_solicitacao": date(2026, 9, 1), "data_inicio_evento": date(2026, 9, 10),
            "data_fim_evento": date(2026, 9, 10), "municipio_id": 501, "tipo_evento_id": None,
            "orgao_responsavel_id": None, "regiao_id": None, "unidade_movel": False,
            "unidade_movel_designada_id": None, "solicitante_nome": "Solicitante sintético",
            "solicitante_cargo_unidade": "", "contato": "", "local_evento": "Local sintético",
            "endereco": "", "bairro": "", "cep": "", "protocolo": "",
            "descricao_complementar": "", "quantidade_servidores": 2, "quantidade_cin": None,
            "motorista_id": None, "observacoes_dg": "", "decidido_por_id": 1,
            "decidido_em": T0, "criado_por_id": 1, "criado_em": T0, "atualizado_em": T1,
            **extra}


def historico(pk: int, acao: str, alteracoes=None, **extra) -> dict:
    return {"id": pk, "acao": acao, "status_anterior": "", "status_novo": "", "observacao": "",
            "alteracoes": alteracoes or [], "usuario_id": 1, "solicitacao_id": 103,
            "criado_em": T0, **extra}


def notificacao(pk: int, link: str, solicitacao_id: int | None, titulo: str) -> dict:
    return {"id": pk, "titulo": titulo, "mensagem": "", "link": link, "lida": False,
            "usuario_id": 1, "solicitacao_id": solicitacao_id, "criada_em": T0}


def os_legado(pk: int, lote: int, numero: str, **extra) -> dict:
    vazio = dict.fromkeys((
        "periodo_evento_texto", "numero_nota_fiscal", "protocolo_pagamento", "observacoes",
        "motivo_cancelamento", "arquivo_nota_fiscal", "detalhamento_pedido", "local_entrega",
        "responsavel_recebimento", "numero_oficio", "protocolo_pcpr_oficio",
        "cnpj_emitente_nf", "arquivo_ordem_bancaria", "numero_ordem_bancaria", "bairro", "cep",
        "endereco"), "")
    nulos = dict.fromkeys((
        "data_fim_evento", "data_atesto_gaf", "data_ordem_bancaria", "data_envio_empresa",
        "cancelada_em", "cancelada_por_id", "data_envio_ordem_servico", "horario_evento",
        "municipio_id", "data_oficio", "pagamento_com_id", "quantidade_faturada",
        "valor_unitario", "data_emissao_nf", "valor_nota_fiscal", "valor_ordem_bancaria",
        "demanda_evento_id", "solicitacao_evento_id"))
    return {**vazio, **nulos, "id": pk, "lote_id": lote, "numero": numero,
            "data_solicitacao": date(2025, 3, 1), "data_inicio_evento": date(2025, 3, 10),
            "descricao_evento": "Evento sintético", "quantidade": 30, "cancelada": False,
            "em_correcao": False, "criado_por_id": 1, "criado_em": T0, "atualizado_em": T1,
            **extra}


def lote(pk: int, numero: int) -> dict:
    return {"id": pk, "numero": numero, "exercicio": "2025", "quantidade_total": 500,
            "empenho": "", "municipios_texto": "", "orientacoes": "",
            "especificacoes_tecnicas": "", "observacoes": "", "ativo": False,
            "criado_em": T0, "atualizado_em": T1, "contrato_id": 6, "valor_empenho": None}


def legado() -> dict[str, list[dict]]:
    return {
        "cadastros_servico": [{"id": 8, "nome": "Serviço do legado (grafia antiga)",
                               "ativo": True, "criado_em": T0, "atualizado_em": T0}],
        "solicitacoes_solicitacaoevento": [
            sol_evento(103, "DEFERIDA_EM_ANDAMENTO", "ATENDER"),
            sol_evento(104, "NAO_ATENDIDA", "PENDENTE", quantidade_servidores=None,
                       decidido_por_id=None, decidido_em=None)],
        "solicitacoes_solicitacaoeventoservico": [
            {"id": 1, "solicitacao_id": 103, "servico_id": 8, "observacao": ""}],
        "solicitacoes_solicitacaoeventoequipe": [
            {"id": 1, "solicitacao_id": 103, "equipe_id": 3, "quantidade_servidores": 2,
             "observacao": ""}],
        "solicitacoes_anexosolicitacao": [],
        "solicitacoes_historicosolicitacao": [
            historico(1, "IMPORTACAO", observacao="Importada"),
            historico(2, "ATUALIZACAO", [{"campo": "local_evento", "antes": "A",
                                          "depois": "B"},
                                         {"campo": "contato", "antes": "", "depois": "C"}]),
            historico(3, "DECISAO", status_anterior="AGUARDANDO_DESPACHO",
                      status_novo="DEFERIDA_EM_ANDAMENTO")],
        "solicitacoes_lembretesolicitacao": [
            {"id": 1, "tipo": "CONFIRMAR_ATENDIMENTO", "referencia": date(2026, 9, 10),
             "enviado_em": T1, "solicitacao_id": 103}],
        "viagens_viagem_viagem_solicitacoes_juntadas": [],
        "viagens_viagem_viagem": [],
        "core_notificacao": [
            notificacao(1, "/solicitacoes/103/editar/#encerramento", 103,
                        "Solicitação #103: confirme o atendimento"),
            notificacao(2, "/solicitacoes/104/editar/", 104, "Solicitação #104 devolvida"),
            notificacao(3, "/", None, "Resumo de hoje (1/2): o que está pendente"),
            notificacao(4, "", None, "Limpeza semanal de arquivos")],
        "coffee_break_fornecedor": [
            {"id": 1, "razao_social": "Buffet Sintético Ltda", "cnpj": "11222333000181",
             "contato": "", "telefone": "", "email": "", "url_certidao_municipal": "",
             "nome_curto": "", "criado_em": T0, "atualizado_em": T1}],
        "coffee_break_contratocoffeebreak": [
            {"id": 6, "numero": "10/2025", "numero_gms": "", "termo_aditivo": "",
             "fiscal_responsavel": "", "objeto": "", "observacoes": "", "criado_em": T0,
             "atualizado_em": T1, "fornecedor_id": 1, "arquivo_contrato": "",
             "arquivo_termo_aditivo": "", "cargo_fiscal": "", "clausula_pagamento": "",
             "quantidade_contratada": None, "valor_total": None,
             "valor_unitario": Decimal("21.07"), "vigencia_estimada": False,
             "vigencia_fim": None, "vigencia_inicio": None, "antecedencia_minima_dias": 2}],
        "coffee_break_aditivocontrato": [],
        "coffee_break_certidaofornecedor": [],
        "coffee_break_lotecoffeebreak": [lote(10, 1), lote(11, 2)],
        "coffee_break_lotecoffeebreak_municipios": [
            {"id": 1, "lotecoffeebreak_id": 10, "municipio_id": 501},
            {"id": 2, "lotecoffeebreak_id": 10, "municipio_id": 502},
            {"id": 3, "lotecoffeebreak_id": 10, "municipio_id": 503},
            {"id": 4, "lotecoffeebreak_id": 11, "municipio_id": 501}],
        "coffee_break_configuracaocoffeebreak": [
            {"id": 1, "oficio_vocativo": "Vocativo sintético,", "oficio_assinante": "",
             "oficio_cargo_assinante": "", "oficio_destinatario": "",
             "eprotocolo_assunto": "LICITACAO", "eprotocolo_palavras_chave": "",
             "despacho_destino": "Ao GAF,", "atualizado_em": T1, "email_copia": "",
             "email_os_assunto": "OS {numero}", "email_os_texto": "Texto {evento}",
             "email_ob_assunto": "OB {numero}", "email_ob_texto": "Texto {nota}"}],
        "coffee_break_solicitacaocoffeebreak": [
            # Mesmo número em lotes diferentes (G1) e o zero à esquerda (G14).
            os_legado(170, 10, "01/2025", local_entrega="Ginásio de Alfaville Sintética"),
            os_legado(171, 11, "1/2025", local_entrega="Praça central"),
            # Dois municípios do lote no texto: ambíguo.
            os_legado(172, 10, "2/2025", local_entrega="Centro de Betânia Sintética do Sul"),
            os_legado(173, 10, "3/2025", municipio_id=502, pagamento_com_id=170,
                      data_fim_evento=date(2025, 3, 11), periodo_evento_texto="dois dias",
                      observacoes="Observação original", horario_evento=time(9, 30))],
        "coffee_break_historicocoffeebreak": [
            {"id": 1, "acao": "CRIACAO", "descricao": "Criada", "criado_em": T0,
             "solicitacao_id": 170, "usuario_id": 1},
            {"id": 2, "acao": "ATUALIZACAO", "descricao": "Atualizada", "criado_em": T1,
             "solicitacao_id": 173, "usuario_id": None}],
        "coffee_break_linkfornecedor": [], "coffee_break_enviofornecedor": [],
        "coffee_break_ocorrenciaentrega": [],
    }


def rodar(ev: dict) -> Relatorio:
    ctx = Contexto(ev=FonteFalsa(ev), gv=None, lote="teste", relatorio=Relatorio())
    cadastros.garantir_usuario_migracao(ctx)
    eventos.executar(ctx)
    coffee.executar(ctx)
    return ctx.relatorio


def _auditoria() -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM auditoria_evento")
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------- regras puras
def test_municipio_pelo_texto_um_ambiguo_e_nenhum():
    candidatos = {1: "Alfaville", 2: "Betânia", 3: "Betânia do Sul"}
    assert coffee.municipios_no_texto(["Ginásio de ALFAVILLE", None], candidatos) == [1]
    assert coffee.municipios_no_texto(["", "praça de betania do sul"], candidatos) == [2, 3]
    assert coffee.municipios_no_texto(["Praça central", ""], candidatos) == []


def test_numero_sem_zero_a_esquerda():
    assert coffee.normalizar_numero("01/2025", 2026) == "1/2025"
    assert coffee.normalizar_numero(" 41/2026 ", 2026) == "41/2026"
    assert coffee.normalizar_numero("", 2026) == ""
    assert coffee.normalizar_numero("S/N", 2026) == "S/N"


def test_periodo_original_e_diff_do_movimento():
    assert coffee.periodo_original(date(2025, 3, 10), date(2025, 3, 11), "dois dias") == (
        "Período original: 10/03/2025 a 11/03/2025; dois dias")
    assert coffee.periodo_original(date(2025, 3, 10), date(2025, 3, 10), "") == ""
    assert eventos.diff_em_texto([{"campo": "a", "antes": "", "depois": "x"}]) == "a: — → x"
    assert eventos.observacao_movimento("Obs", []) == "Obs"


def test_link_do_legado_reescrito():
    def destino(pk):
        return {"103": 103}.get(pk)
    assert eventos.reescrever_link("/solicitacoes/103/editar/#encerramento", destino) == (
        reverse("eventos:solicitacao", args=[103]) + "#encerramento", True)
    assert eventos.reescrever_link("/solicitacoes/999/editar/", destino) == ("", False)
    assert eventos.reescrever_link("/", destino) == ("/", False)
    assert eventos.reescrever_link("", destino) == ("", False)


# ---------------------------------------------------------------------------- etapas
def test_eventos_com_ids_servicos_movimentos_e_notificacoes(base):
    rel = rodar(legado())
    s = Solicitacao.objects.get(pk=103)                      # id do legado preservado
    assert s.status == "deferida" and s.decisao_dg == "atender"
    assert Solicitacao.objects.get(pk=104).quantidade_servidores == 0      # G11
    ss = SolicitacaoServico.objects.get(solicitacao=s)
    assert ss.servico == base["atividade"]
    assert ss.nome_registrado == "Serviço do legado (grafia antiga)"
    assert SolicitacaoEquipe.objects.get(solicitacao=s).quantidade_servidores == 2
    # G6: as ações novas; a lista de campos alterados vai para a observação.
    acoes = dict(Movimento.objects.values_list("acao", "observacao"))
    assert set(acoes) == {"importacao", "atualizacao", "decisao"}
    assert acoes["atualizacao"] == "local_evento: A → B\ncontato: — → C"
    assert Movimento.objects.get(acao="decisao").status_novo == "deferida"
    assert Movimento.objects.get(acao="importacao").get_acao_display() == "Importada da planilha"
    assert Lembrete.objects.get().enviado_em == T1
    # G7: as notificações de solicitação, com o link novo; os resumos ficam de fora.
    links = sorted(Notificacao.objects.values_list("link", flat=True))
    assert links == sorted([reverse("eventos:solicitacao", args=[103]) + "#encerramento",
                            reverse("eventos:solicitacao", args=[104])])
    assert rel.contagens["notificacao"] == {"criado": 2, "link_reescrito": 2,
                                            "resumo_ignorado": 2}
    assert ServicoLegado.objects.get(criterio="importacao_ev").vinculos_originais == {
        "ev_id": 8, "solicitacoes": [103]}
    # G10: incoerências vêm como estão e vão para a conferência.
    motivos = {(i["origem_pk"], i["motivo"]) for i in rel.conferir}
    assert ("104", "status e decisão da DG incoerentes (herdado do legado)") in motivos
    assert ("104", "total de servidores vazio no legado: entrou 0") in motivos
    # A sequência continua depois do maior id do legado.
    nova = Solicitacao.objects.create(data_solicitacao=date(2026, 10, 1),
                                      criado_por=base["u"])
    assert nova.pk > 104


def test_coffee_numero_por_lote_e_municipio(base):
    rel = rodar(legado())
    a, b = OS.objects.get(pk=170), OS.objects.get(pk=171)
    assert a.numero == b.numero == "1/2025" and a.lote_id != b.lote_id      # G1 + G14
    assert queries.proximo_numero(2025, a.lote) == "4/2025"
    assert queries.proximo_numero(2025, b.lote) == "2/2025"
    # G2: um só município do lote no texto → preenchido, com nota.
    assert a.municipio == base["alfa"] and "Município preenchido na migração" in a.observacoes
    assert b.municipio is None and b.municipio_nome == "município não informado"
    assert OS.objects.get(pk=172).municipio is None                        # ambíguo
    motivos = {i["origem_pk"]: i["motivo"] for i in rel.conferir
               if i["entidade"] == "solicitacao_coffee"}
    assert motivos["172"].startswith("sem município no legado; 2 municípios do lote")
    assert motivos["171"].startswith("sem município no legado e nenhum")
    c = OS.objects.get(pk=173)
    assert c.municipio == base["beta"] and c.pagamento_com_id == 170
    assert c.observacoes == ("Observação original\n\nPeríodo original: 10/03/2025 a "
                             "11/03/2025; dois dias")
    assert c.horario == time(9, 30) and c.valor_unitario is None
    assert Lote.objects.get(pk=a.lote_id).municipios.count() == 3
    assert ConfiguracaoOficio.objects.count() == 1
    assert ConfiguracaoOficio.atual().vocativo == "Vocativo sintético,"
    assert set(MovimentoCoffee.objects.values_list("acao", flat=True)) == {"criada",
                                                                           "atualizada"}
    assert MovimentoCoffee.objects.get(acao="atualizada").usuario is None


def test_rodar_duas_vezes_nao_cria_nem_altera_nada(base):
    rodar(legado())
    contagens = (Solicitacao.objects.count(), Movimento.objects.count(), OS.objects.count(),
                 Notificacao.objects.count(), ServicoLegado.objects.count(),
                 MapaLegado.objects.count(), ConfiguracaoOficio.objects.count())
    auditoria = _auditoria()
    rel = rodar(legado())
    assert (Solicitacao.objects.count(), Movimento.objects.count(), OS.objects.count(),
            Notificacao.objects.count(), ServicoLegado.objects.count(),
            MapaLegado.objects.count(), ConfiguracaoOficio.objects.count()) == contagens
    assert _auditoria() == auditoria
    assert not any("criado" in n for n in rel.contagens.get("solicitacao_coffee", {}))
    assert rel.contagens["solicitacao_evento"]["ja_mapeado"] == 2
    assert rel.conferir == []
