"""Bounded presentation of official last-moderation messages; never executes them."""
from html import escape
from listing_content_snapshot import read, ContentUnavailable


def normalize(payload):
    rows=[];limited=len(payload)>10;partial=False
    def text(value,limit):
        nonlocal limited,partial
        if value is None:return None
        if not isinstance(value,str):
            partial=True
            return None
        if len(value)>limit:limited=True
        return value[:limit]
    for raw in payload[:10]:
        if not isinstance(raw,dict):
            partial=True
            continue
        row=dict(name=text(raw.get('name'),200),date=text(raw.get('date_created'),100),messages=[],evidence=[])
        messages=raw.get('wordings')
        if not isinstance(messages,list):partial=True
        else:
            if len(messages)>20:limited=True
            for message in messages[:20]:
                if not isinstance(message,dict) or message.get('type') not in ('REASON','REMEDY'):
                    partial=True
                    continue
                value=text(message.get('value'),2000)
                if value and value.strip():row['messages'].append(dict(kind=message['type'],value=value))
                else:partial=True
        for key in ('evidences','evidence'):
            values=raw.get(key)
            if values is None:continue
            if not isinstance(values,list):
                partial=True
                continue
            if len(values)>5:limited=True
            for ev in values[:5]:
                if not isinstance(ev,dict):
                    partial=True
                    continue
                section=text(ev.get('section_name'),200);value=text(ev.get('text_matched'),1000)
                if section or value:row['evidence'].append(dict(section=section,value=value))
                else:partial=True
        rows.append(row)
    return dict(state='read',rows=rows,limited=limited,partial=partial,returned=len(payload))


def inspect(token,item_id,request_get):
    # Caller first verifies authorized account, item ownership, and the MLB identifier.
    try:return normalize(read(token,'/moderations/last_moderation/'+item_id+'-ITM',request_get,list))
    except ContentUnavailable as exc:return dict(state='unknown',message=str(exc))


def render(result):
    esc=lambda v:escape(str(v),quote=True)
    out='<section class="rr-moderation"><h4>Última moderação retornada</h4>'
    if result is None:return out+'<p>Detalhes ainda não consultados.</p></section>'
    if result['state']!='read':return out+'<p role="status">Moderação não verificada. '+esc(result['message'])+'</p></section>'
    if result['limited']:out+='<p>Exibição limitada a dez registros, vinte mensagens por registro, cinco evidências por origem e textos resumidos.</p>'
    if result['partial']:out+='<p role="status">Resposta parcial: há campos não verificáveis ou mensagens adicionais não exibidas.</p>'
    if not result['returned']:out+='<p>Nenhuma moderação retornada nesta consulta. Isso não comprova ausência de restrições.</p>'
    for row in result['rows']:
        out+='<div class="rr-moderation-entry"><strong>'+esc(row['name'] or 'Código não informado')+'</strong>'
        if row['date']:out+='<p>Data informada pela API: '+esc(row['date'])+'</p>'
        for msg in row['messages']:
            label='Motivo informado' if msg['kind']=='REASON' else 'Ação sugerida pelo Mercado Livre'
            out+='<p><strong>'+label+'</strong></p><p class="rr-note">'+esc(msg['value'])+'</p>'
        if not any(m['kind']=='REMEDY' for m in row['messages']):out+='<p>Ação corretiva não retornada; a possibilidade de recuperação não foi determinada.</p>'
        for ev in row['evidence']:
            out+='<p class="rr-note">Evidência · '+esc(ev['section'] or 'Seção não informada')+': '+esc(ev['value'] or 'Texto não informado')+'</p>'
        out+='</div>'
    return out+'<p>As mensagens são do Mercado Livre e podem mudar após esta leitura. Histórico completo e restrições da conta não consultados. Nenhuma ação foi executada.</p></section>'
