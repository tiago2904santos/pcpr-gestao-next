"""CB7c: a leitura do e-mail de pedido (Python puro) — quantidade (produto, soma, extenso,
rótulo, correção; hora e data não viram quantidade), datas e períodos, horário do coffee,
campos com rótulo, município do PR e a digital do e-mail."""

from __future__ import annotations

from datetime import date, time

from gestao.coffee import dominio_email as d

HOJE = date(2026, 10, 6)
NOMES = {"curitiba": "Curitiba/PR", "sao jose dos pinhais": "São José dos Pinhais/PR",
         "toledo": "Toledo/PR", "campo largo": "Campo Largo/PR"}

EMAIL = """Assunto: Pedido de coffee break - Formatura do curso de investigação
Bom dia,
Solicitamos coffee break para a formatura, dia 14/10, às 15h30, no Auditório da 1ª SDP,
em São José dos Pinhais. Serão 2 turmas de 25 alunos.
Endereço: Rua XV de Novembro, 1234
Bairro: Centro
CEP 83005-000
Recebe: Escrivã Maria (41) 3000-0000
Atenciosamente"""


def test_quantidade():
    assert d.quantidade("Serão 2 turmas de 25 alunos").valor == 50
    assert d.quantidade("30 alunos + 10 instrutores").valor == 40
    assert d.quantidade("para quarenta e cinco pessoas").valor == 45
    assert d.quantidade("Quantidade: 25").valor == 25
    assert d.quantidade("mandar coffee para 30, obrigado").valor == 30
    assert d.quantidade("coffee para 30 pessoas. Corrigindo: serão 36 pessoas").valor == 36
    assert d.quantidade("reunião às 14h do dia 10/10, no 3º andar") is None
    assert d.quantidade("um coffee simples") is None
    assert d.quantidade("") is None


def test_datas_e_periodo():
    assert d.datas("dia 14/10", HOJE) == [date(2026, 10, 14)]
    assert d.datas("em 3 de novembro de 2026", HOJE) == [date(2026, 11, 3)]
    assert d.datas("de 14 a 16/10", HOJE) == [date(2026, 10, 14), date(2026, 10, 15),
                                              date(2026, 10, 16)]
    assert d.datas("dias 20 e 21 de outubro", HOJE) == [date(2026, 10, 20), date(2026, 10, 21)]
    assert d.datas("em 10/01", HOJE) == [date(2027, 1, 10)]  # sem ano e já passou: o próximo
    assert d.datas("31/02/2026 não existe", HOJE) == []


def test_horario_do_coffee():
    assert d.horario("a palestra começa às 14h e o coffee às 15:30") == time(15, 30)
    assert d.horario("evento às 9h") == time(9, 0)
    assert d.horario("sem hora") is None


def test_leitura_completa():
    leitura = d.ler(EMAIL, HOJE, NOMES)
    assert leitura.data == date(2026, 10, 14) and leitura.horario == time(15, 30)
    assert leitura.municipio == "São José dos Pinhais/PR"
    assert leitura.descricao == "Pedido de coffee break - Formatura do curso de investigação"
    assert leitura.quantidade and leitura.quantidade.valor == 50
    assert leitura.local == "Auditório da 1ª SDP"
    assert leitura.endereco == "Rua XV de Novembro, 1234" and leitura.bairro == "Centro"
    assert leitura.cep == "83005-000" and leitura.responsavel == "Escrivã Maria (41) 3000-0000"
    assert not leitura.vazia and d.ler("obrigado!", HOJE, NOMES).vazia


def test_municipio_preferido_e_digital():
    # "Campo Largo" (mais comprido e depois de "em") ganha de "Curitiba" citada no rodapé.
    texto = "Evento em Campo Largo dia 20/10.\nDelegacia de Curitiba"
    assert d.ler(texto, HOJE, NOMES).municipio == "Campo Largo/PR"
    assert d.impressao("Olá,  Coffee\n") == d.impressao("olá, coffee")
