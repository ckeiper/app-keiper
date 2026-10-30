"""Private documented contribution queue, independent of gross revenue decline."""
import re
from decimal import Decimal
from html import escape
from urllib.parse import urlencode
from listing_priority_evidence import number
from freight_comparison import format_brl


def build(signals):
    verified=[]
    for item_id,s in signals.items():
        value=number(s.get('contribution_current'))
        if (re.fullmatch(r'MLB[0-9]{1,20}',str(item_id)) and s.get('margin_documented') is True
                and s.get('contribution_verified') is True and value is not None):
            verified.append(dict(item_id=str(item_id),value=value))
    negative=[r for r in verified if Decimal(format(r['value'],'.2f'))<0]
    negative.sort(key=lambda r:(r['value'],r['item_id']))
    return dict(documented=len(verified),total=len(negative),
                negative_sum=sum((r['value'] for r in negative),Decimal(0)),rows=negative[:6])


def render(signals,listings,cid,start,end):
    result=build(signals)
    out='<section class="pf fq" aria-label="Prioridades financeiras documentadas"><div class="pf-card"><span class="pf-eyebrow">Administrador · custos documentados</span><h2>Prioridades financeiras dos anúncios</h2><p>'+start.strftime('%d/%m/%Y')+' a '+end.strftime('%d/%m/%Y')+'. Inclui contribuição negativa mesmo sem queda de faturamento. Ordem pelo valor mais negativo, sem alterar a fila de perdas brutas.</p>'
    if not result['documented']:
        return out+'<p>Nenhum anúncio com custos válidos documentados para este período. Dados ausentes ou desatualizados não são contribuição zero.</p></div></section>'
    out+='<p>'+str(result['documented'])+' anúncios com contribuição documentada válida; '+str(result['total'])+' com contribuição negativa.</p>'
    if not result['rows']:
        return out+'<p>Não há contribuição negativa nos registros válidos deste recorte. Isso não comprova lucro líquido nem cobertura de toda a loja.</p></div></section>'
    out+='<p>Soma somente das contribuições negativas documentadas: <strong>'+format_brl(result['negative_sum'])+'</strong>. Subconjunto documentado; não é resultado da loja, lucro líquido ou economia disponível. Contribuições positivas não compensam esta soma.</p><div class="pf-recovery-list">'
    names={str(r['item_id']):str(r.get('titulo') or r['item_id']) for r in listings}
    for row in result['rows']:
        url='/anuncios/'+str(int(cid))+'/'+row['item_id']+'/rentabilidade?'+urlencode(dict(inicio=start.isoformat(),fim=end.isoformat()))
        out+='<a class="pf-metric fq-card" href="'+escape(url,quote=True)+'"><span>'+escape(names.get(row['item_id'],row['item_id']))+' · '+row['item_id']+'</span><strong>'+format_brl(row['value'])+'</strong><small>Conferir composição, fontes e plano de revisão da margem ↗</small></a>'
    return out+'</div><p>Exibindo '+str(len(result['rows']))+' de '+str(result['total'])+' anúncios negativos. Fontes declaradas pelo administrador, sem auditoria automática. Sem alteração automática de preço ou Ads.</p></div></section>'
