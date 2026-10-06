"""CB4: documentos do Coffee Break — extenso e datas, pendências que bloqueiam, PDF e prévia,
vias guardadas (sem repetir a mesma folha), versão assinada que vale no lugar do gerado, e o
ofício com um item por OS e as notas no plural."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import conjunto, documentos, financeiro, pedidos, vias
from gestao.coffee.models import Contrato, Fornecedor, Lote, Solicitacao, Via
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def test_extenso_data_e_juntar():
    assert documentos.extenso(40) == "quarenta"
    assert documentos.extenso(21) == "vinte e um"
    assert documentos.extenso(100) == "cem" and documentos.extenso(101) == "cento e um"
    assert documentos.extenso(1250) == "mil duzentos e cinquenta"
    assert documentos.extenso(2000) == "dois mil" and documentos.extenso(1200) == "mil e duzentos"
    assert documentos.data_por_extenso(date(2026, 9, 21)) == "21 de Setembro de 2026"
    assert documentos.juntar(["8950", "8952", "8954"]) == "8950, 8952 e 8954"
    assert documentos.juntar(["8952"]) == "8952"


@pytest.fixture
def os_(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet Exemplo Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="12/2025", numero_gms="4400",
                                valor_unitario=Decimal("20"), fiscal="Fiscal Teste",
                                vigencia_fim=hoje + timedelta(days=300))
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=500, empenho="2026NE1")
    lote.municipios.set([curitiba])
    s = pedidos.salvar(u, {"municipio": curitiba, "data_solicitacao": hoje, "numero": "",
                           "descricao": "Posse da diretoria", "quantidade": 40,
                           "data_evento": hoje + timedelta(days=5)}).solicitacao
    return u, s


def test_pendencias_bloqueiam_e_pdf_sai_quando_completo(os_):
    u, s = os_
    assert documentos.pendencias("os", s) == ["Informe o local de entrega.",
                                              "Informe o responsável pelo recebimento."]
    assert documentos.pendencias("certifico", s) == ["Informe o número da nota fiscal."]
    with pytest.raises(pedidos.PedidoInvalido, match="local de entrega"):
        vias.obter(u, s, "os")
    Solicitacao.objects.filter(pk=s.pk).update(local_entrega="Auditório",
                                               responsavel="Plantão (41) 3000-0000")
    s.refresh_from_db()
    arq = vias.obter(u, s, "os")
    assert arq.conteudo.startswith(b"%PDF") and arq.nome.startswith("OS 1-")
    html = documentos.html("os", s)
    assert "ORDEM DE SERVIÇO" in html and "12/2025 – GMS 4400" in html
    assert "Solicito coffee para:" in html and "p/ 40 pessoas" in html
    vias.obter(u, s, "os")  # mesma folha: não guarda outra via
    assert Via.objects.filter(solicitacao=s, tipo="os").count() == 1
    vias.obter(u, s, "certificado")
    assert not Via.objects.filter(tipo="certificado").exists()  # espelho: não se guarda


def test_oficio_um_item_por_os_e_notas_no_plural(os_):
    u, a = os_
    b = pedidos.salvar(u, {"municipio": a.municipio, "data_solicitacao": a.data_solicitacao,
                           "numero": "", "descricao": "Reunião", "quantidade": 21}).solicitacao
    conjunto.definir(u, a.pk, [b.pk])
    assert documentos.pendencias("oficio", a) == [
        "Informe o número da nota fiscal.", f"Informe o número da nota fiscal da {b}.",
        "Informe o número do ofício."]
    for x, nota in ((b, "8952"), (a, "8950")):
        x.refresh_from_db()
        financeiro.salvar_financeiro(u, x.pk, {**{c: getattr(x, c) for c in financeiro.CAMPOS},
                                               "nota_fiscal": nota})
    a.refresh_from_db()
    html = documentos.html("oficio", a)
    assert "as Notas Fiscais n° 8950 e 8952, devidamente atestadas" in html
    assert "Coffee Break para 21 (vinte e um) pessoas." in html
    assert "Coffee Break para 40 (quarenta) pessoas." in html


def test_versao_assinada_vale_no_lugar_do_gerado(os_):
    u, s = os_
    Solicitacao.objects.filter(pk=s.pk).update(nota_fiscal="8957")
    s.refresh_from_db()
    with pytest.raises(pedidos.PedidoInvalido, match="Envie o arquivo em PDF"):
        vias.anexar_assinada(u, s.pk, "certifico", SimpleUploadedFile("x.pdf", b"nada"))
    vias.anexar_assinada(u, s.pk, "certifico",
                         SimpleUploadedFile("ass.pdf", b"%PDF-1.4 assinado"))
    arq = vias.obter(u, s, "certifico")
    assert arq.assinada and arq.conteudo == b"%PDF-1.4 assinado"
    vias.remover_assinada(u, s.pk, "certifico")
    assert not vias.obter(u, s, "certifico").assinada
    assert Via.objects.filter(assinada=True, removida_em__isnull=False).count() == 1  # guardada


def test_telas_dos_documentos(os_):
    u, s = os_
    c = Client()
    c.force_login(u)
    html = c.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "Documentos" in html and "Falta informação" in html
    r = c.get(reverse("coffee:documento", args=[s.pk, "os"]))
    assert r.status_code == 302 and r["Location"].endswith("#documentos")
    r = c.get(reverse("coffee:documento", args=[s.pk, "certificado"]), {"baixar": "1"})
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert "attachment" in r["Content-Disposition"]
    r = c.get(reverse("coffee:documento", args=[s.pk, "certificado"]), {"formato": "html"})
    assert "CERTIFICADO DA SOLICITAÇÃO" in r.content.decode()
    assert c.get(reverse("coffee:documento", args=[s.pk, "outro"])).status_code == 404
