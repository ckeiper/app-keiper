"""Compare structured units to category metadata; never infer publication errors."""
from decimal import Decimal,InvalidOperation
from html import escape
from content_required_attributes import attributes

SOURCE='https://developers.mercadolivre.com.br/pt_br/atributos'


def check(definition,row):
    if str(row.get('value_id'))=='-1':return 'unknown','Valor declarado não aplicável; unidade não certificada.'
    units=definition.get('allowed_units')
    if not isinstance(units,list) or not 1<=len(units)<=200:return 'unknown','Unidades da categoria não verificáveis.'
    ids=[]
    for unit in units:
        if not isinstance(unit,dict) or not isinstance(unit.get('id'),str) or not unit['id'].strip() or len(unit['id'])>100:return 'unknown','Unidades da categoria não verificáveis.'
        ids.append(unit['id'])
    if len(set(ids))!=len(ids):return 'unknown','Unidades da categoria repetidas na resposta.'
    # Complex/multivalued values require a separate comparison; do not guess.
    if row.get('values'):return 'unknown','Valor composto: unidade não verificada automaticamente.'
    value=row.get('value_struct')
    if not isinstance(value,dict):return 'unknown','A resposta não traz valor numérico e unidade estruturados.'
    number=value.get('number');unit=value.get('unit')
    if isinstance(number,bool) or not isinstance(number,(int,float,Decimal)):return 'unknown','Número estruturado não verificável.'
    try:finite=Decimal(str(number)).is_finite()
    except InvalidOperation:finite=False
    if not finite or not isinstance(unit,str) or not unit.strip() or len(unit)>100:return 'unknown','Número ou unidade estruturados não verificáveis.'
    if unit not in ids:return 'review','Unidade retornada: '+unit+'. Categoria: '+', '.join(ids)+'.'
    return 'matched','Unidade '+unit+' consta nas unidades informadas pela categoria.'


def compare(definitions,item):
    rules=attributes(definitions)
    if rules is None:return dict(state='unknown',message='Regras da categoria não verificáveis.',rows=[])
    rows=[];truncated=False;groups=[('Anúncio principal',item.get('attributes'))]
    variants=item.get('variations');seen=set();variation_unknown=False
    if not isinstance(variants,list) or len(variants)>1000:variation_unknown=True
    else:
        for variant in variants:
            if not isinstance(variant,dict):variation_unknown=True;break
            identifier=variant.get('id')
            if isinstance(identifier,bool) or not isinstance(identifier,(str,int)) or not str(identifier).strip() or len(str(identifier))>200 or str(identifier) in seen:variation_unknown=True;break
            seen.add(str(identifier))
            for key in ('attributes','attribute_combinations'):groups.append(('Variação '+str(identifier)+' · '+key,variant.get(key)))
        if variation_unknown:groups=groups[:1] # No conclusions from an ambiguous variation set.
    inspected=0
    for location,group in groups:
        parsed=attributes(group)
        if parsed is None:
            rows.append(dict(id='',name='Atributos não verificáveis',location=location,state='unknown',message='Grupo de atributos ausente ou inválido na resposta.'))
        else:
            for code,row in parsed.items():
                inspected+=1
                if inspected>5000:truncated=True;break
                definition=rules.get(code)
                if not definition or definition.get('value_type')!='number_unit':continue
                state,message=check(definition,row)
                name=definition.get('name');name=name if isinstance(name,str) and name.strip() and len(name)<=300 else code
                tags=definition.get('tags');managed=isinstance(tags,dict) and any(tags.get(t) is True for t in ('read_only','inferred','fixed'))
                rows.append(dict(id=code,name=name,location=location,state=state,message=message,managed=managed))
        if len(rows)>=100 or truncated:
            truncated=True;break
    return dict(state='read',rows=rows[:100],truncated=truncated,variation_unknown=variation_unknown)


def render(result):
    esc=lambda v:escape(str(v),quote=True)
    out='<section class="cs-units"><h4>Unidades dos atributos numéricos</h4><p>Unidades comparadas com a regra retornada pela categoria.</p>'
    if result.get('state')!='read':return out+'<p>Unidades não verificadas. '+esc(result.get('message','Consulta indisponível.'))+'</p></section>'
    labels={'matched':'Unidade compatível com a resposta da categoria','review':'Conferir unidade','unknown':'Não verificado'}
    for row in result['rows']:
        out+='<article class="cs-unit" data-unit-state="'+row['state']+'"><h5>'+esc(row['name'])+'</h5><p>'+esc(row['location'])+'</p><strong>'+labels[row['state']]+'</strong><p>'+esc(row['message'])+'</p>'
        if row.get('managed'):out+='<p>Campo gerenciado pelo Mercado Livre; não recomenda alteração direta pelo vendedor.</p>'
        elif row['state']=='review':out+='<p>Confira a unidade e a categoria na ficha do Mercado Livre antes de corrigir.</p>'
        out+='</article>'
    if not result['rows']:out+='<p>Nenhum valor do tipo número com unidade identificado para esta conferência.</p>'
    if result.get('variation_unknown'):out+='<p>Variações não verificáveis: nenhuma conclusão foi emitida para elas.</p>'
    if result.get('truncated'):out+='<p>Leitura limitada a 100 resultados e 5.000 entradas de atributos; não certifica cobertura integral.</p>'
    out+='<details><summary>Limites da conferência</summary><p>A divergência nesta consulta não comprova erro de publicação. Compara apenas a unidade estruturada retornada com allowed_units. Não presume unidade pelo texto, não converte medidas e não certifica validade da ficha.</p></details>'
    return out+'</section><style>.cs-unit{border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.cs-unit[data-unit-state=review]{border-left:4px solid #c08d54}.cs-unit h5{font:inherit;font-weight:700;margin:0 0 8px}</style>'
