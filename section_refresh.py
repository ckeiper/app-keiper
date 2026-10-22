"""Explicit per-section refresh with shared status and cross-worker exclusion."""
from datetime import date, timedelta
from html import escape
import threading
import time
from uuid import uuid4

from flask import jsonify, request
from sales_metrics import reporting_today
from sync_exclusion import store_sync_lock

SCOPES = {'ads': 'Ads', 'campanhas': 'Campanhas', 'anuncios': 'Anúncios',
          'promocoes': 'Promoções', 'vendas': 'Vendas', 'full': 'Full e vendas',
          'custos': 'Custos', 'desempenho': 'Desempenho', 'demandas': 'Demandas'}


def collector_names(scope):
    return {
        'ads': ('puxar_ads',), 'campanhas': ('puxar_ads',),
        'anuncios': ('puxar_anuncios', 'puxar_promocoes'), 'promocoes': ('puxar_promocoes',),
        'vendas': ('puxar_pedidos', 'puxar_envios'), 'full': ('puxar_full',),
        'custos': ('puxar_anuncios',), 'desempenho': ('puxar_anuncios',),
        'demandas': ('puxar_anuncios', 'puxar_promocoes'),
    }[scope]


def init_schema(conn, execute):
    execute(conn, """CREATE TABLE IF NOT EXISTS atualizacoes_secao (
        id TEXT PRIMARY KEY, conexao_id INTEGER NOT NULL REFERENCES conexoes(id),
        secao TEXT NOT NULL, status TEXT NOT NULL, mensagem TEXT NOT NULL,
        inicio_em BIGINT NOT NULL, heartbeat_em BIGINT NOT NULL, fim_em BIGINT
    )""")
    execute(conn, """CREATE INDEX IF NOT EXISTS idx_atualizacoes_secao_loja
        ON atualizacoes_secao(conexao_id, inicio_em DESC)""")


def selected_range(args):
    today = reporting_today()
    if args.get('de') or args.get('ate'):
        start, end = date.fromisoformat(args.get('de', '')), date.fromisoformat(args.get('ate', ''))
    else:
        days = int(args.get('dias', 30))
        if days not in (7, 15, 30, 60, 90):
            raise ValueError('Período inválido')
        start, end = today - timedelta(days=days-1), today
    if end > today or start > end or (end-start).days > 89:
        raise ValueError('Período inválido')
    return start, end


def register(app, login_required, can_view, bank, query, execute, collect):
    def expire(conn, cid):
        execute(conn, """UPDATE atualizacoes_secao SET status='falhou',
            mensagem='Atualização interrompida. Tente novamente.', fim_em=%s
            WHERE conexao_id=%s AND status IN ('aguardando','executando')
            AND heartbeat_em < %s""", (int(time.time()), cid, int(time.time())-150))

    def update(job_id, status, message):
        with bank() as conn:
            execute(conn, """UPDATE atualizacoes_secao SET status=%s, mensagem=%s,
                heartbeat_em=%s, fim_em=%s WHERE id=%s""",
                (status, message, int(time.time()), int(time.time()), job_id))

    def worker(job_id, cid, scope, period):
        stop = threading.Event()
        def heartbeat():
            while not stop.wait(15):
                try:
                    with bank() as conn:
                        execute(conn, 'UPDATE atualizacoes_secao SET heartbeat_em=%s WHERE id=%s',
                                (int(time.time()), job_id))
                except Exception:
                    app.logger.error('section_refresh_heartbeat_failed')
        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        try:
            with store_sync_lock(bank, cid) as acquired:
                if not acquired:
                    update(job_id, 'ocupada', 'Esta loja já está sendo atualizada. Tente novamente ao concluir.')
                    return
                with bank() as conn:
                    execute(conn, "UPDATE atualizacoes_secao SET status='executando' WHERE id=%s", (job_id,))
                success = collect(cid, scope, period)
                update(job_id, 'concluida' if success else 'falhou',
                       'Dados atualizados.' if success else 'Não foi possível concluir a coleta. Tente novamente.')
        except Exception:
            app.logger.error('section_refresh_failed cid=%s scope=%s', cid, scope)
            update(job_id, 'falhou', 'Falha na atualização. Tente novamente.')
        finally:
            stop.set()

    @app.route('/atualizacoes/<int:cid>/<scope>', methods=['GET', 'POST'])
    @login_required
    def section_refresh(cid, scope):
        if not can_view(cid):
            return jsonify(error='Acesso restrito'), 403
        if scope not in SCOPES:
            return jsonify(error='Seção inválida'), 400
        if request.method == 'GET':
            with bank() as conn:
                expire(conn, cid)
                rows = query(conn, """SELECT id,secao,status,mensagem,inicio_em,fim_em
                    FROM atualizacoes_secao WHERE conexao_id=%s AND secao=%s
                    ORDER BY inicio_em DESC,id DESC LIMIT 1""", (cid, scope))
            return jsonify(rows[0] if rows else {'status': 'inativa'})
        try:
            period = selected_range(request.args) if scope in ('ads', 'campanhas') else None
        except (ValueError, TypeError):
            return jsonify(error='Período inválido: selecione até 90 dias, sem datas futuras.'), 400
        now, job_id = int(time.time()), uuid4().hex
        with bank() as conn:
            execute(conn, 'SELECT pg_advisory_xact_lock(72593,%s)', (cid,))
            expire(conn, cid)
            active = query(conn, """SELECT id,secao,status,mensagem FROM atualizacoes_secao
                WHERE conexao_id=%s AND status IN ('aguardando','executando') LIMIT 1""", (cid,))
            if active:
                if active[0]['secao'] == scope:
                    return jsonify(active[0]), 202
                return jsonify(error='Outra seção desta loja está sendo atualizada. Aguarde a conclusão.'), 409
            execute(conn, """INSERT INTO atualizacoes_secao
                (id,conexao_id,secao,status,mensagem,inicio_em,heartbeat_em)
                VALUES (%s,%s,%s,'aguardando','Atualizando esta seção…',%s,%s)""",
                (job_id, cid, scope, now, now))
        try:
            threading.Thread(target=worker, args=(job_id,cid,scope,period), daemon=True).start()
        except Exception:
            update(job_id, 'falhou', 'Não foi possível iniciar a atualização. Tente novamente.')
            return jsonify(error='Não foi possível iniciar a atualização.'), 503
        return jsonify(id=job_id, status='aguardando'), 202


def render(cid, scope, last=''):
    if scope not in SCOPES:
        return ''
    label = 'Atualizar ' + SCOPES[scope]
    return ("<div class='k-refresh' data-endpoint='/atualizacoes/" + str(int(cid)) + '/' + scope
            + "' style='display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:14px 0'>"
            + "<button type='button' class='btn-acoes'>" + escape(label) + '</button>'
            + "<span role='status' aria-live='polite' style='font-size:13px'>"
            + (escape('Última atualização: ' + last) if last else '') + '</span></div>' + SCRIPT)


SCRIPT = """<script>(function(){
const root=document.currentScript.previousElementSibling,button=root.querySelector('button'),status=root.querySelector('[role=status]');
const label=button.textContent,endpoint=root.dataset.endpoint+location.search;
let active=false,job=null,timer=null;
function message(text){status.textContent=text;}
function idle(text){active=false;button.disabled=false;button.textContent=label;root.removeAttribute('aria-busy');message(text);}
function busy(){active=true;button.disabled=true;button.textContent='Atualizando…';root.setAttribute('aria-busy','true');}
async function check(resume){try{
const response=await fetch(endpoint,{headers:{Accept:'application/json'}});
if(!response.ok||!response.headers.get('content-type')?.includes('application/json'))throw Error();
const state=await response.json();
if(job&&state.id!==job){idle('Não foi possível acompanhar esta atualização. Recarregue a página.');return;}
if(['aguardando','executando'].includes(state.status)){job=state.id;busy();message('Atualizando somente esta seção…');timer=setTimeout(()=>check(false),2000);return;}
if(resume){if(state.status==='concluida'&&state.fim_em)message('Última atualização: '+new Date(state.fim_em*1000).toLocaleString('pt-BR'));return;}
if(state.status==='concluida'){message('Dados atualizados. Carregando resultados…');location.reload();return;}
idle(state.mensagem||'Atualização não concluída. Tente novamente.');
}catch(e){idle('Não foi possível acompanhar a atualização. Recarregue a página para conferir o resultado.');}}
button.addEventListener('click',async function(){if(active)return;busy();message('Solicitando atualização desta seção…');
try{const response=await fetch(endpoint,{method:'POST',headers:{Accept:'application/json'}});
if(!response.headers.get('content-type')?.includes('application/json'))throw Error();
const state=await response.json();if(!response.ok){idle(state.error||'Não foi possível atualizar.');return;}
job=state.id;check(false);
}catch(e){idle('Falha de conexão. Tente novamente.');}});
check(true);window.addEventListener('pagehide',()=>clearTimeout(timer));
})();</script>"""