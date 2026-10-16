import unittest
from listing_pagination import listing_page


class ListingPaginationTests(unittest.TestCase):
    def test_default_is_twenty_and_navigation_preserves_size(self):
        rows=list(range(45))
        page,top,bottom=listing_page(rows,{},5)
        self.assertEqual(page,list(range(20)))
        self.assertIn("value='20' selected",top)
        self.assertIn('Mostrando 1–20 de 45 anúncios',top)
        self.assertIn('por_pagina=20&amp;pagina=2',bottom)
        self.assertNotIn('pagina=0',top)

    def test_last_page_and_out_of_range_page_are_clamped(self):
        page,top,bottom=listing_page(list(range(45)),dict(pagina='999'),5)
        self.assertEqual(page,list(range(40,45)))
        self.assertIn('Página 3 de 3',top)
        self.assertIn('Mostrando 41–45 de 45',top)
        self.assertNotIn('pagina=4',bottom)

    def test_quantity_and_invalid_values(self):
        for size in (10,20,50,100):
            page,top,_=listing_page(list(range(150)),dict(por_pagina=str(size)),5)
            self.assertEqual(len(page),size)
            self.assertIn(f"value='{size}' selected",top)
        for value in ('0','-5','100000','invalid',"<script>"):
            page,top,_=listing_page(list(range(45)),dict(por_pagina=value,pagina=value),5)
            self.assertLessEqual(len(page),20)
            self.assertNotIn('<script>',top)

    def test_empty_and_single_page(self):
        self.assertIn('Mostrando 0–0 de 0',listing_page([],{},5)[1])
        self.assertEqual(listing_page([1],{},5)[2],'')
