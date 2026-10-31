import unittest
from copy import deepcopy
from content_action_summary import actions, render


def snapshot(rows=None):
    return dict(requirements=dict(state='read', rows=rows or [], total=len(rows or [])),
                attribute_units=dict(state='read', rows=[]), boolean_values=dict(state='read', rows=[]), list_values=dict(state='read', rows=[]), number_values=dict(state='read', rows=[]))


class ActionSummaryTests(unittest.TestCase):
    def test_required_and_conditional_do_not_share_verdict(self):
        data = snapshot([dict(name='Marca', state='review', required=True),
                         dict(name='Modelo', state='review', conditional=True),
                         dict(name='Cor', state='review', conditional_confirmed=True)])
        before = deepcopy(data)
        self.assertEqual([r[0] for r in actions(data)], ['review', 'unknown', 'review'])
        self.assertIn('aplicabilidade', actions(data)[1][2])
        self.assertEqual(data, before)

    def test_unknown_is_never_absence_or_success(self):
        data = snapshot([dict(name='Marca', state='unknown', required=True)])
        data['boolean_values'] = dict(state='unknown')
        self.assertTrue(all(r[0] == 'unknown' for r in actions(data)))
        self.assertIn('0 pontos para conferir', render(data))
        self.assertNotIn('Nenhum apontamento', render(data))

    def test_managed_variation_limits_and_escaping(self):
        data = snapshot()
        data['boolean_values'] = dict(state='read', variation_unknown=True, truncated=True,
            rows=[dict(name='<script>', location='<img>', state='review', managed=True)])
        result = render(data)
        self.assertIn('sem recomendar edição direta', result)
        self.assertIn('cobertura', result)
        self.assertNotIn('<script>', result)
        self.assertNotIn('<img>', result)
        self.assertEqual(len(actions(data)), 2)

    def test_empty_and_truncated_do_not_certify_completeness(self):
        self.assertIn('não certifica', render(snapshot()))
        data = snapshot([dict(name=str(i), state='review', required=True) for i in range(110)])
        result = render(data)
        self.assertEqual(result.count('<li '), 100)
        self.assertIn('100 de 110', result)
        data['requirements']['total'] = 111
        self.assertEqual(actions(data)[0][0], 'unknown')

    def test_lengths_and_value_findings_are_not_lost(self):
        data = snapshot([dict(name='Marca', state='informed', length_findings=[{}])])
        data['attribute_units']['rows'] = [dict(name='Peso', state='review', location='Variação 1')]
        self.assertEqual(len(actions(data)), 2)
        self.assertIn('Variação 1', render(data))
