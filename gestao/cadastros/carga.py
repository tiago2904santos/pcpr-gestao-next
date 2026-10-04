"""Carga de dados de referência públicos (municípios do IBGE)."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

CSV_MUNICIPIOS = Path(__file__).resolve().parent / "dados" / "municipios_ibge.csv"
CSV_COORDENADAS = Path(__file__).resolve().parent / "dados" / "municipios_coordenadas.csv"


def linhas_municipios() -> list[dict[str, str]]:
    with CSV_MUNICIPIOS.open(encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def coordenadas() -> dict[str, tuple[Decimal, Decimal]]:
    with CSV_COORDENADAS.open(encoding="utf-8") as arquivo:
        return {linha["codigo_ibge"]: (Decimal(linha["latitude"]), Decimal(linha["longitude"]))
                for linha in csv.DictReader(arquivo, delimiter=";")}


def garantir_municipios(modelo=None) -> int:
    """Carrega a lista oficial se a tabela estiver vazia (com coordenadas). Retorna o total."""
    if modelo is None:
        from .models import Municipio as modelo
    if not modelo.objects.exists():
        # Na migração 0002 o modelo histórico ainda não tem coordenadas (vêm na 0003).
        com_coordenadas = any(f.name == "latitude" for f in modelo._meta.get_fields())
        coords = coordenadas() if com_coordenadas else {}

        def novo(linha: dict[str, str]):
            extra = {}
            if com_coordenadas:
                lat, lon = coords.get(linha["codigo_ibge"], (None, None))
                extra = {"latitude": lat, "longitude": lon}
            return modelo(codigo_ibge=linha["codigo_ibge"], nome=linha["nome"], uf=linha["uf"],
                          **extra)

        modelo.objects.bulk_create([novo(linha) for linha in linhas_municipios()],
                                   batch_size=2000, ignore_conflicts=True)
    return modelo.objects.count()


def preencher_coordenadas(modelo) -> int:
    """Completa latitude/longitude de municípios já carregados (migração)."""
    coords = coordenadas()
    faltando = list(modelo.objects.filter(latitude__isnull=True))
    for m in faltando:
        if m.codigo_ibge in coords:
            m.latitude, m.longitude = coords[m.codigo_ibge]
    modelo.objects.bulk_update(faltando, ["latitude", "longitude"], batch_size=2000)
    return len(faltando)


# ---------------------------------------------------------------- catálogos do plano de trabalho
# Carga inicial da referência (programas, horários e as 11 atividades com meta e recurso).
# Idempotente: só entra o que não existe; renomear ou desativar depois não volta sozinho.
# Usada pela migração 0012 e por quem recria a base (DEMO, testes que esvaziam o banco).
PROGRAMAS = ["PROGRAMA PARANÁ EM AÇÃO", "PROGRAMA JUSTIÇA NO BAIRRO", "PCPR NA COMUNIDADE"]

HORARIOS = ["09:00 até 17:00", "08:00 até 16:00", "10:00 até 18:00"]

ATIVIDADES = [
    ("CIN", "Confecção da Carteira de Identidade Nacional (CIN)",
     "Ampliar o acesso ao documento oficial de identificação civil, garantindo cidadania e "
     "inclusão social à população atendida.",
     "Kit de captura biométrica, estação de atendimento, conectividade e equipe técnica para "
     "triagem e emissão."),
    ("BO", "Registro de Boletins de Ocorrência",
     "Possibilitar o atendimento imediato de demandas policiais, promovendo orientação e "
     "formalização de ocorrências no próprio evento.",
     "Posto de atendimento com sistema de registro, insumos administrativos e equipe para "
     "orientação ao cidadão."),
    ("AAC", "Emissão de Atestado de Antecedentes Criminais",
     "Facilitar a obtenção do documento, contribuindo para fins trabalhistas e demais "
     "necessidades legais dos cidadãos.",
     "Terminal com acesso aos sistemas institucionais, impressão e equipe de apoio para "
     "validação de dados."),
    ("PALESTRAS", "Palestras e orientações preventivas",
     "Desenvolver ações educativas voltadas à prevenção de crimes, conscientização sobre "
     "segurança pública e fortalecimento do vínculo comunitário.",
     "Espaço para apresentação, sistema de áudio, material didático e equipe de facilitação."),
    ("LUDICO", "Atividades lúdicas e educativas para crianças",
     "Promover aproximação institucional de forma didática, incentivando a cultura de "
     "respeito às leis e à cidadania desde a infância.",
     "Materiais lúdicos, apoio pedagógico e área segura para dinâmicas com crianças."),
    ("NOC", "Apresentação do trabalho do Núcleo de Operações com Cães (NOC)",
     "Demonstrar as atividades operacionais desenvolvidas pela unidade especializada da "
     "Polícia Civil do Paraná, evidenciando técnicas e capacidades institucionais.",
     "Área controlada para exibição operacional, equipe especializada, equipamentos de "
     "segurança e suporte logístico."),
    ("TATICO", "Exposição de material tático",
     "Apresentar equipamentos utilizados nas atividades policiais, proporcionando "
     "transparência e conhecimento sobre os recursos empregados pela instituição.",
     "Bancadas de exposição, controle de acesso, equipe de apresentação e sinalização "
     "informativa."),
    ("PAPILOSCOPIA", "Exposição da atividade de perícia papiloscópica",
     "Demonstrar os procedimentos técnicos de identificação humana, ressaltando a importância "
     "da papiloscopia na investigação criminal e na identificação civil.",
     "Estação demonstrativa, kits de coleta, materiais visuais e equipe técnica especializada."),
    ("VIATURAS", "Exposição de viaturas antigas e modernas",
     "Apresentar a evolução histórica e tecnológica dos veículos operacionais da instituição.",
     "Área de exposição, apoio de segurança patrimonial e equipe para conduzir apresentações "
     "ao público."),
    ("BANDA", "Apresentação da banda institucional",
     "Fortalecer a integração com a comunidade por meio de atividade cultural representativa "
     "da instituição.",
     "Estrutura de palco, sonorização, logística de montagem e suporte técnico para "
     "apresentação musical."),
    ("UNIDADE_MOVEL", "Unidade móvel (ônibus ou caminhão)",
     "Viabilizar a prestação descentralizada dos serviços acima descritos, assegurando "
     "estrutura adequada para atendimento ao público.",
     "Unidade móvel institucional, equipe de operação, energia, conectividade e manutenção de "
     "suporte."),
]


def garantir_catalogos_do_plano(apps=None) -> None:
    """Programas, horários e atividades iniciais (com os modelos históricos numa migração)."""
    if apps is None:
        from .models import AtividadePlano, HorarioAtendimento, ProgramaSolicitante
        programa, horario, atividade = ProgramaSolicitante, HorarioAtendimento, AtividadePlano
    else:
        programa = apps.get_model("cadastros", "ProgramaSolicitante")
        horario = apps.get_model("cadastros", "HorarioAtendimento")
        atividade = apps.get_model("cadastros", "AtividadePlano")
    for nome in PROGRAMAS:
        if not programa.objects.filter(nome__iexact=nome).exists():
            programa.objects.create(nome=nome)
    for faixa in HORARIOS:
        if not horario.objects.filter(nome__iexact=faixa).exists():
            horario.objects.create(nome=faixa)
    for codigo, nome, meta, recurso in ATIVIDADES:
        atividade.objects.get_or_create(codigo=codigo,
                                        defaults={"nome": nome, "meta": meta, "recurso": recurso})

