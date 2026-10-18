"""Regressões de escala, manutenção e autorização dos sete catálogos ASCOM."""

from __future__ import annotations

import json
import re
from time import perf_counter

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Servidor
from gestao.identidade.models import Usuario
from gestao.imprensa.models import Atendimento, Veiculo
from gestao.imprensa.models import Integrante as IntegranteImprensa
from gestao.palestras.forms import FormularioPalestrante
from gestao.palestras.models import Palestrante, RespostaPadrao, Tema
from gestao.publicacoes.models import Integrante as IntegrantePublicacoes
from gestao.publicacoes.models import Publicacao, UnidadeResponsavel

pytestmark = pytest.mark.django_db

CATALOGOS = [
    ("imprensa:equipe", IntegranteImprensa, "nome"),
    ("imprensa:veiculos", Veiculo, "nome"),
    ("publicacoes:equipe", IntegrantePublicacoes, "nome"),
    ("publicacoes:unidades", UnidadeResponsavel, "nome"),
    ("palestras:temas", Tema, "nome"),
    ("palestras:palestrantes", Palestrante, "nome"),
    ("palestras:respostas", RespostaPadrao, "tipo"),
]


@pytest.fixture
def gestor_ascom():
    user = Usuario.objects.create_user("gestor-ascom", "gestor@teste.invalid", None,
                                       nome="Gestor ASCOM")
    user.groups.set(Group.objects.filter(name__in=["ADMINISTRADOR", "ASCOM_PALESTRAS"]))
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.parametrize(("url_name", "modelo", "campo"), CATALOGOS)
def test_busca_paginacao_contagem_e_retorno(gestor_ascom, url_name, modelo, campo):
    for i in range(31):
        modelo.objects.create(**{campo: f"Cadastro exemplo {i:02d}"})
    alvo = modelo.objects.create(**{campo: "Nome longo & específico para busca"})
    url = reverse(url_name)
    resposta = gestor_ascom.get(url)
    assert resposta.status_code == 200
    assert len(resposta.context["registros"]) == 25
    assert resposta.context["page_obj"].paginator.count == 32
    assert len(gestor_ascom.get(url, {"pagina": 2}).context["registros"]) == 7
    filtrada = gestor_ascom.get(url, {"q": "& específico"})
    assert [r.pk for r in filtrada.context["registros"]] == [alvo.pk]
    assert "q=%26+espec%C3%ADfico" in filtrada.context["querystring_base"]
    vazia = gestor_ascom.get(url, {"q": "sem correspondência"})
    assert b"Nenhum resultado" in vazia.content
    assert vazia.context["page_obj"].paginator.count == 0
    dados = {campo: "Novo nome", "pk": alvo.pk}
    if modelo == Palestrante:
        dados = {"pk": alvo.pk, f"p{alvo.pk}-nome": "Novo nome"}
    if modelo == RespostaPadrao:
        dados["mensagem"] = "Olá {solicitante}"
    retorno = gestor_ascom.post(f"{url}?q=Cadastro&pagina=2", dados)
    assert retorno.status_code == 302
    assert retorno.url == f"{url}?q=Cadastro&pagina=2"


@pytest.mark.parametrize(("url_name", "modelo", "campo"), CATALOGOS)
@pytest.mark.parametrize("pk", ["²", "9" * 100, "nao-numero"])
def test_pk_malformado_nao_cria_nem_falha(gestor_ascom, url_name, modelo, campo, pk):
    resposta = gestor_ascom.post(reverse(url_name), {"pk": pk, campo: "Não incluir"})
    assert resposta.status_code == 404
    assert modelo.objects.count() == 0


def test_palestrante_mantem_servidor_inativo_atual():
    atual = Servidor.objects.create(nome="Servidor anterior", ativo=False)
    outro = Servidor.objects.create(nome="Outro inativo", ativo=False)
    palestrante = Palestrante.objects.create(nome="Palestrante vinculado", servidor=atual)
    form = FormularioPalestrante({"nome": "Nome revisado", "servidor": atual.pk},
                                 instance=palestrante)
    assert form.is_valid(), form.errors
    adulterado = FormularioPalestrante({"nome": "Nome revisado", "servidor": outro.pk},
                                       instance=palestrante)
    assert not adulterado.is_valid()
    assert "servidor" in adulterado.errors


def test_busca_servidores_palestras_limitada_sem_permissao_viagens(gestor_ascom, client):
    user = Usuario.objects.get(login="gestor-ascom")
    assert not user.has_perm("cadastros.view_servidor")
    Servidor.objects.bulk_create([Servidor(nome=f"Servidor sintético {i:03d}")
                                  for i in range(30)])
    escolhido = Servidor.objects.create(nome="ZZZ Pessoa localizada fora da primeira página")
    Servidor.objects.create(nome="Pessoa inativa não oferecida", ativo=False)
    url = reverse("palestras:buscar_servidores")
    primeira = gestor_ascom.get(url).json()["resultados"]
    assert len(primeira) == 15
    assert str(escolhido.pk) not in [r["id"] for r in primeira]
    achados = gestor_ascom.get(url, {"q": "Pessoa"}).json()["resultados"]
    assert [r["id"] for r in achados] == [str(escolhido.pk)]
    sem = Usuario.objects.create_user("busca-sem", "busca-sem@teste.invalid", None, nome="Sem")
    client.force_login(sem)
    assert client.get(url, {"q": "Pessoa"}).status_code == 403
    form = FormularioPalestrante(instance=Palestrante.objects.create(
        nome="Registro com pessoa atual", servidor=escolhido))
    html = str(form["servidor"])
    assert escolhido.nome in html
    assert "Servidor sintético 000" not in html
    assert 'data-fonte="/palestras/api/servidores/?q="' in html


def test_palestrantes_volume_sem_multiplicar_formularios(gestor_ascom):
    Servidor.objects.bulk_create([Servidor(nome=f"Servidor sintético {i:03d}")
                                  for i in range(120)])
    Palestrante.objects.bulk_create([Palestrante(nome=f"Palestrante sintético {i:03d}")
                                    for i in range(31)])
    inicio = perf_counter()
    with CaptureQueriesContext(connection) as consultas:
        resposta = gestor_ascom.get(reverse("palestras:palestrantes"))
    milissegundos = round((perf_counter() - inicio) * 1000, 2)
    consultas_servidor = sum('FROM "cadastros_servidor"' in c["sql"] for c in consultas)
    print(json.dumps({"cenario": "31 palestrantes / 120 servidores", "tempo_ms": milissegundos,
                      "consultas": len(consultas), "consultas_servidor": consultas_servidor,
                      "html_bytes": len(resposta.content)}, ensure_ascii=False))
    assert consultas_servidor <= 2
    assert len(resposta.context["registros"]) == 25
    assert re.search(rb'name="p\d+-nome"', resposta.content) is None
    atual = Palestrante.objects.first()
    editando = gestor_ascom.get(reverse("palestras:palestrantes"), {"editar": atual.pk})
    assert f'name="p{atual.pk}-nome"'.encode() in editando.content
    assert sum(hasattr(r, "form") for r in editando.context["registros"]) == 1


def test_erro_na_edicao_preserva_valores_e_cancelamento(gestor_ascom):
    registro = Palestrante.objects.create(nome="Pessoa já cadastrada")
    url = reverse("palestras:palestrantes")
    dados = {"pk": registro.pk, f"p{registro.pk}-nome": "",
             f"p{registro.pk}-lotacao": "Valor digitado a preservar"}
    resposta = gestor_ascom.post(url, dados)
    assert resposta.status_code == 200
    assert b"Valor digitado a preservar" in resposta.content
    assert b"Cancelar" in resposta.content
    assert resposta.context["editando"] == registro.pk
    registro.refresh_from_db()
    assert registro.nome == "Pessoa já cadastrada"


def test_excluir_palestrante_em_edicao_retorna_lista_sem_id_apagado(gestor_ascom):
    registro = Palestrante.objects.create(nome="Pessoa sem uso")
    url = reverse("palestras:palestrantes")
    resposta = gestor_ascom.post(f"{url}?editar={registro.pk}&q=Pessoa",
                                 {"acao": "excluir", "pk": registro.pk})
    assert resposta.status_code == 302
    assert resposta.url == f"{url}?q=Pessoa"
    assert not Palestrante.objects.filter(pk=registro.pk).exists()
    assert gestor_ascom.get(resposta.url).status_code == 200


def test_contagens_por_documento_preservam_multiplas_funcoes_sem_buscar_outros_registros():
    from gestao.imprensa import services as imprensa
    from gestao.publicacoes import services as publicacoes

    autor = Usuario.objects.create_user("autor-contagem", "autor@teste.invalid", None,
                                        nome="Autor dos documentos")
    um = IntegranteImprensa.objects.create(nome="Pessoa em duas funções")
    outro = IntegranteImprensa.objects.create(nome="Outra pessoa")
    Atendimento.objects.create(data=timezone.localdate(), jornalista="Jornalista", pedido="P",
                                responsavel=um, responsavel_resposta=um, criado_por=autor)
    Atendimento.objects.create(data=timezone.localdate(), jornalista="Jornalista", pedido="P",
                                responsavel=outro, responsavel_resposta=um, criado_por=autor)
    assert imprensa.usos_por_registro("equipe", [um.pk]) == {um.pk: 2}
    assert imprensa.usos_por_registro("equipe", [outro.pk]) == {outro.pk: 1}

    pessoa = IntegrantePublicacoes.objects.create(nome="Pessoa em três funções")
    unidade = UnidadeResponsavel.objects.create(nome="Unidade editorial")
    Publicacao.objects.create(data=timezone.localdate(), jornalista=pessoa, revisao=pessoa,
                               galeria_fotos=pessoa, unidade=unidade, titulo="Pauta de exemplo",
                               criado_por=autor)
    assert publicacoes.usos_por_registro("equipe", [pessoa.pk]) == {pessoa.pk: 1}


@pytest.mark.parametrize(("url_name", "modelo", "campo"), CATALOGOS)
def test_sem_permissao_get_post_continuam_protegidos(client, url_name, modelo, campo):
    sem = Usuario.objects.create_user("sem-acesso", "sem@teste.invalid", None, nome="Sem")
    client.force_login(sem)
    url = reverse(url_name)
    assert client.get(url, {"q": "nome", "pagina": 2}).status_code == 403
    assert client.post(url, {campo: "Não autorizado"}).status_code == 403
    assert modelo.objects.count() == 0
