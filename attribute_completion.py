"""Evidence-based suggestions. No model guesses and no marketplace writes."""
import hashlib
import json
import re
import unicodedata
from decimal import Decimal,InvalidOperation
from content_required_attributes import attributes,has_value
from content_technical_specs import parse,PresenceIndex,publication
from listing_content_snapshot import read,ContentUnavailable,ContentRateLimited

BLOCKED=('read_only','inferred','fixed','others','restricted_values','product_pk','parent_pk','child_pk','allow_variations','variation_attribute','defines_picture')
HIDDEN=('hidden','new_hidden','used_hidden')
EXTRACTOR_VERSION=6


def fold(value):
    value=unicodedata.normalize('NFKD',value).casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',''.join(c for c in value if not unicodedata.combining(c))).split())


def known_key(value):
    value=unicodedata.normalize('NFKD',value).casefold()
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())


def unit_match(raw,unit):
    # Unit IDs retain symbols and case (e.g. MB is not Mb). Full textual
    # names may ignore case/accents, but short abbreviations are not guessed.
    if unicodedata.normalize('NFC',raw.strip())==unicodedata.normalize('NFC',unit['id'].strip()):return True
    name=unit.get('name')
    return isinstance(name,str) and len(name.strip())>4 and known_key(raw)==known_key(name)


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def owned(token,seller,item_id,get):
    if not isinstance(token,str) or not token or not re.fullmatch(r'[1-9][0-9]{0,19}',str(seller)) or not re.fullmatch(r'MLB[0-9]{1,20}',item_id):raise ContentUnavailable('Conta ou anúncio inválido.')
    account=read(token,'/users/me',get)
    if str(account.get('id'))!=str(seller):raise ContentUnavailable('Autorização de outra conta.')
    item=read(token,'/items/'+item_id+'?include_internal_attributes=true&include_attributes=all',get)
    if item.get('id')!=item_id or item.get('site_id')!='MLB' or str(item.get('seller_id'))!=str(seller):raise ContentUnavailable('Anúncio de outra conta ou resposta divergente.')
    return item


def gather(token,seller,item_id,get):
    item=owned(token,seller,item_id,get);category=item.get('category_id')
    if not isinstance(category,str) or not re.fullmatch(r'MLB[0-9]{1,20}',category):raise ContentUnavailable('Categoria não verificada.')
    description=None;warnings=[]
    try:
        desc=read(token,'/items/'+item_id+'/description',get);value=desc.get('plain_text')
        if isinstance(value,str) and len(value)<=200000:description=value
        else:warnings.append('Descrição não verificável.')
    except ContentRateLimited:raise
    except ContentUnavailable:warnings.append('Descrição indisponível; somente fontes verificadas serão usadas.')
    definitions=read(token,'/categories/'+category+'/attributes',get,list)
    rules=attributes(definitions)
    if rules is None:raise ContentUnavailable('Atributos da categoria inválidos ou excessivos.')
    specs=read(token,'/categories/'+category+'/technical_specs/input',get)
    try:sheet=parse(specs)
    except ValueError:raise ContentUnavailable('Ficha técnica não verificável.') from None
    reason=''
    if item.get('catalog_listing') is not False:reason='Catálogo ou modalidade não verificada: envio bloqueado nesta etapa.'
    if item.get('status') not in ('active','paused'):reason='Estado do anúncio não permite envio nesta etapa.'
    if attributes(item.get('attributes')) is None:reason='Atributos atuais não verificáveis.'
    if PresenceIndex(item).variants is None:reason='Variações atuais não verificáveis.'
    tags=item.get('tags')
    if not isinstance(tags,list) or any(not isinstance(t,str) for t in tags):reason='Modalidade do anúncio não verificada.'
    scope=[item_id];up=item.get('user_product_id')
    if up:
        if not isinstance(up,str) or not re.fullmatch(r'MLBU[0-9]{1,25}',up):reason='Vínculo User Product não verificado.'
        else:
            linked=read(token,f'/users/{seller}/items/search?user_product_id={up}',get)
            if not isinstance(linked.get('paging'),dict) or type(linked['paging'].get('total')) is not int or linked['paging']['total']!=1 or linked.get('results')!=[item_id]:
                reason='User Product compartilhado ou vínculo incompleto: envio bloqueado para não alterar outros anúncios.'
    elif item.get('family_id') or (isinstance(tags,list) and 'user_product_listing' in tags):reason='Vínculo do anúncio não verificado.'
    title=item.get('title');title=title if isinstance(title,str) and len(title)<=1000 else ''
    subset={k:item.get(k) for k in ('id','seller_id','site_id','category_id','status','condition','title','attributes','variations','catalog_listing','catalog_product_id','user_product_id','family_id','family_name','tags')}
    if isinstance(subset['variations'],list) and all(isinstance(v,dict) for v in subset['variations']):
        subset['variations']=[{k:v.get(k) for k in ('id','attributes','attribute_combinations')} for v in subset['variations']]
    return dict(item=item,rules=rules,sheet=sheet,description=description,title=title,warnings=warnings,blocked=reason,
                fingerprint=digest(dict(item=subset,description=description,rules=rules,sheet=sheet,scope=scope)))


def number(raw):
    if not isinstance(raw,str) or not re.fullmatch(r'-?[0-9]+(?:[.,][0-9]+)?',raw):return None
    # A single separator followed by three digits can mean decimal or thousands.
    if re.fullmatch(r'-?[0-9]{1,3}[.,][0-9]{3}',raw):return None
    try:value=Decimal(raw.replace(',','.'))
    except InvalidOperation:return None
    return value if value.is_finite() else None


def value_for(rule,raw):
    if not isinstance(raw,str) or not 1<=len(raw)<=1000 or any(ord(c)<32 for c in raw):return None
    maximum=rule.get('value_max_length')
    if type(maximum) is int and maximum>0 and len(raw)>maximum:return None
    kind=rule.get('value_type')
    if kind in ('string','list','boolean'):
        options=rule.get('values')
        choices=[];wanted=known_key(raw)
        if isinstance(options,list) and 1<=len(options)<=1000:
            choices=[o for o in options if isinstance(o,dict) and isinstance(o.get('name'),str) and known_key(o['name'])==wanted and isinstance(o.get('id'),(str,int)) and not isinstance(o.get('id'),bool) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(o['id'])) and str(o['id'])!='-1']
        if len(choices)==1:
            code=str(choices[0]['id']);return dict(value_id=code),dict(kind='id',value=code)
        if len(choices)>1 or kind!='string':return None
        return dict(value_name=raw),dict(kind='string',value=raw)
    if kind=='number':
        n=number(raw)
        if n is not None:return dict(value_name=raw),dict(kind='number',value=str(n))
    if kind=='number_unit':
        match=re.fullmatch(r'(-?[0-9]+(?:[.,][0-9]+)?)\s+([^\n]{1,100})',raw)
        units=rule.get('allowed_units')
        if not match or not isinstance(units,list) or not 1<=len(units)<=200:return None
        choices=[u for u in units if isinstance(u,dict) and isinstance(u.get('id'),str) and 1<=len(u['id'])<=100 and unit_match(match[2],u)]
        n=number(match[1])
        if len(choices)==1 and n is not None:
            unit=choices[0]['id'];return dict(value_name=match[1]+' '+unit),dict(kind='unit',value=str(n),unit=unit)
    return None


def analyze(facts,manual_inputs=None,actor=None):
    manual_inputs=[] if manual_inputs is None else manual_inputs
    if not isinstance(manual_inputs,list) or len(manual_inputs)>50:raise ValueError('Informe até 50 campos por revisão.')
    manual={}
    for entry in manual_inputs:
        if not isinstance(entry,dict) or set(entry)!={'id','value','note'}:raise ValueError('Dado informado inválido.')
        code=entry['id'];value=entry['value'];note=entry['note']
        if not isinstance(code,str) or code in manual or not isinstance(value,str) or not value.strip() or len(value)>1000 or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('Valor informado inválido ou repetido.')
        if not isinstance(note,str) or len(note)>500 or any(ord(c)<32 or ord(c)==127 for c in note):raise ValueError('Fonte informada inválida.')
        manual[code]=dict(id=code,value=value.strip(),note=note.strip())
    if manual and (type(actor) is not int or actor<=0):raise ValueError('Responsável pelo dado não identificado.')
    item=facts['item'];rules=facts['rules'];sheet=facts['sheet'];index=PresenceIndex(item)
    definitions=dict(sheet)
    for code,rule in rules.items():definitions.setdefault(code,dict(id=code,name=rule.get('name',code),tags=[]))
    if len(definitions)>5000:raise ContentUnavailable('Inventário excede o limite desta análise.')
    alias={}
    for code,definition in definitions.items():
        for name in (code,definition.get('name',''),rules.get(code,{}).get('name','')):
            if isinstance(name,str) and fold(name):alias.setdefault(fold(name),set()).add(code)
    from attribute_text_evidence import collect
    if item.get('variations'):
        from attribute_common_prose import read as common_prose
        evidence,uncertain=common_prose(facts['title'],facts['description'],item,rules,alias,fold)
    else:evidence,uncertain=collect(facts['title'],facts['description'],alias,fold)
    proposals=[];rows=[];manual_fields=[];main=attributes(item.get('attributes'))
    for code,definition in definitions.items():
        rule=rules.get(code);tags=rule.get('tags') if rule else None;sheet_tags=definition.get('tags',[])
        valid=isinstance(tags,dict) and all(type(v) is bool for v in tags.values())
        hidden=any((valid and tags.get(k) is True) or k in sheet_tags for k in HIDDEN)
        blocked=not valid or any(tags.get(k) is True for k in BLOCKED) or any(k in sheet_tags for k in BLOCKED) or str(rule.get('hierarchy','')).upper() in ('PARENT_PK','CHILD_PK')
        state,message,variants=index.evidence(code)
        declared=main.get(code) if main is not None else None
        if declared is not None and str(declared.get('value_id'))=='-1':message='Não aplicável declarado no anúncio; conferir aplicabilidade'
        sources=evidence.get(code,[]);distinct={unicodedata.normalize('NFC',' '.join(e['raw'].split())).casefold() for e in sources}
        text_review=code in uncertain or len(distinct)>1
        if text_review:message+='; texto precisa de conferência antes de sugerir valor'
        name=definition.get('name');name=name if isinstance(name,str) and 1<=len(name)<=300 else code
        rows.append(dict(id=code,name=name+(' · Oculto' if hidden else ''),state=state,message=message,required='required' in sheet_tags,
                         managed=any((valid and tags.get(k) is True) or k in sheet_tags for k in ('read_only','fixed','inferred')),variation_states=variants,publication=publication(code,rules,{})))
        # Only add genuinely empty common attributes. Never replace N/A, structures,
        # existing values, or variation-owned evidence; identity fields are blocked.
        current=main.get(code) if main is not None else None
        if blocked or main is None or has_value(current) is not False or (current is not None and current.get('value_id') not in (None,'')):continue
        if variants is None or any(v!='r' for v in variants) or (index.variants and len(index.variants)>100):continue
        if rule.get('value_type') in ('string','list','boolean','number','number_unit'):
            examples=rule.get('allowed_units',[]) if rule.get('value_type')=='number_unit' else rule.get('values',[])
            examples=[v.get('name',v.get('id','')) for v in examples[:10] if isinstance(v,dict)] if isinstance(examples,list) else []
            manual_fields.append(dict(id=code,name=name,hidden=hidden,value_type=rule['value_type'],examples=[v[:100] for v in examples if isinstance(v,str)]))
        if code in manual:
            entry=manual[code];parsed=value_for(rule,entry['value'])
            if not parsed:raise ValueError('Valor incompatível com as regras verificadas de '+name+'.')
            payload,expected=parsed
            proposals.append(dict(id=code,name=name,hidden=hidden,manual=True,value=entry['value'],payload=dict(id=code,**payload),expected=expected,before=current,evidence=[dict(source='Informado por você',text=entry['note'] or 'Dado declarado pelo consultor nesta revisão.',raw=entry['value'],reading='manual')]))
            continue
        if text_review:continue
        if len(distinct)!=1:continue
        parsed=value_for(rule,sources[0]['raw'])
        if not parsed:continue
        payload,expected=parsed
        proposals.append(dict(id=code,name=name,hidden=hidden,value=sources[0]['raw'],payload=dict(id=code,**payload),expected=expected,before=current,evidence=sources[:5]))
    from attribute_variations import review
    variation_fields,variation_proposals,variation_snapshot=review(facts,definitions,manual)
    manual_fields.extend(variation_fields);proposals.extend(variation_proposals)
    warnings=list(facts['warnings'])
    if item.get('variations') and variation_snapshot is None:warnings.append('Preenchimento por variação indisponível: estrutura incompleta, IDs não verificáveis ou limite desta etapa (100 variações e 256 KiB).')
    if len(variation_fields)>=1000:warnings.append('Até 1.000 destinos de variação são oferecidos por revisão. Após aplicar os campos, faça nova leitura para os demais.')
    if set(manual)-{f['id'] for f in manual_fields}:raise ValueError('Campo indisponível para preenchimento nesta análise.')
    manual_fields.sort(key=lambda f:(fold(f['name']),f['id']))
    proposals.sort(key=lambda p:(not p.get('manual',False),not p['hidden'],fold(p['name']),p['id']))
    rows.sort(key=lambda r:(not r['required'],fold(r['name']),r['id']))
    return dict(variation_snapshot=variation_snapshot,manual_inputs=list(manual.values()),manual_actor=actor if manual else None,manual_fields=manual_fields,extractor_version=EXTRACTOR_VERSION,title=facts['title'],fingerprint=facts['fingerprint'],blocked=facts['blocked'],warnings=warnings,proposals=proposals[:50],proposal_total=len(proposals),
                inventory=dict(state='read',rows=rows,total=len(rows),variation_ids=index.ids,variation_count=None if index.variants is None else len(index.variants),incomplete_flag=None))


def matches(proposal,item):
    if proposal.get('variation_id'):
        from attribute_variations import variant_id
        variants=item.get('variations')
        if not isinstance(variants,list) or any(not isinstance(v,dict) for v in variants):return False
        selected=[v for v in variants if variant_id(v.get('id'))==proposal['variation_id']]
        if len(selected)!=1:return False
        return matches(dict(proposal,id=proposal['attribute_id'],variation_id=None),selected[0])
    group=attributes(item.get('attributes'));row=group.get(proposal['id']) if group is not None else None
    if not row or str(row.get('value_id'))=='-1':return False
    if row.get('values'):
        values=row['values']
        if not isinstance(values,list) or len(values)!=1 or not isinstance(values[0],dict):return False
        row=dict(row)
        for outer,inner in [('value_id','id'),('value_name','name'),('value_struct','struct')]:
            a=row.get(outer);b=values[0].get(inner)
            if a is not None and b is not None and a!=b:return False
            if a is None:row[outer]=b
    expected=proposal['expected'];kind=expected['kind']
    if kind=='id':return str(row.get('value_id'))==expected['value']
    if kind=='string':return isinstance(row.get('value_name'),str) and row['value_name'].strip()==expected['value'].strip()
    struct=row.get('value_struct')
    if kind=='number':return number(str(row.get('value_name','')))==Decimal(expected['value'])
    if kind=='unit':
        if isinstance(struct,dict):
            try:return not isinstance(struct.get('number'),bool) and Decimal(str(struct.get('number')))==Decimal(expected['value']) and struct.get('unit')==expected['unit']
            except InvalidOperation:return False
        match=re.fullmatch(r'(-?[0-9]+(?:[.,][0-9]+)?)\s+(.+)',str(row.get('value_name','')))
        return bool(match and number(match[1])==Decimal(expected['value']) and match[2]==expected['unit'])
    return False
