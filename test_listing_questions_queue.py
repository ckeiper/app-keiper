"""Fresh unanswered queue excludes stale/foreign/hidden evidence and orders by creation."""
import unittest
from datetime import datetime,timezone,timedelta
from listing_questions import model,render,waiting_seconds,waiting_label
from question_sync import FRESH_SECONDS
import test_listing_questions as fixtures

NOW=1793880000

def question(i,age=3600,**changes):
    row=fixtures.row(i,data=datetime.fromtimestamp(NOW-age,timezone.utc).isoformat(),
        consulta_estado='read',status_confirmado_em=NOW,vendedor_confirmado='7',
        excluida_do_anuncio=False,em_espera=False)
    row.update(changes)
    return row


class QueueTests(unittest.TestCase):
    def test_queue_requires_current_seller_status_and_visibility(self):
        rows=[question(1),question(2,status_confirmado_em=NOW-FRESH_SECONDS),
            question(3,status_confirmado_em=NOW-FRESH_SECONDS-1),question(4,status_confirmado_em=NOW+1),
            question(5,vendedor_confirmado='8'),question(6,consulta_estado='unknown'),
            question(7,excluida_do_anuncio=True),question(8,em_espera=True),
            question(9,em_espera=None),question(10,excluida_do_anuncio=None),
            question(11,status='ANSWERED'),question(12,status='BANNED'),question(13,status='DELETED')]
        data=model(rows,dict(status='pending'),NOW,7)
        self.assertEqual([r['pergunta_id'] for r in data['rows']],['1','2'])
        self.assertEqual(data['pending'],data['filtered'])
        self.assertEqual(model(rows,dict(status='pending'),NOW,None)['filtered'],0)
        self.assertEqual(model(rows,dict(status='UNANSWERED'),NOW,7)['filtered'],10)

    def test_creation_order_unknown_last_paging_and_input_unchanged(self):
        rows=[question(i,age=i*3600,atualizado_em=NOW+i) for i in range(1,14)]
        rows.extend([question(14,data='bad'),question(15,data='2026-11-01T00:00:00'),question(16,age=-60)])
        data=model(rows,dict(status='pending'),NOW,7)
        self.assertEqual([r['pergunta_id'] for r in data['rows']],[str(i) for i in range(13,3,-1)])
        data=model(rows,dict(status='pending',pagina='2'),NOW,7)
        self.assertEqual([r['pergunta_id'] for r in data['rows']],['3','2','1','14','15','16'])
        self.assertEqual(rows[0]['pergunta_id'],'1')
        text=render(7,'MLB1',{},data)
        self.assertIn('status=pending&amp;pagina=1',text)
        self.assertIn('Tempo de espera não verificado',text)
        self.assertIn('Mais antigas primeiro',text)
        self.assertIn('class="lq-card-link"',text)

    def test_elapsed_dates_offsets_boundaries_and_invalids(self):
        for age,label in [(0,'menos de 1 min'),(59,'menos de 1 min'),(60,'1 min'),
            (3599,'59 min'),(3600,'1 h'),(3660,'1 h 1 min'),(86400,'1 d'),(90000,'1 d 1 h')]:
            with self.subTest(age=age):
                self.assertEqual(waiting_seconds(question(1,age),NOW),age)
                self.assertIn(label,waiting_label(age))
        instant=datetime.fromtimestamp(NOW-3600,timezone(timedelta(hours=-3))).isoformat()
        self.assertEqual(waiting_seconds(question(1,data=instant),NOW),3600)
        for value in [None,True,{},'invalid','2026-01-01','2026-01-01T12:00:00','9999-99-99T00:00:00Z']:
            self.assertIsNone(waiting_seconds(question(1,data=value),NOW))
        self.assertIsNone(waiting_seconds(question(1,age=-1),NOW))

    def test_elapsed_not_shown_for_old_or_hidden_records_and_empty_is_bounded(self):
        data=model([question(1,status_confirmado_em=NOW-FRESH_SECONDS-1),question(2,em_espera=True)],{},NOW,7)
        self.assertNotIn('class="lq-wait"',render(7,'MLB1',{},data))
        text=render(7,'MLB1',{},model([],dict(status='pending'),NOW,7))
        self.assertIn('confirmada nesta amostra',text)
        self.assertNotIn('Aguardando há',text)
        rows=[question(i) for i in range(1001)]
        data=model(rows,dict(status='pending'),NOW,7)
        self.assertTrue(data['limited']);self.assertEqual(data['filtered'],1000)

    def test_recurrence_links_distinguish_saved_status_and_confirmed_queue(self):
        rows=[question(1,texto='Serve em 220 V?'),question(2,texto=' SERVE  em 220 v? ',em_espera=True),
              question(3,texto='Serve em 220 V? também',resposta='Serve em 220 V?'),
              question(4,texto='Serve em 220 V?',status='ANSWERED'),
              question(5,texto='Serve em 220 V?',vendedor_confirmado='8')]
        data=model(rows,dict(grupo='4'),NOW,7)
        self.assertEqual([r['pergunta_id'] for r in data['rows']],['1','2','4','5'])
        self.assertEqual(data['group']['pending'],3)
        self.assertEqual(data['group']['confirmed'],1)
        text=render(7,'MLB1',{},data)
        self.assertIn('grupo=1&amp;recorrencias=1&amp;status=pending#perguntas',text)
        self.assertIn('name="grupo" value="1"',text)
        data=model(rows,dict(grupo='1',status='pending'),NOW,7)
        self.assertEqual([r['pergunta_id'] for r in data['rows']],['1'])
        self.assertEqual(model(rows,dict(grupo='1',q='também'),NOW,7)['filtered'],0)
        for qid in ['3','999']:
            data=model(rows,dict(grupo=qid),NOW,7)
            self.assertTrue(data['group_unavailable'])
            self.assertEqual(data['filtered'],0)
