"""Category technical-sheet completeness, separate from publication validation."""
from html import escape
from content_required_attributes import attributes,has_value


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


class PresenceIndex:
    """Parse each attribute group once; keep variation evidence compact."""
    def __init__(self,item):
        def values(raw):
            parsed=attributes(raw)
            return None if parsed is None else {code:has_value(row) for code,row in parsed.items()}
        self.main=values(item.get('attributes'));self.variants=None;self.ids=[]
        raw=item.get('variations')
        if not isinstance(raw,list) or len(raw)>1000:return
        seen=set();prepared=[]
        for variant in raw:
            if not isinstance(variant,dict):return
            identifier=variant.get('id')
            if isinstance(identifier,bool) or not isinstance(identifier,(str,int)) or not str(identifier).strip() or len(str(identifier))>200 or str(identifier) in seen:return
            seen.add(str(identifier));prepared.append((str(identifier),values(variant.get('attributes')),values(variant.get('attribute_combinations'))))
        self.variants=prepared;self.ids=[v[0] for v in prepared[:100]]

    def evidence(self,code):
        common=self.main.get(code,False) if self.main is not None else None
        states=None
        if self.variants is not None:
            states=[]
            for _,left,right in self.variants:
                values=[group.get(code,False) if group is not None else None for group in (left,right)]
                states.append('i' if True in values else 'u' if None in values else 'r')
        compact=None if states is None else ''.join(states[:100])
        if common is True:return 'informed','Valor informado no anúncio principal',compact
        if states is None:return 'unknown','Variações não verificadas',compact
        if not states:return ('unknown','Valor não verificável no anúncio principal',compact) if common is None else ('review','Sem valor identificado no anúncio principal',compact)
        present=states.count('i');total=len(states)
        if present==total:return 'informed',f'Valor informado em {present} de {total} variações',compact
        detail=f'Valor identificado em {present} de {total} variações'
        if 'u' in states or common is None:return 'unknown',detail+'; demais valores não verificáveis',compact
        return 'review',detail+'; conferir variações sem valor identificado',compact


def compare(payload,category_attributes,item,conditional=None):
    try:definitions=parse(payload)
    except ValueError:return dict(state='unknown',message='Ficha técnica ausente, incompleta ou não verificável na resposta.')
    rules=attributes(category_attributes);conditional=conditional or {};rows=[];index=PresenceIndex(item)
    for code,definition in definitions.items():
        state,message,variations=index.evidence(code)
        name=definition.get('name');name=name if isinstance(name,str) and name.strip() and len(name)<=300 else code
        category_tags=rules.get(code,{}).get('tags') if rules is not None else None
        managed=any(t in definition['tags'] for t in ('read_only','inferred','fixed')) or (isinstance(category_tags,dict) and any(category_tags.get(t) is True for t in ('read_only','inferred','fixed')))
        rows.append(dict(id=code,name=name,state=state,message=message,publication=publication(code,rules,conditional),
            required='required' in definition['tags'],variation_states=variations,managed=managed))
    # Preserve the API order inside each group; publication requirements stay distinct.
    rows.sort(key=lambda row:not row['required'])
    tags=item.get('tags');flag='incomplete_technical_specs' in tags if isinstance(tags,list) and all(isinstance(t,str) for t in tags) else None
    return dict(state='read',rows=rows,total=len(rows),incomplete_flag=flag,variation_ids=index.ids,
                variation_count=None if index.variants is None else len(index.variants))


def render(result):
    from content_technical_view import render as view
    return view(result)
