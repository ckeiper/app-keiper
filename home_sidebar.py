"""Accessible, responsive navigation for the home directory."""


def render_home_sidebar(admin=False):
    security = "<footer class='ks-foot'><a href='/seguranca' title='Segurança'><span aria-hidden='true'>◇</span><span class='ks-label'>Segurança</span></a></footer>" if admin else ""
    overview = "<a href='/painel/analise' title='Visão geral'><span aria-hidden='true'>▦</span><span class='ks-label'>Visão geral</span></a>" if admin else ""
    crm = "<a href='/crm' title='CRM'><span aria-hidden='true'>◎</span><span class='ks-label'>CRM</span></a>" if admin else ""
    from navigation_shell import shell
    navigation = overview + "<a href='/painel' aria-current='page' title='Minhas lojas'><span aria-hidden='true'>⌂</span><span class='ks-label'>Minhas lojas</span></a>" + crm
    return shell(navigation, security)
