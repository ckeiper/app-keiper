"""Bounded Portuguese assertions, not semantic guesses or keyword inference."""
import re

LABEL=re.compile(r'\s*(?:[-*•]\s*)?([^:=\n]{1,100})\s*[:=]\s*([^\n]{1,1000}?)\s*')
ASSERTION=re.compile(r'\s*(?:[-*•]\s*)?(?P<label>[^:=\n]{1,100}?)\s+(?P<verb>não\s+é|não\s+são|pode\s+ser|podem\s+ser|talvez\s+seja|é|são|mede|medem)\s+(?:de\s+)?(?P<value>[^\n]{1,1000}?)\s*',re.I)
UNCERTAIN=re.compile(r'\b(nao|talvez|pode|podem|ou|aproximadamente|aproximado|cerca|ate|entre|varia|variavel|opcional|depende|mas|porem|e)\b')
ROOT=re.compile(r'(?m)^\s*(?:caracteristicas do produto|especificacoes do produto|descricao do produto|medidas do produto|dados tecnicos|ficha tecnica)\s*$')
SCOPE=re.compile(r'(?m)^\s*(?:medidas da embalagem|conteudo da embalagem|itens inclusos|acessorios|embalagem|variacao|variacoes|compatibilidade|exemplo|referencia|concorrente|outro produto)\b')


def collect(title,description,aliases,fold,allow_prose=True):
    evidence={};uncertain=set()
    def codes(label):
        name=fold(label);found=aliases.get(name,set())
        if found:return found
        name=re.sub(r'^(?:(?:o|a|os|as)\s+)?(?:(?:seu|sua|seus|suas)\s+)?','',name,count=1)
        return aliases.get(name,set())
    def add(code,source,text,raw,kind):
        evidence.setdefault(code,[]).append(dict(source=source,text=text,raw=raw,reading=kind))
    for source,body in [('Título',title),('Descrição',description or '')]:
        for line in body.splitlines():
            match=LABEL.fullmatch(line)
            if not match or ';' in match[2] or ':' in match[2]:continue
            found=aliases.get(fold(match[1]),set())
            if len(found)==1:add(next(iter(found)),source,line.strip(),match[2].strip(),'label')
        if not allow_prose:continue
        scoped=False
        for paragraph in re.split(r'\n\s*\n',body):
            normalized='\n'.join(fold(line) for line in paragraph.splitlines())
            if ROOT.search(normalized):scoped=False
            if SCOPE.search(normalized) or 'compativel com' in normalized or 'compativeis com' in normalized:scoped=True
            if scoped:continue
            for clause in re.split(r'\n|(?<=[.!?])\s+',paragraph):
                if len(clause)>1200 or any(c in clause for c in ':=;'):continue
                match=ASSERTION.fullmatch(clause)
                if not match:continue
                found=codes(match['label'])
                if len(found)!=1:continue
                code=next(iter(found));raw=match['value'].strip()
                if (fold(match['verb']) not in ('e','sao','mede','medem') or '?' in clause or '!' in clause or UNCERTAIN.search(fold(raw)) or re.search(r'\bum(?:a|as|s)?\b',fold(raw))):
                    uncertain.add(code);continue
                # Only a final sentence stop is removed. Embedded punctuation is
                # preserved; the existing typed validator still decides eligibility.
                if raw.endswith('.'):raw=raw[:-1].rstrip()
                if not raw or len(raw)>1000:continue
                context=paragraph.strip() if len(paragraph.strip())<=1500 else clause.strip()
                add(code,source,context,raw,'assertion')
    return evidence,uncertain
