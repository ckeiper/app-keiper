"""Read-only store data-collection health from already persisted telemetry.

No marketplace calls, no automatic refresh contention, no zero-filled gaps.
"""
from datetime import timedelta
from html import escape
from sales_metrics import reporting_today


def assess(shops, catalog, ads, sales, runs, errors, today=None, now=None):
    import time
    today=today or reporting_today()
    now=int(time.time()) if now is None else int(now)
    by_catalog={int(x['conexao_id']):x for x in catalog}
    by_ads={int(x['conexao_id']):x for x in ads}
    by_sales={int(x['conexao_id']):x for x in sales}
    by_runs={int(x['conexao_id']):x for x in runs}
    by_errors={}
    for e in errors:
        cid=int(e['conexao_id'])
        by_errors.setdefault(cid,[]).append(str(e['categoria']))
    yesterday=(today-timedelta(days=1)).isoformat()
    two_days=(today-timedelta(days=2)).isoformat()
    rows=[]
    for shop in shops:
        cid=int(shop['id'])
        if str(shop.get('status') or '').lower()!='ativa':
            rows.append(dict(id=cid,name=str(shop.get('cliente') or cid),state='inativa',
                             issues=['Conexão inativa; revalidar autorização.'],action='Revalidar conexão'))
            continue
        issues=[]
        catalogue=by_catalog.get(cid,{})
        stamp=catalogue.get('latest')
        if stamp is None:
            issues.append('Sem leitura registrada de catálogo.')
        elif now-int(stamp)>24*3600:
            issues.append('Catálogo sem atualização há mais de 24 horas.')
        a=by_ads.get(cid,{})
        if a.get('first_day'):
            if not a.get('last_day') or str(a['last_day'])<two_days:
                issues.append('Ads sem registros nos últimos 2 dias completos.')
            if int(a.get('days_7') or 0)<7:
                issues.append('Ads: %s/7 dias completos com registros.' % int(a.get('days_7') or 0))
        else:
            # A store might not advertise; lack of Ads history is not a failure.
            pass
        v=by_sales.get(cid,{})
        if v.get('latest_day') is not None and str(v['latest_day'])<two_days:
            issues.append('Cobertura de vendas sem registro nos últimos 2 dias completos.')
        elif v.get('latest_day') is None:
            issues.append('Sem histórico de cobertura de vendas.')
        run=by_runs.get(cid,{})
        if run.get('status')=='falhou':
            issues.append('Última sincronização terminou com falha.')
        if run.get('status')=='executando' and now-int(run.get('heartbeat_em') or run.get('inicio_em') or 0)>7200:
            issues.append('Sincronização em execução há mais de 2 horas sem confirmação recente.')
        categories=by_errors.get(cid,[])
        if categories:
            issues.append('%s erro(s) de coleta pendente(s).' % len(categories))
        rows.append(dict(id=cid,name=str(shop.get('cliente') or cid),
                         state='atencao' if issues else 'normal',issues=issues,
                         action='Investigar e sincronizar' if issues else 'Nenhuma ação urgente'))
    rows.sort(key=lambda x:({'atencao':0,'inativa':1,'normal':2}[x['state']],x['name'].casefold()))
    return rows


def summary(rows):
    return {'attention':sum(r['state']=='atencao' for r in rows),
            'normal':sum(r['state']=='normal' for r in rows),
            'inactive':sum(r['state']=='inativa' for r in rows)}


def render(rows, compact=False):
    stats=summary(rows)
    html='<section class="kh-health" aria-label="Saúde das coletas"><div class="kh-health-head">'
    html+='<div><span class="kh-health-eyebrow">MONITORAMENTO · DADOS</span><h3>Saúde das sincronizações</h3>'
    html+='<p>%s loja(s) precisam de verificação · %s sem alertas · %s inativa(s)</p></div>' % (
        stats['attention'],stats['normal'],stats['inactive'])
    html+='<a href="/diagnostico">Ver diagnóstico →</a></div>'
    showing=[r for r in rows if r['state']=='atencao']
    if compact:
        showing=showing[:4]
    if not showing:
        html+='<p class="kh-health-empty">Nenhuma falha de coleta detectada nas lojas ativas pelos critérios monitorados.</p>'
    else:
        html+='<div class="kh-health-grid">'
        for r in showing:
            html+='<a class="kh-health-item" href="/painel/'+str(r['id'])+'"><strong>'+escape(r['name'])+'</strong>'
            html+='<span>'+escape(r['issues'][0])+'</span><small>'+str(len(r['issues']))+' sinal(is) · Abrir loja →</small></a>'
        html+='</div>'
    html+='<p class="kh-health-foot">A ausência de alerta não valida a integridade de todos os dados. Ads sem histórico pode significar que a loja não anuncia. Verificação por registros locais, sem chamadas extras à API.</p></section>'
    return html


CSS="""<style>
.kh-health{max-width:1240px;margin:22px auto 32px;padding:21px 24px;background:#fff;border:1px solid #dce5f1;border-radius:16px;box-shadow:0 5px 22px #173b6610;color:#243651}
.kh-health-head{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
.kh-health-head h3{font-size:20px;letter-spacing:-.4px;margin:5px 0}.kh-health-head p{font-size:12px;color:#6a7c94;margin:0}
.kh-health-head a{font-size:12px;color:#3567b7;font-weight:750;text-decoration:none}
.kh-health-eyebrow{font-size:10px;font-weight:800;letter-spacing:1.2px;color:#6381b1}
.kh-health-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin:16px 0 8px}
.kh-health-item{display:flex;flex-direction:column;gap:7px;padding:13px 14px;border:1px solid #f0d9d7;border-radius:10px;text-decoration:none;color:#273b56;background:#fff9f7}
.kh-health-item strong{font-size:13px}.kh-health-item span{font-size:12px;color:#9d5360}
.kh-health-item small{font-size:11px;color:#446aa4}.kh-health-empty{font-size:13px;color:#34815d;margin-top:14px}
.kh-health-foot{font-size:11px;color:#7c8ca2;line-height:1.6;margin-top:12px}
@media(max-width:600px){.kh-health{margin:16px 12px;padding:17px}.kh-health-head h3{font-size:18px}}
</style>"""
