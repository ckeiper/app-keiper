"""Declared missing variation attributes; preserve existing variants and values."""
from copy import deepcopy
import json
import re
from content_required_attributes import attributes,has_value


def variant_id(value):
    if isinstance(value,bool) or not isinstance(value,(int,str)):return None
    text=str(value)
    return text if re.fullmatch(r'[1-9][0-9]{0,24}',text) else None


def snapshot(item):
    rows=item.get('variations')
    if not isinstance(rows,list) or not 1<=len(rows)<=100:return None
    result=[];seen=set()
    for row in rows:
        if not isinstance(row,dict):return None
        if any(row.get(k) for k in ('catalog_product_id','user_product_id','family_id')):return None
        vid=variant_id(row.get('id'))
        if not vid or vid in seen or attributes(row.get('attributes')) is None or attributes(row.get('attribute_combinations')) is None:return None
        seen.add(vid)
        result.append({k:deepcopy(row[k]) for k in ('id','attributes','attribute_combinations')})
    if len(json.dumps(result,ensure_ascii=True))>262144:return None
    return result


def empty(row):
    return has_value(row) is False and (row is None or row.get('value_id') in (None,''))


def review(facts,definitions,manual):
    from attribute_completion import BLOCKED,HIDDEN,value_for,fold
    saved=snapshot(facts['item']);main=attributes(facts['item'].get('attributes'))
    if saved is None or main is None:return [],[],None
    fields=[];proposals=[]
    for row in saved:
        vid=str(row['id']);group=attributes(row['attributes']);combinations=attributes(row['attribute_combinations'])
        labels=[a.get('value_name') for a in row['attribute_combinations'] if isinstance(a.get('value_name'),str) and a['value_name'].strip()]
        label=' / '.join(labels)[:160]
        label=('Variação '+vid)+(' · '+label if label else '')
        if len(fields)>=1000:break
        if len(group)>=2000:continue
        for code,rule in sorted(facts['rules'].items()):
            if len(fields)>=1000:break
            tags=rule.get('tags');definition=definitions.get(code,{})
            sheet_tags=definition.get('tags',[])
            if not isinstance(tags,dict) or any(type(v) is not bool for v in tags.values()) or tags.get('variation_attribute') is not True:continue
            if any(tags.get(t) is True or t in sheet_tags for t in BLOCKED if t!='variation_attribute') or str(rule.get('hierarchy','')).upper() in ('PARENT_PK','CHILD_PK'):continue
            if not empty(main.get(code)) or not empty(group.get(code)) or code in combinations:continue
            if rule.get('value_type') not in ('string','list','boolean','number','number_unit'):continue
            name=definition.get('name',rule.get('name',code));name=name if isinstance(name,str) and 1<=len(name)<=300 else code
            hidden=any(tags.get(t) is True or t in sheet_tags for t in HIDDEN)
            key='v:'+vid+':'+code
            if key in definitions:continue
            examples=rule.get('allowed_units',[]) if rule['value_type']=='number_unit' else rule.get('values',[])
            examples=[e.get('name',e.get('id','')) for e in examples[:10] if isinstance(e,dict)] if isinstance(examples,list) else []
            fields.append(dict(id=key,attribute_id=code,variation_id=vid,name=label+' · '+name,hidden=hidden,value_type=rule['value_type'],examples=[e[:100] for e in examples if isinstance(e,str)]))
            if key in manual:
                entry=manual[key];parsed=value_for(rule,entry['value'])
                if not parsed:raise ValueError('Valor incompatível com as regras verificadas de '+name+' nesta variação.')
                payload,expected=parsed
                proposals.append(dict(id=key,attribute_id=code,variation_id=vid,name=name+' · '+label,hidden=hidden,manual=True,value=entry['value'],payload=dict(id=code,**payload),expected=expected,before=group.get(code),evidence=[dict(source='Informado por você · '+label,text=entry['note'] or 'Dado declarado pelo consultor para esta variação.',raw=entry['value'],reading='manual')]))
    fields.sort(key=lambda f:(fold(f['name']),f['id']))
    return fields,proposals,saved


def payload(proposals,item):
    common=[p['payload'] for p in proposals if not p.get('variation_id')]
    selected=[p for p in proposals if p.get('variation_id')]
    result={'attributes':common} if common else {}
    if not selected:return result
    saved=snapshot(item)
    if saved is None:raise ValueError('Variações não verificáveis para envio.')
    by_id={str(v['id']):v for v in saved};updates={}
    for p in selected:
        vid=p['variation_id'];code=p['attribute_id']
        if vid not in by_id or p['payload'].get('id')!=code:raise ValueError('Destino da atualização não verificável.')
        group=attributes(by_id[vid]['attributes'])
        if not empty(group.get(code)):raise ValueError('O campo da variação não está vazio.')
        updates.setdefault(vid,{})[code]=p['payload']
    variants=[]
    for row in saved:
        vid=str(row['id']);out={'id':row['id']}
        if vid in updates:
            # The official update requires all existing attributes of each edited
            # variation. Other variations are retained by ID, never recreated.
            out['attributes']=[deepcopy(a) for a in row['attributes'] if a['id'] not in updates[vid]]+list(deepcopy(updates[vid]).values())
        variants.append(out)
    if any(len(v.get('attributes',[]))>2000 for v in variants) or len(json.dumps(variants,ensure_ascii=True))>262144:raise ValueError('Atualização excede o limite seguro desta revisão.')
    result['variations']=variants
    return result


def preserved(data,proposals,item):
    if not any(p.get('variation_id') for p in proposals):return True
    before=snapshot({'variations':data.get('variation_snapshot')});after=snapshot(item)
    if before is None or after is None:return False
    old={str(v['id']):v for v in before};new={str(v['id']):v for v in after}
    if old.keys()!=new.keys():return False
    edits={(p['variation_id'],p['attribute_id']) for p in proposals if p.get('variation_id')}
    for vid,row in old.items():
        if row['attribute_combinations']!=new[vid]['attribute_combinations']:return False
        current=attributes(new[vid]['attributes'])
        for a in row['attributes']:
            if (vid,a['id']) not in edits and current.get(a['id'])!=a:return False
    return True
