"""Append-only human reviews of listing content; no automatic quality verdict."""
import re
import time

CRITERIA={
 'titulo':('Título e identificação','O título identifica o produto, modelo e especificação relevante sem prometer características não verificadas?'),
 'principal':('Imagem principal','O produto está legível e bem representado, sem elementos que confundam o comprador?'),
 'detalhes':('Imagens de detalhes e uso','As imagens mostram detalhes, acabamento e uso real, com informações verificáveis?'),
 'medidas':('Medidas e especificações','Dimensões, material e especificações estão claros e coerentes entre imagens, título e descrição?'),
 'compatibilidade':('Compatibilidade e aplicação','Aplicações, limitações e incompatibilidades relevantes estão explícitas?'),
 'conteudo':('Conteúdo da embalagem','Quantidade e itens inclusos estão claros, distinguindo acessórios que não acompanham o produto?'),
 'objecoes':('Objeções do comprador','O conteúdo responde às dúvidas reais identificadas nas perguntas e no atendimento, sem inventar avaliações?'),
 'video':('Vídeo e demonstração','Quando aplicável, o vídeo demonstra o produto e é coerente com a oferta?')}
STATES={'approved':'Conferido pelo administrador','revise':'Precisa de ajuste','na':'Não se aplica'}
class StaleReview(ValueError):pass


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144278)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_content_reviews (
        id BIGSERIAL PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        criterion TEXT NOT NULL CHECK(criterion IN ('titulo','principal','detalhes','medidas','compatibilidade','conteudo','objecoes','video')),
        verdict TEXT NOT NULL CHECK(verdict IN ('approved','revise','na')),
        note TEXT NOT NULL CHECK(char_length(note) BETWEEN 10 AND 1500),
        created_at BIGINT NOT NULL,created_by INTEGER NOT NULL,
        submission_key VARCHAR(64) NOT NULL,UNIQUE(conexao_id,item_id,submission_key))''')
    execute(conn,'''CREATE INDEX IF NOT EXISTS listing_content_scope
        ON listing_content_reviews(conexao_id,item_id,criterion,id DESC)''')


def validate(form):
    criterion=form.get('criterion');verdict=form.get('verdict');note=str(form.get('note','')).strip()
    key=str(form.get('submission_key',''))
    if criterion not in CRITERIA or verdict not in STATES:raise ValueError('Selecione o critério e o resultado da revisão.')
    if not 10<=len(note)<=1500 or '\x00' in note:raise ValueError('Registre a evidência ou justificativa, entre 10 e 1.500 caracteres.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Recarregue o formulário.')
    try:expected=int(form.get('expected','0'))
    except (ValueError,TypeError):raise ValueError('Revisão inválida.') from None
    if not 0<=expected<2**63:raise ValueError('Revisão inválida.')
    return dict(criterion=criterion,verdict=verdict,note=note,submission_key=key,expected=expected)


def save(conn,query,execute,cid,item,values,actor):
    # Same scope lock for retry/concurrent updates. No existing record is overwritten.
    execute(conn,'SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(f'content:{cid}:{item}',))
    old=query(conn,'SELECT * FROM listing_content_reviews WHERE conexao_id=%s AND item_id=%s AND submission_key=%s',(cid,item,values['submission_key']))
    if old:
        if any(old[0][k]!=values[k] for k in ('criterion','verdict','note')):raise ValueError('Este formulário já foi usado com outros dados. Recarregue a página.')
        return old[0]['id']
    latest=query(conn,'SELECT id FROM listing_content_reviews WHERE conexao_id=%s AND item_id=%s AND criterion=%s ORDER BY id DESC LIMIT 1',(cid,item,values['criterion']))
    if (latest[0]['id'] if latest else 0)!=values['expected']:raise StaleReview('Este critério mudou em outra aba. Confira a revisão atual antes de salvar.')
    return query(conn,'''INSERT INTO listing_content_reviews(conexao_id,item_id,criterion,verdict,note,created_at,created_by,submission_key)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',(cid,item,values['criterion'],values['verdict'],values['note'],int(time.time()),actor,values['submission_key']))[0]['id']


def load(conn,query,cid,item,args):
    latest=query(conn,'''SELECT DISTINCT ON(criterion) * FROM listing_content_reviews
        WHERE conexao_id=%s AND item_id=%s ORDER BY criterion,id DESC''',(cid,item))
    total=query(conn,'SELECT COUNT(*) AS n FROM listing_content_reviews WHERE conexao_id=%s AND item_id=%s',(cid,item))[0]['n'];pages=max(1,(total+9)//10)
    try:page=max(1,min(pages,int(args.get('pagina','1'))))
    except (ValueError,TypeError):page=1
    history=query(conn,'''SELECT * FROM listing_content_reviews WHERE conexao_id=%s AND item_id=%s
        ORDER BY id DESC LIMIT 10 OFFSET %s''',(cid,item,(page-1)*10))
    return dict(latest={r['criterion']:r for r in latest},history=history,total=total,pages=pages,page=page)
