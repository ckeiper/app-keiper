"""Observed listing changes near the boundary of two completed sales windows.

Timing alone does not prove causality or pinpoint the first day of a sales decline.
"""
from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")
CATEGORIES = {"preco":"Preço e promoções","full":"Estoque e Full",
              "entrega":"Frete e entrega","conteudo":"Conteúdo do anúncio",
              "ads":"Publicidade","outro":"Outras alterações"}
MAX_SHOWN = 8


def read(rows, end, days=7, sales_verified=False, declining=False):
    boundary = end-timedelta(days=days-1)
    earliest = boundary-timedelta(days=3)
    latest = boundary+timedelta(days=3)
    selected = []
    for row in rows:
        day = row.get("event_date")
        if isinstance(day, datetime):
            day = day.date()
        elif isinstance(day,str):
            try:
                day = date.fromisoformat(day)
            except ValueError:
                continue
        if not isinstance(day,date) or not earliest <= day <= latest:
            continue
        source = row.get("source")
        if source not in ("manual","automatic"):
            continue
        stamp = row.get("created_at")
        if not isinstance(stamp,int) or stamp <= 0:
            continue
        kind = str(row.get("kind") or "outro")
        note = str(row.get("note") or "")
        field = str(row.get("field") or "")
        selected.append(dict(day=day,stamp=stamp,source=source,
                             category=CATEGORIES.get(kind,"Outras alterações"),
                             field=field,note=note[:280],
                             position="antes" if day < boundary else "na janela atual"))
    selected.sort(key=lambda v:(abs((v["day"]-boundary).days),-v["stamp"],v["category"]))
    result = selected[:MAX_SHOWN]
    state = ("sem_dados" if not result else
             "queda_verificada" if sales_verified and declining else
             "sem_queda" if sales_verified else "nao_verificada")
    return {"state":state,"boundary":boundary,"items":result,
            "total":len(selected),"truncated":len(selected)>MAX_SHOWN}


CSS = """<style>
.decline-changes{border:1px solid #dde5f1;background:linear-gradient(140deg,#fff,#f9fbff);border-radius:14px;padding:19px;margin:15px 0;color:#243651}
.decline-changes header{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.decline-changes h4{font-size:16px;margin:0;color:#234264}
.decline-changes p,.decline-changes small{font-size:12px;line-height:1.6;color:#687b93}
.decline-changes .dc-tag{font-size:10px;font-weight:750;letter-spacing:.4px;border:1px solid #d6e4f8;background:#edf4ff;padding:6px 8px;border-radius:7px;color:#426796}
.decline-changes ol{list-style:none;margin:14px 0;padding:0}
.decline-changes li{display:flex;align-items:flex-start;gap:12px;border-top:1px solid #e7edf5;padding:12px 0}
.decline-changes time{font-size:11px;color:#526c8d;font-weight:750;min-width:60px}
.decline-changes li strong{font-size:12px}.decline-changes li p{margin:4px 0 0;overflow-wrap:anywhere}
.decline-changes li small{display:block;margin-top:3px}
@media(max-width:600px){.decline-changes{padding:15px}.decline-changes li{gap:8px}}
</style>"""


def render(data):
    out = CSS+'<section class="decline-changes" aria-label="Alterações próximas da queda">'
    out += '<header><h4>O que mudou perto da virada?</h4><span class="dc-tag">Histórico observado</span></header>'
    out += '<p>Comparação de 7 dias anteriores e atuais: transição em '+data["boundary"].strftime("%d/%m/%Y")+'. Verificamos registros até 3 dias antes e 3 dias depois dessa data.</p>'
    if data["state"]=="sem_dados":
        out += '<p>Nenhuma alteração registrada nessa faixa. Isso não significa que nada tenha mudado: o histórico pode estar incompleto.</p>'
    else:
        if data["state"]!="queda_verificada":
            out += '<p>Não há queda de faturamento confirmada para relacionar a estes registros. Eles são apresentados apenas como contexto.</p>'
        out += '<ol>'
        for item in data["items"]:
            qualifier = "Detectada nas coletas" if item["source"]=="automatic" else "Informada manualmente"
            out += '<li><time>'+item["day"].strftime("%d/%m")+'</time><div><strong>'+escape(item["category"])+'</strong>'
            out += '<p>'+escape(item["note"] or "Alteração sem descrição")+'</p>'
            out += '<small>'+qualifier+' · '+escape(item["position"])+'</small></div></li>'
        out += '</ol>'
        if data["truncated"]:
            out += '<p>Exibindo os '+str(MAX_SHOWN)+' registros mais próximos entre '+str(data["total"])+'. Consulte o histórico completo para os demais.</p>'
    out += '<small>A virada é a divisão entre períodos comparados, não o início comprovado da queda. Registros automáticos mostram o dia da detecção, não a hora real da alteração. Registros manuais não comprovam execução. Coincidência temporal não demonstra causalidade.</small></section>'
    return out
