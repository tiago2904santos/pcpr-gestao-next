"""Dataset DEMO do PREVIEW: determinístico, idempotente, coerente e 100% fictício (ADR 0011)."""

from __future__ import annotations

import hashlib
from datetime import date

import pytest
from django.core.management import call_command
from django.test import override_settings

from gestao.cadastros.models import ConfiguracaoInstitucional, Servidor, Viatura
from gestao.cadastros.validacoes import cpf_valido, placa_valida
from gestao.identidade.backends import LOGIN_DEMO
from gestao.identidade.models import Usuario
from gestao.plataforma.ambiente import OperacaoBloqueadaPorAmbiente
from gestao.viagens import demonstracao, services
from gestao.viagens.models import Documento, Historico, LacunaNumeracao, Oficio

pytestmark = pytest.mark.django_db(transaction=True)

HOJE = date(2026, 10, 1)
ESCALA = 0.15  # ~39 ofícios: rápido o bastante para a suíte, variado o bastante para provar

# SHA-256 (minúsculas, espaços normalizados) dos dados reais que já estiveram no histórico
# do Git — nomes de servidores, placa, protocolo e login. Só os hashes ficam no repositório.
HASHES_DE_DADOS_REAIS = {
    "0a3bfdb3a669c601d8de063b584c05a69d14465986f7edb7173f67ebf72da966",
    "0a282b57c110d43f63d0d7ade7738b0488fe2328fb35f2e9b4a6b95a41307dcc",
    "02f368051fb7438007181580fbd45749851b55480ab4233de3711d44c7dac689",
    "c509177521922fc0dc7d5ed53dc517b34ce6b4120f1789eb0a28f85563a95c96",
    "8853e264924178afe31b7a494fa9ddf009b16d8fb4b72fb5c1dd59a7b0ec9605",
    "0e2416c2abe27d6d2db32ea9281a6497fdd1e75a56a9c6545adea6aad30abd3d",
    "5587c5a3e28e9ca496670150982fb7d9202cdae655052cee213287d4b4d0a16e",
    "954a77f57fb14df289ad4765fac7a75e731b294687025bc204dbb2e7f37f3c7d",
    "144d4e4b026dccb05a3c529295cf47de18c9d2847154e0a867f28e43b0c9869b",
    "df05fc85e496fd6c5d6e19c6d96f653a98612db0deb218d9ac09c9ec3beda81f",
    "16a0515972ab78d3dad453f31779c5fc9a186021caa0095630d3812cb8aab924",
    "e3184df8be285233b773f5b13c0bb3ddbb70cb9b4a1211137baa23922e98a94e",
    "e6a9d353bd1b21fb49a795a25ca133ee1cfd77002338aa7edf85ce162df8febf",
}


def _hash(valor: str) -> str:
    return hashlib.sha256(" ".join(valor.lower().split()).encode()).hexdigest()


@pytest.fixture
def dataset():
    return demonstracao.semear(hoje=HOJE, escala=ESCALA)


def test_seed_e_deterministico_e_idempotente(dataset):
    primeira = demonstracao.impressao_digital()
    contagens = demonstracao.resumo().contagens
    demonstracao.semear(hoje=HOJE, escala=ESCALA)
    demonstracao.semear(hoje=HOJE, escala=ESCALA)
    assert demonstracao.impressao_digital() == primeira
    assert demonstracao.resumo().contagens == contagens  # sem duplicações
    assert Usuario.objects.filter(login=LOGIN_DEMO).count() == 1


def test_mesmo_dia_em_horarios_diferentes_gera_o_mesmo_dataset(monkeypatch):
    from datetime import datetime

    from django.utils import timezone

    impressoes = []
    for hora in (7, 23):
        instante = timezone.make_aware(datetime(2026, 10, 1, hora, 30))
        monkeypatch.setattr(timezone, "now", lambda instante=instante: instante)
        demonstracao.semear(hoje=HOJE, escala=ESCALA)
        impressoes.append(demonstracao.impressao_digital())
    assert impressoes[0] == impressoes[1]


def test_dataset_tem_variedade_para_avaliar_a_interface(dataset):
    situacoes = set(Oficio.objects.values_list("situacao", flat=True))
    assert situacoes == {"rascunho", "emitido", "cancelado"}
    assert Oficio.objects.values("ano").distinct().count() >= 2  # anos anteriores e atual
    assert Oficio.objects.values("unidade").distinct().count() >= 10
    assert Oficio.objects.filter(justificativa__gt="").exists()
    assert LacunaNumeracao.objects.exists()  # rascunhos excluídos liberaram números (D5)
    tamanhos = {o.viajantes.count() for o in Oficio.objects.all()}
    assert 1 in tamanhos and max(tamanhos) >= 4
    assert Servidor.objects.count() >= 50 and Viatura.objects.count() >= 12
    demo = Usuario.objects.get(login=LOGIN_DEMO)
    assert demo.nome == "Operador de Demonstração" and demo.has_perm("viagens.emitir_oficio")
    assert demo.has_perm("viagens.ver_todas_unidades") and not demo.has_usable_password()


def test_dataset_e_coerente_com_as_regras(dataset):
    for oficio in Oficio.objects.filter(situacao="emitido"):
        assert oficio.protocolo  # D1
        assert oficio.diarias_total == services.calcular(oficio).total
        assert oficio.documentos.filter(tipo=Documento.Tipo.OFICIO).exists()
        prazo = services.avaliar_prazo_do_oficio(oficio)
        assert not prazo.justificativa_obrigatoria or oficio.justificativa.strip()
    for oficio in Oficio.objects.all():
        eventos = list(oficio.historico.order_by("pk").values_list("acao", "em"))
        assert eventos[0][0] == Historico.Acao.CRIADO
        assert [em for _, em in eventos] == sorted(em for _, em in eventos)  # linha do tempo
        if oficio.situacao == "emitido":
            assert Historico.Acao.EMITIDO in {a for a, _ in eventos}


def test_dataset_e_ficticio(dataset):
    for servidor in Servidor.objects.all():
        assert not cpf_valido(servidor.cpf), "CPF DEMO precisa ter dígito inválido"
        assert _hash(servidor.nome) not in HASHES_DE_DADOS_REAIS
    for viatura in Viatura.objects.all():
        assert viatura.placa.startswith("ZZ") and placa_valida(viatura.placa)
        assert _hash(viatura.placa) not in HASHES_DE_DADOS_REAIS
    for protocolo in Oficio.objects.exclude(protocolo="").values_list("protocolo", flat=True):
        assert protocolo.startswith("00") and _hash(protocolo) not in HASHES_DE_DADOS_REAIS
    for usuario in Usuario.objects.all():
        assert usuario.email.endswith(".invalid")
        assert _hash(usuario.nome) not in HASHES_DE_DADOS_REAIS
        assert _hash(usuario.login) not in HASHES_DE_DADOS_REAIS
    for config in ConfiguracaoInstitucional.objects.all():
        for nome in (config.chefia_nome, config.destinatario_nome):
            assert _hash(nome) not in HASHES_DE_DADOS_REAIS


@pytest.mark.parametrize("app_env", ["production", "staging", "dev", "lab"])
@pytest.mark.parametrize("comando", ["semear_demo", "resetar_demo"])
def test_comandos_demo_recusam_fora_do_preview(app_env, comando):
    with override_settings(APP_ENV=app_env), pytest.raises(OperacaoBloqueadaPorAmbiente):
        call_command(comando, escala=0.05, sem_documentos=True)


def test_resetar_demo_recria_base_limpa():
    Usuario.objects.create_user("intruso", "intruso@demo.invalid", None, nome="Sobra")
    call_command("resetar_demo", escala=0.05, sem_documentos=True)
    assert not Usuario.objects.filter(login="intruso").exists()
    assert Usuario.objects.filter(login=LOGIN_DEMO).exists()
    assert Oficio.objects.count() >= 10
