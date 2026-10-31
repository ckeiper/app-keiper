"""Accessible, responsive navigation for the home directory."""


def render_home_sidebar(admin=False,active='home'):
    security = "<footer class='ks-foot'><a href='/seguranca' title='Segurança'><span aria-hidden='true'>◇</span><span class='ks-label'>Segurança</span></a></footer>" if admin else ""
    overview = "<a href='/painel/analise' title='Relatórios consolidados'><span aria-hidden='true'>▦</span><span class='ks-label'>Relatórios consolidados</span></a>" if admin else ""
    if admin:overview += "<a href='/carteira' title='Visão da Carteira'><span aria-hidden='true'>▥</span><span class='ks-label'>Visão da Carteira</span></a>"
    crm = "<a href='/crm' title='CRM e leads'><span aria-hidden='true'>◎</span><span class='ks-label'>CRM e leads</span></a>" if admin else ""
    management = ("<a href='/usuarios' title='Usuários'><span aria-hidden='true'>♙</span><span class='ks-label'>Usuários</span></a>"
                  "<a href='/diagnostico'"+(" aria-current='page'" if active=='diagnostic' else '')+" title='Diagnóstico'><span aria-hidden='true'>⌕</span><span class='ks-label'>Diagnóstico</span></a>"
                  "<a href='/prioridades' title='Central de prioridades'><span aria-hidden='true'>⚑</span><span class='ks-label'>Central de prioridades</span></a>") if admin else ""
    if admin:
        management += "<a href='/evolucao-anuncios'"+(" aria-current='page'" if active=='progress' else '')+" title='Evolução de Anúncios'><span aria-hidden='true'>▤</span><span class='ks-label'>Evolução de Anúncios</span></a>"
    from navigation_shell import shell
    navigation = overview + "<a href='/painel'"+(" aria-current='page'" if active=='home' else '')+" title='Minhas lojas'><span aria-hidden='true'>⌂</span><span class='ks-label'>Minhas lojas</span></a>" + crm + management
    return shell(navigation, security)
