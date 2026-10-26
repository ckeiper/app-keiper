import contextlib
from datetime import date
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_calendar import load,render
from listing_task_routes import register_tasks

DAY=date(2026,10,26)
class CalendarTests(unittest.TestCase):
    def test_month_scope_bounds_and_pagination(self):
        q=Mock(side_effect=[[dict(due_date=DAY,n=23)],[]])
        m=load(None,q,7,'MLB1',dict(mes='2026-10',status='done',pagina='99'),DAY)
        self.assertEqual((m['page'],m['pages'],m['total']),(3,3,23))
        self.assertEqual(q.call_args_list[0].args[2],(7,'MLB1',date(2026,10,1),date(2026,11,1),'done'))
        self.assertIn('LIMIT 10 OFFSET %s',q.call_args.args[1]);self.assertEqual(q.call_args.args[2][-1],20)
        for c in q.call_args_list:self.assertIn('conexao_id=%s AND item_id=%s',c.args[1])
    def test_invalid_and_year_boundary(self):
        for month in ['bad','2026-2','0000-01','2101-01','2026-13']:
            q=Mock()
            with self.assertRaises(ValueError):load(None,q,7,'MLB1',dict(mes=month),DAY)
            q.assert_not_called()
        q=Mock(side_effect=[[],[]]);m=load(None,q,7,'MLB1',dict(mes='2026-12',status='bad',pagina='bad'),DAY)
        self.assertEqual(q.call_args_list[0].args[2][-2:],(date(2027,1,1),'open'));self.assertEqual(m['page'],1)
    def test_render_empty_leap_month_and_escape(self):
        q=Mock(side_effect=[[],[]]);m=load(None,q,7,'MLB1',dict(mes='2024-02'),DAY)
        text=render(7,'MLB1',dict(titulo='<script>'),m,DAY)
        self.assertEqual(text.count('role="listitem"'),29);self.assertIn('Nenhuma tarefa',text);self.assertNotIn('<script>',text)
    def test_aggregate_all_pages_links_and_overdue(self):
        m=load(None,Mock(side_effect=[[dict(due_date=DAY,n=23)],[]]),7,'MLB1',{},DAY)
        m['rows']=[dict(id=1,title='<img>',responsible='<script>',due_date=date(2026,10,25),status='open')]
        text=render(7,'MLB1',{},m,DAY)
        self.assertIn('23 tarefas',text);self.assertIn('Atrasada',text);self.assertIn('pagina=2',text);self.assertIn('mes=2026-10',text)
        self.assertIn('tarefas?status=all&amp;tarefa=1#lt-historico',text);self.assertNotIn('<img>',text)
    def test_route_auth_scope_readonly_and_errors(self):
        app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
        register_tasks(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1],today=lambda:DAY)
        client=app.test_client();path='/anuncios/7/MLB1/calendario'
        self.assertEqual(client.get(path).status_code,403)
        with client.session_transaction() as s:s.update(tipo='admin',usuario_id=1)
        self.assertEqual(client.get('/anuncios/8/MLB1/calendario').status_code,403);q.assert_not_called()
        q.return_value=[];self.assertEqual(client.get(path).status_code,404)
        q.side_effect=[[dict(cliente='Loja',titulo='Anúncio')],[],[]]
        self.assertEqual(client.get(path).status_code,200)
        self.assertIn('READ ONLY',e.call_args.args[1])
        q.side_effect=[[dict(cliente='Loja')]];self.assertEqual(client.get(path+'?mes=bad').status_code,400)
        self.assertEqual(client.post(path).status_code,405)
