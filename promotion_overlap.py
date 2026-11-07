"""Calendar intersections within one archived reading, never stacked discounts or attribution."""
from datetime import date,datetime,time,timedelta
from html import escape
from promotion_observations import timestamp,CALENDAR_TYPES
from sales_metrics import SAO_PAULO

TYPE_NAMES={'PRICE_DISCOUNT':'Desconto do vendedor','SELLER_CAMPAIGN':'Campanha do vendedor','SMART':'Campanha cofinanciada','DEAL':'Campanha Mercado Livre','DOD':'Oferta do dia','LIGHTNING':'Oferta relâmpago'}


def identity(row):
    if not isinstance(row,dict) or not isinstance(row.get('conditions',{}),dict):return None
    values=(row.get('id'),row.get('type'),row.get('conditions',{}).get('offer_id'),row.get('variation_id'))
    for index,value in enumerate(values):
        if value is None and index>=2:continue
        if not isinstance(value,str) or not 1<=len(value)<=250 or value.strip()!=value or any(ord(c)<32 for c in value):return None
    return values


def signature(row):
    return [row.get(k) for k in ('status','start','end','price','original','conditions')]


def analyze(promotions,selected_index,start,end,phase='during'):
    unknown=lambda reason:dict(available=False,reason=reason)
    if (not isinstance(promotions,list) or not 1<=len(promotions)<=200 or type(selected_index) is not int
            or not 0<=selected_index<len(promotions) or type(start) is not date or type(end) is not date or end<start
            or phase not in ('before','during')):
        return unknown('Base ou janela de calendários não verificável.')
    try:
        left=datetime.combine(start,time.min,SAO_PAULO)
        right=datetime.combine(end+timedelta(days=1),time.min,SAO_PAULO)
    except (ValueError,OverflowError):return unknown('Janela de calendários não verificável.')
    chosen=promotions[selected_index];chosen_key=identity(chosen)
    if chosen_key is None:return unknown('Identidade da oferta selecionada não verificável.')
    chosen_start,chosen_end=timestamp(chosen.get('start')),timestamp(chosen.get('end'))
    if (chosen.get('type') not in CALENDAR_TYPES or chosen.get('status') not in ('active','started')
            or chosen.get('variation_id') is not None or not chosen_start or not chosen_end or chosen_end<=chosen_start
            or (phase=='during' and (chosen_start>left or chosen_end<right))
            or (phase=='before' and right>chosen_start)):
        return unknown('O calendário selecionado não confirma esta janela completa.')
    groups={};invalid=0
    for row in promotions:
        key=identity(row)
        if key is None:invalid+=1;continue
        groups.setdefault(key,[]).append(row)
    # Conflicting identities are not silently resolved by choosing one row.
    if any(signature(row)!=signature(chosen) for row in groups[chosen_key]):
        return unknown('A oferta selecionada tem registros conflitantes nesta consulta.')
    counts=dict(unknown=invalid,not_active=0,variation=0,unsupported=0,checked=0)
    duplicates=0;overlaps=[]
    for key,rows in groups.items():
        if key==chosen_key:
            duplicates+=len(rows)-1;continue
        if any(signature(row)!=signature(rows[0]) for row in rows):
            counts['unknown']+=1;continue
        duplicates+=len(rows)-1;row=rows[0]
        if row.get('status') not in ('active','started'):
            counts['not_active']+=1;continue
        if row.get('variation_id') is not None:
            counts['variation']+=1;continue
        if row.get('type') not in CALENDAR_TYPES:
            counts['unsupported']+=1;continue
        begin,finish=timestamp(row.get('start')),timestamp(row.get('end'))
        if not begin or not finish or finish<=begin:
            counts['unknown']+=1;continue
        counts['checked']+=1
        overlap_start,overlap_end=max(left,begin),min(right,finish)
        if overlap_start<overlap_end:
            overlaps.append(dict(id=row['id'],type=row['type'],status=row['status'],
                start=overlap_start,end=overlap_end,offer_id=row.get('conditions',{}).get('offer_id'),
                name=row.get('name') if isinstance(row.get('name'),str) and 0<len(row['name'])<=250 else None))
    overlaps.sort(key=lambda r:(r['start'],r['end'],r['id'],r['type'],r['offer_id'] or ''))
    return dict(available=True,rows=overlaps[:20],total=len(overlaps),limited=len(overlaps)>20,
                counts=counts,duplicates=duplicates,start=left,end=right)


def render(data,before=None):
    esc=lambda v:escape(str(v),quote=True)
    out=STYLE+'<section class="card pc-overlap"><h3>Calendários coincidentes na consulta</h3>'
    windows=[('Antes',before),('Dentro do calendário',data)] if before is not None else [('Dentro do calendário',data)]
    valid=[]
    for label,model in windows:
        if not model['available']:
            out+='<p role="status">'+label+' · '+esc(model['reason'])+'</p>'
        else:
            valid.append((label,model))
            out+='<p>'+label+' · coincidências verificadas: <strong>'+str(model['total'])+'</strong> · calendários comparados: '+str(model['counts']['checked'])+'.</p>'
    if not valid:return out+'</section>'
    c=valid[-1][1]['counts']
    out+='<p>Outras ofertas da mesma consulta, com as datas recortadas às janelas comparadas.</p>'
    if c['unknown']:out+='<p role="status">Há '+str(c['unknown'])+' registro(s) com identidade ou datas não verificáveis.</p>'
    def stamp(v):
        value=v.astimezone(SAO_PAULO)
        return value.strftime('%d/%m/%Y %H:%M:%S')+('.'+str(value.microsecond).zfill(6) if value.microsecond else '')
    if any(model['rows'] for _,model in valid):
        out+='<div class="pc-scroll" role="region" aria-label="Calendários coincidentes" tabindex="0"><table><caption>Interseções de calendários · Brasília · fim exclusivo</caption><thead><tr><th scope="col">Janela</th><th scope="col">Oferta</th><th scope="col">Tipo e status na leitura</th><th scope="col">Início da interseção</th><th scope="col">Fim da interseção</th></tr></thead><tbody>'
        for label,model in valid:
            for r in model['rows']:
                out+='<tr><th scope="row">'+label+'</th><td>'+esc(r['name'] or r['id'])+('<small>'+esc(r['id'])+'</small>' if r['name'] else '')+('<small> · '+esc(r['offer_id'])+'</small>' if r['offer_id'] else '')+'</td><td>'+esc(TYPE_NAMES.get(r['type'],r['type']))+' · ativa na consulta'+'</td><td>'+stamp(r['start'])+'</td><td>'+stamp(r['end'])+'</td></tr>'
        out+='</tbody></table></div>'
    else:out+='<p>Nenhuma coincidência verificável nesta consulta. Isso não comprova ausência de outras promoções no período.</p>'
    for label,model in valid:
        if model['limited']:out+='<p role="status">'+label+' · exibidas as primeiras 20 interseções de '+str(model['total'])+'.</p>'
    out+='<details><summary>Escopo e registros fora da comparação</summary><p>Sem confirmação de status ativo: '+str(c['not_active'])+' · por variação: '+str(c['variation'])+' · tipo sem regra validada: '+str(c['unsupported'])+' · identidade ou datas insuficientes/conflitantes: '+str(c['unknown'])+'.</p><p>Repetições idênticas agrupadas: '+str(valid[-1][1]['duplicates'])+'. Registros ambíguos não viram ausência de coincidências. Ofertas por variação e tipos condicionais ficam fora desta comparação.</p><p>Calendários coincidentes não comprovam aplicação conjunta, participação contínua nem quais vendas receberam cada promoção. Preços e descontos não são somados e os resultados não são atribuídos a uma oferta isolada.</p></details><p>Leitura pontual; não confirma aplicação conjunta de descontos.</p></section>'
    return out


STYLE='''<style>.pc-overlap{min-width:0;overflow-wrap:anywhere}.pc-overlap table{min-width:700px}.pc-overlap caption{text-align:left;font-size:12px;padding:10px 0}.pc-overlap .pc-scroll:focus-visible{outline:3px solid #55aef0;outline-offset:3px}.pc-overlap details{margin:16px 0}.pc-overlap summary{cursor:pointer;font-weight:700}html:not([data-theme=light]) body .pc-overlap tbody tr:hover :is(td,th){background:#1b344e!important}html:not([data-theme=light]) body .pc-overlap :is(h3,strong){color:#eaf2ff!important}@layer keiper-appearance{html[data-theme=light] body .pc-overlap{background:#fff!important;color:#172d47!important}}.pc-overlap small{display:block}</style>'''
