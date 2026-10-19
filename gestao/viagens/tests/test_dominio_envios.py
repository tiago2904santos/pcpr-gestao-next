from urllib.parse import parse_qs, urlparse

from gestao.viagens.dominio.envios import mensagem, telefone_whatsapp, url_whatsapp


def test_numero_nacional_e_internacional_sem_duplicar_55():
    assert telefone_whatsapp("(41) 99999-0001") == "5541999990001"
    assert telefone_whatsapp("+55 41 99999-0001") == "5541999990001"
    assert telefone_whatsapp("999") == ""


def test_uma_mensagem_explicando_cada_item_preserva_links_e_acentos():
    itens = [("Ofício", "confira a viagem", "https://exemplo.test/p/a/oficio/"),
             ("RT", "confira e assine", "https://exemplo.test/p/a/rt/"),
             ("KM", "preencha o diário", "https://exemplo.test/p/b/")]
    texto = mensagem("João", "12/2026", "liberadas; prazo 20/10/2026", itens)
    url = url_whatsapp("5541999990001", texto)
    assert parse_qs(urlparse(url).query)["text"] == [texto]
    assert texto.count("Saque das diárias:") == 1
    assert all(texto.count(link) == 1 for _, _, link in itens)
    assert url_whatsapp("", texto) == ""
