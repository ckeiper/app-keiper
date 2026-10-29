import contextlib,os,unittest
from unittest.mock import Mock,patch
from datetime import date
from flask import Flask
from goal_notifications import email_valid,save,parent,dispatch,claim,send_smtp
from goal_notification_routes import register,history
from goal_notification_view import render
EMAIL='admin@example.invalid'
class GoalNotificationTests(unittest.TestCase):
 def test_email_validation_blocks_header_injection(self):
    self.assertTrue(email_valid(EMAIL))
    for email in [None,'','bad','a@x','a@b.com\nBcc: other@b.com','a@b.com\r','x'*255+'@x.com','á@x.com']:self.assertFalse(email_valid(email))
 def test_opt_in_own_address_and_cancelled_goal(self):
    q=Mock(side_effect=[[dict(id=1,cancelled_at=None)],[dict(email=EMAIL)],[dict(id=2)]])
    save(None,q,7,'MLB1','stock',1,9,dict(enabled='yes',confirmed_email=EMAIL),100)
    self.assertEqual(q.call_args.args[2],('stock',1,7,'MLB1',9,EMAIL,100,100))
    for email,form,goal in [(EMAIL,dict(enabled='yes',confirmed_email='other@x.com'),{}),(None,dict(enabled='yes'),{}),(EMAIL,dict(enabled='yes',confirmed_email=EMAIL),dict(cancelled_at=1))]:
        with self.assertRaises(ValueError):save(None,Mock(side_effect=[[goal],[dict(email=email)]]),7,'MLB1','stock',1,9,form,100)
    q=Mock(side_effect=[[{}],[dict(email=None)],[]]);save(None,q,7,'MLB1','sales',1,9,{},100);self.assertIn('enabled=FALSE',q.call_args.args[1])
    with self.assertRaises(LookupError):parent(None,Mock(),7,'MLB1','injected',1)
 def test_dispatch_without_smtp_does_nothing(self):
    q=Mock();sender=Mock();self.assertEqual(dispatch(Mock(),q,Mock(),100,sender,lambda:False),0);q.assert_not_called();sender.assert_not_called()
 def test_dispatch_claim_commit_before_smtp_and_uncertainty(self):
    row=dict(kind='stock',email=EMAIL,item_id='MLB1',observed=0,target=5,evaluated_at=100,notification_id=1)
    bank=Mock(side_effect=lambda:contextlib.nullcontext(None));e=Mock();sender=Mock(return_value=False)
    with patch('goal_notifications.claim',side_effect=[row,None,None]):self.assertEqual(dispatch(bank,Mock(),e,101,sender,lambda:True),1)
    self.assertEqual(e.call_args.args[2],('uncertain',101,1));self.assertEqual(sender.call_count,1)
    self.assertIn('0 unidades',sender.call_args.args[2])
    with patch('goal_notifications.claim',side_effect=[row,None,None]):
        dispatch(bank,Mock(),e,101,Mock(side_effect=TimeoutError),lambda:True)
    self.assertEqual(e.call_args.args[2][0],'uncertain')
 def test_claim_scope_freshness_concurrency_and_daily_dedup(self):
    q=Mock(return_value=[]);self.assertIsNone(claim(None,q,'stock',100000,date(2026,10,29)))
    sql=q.call_args.args[1]
    for required in ['SKIP LOCKED','u.email=s.email',"c.status='ativa'",'g.cancelled_at IS NULL',"o.state='alert'",'o.evaluated_at>s.enabled_at','a.atualizado_em=o.source_at','notification_day=%s']:self.assertIn(required,sql)
    q=Mock(side_effect=[[dict(email=EMAIL,subscription_id=3,observation_id=5,item_id='MLB1')],[dict(id=9)]])
    self.assertEqual(claim(None,q,'sales',100000,date(2026,10,29))['notification_id'],9);self.assertIn('ON CONFLICT',q.call_args.args[1])
 def test_smtp_tls_timeout_acceptance_and_no_retry(self):
    with patch.dict(os.environ,dict(SMTP_HOST='smtp.example.invalid',SMTP_USER=EMAIL,SMTP_PASS='synthetic',SMTP_PORT='587'),clear=True),patch('goal_notifications.smtplib.SMTP') as smtp:
        smtp.return_value.__enter__.return_value.sendmail.return_value={}
        self.assertTrue(send_smtp(EMAIL,'Subject','Body'));self.assertEqual(smtp.call_args.kwargs['timeout'],15)
        smtp.return_value.__enter__.return_value.starttls.assert_called_once()
        smtp.return_value.__enter__.return_value.sendmail.side_effect=TimeoutError
        self.assertFalse(send_smtp(EMAIL,'Subject','Body'));self.assertEqual(smtp.return_value.__enter__.return_value.sendmail.call_count,2)
 def test_ui_default_off_escape_history_status(self):
    text=render(7,'MLB1','stock',dict(id=1),EMAIL,None,dict(rows=[],page=1,pages=1),'token',False)
    self.assertNotIn(' checked',text);self.assertIn('Desativados',text);self.assertIn('SMTP ainda não configurado',text)
    q=Mock(side_effect=[[dict(n=23)],[]]);self.assertEqual(history(None,q,1,dict(pagina='999'))['page'],3);self.assertEqual(q.call_args.args[2],(1,20))
 def test_route_admin_store_csrf_and_readonly(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1],ready=lambda:False)
    c=app.test_client();path='/anuncios/7/MLB1/metas/avisos/stock/1'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin',usuario_id=9,_csrf='token')
    self.assertEqual(c.get(path.replace('/7/','/8/')).status_code,403)
    self.assertEqual(c.post(path,data={}).status_code,400);q.assert_not_called()
    q.side_effect=[[dict(cliente='Loja')],[dict(id=1)],[dict(email=EMAIL)],[]]
    self.assertEqual(c.get(path).status_code,200);self.assertEqual(e.call_count,1);self.assertIn('READ ONLY',e.call_args.args[1])
