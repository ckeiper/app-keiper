import unittest
import contextlib
from flask import Flask
from unittest.mock import Mock,patch
from listing_image_diagnostic import inspect,normalize,render,register
from test_listing_image_diagnostic import item,requester,poster,payload,ID,PHOTO,NOW


def listing(**changes):
    data=item(pictures=[dict(id=PHOTO),dict(id='SECOND'),dict(id='VAR')],variations=[dict(id=10,picture_ids=['VAR','SECOND'])])
    data.update(changes);return data


class ImageSelectionTests(unittest.TestCase):
    def read(self,value=None,selected=None,load=False,p=None,page=1):
        get=requester([dict(id=7),listing() if value is None else value]);post=poster(p)
        with patch('listing_image_diagnostic.uuid4',return_value=ID):
            result=inspect('token',7,'MLB123',get,post,NOW,selected_picture=selected,load_pictures=load,picture_page=page)
        return result,get,post

    def test_load_roles_without_diagnostic(self):
        result,get,post=self.read(load=True)
        self.assertEqual(result['state'],'selection');self.assertEqual(get.call_count,2);post.assert_not_called()
        self.assertEqual([p['role'] for p in result['choices']],['thumbnail','other','variation_thumbnail'])
        self.assertIn('Escolher foto do anúncio',render(1,'MLB123','Produto','csrf',result))

    def test_selected_role_is_server_verified_and_response_role_must_match(self):
        for image,role in [('SECOND','other'),('VAR','variation_thumbnail'),(PHOTO,'thumbnail')]:
            p=payload('empty');p['diagnostics'][0]['picture_type']=role
            result,get,post=self.read(selected=image,p=p)
            self.assertEqual(result['state'],'read');self.assertEqual(get.call_count,2);self.assertEqual(post.call_count,1)
            self.assertEqual(post.call_args.kwargs['json']['context']['picture_type'],role)
            self.assertEqual(post.call_args.kwargs['json']['picture_id'],image)
        result,_,_=self.read(selected='SECOND',p=payload('empty'))
        self.assertEqual(result['state'],'unknown')

    def test_missing_or_foreign_image_and_incomplete_variations_block_post(self):
        for change in (dict(variations=None),dict(variations=[dict(id=1,picture_ids=[])]),dict(variations=[dict(id=1,picture_ids=['FOREIGN'])]),dict(variations=[dict(id=1,picture_ids=['VAR'])]*2),dict(thumbnail_id='MISSING')):
            result,_,post=self.read(listing(**change),selected='SECOND')
            self.assertEqual(result['state'],'unknown');post.assert_not_called()
        for selected in ('FOREIGN','https://evil.invalid/photo','', '<script>'):
            result,_,post=self.read(selected=selected)
            self.assertEqual(result['state'],'unknown');post.assert_not_called()

    def test_owner_mismatch_never_diagnoses_or_offers_choices(self):
        result,_,post=self.read(listing(seller_id=8),load=True)
        self.assertEqual(result['state'],'unknown');self.assertNotIn('choices',result);post.assert_not_called()

    def test_selection_budget_and_zero_variations(self):
        pictures=[dict(id=PHOTO)]+[dict(id='P'+str(i)) for i in range(60)]
        value=listing(pictures=pictures,variations=[])
        result,_,_=self.read(value,load=True)
        self.assertEqual(len(result['choices']),50);self.assertEqual(result['total'],61)
        p=payload('empty');p['diagnostics'][0]['picture_type']='other'
        result,_,post=self.read(value,selected='P59',p=p);self.assertEqual(result['state'],'read');self.assertEqual(post.call_count,1)
        value=listing(variations=[dict(id=i+1,picture_ids=['VAR']) for i in range(101)])
        result,_,post=self.read(value,load=True);self.assertEqual(result['state'],'unknown');post.assert_not_called()

    def test_main_role_wins_when_shared_with_variation(self):
        value=listing(variations=[dict(id=1,picture_ids=[PHOTO,'VAR'])])
        result,_,_=self.read(value,load=True)
        self.assertEqual(result['choices'][0]['role'],'thumbnail')
        self.assertEqual(result['choices'][2]['role'],'other')

    def test_route_selection_actions_csrf_and_forged_role(self):
        app=Flask(__name__);app.secret_key='test'
        query=Mock(return_value=[dict(user_id=7,cliente='Loja',titulo='Produto')])
        get=requester([dict(id=7),listing()]);post=poster()
        register(app,lambda f:f,lambda cid:cid==1,lambda:contextlib.nullcontext(None),query,lambda *a,**kw:a[4],lambda s:'token',get,post)
        client=app.test_client();path='/anuncios/1/MLB123/imagem-principal'
        with client.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='csrf')
        self.assertEqual(client.post(path,data=dict(action='load_pictures',_csrf='bad')).status_code,400);get.assert_not_called()
        result=client.post(path,data=dict(action='load_pictures',_csrf='csrf'))
        self.assertEqual(result.status_code,200);self.assertIn('Principal de variação',result.get_data(as_text=True));post.assert_not_called()
        self.assertEqual(client.post(path,data=dict(action='diagnose_picture',_csrf='csrf')).status_code,400)
        p=payload('empty');p['diagnostics'][0]['picture_type']='other';post.return_value.json.return_value=p
        get.side_effect=requester([dict(id=7),listing()]).side_effect
        with patch('listing_image_diagnostic.uuid4',return_value=ID):
            result=client.post(path,data=dict(action='diagnose_picture',selected_picture='SECOND',picture_type='thumbnail',_csrf='csrf'))
        self.assertEqual(result.status_code,200);self.assertEqual(post.call_args.kwargs['json']['context']['picture_type'],'other')

    def test_pages_cover_all_verified_photos_with_original_positions(self):
        value=listing(pictures=[dict(id=PHOTO)]+[dict(id='P'+str(i)) for i in range(60)],variations=[])
        result,get,post=self.read(value,load=True,page=2)
        self.assertEqual((result['page'],result['pages'],result['total']),(2,2,61))
        self.assertEqual([p['position'] for p in result['choices']],list(range(51,62)))
        self.assertEqual(result['choices'][-1]['id'],'P59')
        self.assertEqual(get.call_count,2);post.assert_not_called()
        html=render(1,'MLB123','Produto','csrf',result)
        self.assertIn('Fotos 51 a 61 de 61',html);self.assertIn('Fotos anteriores',html)
        self.assertNotIn('Próximas fotos',html);self.assertNotIn(' checked',html)
        self.assertIn('name="picture_page" value="1"',html)

    def test_page_validation_and_photo_limit_never_diagnose(self):
        for page in (0,-1,21,True,'2',None):
            result,get,post=self.read(load=True,page=page)
            self.assertEqual(result['state'],'unknown');get.assert_not_called();post.assert_not_called()
        result,get,post=self.read(load=True,page=2)
        self.assertEqual(result['state'],'unknown');self.assertNotIn('choices',result);post.assert_not_called()
        pictures=[dict(id=PHOTO)]+[dict(id='P'+str(i)) for i in range(999)]
        result,_,_=self.read(listing(pictures=pictures,variations=[]),load=True,page=20)
        self.assertEqual(len(result['choices']),50);self.assertEqual(result['choices'][-1]['position'],1000)
        result,_,post=self.read(listing(pictures=pictures+[dict(id='TOO_MANY')],variations=[]),load=True)
        self.assertEqual(result['state'],'unknown');post.assert_not_called()

    def test_route_pagination_validates_input_before_external_reads(self):
        app=Flask(__name__);app.secret_key='test'
        query=Mock(return_value=[dict(user_id=7,cliente='Loja',titulo='Produto')])
        value=listing(pictures=[dict(id=PHOTO)]+[dict(id='P'+str(i)) for i in range(60)],variations=[])
        get=requester([dict(id=7),value]);post=poster()
        register(app,lambda f:f,lambda cid:cid==1,lambda:contextlib.nullcontext(None),query,lambda *a,**kw:a[4],lambda s:'token',get,post)
        client=app.test_client();path='/anuncios/1/MLB123/imagem-principal'
        with client.session_transaction() as session:session.update(tipo='admin',usuario_id=1,_csrf='csrf')
        for page in ('0','-1','21','1.5','01','99999999999999999999','<script>'):
            self.assertEqual(client.post(path,data=dict(action='load_pictures',picture_page=page,_csrf='csrf')).status_code,400)
        get.assert_not_called();post.assert_not_called()
        self.assertEqual(client.post(path,data=dict(action='load_pictures',picture_page='2',_csrf='bad')).status_code,400)
        get.assert_not_called()
        response=client.post(path,data=dict(action='load_pictures',picture_page='2',_csrf='csrf'))
        self.assertEqual(response.status_code,200);self.assertIn('Fotos 51 a 61 de 61',response.get_data(as_text=True))
        self.assertEqual(get.call_count,2);post.assert_not_called()
        get.side_effect=requester([dict(id=7),listing(variations=[])]).side_effect
        response=client.post(path,data=dict(action='diagnose_picture',selected_picture='P59',_csrf='csrf'))
        self.assertIn('não está entre as fotos disponíveis',response.get_data(as_text=True));post.assert_not_called()
