"""Etapas de viagens e de prestação com bancos legados FALSOS (só dados sintéticos)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from django.db import connection

from gestao.migracao.contexto import Contexto, Relatorio
from gestao.migracao.etapas import cadastros, prestacao, viagens
from gestao.migracao.etapas.comum import impressao, json_legado
from gestao.migracao.models import MapaLegado
from gestao.viagens.models import (
    Historico,
    Oficio,
    OrdemServico,
    PrestacaoContas,
    PrestacaoServidor,
    Viagem,
    ViagemDestino,
    Viajante,
)

pytestmark = pytest.mark.django_db

LOTE = datetime(2026, 9, 21, 0, 7, 45, tzinfo=UTC)
ANTES = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
DEPOIS = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
MAIS_DEPOIS = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


class FonteFalsa:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def tabela(self, nome: str) -> list[dict]:
        return [dict(r) for r in self.tabelas.get(nome, [])]

    def tem_tabela(self, nome: str) -> bool:
        return nome in self.tabelas


def oficio_ev(pk: int, numero: int, *, motivo: str = "Motivo sintético", atualizado=ANTES,
              legado: str = "", **extra) -> dict:
    return {"id": pk, "numero": numero, "ano": 2026, "status": "GERADO", "cancelado": False,
            "data_criacao": date(2026, 9, 1), "protocolo": "123456789", "motivo": motivo,
            "custeio": "UNIDADE_DPC", "motorista_modo": "SERVIDOR", "motorista_id": 1,
            "viagem_id": None, "roteiro_id": None, "viatura_id": None,
            "porte_transporte_armas": True, "protocolo_origem": "MANUAL",
            "criado_em": ANTES, "atualizado_em": atualizado, "legado_origem": legado, **extra}


def oficio_gv(pk: int, numero: int, *, motivo: str = "Motivo sintético", atualizado=ANTES,
              **extra) -> dict:
    return {"id": pk, "numero": numero, "ano": 2026, "status": "GERADO", "cancelado": False,
            "data_criacao": date(2026, 9, 1), "protocolo": "987654321", "motivo": motivo,
            "custeio": "UNIDADE_DPC", "motorista_modo": "SERVIDOR", "motorista_id": 71,
            "evento_id": None, "roteiro_id": None, "viatura_id": None,
            "porte_transporte_armas": True, "created_at": ANTES, "updated_at": atualizado,
            "destino_gabinete": None, **extra}


def legados(ev_extra: dict | None = None, gv_extra: dict | None = None) -> tuple[dict, dict]:
    ev: dict[str, list[dict]] = {
        "migracao_legado_lote": [{"id": 1, "criado_em": LOTE, "desfeito_em": None}],
        "migracao_legado_etapa": [{"id": 1, "concluida_em": LOTE}],
        "migracao_legado_registro": [],
        "viagens_oficios_oficio": [], "viagens_oficios_oficio_servidores": [],
    }
    gv: dict[str, list[dict]] = {"oficios_oficio": [], "oficios_oficio_servidores": []}
    for alvo, extra in ((ev, ev_extra), (gv, gv_extra)):
        for k, v in (extra or {}).items():
            alvo.setdefault(k, []).extend(v)
    return ev, gv


def registrar(ev: dict, tabela_gv: str, gv_linha: dict, ev_pk: int, *, mudou: bool = False):
    """A linha do GV que a carga do EV trouxe (com a impressão digital daquele momento)."""
    ev["migracao_legado_registro"].append({
        "tabela": tabela_gv, "origem_pk": str(gv_linha["id"]), "destino_pk": str(ev_pk),
        "fingerprint": "impressao-antiga" if mudou else impressao(gv_linha)})


def rodar(ev: dict, gv: dict, etapas=("viagens",)) -> Relatorio:
    ctx = Contexto(ev=FonteFalsa(ev), gv=FonteFalsa(gv), lote="teste", relatorio=Relatorio())
    cadastros.garantir_usuario_migracao(ctx)
    for etapa in etapas:
        {"viagens": viagens, "prestacao": prestacao}[etapa].executar(ctx)
    return ctx.relatorio


def test_json_com_dupla_codificacao_e_decodificado():
    destinos = [{"cidade": "Cidade", "uf": "PR"}]
    assert json_legado(json.dumps(json.dumps(destinos))) == destinos
    assert json_legado(json.dumps(destinos)) == destinos
    assert json_legado(destinos) == destinos
    assert json_legado("texto qualquer") == "texto qualquer"


def test_destinos_extras_duplamente_codificados_viram_destinos_da_viagem(base):
    m2 = base["m2"]
    extras = json.dumps([{"cidade": m2.nome, "uf": m2.uf}])   # string JSON dentro do jsonb
    ev, gv = legados({"viagens_viagem_viagem": [{
        "id": 1, "titulo": "Viagem sintética", "status": "rascunho", "cancelado": False,
        "destino_municipio_id": 10, "destinos_extras": extras, "unidade_responsavel_id": None,
        "criado_em": ANTES, "atualizado_em": ANTES}]})

    rodar(ev, gv)

    viagem = Viagem.objects.get()
    assert list(ViagemDestino.objects.filter(viagem=viagem).values_list(
        "municipio_id", flat=True)) == [base["m1"].pk, m2.pk]
    assert viagem.criado_em == ANTES


def test_oficio_so_do_gv_com_numero_ocupado_e_renumerado_com_o_antigo_no_historico(base):
    ev, gv = legados(
        {"viagens_oficios_oficio": [oficio_ev(1, 127), oficio_ev(2, 141)],
         "viagens_oficios_oficio_servidores": [{"id": 1, "oficio_id": 1, "servidor_id": 1}]},
        {"oficios_oficio": [oficio_gv(9, 127), oficio_gv(10, 128)],
         "oficios_oficio_servidores": [{"id": 1, "oficio_id": 9, "servidor_id": 72}]})

    relatorio = rodar(ev, gv)

    assert set(Oficio.objects.values_list("numero", flat=True)) == {127, 141, 142, 128}
    renumerado = Oficio.objects.get(numero=142)
    assert renumerado.protocolo == "987654321"
    historico = Historico.objects.get(oficio=renumerado)
    assert historico.dados["numero_anterior"] == 127
    assert "127/2026" in historico.descricao
    assert relatorio.contagens["oficio"]["renumerado"] == 1
    assert any("renumerado para 142/2026" in c["motivo"] for c in relatorio.conferir)
    # 128 do GV não colide: mantém o número.
    assert Oficio.objects.filter(numero=128).count() == 1
    assert Viajante.objects.get(oficio=renumerado).servidor == base["s2"]


@pytest.mark.parametrize(("gv_mais_recente", "motivo_final"),
                         [(True, "Motivo do GV"), (False, "Motivo do EV")])
def test_editado_nos_dois_vale_o_mais_recente_e_o_outro_vai_para_a_conferencia(
        base, gv_mais_recente, motivo_final):
    ev_quando, gv_quando = (DEPOIS, MAIS_DEPOIS) if gv_mais_recente else (MAIS_DEPOIS, DEPOIS)
    gv_linha = oficio_gv(5, 100, motivo="Motivo do GV", atualizado=gv_quando)
    ev, gv = legados(
        {"viagens_oficios_oficio": [oficio_ev(1, 100, motivo="Motivo do EV",
                                              atualizado=ev_quando, protocolo="987654321",
                                              legado="gerenciador_viagens")]},
        {"oficios_oficio": [gv_linha]})
    registrar(ev, "oficios_oficio", gv_linha, 1, mudou=True)

    relatorio = rodar(ev, gv)

    oficio = Oficio.objects.get()
    assert oficio.motivo == motivo_final
    assert relatorio.contagens["oficio"]["editado_nos_dois"] == 1
    [item] = [c for c in relatorio.conferir if "editado nos dois" in c["motivo"]]
    assert item["campos"] == ["motivo"]
    assert (item["ev_pk"], item["gv_pk"]) == (1, 5)
    # As duas linhas de origem apontam para o mesmo ofício.
    alvos = set(MapaLegado.objects.filter(tabela__in=["viagens_oficios_oficio", "oficios_oficio"])
                .values_list("destino_pk", flat=True))
    assert alvos == {str(oficio.pk)}


def test_mudou_so_no_gv_entra_a_versao_do_gv_sem_ir_para_a_conferencia(base):
    gv_linha = oficio_gv(5, 100, motivo="Motivo corrigido no GV", atualizado=DEPOIS)
    ev, gv = legados({"viagens_oficios_oficio": [oficio_ev(
        1, 100, protocolo="987654321", legado="gerenciador_viagens")]},
        {"oficios_oficio": [gv_linha]})
    registrar(ev, "oficios_oficio", gv_linha, 1, mudou=True)

    relatorio = rodar(ev, gv)

    assert Oficio.objects.get().motivo == "Motivo corrigido no GV"
    assert relatorio.contagens["oficio"]["versao_do_gv_mais_recente"] == 1
    assert not any("editado nos dois" in c["motivo"] for c in relatorio.conferir)


def test_os_trazida_do_gv_le_as_funcoes_do_gv(base):
    """A carga do EV gravou as funções da OS com o id do servidor NO GV (e como string JSON):
    a migração lê do GV e traduz."""
    os_gv = {"id": 30, "numero": 7, "ano": 2026, "tipo_necessidade": "MICROONIBUS",
             "funcoes_servidores": {"71": "CONDUCAO", "72": "TECNICO"}, "cancelado": False,
             "evento_id": None, "created_at": ANTES, "updated_at": ANTES}
    os_ev = {"id": 3, "numero": 7, "ano": 2026, "tipo_necessidade": "MICROONIBUS",
             "funcoes_servidores": json.dumps({"71": "CONDUCAO", "72": "TECNICO"}),
             "cancelado": False, "viagem_id": None, "legado_origem": "gerenciador_viagens",
             "criado_em": ANTES, "atualizado_em": ANTES}
    ev, gv = legados({"viagens_ordens_ordemservico": [os_ev]},
                     {"ordens_servico_ordemservico": [os_gv]})
    registrar(ev, "ordens_servico_ordemservico", os_gv, 3)

    rodar(ev, gv)

    assert OrdemServico.objects.get().funcoes == {str(base["s1"].pk): "conducao",
                                                  str(base["s2"].pk): "tecnico"}


def _contar_auditoria() -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM auditoria_evento")
        return cur.fetchone()[0]


def test_rodar_duas_vezes_nao_cria_nem_altera_nada(base):
    gv_mudado = oficio_gv(5, 100, motivo="Motivo do GV", atualizado=MAIS_DEPOIS)
    prest_gv = {"id": 50, "oficio_id": 5, "observacoes": "", "roteiro_ajustado_id": None,
                "criado_em": ANTES, "atualizado_em": ANTES}
    ps_gv = {"id": 60, "prestacao_id": 50, "servidor_id": 71, "numero_solicitacao": "1234567",
             "status": "em_preenchimento", "arquivada": False, "finalizada": False,
             "criado_em": ANTES, "atualizado_em": MAIS_DEPOIS}
    ev, gv = legados(
        {"viagens_oficios_oficio": [
            oficio_ev(1, 100, atualizado=DEPOIS, protocolo="987654321",
                      legado="gerenciador_viagens"),
            oficio_ev(2, 127)],
         "viagens_oficios_oficio_servidores": [{"id": 1, "oficio_id": 1, "servidor_id": 1}],
         "viagens_prestacoes_prestacaocontas": [
             {"id": 500, "oficio_id": 1, "observacoes": "", "roteiro_ajustado_id": None,
              "criado_em": ANTES, "atualizado_em": ANTES}],
         "viagens_prestacoes_prestacaoservidor": [
             {"id": 600, "prestacao_id": 500, "servidor_id": 1, "numero_solicitacao": "",
              "status": "pendente", "arquivada": False, "finalizada": False,
              "criado_em": ANTES, "atualizado_em": DEPOIS}]},
        {"oficios_oficio": [gv_mudado, oficio_gv(9, 127)],
         "oficios_oficio_servidores": [{"id": 1, "oficio_id": 5, "servidor_id": 71}],
         "prestacoes_contas_prestacaocontas": [prest_gv],
         "prestacoes_contas_prestacaoservidor": [ps_gv]})
    registrar(ev, "oficios_oficio", gv_mudado, 1, mudou=True)
    registrar(ev, "prestacoes_contas_prestacaocontas", prest_gv, 500)
    registrar(ev, "prestacoes_contas_prestacaoservidor", ps_gv, 600, mudou=True)

    primeira = rodar(ev, gv, ("viagens", "prestacao"))
    modelos = (Oficio, Historico, Viajante, PrestacaoContas, PrestacaoServidor, MapaLegado)
    contagem = {m: m.objects.count() for m in modelos}
    auditoria = _contar_auditoria()
    segunda = rodar(ev, gv, ("viagens", "prestacao"))

    assert primeira.contagens["oficio"]["criado"] == 2
    assert primeira.contagens["oficio"]["renumerado"] == 1
    # Prestação do servidor editada nos dois: vale o GV (mais recente), vazio não apaga.
    ps = PrestacaoServidor.objects.get()
    assert (ps.numero_solicitacao, ps.situacao) == ("1234567", "preenchimento")
    assert primeira.contagens["prestacao_servidor"]["editado_nos_dois"] == 1
    assert {m: m.objects.count() for m in modelos} == contagem
    assert _contar_auditoria() == auditoria
    assert not any(k.startswith("criado") for n in segunda.contagens.values() for k in n)
    assert not segunda.conferir
