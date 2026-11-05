import unittest
from listing_image_selection import preview_url,gallery
import test_listing_image_selection as selection_tests
from test_listing_image_diagnostic import PHOTO


class ImageGalleryTests(unittest.TestCase):
    def test_only_verified_https_cdn_previews(self):
        good='https://http2.mlstatic.com/D_NQ_NP_photo-F.jpg'
        self.assertEqual(preview_url(good),good)
        for url in (None,1,'http://http2.mlstatic.com/x','https://evil.invalid/x','https://http2.mlstatic.com.evil.invalid/x','https://user@http2.mlstatic.com/x','https://http2.mlstatic.com:444/x','https://http2.mlstatic.com:bad/x','javascript:alert(1)','https://http2.mlstatic.com/x?q=1','https://http2.mlstatic.com/x#part','https://http2.mlstatic.com/\nx','https://http2.mlstatic.com/'+'x'*2049):
            self.assertIsNone(preview_url(url))

    def test_preview_metadata_reuses_existing_reads_and_id_binding(self):
        value=selection_tests.listing(pictures=[dict(id=PHOTO,secure_url='https://http2.mlstatic.com/one.jpg'),dict(id='SECOND',secure_url='https://evil.invalid/second.jpg'),dict(id='VAR')])
        result,get,post=selection_tests.ImageSelectionTests().read(value,load=True)
        self.assertEqual(get.call_count,2);post.assert_not_called()
        self.assertEqual(result['choices'][0]['preview_url'],'https://http2.mlstatic.com/one.jpg')
        self.assertIsNone(result['choices'][1]['preview_url']);self.assertIsNone(result['choices'][2]['preview_url'])

    def test_gallery_escapes_fields_requires_selection_and_keeps_fallback(self):
        html=gallery([dict(id='<script>',position=1,role='other',preview_url='https://evil.invalid/x')])
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<img',html);self.assertIn('Prévia indisponível',html)
        self.assertIn('type="radio"',html);self.assertIn(' required ',html);self.assertNotIn(' checked',html)
        html=gallery([dict(id='PIC',position=2,role='variation_thumbnail',preview_url='https://http2.mlstatic.com/photo.jpg')])
        self.assertIn('referrerpolicy="no-referrer"',html);self.assertIn('loading="lazy"',html)
        self.assertIn('Principal de variação',html);self.assertNotIn('>PIC<',html)

    def test_variation_links_include_shared_secondary_and_main_photos(self):
        value=selection_tests.listing(variations=[
            dict(id=10,picture_ids=[PHOTO,'SECOND'],attribute_combinations=[dict(name='Cor',value_name='Azul')]),
            dict(id=20,picture_ids=['VAR','SECOND'],attribute_combinations=[dict(name='Tamanho',value_name='G')])])
        result,get,post=selection_tests.ImageSelectionTests().read(value,load=True)
        rows=result['choices']
        self.assertEqual(rows[0]['role'],'thumbnail')
        self.assertEqual(rows[0]['variations'],['Variação 10 — Cor: Azul'])
        self.assertEqual(rows[1]['role'],'other')
        self.assertEqual(rows[1]['variations'],['Variação 10 — Cor: Azul','Variação 20 — Tamanho: G'])
        self.assertEqual(get.call_count,2);post.assert_not_called()
        html=gallery(rows)
        self.assertIn('Vinculada a 2 variações',html)
        self.assertIn('Vinculada a 1 variação',html)

    def test_optional_metadata_fallback_and_bounded_escaped_rendering(self):
        from listing_image_selection import variation_label
        for metadata in (None,[],[None],[dict(name='Cor')],[dict(name='Cor',value_name='x'*121)]):
            self.assertEqual(variation_label(dict(id=10,attribute_combinations=metadata)),'Variação 10')
        label=variation_label(dict(id=10,attribute_combinations=[dict(name='n'*80,value_name='x'*120)]*10))
        self.assertLessEqual(len(label),260);self.assertTrue(label.endswith('…'))
        html=gallery([dict(id='P',position=1,role='other',variations=['<script>alert(1)</script>','B','C','HIDDEN'])])
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
        self.assertIn('Vinculada a 4 variações',html);self.assertIn('Mais 1 variação vinculada.',html)
        self.assertNotIn('HIDDEN',html)
