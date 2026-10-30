"""Store-scoped competitor registration and cached reports."""
import hmac
import secrets
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from html import escape
from urllib.parse import urlencode

from flask import request, redirect, session
from competitor_monitor import item_from_link, next_slot, HOURS

BR = timezone(timedelta(hours=-3))


def tabs(cid, selected='concorrencia'):
    return ("<nav class='card' aria-label='Abas de anúncios' style='display:flex;gap:18px'>"
            + ("<b>Meus anúncios</b>" if selected == 'anuncios' else
               f"<a href='/anuncios/{cid}'>Meus anúncios</a>")
            + ("<b>Concorrência</b>" if selected == 'concorrencia' else
               f"<a href='/anuncios/{cid}/concorrencia'>Concorrência</a>") + '</nav>')


def brl(value):
    if value is None:
        return 'Não confirmado'
    return 'R$ ' + format(Decimal(str(value)), ',.2f').replace(',', 'x').replace('.', ',').replace('x', '.')


def date_time(value):
    return datetime.fromtimestamp(int(value), BR).strftime('%d/%m/%Y %H:%M') if value else 'Ainda não consultado'


def full_text(value):
    return 'Sim' if value is True else ('Não' if value is False else 'Não confirmado')


def delta(current, previous):
    if current is None or previous is None or previous <= 0:
        return '—'
    change = current - previous
    sign = '+' if change > 0 else ('−' if change < 0 else '')
    return sign + brl(abs(change)) + ' (' + sign + f'{abs(change / previous * 100):.2f}'.replace('.', ',') + '%)'


def pagination(args, count):
    try:
        size = int(args.get('por_pagina', 25))
        size = size if size in (25, 50, 100) else 25
        page = max(1, int(args.get('pagina', 1)))
    except (ValueError, TypeError):
        page, size = 1, 25
    pages = max(1, (count + size - 1) // size)
    page = min(page, pages)
    return page, size, pages


def pager(path, args, page, pages, count):
    def link(number, label):
        params = dict(args)
        params['pagina'] = number
        return "<a class='btn-acoes cinza' href='" + escape(path + '?' + urlencode(params), quote=True) + "'>" + label + '</a>'
    return ("<div style='display:flex;gap:12px;align-items:center;flex-wrap:wrap'>"
            + (link(page-1, '← Anterior') if page > 1 else '')
            + f'<span>Página {page} de {pages} · {count} registros</span>'
            + (link(page+1, 'Próxima →') if page < pages else '') + '</div>')


def register_competitors(app, login_required, can_view, bank, query, execute, page, shop_page):
    def shop(cid):
        if not can_view(cid):
            return None, (page('Acesso negado', '<div class="card">Acesso restrito</div>'), 403)
        with bank() as conn:
            rows = query(conn, 'SELECT id,cliente FROM conexoes WHERE id=%s', (cid,))
        if not rows:
            return None, (page('Loja não encontrada', '<div class="card">Loja não encontrada</div>'), 404)
        return rows[0], None

    def csrf():
        session.setdefault('competitor_csrf', secrets.token_urlsafe(32))
        if request.method == 'POST' and not hmac.compare_digest(
                session['competitor_csrf'].encode(), request.form.get('csrf_token', '').encode()):
            return 'Formulário expirado. Recarregue a página e tente novamente.', 400
        return None

    def form_token():
        return "<input type='hidden' name='csrf_token' value='" + escape(session['competitor_csrf'], quote=True) + "'>"

    def filters(cid):
        clauses, values = ['t.conexao_id=%s'], [cid]
        search = request.args.get('busca', '').strip()[:200]
        if search:
            # Treat wildcard characters literally in the search box.
            pattern = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            clauses.append('(t.label ILIKE %s OR t.title ILIKE %s OR t.item_id ILIKE %s OR t.own_item_id ILIKE %s)')
            values += [pattern] * 4
        status = request.args.get('status', 'ativos')
        if status == 'pausados':
            clauses.append('NOT t.active')
        elif status == 'falhas':
            clauses.append("t.active AND t.error <> ''")
        elif status != 'todos':
            clauses.append('t.active')
        full = request.args.get('full', '')
        if full in ('sim', 'nao', 'desconhecido'):
            clauses.append('t.full_state IS ' + {'sim':'TRUE', 'nao':'FALSE', 'desconhecido':'NULL'}[full])
        change = request.args.get('preco', '')
        if change in ('queda', 'aumento'):
            clauses.append('t.price ' + ('<' if change == 'queda' else '>') + ' t.previous_price')
        elif change == 'alterado':
            clauses.append('t.price_changed_at IS NOT NULL')
        return ' AND '.join(clauses), tuple(values)

    def select(name, options):
        return (f"<select name='{name}'>" + ''.join(
            "<option value='" + key + "'" + (' selected' if request.args.get(name, '') == key else '')
            + '>' + title + '</option>' for key, title in options) + '</select>')

    @app.route('/anuncios/<int:cid>/concorrencia', methods=['GET', 'POST'])
    @login_required
    def competitor_list(cid):
        store, denied = shop(cid)
        if denied:
            return denied
        invalid_csrf = csrf()
        if invalid_csrf:
            return invalid_csrf
        path = f'/anuncios/{cid}/concorrencia'
        message, status_code = '', 200
        if request.method == 'POST':
            try:
                item_id = item_from_link(request.form.get('link'))
                label = request.form.get('nome', '').strip()
                if len(label) > 150:
                    raise ValueError('Use até 150 caracteres para o nome do concorrente.')
                own=request.form.get('meu_anuncio','').strip()
                own=item_from_link(own) if own else None
                if own==item_id:
                    raise ValueError('O concorrente deve ser diferente do seu anúncio.')
                with bank() as conn:
                    if own and not query(conn,'SELECT item_id FROM anuncios WHERE conexao_id=%s AND item_id=%s',(cid,own)):
                        raise ValueError('O anúncio próprio não pertence a esta loja.')
                    execute(conn, '''INSERT INTO competitor_targets(conexao_id,item_id,label,created_at,own_item_id)
                        VALUES(%s,%s,%s,%s,%s) ON CONFLICT(conexao_id,item_id)
                        DO UPDATE SET label=EXCLUDED.label,active=TRUE,
                        own_item_id=COALESCE(EXCLUDED.own_item_id,competitor_targets.own_item_id)''', (cid,item_id,label,int(time.time()),own))
                return redirect(path + '?cadastrado=1', code=303)
            except ValueError as exc:
                message, status_code = str(exc), 400
        elif request.args.get('cadastrado') == '1':
            message = 'Anúncio cadastrado. A primeira consulta será feita automaticamente; recarregue em instantes.'
        where, values = filters(cid)
        midnight = int(datetime.now(BR).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
        with bank() as conn:
            total = query(conn, 'SELECT COUNT(*) AS n FROM competitor_targets t WHERE ' + where, values)[0]['n']
            current_page, size, pages = pagination(request.args, total)
            rows = query(conn, 'SELECT t.* FROM competitor_targets t WHERE ' + where
                         + ' ORDER BY t.created_at DESC,t.id DESC LIMIT %s OFFSET %s',
                         values + (size,(current_page-1)*size))
            summary = query(conn, '''SELECT COUNT(*) FILTER(WHERE active) AS active,
                COUNT(*) FILTER(WHERE active AND full_state IS TRUE) AS full,
                COUNT(*) FILTER(WHERE active AND price_changed_at >= %s) AS changed,
                COUNT(*) FILTER(WHERE active AND error <> '') AS errors
                FROM competitor_targets WHERE conexao_id=%s''', (midnight,cid))[0]
        body = tabs(cid) + '<h2>Monitoramento da concorrência</h2>'
        if message:
            body += "<div class='card' role='status'>" + escape(message) + '</div>'
        body += "<div class='grid'>" + ''.join(
            "<div class='stat'><div class='num'>" + str(summary[key]) + "</div><div class='lab'>" + label + '</div></div>'
            for key,label in [('active','Anúncios monitorados'),('full','Última confirmação no Full'),
                              ('changed','Preços alterados hoje'),('errors','Consultas com pendência')]) + '</div>'
        body += ("<div class='card'><h3>Adicionar concorrente</h3><form method='post' class='competitor-form'>" + form_token()
                 + "<label>Nome do concorrente (opcional)<input name='nome' maxlength='150' value='"
                 + escape(request.form.get('nome', '')[:150],quote=True) + "'></label>"
                 + "<label>Link ou código MLB do anúncio<input name='link' required maxlength='3000' placeholder='Cole o link da oferta do vendedor' value='"
                 + escape(request.form.get('link', '')[:3000],quote=True) + "'></label>"
                 + "<label>Seu anúncio para comparação (opcional)<input name='meu_anuncio' maxlength='3000' placeholder='Código MLB do seu produto' value='"
                 + escape(request.form.get('meu_anuncio',request.args.get('meu_anuncio',''))[:3000],quote=True) + "'></label>"
                 + "<button class='btn-acoes' type='submit'>Monitorar anúncio</button></form>"
                 + "<p class='muted'>Preço final para 1 unidade, incluindo promoção disponível ao público. "
                 "Cupons pessoais e frete não entram no valor. O vendedor da oferta fica fixo no monitoramento.</p>"
                 + '<details><summary>10 verificações diárias · horário de Brasília</summary><p>' + HOURS
                 + '</p><p>Próximo horário: ' + date_time(next_slot(time.time()))
                 + '. A execução depende da disponibilidade do sistema e do Mercado Livre. '
                 'Períodos sem coleta aparecem como lacunas.</p></details></div>')
        body += ("<div class='card'><form method='get' class='competitor-form' aria-label='Filtros da concorrência'>"
                 + "<label>Buscar<input name='busca' maxlength='200' placeholder='Nome, título ou MLB' value='"
                 + escape(request.args.get('busca', '')[:200],quote=True) + "'></label>"
                 + '<label>Monitoramento' + select('status',[('ativos','Ativos'),('pausados','Pausados'),('falhas','Com pendência'),('todos','Todos')]) + '</label>'
                 + '<label>Full (última confirmação)' + select('full',[('','Todos'),('sim','Sim'),('nao','Não'),('desconhecido','Não confirmado')]) + '</label>'
                 + '<label>Última alteração de preço' + select('preco',[('','Todas'),('queda','Queda'),('aumento','Aumento'),('alterado','Qualquer alteração')]) + '</label>'
                 + '<label>Por página' + select('por_pagina',[('25','25'),('50','50'),('100','100')]) + '</label>'
                 + "<button class='btn-acoes'>Filtrar</button><a href='" + path + "'>Limpar filtros</a></form></div>")
        body += "<div class='card'><div style='overflow:auto'><table><thead><tr><th>Concorrente / anúncio</th><th>Preço final</th><th>Preço anterior / variação</th><th>Full</th><th>Última consulta</th><th>Ações</th></tr></thead><tbody>"
        for row in rows:
            title = escape(row['title'] or row['item_id'])
            error = row['error']
            if error == 'Consulta em andamento' and row['attempted_at'] and time.time() - row['attempted_at'] > 120:
                error = 'Consulta sem conclusão. Nova tentativa no próximo horário.'
            stale = "<small class='competitor-warning'>Último dado confirmado; consulta atual com pendência.</small>" if error and (row['price'] is not None or row['full_state'] is not None) else ''
            body += ("<tr><td><b>" + escape(row['label'] or 'Concorrente') + '</b><br>'
                     + f"<a href='https://produto.mercadolivre.com.br/{row['item_id']}' target='_blank' rel='noopener noreferrer'>" + title + '</a><br><small>' + row['item_id']
                     + (' · vendedor ' + str(row['seller_id']) if row['seller_id'] else '') + '</small>'
                     + ('<small>Seu anúncio: '+escape(str(row['own_item_id']))+'</small>' if row.get('own_item_id') else '')
                     + ('<br><b>Pausado</b>' if not row['active'] else '') + '</td><td>'
                     + brl(row['price']) + '<small>Confirmado: ' + date_time(row['price_at']) + '</small>' + stale + '</td><td>'
                     + (brl(row['previous_price']) if row['previous_price'] is not None else '—')
                     + '<small>' + delta(row['price'],row['previous_price']) + '</small><small>'
                     + ('Alterado: ' + date_time(row['price_changed_at']) if row['price_changed_at'] else 'Sem alteração registrada')
                     + '</small></td><td>' + full_text(row['full_state']) + '<small>Confirmado: ' + date_time(row['full_at']) + '</small>'
                     + ('<small>' + full_text(row['previous_full']) + ' → ' + full_text(row['full_state']) + ' em ' + date_time(row['full_changed_at']) + '</small>' if row['full_changed_at'] else '')
                     + '</td><td>' + date_time(row['attempted_at']) + "<small class='competitor-warning'>" + escape(error)
                     + '</small></td><td>' + f"<a href='{path}/{row['id']}'>Histórico</a>"
                     + f"<form method='post' action='{path}/{row['id']}/estado'>" + form_token()
                     + "<input type='hidden' name='ativo' value='" + ('0' if row['active'] else '1') + "'>"
                     + "<button class='btn-acoes cinza'>" + ('Pausar' if row['active'] else 'Retomar') + '</button></form></td></tr>')
        if not rows:
            body += "<tr><td colspan='6'>Nenhum concorrente encontrado. Cadastre um link acima ou ajuste os filtros.</td></tr>"
        body += '</tbody></table></div>' + pager(path,request.args,current_page,pages,total) + '</div>'
        body += "<style>.competitor-form{display:flex;gap:12px;flex-wrap:wrap;align-items:end}.competitor-form label{display:grid;gap:5px;flex:1;min-width:170px}td small{display:block;margin-top:5px}.competitor-warning{color:#9a3412}td{vertical-align:top}</style>"
        return shop_page('Concorrência',cid,store['cliente'],'anuncios',body), status_code

    @app.route('/anuncios/<int:cid>/concorrencia/<int:target_id>/estado', methods=['POST'])
    @login_required
    def competitor_state(cid, target_id):
        _, denied = shop(cid)
        if denied:
            return denied
        invalid_csrf = csrf()
        if invalid_csrf:
            return invalid_csrf
        if request.form.get('ativo') not in ('0','1'):
            return 'Estado inválido', 400
        with bank() as conn:
            rows = query(conn, '''UPDATE competitor_targets SET active=%s
                WHERE id=%s AND conexao_id=%s RETURNING id''', (request.form['ativo']=='1',target_id,cid))
        if not rows:
            return 'Concorrente não encontrado nesta loja', 404
        return redirect(f'/anuncios/{cid}/concorrencia',code=303)

    @app.route('/anuncios/<int:cid>/concorrencia/<int:target_id>')
    @login_required
    def competitor_history(cid, target_id):
        store, denied = shop(cid)
        if denied:
            return denied
        with bank() as conn:
            targets = query(conn,'SELECT * FROM competitor_targets WHERE id=%s AND conexao_id=%s',(target_id,cid))
            if not targets:
                return 'Concorrente não encontrado nesta loja', 404
            target = targets[0]
            clauses, values = ['target_id=%s'], [target_id]
            days = request.args.get('dias','30')
            days = int(days) if days in ('7','30','90') else 30
            clauses.append('observed_at >= %s')
            values.append(int(time.time()) - days * 86400)
            if request.args.get('alteracoes') == '1':
                clauses.append('(price_changed OR full_changed)')
            where = ' AND '.join(clauses)
            total = query(conn,'SELECT COUNT(*) AS n FROM competitor_observations WHERE ' + where,tuple(values))[0]['n']
            current_page,size,pages = pagination(request.args,total)
            rows = query(conn,'SELECT * FROM competitor_observations WHERE ' + where
                         + ' ORDER BY observed_at DESC,slot DESC LIMIT %s OFFSET %s',tuple(values)+(size,(current_page-1)*size))
        path = f'/anuncios/{cid}/concorrencia/{target_id}'
        body = tabs(cid) + '<h2>Histórico · ' + escape(target['label'] or target['title'] or target['item_id']) + '</h2>'
        body += '<p>' + target['item_id'] + ' · histórico desde o cadastro em ' + date_time(target['created_at']) + '</p>'
        body += ("<div class='card'><form method='get'><label>Período " + select('dias',[('7','7 dias'),('30','30 dias'),('90','90 dias')]).replace("value='30'", "value='30' selected" if not request.args.get('dias') else "value='30'")
                 + "</label> <label><input type='checkbox' name='alteracoes' value='1'" + (' checked' if request.args.get('alteracoes')=='1' else '')
                 + "> Apenas alterações</label> <button class='btn-acoes'>Filtrar</button></form>"
                 + '<p>Horário de Brasília. O primeiro dado é a referência inicial. Falhas não criam alterações e os períodos sem consulta não são preenchidos.</p></div>')
        body += "<div class='card'><div style='overflow:auto'><table><thead><tr><th>Consulta</th><th>Preço final</th><th>Alteração do preço</th><th>Full</th><th>Alteração Full</th><th>Resultado</th></tr></thead><tbody>"
        for row in rows:
            body += ('<tr><td>' + date_time(row['observed_at']) + '</td><td>' + brl(row['price']) + '</td><td>'
                     + (delta(row['price'],row['previous_price']) if row['price_changed'] else '—') + '</td><td>'
                     + full_text(row['full_state']) + '</td><td>'
                     + (full_text(row['previous_full']) + ' → ' + full_text(row['full_state']) if row['full_changed'] else '—')
                     + '</td><td>' + escape(row['error'] or 'Consulta concluída') + '</td></tr>')
        if not rows:
            body += "<tr><td colspan='6'>Ainda não há consultas para este filtro.</td></tr>"
        body += '</tbody></table></div>' + pager(path,request.args,current_page,pages,total) + '</div>'
        body += f"<p><a href='/anuncios/{cid}/concorrencia'>← Voltar à concorrência</a></p>"
        return shop_page('Histórico da concorrência',cid,store['cliente'],'anuncios',body)
