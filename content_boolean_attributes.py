"""Compare explicit boolean value IDs with category metadata, without text inference."""
from html import escape
from content_required_attributes import attributes


def identifier(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)):return None
    value=str(value)
    return value if value.strip() and len(value)<=200 else None


def check(definition,row):
    values=definition.get('values')
    if not isinstance(values,list) or len(values)!=2:return 'unknown','Lista de identificadores booleanos não verificável.'
    ids=[]
    for value in values:
        if not isinstance(value,dict) or identifier(value.get('id')) is None:return 'unknown','Lista de identificadores booleanos não verificável.'
        ids.append(identifier(value['id']))
    if len(set(ids))!=2 or '-1' in ids:return 'unknown','Lista de identificadores booleanos não verificável.'
    actual=identifier(row.get('value_id'))
    if actual is None:return 'unknown','Sem identificador verificável; o texto não é interpretado como sim ou não.'
    if actual=='-1':return 'unknown','Valor declarado não aplicável; identificador booleano não certificado.'
    complex_values=row.get('values')
    if complex_values:
        if not isinstance(complex_values,list) or len(complex_values)!=1 or not isinstance(complex_values[0],dict) or identifier(complex_values[0].get('id'))!=actual:
            return 'unknown','Valores compostos ou identificadores divergentes na resposta.'
    if actual in ids:return 'matched','Identificador '+actual+' consta nos valores retornados pela categoria.'
    return 'review','Identificador '+actual+' não consta nos valores retornados pela categoria: '+', '.join(ids)+'.'


def compare(definitions,item):
    rules=attributes(definitions)
    if rules is None:return dict(state='unknown',message='Regras da categoria não verificáveis.')
    rows=[];groups=[('Anúncio principal',item.get('attributes'))];variants=item.get('variations');seen=set();variation_unknown=False
    if not isinstance(variants,list) or len(variants)>1000:variation_unknown=True
    else:
        for variant in variants:
            if not isinstance(variant,dict):variation_unknown=True;break
            vid=identifier(variant.get('id'))
            if vid is None or vid in seen:variation_unknown=True;break
            seen.add(vid)
            for key in ('attributes','attribute_combinations'):groups.append(('Variação '+vid+' · '+('características' if key=='attributes' else 'combinação'),variant.get(key)))
        if variation_unknown:groups=groups[:1]
    inspected=0;truncated=False
    for location,group in groups:
        parsed=attributes(group)
        if parsed is None:
            rows.append(dict(name='Atributos não verificáveis',location=location,state='unknown',message='Grupo de atributos ausente ou inválido na resposta.'))
        else:
            for code,row in parsed.items():
                inspected+=1
                if inspected>5000:truncated=True;break
                definition=rules.get(code)
                if not definition or definition.get('value_type')!='boolean':continue
                state,message=check(definition,row);name=definition.get('name');name=name if isinstance(name,str) and name.strip() and len(name)<=300 else code
                tags=definition.get('tags');managed=isinstance(tags,dict) and any(tags.get(t) is True for t in ('read_only','fixed','inferred'))
                rows.append(dict(name=name,location=location,state=state,message=message,managed=managed))
        if len(rows)>=100 or truncated:truncated=True;break
    return dict(state='read',rows=rows[:100],variation_unknown=variation_unknown,truncated=truncated)


def render(result):
    esc=lambda v:escape(str(v),quote=True)
    out='<section class="cs-boolean"><h4>Atributos sim/não</h4><p>Identificadores comparados com os valores retornados pela categoria.</p>'
    if result.get('state')!='read':return out+'<p>Valores booleanos não verificados. '+esc(result.get('message','Consulta indisponível.'))+'</p></section>'
    labels={'matched':'Identificador encontrado na categoria','review':'Conferir identificador','unknown':'Não verificado'}
    for row in result['rows']:
        out+='<article class="cs-bool-row" data-value-state="'+row['state']+'"><h5>'+esc(row['name'])+'</h5><p>'+esc(row['location'])+'</p><strong>'+labels[row['state']]+'</strong><p>'+esc(row['message'])+'</p>'
        if row.get('managed'):out+='<p>Campo gerenciado pelo Mercado Livre; não recomenda edição direta pelo vendedor.</p>'
        elif row['state']=='review':out+='<p>Confira a opção e a categoria na ficha do Mercado Livre.</p>'
        out+='</article>'
    if not result['rows']:out+='<p>Nenhum atributo booleano identificado para esta conferência.</p>'
    if result.get('variation_unknown'):out+='<p>Variações não verificáveis: nenhuma conclusão foi emitida para elas.</p>'
    if result.get('truncated'):out+='<p>Leitura limitada a 100 resultados e 5.000 entradas; não certifica cobertura integral.</p>'
    out+='<details><summary>Limites da conferência</summary><p>Não interpreta texto livre, não presume sim/não pela ausência e não rejeita valores personalizados de outros tipos de atributo. Identificador encontrado não certifica coerência do texto, aplicabilidade ou validade integral da ficha. Uma divergência nesta consulta não comprova erro de publicação.</p></details>'
    return out+'</section><style>.cs-bool-row{border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.cs-bool-row[data-value-state=review]{border-left:4px solid #c08d54}.cs-bool-row h5{font:inherit;font-weight:700;margin:0 0 8px}</style>'
