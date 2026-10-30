import contextlib
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from unittest.mock import Mock
import requests
from flask import Flask,session,redirect
from listing_buyer_reviews import inspect,normalize,render,register

NOW=datetime(2026,10,30,14,tzinfo=timezone.utc)

def item(**patch):
    return dict(dict(id='MLB123',seller_id=7,site_id='MLB',status='active',catalog_product_id=None),**patch)

def review(**patch):
    return dict(dict(id=1,status='published',reviewable_object=dict(type='item',id='MLB123'),rate=4,title='Boa compra',content='Material conforme descrição.'),**patch)

def payload(**patch):
    return dict(dict(paging=dict(total=12,total_pageable=11,limit=5,offset=0),rating_average=4.5,
        rating_levels=dict(one_star=0,two_star=1,three_star=1,four_star=1,five_star=9),reviews=[review()]),**patch)

def requester(values=None):
    return Mock(side_effect=[Mock(status_code=200,json=Mock(return_value=v)) for v in (values or [dict(id=7),item(),payload()])])

class BuyerReviewTests(unittest.TestCase):
    def test_bounded_gets_ownership_no_storage_or_secret_fields(self):
        p=payload();p['buyer']={'email':'private@example.com'};p['reviews'][0]['media']=[{'url':'https://evil.invalid'}]
        before=deepcopy(p);get=requester([dict(id=7),item(),p]);r=inspect('secret',7,'MLB123',get,now=NOW)
        self.assertEqual(r['state'],'read');self.assertEqual(r['total'],12);self.assertEqual(p,before)
        self.assertEqual(get.call_count,3);self.assertEqual(get.call_args.args[0],'https://api.mercadolibre.com/reviews/item/MLB123?limit=5&offset=0')
        for c in get.call_args_list:
            self.assertEqual(c.kwargs,dict(headers={'Authorization':'Bearer secret'},timeout=(3,8),allow_redirects=False))
        for private in ('secret','private@example.com','evil.invalid','media','buyer'):
            self.assertNotIn(private,str(r))

    def test_catalog_scope_and_offset(self):
        p=payload(paging=dict(total=200,total_pageable=180,offset=5,limit=5),reviews=[review(reviewable_object=dict(type='product',id='MLB456'))])
        get=requester([dict(id=7),item(catalog_product_id='MLB456',catalog_listing=True),p]);r=inspect('x',7,'MLB123',get,5,NOW)
        self.assertEqual(r['state'],'read');self.assertEqual(len(r['rows']),1);self.assertTrue(r['capped'])
        self.assertIn('catalog_product_id=MLB456',get.call_args.args[0]);self.assertIn('offset=5',get.call_args.args[0])
        html=render(1,'MLB123','Título','csrf',r);self.assertIn('outros vendedores',html);self.assertIn('Página anterior',html)
        self.assertIn('não medem atendimento',html)

    def test_invalid_input_never_calls_api(self):
        for patch in (dict(token=None),dict(seller_id=True),dict(seller_id=None),dict(item_id='../users/me'),dict(offset=True),dict(offset=-5),dict(offset=100),dict(offset=1)):
            args=dict(token='x',seller_id=7,item_id='MLB123',offset=0);args.update(patch);get=Mock()
            self.assertEqual(inspect(**args,request_get=get)['state'],'unknown');get.assert_not_called()

    def test_owner_site_status_and_catalog_mismatch_stop(self):
        get=requester([dict(id=8)]);self.assertEqual(inspect('x',7,'MLB123',get)['state'],'unknown');self.assertEqual(get.call_count,1)
        for patch in (dict(id='MLB124'),dict(seller_id=8),dict(site_id='MLA'),dict(status='paused'),dict(status=None),dict(catalog_product_id='../bad'),dict(catalog_listing=True)):
            get=requester([dict(id=7),item(**patch)])
            self.assertEqual(inspect('x',7,'MLB123',get)['state'],'unknown');self.assertEqual(get.call_count,2)

    def test_http_errors_stop_without_retry_or_absence(self):
        for status in (301,400,401,403,404,429,500):
            get=requester([dict(id=7),item()]);get.side_effect=[Mock(status_code=200,json=Mock(return_value=dict(id=7))),Mock(status_code=200,json=Mock(return_value=item())),Mock(status_code=status)]
            r=inspect('secret',7,'MLB123',get);self.assertEqual(r['state'],'unknown');self.assertEqual(get.call_count,3)
            self.assertNotIn('secret',str(r));self.assertNotIn('total',r)
        for exc in (requests.Timeout('secret'),ValueError('secret'),requests.ConnectionError('secret')):
            get=Mock(side_effect=exc);r=inspect('secret',7,'MLB123',get);self.assertNotIn('secret',str(r));self.assertEqual(get.call_count,1)

    def test_page_metadata_and_types_are_checked(self):
        for p in (payload(paging=None),payload(reviews=None),payload(reviews=[review()]*6),payload(paging=dict(offset=5,limit=5)),payload(paging=dict(offset=0,limit=True)),payload(paging=dict(offset=False,limit=5))):
            self.assertEqual(inspect('x',7,'MLB123',requester([dict(id=7),item(),p]))['state'],'unknown')

    def test_unpublished_wrong_scope_duplicates_and_invalid_values_omitted(self):
        for patch in (dict(status='blocked'),dict(status='pending'),dict(reviewable_object=dict(type='product',id='MLB456')),dict(reviewable_object=dict(type='item',id='MLB999')),dict(rate=True),dict(rate=6),dict(id=True),dict(title=[]),dict(content=3)):
            r=normalize(payload(reviews=[review(**patch)]),'MLB123',None,0)
            self.assertEqual(r['rows'],[]);self.assertEqual(r['omitted'],1)
        r=normalize(payload(reviews=[review(),review()]),'MLB123',None,0);self.assertEqual(len(r['rows']),1);self.assertEqual(r['omitted'],1)

    def test_missing_malformed_conflicting_and_zero_aggregates(self):
        for p in (payload(rating_average=True,rating_levels=None,paging=dict(offset=0,limit=5)),payload(rating_average=float('nan'),rating_levels={},paging=dict(offset=0,limit=5,total=True,total_pageable=-1))):
            r=normalize(p,'MLB123',None,0);self.assertIsNone(r['total']);self.assertIsNone(r['average']);self.assertIsNone(r['pageable']);self.assertEqual(r['levels'],[None]*5)
        r=normalize(payload(paging=dict(offset=0,limit=5,total=0,total_pageable=0),reviews=[]),'MLB123',None,0)
        self.assertEqual(r['total'],0);self.assertIsNone(r['average']);self.assertIsNone(r['next_offset']);self.assertEqual(r['levels'],[None]*5)
        r=normalize(payload(paging=dict(offset=0,limit=5,total=1,total_pageable=12)),'MLB123',None,0);self.assertIsNone(r['pageable']);self.assertEqual(r['levels'],[None]*5)

    def test_pagination_uses_total_pageable_never_deprecated_count(self):
        p=payload(reviews=[review(id=i+1) for i in range(5)],paging=dict(total=200,total_pageable=11,reviews_with_comment=1,offset=0,limit=5))
        r=normalize(p,'MLB123',None,0);self.assertEqual(r['next_offset'],5)
        p['paging'].pop('total_pageable');self.assertIsNone(normalize(p,'MLB123',None,0)['next_offset'])
        p['paging'].update(total_pageable=200,offset=95);self.assertIsNone(normalize(p,'MLB123',None,95)['next_offset'])

    def test_escape_bounded_text_empty_unknown_and_timezone(self):
        p=payload(reviews=[review(title='<script>bad()</script>',content='<img onerror=x>'+('z'*5000))],cross_site_enabled=True)
        r=inspect('x',7,'MLB123',requester([dict(id=7),item(),p]),now=NOW);html=render(1,'MLB123','<script>','csrf',r)
        self.assertNotIn('<script>',html);self.assertNotIn('<img',html);self.assertIn('Texto abreviado',html);self.assertIn('11:00:00',html)
        self.assertIn('entre países',html);self.assertLessEqual(len(r['rows'][0]['content']),4000)
        self.assertNotIn('buyer-review-result',render(1,'MLB123','P','csrf'))
        empty=inspect('x',7,'MLB123',requester([dict(id=7),item(),payload(reviews=[])]),now=NOW)
        self.assertIn('não comprova ausência',render(1,'MLB123','P','csrf',empty))

    def test_route_auth_store_csrf_and_get_are_scoped(self):
        app=Flask(__name__);app.secret_key='test-only';get=requester();query=Mock(return_value=[dict(user_id=7,cliente='Loja de teste',titulo='Título')]);resolve=Mock(return_value='x');shell=Mock(side_effect=lambda *a,**kw:a[4])
        def login(fn):
            @wraps(fn)
            def wrapped(*a,**kw):return fn(*a,**kw) if session.get('usuario_id') else redirect('/login')
            return wrapped
        register(app,login,lambda cid:cid==1,lambda:contextlib.nullcontext(None),query,shell,resolve,get)
        client=app.test_client();path='/anuncios/1/MLB123/avaliacoes'
        self.assertEqual(client.get(path).status_code,302)
        with client.session_transaction() as s:s.update(usuario_id=1,tipo='cliente',_csrf='csrf')
        self.assertEqual(client.get(path).status_code,403)
        with client.session_transaction() as s:s['tipo']='admin'
        self.assertEqual(client.get('/anuncios/2/MLB123/avaliacoes').status_code,403)
        self.assertEqual(client.post(path,data={'_csrf':'wrong'}).status_code,400);get.assert_not_called()
        self.assertEqual(client.get(path).status_code,200);get.assert_not_called();resolve.assert_not_called()
        self.assertFalse(shell.call_args.kwargs['refresh']);self.assertEqual(query.call_args.args[-1],(1,'MLB123'))
        for offset in ('-1','1','100','https://evil','true'):
            self.assertEqual(client.post(path,data={'_csrf':'csrf','offset':offset}).status_code,400)
        self.assertEqual(client.post(path,data={'_csrf':'csrf'}).status_code,200);self.assertEqual(get.call_count,3)
        query.return_value=[];self.assertEqual(client.post(path,data={'_csrf':'csrf'}).status_code,404);self.assertEqual(get.call_count,3)

    def test_real_shell_explicit_refresh_option(self):
        import html
        from test_listing_details import main_function
        from visual_theme import VISUAL_CSS
        page=main_function('pagina_loja',dict(session={'tipo':'admin'},esc=html.escape,CSS='',VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:''))
        out=page('Avaliações',1,'Loja de teste','anuncios',render(1,'MLB123','Produto','csrf'),refresh=False)
        self.assertNotIn("class='k-refresh'",out);self.assertNotIn('Atualizar Anúncios',out)
        self.assertIn('/anuncios/1',out)
        self.assertIn("class='k-refresh'",page('Catálogo',1,'Loja de teste','anuncios','Catálogo'))

if __name__=='__main__':unittest.main()
