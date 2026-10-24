"""Private, deterministic financial snapshots. No network, inference or account profit."""
import copy
import re
from datetime import timedelta
from decimal import Decimal

from listing_ranking import ranking_metrics
from profitability_store import read_sales_context
from profitability_priority import load_records,build_signals


def empty_snapshot(end,checked_at,status='no_records'):
    start=end-timedelta(days=6)
    return dict(version='documented-finance-v1',status=status,checked_at=checked_at,
        start=start.isoformat(),end=end.isoformat(),
        previous_start=(start-timedelta(days=7)).isoformat(),previous_end=(start-timedelta(days=1)).isoformat(),
        documented_current=None,comparable_margins=None,current_sold_items=None,covered_sold_items=None,
        negative_count=None,negative_contribution_sum=None,declining_margin_count=None,flagged_count=None,findings=[])


def load_snapshot(conn,query,cid,end,checked_at):
    """At most five scoped reads. Without documented costs, only one read."""
    start=end-timedelta(days=6);old_start=start-timedelta(days=7);old_end=start-timedelta(days=1)
    records=load_records(conn,query,cid,start,end,old_start,old_end)
    if not records:
        return empty_snapshot(end,checked_at)
    context=read_sales_context(conn,query,cid,old_start,end)
    return build_snapshot(cid,context,records,end,checked_at)


def build_snapshot(cid,context,records,end,checked_at):
    result=empty_snapshot(end,checked_at)
    start=end-timedelta(days=6);old_start=start-timedelta(days=7);old_end=start-timedelta(days=1)
    records=[r for r in records if r.get('conexao_id')==cid
             and re.fullmatch(r'MLB[0-9]{1,20}',str(r.get('item_id') or ''))
             and (r.get('inicio'),r.get('fim')) in ((start,end),(old_start,old_end))]
    if not records:
        return result
    context=dict(context,orders=[r for r in context['orders'] if r.get('conexao_id')==cid],
                 items=[r for r in context['items'] if r.get('conexao_id')==cid])
    ids=sorted({str(i['item_id']) for i in context['items'] if i.get('item_id')}
               | {str(r['item_id']) for r in records})
    ranking=ranking_metrics(context['orders'],context['items'],context['coverage'],ids,
        end=end,days=7,pending=context['pending'])
    if not ranking['available']:
        return dict(result,status='unverified_sales')
    signals=build_signals(cid,ranking,context['orders'],context['items'],records,
        start,end,old_start,old_end)
    current=[(item_id,s) for item_id,s in signals.items() if s['contribution_verified']]
    comparable=[(item_id,s) for item_id,s in signals.items() if s['margin_verified']]
    sold={item_id for item_id,r in ranking['rows'].items() if r['orders']>0}
    negative=[(item_id,s) for item_id,s in current if Decimal(format(s['contribution_current'],'.2f'))<0]
    declined=[(item_id,s) for item_id,s in comparable
              if Decimal(format(s['margin_current_pct']-s['margin_previous_pct'],'.2f'))<0]
    findings=[]
    for item_id,s in current:
        is_negative=Decimal(format(s['contribution_current'],'.2f'))<0
        is_declining=s['margin_verified'] and Decimal(format(s['margin_current_pct']-s['margin_previous_pct'],'.2f'))<0
        if not (is_negative or is_declining):
            continue
        kind='negative' if is_negative else 'margin_decline'
        evidence=dict(item_id=item_id,contribution_current=str(s['contribution_current']),
            margin_current_pct=str(s['margin_current_pct']) if s['margin_current_pct'] is not None else None,
            margin_previous_pct=str(s['margin_previous_pct']) if s['margin_verified'] else None)
        findings.append(dict(code='finance_'+kind+'_'+end.strftime('%Y%m%d')+'_'+item_id,
            item_id=item_id,kind=kind,priority=98 if is_negative else 88,
            title=('Contribuição documentada negativa' if is_negative else 'Margem documentada menor')+' · '+item_id,
            action='Conferir os custos e as fontes deste anúncio no período antes de decidir sobre preço, promoção ou publicidade.',
            evidence=evidence))
    findings.sort(key=lambda f:(-f['priority'],
        Decimal(f['evidence']['contribution_current']) if f['kind']=='negative' else
        Decimal(f['evidence']['margin_current_pct'])-Decimal(f['evidence']['margin_previous_pct']),f['item_id']))
    return dict(result,status='ready' if current else 'unverified_costs',
        documented_current=len(current),comparable_margins=len(comparable),
        current_sold_items=len(sold),covered_sold_items=sum(item_id in sold for item_id,_ in current),
        negative_count=len(negative) if current else None,
        negative_contribution_sum=str(sum((s['contribution_current'] for _,s in negative),Decimal(0))) if current else None,
        declining_margin_count=len(declined) if comparable else None,flagged_count=len(findings),findings=findings[:3])


def visible_result(result,admin=False):
    """Client views/history must not expose private financial snapshots."""
    if not isinstance(result,dict):
        return None
    output=copy.deepcopy(result)
    if not admin:
        output.pop('financial',None)
        # Defense for future/legacy records that mixed private rules into the
        # public list. An interpretation of those rules is private as well.
        findings=output.get('recommendations') or []
        if any(str(f.get('code','')).startswith('finance_') for f in findings if isinstance(f,dict)):
            output['recommendations']=[f for f in findings if isinstance(f,dict) and not str(f.get('code','')).startswith('finance_')]
            output['interpretation']=None
    return output


def review_findings(result):
    if not isinstance(result,dict):
        return []
    public=result.get('recommendations') or []
    private=(result.get('financial') or {}).get('findings') or []
    return list(public)+list(private)


def central_findings(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('status')!='ready':
        return []
    output=[]
    if snapshot.get('negative_count'):
        output.append(dict(code='finance_negative_summary',priority=98,
            title=str(snapshot['negative_count'])+(' anúncio' if snapshot['negative_count']==1 else ' anúncios')+' com contribuição documentada negativa',
            action='Revisar a análise financeira e suas fontes. Contagem limitada aos anúncios com custos documentados na execução.'))
    if snapshot.get('declining_margin_count'):
        output.append(dict(code='finance_margin_summary',priority=88,
            title=str(snapshot['declining_margin_count'])+(' anúncio' if snapshot['declining_margin_count']==1 else ' anúncios')+' com margem documentada menor',
            action='Conferir os períodos comparáveis e o peso de cada custo antes de alterar os anúncios.'))
    return output
