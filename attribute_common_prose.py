"""Read common assertions only in explicit product sections of variant listings."""
import re
import unicodedata
from attribute_text_evidence import collect,ROOT,SCOPE
from attribute_variations import snapshot

INLINE=re.compile(r'\b(?:variacao|variacoes|variante|variantes|versao|versoes|opcao|opcoes|modelo|modelos|para|na|nas|no|nos)\b')
COMMON_ROOT=re.compile(r'(?:atributos|caracteristicas|especificacoes|dados|ficha tecnica) (?:comuns|comum) a todas as variacoes')


def context(item,rules,fold):
    variants=snapshot(item)
    if variants is None:return None
    terms=set();prefixes=set()
    for variant in variants:
        combinations=variant['attribute_combinations']
        if not combinations:return None
        values=[];terms.add(str(variant['id']))
        for row in combinations:
            value=row.get('value_name');rule=rules.get(row['id'],{})
            names=[name for name in (row.get('name'),rule.get('name')) if isinstance(name,str) and name.strip()]
            if not isinstance(value,str) or not value.strip() or not names:return None
            value=fold(value)
            if not value or not any(fold(name) for name in names):return None
            values.append(value);terms.add(value)
            for name in names+[row['id']]:
                name=fold(name)
                if name:prefixes.add(name)
        terms.add(' '.join(values))
    for code,rule in rules.items():
        tags=rule.get('tags')
        if isinstance(tags,dict) and any(tags.get(k) is True for k in ('allow_variations','variation_attribute')):
            for name in (code,rule.get('name')):
                if isinstance(name,str) and fold(name):prefixes.add(fold(name))
    if len(terms)+len(prefixes)>4096:return None
    return terms,prefixes


def read(title,description,item,rules,aliases,fold):
    bounds=context(item,rules,fold)
    if bounds is None:return collect(title,description,aliases,fold,allow_prose=False)
    terms,prefixes=bounds;markers=terms|prefixes;starts=tuple(term+' ' for term in markers if term)
    references=tuple(' '+term+' ' for term in markers if term)
    evidence={};uncertain=set()
    def parse(source,text,prose):
        return collect(text if source=='Título' else '',text if source=='Descrição' else '',aliases,fold,allow_prose=prose)
    def merge(found,kind,paragraph=None):
        for code,rows in found.items():
            for row in rows:
                if row['reading']!=kind:continue
                row=dict(row)
                if paragraph and len(paragraph)<=1500:row['text']=paragraph
                evidence.setdefault(code,[]).append(row)
    for source,body in [('Título',title),('Descrição',description or '')]:
        active=False;scoped=False;preface=False
        for paragraph in re.split(r'\n\s*\n',body):
            general=[]
            for line in paragraph.splitlines():
                normalized=fold(line)
                if not normalized:continue
                if COMMON_ROOT.fullmatch(normalized):active=True;scoped=False;preface=False;continue
                stripped=re.sub(r'^(?:o|a|os|as)\s+','',normalized,count=1)
                marker=bool(INLINE.search(normalized) or any(term in ' '+normalized+' ' for term in references) or SCOPE.match(normalized) or 'compativel com' in normalized or 'compativeis com' in normalized or stripped in markers or (starts and stripped.startswith(starts)))
                if marker:active=False;scoped=True
                if ROOT.fullmatch(normalized):
                    if not scoped and not preface:active=True
                    else:active=False;scoped=True
                    continue
                if scoped:
                    found,review=parse(source,line,True)
                    uncertain.update(found);uncertain.update(review)
                    continue
                found,_=parse(source,line,False)
                if not active and not found:preface=True
                if active:
                    asserted,review=parse(source,line,True)
                    if not asserted and not review:active=False;scoped=True;continue
                    general.append(line)
                merge(found,'label')
            if general:
                found,review=parse(source,'\n'.join(general),True)
                merge(found,'assertion',paragraph.strip());uncertain.update(review)
    for code,rows in evidence.items():
        if rules.get(code,{}).get('value_type')=='number_unit':
            values={unicodedata.normalize('NFC',' '.join(row['raw'].split())) for row in rows}
            if len(values)>1:uncertain.add(code)
    return evidence,uncertain
