from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock,patch
from attribute_review_recovery import eligible,recover
from test_attribute_completion import facts


def parent():
 return dict(id='parent',conexao_id=1,item_id='MLB123',created_by=42,state='rejected',result=dict(conditional=dict(state='review',allow_send=False)),data=dict(manual_actor=42,manual_inputs=[dict(id='MATERIAL',value='Aço',note='Fabricante')]))

class RecoveryTests(TestCase):
 def run_recovery(self,p=None,f=None,active=None):
  self.create=Mock(return_value=(dict(id='child'),True));self.transition=Mock();self.read=Mock(return_value=f or facts());self.token=Mock(return_value='secret')
  with patch('attribute_review_recovery.store.by_key',return_value=None),patch('attribute_review_recovery.store.active',return_value=active or []),patch('attribute_review_recovery.store.create',self.create),patch('attribute_review_recovery.store.transition',self.transition),patch('attribute_review_recovery.gather',self.read):
   return recover(None,Mock(),1,'MLB123',42,p or parent(),'k'*24,dict(status='ativa',user_id=123),self.token,Mock())
 def test_fresh_read_new_draft_no_mutation_and_no_automatic_selection(self):
  p=parent();before=deepcopy(p);self.run_recovery(p)
  self.read.assert_called_once();d=self.transition.call_args_list[0].kwargs['data']
  self.assertEqual(d['manual_inputs'],p['data']['manual_inputs']);self.assertEqual(d['manual_actor'],42)
  self.assertNotIn('selected',self.transition.call_args_list[0].kwargs);self.assertEqual(p,before)
  self.assertEqual(self.transition.call_args_list[-1].args[4],'stale')
 def test_uncertain_sending_confirmed_closed_or_unproven_rejection_never_read(self):
  for state in ['sending','uncertain','confirmed','closed','ready']:
   p=parent();p['state']=state
   with self.assertRaises(ValueError):self.run_recovery(p)
   self.read.assert_not_called()
  p=parent();p['result']={}
  self.assertFalse(eligible(p))
 def test_foreign_actor_scope_and_pending_writes_stop_before_token(self):
  for key,value in [('created_by',43),('conexao_id',2),('item_id','MLB999')]:
   p=parent();p[key]=value
   with self.assertRaises(ValueError):self.run_recovery(p)
   self.token.assert_not_called()
  with self.assertRaises(ValueError):self.run_recovery(active=[dict(id='pending')])
  self.token.assert_not_called()
 def test_newly_filled_fields_are_not_overwritten_or_reproposed(self):
  f=facts();f['item']['attributes']=[dict(id='MATERIAL',value_name='Plástico')]
  self.run_recovery(f=f);call=self.transition.call_args_list[0]
  self.assertEqual(call.kwargs['data']['manual_inputs'],[]);self.assertEqual(call.args[5]['recovery']['omitted'],['MATERIAL'])
 def test_new_rules_are_applied_to_retained_data(self):
  f=facts();f['rules']['MATERIAL']['value_max_length']=2
  with self.assertRaises(ValueError):self.run_recovery(f=f)
  self.create.assert_not_called()
 def test_replayed_key_returns_same_child_without_network(self):
  p=parent();p['state']='stale';child=dict(data=dict(recovery_request=dict(parent_plan='parent')))
  with patch('attribute_review_recovery.store.by_key',return_value=child),patch('attribute_review_recovery.gather') as read:
   result=recover(None,Mock(),1,'MLB123',42,p,'k'*24,{},Mock(),Mock())
  self.assertIs(result,child);read.assert_not_called()
