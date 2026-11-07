"""Admin-only financial workspace. All writes use the application's CSRF guard."""
from contextlib import closing
from functools import wraps
from datetime import date
from flask import request, session, redirect, abort, render_template_string
import psycopg2
import uuid
from financeiro_service import (sync_finance, create_manual_client, create_contract,
                               record_payment, consolidate_account, today_br)
from financeiro_store import balance_status


def money(value):
    value = int(value or 0)
    return ('R$ {:,.2f}'.format(value / 100)).replace(',', 'X').replace('.', ',').replace('X', '.')


def register_financeiro(app, bank, query, page):
    def admin(fn):
        @wraps(fn)
        def protected(*args, **kwargs):
            if 'usuario_id' not in session:
                return redirect('/login')
            if session.get('tipo') != 'admin':
                abort(403)
            return fn(*args, **kwargs)
        return protected

    @app.route('/financeiro', methods=['GET'])
    @admin
    def financeiro():
        today = today_br()
        try:
            competence = date.fromisoformat(request.args.get('competencia', today.strftime('%Y-%m')) + '-01')
        except ValueError:
            abort(400, 'Competência inválida')
        with closing(bank()) as conn, conn:
            clients = query(conn, '''SELECT c.*, COALESCE(string_agg(x.cliente, ', ' ORDER BY x.id),'') AS lojas
                FROM financeiro_clientes c LEFT JOIN financeiro_vinculos v ON v.cliente_id=c.id
                LEFT JOIN conexoes x ON x.id=v.conexao_id GROUP BY c.id ORDER BY c.nome,c.id''')
            accounts = query(conn, 'SELECT id,cliente FROM conexoes ORDER BY cliente,id')
            contracts = query(conn, '''SELECT t.*,c.nome FROM financeiro_contratos t
                JOIN financeiro_clientes c ON c.id=t.cliente_id ORDER BY t.id DESC''')
            invoices = query(conn, '''SELECT m.*,c.nome,COALESCE(p.pago,0) AS pago
                FROM financeiro_mensalidades m JOIN financeiro_contratos t ON t.id=m.contrato_id
                JOIN financeiro_clientes c ON c.id=t.cliente_id
                LEFT JOIN (SELECT mensalidade_id,SUM(valor_centavos) AS pago FROM financeiro_pagamentos
                    GROUP BY mensalidade_id) p ON p.mensalidade_id=m.id
                WHERE m.competencia=%s ORDER BY c.nome,m.id''', (competence,))
            history = query(conn, '''SELECT p.*,c.nome,m.competencia FROM financeiro_pagamentos p
                JOIN financeiro_mensalidades m ON m.id=p.mensalidade_id
                JOIN financeiro_contratos t ON t.id=m.contrato_id
                JOIN financeiro_clientes c ON c.id=t.cliente_id
                ORDER BY p.data_pagamento DESC,p.id DESC LIMIT 200''')
        totals = dict(previsto=0, recebido=0, aberto=0, atrasado=0)
        for row in invoices:
            row['chave'] = str(uuid.uuid4())
            row['saldo'] = row['valor_centavos'] - row['pago']
            row['status'] = balance_status(row['valor_centavos'], row['pago'], row['vencimento'], today)
            totals['previsto'] += row['valor_centavos']
            totals['recebido'] += row['pago']
            totals['aberto'] += row['saldo']
            if row['vencimento'] < today:
                totals['atrasado'] += row['saldo']
        return page('Financeiro', render_template_string(TEMPLATE, clients=clients, accounts=accounts,
            contracts=contracts, invoices=invoices, history=history, totals=totals,
            competence=competence.strftime('%Y-%m'), today=today, money=money,
            notice=request.args.get('ok') == '1'))

    @app.route('/financeiro/<action>', methods=['POST'])
    @admin
    def financeiro_write(action):
        data = request.form
        try:
            with closing(bank()) as conn, conn:
                if action == 'clientes':
                    create_manual_client(conn, data.get('nome'), data.get('telefone') or None, data.get('email') or None)
                elif action == 'contratos':
                    start = date.fromisoformat(data['inicio'])
                    if not 2000 <= start.year <= today_br().year + 5:
                        raise ValueError('Início fora do período permitido (2000 até os próximos 5 anos)')
                    create_contract(conn, int(data['cliente_id']), data['valor'].replace(',', '.'), start)
                elif action == 'pagamentos':
                    paid_on = date.fromisoformat(data['data_pagamento'])
                    if paid_on > today_br():
                        raise ValueError('Pagamento não pode ter data futura')
                    record_payment(conn, int(data['mensalidade_id']), data['valor'].replace(',', '.'),
                                   paid_on, data['meio'], data.get('observacao'),
                                   str(uuid.UUID(data['chave'])), session['usuario_id'])
                elif action == 'vinculos':
                    if data.get('confirmar') != 'sim':
                        raise ValueError('Confirme a consolidação do vínculo')
                    consolidate_account(conn, int(data['cliente_id']), int(data['conexao_id']))
                else:
                    abort(404)
                if action == 'contratos':
                    sync_finance(conn)
        except (ValueError, KeyError):
            return page('Financeiro', '<div class="card"><h2>Não foi possível salvar</h2>'
                        '<p>Confira os campos. Vínculos de clientes com contratos e pagamentos acima do saldo são bloqueados.</p>'
                        '<a href="/financeiro">Voltar ao Financeiro</a></div>'), 400
        except psycopg2.IntegrityError:
            return page('Financeiro', '<div class="card"><h2>Cadastro indisponível</h2><p>Recarregue e confira o cliente ou a loja selecionada.</p><a href="/financeiro">Voltar</a></div>'), 409
        return redirect('/financeiro?ok=1', code=303)


TEMPLATE = '''
<style>
.kf{max-width:1400px;margin:auto}.kf h2{margin-bottom:8px}.kf .muted{color:var(--kp-subtle,#71829b)}
.kf-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:24px 0}
.kf .card{padding:22px;margin-bottom:18px}.kf-grid strong{display:block;font-size:25px;margin-top:10px}
.kf-forms{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.kf label{display:block;margin:12px 0}
.kf input,.kf select{display:block;box-sizing:border-box;width:100%;padding:10px;margin-top:5px;border:1px solid var(--kp-line,#ccd6e5);border-radius:8px;background:inherit;color:inherit}
.kf button{padding:10px 16px;border:0;border-radius:8px;background:var(--kp-blue,#315cdd);color:white;cursor:pointer}
.kf .scroll{overflow:auto}.kf table{width:100%;border-collapse:collapse;white-space:nowrap}.kf th,.kf td{text-align:left;padding:12px;border-bottom:1px solid var(--kp-line,#ccd6e5)}
.kf details{margin:12px 0}.kf summary{cursor:pointer;font-weight:600}.kf .payment{min-width:240px;white-space:normal}.kf .success{padding:15px;border:1px solid #36a888;border-radius:10px}
@media(max-width:800px){.kf-grid,.kf-forms{grid-template-columns:1fr 1fr}}@media(max-width:520px){.kf-grid,.kf-forms{grid-template-columns:1fr}}
</style><main class="kf">
<h2>Financeiro <small class="muted">Keiper 1.0</small></h2>
<p class="muted">Mensalidades individuais · vencimento sempre dia 5 · recebimentos manuais PIX ou transferência</p>
{% if notice %}<p class="success" role="status">Registro salvo com sucesso.</p>{% endif %}
<form method="get"><label>Competência <input type="month" name="competencia" value="{{competence}}" required></label><button>Consultar</button></form>
<div class="kf-grid">{% for key,label in [('previsto','Previsto'),('recebido','Recebido'),('aberto','Saldo a receber'),('atrasado','Saldo em atraso')] %}<div class="card"><span>{{label}}</span><strong>{{money(totals[key])}}</strong><small class="muted">Competência {{competence}}</small></div>{% endfor %}</div>
<section class="card"><h3>Mensalidades da competência</h3><p class="muted">Lançamentos automáticos desde o início de cada contrato até o mês atual. Recebido considera as baixas dessas mensalidades.</p>
<div class="scroll"><table><thead><tr><th>Cliente</th><th>Vencimento</th><th>Mensalidade</th><th>Recebido</th><th>Saldo</th><th>Situação / baixa</th></tr></thead><tbody>
{% for i in invoices %}<tr><td>{{i.nome}}<br><small>#{{i.id}} · contrato #{{i.contrato_id}}</small></td><td>{{i.vencimento.strftime('%d/%m/%Y')}}</td><td>{{money(i.valor_centavos)}}</td><td>{{money(i.pago)}}</td><td>{{money(i.saldo)}}</td><td>{{i.status.replace('_',' ')}}
{% if i.saldo > 0 %}<details class="payment"><summary>Registrar pagamento</summary><form method="post" action="/financeiro/pagamentos"><input type="hidden" name="chave" value="{{i.chave}}"><input type="hidden" name="mensalidade_id" value="{{i.id}}"><label>Valor recebido (R$)<input name="valor" type="number" min="0.01" step="0.01" max="{{i.saldo / 100}}" required></label><label>Data do pagamento<input type="date" name="data_pagamento" value="{{today}}" max="{{today}}" required></label><label>Meio<select name="meio"><option value="pix">PIX</option><option value="transferencia">Transferência</option></select></label><label>Observação<input name="observacao" maxlength="1000"></label><button>Confirmar recebimento</button></form></details>{% endif %}</td></tr>{% else %}<tr><td colspan="6">Nenhuma mensalidade nesta competência. Cadastre um contrato para começar.</td></tr>{% endfor %}</tbody></table></div></section>
<div class="kf-forms"><section class="card"><h3>Cliente não integrado</h3><form method="post" action="/financeiro/clientes"><label>Nome<input name="nome" maxlength="300" required></label><label>Telefone<input name="telefone" maxlength="50"></label><label>E-mail<input name="email" type="email" maxlength="300"></label><button>Cadastrar cliente</button></form></section>
<section class="card"><h3>Novo contrato</h3><form method="post" action="/financeiro/contratos"><label>Cliente<select name="cliente_id" required><option value="">Selecione</option>{% for c in clients %}<option value="{{c.id}}">{{c.nome}} · #{{c.id}}</option>{% endfor %}</select></label><label>Mensalidade (R$)<input type="number" name="valor" min="0" step="0.01" required></label><label>Início<input type="date" name="inicio" value="{{today}}" required></label><p>Vencimento: dia 5. A primeira cobrança corresponde ao mês de início, sem proporcionalidade.</p><button>Criar contrato</button></form></section></div>
<section class="card"><h3>Clientes e lojas integradas</h3><p class="muted">Novas lojas são importadas automaticamente uma vez, sem unir clientes apenas pelo nome. Nenhum valor é presumido.</p><div class="scroll"><table><thead><tr><th>Cliente</th><th>Contato</th><th>Lojas vinculadas</th></tr></thead><tbody>{% for c in clients %}<tr><td>#{{c.id}} · {{c.nome}}</td><td>{{c.telefone or '—'}}<br>{{c.email or ''}}</td><td>{{c.lojas or 'Cadastro manual'}}</td></tr>{% else %}<tr><td colspan="3">Nenhum cliente cadastrado.</td></tr>{% endfor %}</tbody></table></div>
<details><summary>Consolidar loja no cliente correto</summary><p>Selecione a loja e seu cliente financeiro. Clientes de origem com contratos são bloqueados para preservar o histórico. Confira os identificadores antes de confirmar.</p><form method="post" action="/financeiro/vinculos"><label>Loja<select name="conexao_id" required>{% for a in accounts %}<option value="{{a.id}}">#{{a.id}} · {{a.cliente}}</option>{% endfor %}</select></label><label>Cliente de destino<select name="cliente_id" required>{% for c in clients %}<option value="{{c.id}}">#{{c.id}} · {{c.nome}}</option>{% endfor %}</select></label><label><select name="confirmar" required><option value="">Confirme que conferiu loja e cliente</option><option value="sim">Conferi e confirmo o vínculo</option></select></label><button>Salvar vínculo</button></form></details></section>
<section class="card"><h3>Contratos</h3><div class="scroll"><table><thead><tr><th>Contrato / cliente</th><th>Mensalidade</th><th>Início</th><th>Vencimento</th></tr></thead><tbody>{% for c in contracts %}<tr><td>#{{c.id}} · {{c.nome}}</td><td>{{money(c.valor_centavos)}}</td><td>{{c.inicio}}</td><td>Dia 5</td></tr>{% else %}<tr><td colspan="4">Nenhum contrato cadastrado.</td></tr>{% endfor %}</tbody></table></div></section>
<section class="card"><h3>Histórico de recebimentos</h3><p class="muted">Últimos 200 registros, de todas as competências.</p><div class="scroll"><table><thead><tr><th>Data</th><th>Cliente / competência</th><th>Valor</th><th>Meio</th><th>Observação</th></tr></thead><tbody>{% for p in history %}<tr><td>{{p.data_pagamento}}</td><td>{{p.nome}} · {{p.competencia.strftime('%m/%Y')}}</td><td>{{money(p.valor_centavos)}}</td><td>{{p.meio}}</td><td>{{p.observacao or '—'}}</td></tr>{% else %}<tr><td colspan="5">Nenhum pagamento registrado.</td></tr>{% endfor %}</tbody></table></div></section></main>
'''
