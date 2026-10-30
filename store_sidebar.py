"""Store navigation uses the same shell and controls as the homepage."""
from html import escape
from navigation_shell import shell

ITEMS = [
    ('resumo','Resumo','/painel/','M3 3v18h18M7 16v-5m5 5V7m5 9v-8'),
    ('prioridades','Minhas prioridades','/prioridades/','m12 3 3 6 6 1-4.5 4.5 1 6.5-5.5-3-5.5 3 1-6.5L3 10l6-1z'),
    ('anuncios','Anúncios','/anuncios/','M4 7h16v14H4zM3 3h18v4H3zM9 12h6'),
    ('full','Full e vendas','/full/','M3 5h11v13H3zM14 10h4l3 4v4h-7M6 18v2m12-2v2'),
    ('desempenho','Desempenho','/desempenho/','m3 17 6-6 4 3 8-10M15 4h6v6'),
    ('demandas','Demandas','/demandas/','M4 4h16v12H8l-4 4zM8 8h8M8 12h5'),
    ('promocoes','Promoções','/promocoes/','M3 3h8l10 10-8 8L3 11zM7 7h.01'),
    ('ads','Ads','/ads/','M4 10v5h4l10 5V5L8 10zM8 15l2 6'),
    ('custos','Custos','/custos/','M4 4h16v16H4zM8 8h8M8 12h2m4 0h2m-8 4h2m4 0h2'),
    ('vendas','Vendas','/vendas/','M3 3h2l3 13h11l2-9H6M9 21h.01M18 21h.01'),
    ('auditoria_frete','Auditoria de Frete','/auditoria-frete/','M4 3h12v18H4zM8 7h4m-4 4h4m-4 4h4M16 8h4v10h-4'),
]


def link(label, href, path, active=False, danger=False):
    return ("<a href='"+escape(href,quote=True)+"' title='"+escape(label,quote=True)+"'"
            +(" aria-current='page'" if active else '')+(" class='ks-danger'" if danger else '')+">"
            +"<span aria-hidden='true'><svg viewBox='0 0 24 24'><path d='"+path+"'/></svg></span><span class='ks-label'>"+escape(label)+"</span></a>")


def render_store_sidebar(cid, cliente, secao, admin=False):
    cid=str(int(cid))
    nav=link('Todas as lojas','/painel','m14 6-6 6 6 6M8 12h13')
    items={item[0]:item for item in ITEMS}
    nav+=link('Visão geral','/painel/'+cid,items['resumo'][3],secao=='resumo')
    nav+=link('KEVIA','/ia-keiper/'+cid,items['prioridades'][3],secao=='ia')
    groups=[('anuncios','Anúncios',['anuncios','desempenho','promocoes']),
            ('vendas','Vendas',['vendas','full','auditoria_frete']),
            ('ads','Publicidade',['ads']),
            ('demandas','Gestão',['prioridades','demandas','custos'])]
    for icon,label,keys in groups:
        if icon=='ads':
            nav+=link('Publicidade','/ads/'+cid,items['ads'][3],secao in ('ads','campanhas'))
            continue
        active=secao in keys
        nav+="<details class='ks-nav-group'"+(' open' if active else '')+"><summary><span aria-hidden='true'><svg viewBox='0 0 24 24'><path d='"+items[icon][3]+"'/></svg></span><span class='ks-label'>"+label+"</span><span class='ks-chevron' aria-hidden='true'>⌄</span></summary><div class='ks-nav-children'>"
        nav+=''.join(link(items[key][1],items[key][2]+cid,items[key][3],secao==key) for key in keys)
        nav+='</div></details>'
    footer=link('Atualizar dados','/atualizar?cid='+cid,'M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2')
    if admin:
        footer+=link('Evolução de Anúncios','/evolucao-anuncios','M4 4h16v16H4zM8 9h8M8 13h5M8 17h3')
        footer+=link('Diagnóstico','/diagnostico','M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6')
        footer+=link('Segurança','/seguranca','M12 3 3 7v6c0 4 9 8 9 8s9-4 9-8V7z')
    footer="<details class='ks-nav-group'><summary><span aria-hidden='true'>⚙</span><span class='ks-label'>Ferramentas</span><span class='ks-chevron' aria-hidden='true'>⌄</span></summary><div class='ks-nav-children'>"+footer+'</div></details>'
    footer+=link('Excluir loja','/excluir/'+cid,'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',danger=True)
    return shell(nav,"<footer class='ks-foot'>"+footer+"</footer>",store_name=cliente)
