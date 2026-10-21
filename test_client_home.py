"""Landing directory regression checks."""
from client_home import render_client_home


def test_directory_actions_and_single_connect_control():
    page = render_client_home([{"id": 7, "cliente": "Loja Exemplo", "status": "ativa"}], admin=True)
    assert "href='/conectar'" not in page
    assert "Conectar loja" not in page
    assert "data-act='rename'" in page
    assert "data-act='up'" not in page and "data-act='down'" not in page
    assert "href='/excluir/7'" in page
    assert "href='/painel/7'" in page
    assert "/painel/tendencias" in page
    assert "localStorage" not in page
    assert "span.innerHTML=trend" in page
    assert "svg viewBox=" in page
    assert "stroke:currentColor" in page
    assert "<svg width='23'" in page


def test_directory_escapes_shop_names():
    page = render_client_home([{"id": 8, "cliente": "<script>alert(1)</script>", "status": "ativa"}], admin=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_directory_alphabetical_order():
    page = render_client_home([{'id':2,'cliente':'Zeta','status':'ativa'}, {'id':1,'cliente':'Alfa','status':'ativa'}], admin=True)
    assert page.index("href='/painel/1'") < page.index("href='/painel/2'")


def test_home_cards_show_separate_trend_summary_without_unverified_percentage():
    page = render_client_home([{'id':3, 'cliente':'Copas Ind', 'status':'ativa'}], admin=True)
    assert 'kh-card-bottom' in page
    assert 'FATURAMENTO · ÚLTIMOS 7 DIAS' in page
    assert 'kh-metric-value' in page
    assert 'Sinal de queda' in page and 'Sinal de crescimento' in page
    assert 'kh-card-go' in page
    assert 'Tendência indisponível' in page
    assert 'localStorage' not in page
