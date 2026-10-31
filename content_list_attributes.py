"""Compare explicit list IDs to category options; never reject custom text."""
from html import escape
from content_required_attributes import attributes
from content_boolean_attributes import identifier


def check(definition,row):
    values=definition.get('values')
    if not isinstance(values,list) or not 1<=len(values)<=2000:
        return 'unknown','Opções da categoria ausentes ou fora do limite desta conferência.'
    ids=[]
    for option in values:
        if not isinstance(option,dict) or identifier(option.get('id')) is None:
            return 'unknown','Identificadores das opções não verificáveis na resposta.'
        ids.append(identifier(option['id']))
    if len(set(ids))!=len(ids) or '-1' in ids:
        return 'unknown','Opções repetidas ou não aplicáveis na resposta da categoria.'
    actual=identifier(row.get('value_id'))
    if actual is None:
        return 'unknown','Sem identificador simples verificável; texto personalizado não é rejeitado nem convertido em opção.'
    if actual=='-1':
        return 'unknown','Valor declarado não aplicável; opção não certificada.'
    extra=row.get('values')
    if extra is not None and extra!=[]:
        if not isinstance(extra,list) or len(extra)!=1 or not isinstance(extra[0],dict) or identifier(extra[0].get('id'))!=actual:
            return 'unknown','Valor composto ou identificadores divergentes; confira a ficha antes de concluir.'
    if actual in ids:
        return 'matched','Identificador '+actual+' encontrado entre '+str(len(ids))+' opções retornadas pela categoria.'
    return 'review','Identificador '+actual+' não identificado entre '+str(len(ids))+' opções nesta leitura. Confira a categoria e o valor atual; isso não confirma erro de publicação.'


def compare(definitions,item):
    rules=attributes(definitions)
    if rules is None:return dict(state='unknown',message='Regras da categoria não verificáveis.',rows=[])
    groups=[('Anúncio principal',item.get('attributes'))];variants=item.get('variations');seen=set();variation_unknown=False
    if not isinstance(variants,list) or len(variants)>1000:variation_unknown=True
    else:
        for variant in variants:
            if not isinstance(variant,dict):variation_unknown=True;break
            vid=identifier(variant.get('id'))
            if vid is None or vid in seen:variation_unknown=True;break
            seen.add(vid)
            for key,label in [('attributes','características'),('attribute_combinations','combinação')]:
                groups.append(('Variação '+vid+' · '+label,variant.get(key)))
        if variation_unknown:groups=groups[:1]
    rows=[];inspected=0;truncated=False
    for location,group in groups:
        parsed=attributes(group)
        if parsed is None:
            rows.append(dict(name='Atributos não verificáveis',location=location,state='unknown',message='Grupo ausente ou inválido na resposta.'))
        else:
            for code,row in parsed.items():
                inspected+=1
                if inspected>5000:truncated=True;break
                definition=rules.get(code)
                if not definition or definition.get('value_type')!='list':continue
                state,message=check(definition,row);name=definition.get('name');name=name if isinstance(name,str) and name.strip() and len(name)<=300 else code
                tags=definition.get('tags');managed=isinstance(tags,dict) and any(tags.get(t) is True for t in ('read_only','fixed','inferred'))
                rows.append(dict(name=name,location=location,state=state,message=message,managed=managed))
        if len(rows)>=100 or truncated:truncated=True;break
    return dict(state='read',rows=rows[:100],variation_unknown=variation_unknown,truncated=truncated)


def render(result):
    esc=lambda value:escape(str(value),quote=True)
    out='<section class="cs-list-values"><h4>Opções dos atributos de lista</h4><p>Compara identificadores explícitos com as opções retornadas pela categoria, no anúncio e em cada variação.</p>'
    if result.get('state')!='read':return out+'<p>Opções não verificadas. '+esc(result.get('message','Consulta indisponível.'))+'</p></section>'
    labels={'matched':'Identificador encontrado','review':'Conferir referência da opção','unknown':'Não verificado'}
    for row in result['rows']:
        out+='<article class="cs-list-row" data-list-state="'+row['state']+'"><h5>'+esc(row['name'])+'</h5><p>'+esc(row['location'])+'</p><strong>'+labels[row['state']]+'</strong><p>'+esc(row['message'])+'</p>'
        if row.get('managed'):out+='<p>Campo gerenciado pelo Mercado Livre; confira a origem sem recomendar edição direta.</p>'
        out+='</article>'
    if not result['rows']:out+='<p>Nenhum atributo do tipo lista identificado nos grupos conferidos.</p>'
    if result.get('variation_unknown'):out+='<p>Variações não verificáveis; nenhuma conclusão foi emitida para elas.</p>'
    if result.get('truncated'):out+='<p>Leitura limitada a 100 resultados e 5.000 entradas; não certifica cobertura integral.</p>'
    out+='<details><summary>Limites da comparação</summary><p>O texto pode ser personalizado e não é comparado ao nome da opção. Encontrar o ID não certifica coerência do texto, aplicabilidade ou validade integral. Não encontrar o ID na leitura atual não comprova erro ou exigência de troca. Ausência, valor não aplicável e valores compostos permanecem não verificados. A comparação não decide quais atributos são obrigatórios.</p></details>'
    return out+'</section><style>.cs-list-row{border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.cs-list-row[data-list-state=review]{border-left:4px solid #c08d54}.cs-list-row h5{font:inherit;font-weight:700;margin:0 0 8px}</style>'
