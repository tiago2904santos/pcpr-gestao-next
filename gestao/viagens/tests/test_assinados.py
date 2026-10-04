"""Vias assinadas (paridade com `anexar_arquivo_assinado`/`remover_arquivo_assinado` da
referência): validação do upload, versões imutáveis, revogação, a via prevalecendo no PDF,
"Assinado, mas os dados mudaram", reabertura do ofício e permissões por objeto."""

from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio, Servidor
from gestao.plataforma import outbox
from gestao.viagens import assinados, ordens, policies, services, termos
from gestao.viagens.models import Historico, Oficio, TermoAutorizacao, ViaAssinada

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n% via assinada de teste\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def c():
    return cenario_completo()


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def _upload(conteudo: bytes = PDF, nome: str = "assinado.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


def _emitido(c) -> Oficio:
    while outbox.processar_lote():
        pass
    return Oficio.objects.get(pk=c.ids["oficio_emitido"])


def _os_gerada(c):
    ordem, _ = ordens.salvar(c.usuarios["operador"],
                             destinos=[Municipio.objects.get(nome="Londrina", uf="PR")],
                             servidores=[Servidor.objects.first()], motivo="a feira fictícia")
    ordens.dados_do_documento(ordem, fixar=True)  # conta como gerada
    ordem.refresh_from_db()
    return ordem


class TestValidacao:
    @pytest.mark.parametrize(("nome", "tamanho", "inicio", "mensagem"), [
        ("assinado.docx", 10, b"%PDF-", "Envie um arquivo PDF."),
        ("assinado.pdf", 15 * 1024 * 1024 + 1, b"%PDF-", "Arquivo maior que 15MB."),
        ("assinado.pdf", 10, b"GIF89", "O arquivo não parece ser um PDF válido."),
    ])
    def test_as_tres_conferencias_da_referencia(self, nome, tamanho, inicio, mensagem):
        with pytest.raises(assinados.ArquivoAssinadoInvalido, match=mensagem):
            assinados.validar(nome, tamanho, inicio)

    def test_extensao_em_maiusculas_vale(self):
        assinados.validar("ASSINADO.PDF", 10, b"%PDF-1.4")

    def test_impressao_ignora_a_marca_de_previa(self):
        assert assinados.impressao({"a": 1, "previa": True}) == assinados.impressao({"a": 1})
        assert assinados.impressao({"a": 1}) != assinados.impressao({"a": 2})


class TestOficio:
    def test_anexar_prevalece_no_pdf_e_remover_volta_ao_gerado(self, c):
        oficio = _emitido(c)
        op = c.usuarios["operador"]
        alvo = assinados.Alvo("oficio", oficio)
        via = assinados.anexar(op, alvo, nome="oficio-assinado.pdf", conteudo=PDF)
        doc = assinados.documento_emitido(oficio, "oficio")
        assert via.documento == doc and via.sha256 and via.tamanho == len(PDF)
        cli = _cliente(op)
        url = reverse("viagens:baixar_documento", args=[doc.pk])
        r = cli.get(url)
        assert b"".join(r.streaming_content) == PDF and r["Cache-Control"] == "no-store"
        assert r["X-Content-SHA256"] == via.sha256
        original = b"".join(cli.get(url + "?versao=original").streaming_content)
        assert original != PDF and original.startswith(b"%PDF")
        assert Historico.objects.filter(oficio=oficio, acao=Historico.Acao.ASSINADO).count() == 1
        assinados.revogar(op, via.pk)
        assert b"".join(cli.get(url).streaming_content) != PDF
        via.refresh_from_db()
        assert via.revogada_em is not None and via.revogada_por == op
        assert via.arquivo.storage.exists(via.arquivo.name)  # o arquivo fica como prova

    def test_trocar_cria_versao_nova_e_a_mais_recente_vale(self, c):
        oficio = _emitido(c)
        alvo = assinados.Alvo("oficio", oficio)
        assinados.anexar(c.usuarios["operador"], alvo, nome="v1.pdf", conteudo=PDF)
        segunda = assinados.anexar(c.usuarios["operador"], alvo, nome="v2.pdf",
                                   conteudo=PDF + b"%v2")
        assert assinados.vigente(alvo) == segunda
        assert ViaAssinada.objects.filter(oficio=oficio).count() == 2
        primeira = ViaAssinada.objects.get(nome_original="v1.pdf")
        assert primeira.revogada_em is not None
        assert primeira.motivo_revogacao == "Substituída por uma via nova."
        # Remover a nova volta ao PDF gerado, não à via antiga.
        assinados.revogar(c.usuarios["operador"], segunda.pk)
        assert assinados.vigente(alvo) is None
        with pytest.raises(assinados.ViaJaRemovida):
            assinados.revogar(c.usuarios["operador"], segunda.pk)

    def test_rascunho_nao_recebe_via(self, c):
        rascunho = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
        with pytest.raises(PermissionDenied):
            assinados.anexar(c.usuarios["operador"], assinados.Alvo("oficio", rascunho),
                             nome="a.pdf", conteudo=PDF)

    def test_reabrir_e_retificar_revogam_a_via(self, c):
        oficio = _emitido(c)
        alvo = assinados.Alvo("oficio", oficio)
        via = assinados.anexar(c.usuarios["operador"], alvo, nome="a.pdf", conteudo=PDF)
        services.reabrir(oficio, c.usuarios["gestor"], "Corrigir o motivo.")
        via.refresh_from_db()
        assert via.revogada_em is not None
        assert via.motivo_revogacao == "Reaberto para correção: Corrigir o motivo."
        assert assinados.vigente(alvo) is None

    def test_tela_anexa_pela_janela_e_volta_para_a_lista(self, c):
        oficio = _emitido(c)
        cli = _cliente(c.usuarios["operador"])
        url = reverse("viagens:anexar_assinado", args=["oficio", oficio.pk])
        voltar = f"/viagens/oficios/?resumo={oficio.pk}"
        r = cli.post(url, {"arquivo": _upload(), "voltar": voltar})
        assert r.status_code == 302 and r["Location"] == voltar
        assert assinados.vigente(assinados.Alvo("oficio", oficio)) is not None
        # O resumo mostra a via, com o selo e as ações.
        html = cli.get(reverse("viagens:resumo", args=[oficio.pk])).content.decode()
        assert f"Ofício {oficio.numero_formatado} · v1" in html and "Assinado" in html

    def test_erro_da_janela_volta_como_mensagem_e_sem_janela_mostra_a_pagina(self, c):
        oficio = _emitido(c)
        cli = _cliente(c.usuarios["operador"])
        url = reverse("viagens:anexar_assinado", args=["oficio", oficio.pk])
        r = cli.post(url, {"arquivo": _upload(b"GIF89a", "foto.pdf"), "voltar": "/viagens/"})
        html = r.content.decode()
        assert r.status_code == 422 and "O arquivo não parece ser um PDF válido." in html
        assert 'name="voltar" value="/viagens/"' in html
        r = cli.post(url, {"arquivo": _upload(nome="a.docx")})
        assert r.status_code == 422 and "Envie um arquivo PDF." in r.content.decode()
        assert not ViaAssinada.objects.exists()

    def test_voltar_externo_e_ignorado(self, c):
        oficio = _emitido(c)
        cli = _cliente(c.usuarios["operador"])
        url = reverse("viagens:anexar_assinado", args=["oficio", oficio.pk])
        r = cli.post(url, {"arquivo": _upload(), "voltar": "https://exemplo.invalid/x"})
        assert r.status_code == 302 and r["Location"].startswith("/viagens/oficios/")

    def test_permissoes_por_objeto(self, c):
        oficio = _emitido(c)
        url = reverse("viagens:anexar_assinado", args=["oficio", oficio.pk])
        assert _cliente(c.usuarios["outra"]).get(url).status_code == 404  # outra unidade
        assert _cliente(c.usuarios["consulta"]).post(url, {"arquivo": _upload()}).status_code == 403
        via = assinados.anexar(c.usuarios["operador"], assinados.Alvo("oficio", oficio),
                               nome="a.pdf", conteudo=PDF)
        abrir = reverse("viagens:abrir_via_assinada", args=[via.pk])
        assert _cliente(c.usuarios["outra"]).get(abrir).status_code == 404
        assert _cliente(c.usuarios["outra"]).post(
            reverse("viagens:remover_via_assinada", args=[via.pk])).status_code == 404
        assert _cliente(c.usuarios["consulta"]).post(
            reverse("viagens:remover_via_assinada", args=[via.pk])).status_code == 403
        via.refresh_from_db()
        assert via.revogada_em is None

    def test_remover_pela_tela(self, c):
        oficio = _emitido(c)
        via = assinados.anexar(c.usuarios["operador"], assinados.Alvo("oficio", oficio),
                               nome="a.pdf", conteudo=PDF)
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:remover_via_assinada", args=[via.pk]), follow=True)
        assert "Via assinada removida: o PDF gerado volta a valer." in r.content.decode()


class TestTermo:
    def test_via_por_documento_e_aviso_de_dados_que_mudaram(self, c):
        op = c.usuarios["operador"]
        oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
        termo = termos.salvar(op, oficio=oficio)
        alvo = assinados.Alvo("termo", termo, termos.GENERICO)
        via = assinados.anexar(op, alvo, nome="termo.pdf", conteudo=PDF)
        assert via.impressao_dos_dados and not assinados.dados_mudaram(via)
        cli = _cliente(op)
        pdf = reverse("viagens:documento_termo", args=[termo.pk, termos.GENERICO, "pdf"])
        assert cli.get(pdf).content != PDF  # gerar sempre gera o documento atual
        abrir = reverse("viagens:abrir_via_assinada", args=[via.pk])
        assert b"".join(cli.get(abrir).streaming_content) == PDF
        # Outro documento do mesmo termo continua sem via.
        servidor = str(termos.efetivo(termo).servidores[0].pk)
        assert assinados.vigente(assinados.Alvo("termo", termo, servidor)) is None
        termos.salvar(op, pk=termo.pk, oficio=oficio, evento="Outro evento")
        assert assinados.dados_mudaram(ViaAssinada.objects.get(pk=via.pk))
        html = cli.get(reverse("viagens:editar_termo", args=[termo.pk])).content.decode()
        assert "Via assinada do termo genérico anexada (termo.pdf)" in html  # histórico
        assert "Assinado, mas os dados mudaram" in html and 'id="dialogo-assinado"' in html

    def test_termo_com_via_nao_se_exclui(self, c):
        op = c.usuarios["operador"]
        termo = termos.salvar(op, oficio=Oficio.objects.get(pk=c.ids["oficio_emitido"]))
        assinados.anexar(op, assinados.Alvo("termo", termo, termos.GENERICO), nome="t.pdf",
                         conteudo=PDF)
        termo = TermoAutorizacao.objects.get(pk=termo.pk)
        assert not policies.pode_excluir_termo(c.usuarios["gestor"], termo)  # menu esconde
        with pytest.raises(PermissionDenied):
            termos.excluir(c.usuarios["gestor"], termo.pk)
        html = _cliente(c.usuarios["operador"]).get(reverse("viagens:termos")).content.decode()
        assert "Assinado" in html or "assinados" in html  # selo na lista

    def test_chave_que_nao_e_do_termo_da_404(self, c):
        op = c.usuarios["operador"]
        termo = termos.salvar(op, oficio=Oficio.objects.get(pk=c.ids["oficio_emitido"]))
        url = reverse("viagens:anexar_assinado_de", args=["termo", termo.pk, "999999"])
        assert _cliente(op).get(url).status_code == 404


class TestOrdem:
    def test_so_depois_de_gerada(self, c):
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(op, destinos=[Municipio.objects.get(nome="Londrina", uf="PR")],
                                 servidores=[Servidor.objects.first()], motivo="a feira")
        with pytest.raises(PermissionDenied):
            assinados.anexar(op, assinados.Alvo("ordem", ordem), nome="os.pdf", conteudo=PDF)
        html = _cliente(op).get(reverse("viagens:editar_ordem", args=[ordem.pk])).content.decode()
        assert "Gere a OS (PDF) para depois anexar a via assinada." in html

    def test_via_prevalece_e_dados_mudados(self, c):
        op = c.usuarios["operador"]
        ordem = _os_gerada(c)
        via = assinados.anexar(op, assinados.Alvo("ordem", ordem), nome="os.pdf", conteudo=PDF)
        cli = _cliente(op)
        pdf = reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"])
        assert cli.get(pdf).content != PDF  # "Gerar a OS" sempre gera
        html = cli.get(reverse("viagens:ordens")).content.decode()
        assert reverse("viagens:abrir_via_assinada", args=[via.pk]) in html  # menu da lista
        assert not assinados.dados_mudaram(via)
        ordens.salvar(op, pk=ordem.pk, destinos=[Municipio.objects.get(nome="Londrina",
                                                                         uf="PR")],
                      servidores=[Servidor.objects.first()], motivo="outro motivo",
                      versao=ordens.versao_de(ordem))
        assert assinados.dados_mudaram(ViaAssinada.objects.get(pk=via.pk))

    def test_os_cancelada_nao_recebe_via(self, c):
        op = c.usuarios["operador"]
        ordem = _os_gerada(c)
        ordens.cancelar(op, ordem.pk, "Adiada")
        ordem.refresh_from_db()
        assert not assinados.pode_anexar(op, assinados.Alvo("ordem", ordem))

    def test_consulta_nao_abre_a_via_da_os(self, c):
        op = c.usuarios["operador"]
        ordem = _os_gerada(c)
        via = assinados.anexar(op, assinados.Alvo("ordem", ordem), nome="os.pdf", conteudo=PDF)
        url = reverse("viagens:abrir_via_assinada", args=[via.pk])
        assert _cliente(c.usuarios["consulta"]).get(url).status_code == 404
        assert _cliente(op).get(url).status_code == 200
        ordens.cancelar(op, ordem.pk, "Adiada")
        assert _cliente(op).get(url).status_code == 404  # como o PDF gerado: OS ativa


def test_constraint_um_dono_do_tipo(c):
    from django.db import IntegrityError, transaction
    oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    with pytest.raises(IntegrityError), transaction.atomic():
        ViaAssinada.objects.create(tipo="termo", oficio=oficio, sha256="x" * 64, tamanho=1,
                                   arquivo="assinados/x.pdf",
                                   enviado_por=c.usuarios["operador"])


def test_abrir_a_via_e_pagina_sem_janela(c):
    oficio = _emitido(c)
    op = c.usuarios["operador"]
    cli = _cliente(op)
    url = reverse("viagens:anexar_assinado", args=["oficio", oficio.pk])
    html = cli.get(url).content.decode()
    assert "Anexar via assinada" in html and 'enctype="multipart/form-data"' in html
    via = assinados.anexar(op, assinados.Alvo("oficio", oficio), nome="a.pdf", conteudo=PDF)
    r = cli.get(reverse("viagens:abrir_via_assinada", args=[via.pk]))
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r["Cache-Control"] == "no-store" and b"".join(r.streaming_content) == PDF
    assert "Trocar via assinada" in cli.get(url).content.decode()


def test_remover_pelo_resumo_volta_para_a_lista_com_o_resumo(c):
    oficio = _emitido(c)
    op = c.usuarios["operador"]
    via = assinados.anexar(op, assinados.Alvo("oficio", oficio), nome="a.pdf", conteudo=PDF)
    html = _cliente(op).get(reverse("viagens:resumo", args=[oficio.pk])).content.decode()
    voltar = f"/viagens/oficios/?resumo={oficio.pk}"
    assert f'id="remover-via-{via.pk}"' in html and f'value="{voltar}"' in html
    r = _cliente(op).post(reverse("viagens:remover_via_assinada", args=[via.pk]),
                          {"voltar": voltar})
    assert r.status_code == 302 and r["Location"] == voltar


def test_corpo_acima_do_limite_e_recusado_antes_do_upload(c):
    oficio = _emitido(c)
    cli = _cliente(c.usuarios["operador"])
    url = reverse("viagens:anexar_assinado", args=["oficio", oficio.pk])
    r = cli.generic("POST", url, b"x", content_type="multipart/form-data; boundary=x",
                    CONTENT_LENGTH=str(17 * 1024 * 1024))
    assert r.status_code == 413 and "até 15 MB" in r.content.decode()
    assert not ViaAssinada.objects.exists()


def _pdf_com_texto(texto: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=f"<p>{texto}</p>").write_pdf()


def _pdf_com_campo_de_assinatura(nome: str) -> bytes:
    import io

    import pikepdf
    pdf = pikepdf.open(io.BytesIO(_pdf_com_texto("documento")))
    valor = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Sig, Name=pikepdf.String(nome),
        M=pikepdf.String("D:20260924103000-03'00'")))
    campo = pdf.make_indirect(pikepdf.Dictionary(FT=pikepdf.Name.Sig,
                                                 T=pikepdf.String("Assinatura1"), V=valor))
    pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([campo]))
    saida = io.BytesIO()
    pdf.save(saida)
    return saida.getvalue()


class TestConferencia:
    def test_carimbo_e_numero_errado_viram_avisos(self, c):
        oficio = _emitido(c)
        outro = oficio.numero + 1
        pdf = _pdf_com_texto(
            f"Ofício nº {outro}/{oficio.ano} — Assinatura Avançada realizada por: Maria "
            "Exemplo (XXX.033.259-XX) em 24/09/2026 11:13")
        cli = _cliente(c.usuarios["operador"])
        url = reverse("viagens:anexar_assinado", args=["oficio", oficio.pk])
        r = cli.post(url, {"arquivo": _upload(pdf), "voltar": "/viagens/"}, follow=True)
        html = r.content.decode()
        assert "Assinado digitalmente por Maria Exemplo em 24/09/2026 11:13." in html
        assert f"O número neste PDF é {outro:03d}/{oficio.ano}" in html
        via = ViaAssinada.objects.get()
        assert via.conferencia["assinado"] and via.conferencia["avisos"]

    def test_campo_de_assinatura_do_pdf(self, c):
        oficio = _emitido(c)
        via = assinados.anexar(c.usuarios["operador"], assinados.Alvo("oficio", oficio),
                               nome="a.pdf", conteudo=_pdf_com_campo_de_assinatura("FULANO"))
        assert via.conferencia["assinantes"][0]["nome"] == "FULANO"
        assert via.conferencia["resumo"].startswith("Assinado digitalmente por FULANO em 24/09")

    def test_pdf_sem_assinatura_avisa_e_nao_bloqueia(self, c):
        oficio = _emitido(c)
        via = assinados.anexar(c.usuarios["operador"], assinados.Alvo("oficio", oficio),
                               nome="a.pdf", conteudo=_pdf_com_texto("sem nada"))
        assert via.pk and not via.conferencia["assinado"]
        html = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:resumo", args=[oficio.pk])).content.decode()
        assert "Este PDF não tem assinatura digital reconhecível." in html

    def test_pdf_quebrado_nao_derruba_o_anexo(self, c):
        oficio = _emitido(c)
        via = assinados.anexar(c.usuarios["operador"], assinados.Alvo("oficio", oficio),
                               nome="a.pdf", conteudo=PDF)
        assert via.pk and isinstance(via.conferencia, dict)

    def test_termo_confere_o_nome_do_servidor(self, c):
        op = c.usuarios["operador"]
        termo = termos.salvar(op, oficio=Oficio.objects.get(pk=c.ids["oficio_emitido"]))
        servidor = termos.efetivo(termo).servidores[0]
        via = assinados.anexar(op, assinados.Alvo("termo", termo, str(servidor.pk)),
                               nome="t.pdf", conteudo=_pdf_com_texto("Termo de outra pessoa"))
        assert f"O nome {servidor.nome} não aparece neste PDF." in via.conferencia["avisos"]
