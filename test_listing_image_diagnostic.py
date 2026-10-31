import contextlib
import unittest
from copy import deepcopy
from datetime import datetime,timezone
from functools import wraps
from unittest.mock import Mock,patch
import requests
from flask import Flask,session,redirect
from listing_image_diagnostic import inspect,normalize,render,register

ID='f0b6198b-a4ef-4291-82a5-41956e0af96e'
NOW=datetime(2026,10,30,22,tzinfo=timezone.utc)
PHOTO='123456-MLB123456_102026'

def item(**changes):return dict(dict(id='MLB123',seller_id=7,site_id='MLB',title='Produto de teste',category_id='MLB200',thumbnail_id=PHOTO,pictures=[dict(id=PHOTO)]),**changes)
def detection(name='white_background',message='Confira o fundo conforme a categoria.'):return dict(name=name,wordings=[dict(kind='REMEDY_SHORT',value=message)])
def payload(action='diagnostic',detections=None):return dict(id=ID,diagnostics=[dict(picture_type='thumbnail',action=action,detections=([detection()] if detections is None and action=='diagnostic' else detections or []))])
def requester(values=None):return Mock(side_effect=[Mock(status_code=200,json=Mock(return_value=v)) for v in (values or [dict(id=7),item()])])
def poster(p=None):return Mock(return_value=Mock(status_code=200,json=Mock(return_value=payload() if p is None else p)))
def read_result(get=None,post=None):
    with patch('listing_image_diagnostic.uuid4',return_value=ID):return inspect('secret-token',7,'MLB123',get or requester(),post or poster(),NOW)

class ImageDiagnosticTests(unittest.TestCase):
    def test_verified_thumbnail_two_gets_one_post_no_remote_url_or_offer_mutation(self):
        value=item(pictures=[dict(id='OTHER'),dict(id=PHOTO)],buyer={'contact':'private'})
        before=deepcopy(value);get=requester([dict(id=7),value]);post=poster();r=read_result(get,post)
        self.assertEqual(r['state'],'read');self.assertEqual(get.call_count,2);self.assertEqual(post.call_count,1);self.assertEqual(value,before)
        self.assertEqual([c.args[0] for c in get.call_args_list],['https://api.mercadolibre.com/users/me','https://api.mercadolibre.com/items/MLB123'])
        self.assertEqual(post.call_args.args[0],'https://api.mercadolibre.com/moderations/pictures/diagnostic')
        body=post.call_args.kwargs['json'];self.assertEqual(body,dict(id=ID,picture_id=PHOTO,context=dict(category_id='MLB200',picture_type='thumbnail',title='Produto de teste')))
        self.assertNotIn('picture_url',body);self.assertNotIn('private',str(body));self.assertNotIn('secret-token',str(r))
        for call in get.call_args_list+[post.call_args]:self.assertEqual(call.kwargs['timeout'],(3,8));self.assertFalse(call.kwargs['allow_redirects'])

    def test_invalid_input_and_owner_or_site_stop_before_diagnostic(self):
        for args in [(None,7,'MLB123'),('x',True,'MLB123'),('x',None,'MLB123'),('x',7,'../pictures')]:
            get=Mock();post=Mock();self.assertEqual(inspect(*args,get,post)['state'],'unknown');get.assert_not_called();post.assert_not_called()
        for values,count in [([dict(id=8)],1)]+[([dict(id=7),item(**p)],2) for p in (dict(id='MLB124'),dict(seller_id=8),dict(site_id='MLA'))]:
            get=requester(values);post=poster();self.assertEqual(read_result(get,post)['state'],'unknown');self.assertEqual(get.call_count,count);post.assert_not_called()

    def test_missing_ambiguous_or_foreign_picture_and_category_are_not_absence(self):
        for change in (dict(thumbnail_id=None),dict(thumbnail_id='https://evil.invalid/x'),dict(thumbnail_id='OTHER'),dict(pictures=[]),dict(pictures=None),dict(pictures=[dict(id=PHOTO),dict(id=PHOTO)]),dict(pictures=[None]),dict(category_id='../bad'),dict(pictures=[dict(id=str(i)) for i in range(1001)])):
            get=requester([dict(id=7),item(**change)]);post=poster();r=read_result(get,post)
            self.assertEqual(r['state'],'unknown');post.assert_not_called();self.assertEqual(get.call_count,2)

    def test_get_http_failures_and_network_errors_never_continue_or_leak(self):
        for stage in (0,1):
            for status in (301,401,403,404,429,500):
                get=Mock(side_effect=([Mock(status_code=200,json=Mock(return_value=dict(id=7)))] if stage else [])+[Mock(status_code=status)])
                post=poster();r=read_result(get,post);self.assertEqual(r['state'],'unknown');self.assertEqual(get.call_count,stage+1);post.assert_not_called();self.assertNotIn('secret-token',str(r))
        for exc in (requests.Timeout('secret-token'),ValueError('secret-token')):
            get=Mock(side_effect=exc);post=poster();self.assertEqual(read_result(get,post)['state'],'unknown');post.assert_not_called()

    def test_post_errors_do_not_become_approval_retry_or_empty(self):
        for status in (201,301,401,403,404,429,500):
            post=Mock(return_value=Mock(status_code=status));r=read_result(post=post);self.assertEqual(r['state'],'unknown');self.assertEqual(post.call_count,1);self.assertNotIn('action',r)
        for exc in (requests.Timeout('secret-token'),ValueError('secret-token')):
            post=Mock(side_effect=exc);r=read_result(post=post);self.assertEqual(r['state'],'unknown');self.assertNotIn('secret-token',str(r))

    def test_only_requested_role_and_matching_receipt_are_used(self):
        p=payload('empty');p['diagnostics'].append(dict(picture_type='other',action='diagnostic',detections=[detection('watermark')]))
        self.assertEqual(normalize(p,ID),dict(action='empty',findings=[]))
        for mutation in (dict(id='OTHER'),dict(diagnostics=[]),dict(diagnostics=[dict(picture_type='other',action='empty',detections=[])]),dict(diagnostics=payload()['diagnostics']*2),dict(diagnostics=[None])):
            p=payload();p.update(mutation)
            with self.assertRaises(ValueError):normalize(p,ID)

    def test_unknown_malformed_or_inconsistent_detection_never_empty(self):
        cases=[payload('empty',[detection()]),payload('diagnostic',[]),payload(detections=[detection('future_signal')]),payload(detections=[detection(),detection()]),payload(detections=[dict(name='white_background',wordings=[])]),payload(detections=[detection(message='x'*2001)])]
        p=payload();p['diagnostics'][0]['detections'][0]['wordings'][0]['kind']='OTHER';cases.append(p)
        cases.append(dict(id=ID,diagnostics=payload()['diagnostics']*11))
        cases.append(payload(detections=[detection() for _ in range(21)]))
        d=detection();d['wordings']*=11;cases.append(payload(detections=[d]))
        for p in cases:
            with self.assertRaises(ValueError):normalize(p,ID)

    def test_four_official_signals_bounds_escape_and_no_approval_claim(self):
        p=payload(detections=[detection(n,'<script>x()</script>') for n in ('white_background','minimum_size','text_logo','watermark')])
        r=read_result(post=poster(p));self.assertEqual(len(r['findings']),4)
        html=render(1,'MLB123','<script>','csrf',r);self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertNotIn('<img',html);self.assertIn('19:00:00',html)
        r=read_result(post=poster(payload('empty')));html=render(1,'MLB123','Título','csrf',r)
        self.assertIn('Isso não aprova',html);self.assertNotIn('aprovada',html)
        self.assertNotIn('image-diagnostic-result',render(1,'MLB123','Título','csrf'))
        r=read_result(get=requester([dict(id=7),item(catalog_listing=True)]));self.assertIn('gestão das imagens',render(1,'MLB123','Título','csrf',r))

    def test_route_auth_store_csrf_get_and_fixed_picture_selection(self):
        app=Flask(__name__);app.secret_key='test-only';get=requester();post=poster();resolve=Mock(return_value='x');query=Mock(return_value=[dict(user_id=7,cliente='Loja teste',titulo='Produto')]);shell=Mock(side_effect=lambda *a,**kw:a[4])
        def login(fn):
            @wraps(fn)
            def inner(*a,**kw):return fn(*a,**kw) if session.get('usuario_id') else redirect('/login')
            return inner
        register(app,login,lambda cid:cid==1,lambda:contextlib.nullcontext(None),query,shell,resolve,get,post)
        client=app.test_client();path='/anuncios/1/MLB123/imagem-principal'
        self.assertEqual(client.get(path).status_code,302)
        with client.session_transaction() as s:s.update(usuario_id=1,tipo='cliente',_csrf='csrf')
        self.assertEqual(client.get(path).status_code,403)
        with client.session_transaction() as s:s['tipo']='admin'
        self.assertEqual(client.get('/anuncios/2/MLB123/imagem-principal').status_code,403)
        self.assertEqual(client.post(path,data={'_csrf':'bad'}).status_code,400)
        self.assertEqual(client.get(path).status_code,200);get.assert_not_called();post.assert_not_called();resolve.assert_not_called()
        self.assertFalse(shell.call_args.kwargs['refresh']);self.assertEqual(query.call_args.args[-1],(1,'MLB123'))
        with patch('listing_image_diagnostic.uuid4',return_value=ID):
            self.assertEqual(client.post(path,data={'_csrf':'csrf','picture_id':'evil','picture_url':'https://evil.invalid'}).status_code,200)
        self.assertEqual(post.call_args.kwargs['json']['picture_id'],PHOTO)
        query.return_value=[];self.assertEqual(client.post(path,data={'_csrf':'csrf'}).status_code,404);self.assertEqual(post.call_count,1)
