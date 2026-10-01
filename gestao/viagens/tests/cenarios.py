"""Cenário fictício completo, usado por testes E2E e pelo `manage.py semear_dev`.

Todos os nomes, CPFs e placas são FICTÍCIOS (CPFs gerados com dígito válido).
Valores de diária: tabela pública vigente (Interior 290,55; Capital 371,26;
Brasília 468,12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.utils import timezone

from gestao.cadastros.carga import garantir_municipios
from gestao.cadastros.models import (
    Cargo,
    Combustivel,
    ConfiguracaoInstitucional,
    Lotacao,
    ModeloTexto,
    Municipio,
    Servidor,
    TabelaDiaria,
    Unidade,
    Viatura,
)
from gestao.identidade.models import Usuario
from gestao.identidade.papeis import sincronizar_papeis

NOMES = [
    "Ana Beatriz Correia Lima", "Bruno Henrique Martins", "Carla Regina Duarte",
    "Diego Fernandes Rocha", "Elaine Cristina Moraes", "Fábio Augusto Teixeira",
    "Gabriela Nunes Ribeiro", "Henrique Lopes Batista", "Isabela Prado Cavalcanti",
    "João Pedro Albuquerque", "Karen Lúcia Siqueira", "Leonardo Vieira Campos",
]


def cpf_ficticio(base: int) -> str:
    numeros = [int(c) for c in f"{base:09d}"]
    for tamanho in (9, 10):
        soma = sum(n * (tamanho + 1 - i) for i, n in enumerate(numeros[:tamanho]))
        numeros.append((soma * 10) % 11 % 10)
    return "".join(map(str, numeros))


@dataclass
class Cenario:
    ids: dict[str, int] = field(default_factory=dict)
    usuarios: dict[str, Usuario] = field(default_factory=dict)


def _municipio(nome: str, uf: str) -> Municipio:
    return Municipio.objects.get(nome=nome, uf=uf)


def _aware(dt: datetime) -> datetime:
    return timezone.make_aware(dt)


def cenario_completo(senha: str = "senha-local-123", hoje: date | None = None) -> Cenario:
    from gestao.viagens import services
    from gestao.viagens.models import Oficio

    hoje = hoje or timezone.localdate()
    garantir_municipios()
    sincronizar_papeis()
    c = Cenario()
    ascom = Unidade.objects.create(sigla="ASCOM", nome="Assessoria de Comunicação Social")
    dpc = Unidade.objects.create(sigla="DPC", nome="Divisão de Polícia da Capital")
    curitiba = _municipio("Curitiba", "PR")
    ConfiguracaoInstitucional.objects.create(
        unidade=ascom, nome_extenso="Assessoria de Comunicação Social", sede=curitiba,
        endereco_rodape="Assessoria de Comunicação Social - Rua Fictícia, 100 - Centro - "
                        "Curitiba/PR - CEP 80000-000 - (41) 3000-0000",
        chefia_nome="Marcos Antônio Pereira", chefia_cargo="Chefe da Assessoria de Comunicação",
        destinatario_nome="Dr. Roberto Carlos Mendes",
        destinatario_cargo="MD. Delegado-Geral Adjunto Administrativo",
        destinatario_orgao="Gabinete do Delegado-Geral Adjunto Administrativo",
    )
    ConfiguracaoInstitucional.objects.create(
        unidade=dpc, nome_extenso="Divisão de Polícia da Capital", sede=curitiba,
        endereco_rodape="Divisão de Polícia da Capital - Curitiba/PR",
        chefia_nome="Paula Andrade", chefia_cargo="Delegada Chefe",
        destinatario_nome="Dr. Roberto Carlos Mendes",
        destinatario_cargo="MD. Delegado-Geral Adjunto Administrativo",
        destinatario_orgao="Gabinete do Delegado-Geral Adjunto Administrativo",
    )
    agente = Cargo.objects.create(nome="Agente de Polícia Judiciária")
    escrivao = Cargo.objects.create(nome="Escrivão de Polícia")
    Cargo.objects.create(nome="Delegado de Polícia")
    gasolina = Combustivel.objects.create(nome="Gasolina")
    diesel = Combustivel.objects.create(nome="Diesel")
    servidores = []
    for i, nome in enumerate(NOMES):
        servidores.append(Servidor.objects.create(
            nome=nome, cpf=cpf_ficticio(123456700 + i), rg=f"{10_000_000 + i}-{i % 9}",
            cargo=agente if i % 3 else escrivao, unidade=ascom if i < 8 else dpc,
        ))
    master = Viatura.objects.create(placa="ABC1D23", modelo="Renault Master",
                                    combustivel=diesel,
                                    tipo=Viatura.Tipo.CARACTERIZADA, unidade=ascom)
    Viatura.objects.create(placa="XYZ9876", modelo="Renault Duster", combustivel=gasolina,
                           tipo=Viatura.Tipo.DESCARACTERIZADA, unidade=ascom)
    for faixa, valor in ((TabelaDiaria.Faixa.INTERIOR, "290.55"),
                         (TabelaDiaria.Faixa.CAPITAL, "371.26"),
                         (TabelaDiaria.Faixa.BRASILIA, "468.12")):
        TabelaDiaria.objects.create(faixa=faixa, vigente_desde=date(2000, 1, 1),
                                    valor_24h=Decimal(valor),
                                    norma="Decreto Estadual (tabela vigente)")
    ModeloTexto.objects.create(tipo=ModeloTexto.Tipo.MOTIVO, nome="Unidade móvel em evento",
                               texto="Apoio e condução da Unidade Móvel no evento.")
    ModeloTexto.objects.create(
        tipo=ModeloTexto.Tipo.JUSTIFICATIVA, nome="Convocação de última hora",
        texto="A convocação para o evento foi recebida com antecedência inferior ao prazo "
              "regulamentar, inviabilizando o encaminhamento da solicitação no prazo de 10 "
              "dias, sem prejuízo do interesse público na participação.",
    )

    def usuario(login, nome, papel, unidade):
        u = Usuario.objects.create_user(login, f"{login}@pc.pr.gov.br", senha, nome=nome)
        u.groups.add(Group.objects.get(name=papel))
        if unidade:
            Lotacao.objects.create(usuario=u, unidade=unidade)
        c.usuarios[login] = u
        return u

    operador = usuario("operador", "Operador de Testes", "OPERADOR_VIAGENS", ascom)
    usuario("gestor", "Gestora de Viagens", "GESTOR_VIAGENS", ascom)
    usuario("consulta", "Usuário de Consulta", "CONSULTA", None)
    usuario("outra", "Operadora da DPC", "OPERADOR_VIAGENS", dpc)

    destino_interior = _municipio("Arapongas", "PR")

    def roteiro(dias_ate_saida, duracao_dias, destino=destino_interior):
        saida = _aware(datetime.combine(hoje + timedelta(days=dias_ate_saida),
                                        datetime.min.time()).replace(hour=9))
        chegada = saida + timedelta(hours=7, minutes=30)
        volta = saida + timedelta(days=duracao_dias)
        return [
            services.TrechoInformado(curitiba.pk, destino.pk, saida, chegada),
            services.TrechoInformado(destino.pk, curitiba.pk, volta, volta + timedelta(hours=7,
                                                                                     minutes=30)),
        ]

    # 1. Emitido, no prazo, dois servidores (um motorista), viatura.
    emitido = services.criar_rascunho(operador, data_oficio=hoje)
    emitido = services.salvar_dados(emitido, operador, {
        "protocolo": "266554346", "motivo": "Apoio e condução da Unidade Móvel no evento "
        "Expoara.", "viatura": master})
    for s in servidores[:2]:
        services.adicionar_viajante(emitido, operador, s)
    services.definir_motorista(emitido, operador, emitido.viajantes.last().pk)
    services.salvar_trechos(emitido, operador, roteiro(20, 4))
    emitido.refresh_from_db()
    services.emitir(emitido, operador)
    c.ids["oficio_emitido"] = emitido.pk

    # 2. Rascunho fora do prazo (precisa de justificativa), um servidor.
    rascunho = services.criar_rascunho(operador, data_oficio=hoje)
    rascunho = services.salvar_dados(rascunho, operador, {
        "motivo": "Cobertura jornalística de operação no interior.", "viatura": master})
    services.adicionar_viajante(rascunho, operador, servidores[2])
    services.definir_motorista(rascunho, operador, rascunho.viajantes.first().pk)
    services.salvar_trechos(rascunho, operador, roteiro(3, 2, _municipio("Maringá", "PR")))
    c.ids["oficio_rascunho"] = rascunho.pk

    # 3. Rascunho vazio (recém-criado).
    vazio = services.criar_rascunho(operador, data_oficio=hoje)
    c.ids["oficio_vazio"] = vazio.pk

    # 4. Cancelado (capital, outro estado).
    cancelado = services.criar_rascunho(operador, data_oficio=hoje)
    cancelado = services.salvar_dados(cancelado, operador, {
        "motivo": "Participação em seminário nacional.", "tipo_transporte": "outro",
        "transporte_descricao": "Ônibus de linha"})
    services.adicionar_viajante(cancelado, operador, servidores[3])
    services.salvar_trechos(cancelado, operador, roteiro(30, 3, _municipio("São Paulo", "SP")))
    services.cancelar(cancelado, c.usuarios["gestor"], "Evento adiado pela organização.")
    c.ids["oficio_cancelado"] = cancelado.pk

    # 5. Ofício de outra unidade (não visível ao operador da ASCOM).
    outra = services.criar_rascunho(c.usuarios["outra"], data_oficio=hoje)
    c.ids["oficio_outra_unidade"] = outra.pk
    assert Oficio.objects.count() == 5
    return c
