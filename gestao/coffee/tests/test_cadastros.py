"""CB1: acesso ao módulo e cadastros contratuais do Coffee Break — quem entra, fornecedor
(CNPJ, únicos), contrato (vigência, PDF conferido, vigência efetiva com o aditivo), lote
(municípios do Paraná, único por contrato/número/exercício), exclusão protegida, trava de
versão, busca e a configuração do ofício (registro único)."""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio
from gestao.coffee.forms import versao_de
from gestao.coffee.models import ConfiguracaoOficio, Contrato, Fornecedor, Lote, TermoAditivo
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


def _cliente(u: Usuario) -> Client:
    c = Client()
    c.force_login(u)
    return c


@pytest.fixture
def admin():
    return _cliente(_usuario("admin", "ASCOM_COFFEE_BREAK", "ADMINISTRADOR"))


def _fornecedor(**extra) -> Fornecedor:
    return Fornecedor.objects.create(**{"razao_social": "Buffet Exemplo Ltda",
                                        "cnpj": "12345678000195", **extra})


def _contrato(**extra) -> Contrato:
    return Contrato.objects.create(**{"fornecedor": extra.pop("fornecedor", None) or _fornecedor(),
                                      "numero": "123/2025", **extra})


def _pdf(nome: str = "contrato.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, b"%PDF-1.4 conteudo", content_type="application/pdf")


def test_quem_entra_nos_cadastros():
    url = reverse("coffee:cadastros", args=["fornecedores"])
    assert Client().get(url).status_code == 302  # anônimo vai ao login
    assert _cliente(_usuario("x")).get(url).status_code == 403
    assert _cliente(_usuario("so_admin", "ADMINISTRADOR")).get(url).status_code == 403
    assert _cliente(_usuario("operador", "ASCOM_COFFEE_BREAK")).get(url).status_code == 403
    assert _cliente(_usuario("adm", "ASCOM_COFFEE_BREAK", "ADMINISTRADOR")).get(
        url).status_code == 200
    assert _cliente(_usuario("adm2", "ASCOM_COFFEE_BREAK", "ADMINISTRADOR")).get(
        reverse("coffee:cadastros", args=["inexistente"])).status_code == 404


def test_fornecedor_cnpj_e_unicos(admin):
    url = reverse("coffee:salvar", args=["fornecedores"])
    r = admin.post(url, {"razao_social": "  Doces   Bons Ltda ", "cnpj": "12.345.678/0001-95"})
    assert r.status_code == 302
    f = Fornecedor.objects.get()
    assert f.razao_social == "Doces Bons Ltda" and f.cnpj == "12345678000195"
    assert f.nome_para_documentos == "DOCES BONS"
    r = admin.post(url, {"razao_social": "doces bons ltda", "cnpj": "123"})
    html = r.content.decode()
    assert r.status_code == 422 and "O CNPJ deve ter 14 dígitos." in html
    assert "Já existe um fornecedor com esta razão social." in html
    r = admin.post(url, {"razao_social": "Outro", "cnpj": "12345678000195"})
    assert "Já existe um fornecedor com este CNPJ." in r.content.decode()
    html = admin.get(reverse("coffee:cadastros", args=["fornecedores"]),
                     {"q": "12.345.678"}).content.decode()
    assert "Doces Bons Ltda" in html  # busca pelo CNPJ com pontuação


def test_trava_de_versao(admin):
    f = _fornecedor()
    url = reverse("coffee:salvar", args=["fornecedores"])
    r = admin.post(url, {"pk": f.pk, "versao": "2020-01-01T00:00:00", "razao_social": "Novo"})
    assert r.status_code == 422 and "alterado por outra pessoa" in r.content.decode()
    r = admin.post(url, {"pk": f.pk, "versao": versao_de(f), "razao_social": "Novo"})
    assert r.status_code == 302
    f.refresh_from_db()
    assert f.razao_social == "Novo"


def test_contrato_vigencia_pdf_e_aditivo(admin, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    f = _fornecedor()
    url = reverse("coffee:salvar", args=["contratos"])
    base = {"fornecedor": f.pk, "numero": "77/2025", "antecedencia_minima_dias": "2",
            "vigencia_inicio": "01/03/2025", "vigencia_fim": "01/01/2025"}
    r = admin.post(url, base)
    assert "O fim da vigência não pode ser anterior ao início." in r.content.decode()
    r = admin.post(url, {**base, "vigencia_fim": "28/02/2026",
                         "arquivo": SimpleUploadedFile("x.pdf", b"nao e pdf")})
    assert "Envie o arquivo em PDF." in r.content.decode()
    r = admin.post(url, {**base, "vigencia_fim": "28/02/2026", "valor_unitario": "21,07",
                         "arquivo": _pdf()})
    assert r.status_code == 302
    c = Contrato.objects.get(numero="77/2025")
    assert str(c.valor_unitario) == "21.0700" and c.arquivo
    baixar = reverse("coffee:arquivo", args=["contratos", c.pk])
    r = admin.get(baixar)
    assert r.status_code == 200 and b"".join(r.streaming_content).startswith(b"%PDF")
    assert _cliente(_usuario("sem")).get(baixar).status_code == 403
    TermoAditivo.objects.create(contrato=c, numero="1", vigencia_fim=date(2026, 12, 31))
    assert c.fim_efetivo() == date(2026, 12, 31)
    assert c.referencia_documental == "77/2025"


def test_lote_municipios_do_parana_e_unico(admin):
    c = _contrato()
    for nome, uf, ibge in (("Curitiba", "PR", "4106902"), ("Londrina", "PR", "4113700"),
                           ("Santos", "SP", "3548500")):
        Municipio.objects.get_or_create(codigo_ibge=ibge, defaults={"nome": nome, "uf": uf})
    url = reverse("coffee:salvar", args=["lotes"])
    base = {"contrato": c.pk, "numero": "1", "exercicio": "2026", "quantidade_total": "1000",
            "ativo": "on"}
    r = admin.post(url, {**base, "lista_municipios": "Curitiba, Santos"})
    assert "Município não encontrado no Paraná: Santos." in r.content.decode()
    r = admin.post(url, {**base, "lista_municipios": "curitiba;\nLondrina/PR"})
    assert r.status_code == 302
    lote = Lote.objects.get()
    assert sorted(m.nome for m in lote.municipios.all()) == ["Curitiba", "Londrina"]
    assert "Londrina/PR" in lote.municipios_texto
    r = admin.post(url, {**base, "lista_municipios": ""})
    assert "O Lote 1 (2026) deste contrato já existe." in r.content.decode()
    r = admin.post(url, {**base, "quantidade_total": "0", "numero": "2"})
    assert r.status_code == 422


def test_exclusao_protegida(admin):
    c = _contrato()
    r = admin.post(reverse("coffee:excluir", args=["fornecedores", c.fornecedor_id]),
                   follow=True)
    assert "Não é possível excluir: fornecedor em uso" in r.content.decode()
    assert Fornecedor.objects.filter(pk=c.fornecedor_id).exists()
    livre = _fornecedor(razao_social="Sem contrato", cnpj="")
    admin.post(reverse("coffee:excluir", args=["fornecedores", livre.pk]))
    assert not Fornecedor.objects.filter(pk=livre.pk).exists()


def test_configuracao_registro_unico_com_valores_neutros(admin):
    url = reverse("coffee:configuracao")
    html = admin.get(url).content.decode()
    assert ConfiguracaoOficio.objects.count() == 1 and "Ao GAF," in html
    cfg = ConfiguracaoOficio.objects.get()
    assert cfg.assinante == ""  # nada de nomes de pessoas
    dados = {"versao": versao_de(cfg), "destino_despacho": "Ao GAF,",
             "emails_ascom": "ascom@exemplo.invalid, errado"}
    r = admin.post(url, dados)
    assert r.status_code == 422 and "E-mail inválido: errado" in r.content.decode()
    r = admin.post(url, {**dados, "emails_ascom": "a@exemplo.invalid,b@exemplo.invalid"})
    assert r.status_code == 302
    admin.get(url)
    assert ConfiguracaoOficio.objects.count() == 1
    cfg.refresh_from_db()
    assert cfg.emails_ascom == "a@exemplo.invalid, b@exemplo.invalid"


def test_telas_de_todas_as_tabelas_e_janelas(admin):
    c = _contrato()
    TermoAditivo.objects.create(contrato=c, numero="2")
    Lote.objects.create(contrato=c, numero=1, exercicio="2026", quantidade_total=10)
    for tabela in ("fornecedores", "contratos", "aditivos", "lotes"):
        url = reverse("coffee:cadastros", args=[tabela])
        assert admin.get(url).status_code == 200
        assert 'data-abrir-ao-carregar' in admin.get(url, {"novo": "1"}).content.decode()
    pk = Lote.objects.get().pk
    assert admin.get(reverse("coffee:cadastros", args=["lotes"]),
                     {"editar": pk}).status_code == 200


def test_trocar_o_pdf_apaga_o_antigo_e_capacidade_nao_abaixo_do_consumido(
        admin, settings, tmp_path, django_capture_on_commit_callbacks):
    """Revisão de segurança da CB1/CB2: o PDF trocado sai do disco (e só ele); o lote não
    fica com capacidade abaixo do que já consumiu; a permissão vale por tabela."""
    from pathlib import Path

    from gestao.coffee import pedidos

    settings.MEDIA_ROOT = tmp_path
    f = _fornecedor()
    url = reverse("coffee:salvar", args=["contratos"])
    base = {"fornecedor": f.pk, "numero": "1/2026", "antecedencia_minima_dias": "2"}
    admin.post(url, {**base, "arquivo": _pdf("primeiro.pdf")})
    c = Contrato.objects.get(numero="1/2026")
    antigo = Path(c.arquivo.path)
    assert antigo.exists()
    with django_capture_on_commit_callbacks(execute=True):
        r = admin.post(url, {**base, "pk": c.pk, "versao": versao_de(c),
                             "arquivo": _pdf("segundo.pdf")})
    assert r.status_code == 302
    c.refresh_from_db()
    assert not antigo.exists() and Path(c.arquivo.path).exists()

    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio="2026", quantidade_total=100)
    lote.municipios.set([curitiba])
    u = _usuario("op", "ASCOM_COFFEE_BREAK")
    pedidos.salvar(u, {"municipio": curitiba, "data_solicitacao": date(2026, 1, 5),
                       "numero": "", "descricao": "Evento", "quantidade": 60})
    r = admin.post(reverse("coffee:salvar", args=["lotes"]), {
        "pk": lote.pk, "versao": versao_de(lote), "contrato": c.pk, "numero": "1",
        "exercicio": "2026", "quantidade_total": "50", "lista_municipios": "Curitiba"})
    assert "O lote já consumiu 60 unidades" in r.content.decode()

    so_fornecedor = _usuario("sf", "ASCOM_COFFEE_BREAK")
    from django.contrib.auth.models import Permission
    so_fornecedor.user_permissions.add(Permission.objects.get(codename="change_fornecedor"))
    cli = _cliente(so_fornecedor)
    assert cli.get(reverse("coffee:cadastros", args=["fornecedores"])).status_code == 200
    assert cli.get(reverse("coffee:cadastros", args=["lotes"])).status_code == 403
