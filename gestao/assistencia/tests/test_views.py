"""Telas da assistência e da Central de ajuda: permissões (403/404), o cartão nas folhas de
RT, ofício, plano e viagem, o ciclo pedir → revisar → aceitar pela tela, e o worker."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from gestao.assistencia import servicos
from gestao.assistencia.models import ConfiguracaoUso, PedidoSugestao, Sugestao
from gestao.assistencia.usos_proprios import recurso_da_pessoa
from gestao.viagens import planos, relatorio
from gestao.viagens.models import Oficio, PrestacaoContas
from gestao.viagens.tests.cenarios import cenario_completo

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
RT = "viagens.rt_rascunho"


@pytest.fixture
def c(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.IA = {}
    return cenario_completo()


def _cliente(u) -> Client:
    cliente = Client()
    cliente.force_login(u)
    return cliente


def _admin(c):
    u = c.usuarios["gestor"]
    for codigo in ("administrar_ia", "ver_painel_ia"):
        u.user_permissions.add(Permission.objects.get(codename=codigo))
    return u


def _p(c) -> PrestacaoContas:
    return PrestacaoContas.objects.get(oficio_id=c.ids["oficio_emitido"])


def test_templates_sem_estilo_nem_script_inline():
    for arquivo in TEMPLATES.rglob("*.html"):
        texto = arquivo.read_text(encoding="utf-8")
        assert not re.search(r"\sstyle=", texto), arquivo.name
        assert "<script" not in texto, arquivo.name


def test_painel_usos_e_sugestoes_so_para_quem_tem_permissao(c):
    for nome in ("assistencia:painel", "assistencia:usos", "assistencia:sugestoes"):
        assert _cliente(c.usuarios["consulta"]).get(reverse(nome)).status_code == 403
        r = _cliente(_admin(c)).get(reverse(nome))
        assert r.status_code == 200, nome
    r = _cliente(_admin(c)).get(reverse("assistencia:painel"))
    assert "Custo estimado no mês" in r.content.decode() and "Simulada" in r.content.decode()


def test_admin_muda_modo_e_teto_pela_tela(c):
    cliente = _cliente(_admin(c))
    r = cliente.post(reverse("assistencia:alterar_uso", args=[RT]),
                     {"ligado": "1", "modo": "ia", "max_tentativas": "2", "motivo": "Ensaio"})
    assert r.status_code == 302
    assert ConfiguracaoUso.objects.get(uso=RT).modo == "ia"
    r = cliente.post(reverse("assistencia:definir_teto"), {"escopo": "global", "teto": "2,50"})
    assert r.status_code == 302
    assert "2,50" in cliente.get(reverse("assistencia:usos")).content.decode()
    # Operador não administra.
    r = _cliente(c.usuarios["operador"]).post(reverse("assistencia:alterar_uso", args=[RT]),
                                              {"ligado": "1", "modo": "regra"})
    assert r.status_code == 403


def test_cartao_nas_folhas_e_ciclo_completo_pela_tela(c):
    p = _p(c)
    op = _cliente(c.usuarios["operador"])
    folha = op.get(reverse("viagens:relatorio", args=[p.pk])).content.decode()
    assert "Rascunho do relatório técnico" in folha and "Pedir rascunho do relato" in folha
    r = op.post(reverse("assistencia:pedir", args=[RT, p.pk]), {"relato": "Tudo certo."})
    s = Sugestao.objects.get(uso=RT)
    assert r.status_code == 302 and r.url == reverse("assistencia:sugestao", args=[s.pk])
    pagina = op.get(r.url).content.decode()
    assert "Fontes:" in pagina and "Ofício · destinos dos trechos" in pagina
    assert "Gravar “Descrição do evento”" in pagina and "Descartar sugestão" in pagina
    assert "Atual" in pagina and "Sugerido" in pagina
    r = op.post(reverse("assistencia:aceitar", args=[s.pk]), {"texto-motivo": "Meu texto."})
    assert r.status_code == 302 and r.url == reverse("viagens:relatorio", args=[p.pk])
    assert relatorio.obter(p).motivo == "Meu texto."
    assert Sugestao.objects.get(pk=s.pk).estado == "editada"


def test_sugestao_de_outra_unidade_e_404(c):
    p = _p(c)
    relatorio.obter(p)
    s = Sugestao.objects.get(pedido=servicos.pedir(c.usuarios["operador"], RT, p.pk))
    outra = _cliente(c.usuarios["outra"])
    assert outra.get(reverse("assistencia:sugestao", args=[s.pk])).status_code == 404
    assert outra.post(reverse("assistencia:aceitar", args=[s.pk])).status_code == 404
    assert outra.get(reverse("assistencia:pedir", args=[RT, p.pk])).status_code == 404


def test_cartoes_no_oficio_plano_e_viagem(c):
    from gestao.viagens import viagem

    op = c.usuarios["operador"]
    cliente = _cliente(op)
    pagina = cliente.get(reverse("viagens:editar", args=[c.ids["oficio_rascunho"]]))
    texto = pagina.content.decode()
    # A folha do ofício tem orçamento de consultas: os usos entram como link (`link_ia`, sem
    # consulta) para a tela do pedido, não como cartão completo.
    oficio_id = c.ids["oficio_rascunho"]
    assert "Pedir rascunho do motivo e da justificativa" in texto
    assert reverse("assistencia:pedir", args=["viagens.oficio_textos", oficio_id]) in texto
    assert "Ler a programação" in texto
    assert reverse("assistencia:pedir", args=["viagens.leitura_programacao", oficio_id]) in texto
    assert "Motivo do ofício e justificativa de antecedência" not in texto  # sem o cartão
    plano, _ = planos.salvar(op, oficios=[Oficio.objects.get(pk=c.ids["oficio_emitido"])])
    texto = cliente.get(reverse("viagens:editar_plano", args=[plano.pk])).content.decode()
    assert "Contextualização e considerações do plano de trabalho" in texto
    v = viagem.criar(op)
    texto = cliente.get(reverse("viagens:editar_viagem", args=[v.pk])).content.decode()
    assert "O que falta na viagem, em linguagem simples" in texto


def test_pedido_no_modo_ia_fica_na_fila_e_desligado_explica(c):
    p = _p(c)
    relatorio.obter(p)
    ConfiguracaoUso.objects.create(uso=RT, modo="ia")
    op = _cliente(c.usuarios["operador"])
    r = op.post(reverse("assistencia:pedir", args=[RT, p.pk]), {})
    pedido = PedidoSugestao.objects.get(uso=RT)
    assert r.url == reverse("assistencia:pedido", args=[pedido.pk])
    assert "Redigindo" in op.get(reverse("viagens:relatorio", args=[p.pk])).content.decode()
    assert "Na fila" in op.get(r.url).content.decode()
    ConfiguracaoUso.objects.filter(uso=RT).update(ligado=False)
    folha = op.get(reverse("viagens:relatorio", args=[p.pk])).content.decode()
    assert "Este uso está desligado" in folha


def test_central_de_ajuda_e_assistente(c):
    cliente = _cliente(c.usuarios["consulta"])
    r = cliente.get(reverse("ajuda:central"))
    assert r.status_code == 200 and "Prazo para prestar contas" in r.content.decode()
    r = cliente.post(reverse("ajuda:central"), {"pergunta": "Como envio o comprovante do saque?"})
    texto = r.content.decode()
    assert "Fontes:" in texto and reverse("ajuda:artigo", args=["comprovante-saque"]) in texto
    r = cliente.post(reverse("ajuda:central"), {"pergunta": "Cancele minha viagem"})
    assert "não altera" in r.content.decode()
    assert cliente.get(reverse("ajuda:artigo", args=["prazo-prestacao"])).status_code == 200
    assert cliente.get(reverse("ajuda:artigo", args=["nao-existe"])).status_code == 404
    assert Client().get(reverse("ajuda:central")).status_code in (302, 403)


def test_pergunta_ao_assistente_nunca_vai_na_url(c):
    """A dúvida pode ter dado pessoal: vai no corpo de um POST com CSRF, nunca na URL (log de
    acesso, histórico, Referer). Uma URL antiga com ?pergunta= não responde nada."""
    cliente = _cliente(c.usuarios["consulta"])
    texto = cliente.get(reverse("ajuda:central")).content.decode()
    formulario = texto[texto.index('id="t-pergunta"'):]
    assert '<form method="post"' in formulario[:600]
    assert 'name="csrfmiddlewaretoken"' in formulario[:800]
    pela_url = cliente.get(reverse("ajuda:central"),
                           {"pergunta": "Como envio o comprovante do saque?"})
    assert "Fontes:" not in pela_url.content.decode()
    com_csrf = Client(enforce_csrf_checks=True)
    com_csrf.force_login(c.usuarios["consulta"])
    assert com_csrf.post(reverse("ajuda:central"), {"pergunta": "x"}).status_code == 403


def test_reformular_so_aparece_no_modo_ia(c):
    cliente = _cliente(c.usuarios["consulta"])
    pergunta = "Como envio o comprovante do saque?"
    assert "linguagem simples" not in cliente.post(reverse("ajuda:central"),
                                                   {"pergunta": pergunta}).content.decode()
    ConfiguracaoUso.objects.create(uso="assistencia.reformular_resposta", modo="ia")
    texto = cliente.post(reverse("ajuda:central"), {"pergunta": pergunta}).content.decode()
    assert "Explicar em linguagem simples (IA)" in texto
    assert recurso_da_pessoa(c.usuarios["consulta"], pergunta) in texto


@pytest.mark.django_db(transaction=True)
def test_worker_processa_a_fila_fora_de_transacao(settings, django_user_model):
    settings.IA = {}
    u = django_user_model.objects.create_user("worker-ia", "w@pc.pr.gov.br", "senha-forte-1",
                                              nome="Teste do worker")
    ConfiguracaoUso.objects.create(uso="assistencia.triagem_modulo", modo="ia")
    texto = "Pedido de coffee break para o seminário"
    pedido = servicos.pedir(u, "assistencia.triagem_modulo", recurso_da_pessoa(u, texto),
                            {"texto": texto})
    assert pedido.estado == "pendente"
    call_command("processar_ia", "--uma-vez")
    s = Sugestao.objects.get(pedido=pedido)
    assert s.origem == "simulado" and not s.fallback and s.custo_estimado_usd == 0


# ------------------------------------------------------------------ entradas nas telas donas
def test_central_avisa_que_o_conteudo_e_rascunho(c):
    cliente = _cliente(c.usuarios["consulta"])
    texto = cliente.get(reverse("ajuda:central")).content.decode()
    assert "Rascunho para o sistema de testes" in texto
    texto = cliente.get(reverse("ajuda:artigo", args=["prazo-prestacao"])).content.decode()
    assert "revisão do responsável pendente" in texto


def test_entrada_na_revisao_da_importacao(c):
    from django.core.files.base import ContentFile

    from gestao.viagens.models import ArquivoImportado, ParteImportada

    op = c.usuarios["operador"]
    arq = ArquivoImportado.objects.create(usuario=op, nome="l.pdf", sha256="e" * 64,
                                          original=ContentFile(b"%PDF-1.4", "l.pdf"))
    parte = ParteImportada.objects.create(importacao=arq, inicio=1, fim=1, sha256="f" * 64,
                                          arquivo=ContentFile(b"%PDF-1.4", "p.pdf"))
    texto = _cliente(op).get(reverse("viagens:revisar_importacao",
                                     args=[parte.pk])).content.decode()
    assert "Tipo e destino na revisão da importação" in texto
    assert reverse("assistencia:pedir", args=["viagens.importacao_tipo", parte.pk]) in texto


def test_entrada_na_leitura_do_comprovante(c):
    from gestao.viagens import anexos
    from gestao.viagens.models import PrestacaoServidor

    p = _p(c)
    ps = PrestacaoServidor.objects.filter(prestacao=p).order_by("pk").first()
    a = anexos.anexar(c.usuarios["operador"], p.pk, "comprovante", nome="c.pdf",
                      conteudo=b"%PDF-1.4" + bytes([10]) + b"%%EOF", servidor_pk=ps.pk)
    texto = _cliente(c.usuarios["operador"]).get(
        reverse("viagens:leitura_prestacao", args=[p.pk])).content.decode()
    assert reverse("assistencia:pedir", args=["viagens.leitura_comprovante", a.pk]) in texto
    assert "Ler o comprovante" in texto


def test_entrada_no_catalogo_de_atividades(c):
    from gestao.cadastros.models import AtividadePlano

    a = AtividadePlano.objects.create(codigo="TESTE_IA_V", nome="Atividade sem recurso",
                                      meta="Atender.", recurso="")
    texto = _cliente(c.usuarios["operador"]).get(
        reverse("cadastros:atividades")).content.decode()
    assert reverse("assistencia:pedir", args=["cadastros.atividade_complemento", a.pk]) in texto
    pedido = _cliente(c.usuarios["operador"]).get(
        reverse("assistencia:pedir", args=["cadastros.atividade_complemento", a.pk]))
    assert pedido.status_code == 200 and "Sugerir meta e recursos" in pedido.content.decode()


def test_entrada_no_relatorio_consolidado(c):
    texto = _cliente(c.usuarios["operador"]).get(reverse("painel:relatorios")).content.decode()
    assert "Nota executiva do mês" in texto
    passado = _cliente(c.usuarios["operador"]).get(reverse("painel:relatorios"),
                                                   {"ano": "todos"}).content.decode()
    assert "Nota executiva do mês" not in passado


def test_pedir_mostra_a_ultima_sugestao(c):
    p = _p(c)
    relatorio.obter(p)
    s = Sugestao.objects.get(pedido=servicos.pedir(c.usuarios["operador"], RT, p.pk))
    texto = _cliente(c.usuarios["operador"]).get(
        reverse("assistencia:pedir", args=[RT, p.pk])).content.decode()
    assert reverse("assistencia:sugestao", args=[s.pk]) in texto


def test_ui_lab_mostra_o_cartao_em_todos_os_estados(c):
    texto = _cliente(c.usuarios["operador"]).get(reverse("ui_lab:indice")).content.decode()
    assert 'id="sugestao-ia-lab"' in texto
    for estado in ("Redigindo", "Sugestão pronta", "Sugestão obsoleta", "Desligado",
                   "Por regra (AUT-50)", "Ofício · motivo da viagem"):
        assert estado in texto, estado


# ------------------------------------------------------------------ revisão: edição e atual
def _rt_com_texto_humano(c):
    p = _p(c)
    rt = relatorio.obter(p)
    relatorio.salvar(c.usuarios["operador"], rt.pk, {"motivo": "Escrito pela equipe."})
    s = Sugestao.objects.get(pedido=servicos.pedir(c.usuarios["operador"], RT, p.pk))
    return p, rt, s


def test_revisao_mostra_atual_ao_lado_do_sugerido_e_nomeia_o_que_muda(c):
    p, _, s = _rt_com_texto_humano(c)
    pagina = _cliente(c.usuarios["operador"]).get(
        reverse("assistencia:sugestao", args=[s.pk])).content.decode()
    assert "Atual" in pagina and "Sugerido" in pagina and "Escrito pela equipe." in pagina
    assert f"em RT · Ofício {p.oficio.numero_formatado}" in pagina
    assert "Substituir o texto atual de “Descrição do evento”" in pagina


def test_envio_que_falha_devolve_o_texto_editado_e_nao_a_sugestao(c):
    from gestao.assistencia.models import ConteudoSugestao

    p, _, s = _rt_com_texto_humano(c)
    original = next(i["valor"] for i in ConteudoSugestao.objects.get(sugestao=s).itens
                    if i["campo"] == "motivo")
    op = _cliente(c.usuarios["operador"])
    r = op.post(reverse("assistencia:aceitar", args=[s.pk]),
                {"texto-motivo": "Minha edição cuidadosa."})  # sem confirmar a substituição
    texto = r.content.decode()
    assert r.status_code == 409 and "Minha edição cuidadosa." in texto
    assert original not in texto and "Nada foi gravado" in texto
    assert relatorio.obter(p).motivo == "Escrito pela equipe."
    # Com a ação explícita de substituir, grava o texto editado.
    r = op.post(reverse("assistencia:aceitar", args=[s.pk]),
                {"texto-motivo": "Minha edição cuidadosa.", "substituir": "1"})
    assert r.status_code == 302 and relatorio.obter(p).motivo == "Minha edição cuidadosa."


def test_sugestao_obsoleta_no_envio_mostra_o_texto_editado_para_copiar(c):
    p, rt, s = _rt_com_texto_humano(c)
    relatorio.salvar(c.usuarios["operador"], rt.pk, {"conclusao": "Mudou enquanto revisava."})
    r = _cliente(c.usuarios["operador"]).post(
        reverse("assistencia:aceitar", args=[s.pk]),
        {"texto-motivo": "Texto que não pode se perder.", "substituir": "1"})
    texto = r.content.decode()
    assert r.status_code == 409 and "Seu texto editado (não gravado)" in texto
    assert "Texto que não pode se perder." in texto
    assert relatorio.obter(p).motivo == "Escrito pela equipe."


# ------------------------------------------------------------------ desempenho das telas
def test_usos_soma_as_chamadas_do_dia_numa_consulta_so(c):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    p = _p(c)
    relatorio.obter(p)
    servicos.pedir(c.usuarios["operador"], RT, p.pk)
    with CaptureQueriesContext(connection) as consultas:
        r = _cliente(_admin(c)).get(reverse("assistencia:usos"))
    assert r.status_code == 200
    somas = [q["sql"] for q in consultas.captured_queries
             if "tentativas_ia" in q["sql"] and "SUM(" in q["sql"].upper()]
    assert len(somas) == 1, somas


def test_get_do_painel_e_dos_usos_nao_grava_nada(c):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from gestao.assistencia.models import OrcamentoIA

    assert not OrcamentoIA.objects.exists()
    cliente = _cliente(_admin(c))
    with CaptureQueriesContext(connection) as consultas:
        for nome in ("assistencia:painel", "assistencia:usos"):
            assert cliente.get(reverse(nome)).status_code == 200
    escritas = [q["sql"] for q in consultas.captured_queries
                if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                and "assistencia_" in q["sql"]]
    assert escritas == [] and not OrcamentoIA.objects.exists()
    # Quem cria a linha do mês é a rotina diária (ou o primeiro caminho de escrita).
    from gestao.assistencia import manutencao

    manutencao.diaria()
    assert OrcamentoIA.objects.filter(escopo="global").exists()
