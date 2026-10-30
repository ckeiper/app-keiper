"""Recorded listing changes around the period boundary."""
import unittest
from datetime import date, timedelta
from investigation_change_context import read, render

END = date(2026,10,20)
BOUNDARY = END-timedelta(days=6)


def event(offset, source='automatic', note='Preço alterado nas coletas.', kind='preco'):
    return dict(event_date=BOUNDARY+timedelta(days=offset),source=source,
                note=note,kind=kind,created_at=1792500000+offset*3600,field='preco_final')


class ContextTests(unittest.TestCase):
    def test_detects_nearby_change_and_labels_sources(self):
        rows=[event(-2),event(0,'manual','Atualizei o título','conteudo'),event(3)]
        result=read(rows,END,sales_verified=True,declining=True)
        self.assertEqual(len(result['items']),3)
        output=render(result)
        self.assertIn('Detectada nas coletas',output)
        self.assertIn('Informada manualmente',output)
        self.assertIn('Coincidência temporal não demonstra causalidade',output)

    def test_does_not_claim_decline_when_sales_unverified(self):
        result=read([event(0)],END,sales_verified=False,declining=True)
        self.assertEqual(result['state'],'nao_verificada')
        self.assertIn('Não há queda de faturamento confirmada',render(result))

    def test_discards_out_of_range_invalid_and_void_rows_filtered_at_database(self):
        result=read([event(-4),event(4),event(-3),dict(event(0),source='unknown'),
                     dict(event(0),event_date='not a date')],END)
        self.assertEqual(result['total'],1)

    def test_caps_many_and_escapes_untrusted_notes(self):
        rows=[event(0,note='<script>unsafe</script>') for _ in range(12)]
        result=read(rows,END,sales_verified=True,declining=True)
        self.assertEqual(len(result['items']),8)
        self.assertTrue(result['truncated'])
        self.assertIn('&lt;script&gt;',render(result))
        self.assertNotIn('<script>',render(result))

    def test_no_events_does_not_claim_no_changes(self):
        self.assertIn('histórico pode estar incompleto',render(read([],END)))


if __name__=='__main__':
    unittest.main()
