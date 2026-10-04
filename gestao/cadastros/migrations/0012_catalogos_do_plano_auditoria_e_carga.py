"""Catálogos do plano de trabalho: trilha de auditoria e carga inicial.

A carga é a da referência (programas, horários e as 11 atividades com meta e recurso) e é
idempotente: cada item só entra se ainda não existir; renomear ou desativar depois não
volta sozinho.
"""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela

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


def carregar(apps, schema_editor):
    Programa = apps.get_model("cadastros", "ProgramaSolicitante")
    Horario = apps.get_model("cadastros", "HorarioAtendimento")
    Atividade = apps.get_model("cadastros", "AtividadePlano")
    for nome in PROGRAMAS:
        if not Programa.objects.filter(nome__iexact=nome).exists():
            Programa.objects.create(nome=nome)
    for faixa in HORARIOS:
        if not Horario.objects.filter(nome__iexact=faixa).exists():
            Horario.objects.create(nome=faixa)
    for codigo, nome, meta, recurso in ATIVIDADES:
        Atividade.objects.get_or_create(codigo=codigo,
                                        defaults={"nome": nome, "meta": meta, "recurso": recurso})


class Migration(migrations.Migration):
    dependencies = [("cadastros", "0011_catalogos_do_plano")]

    operations = [
        auditar_tabela("cadastros_programasolicitante"),
        auditar_tabela("cadastros_horarioatendimento"),
        auditar_tabela("cadastros_atividadeplano"),
        auditar_tabela("cadastros_presetatividades"),
        auditar_tabela("cadastros_presetatividades_atividades"),
        migrations.RunPython(carregar, migrations.RunPython.noop),
    ]
