"""Administrator task workflow, independent from records of executed actions."""
from datetime import date,timedelta
import re
import time

STATES={'open':'Aberta','done':'Concluída','cancelled':'Cancelada'}
TRANSITIONS={'open':('done','cancelled'),'done':('open',),'cancelled':('open',)}
class MissingTask(LookupError):pass
class StaleTask(ValueError):pass


def init_schema(conn,execute):
    # Serialize these new DDL statements across workers; released on transaction end.
    execute(conn,'SELECT pg_advisory_xact_lock(186144275)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_tasks (
        id BIGSERIAL PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        title TEXT NOT NULL CHECK(char_length(title) BETWEEN 5 AND 120),
        responsible TEXT NOT NULL CHECK(char_length(responsible) BETWEEN 1 AND 80),
        due_date DATE NOT NULL,description TEXT NOT NULL CHECK(char_length(description)<=1500),
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done','cancelled')),
        version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),created_at BIGINT NOT NULL,
        created_by INTEGER NOT NULL,submission_key VARCHAR(64) NOT NULL,
        UNIQUE(conexao_id,item_id,submission_key))''')
    execute(conn,'''CREATE INDEX IF NOT EXISTS listing_tasks_scope_due
        ON listing_tasks(conexao_id,item_id,status,due_date,id)''')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_task_events (
        id BIGSERIAL PRIMARY KEY,task_id BIGINT NOT NULL REFERENCES listing_tasks(id),
        conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,version INTEGER NOT NULL,
        from_status TEXT CHECK(from_status IN ('open','done','cancelled')),
        to_status TEXT NOT NULL CHECK(to_status IN ('open','done','cancelled')),
        created_at BIGINT NOT NULL,created_by INTEGER NOT NULL,UNIQUE(task_id,version))''')
    execute(conn,'''CREATE INDEX IF NOT EXISTS listing_task_events_scope
        ON listing_task_events(conexao_id,item_id,task_id,version DESC)''')


def validate(form,today):
    title=str(form.get('title','')).strip();responsible=str(form.get('responsible','')).strip()
    description=str(form.get('description','')).strip();key=str(form.get('submission_key',''))
    if not 5<=len(title)<=120 or '\x00' in title:raise ValueError('Informe um título de 5 a 120 caracteres.')
    if not 1<=len(responsible)<=80 or '\x00' in responsible:raise ValueError('Informe o responsável, com até 80 caracteres.')
    if len(description)>1500 or '\x00' in description:raise ValueError('A descrição aceita até 1.500 caracteres.')
    try:due=date.fromisoformat(form.get('due_date',''))
    except (TypeError,ValueError):raise ValueError('Informe um prazo válido.') from None
    if not today-timedelta(days=366)<=due<=today+timedelta(days=366):
        raise ValueError('O prazo deve estar entre um ano atrás e um ano à frente.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Formulário inválido. Recarregue a página.')
    return dict(title=title,responsible=responsible,due_date=due,description=description,submission_key=key)


def identifier(value):
    try:n=int(value)
    except (ValueError,TypeError):raise ValueError('Registro inválido.') from None
    if not 0<n<2**63:raise ValueError('Registro inválido.')
    return n


def create(conn,query,execute,cid,item,values,actor,now=None):
    now=int(time.time()) if now is None else now
    rows=query(conn,'''INSERT INTO listing_tasks
        (conexao_id,item_id,title,responsible,due_date,description,created_at,created_by,submission_key)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(conexao_id,item_id,submission_key) DO NOTHING RETURNING id''',
        (cid,item,values['title'],values['responsible'],values['due_date'],values['description'],now,actor,values['submission_key']))
    if not rows:
        old=query(conn,'''SELECT id,title,responsible,due_date,description FROM listing_tasks
            WHERE conexao_id=%s AND item_id=%s AND submission_key=%s''',(cid,item,values['submission_key']))
        if not old or any(old[0][key]!=values[key] for key in ('title','responsible','due_date','description')):
            raise ValueError('Este formulário já foi usado com outros dados. Recarregue a página.')
        return old[0]['id']
    task_id=rows[0]['id']
    execute(conn,'''INSERT INTO listing_task_events
        (task_id,conexao_id,item_id,version,from_status,to_status,created_at,created_by)
        VALUES(%s,%s,%s,1,NULL,'open',%s,%s)''',(task_id,cid,item,now,actor))
    return task_id


def transition(conn,query,execute,cid,item,task_id,version,previous,target,actor,now=None):
    task_id=identifier(task_id);version=identifier(version)
    if target not in TRANSITIONS.get(previous,()):raise ValueError('Mudança de status inválida.')
    changed=query(conn,'''UPDATE listing_tasks SET status=%s,version=version+1
        WHERE id=%s AND conexao_id=%s AND item_id=%s AND version=%s AND status=%s
        RETURNING version''',(target,task_id,cid,item,version,previous))
    if not changed:
        found=query(conn,'SELECT id FROM listing_tasks WHERE id=%s AND conexao_id=%s AND item_id=%s',(task_id,cid,item))
        if not found:raise MissingTask('Tarefa não encontrada neste anúncio.')
        raise StaleTask('A tarefa foi atualizada em outra aba. Confira o status atual antes de tentar novamente.')
    now=int(time.time()) if now is None else now
    execute(conn,'''INSERT INTO listing_task_events
        (task_id,conexao_id,item_id,version,from_status,to_status,created_at,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',(task_id,cid,item,changed[0]['version'],previous,target,now,actor))


def load(conn,query,cid,item,args,today):
    selected=args.get('status','open')
    if selected not in (*STATES,'all','overdue'):selected='open'
    where='conexao_id=%s AND item_id=%s';params=[cid,item]
    if selected in STATES:where+=' AND status=%s';params.append(selected)
    elif selected=='overdue':where+=" AND status='open' AND due_date<%s";params.append(today)
    counts=query(conn,'''SELECT status,COUNT(*) AS n,
        COUNT(*) FILTER(WHERE status='open' AND due_date<%s) AS overdue
        FROM listing_tasks WHERE conexao_id=%s AND item_id=%s GROUP BY status''',(today,cid,item))
    total=query(conn,'SELECT COUNT(*) AS n FROM listing_tasks WHERE '+where,tuple(params))[0]['n']
    pages=max(1,(total+9)//10)
    try:page=max(1,min(pages,int(args.get('pagina','1'))))
    except (ValueError,TypeError):page=1
    rows=query(conn,'SELECT * FROM listing_tasks WHERE '+where+' ORDER BY due_date,id LIMIT 10 OFFSET %s',tuple(params+[(page-1)*10]))
    history=None;events=[];event_page=event_pages=1
    if args.get('tarefa'):
        tid=identifier(args['tarefa'])
        found=query(conn,'SELECT * FROM listing_tasks WHERE id=%s AND conexao_id=%s AND item_id=%s',(tid,cid,item))
        if not found:raise MissingTask('Tarefa não encontrada neste anúncio.')
        history=found[0]
        n=query(conn,'SELECT COUNT(*) AS n FROM listing_task_events WHERE task_id=%s AND conexao_id=%s AND item_id=%s',(tid,cid,item))[0]['n']
        event_pages=max(1,(n+9)//10)
        try:event_page=max(1,min(event_pages,int(args.get('historico_pagina','1'))))
        except (TypeError,ValueError):event_page=1
        events=query(conn,'''SELECT * FROM listing_task_events WHERE task_id=%s AND conexao_id=%s AND item_id=%s
            ORDER BY version DESC LIMIT 10 OFFSET %s''',(tid,cid,item,(event_page-1)*10))
    return dict(rows=rows,counts=counts,status=selected,total=total,page=page,pages=pages,
                history=history,events=events,event_page=event_page,event_pages=event_pages)
