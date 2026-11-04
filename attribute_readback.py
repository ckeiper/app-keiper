"""Bounded display evidence from the existing owned read-back, never a write."""
from content_required_attributes import attributes
from content_current_values import text as bounded_text
from attribute_variations import variant_id


def text(value):
    return bounded_text(value) or ''


def value(row):
    if row is None:return dict(state='missing',text='Não retornado nesta leitura')
    if not isinstance(row,dict):return dict(state='unknown',text='Leitura inconclusiva')
    row=dict(row)
    if row.get('values') is not None and not isinstance(row['values'],list):return dict(state='unknown',text='Leitura inconclusiva')
    if row.get('values'):
        values=row['values']
        if not isinstance(values,list) or len(values)!=1 or not isinstance(values[0],dict):return dict(state='unknown',text='Leitura inconclusiva')
        for outer,inner in [('value_id','id'),('value_name','name'),('value_struct','struct')]:
            a=row.get(outer);b=values[0].get(inner)
            if a is not None and b is not None and a!=b:return dict(state='unknown',text='Leitura inconclusiva')
            if a is None:row[outer]=b
    code=text(row.get('value_id'))
    if code=='-1':return dict(state='not_applicable',text='Não aplicável informado',value_id=code)
    name=text(row.get('value_name'));struct=row.get('value_struct')
    if not name and isinstance(struct,dict):
        number=text(struct.get('number'));unit=text(struct.get('unit'))
        if number and unit:name=text(number+' '+unit)
    if name or code:return dict(state='read',text=name or 'ID: '+code,value_id=code)
    if struct is not None:return dict(state='unknown',text='Leitura inconclusiva')
    return dict(state='empty',text='Sem valor nesta leitura')


def observed(proposal,item):
    if proposal.get('variation_id'):
        variants=item.get('variations')
        if not isinstance(variants,list) or len(variants)>1000 or any(not isinstance(v,dict) for v in variants):return value(False)
        selected=[v for v in variants if variant_id(v.get('id'))==proposal['variation_id']]
        if len(selected)!=1:return value(False)
        item=selected[0]
    group=attributes(item.get('attributes'))
    if group is None:return value(False)
    return value(group.get(proposal.get('attribute_id',proposal['id'])))


def field(proposal,item,confirmed):
    return dict(id=proposal['id'],name=proposal['name'],confirmed=confirmed,
                before=value(proposal.get('before')) if proposal.get('before') is not None else dict(state='missing',text='Sem valor identificado na análise'),selected=text(proposal['value']),observed=observed(proposal,item))


def render(fields):
    from html import escape
    from contextual_help import tip
    esc=lambda v:escape(str(v),quote=True)
    if not fields:return ''
    out='<section class="ae-verification"><h4>Conferência por campo'+tip('Conferência por campo','Compara o valor revisado com a nova leitura autenticada do anúncio. Um valor não retornado ou uma leitura inconclusiva não comprova erro nem autoriza reenvio. Análises antigas podem não ter o valor registrado. O valor retornado pode ter formatação normalizada pelo Mercado Livre.')+'</h4>'
    for row in fields:
        ok=row['confirmed'];observation=row.get('observed') or {};before=row.get('before') or {}
        out+='<article class="ae-verified-field"><h5>'+esc(row['name'])+'</h5><span class="'+('ae-confirmed' if ok else 'ae-unconfirmed')+'">'+('Confirmado' if ok else 'Não confirmado')+'</span><dl>'
        for label,display in [('Antes',before.get('text','Valor não registrado nesta análise')),('Selecionado',row.get('selected','Valor não registrado nesta análise')),('Retornado pelo Mercado Livre',observation.get('text','Valor não registrado nesta análise'))]:
            out+='<div><dt>'+label+'</dt><dd>'+esc(display)+'</dd></div>'
        out+='</dl>'
        code=observation.get('value_id')
        if code and observation.get('text')!='ID: '+code:out+='<small>ID retornado: '+esc(code)+'</small>'
        out+='</article>'
    return out+'</section>'
