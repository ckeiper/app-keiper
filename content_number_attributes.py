"""Conservative lexical evidence for value_type=number, without invented ranges."""
import re
from html import escape
from content_required_attributes import attributes
from content_boolean_attributes import identifier

SIMPLE=re.compile(r'[+-]?[0-9]+(?:[.,][0-9]+)?')


def check(definition,row):
    if str(row.get('value_id'))=='-1':return 'unknown','Valor declarado não aplicável; formato numérico não certificado.'
    if row.get('value_id') is not None and identifier(row.get('value_id')) is None:
        return 'unknown','Identificador em formato não verificável; confira a representação do valor.'
    value=row.get('value_name')
    if not isinstance(value,str) or not value.strip() or len(value)>10000:
        return 'unknown','Texto numérico ausente ou fora do limite desta conferência; o ID não é interpretado como quantidade.'
    if row.get('value_struct') is not None:
        return 'unknown','Valor estruturado: formato simples não verificado.'
    extra=row.get('values')
    if extra is not None and extra!=[]:
        if (not isinstance(extra,list) or len(extra)!=1 or not isinstance(extra[0],dict)
                or extra[0].get('name')!=value
                or (extra[0].get('id') is not None and identifier(extra[0].get('id')) is None)
                or identifier(extra[0].get('id'))!=identifier(row.get('value_id'))
                or extra[0].get('struct') is not None):
            return 'unknown','Valores compostos ou representações divergentes; confira o valor na ficha.'
    value=value.strip()
    # Recognizing digits does not determine decimal locale, limits or API acceptance.
    if SIMPLE.fullmatch(value):
        return 'matched','Texto com formato numérico simples identificado. Sinal e separador não foram convertidos; aceitação e faixa não certificadas.'
    return 'review','Texto fora do formato numérico simples desta conferência. Confira o valor e o formato no Mercado Livre; isso não confirma erro de publicação.'


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
                if not definition or definition.get('value_type')!='number':continue
                state,message=check(definition,row);name=definition.get('name');name=name if isinstance(name,str) and name.strip() and len(name)<=300 else code
                tags=definition.get('tags');managed=isinstance(tags,dict) and any(tags.get(t) is True for t in ('read_only','fixed','inferred'))
                rows.append(dict(name=name,location=location,state=state,message=message,managed=managed))
        if len(rows)>=100 or truncated:truncated=True;break
    return dict(state='read',rows=rows[:100],variation_unknown=variation_unknown,truncated=truncated)

def render(result):
    esc=lambda value:escape(str(value),quote=True)
    out='<section class="cs-number-values"><h4>Atributos numéricos simples</h4><p>Formato do texto retornado para campos do tipo número, no anúncio e nas variações.</p>'
    if result.get('state')!='read':return out+'<p>Números não verificados. '+esc(result.get('message','Consulta indisponível.'))+'</p></section>'
    labels={'matched':'Formato numérico identificado','review':'Conferir formato','unknown':'Não verificado'}
    for row in result['rows']:
        out+='<article class="cs-number-row" data-number-state="'+row['state']+'"><h5>'+esc(row['name'])+'</h5><p>'+esc(row['location'])+'</p><strong>'+labels[row['state']]+'</strong><p>'+esc(row['message'])+'</p>'
        if row.get('managed'):out+='<p>Campo gerenciado pelo Mercado Livre; confira a origem sem recomendar edição direta.</p>'
        out+='</article>'
    if not result['rows']:out+='<p>Nenhum atributo do tipo número identificado nos grupos conferidos.</p>'
    if result.get('variation_unknown'):out+='<p>Variações não verificáveis; nenhuma conclusão foi emitida para elas.</p>'
    if result.get('truncated'):out+='<p>Leitura limitada a 100 resultados e 5.000 entradas; não certifica cobertura integral.</p>'
    out+='<details><summary>Limites da conferência numérica</summary><p>Não determina faixa, precisão, positividade ou exigência de inteiro. Não interpreta o ID como quantidade, não converte separadores nem rejeita números por não estarem nas sugestões da categoria. Formatos como fração, notação científica ou múltiplos valores exigem conferência, sem erro confirmado. Formato simples não certifica validade, semântica ou aceitação da publicação. Campos sem valor permanecem não verificados.</p></details>'
    return out+'</section><style>.cs-number-row{border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.cs-number-row[data-number-state=review]{border-left:4px solid #c08d54}.cs-number-row h5{font:inherit;font-weight:700;margin:0 0 8px}</style>'
