"""Regression checks for home navigation and header security placement."""
import html
from client_home import render_client_home
from test_listing_details import main_function


def page(admin=True, home=True):
    render = main_function('pagina', dict(session={'tipo': 'admin' if admin else 'cliente'},
        esc=html.escape, CSS='', VISUAL_CSS='', SCRIPT='', img_logo=lambda size: ''))
    return render('Lojas', render_client_home([], admin=admin) if home else '<p>Outra página</p>')


def test_home_has_sidebar_and_security_only_in_footer():
    rendered = page()
    assert "aria-controls='ks-navigation'" in rendered
    assert "href='/painel/analise' title='Relatórios consolidados'" in rendered
    assert "aria-current='page' title='Minhas lojas'" in rendered
    assert "href='/crm' title='CRM e leads'" in rendered
    assert rendered.count("href='/seguranca'") == 1
    assert "<footer class='ks-foot'><a href='/seguranca'" in rendered
    header = rendered.split("<div class='top'>", 1)[1].split("<div class='wrap'>", 1)[0]
    assert '/seguranca' not in header
    assert "href='/conectar'" not in header


def test_client_sidebar_keeps_admin_routes_hidden():
    rendered = page(admin=False)
    assert "title='Minhas lojas'" in rendered
    assert "href='/seguranca'" not in rendered
    assert "href='/crm'" not in rendered
    assert "href='/painel/analise'" not in rendered


def test_other_pages_use_sidebar_without_header_actions():
    rendered = page(home=False)
    assert "<aside class='ks-sidebar'" in rendered
    assert "href='/seguranca'" in rendered


def test_login_connection_action_lives_in_login_form():
    form = main_function('form_login', {})()
    assert "href='/conectar'" in form


def test_settings_switch_shared_by_home_and_store():
    from store_sidebar import render_store_sidebar
    for rendered in (page(), render_store_sidebar(1, 'Loja', 'resumo')):
        assert rendered.count("role='switch'") == 1
        assert 'Configuração' in rendered
        assert "aria-label='Tema escuro'" in rendered
