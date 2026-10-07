"""Data efetiva de emissão, sem depender de relógio ou persistência."""

from datetime import date


def data_da_emissao(data_salva: date, hoje: date, *, manual: bool, ano: int) -> date:
    final = data_salva if manual else hoje
    if final.year != ano:
        raise ValueError(
            f"A data da emissão deve estar em {ano}. Crie um ofício no ano atual "
            "ou escolha manualmente uma data válida para este número.")
    return final
