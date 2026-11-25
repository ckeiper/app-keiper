import unittest
from unittest.mock import patch
from listing_catalog import filter_catalog,render_catalog,logistics

NOW=1800000000

def item(i,**kwargs):
    return dict(item_id='MLB'+str(i),titulo='Produto '+str(i),status='active',quantidade=10,preco=100,fotos=7,clips=1,vendidos=i,atualizado_em=NOW,**kwargs)


class CatalogTests(unittest.TestCase):
    def test_unknown_stock_is_not_zero_and_missing_full_is_not_other(self):
        rows=[dict(item(1),quantidade=None),dict(item(2),quantidade=0),dict(item(3),quantidade=2)]
        self.assertEqual([r['item_id'] for r in filter_catalog(rows,{'estoque':'zero'},NOW)],['MLB2'])
        self.assertEqual([r['item_id'] for r in filter_catalog(rows,{'estoque':'desconhecido'},NOW)],['MLB1'])
        self.assertEqual(len(filter_catalog(rows,{'estoque':'baixo'},NOW)),1)
        self.assertEqual(filter_catalog(rows,{'logistica':'outros'},NOW),[])
        full=dict(item(4),full_metadata_json={'collected_at':NOW,'logistics':'fulfillment'})
        self.assertEqual(logistics(full,NOW),'full')
        self.assertEqual(logistics(full,NOW+21601),'desconhecido')

    def test_combined_filters_search_sku_and_pagination_preserve_context(self):
        rows=[dict(item(i),titulo='Caneca azul',sku='SKU-A',quantidade=2) for i in range(35)]
        args={'busca':'SKU-A','status':'active','estoque':'baixo','por_pagina':'10','pagina':'2','ordem':'titulo'}
        self.assertEqual(len(filter_catalog(rows,args,NOW)),35)
        output=render_catalog(4,rows,args,now=NOW)
        self.assertEqual(output.count('<tr><td>'),10)
        self.assertIn('Página 2 de 4',output)
        self.assertIn('status=active&amp;estoque=baixo',output)
        self.assertIn('por_pagina=10&amp;pagina=3',output)
        self.assertIn('busca=SKU-A',output)

    def test_untrusted_content_escaped_and_technical_details_retained(self):
        row=dict(item(1),titulo='<img src=x onerror=alert(1)>',tags='["<script>"]',quantidade=None,preco=None,fotos=None)
        output=render_catalog(1,[row],{},now=NOW)
        self.assertNotIn('<img src=x',output)
        self.assertIn('&lt;script&gt;',output)
        self.assertIn('Estoque não verificado',output)
        self.assertIn('PACKAGE_WEIGHT',output)
        self.assertIn('SELLER_PACKAGE_WEIGHT',output)
        self.assertIn('Não corresponde ao período atual',output)
        self.assertNotIn('0/10',output)

    def test_effective_price_requires_official_recent_promotion(self):
        row=dict(item(1),promocoes_json={'sale_price':{'checked_at':NOW,'data':{'currency_id':'BRL','amount':80,'regular_amount':100,'metadata':{'promotion_id':'A'}}}})
        with patch('listing_details.time.time',return_value=NOW):
            output=render_catalog(1,[row],{},now=NOW)
            self.assertIn("catalog-price'>R$ 80,00",output)
            self.assertIn('Promoção confirmada',output)
        with patch('listing_details.time.time',return_value=NOW+8000):
            output=render_catalog(1,[row],{},now=NOW+8000)
            self.assertIn("catalog-price'>R$ 100,00",output)
            self.assertNotIn('Promoção confirmada',output)

    def test_empty_and_invalid_parameters(self):
        output=render_catalog(1,[],{'por_pagina':'100000','pagina':'NaN'},now=NOW)
        self.assertIn('Seu catálogo ainda não foi sincronizado',output)
        self.assertIn('Página 1 de 1',output)
        output=render_catalog(1,[item(1)],{'busca':'inexistente'},now=NOW)
        self.assertIn('Nenhum anúncio para estes filtros',output)

    def test_removing_one_filter_preserves_others_and_resets_page(self):
        from html import unescape
        import re
        from urllib.parse import urlsplit, parse_qs
        from listing_catalog import active_filters
        html = active_filters(7, {'busca':'<azul>','status':'active','estoque':'baixo',
            'ordem':'titulo','por_pagina':'10','pagina':'3','unexpected':'secret'})
        self.assertIn('&lt;azul&gt;', html)
        self.assertNotIn('unexpected', html)
        links = re.findall(r'href="([^"]+)" aria-label="([^"]+)"',html)
        self.assertEqual(len(links),3)
        for href,label in links:
            parsed=urlsplit(unescape(href)); args=parse_qs(parsed.query)
            self.assertEqual(parsed.path,'/anuncios/7')
            self.assertNotIn('pagina',args)
            self.assertEqual(args['ordem'],['titulo'])
            self.assertEqual(args['por_pagina'],['10'])
            if 'Status' in label:
                self.assertNotIn('status',args)
                self.assertEqual(args['estoque'],['baixo'])
                self.assertEqual(args['busca'],['<azul>'])
        self.assertEqual(active_filters(7, {'status':'invalid','ordem':'titulo'}),'')

    def test_summary_shortcuts_replace_filters_and_match_global_counts(self):
        import re
        from html import unescape
        from urllib.parse import urlsplit,parse_qs
        rows=[item(1),dict(item(2),quantidade=0,status='paused')]
        output=render_catalog(7,rows,{'busca':'missing','pagina':'3'},now=NOW)
        links=re.findall(r"<a href='([^']+)' aria-label='Ver ([^']+)' class='catalog-summary-link",output)
        self.assertEqual(len(links),4)
        counts=[]
        for href,_ in links:
            url=urlsplit(unescape(href)); self.assertEqual(url.path,'/anuncios/7')
            args={k:v[0] for k,v in parse_qs(url.query).items()}
            self.assertNotIn('busca',args); self.assertNotIn('pagina',args)
            counts.append(len(filter_catalog(rows,args,NOW)))
        self.assertEqual(counts,[2,1,1,0])
