"""Explicitly scheduled 30-day review plan, backed by ordinary listing tasks."""
from datetime import date,timedelta
import re
from listing_tasks import create

STEPS=[(0,'Conferir a base do anúncio','Revisar identificação, conteúdo, medidas e compatibilidade. Registrar evidências no checklist; conferir custos e fontes disponíveis sem presumir rentabilidade.'),
       (6,'Revisar a primeira semana','Conferir cobertura de visitas e vendas, perguntas registradas e estoque. Separar ausência de dados de ausência de resultado.'),
       (13,'Revisar os primeiros quatorze dias','Revisar ações executadas, concorrência e desempenho observado. Comparar períodos somente quando a cobertura permitir; não atribuir causas sem evidência.'),
       (29,'Consolidar a revisão de trinta dias','Revisar pendências e evidências, documentar aprendizados e planejar próximos ajustes. Encerrar tarefas apenas após a conferência humana.')]


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144280)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_onboarding_plans(
        id BIGSERIAL PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        start_date DATE NOT NULL,responsible TEXT NOT NULL CHECK(char_length(responsible) BETWEEN 1 AND 80),
        UNIQUE(conexao_id,item_id))''')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_onboarding_steps(
        plan_id BIGINT NOT NULL REFERENCES listing_onboarding_plans(id),
        step INTEGER NOT NULL CHECK(step BETWEEN 0 AND 3),task_id BIGINT NOT NULL REFERENCES listing_tasks(id),
        PRIMARY KEY(plan_id,step),UNIQUE(task_id))''')


def validate(form,today):
    try:start=date.fromisoformat(form.get('start_date',''))
    except (ValueError,TypeError):raise ValueError('Informe uma data de início válida.') from None
    if not today-timedelta(days=90)<=start<=today+timedelta(days=90):raise ValueError('O início deve estar entre 90 dias atrás e 90 dias à frente.')
    owner=str(form.get('responsible','')).strip();key=str(form.get('submission_key',''))
    if not 1<=len(owner)<=80 or '\x00' in owner:raise ValueError('Informe o responsável, com até 80 caracteres.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Recarregue o formulário.')
    return dict(start_date=start,responsible=owner,submission_key=key)


def create_plan(conn,query,execute,cid,item,values,actor):
    rows=query(conn,'''INSERT INTO listing_onboarding_plans(conexao_id,item_id,start_date,responsible)
        VALUES(%s,%s,%s,%s) ON CONFLICT(conexao_id,item_id) DO NOTHING RETURNING id''',
        (cid,item,values['start_date'],values['responsible']))
    if not rows:
        old=query(conn,'SELECT * FROM listing_onboarding_plans WHERE conexao_id=%s AND item_id=%s',(cid,item))
        if not old or any(old[0][k]!=values[k] for k in ('start_date','responsible')):raise ValueError('Este anúncio já possui um plano. Confira o início e o responsável registrados; nenhum dado foi substituído.')
        return old[0]['id']
    pid=rows[0]['id']
    for step,(offset,title,description) in enumerate(STEPS):
        # Stable plan-based keys avoid duplicate tasks even on client retries.
        task=create(conn,query,execute,cid,item,dict(title=title,responsible=values['responsible'],
            due_date=values['start_date']+timedelta(days=offset),description=description,submission_key=f'onboarding-plan-{pid}-step-{step}'),actor)
        execute(conn,'INSERT INTO listing_onboarding_steps(plan_id,step,task_id) VALUES(%s,%s,%s)',(pid,step,task))
    return pid


def load(conn,query,cid,item):
    rows=query(conn,'SELECT * FROM listing_onboarding_plans WHERE conexao_id=%s AND item_id=%s',(cid,item))
    if not rows:return dict(plan=None,steps=[])
    plan=rows[0]
    steps=query(conn,'''SELECT s.step,t.* FROM listing_onboarding_steps s JOIN listing_tasks t ON t.id=s.task_id
        WHERE s.plan_id=%s AND t.conexao_id=%s AND t.item_id=%s ORDER BY s.step''',(plan['id'],cid,item))
    return dict(plan=plan,steps=steps)
