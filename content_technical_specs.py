"""Category technical-sheet completeness, separate from publication validation."""
from html import escape
from content_required_attributes import attributes,presence,variation_details


def parse(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('groups'),list) or len(payload['groups'])>100:raise ValueError
    result={};entries=0
    for group in payload['groups']:
        if not isinstance(group,dict) or not isinstance(group.get('components'),list) or len(group['components'])>200:raise ValueError
        for component in group['components']:
            if not isinstance(component,dict) or not isinstance(component.get('attributes'),list):raise ValueError
            entries+=len(component['attributes'])
            if entries>5000:raise ValueError
            for row in component['attributes']:
                if not isinstance(row,dict):raise ValueError
                code=row.get('id');tags=row.get('tags')
                if not isinstance(code,str) or not code.strip() or len(code)>200 or code in result:raise ValueError
                if not isinstance(tags,list) or len(tags)>100 or any(not isinstance(t,str) or len(t)>100 for t in tags):raise ValueError
                result[code]=row
    return result


def publication(code,rules,conditional):
    if rules is None:return 'unknown'
    rule=rules.get(code)
    if rule is None:return 'technical'
    tags=rule.get('tags')
    keys=('required','conditional_required','new_required','catalog_listing_required')
    if not isinstance(tags,dict) or any(k in tags and type(tags[k]) is not bool for k in keys):return 'unknown'
    if tags.get('required') is True:return 'publication'
    if tags.get('conditional_required') is True:
        if conditional.get('state')=='read' and code in conditional.get('required_ids',[]):return 'conditional'
        return 'context'
    if tags.get('new_required') is True or tags.get('catalog_listing_required') is True:return 'context'
    return 'technical'


def compare(payload,category_attributes,item,conditional=None):
    try:definitions=parse(payload)
    except ValueError:return dict(state='unknown',message='Ficha técnica ausente, incompleta ou não verificável na resposta.')
    rules=attributes(category_attributes);conditional=conditional or {};rows=[]
    for code,definition in definitions.items():
        if 'required' not in definition['tags']:continue
        state,message=presence(code,item)
        name=definition.get('name');name=name if isinstance(name,str) and name.strip() and len(name)<=300 else code
        category_tags=rules.get(code,{}).get('tags') if rules is not None else None
        managed=any(t in definition['tags'] for t in ('read_only','inferred','fixed')) or (isinstance(category_tags,dict) and any(category_tags.get(t) is True for t in ('read_only','inferred','fixed')))
        rows.append(dict(id=code,name=name,state=state,message=message,publication=publication(code,rules,conditional),
            variations=variation_details(code,item),managed=managed))
    tags=item.get('tags');flag='incomplete_technical_specs' in tags if isinstance(tags,list) and all(isinstance(t,str) for t in tags) else None
    return dict(state='read',rows=rows[:100],total=len(rows),incomplete_flag=flag)


def render(result):
    esc=lambda v:escape(str(v),quote=True)
    out='<section class="cs-technical"><h4>Ficha técnica da categoria</h4>'
    if result.get('state')!='read':return out+'<p>Ficha técnica não verificada. '+esc(result.get('message','Consulta indisponível.'))+'</p></section>'
    if result.get('incomplete_flag') is True:out+='<p>O Mercado Livre retornou o sinal de ficha técnica incompleta nesta leitura.</p>'
    labels={'publication':'Também obrigatório na regra de publicação consultada','conditional':'Também obrigatório na consulta condicional do Mercado Livre','technical':'Exigido na ficha técnica · não confirma impedimento de publicação','context':'Regra de publicação depende do contexto; confira a condição ou o catálogo','unknown':'Obrigatoriedade de publicação não verificada'}
    counts={key:sum(row['state']==key for row in result['rows']) for key in ('informed','review','unknown')}
    out+='<p>'+str(result['total'])+' campos exigidos retornados. Nesta tela: '+str(counts['informed'])+' com valor identificado, '+str(counts['review'])+' para conferir e '+str(counts['unknown'])+' não verificáveis.</p>'
    for row in result['rows']:
        out+='<article class="cs-tech-row" data-presence="'+row['state']+'"><h5>'+esc(row['name'])+'</h5><p>'+labels[row['publication']]+'</p><strong>'+esc(row['message'])+'</strong>'
        if row['managed']:out+='<p>Campo gerenciado pelo Mercado Livre; confira a ficha sem presumir edição direta pelo vendedor.</p>'
        elif row['state']=='review':out+='<p>Confira o preenchimento e a aplicabilidade na ficha do anúncio.</p>'
        variants=row['variations']
        if variants:
            out+='<details><summary>Conferir variações</summary><ul>'
            names={'informed':'Valor identificado','review':'Sem valor identificado','unknown':'Não verificável'}
            for variant in variants[:100]:out+='<li>Variação '+esc(variant['id'])+': '+names[variant['state']]+'</li>'
            if len(variants)>100:out+='<li>Exibidas 100 de '+str(len(variants))+' variações.</li>'
            out+='</ul></details>'
        elif variants is None:out+='<p>Variações não verificáveis.</p>'
        out+='</article>'
    if not result['rows']:out+='<p>Nenhum campo marcado como exigido na resposta consultada. Isso não certifica a ficha completa.</p>'
    if result['total']>100:out+='<p>Exibidos 100 de '+str(result['total'])+' campos exigidos.</p>'
    out+='<details><summary>Limites desta conferência</summary><p>Presença não valida o valor. Ausência na variação não comprova erro: o atributo pode estar no anúncio principal e a aplicabilidade depende da categoria. As exigências da ficha técnica e as regras de publicação são consultas distintas. Esta leitura não certifica aprovação, penalização ou perda de exposição, nem altera o anúncio ou as revisões manuais.</p></details>'
    return out+'</section><style>.cs-tech-row{border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.cs-tech-row[data-presence=review]{border-left:4px solid #c08d54}.cs-tech-row h5{font:inherit;font-weight:700;margin:0 0 8px}.cs-technical summary{cursor:pointer;margin:12px 0}</style>'
