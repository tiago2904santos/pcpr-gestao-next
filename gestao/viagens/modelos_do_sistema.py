"""Os tipos de OS (além da OS padrão, que não tem modelo): operação policial, unidade móvel
(micro-ônibus, ônibus, caminhão ou van: a mesma OS) e cerimonial — textos por etapa da viagem
e funções da equipe. São fixos: não há cadastro na tela; mudar um texto é mudar aqui e
sincronizar numa migração (`sincronizar`)."""

from __future__ import annotations

# Concordância: "{singular|plural}" escolhe a forma pelo número de pessoas do item — na função,
# quem a tem; na etapa, a equipe toda (dominio.modelo_os.concordar). {equipe} na função lista só
# quem tem a função, com o cargo ("do agente de polícia judiciária Fulano").

# Unidade móvel: depois do DETERMINO, o deslocamento de cada um com a sua função;
# depois os dias — deslocamento, montagem, participação no evento, desmontagem e volta.
UNIDADE_MOVEL = "unidade_movel"  # a OS da viatura unidade móvel (ordens.tipo_sugerido)
_FUNCAO = "O deslocamento {equipe}, na função de "
_VOLTA = "Que a equipe realize {data} o deslocamento de volta à sede de lotação em {sede}."

MODELOS: list[dict] = [
    {
        "chave": "operacao_policial", "nome": "Operação policial", "ordem": 10,
        "referencia": "Deslocamento de Operação Policial",
        "ida": "O deslocamento {equipe} para {municipio} {data}.",
        "ida_e_antes": "",
        "antes": "",
        "evento": ("Que {o policial|os policiais} {servidores} {acompanhe|acompanhem} o briefing "
                   "da operação policial que será realizado na cidade de {destino}, {hora} "
                   "{data}, e {permaneça|permaneçam} no município {data} para prestar "
                   "assessoria de imprensa, conduzir o atendimento aos veículos de comunicação "
                   "e prestar suporte de comunicação com relação à operação realizada."),
        "depois": ("Que {o policial|os policiais} {servidores} {permaneça|permaneçam} em "
                   "{destino} {data} para a assessoria de imprensa pós-operação, incluindo a "
                   "condução de entrevistas coletivas e o atendimento às demandas dos veículos "
                   "de comunicação."),
        "depois_e_volta": "",
        "volta": ("Que {o policial|os policiais} {servidores} {efetue|efetuem} o retorno à sede "
                  "de lotação em {sede} {data}."),
        "justificativas": "",
        "finalidade": "",
        "funcoes": [],
    },
    {
        "chave": "unidade_movel", "nome": "Unidade móvel", "ordem": 20,
        "referencia": "Deslocamento - Unidade Móvel",
        "ida": ("Que a equipe realize {data} o deslocamento até {municipio}, para apoio "
                "logístico com a Unidade Móvel em {motivo}."),
        "ida_e_antes": ("Que a equipe realize {data} o deslocamento até {municipio} e a "
                        "montagem da Unidade Móvel no local do evento, para apoio logístico "
                        "em {motivo}."),
        "antes": ("Que a equipe realize {data} a montagem da Unidade Móvel, com o traslado, a "
                  "descarga, a conferência técnica e a adequação dos materiais e equipamentos "
                  "no local do evento."),
        "evento": ("Que a equipe participe {data} do evento em {destino}, operando a Unidade "
                   "Móvel durante {motivo}."),
        "depois": ("Que a equipe realize {data} a desmontagem da Unidade Móvel, com a "
                   "conferência, o acondicionamento e o carregamento dos materiais."),
        "depois_e_volta": ("Que a equipe realize {data} a desmontagem da Unidade Móvel e o "
                           "deslocamento de volta à sede de lotação em {sede}."),
        "volta": _VOLTA,
        "justificativas": (
            "O deslocamento da Unidade Móvel com antecedência faz-se necessário para viabilizar "
            "o traslado, descarga, montagem, conferência técnica e adequação dos materiais e "
            "equipamentos no local do evento.\n"
            "A permanência posterior ao evento justifica-se pela necessidade de desmontagem, "
            "conferência, acondicionamento, carregamento dos materiais e retorno do veículo "
            "com segurança, preservando os bens públicos utilizados."),
        "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir o planejamento, "
                       "a execução e a desmobilização do apoio logístico prestado com a Unidade "
                       "Móvel."),
        "funcoes": [
            {"codigo": "conducao", "nome": "Condução", "icone": "bus",
             "texto": (_FUNCAO + "{condutor|condutores} da Unidade Móvel, "
                       "{responsável|responsáveis} pelo deslocamento desde o local onde o "
                       "veículo estiver estacionado até o município de destino e, ao término "
                       "das atividades, pelo retorno ao local de guarda do veículo, "
                       "computando-se todo o percurso, cabendo-{lhe|lhes}, ainda, prestar apoio "
                       "às atividades de instalação, posicionamento, operação e desmontagem da "
                       "estrutura da Unidade Móvel.")},
            {"codigo": "tecnico", "nome": "Técnico", "icone": "wrench",
             "texto": (_FUNCAO + "{técnico|técnicos}, {responsável|responsáveis} pelo apoio "
                       "técnico na instalação, configuração, testes e operação dos equipamentos "
                       "de informática, rede lógica, comunicação e demais sistemas utilizados "
                       "durante os atendimentos, devendo verificar antecipadamente, no "
                       "local do evento, as condições de fornecimento de energia elétrica, "
                       "conectividade de internet e infraestrutura necessária ao funcionamento "
                       "da Unidade Móvel, considerando que, em razão da dinâmica da operação, "
                       "não foi possível a realização de visita técnica prévia.")},
            {"codigo": "apoio", "nome": "Apoio", "icone": "hand-helping",
             "texto": (_FUNCAO + "apoio, {responsável|responsáveis} pela escolta e pelo apoio "
                       "operacional da Unidade Móvel durante todo o deslocamento entre {sede} e "
                       "{destino}, bem como no retorno, computando-se todo o trajeto, e pelo "
                       "auxílio na montagem, organização, manutenção operacional e desmontagem "
                       "dos equipamentos da Unidade Móvel.")},
        ],
    },
    {
        "chave": "cerimonial", "nome": "Cerimonial", "ordem": 40,
        "referencia": "Deslocamento - Equipe de Cerimonial",
        "ida": ("O deslocamento {equipe} para {municipio} {data}, para atuação na organização "
                "e realização de {motivo}."),
        "ida_e_antes": ("O deslocamento {equipe} para {municipio} {data}, com a visita técnica "
                        "ao local do evento no mesmo dia, para atuação na organização e "
                        "realização de {motivo}."),
        "antes": ("Que a equipe realize {data} a visita técnica ao local do evento, verificando "
                  "a estrutura, o sistema de sonorização, a disposição do palco, púlpito, "
                  "bandeiras, autoridades e convidados, a decoração, os acessos e demais "
                  "aspectos logísticos da solenidade."),
        "evento": ("Que a equipe atue em {destino} {data} na organização e realização de "
                   "{motivo}."),
        "depois": "Que a equipe desmobilize {data} a estrutura e os materiais da solenidade.",
        "depois_e_volta": ("Que a equipe desmobilize {data} a estrutura da solenidade e efetue "
                           "o retorno à sede de lotação em {sede}."),
        "volta": "Que a equipe efetue o retorno à sede de lotação em {sede} {data}.",
        "justificativas": (
            "O deslocamento da equipe com antecedência faz-se necessário para a realização da "
            "visita técnica ao local do evento e a organização dos trabalhos antes da "
            "solenidade.\n"
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
             "texto": ("Que {servidores} {conduza|conduzam} o veículo oficial durante o "
                       "deslocamento de ida e retorno, bem como {coordene|coordenem} as "
                       "atividades de Cerimonial, supervisionando os procedimentos "
                       "protocolares, a recepção das autoridades, a composição do dispositivo "
                       "de honra e a execução do roteiro oficial.")},
            {"codigo": "apoio", "nome": "Apoio", "icone": "hand-helping",
             "texto": ("Que {servidores} {preste|prestem} apoio às atividades de Cerimonial, "
                       "auxiliando na organização do ambiente, recepção das autoridades e "
                       "execução dos procedimentos protocolares.")},
            {"codigo": "preparacao", "nome": "Preparação", "icone": "package-check",
             "texto": ("Que {servidores} {auxilie|auxiliem} na preparação da solenidade, "
                       "conferência dos materiais, organização dos espaços e demais atividades "
                       "necessárias à realização do evento.")},
        ],
    },
]

# O tipo que a OS tinha antes dos modelos → a chave do modelo (migração 0053).
CHAVE_DO_TIPO = {"operacao_retorno_posterior": "operacao_policial",
                 "caminhao": "unidade_movel", "microonibus": "unidade_movel",
                 "cerimonial_antecipado": "cerimonial"}

# Tipos que viraram outro (migração 0056): micro-ônibus e caminhão são a mesma OS agora.
JUNTADOS = {"caminhao": "unidade_movel", "microonibus": "unidade_movel"}


def juntar(ModeloOS, OrdemServico) -> None:
    """Leva as OS dos tipos juntados para o tipo novo e apaga os antigos. O primeiro antigo
    encontrado vira o novo (mesmo registro), se o novo ainda não existe."""
    for antiga, nova in JUNTADOS.items():
        velho = ModeloOS.objects.filter(chave=antiga).first()
        if velho is None:
            continue
        destino = ModeloOS.objects.filter(chave=nova).first()
        if destino is None:
            # O nome é único: o texto e o nome certos vêm do `sincronizar` logo depois.
            ModeloOS.objects.filter(pk=velho.pk).update(chave=nova, nome=f"__{nova}")
            continue
        OrdemServico.objects.filter(modelo_id=velho.pk).update(modelo_id=destino.pk)
        velho.delete()


def semear(ModeloOS, FuncaoOS) -> dict[str, int]:
    """Cria os tipos que ainda não existem (idempotente; a migração 0053 o usa)."""
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


def sincronizar(ModeloOS, FuncaoOS) -> dict[str, int]:
    """Deixa os tipos gravados iguais aos daqui (nome, ordem, textos e funções): sem
    cadastro, o código é a fonte. Funções que saíram do tipo são apagadas só se nenhuma OS
    as usa; as OS antigas continuam apontando para os mesmos códigos."""
    pks = semear(ModeloOS, FuncaoOS)
    for dados in MODELOS:
        campos = {k: v for k, v in dados.items() if k not in ("funcoes", "chave")}
        ModeloOS.objects.filter(pk=pks[dados["chave"]]).update(
            ativo=True, padrao_sistema=True, **campos)
        codigos = []
        for ordem, f in enumerate(dados["funcoes"]):
            FuncaoOS.objects.update_or_create(
                modelo_id=pks[dados["chave"]], codigo=f["codigo"],
                defaults={"nome": f["nome"], "icone": f["icone"], "texto": f["texto"],
                          "ordem": ordem})
            codigos.append(f["codigo"])
        FuncaoOS.objects.filter(modelo_id=pks[dados["chave"]]).exclude(
            codigo__in=codigos).delete()
    return pks
