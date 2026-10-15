"""Os modelos de OS que vêm com o sistema (caminhão, micro-ônibus, cerimonial e operação
policial): os textos da referência reescritos em etapas e funções. A migração os semeia e a
demonstração os usa; o gestor pode editá-los e desativá-los, não apagá-los."""

from __future__ import annotations

# Ícones que uma função pode ter (nome no sprite, rótulo na escolha).
ICONES_DE_FUNCAO: list[tuple[str, str]] = [
    ("car", "Carro"), ("truck", "Caminhão"), ("bus", "Micro-ônibus"),
    ("wrench", "Ferramenta"), ("hand-helping", "Mão que ajuda"),
    ("clipboard-list", "Prancheta"), ("package-check", "Caixa conferida"),
    ("camera", "Câmera"), ("video", "Filmadora"), ("mic", "Microfone"), ("headset", "Fone"),
    ("briefcase", "Maleta"), ("hard-hat", "Capacete"), ("clipboard-check", "Conferência"),
    ("shield-check", "Escudo"), ("star", "Estrela"), ("users", "Equipe"),
    ("map-pin", "Local"), ("monitor", "Monitor"), ("megaphone", "Megafone"),
]

_VOLTA = "Que a equipe efetue o retorno à sede de lotação em {sede} {data}."

MODELOS: list[dict] = [
    {
        "chave": "operacao_policial", "nome": "Operação policial", "ordem": 10,
        "referencia": "Deslocamento de Operação Policial",
        "ida": "O deslocamento {equipe} para {municipio} {data}.",
        "ida_e_antes": "",
        "antes": "",
        "evento": ("Que o policial {servidores} acompanhe o briefing da operação policial que "
                   "será realizado na cidade de {destino}, {hora} {data}, e permaneça no "
                   "município {data} para prestar assessoria de imprensa, conduzir o "
                   "atendimento aos veículos de comunicação e prestar suporte de comunicação "
                   "com relação à operação realizada."),
        "depois": ("Que o policial {servidores} permaneça em {destino} {data} para a "
                   "assessoria de imprensa pós-operação, incluindo a condução de entrevistas "
                   "coletivas e o atendimento às demandas dos veículos de comunicação."),
        "depois_e_volta": "",
        "volta": ("Que o policial {servidores} efetue o retorno à sede de lotação em {sede} "
                  "{data}."),
        "justificativas": "",
        "finalidade": "",
        "funcoes": [],
    },
    {
        "chave": "caminhao", "nome": "Caminhão", "ordem": 20,
        "referencia": "Deslocamento - Caminhão de apoio",
        "ida": ("O deslocamento {equipe} para {municipio} {data}, para apoio logístico com "
                "caminhão em {motivo}."),
        "ida_e_antes": ("O deslocamento {equipe} para {municipio} {data}, com a descarga, "
                        "montagem e conferência técnica da Unidade Móvel no mesmo dia, para "
                        "apoio logístico com caminhão em {motivo}."),
        "antes": ("Que a equipe realize {data} o traslado, descarga, montagem, conferência "
                  "técnica e adequação dos materiais e equipamentos no local do evento."),
        "evento": ("Que a equipe permaneça em {destino} {data} para a operação da Unidade "
                   "Móvel durante {motivo}."),
        "depois": ("Que a equipe realize {data} a desmontagem, conferência, acondicionamento e "
                   "carregamento dos materiais."),
        "depois_e_volta": ("Que a equipe realize {data} a desmontagem e o carregamento dos "
                           "materiais e efetue o retorno à sede de lotação em {sede}."),
        "volta": _VOLTA,
        "justificativas": (
            "O deslocamento do caminhão com antecedência faz-se necessário para viabilizar o "
            "traslado, descarga, montagem, conferência técnica e adequação dos materiais e "
            "equipamentos no local do evento.\n"
            "A permanência posterior ao evento justifica-se pela necessidade de desmontagem, "
            "conferência, acondicionamento, carregamento dos materiais e retorno do veículo "
            "com segurança, preservando os bens públicos utilizados."),
        "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir o planejamento, "
                       "a execução e a desmobilização do apoio logístico prestado com caminhão."),
        "funcoes": [
            {"codigo": "conducao", "nome": "Condução", "icone": "truck",
             "texto": ("Que {servidores} conduza a Unidade Móvel (caminhão), realizando o "
                       "deslocamento desde o local onde o veículo estiver estacionado até o "
                       "município de destino e, ao término das atividades, o retorno ao local "
                       "de guarda do veículo, computando-se todo o percurso. Caberá, ainda, "
                       "prestar apoio às atividades de instalação, posicionamento, operação e "
                       "desmontagem da estrutura da Unidade Móvel.")},
            {"codigo": "tecnico", "nome": "Técnico", "icone": "wrench",
             "texto": ("Que {servidores} preste apoio técnico na instalação, configuração, "
                       "testes e operação dos equipamentos de informática, rede lógica, "
                       "comunicação e demais sistemas utilizados durante os atendimentos. "
                       "Deverá deslocar-se antecipadamente ao local do evento para verificar "
                       "as condições de fornecimento de energia elétrica, conectividade de "
                       "internet e infraestrutura necessária ao funcionamento da Unidade "
                       "Móvel, considerando que, em razão da dinâmica da operação, não foi "
                       "possível a realização de visita técnica prévia.")},
            {"codigo": "apoio", "nome": "Apoio", "icone": "hand-helping",
             "texto": ("Que {servidores} realize a escolta e o apoio operacional da Unidade "
                       "Móvel durante todo o deslocamento entre {sede} e {destino}, bem como "
                       "no retorno, computando-se todo o trajeto. Deverá auxiliar na montagem, "
                       "organização, manutenção operacional e desmontagem dos equipamentos da "
                       "Unidade Móvel.")},
        ],
    },
    {
        "chave": "microonibus", "nome": "Micro-ônibus", "ordem": 30,
        "referencia": "Deslocamento - Micro-ônibus",
        "ida": ("O deslocamento {equipe} para {municipio} {data}, para apoio logístico com "
                "micro-ônibus em {motivo}."),
        "ida_e_antes": "",
        "antes": ("Que a equipe organize {data} os materiais e equipamentos no local da "
                  "atividade."),
        "evento": ("Que a equipe permaneça em {destino} {data} para o transporte e o apoio "
                   "logístico de {motivo}."),
        "depois": "Que a equipe recolha {data} os materiais utilizados na atividade.",
        "depois_e_volta": "",
        "volta": _VOLTA,
        "justificativas": (
            "O micro-ônibus será utilizado para transporte e apoio logístico da equipe, "
            "observando-se o cronograma da atividade."),
        "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir o transporte, a "
                       "organização e o apoio logístico necessários à realização da atividade."),
        "funcoes": [
            {"codigo": "conducao", "nome": "Condução", "icone": "bus",
             "texto": ("Que {servidores} conduza o micro-ônibus oficial durante os "
                       "deslocamentos de ida e retorno, zelando pela segurança da equipe e dos "
                       "passageiros.")},
            {"codigo": "tecnico", "nome": "Técnico", "icone": "wrench",
             "texto": ("Que {servidores} preste suporte técnico à operação dos equipamentos e "
                       "acompanhe a organização dos materiais utilizados na atividade.")},
            {"codigo": "apoio", "nome": "Apoio", "icone": "hand-helping",
             "texto": ("Que {servidores} preste apoio operacional à equipe, auxiliando na "
                       "organização, montagem, escolta e movimentação necessárias à "
                       "realização da atividade.")},
        ],
    },
    {
        "chave": "cerimonial", "nome": "Cerimonial", "ordem": 40,
        "referencia": "Deslocamento - Equipe de Cerimonial",
        "ida": ("O deslocamento {equipe} para {municipio} {data}, para atuação na organização "
                "e realização de {motivo}."),
        "ida_e_antes": ("O deslocamento {equipe} para {municipio} {data}, com a verificação da "
                        "estrutura do local no mesmo dia, para atuação na organização e "
                        "realização de {motivo}."),
        "antes": ("Que a equipe verifique {data} a estrutura do local, o sistema de "
                  "sonorização, a disposição do palco, púlpito, bandeiras, autoridades e "
                  "convidados, a decoração, os acessos e demais aspectos logísticos da "
                  "solenidade."),
        "evento": ("Que a equipe atue em {destino} {data} na organização e realização de "
                   "{motivo}."),
        "depois": "Que a equipe desmobilize {data} a estrutura e os materiais da solenidade.",
        "depois_e_volta": ("Que a equipe desmobilize {data} a estrutura da solenidade e efetue "
                           "o retorno à sede de lotação em {sede}."),
        "volta": _VOLTA,
        "justificativas": (
            "O deslocamento da equipe com antecedência faz-se necessário para o deslocamento "
            "até o município do evento e a organização dos trabalhos, em razão da "
            "inexistência de visita técnica prévia.\n"
            "A permanência da equipe permitirá verificar a estrutura do local, sistema de "
            "sonorização, disposição do palco, púlpito, bandeiras, autoridades e convidados, "
            "decoração, acessos e demais aspectos logísticos, possibilitando os ajustes "
            "necessários para assegurar a adequada realização da solenidade."),
        "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir o planejamento, "
                       "a organização e a execução das atividades de Cerimonial, assegurando o "
                       "cumprimento das normas de protocolo e a realização do evento "
                       "institucional com eficiência e observância aos padrões da Polícia "
                       "Civil do Paraná."),
        "funcoes": [
            {"codigo": "coordenacao", "nome": "Coordenação", "icone": "clipboard-list",
             "texto": ("Que {servidores} conduza o veículo oficial durante o deslocamento de "
                       "ida e retorno, bem como coordene as atividades de Cerimonial, "
                       "supervisionando os procedimentos protocolares, a recepção das "
                       "autoridades, a composição do dispositivo de honra e a execução do "
                       "roteiro oficial.")},
            {"codigo": "apoio", "nome": "Apoio", "icone": "hand-helping",
             "texto": ("Que {servidores} preste apoio às atividades de Cerimonial, auxiliando "
                       "na organização do ambiente, recepção das autoridades e execução dos "
                       "procedimentos protocolares.")},
            {"codigo": "preparacao", "nome": "Preparação", "icone": "package-check",
             "texto": ("Que {servidores} auxilie na preparação da solenidade, conferência dos "
                       "materiais, organização dos espaços e demais atividades necessárias à "
                       "realização do evento.")},
        ],
    },
]

# O tipo que a OS tinha antes dos modelos → a chave do modelo (migração 0053).
CHAVE_DO_TIPO = {"operacao_retorno_posterior": "operacao_policial", "caminhao": "caminhao",
                 "microonibus": "microonibus", "cerimonial_antecipado": "cerimonial"}


def semear(ModeloOS, FuncaoOS) -> dict[str, int]:
    """Cria os modelos do sistema que ainda não existem (idempotente). Recebe as classes
    para servir à migração (`apps.get_model`) e ao código normal."""
    pks: dict[str, int] = {}
    for dados in MODELOS:
        funcoes = dados["funcoes"]
        campos = {k: v for k, v in dados.items() if k != "funcoes"}
        modelo = ModeloOS.objects.filter(chave=dados["chave"]).first()
        if modelo is None:
            modelo = ModeloOS.objects.create(padrao_sistema=True, **campos)
            for ordem, f in enumerate(funcoes):
                FuncaoOS.objects.create(modelo=modelo, ordem=ordem, **f)
        pks[dados["chave"]] = modelo.pk
    return pks
