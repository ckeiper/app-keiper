"""Bulk documented financial signals for the administrator's existing listing queue.

Reuses verified ranking metrics and paid-order data already loaded by the page.
No per-listing database/API calls and no estimated monetary recovery.
"""
from collections import defaultdict
from datetime import timedelta
from profitability_store import fingerprint_for,result_for
from sales_metrics import created_day


def load_signals(conn,query,cid,ranking,orders,items,end,days):
    if not ranking.get('available') or days not in (7,30):
        return {}
    start=end-timedelta(days=days-1)
    previous_end=start-timedelta(days=1)
    previous_start=previous_end-timedelta(days=days-1)
    records=load_records(conn,query,cid,start,end,previous_start,previous_end)
    return build_signals(cid,ranking,orders,items,records,start,end,previous_start,previous_end)


def load_records(conn,query,cid,start,end,previous_start,previous_end):
    return query(conn,'''SELECT DISTINCT ON (item_id,inicio,fim) *
        FROM listing_profitability_records
        WHERE conexao_id=%s AND ((inicio=%s AND fim=%s) OR (inicio=%s AND fim=%s))
        ORDER BY item_id,inicio,fim,id DESC''',
        (cid,start,end,previous_start,previous_end))


def build_signals(cid,ranking,orders,items,records,start,end,previous_start,previous_end):
    if not ranking.get('available'):
        return {}
    metrics=ranking.get('rows') or {}
    selected={}
    for record in records:
        item_id=str(record.get('item_id'))
        if record.get('conexao_id')!=cid or item_id not in metrics:
            continue
        window=(record.get('inicio'),record.get('fim'))
        if window not in ((start,end),(previous_start,previous_end)):
            continue
        # Extra defensive ordering: the SQL already selects the newest version.
        key=(item_id,window)
        if key not in selected or record['id']>selected[key]['id']:
            selected[key]=record
    if not selected:
        return {}
    desired={key[0] for key in selected}
    by_order={(r.get('conexao_id'),str(r.get('pedido_id'))):r for r in orders
              if r.get('conexao_id')==cid}
    windows={}
    for key,row in by_order.items():
        day=created_day(row.get('criado_em'))
        if day is None:
            continue
        if start<=day<=end:windows[key]=(start,end)
        elif previous_start<=day<=previous_end:windows[key]=(previous_start,previous_end)
    grouped=defaultdict(list)
    grouped_keys=defaultdict(set)
    for row in items:
        item_id=str(row.get('item_id'))
        key=(row.get('conexao_id'),str(row.get('pedido_id')))
        if row.get('conexao_id')==cid and item_id in desired and key in windows:
            group=(item_id,windows[key]);grouped[group].append(row);grouped_keys[group].add(key)
    signals={}
    for item_id in desired:
        results=[]
        for window,prefix in [((start,end),''),((previous_start,previous_end),'previous_')]:
            group=(item_id,window);entry=selected.get(group)
            if entry is None:
                results.append(dict(available=False,margin_pct=None));continue
            row=metrics[item_id]
            basis=dict(orders=row[prefix+'orders'],units=row[prefix+'units'],gross_items=row[prefix+'value'],
                start=window[0].isoformat(),end=window[1].isoformat(),
                fingerprint=fingerprint_for(cid,item_id,*window,
                    [by_order[key] for key in grouped_keys[group]],grouped[group]))
            results.append(result_for(basis,entry))
        current,previous=results
        verified=bool(current['available'] and previous['available']
                      and current['margin_pct'] is not None and previous['margin_pct'] is not None)
        signals[item_id]=dict(margin_verified=verified,margin_documented=True,
            margin_current_pct=current.get('margin_pct'),margin_previous_pct=previous.get('margin_pct'),
            contribution_verified=current['available'],contribution_current=current.get('contribution'))
    return signals
