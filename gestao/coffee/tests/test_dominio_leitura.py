"""Leitura da nota fiscal e da ordem bancária pelo texto (CB5b)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from gestao.coffee import dominio_leitura as d

# Chave fictícia: UF 41, 26/09, CNPJ 11222333000181, modelo 55, série 001, nº 000008957.
CHAVE = "41260911222333000181550010000089571000000017"


def test_nota_pela_chave_de_acesso():
    texto = (f"DANFE ... CHAVE DE ACESSO {' '.join(CHAVE[i:i + 4] for i in range(0, 44, 4))} "
             "DATA DA EMISSÃO 26/09/2026 ... VALOR TOTAL DA NOTA 842,80")
    n = d.ler_nota(texto)
    assert n.numero == "8957" and n.cnpj == "11222333000181"
    assert n.valor == Decimal("842.80") and n.emissao == date(2026, 9, 26)


def test_nota_pelo_danfe_e_pela_nfse():
    assert d.ler_nota("DANFE Nº 000.008.958 Série 1").numero == "8958"
    nfse = ("NFS-e  Número da NFS-e: 1234  Data e Hora de Emissão 01/10/2026 10:00  "
            "PRESTADOR DE SERVIÇOS Razão: Buffet CNPJ: 44.555.666/0001-72  "
            "Valor Líquido da NFS-e R$ 1.110,00")
    n = d.ler_nota(nfse)
    assert (n.numero, n.cnpj, n.valor) == ("1234", "44555666000172", Decimal("1110.00"))
    assert d.ler_nota("nada aqui") == d.Nota()


def test_ob_e_avisos():
    ob = d.ler_ob("Ordem Bancária 2026OB012345 Data de Emissão 05/10/2026 Valor 842,80")
    assert ob == d.OrdemBancaria("2026OB012345", date(2026, 10, 5), Decimal("842.80"))
    nota = d.Nota("8957", "44555666000172", Decimal("900.00"), date(2026, 9, 20))
    avisos = d.avisos_da_nota(nota, cnpj_fornecedor="11222333000181", razao="Buffet",
                              cnpj_formatado="11.222.333/0001-81", quantidade=40,
                              unitario=Decimal("21.07"), data_evento=date(2026, 9, 26),
                              repetida_em="OS 3/2026")
    assert "emitida pelo CNPJ 44.555.666/0001-72" in avisos[0]
    assert "40 pessoas × R$ 21,07 = R$ 842,80" in avisos[1]
    assert "antes do evento" in avisos[2] and "já está na OS 3/2026" in avisos[3]
    assert d.aviso_da_ob(Decimal("800"), Decimal("842.80")).startswith(
        "O valor da ordem bancária (R$ 800,00)")
    assert d.aviso_da_ob(Decimal("842.80"), Decimal("842.80")) == ""
