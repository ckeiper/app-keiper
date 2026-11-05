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
