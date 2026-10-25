"""Private documented contribution before/after observed price or promotion change."""
from datetime import timedelta
from decimal import Decimal
from html import escape
from urllib.parse import urlencode
from profitability_store import fingerprint_for,result_for
from freight_comparison import format_brl


def load(conn,query,cid,item_id,periods,orders,items,today):
    if any(p['end']>=today for p in periods):
        return dict(available=False,reason='Aguardando os dois períodos encerrados. Não projetamos custos ou margem futura.')
    if any(p['sales']['orders'] is None for p in periods):
        return dict(available=False,reason='A conferência financeira exige vendas verificadas nos dois períodos.')
    bounds=[(p['start'],p['end']) for p in periods]
    rows=query(conn,'''SELECT DISTINCT ON (inicio,fim) * FROM listing_profitability_records
        WHERE conexao_id=%s AND item_id=%s AND ((inicio=%s AND fim=%s) OR (inicio=%s AND fim=%s))
        ORDER BY inicio,fim,id DESC''',(cid,item_id,*bounds[0],*bounds[1]))
    results=[];records=[]
    for p,window in zip(periods,bounds):
        eligible=[r for r in rows if r.get('conexao_id')==cid and r.get('item_id')==item_id
                  and (r.get('inicio'),r.get('fim'))==window]
        record=max(eligible,key=lambda r:r['id']) if eligible else None
        sales=dict(p['sales'],fingerprint=fingerprint_for(cid,item_id,*window,orders,items))
        results.append(result_for(sales,record));records.append(record)
    before,after=results
    return dict(available=before['available'] and after['available'],before=before,after=after,
        records=records,reason='A comparação exige custos documentados e fontes válidas para as datas exatas dos dois períodos.',
        delta=after['contribution']-before['contribution'] if before['available'] and after['available'] else None,
        margin_delta=after['margin_pct']-before['margin_pct'] if before.get('margin_pct') is not None and after.get('margin_pct') is not None else None)


def unit_contribution(period):
    units=period.get('units')
    if (not period.get('available') or not isinstance(units,Decimal) or
            not units.is_finite() or units<=0 or units!=units.to_integral_value()):
        return None
    return period['contribution']/units


def render(result,cid,item_id,periods,today):
    out='<section class="iv-card action-finance" aria-label="Conferência financeira da alteração"><h3>Contribuição documentada antes e depois</h3><p>Somente administrador · datas exatas dos dois períodos de sete dias, excluindo o dia do registro.</p>'
    if not result['available']:
        out+='<p>'+escape(result['reason'])+'</p>'
        for label,key in [('Antes','before'),('Depois','after')]:
            if key in result and not result[key]['available']:
                out+='<p>'+label+': '+escape(result[key]['reason'])+'</p>'
    else:
        out+='<div class="iv-scroll"><table class="iv-table"><thead><tr><th>Indicador</th><th>Antes</th><th>Depois</th></tr></thead><tbody>'
        for label,key,kind in [('Valor bruto dos itens','revenue','money'),('Unidades verificadas','units','units'),('Contribuição documentada','contribution','money'),('Margem de contribuição','margin_pct','percent'),('Contribuição média por unidade','unit_contribution','money')]:
            out+='<tr><th>'+label+'</th>'
            for period in [result['before'],result['after']]:
                value=unit_contribution(period) if key=='unit_contribution' else period[key]
                out+='<td>'+('Indisponível' if value is None else format_brl(value) if kind=='money' else str(int(value)) if kind=='units' else format(value,'.2f').replace('.',',')+'%')+'</td>'
            out+='</tr>'
        out+='</tbody></table></div><p>Variação da contribuição: '+format_brl(result['delta'])+'. Variação da margem: '+('indisponível' if result['margin_delta'] is None else format(result['margin_delta'],'.2f').replace('.',',')+' p.p.')+'.</p><p>Registros de custos #'+escape(str(result['records'][0]['id']))+' e #'+escape(str(result['records'][1]['id']))+'.</p>'
    out+='<p>A média por unidade usa a contribuição e as unidades verificadas de cada período. Não é calculada com zero unidades. Pode variar com volume, mix, descontos e custos; não equivale ao lucro por produto ou a uma projeção.</p>'
    for index,(label,p) in enumerate(zip(('Conferir fontes anteriores','Conferir fontes seguintes'),periods)):
        if p['start']>=today-timedelta(days=366) and p['end']<today:
            params=dict(inicio=p['start'].isoformat(),fim=p['end'].isoformat())
            records=result.get('records') or []
            record=records[index] if index<len(records) else None
            exact=bool(record and type(record.get('id')) is int and 0<record['id']<=9223372036854775807 and record.get('conexao_id')==int(cid) and str(record.get('item_id'))==str(item_id) and (record.get('inicio'),record.get('fim'))==(p['start'],p['end']))
            if exact:params['registro']=record['id']
            href='/anuncios/'+str(int(cid))+'/'+item_id+'/rentabilidade?'+urlencode(params)+('#pf-registro' if exact else '')
            out+='<p><a class="iv-btn" href="'+escape(href,quote=True)+'">'+label+(' · registro #'+str(record['id']) if exact else '')+' · '+p['start'].strftime('%d/%m/%Y')+' a '+p['end'].strftime('%d/%m/%Y')+' ↗</a></p>'
    return out+'<p>Custos e fontes declarados pelo administrador, sem auditoria automática. Não é lucro líquido, repasse ou ganho causado pela promoção. Os valores incluem mudanças de volume e mix. O registro não comprova que a mesma promoção ou preço permaneceu durante toda a janela. Confira outras alterações e condições antes de concluir sobre o resultado.</p></section><style>body .conteudo .interventions .action-finance{background:#102238;color:#eaf2ff;border-color:#34516e}body .conteudo .interventions .action-finance h3{color:#eaf2ff}.action-finance p{color:#bdcce1;line-height:1.65}body .conteudo .interventions .action-finance table th,body .conteudo .interventions .action-finance table td{background:#182e49;color:#eaf2ff;border-color:#34516e}</style>'
