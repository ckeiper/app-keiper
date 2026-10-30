from copy import deepcopy
import unittest
from delivery_progress import STAGES, validate, render_latest
from anuncios_progress import read, summary
from anuncios_progress_view import render


def fixture():
    return dict(versao=1, entregas=[dict(id='synthetic-content', escopo='Escopo sintético de teste',
        frentes=['conteudo-checklist'], etapa='publicada', pr=1, head_sha='c'*40, lacuna='',
        checks=[dict(nome='Sales tests', run_id=1, resultado='success', head_sha='c'*40)],
        publicacao=dict(deploy_id='dep-synthetic', commit='d'*40, status='live', horario_brasilia='2026-10-30T01:24:43-03:00'),
        atualizado_em='2026-10-30T01:24:43-03:00')])


class DeliveryProgressTests(unittest.TestCase):
    def test_seven_distinct_stages_and_no_front_count_changes(self):
        self.assertEqual(len(STAGES), 7)
        for code, label in STAGES.items():
            row = fixture()['entregas'][0]
            row['etapa'] = code
            self.assertIn(label, render_latest([row]))
        model = read()
        before = deepcopy(summary(model))
        model = deepcopy(model)
        model['entregas'] = []
        self.assertEqual(summary(model), before)
        text = render(read(), summary(read()))
        self.assertIn('Etapa da entrega', text)
        self.assertNotIn('<table', text)
        self.assertNotIn('<ul', text)
        self.assertNotIn('<a ', text)
        self.assertEqual(text.count('<rect class="ap-column"'), min(12,len({e['data'] for e in read()['historico'] if e['base']==summary(read())['base']})))

    def test_published_needs_passed_checks_for_exact_head_and_live_deploy(self):
        for mutation in ('failed', 'head', 'no_checks', 'deploy', 'commit', 'time'):
            model = fixture()
            row = model['entregas'][0]
            if mutation == 'failed': row['checks'][0]['resultado'] = 'failure'
            if mutation == 'head': row['checks'][0]['head_sha'] = 'a'*40
            if mutation == 'no_checks': row['checks'] = []
            if mutation == 'deploy': row['publicacao']['status'] = 'build_in_progress'
            if mutation == 'commit': row['publicacao']['commit'] = 'not-a-sha'
            if mutation == 'time': row['atualizado_em'] = '2026-10-29T01:24:43-03:00'
            with self.assertRaises(ValueError): validate(model, {'conteudo-checklist'})

    def test_stage_does_not_imply_completion_and_early_stages_need_no_fake_evidence(self):
        for state in ('planejada', 'em_desenvolvimento', 'aguardando_testes', 'aprovada'):
            model = fixture()
            row = model['entregas'][0]
            row.update(etapa=state)
            row.pop('publicacao')
            if state in ('planejada', 'em_desenvolvimento'):
                row.pop('pr'); row.pop('head_sha'); row.pop('checks')
            self.assertEqual(validate(model, {'conteudo-checklist'})['entregas'][0]['etapa'], state)
        model = fixture();row=model['entregas'][0];row['etapa']='concluida'
        with self.assertRaises(ValueError): validate(model, {'conteudo-checklist'})
        row['escopo_concluido'] = True
        validate(model, {'conteudo-checklist'})
        row['lacuna'] = 'Falta algo'
        with self.assertRaises(ValueError): validate(model, {'conteudo-checklist'})
        row['etapa'] = 'parcialmente_concluida'
        validate(model, {'conteudo-checklist'})

    def test_duplicate_unknown_front_timezone_and_xss(self):
        model = fixture();model['entregas'].append(deepcopy(model['entregas'][0]))
        with self.assertRaises(ValueError): validate(model, {'conteudo-checklist'})
        with self.assertRaises(ValueError): validate(fixture(), {'other'})
        model = fixture();model['entregas'][0]['atualizado_em'] = '2026-10-30T04:24:43+00:00'
        with self.assertRaises(ValueError): validate(model, {'conteudo-checklist'})
        row = fixture()['entregas'][0];row['escopo']='<script>"'
        text = render_latest([row])
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)
