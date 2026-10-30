import json
from copy import deepcopy
from datetime import date,timedelta
from pathlib import Path
import unittest
from unittest.mock import patch
from functools import wraps
from flask import Flask,session,redirect
from anuncios_progress import read,validate,summary
from anuncios_progress_view import render
from anuncios_progress_routes import register_progress
from test_listing_details import main_function
from home_sidebar import render_home_sidebar
from store_sidebar import render_store_sidebar
import html


class AnunciosProgressTests(unittest.TestCase):
    def test_current_counts_come_from_records_and_not_the_target_90(self):
        data=read();model=summary(data)
        self.assertEqual(model['total'],len([r for r in data['capacidades'] if r['numero_original'] is not None]) if data['lista_original_completa'] else len(data['capacidades']))
        self.assertEqual(model['counts']['concluida'],sum(r['estado']=='concluida' for r in data['capacidades'] if not data['lista_original_completa'] or r['numero_original'] is not None))
        self.assertEqual(sum(model['counts'].values()),model['total'])
        if not data['lista_original_completa']:
            self.assertIsNone(data['contagem_das_90']);self.assertEqual(model['base'],'frentes_auditadas')
        else:self.assertEqual(model['base'],'originais')

    def test_unproven_completion_missing_references_and_duplicate_ids_rejected(self):
        for change in ('gap','file','duplicate','status'):
            data=deepcopy(read());row=next(r for r in data['capacidades'] if r['estado']=='concluida')
            if change=='gap':row['falta']='Falta validar'
            if change=='file':row['testes']=['missing.py']
            if change=='duplicate':data['capacidades'].append(deepcopy(row))
            if change=='status':row['estado']='inventado'
            with self.assertRaises(ValueError):validate(data)

    def test_original_mapping_and_history_cannot_fabricate_counts(self):
        for key,value in [('contagem_das_90',20),('lista_original_completa',True)]:
            data=deepcopy(read());data[key]=value
            with self.assertRaises(ValueError):validate(data)
        data=deepcopy(read());data['capacidades'][0]['numero_original']=90
        with self.assertRaises(ValueError):validate(data)
        data=deepcopy(read());data['historico'][0]['contagens']['concluida']=999
        with self.assertRaises(ValueError):validate(data)

    def test_graph_only_no_links_lists_or_controls_and_no_fake_prior_measurements(self):
        data=deepcopy(read());data['historico']=[data['historico'][-1]];text=render(data,summary(data))
        self.assertEqual(text.count('<svg'),1);self.assertEqual(text.count('<rect class="ap-column"'),1)
        for tag in ('<a ','<table','<form','<ul','<ol'):
            self.assertNotIn(tag,text)
        self.assertIn('Primeira medição',text)
        if not data['lista_original_completa']:
            self.assertIn(str(summary(data)['total'])+' frentes identificadas',text);self.assertIn('Meta original: 90',text)
            self.assertNotIn(str(summary(data)['counts']['concluida'])+'/90',text)

    def test_new_release_measurement_updates_chart_without_mutating_ledger(self):
        data=deepcopy(read());before=deepcopy(data)
        row=next(r for r in data['capacidades'] if not data['lista_original_completa'] or r['numero_original'] is not None)
        row.update(estado='parcial',falta='Lacuna sintética')
        initial=summary(data);data['historico']=[dict(base=initial['base'],data=data['historico'][-1]['data'],resumo='Medição sintética',contagens=dict(initial['counts']),total=initial['total'],prs=[])]
        row.update(estado='concluida',falta='')
        model=summary(data)
        data['historico'].append(dict(base=model['base'],data=(date.fromisoformat(data['historico'][-1]['data'])+timedelta(days=1)).isoformat(),resumo='Entrega verificada',contagens=dict(model['counts']),total=model['total'],prs=[]))
        text=render(data,model)
        self.assertEqual(text.count('<rect class="ap-column"'),2);self.assertNotIn('<polyline',text)
        self.assertEqual(model['counts']['concluida'],initial['counts']['concluida']+1)
        self.assertEqual(read(),before)

    def test_history_text_is_escaped_in_svg_and_only_same_basis_is_plotted(self):
        data=deepcopy(read());data['historico']=[data['historico'][-1]];data['historico'][0]['resumo']='<script>'
        data['historico'].append(dict(base='originais' if summary(data)['base']=='frentes_auditadas' else 'frentes_auditadas',data=(date.fromisoformat(data['historico'][-1]['data'])+timedelta(days=1)).isoformat(),resumo='Outra base',contagens={'pendente':90},total=90,prs=[]))
        text=render(data,summary(data))
        self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
        self.assertEqual(text.count('<rect class="ap-column"'),1)

    def test_same_day_keeps_last_measurement_without_changing_history(self):
        data=deepcopy(read());event=deepcopy(data['historico'][-1]);day=event['data']
        first=deepcopy(event);first['contagens']['concluida']=17
        last=deepcopy(event);last['contagens']['concluida']=22;last['resumo']='Última entrega do dia'
        data['historico']=[first,last];before=deepcopy(data['historico'])
        text=render(data,summary(data))
        self.assertEqual(text.count('<rect class="ap-column"'),1)
        self.assertIn('22 concluídas. Última entrega do dia',text)
        self.assertNotIn('17 concluídas.',text)
        self.assertEqual(data['historico'],before)
        # Apply the twelve-day display limit after merging duplicate days.
        previous=deepcopy(event);previous['data']=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
        data['historico']=[previous]+[deepcopy(last) for _ in range(20)]
        self.assertEqual(render(data,summary(data)).count('<rect class="ap-column"'),2)

    def test_admin_route_requires_login_role_and_performs_no_network_requests(self):
        app=Flask(__name__);app.secret_key='isolated'
        def login(fn):
            @wraps(fn)
            def wrapped(*a,**kw):
                return fn(*a,**kw) if session.get('usuario_id') else redirect('/login')
            return wrapped
        register_progress(app,login,lambda title,body:body)
        client=app.test_client();self.assertEqual(client.get('/evolucao-anuncios').status_code,302)
        with client.session_transaction() as s:s.update(usuario_id=1,tipo='cliente')
        self.assertEqual(client.get('/evolucao-anuncios').status_code,403)
        self.assertEqual(client.get('/evolucao-anuncios/grafico').status_code,403)
        with client.session_transaction() as s:s['tipo']='admin'
        with patch('requests.get',side_effect=AssertionError('network')):
            self.assertEqual(client.get('/evolucao-anuncios').status_code,200)
            response=client.get('/evolucao-anuncios/grafico')
            self.assertEqual(response.status_code,200);self.assertIn('<svg',response.get_json()['html'])
            self.assertNotIn('capacidades',response.get_json());self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(client.post('/evolucao-anuncios').status_code,405)
        with patch('anuncios_progress_routes.read',side_effect=ValueError('bad ledger')):
            response=client.get('/evolucao-anuncios')
            self.assertEqual(client.get('/evolucao-anuncios/grafico').status_code,503)
        self.assertEqual(response.status_code,503);self.assertNotIn('<svg',response.get_data(as_text=True))

    def test_navigation_is_administrative_and_page_has_correct_active_link(self):
        self.assertNotIn('/evolucao-anuncios',render_home_sidebar(False))
        self.assertNotIn('/evolucao-anuncios',render_store_sidebar(1,'Loja','anuncios',False))
        page=main_function('pagina',dict(session={'tipo':'admin'},esc=html.escape,CSS='',VISUAL_CSS='',SCRIPT='',img_logo=lambda size:''))
        text=page('Evolução',render(read(),summary(read())))
        self.assertIn("href='/evolucao-anuncios' aria-current='page'",text)
        self.assertNotIn("href='/painel' aria-current='page'",text)
        self.assertEqual(text.count("href='/seguranca'"),1)
