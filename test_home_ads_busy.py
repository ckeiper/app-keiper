"""Execute the actual home refresh JS against busy/success/failure responses."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from client_home import render_client_home


@unittest.skipUnless(shutil.which('node'), 'Node.js required for home JavaScript regression')
class HomeAdsBusyTests(unittest.TestCase):
    def run_refresh(self, status):
        page = render_client_home([{'id': 5, 'cliente': 'Copas Ind', 'status': 'ativa'}])
        source = page[page.index('async function refreshAds'):page.index('async function loadCard')]
        script = """
const today='2026-10-30';const pause=async()=>{};let calls=0;
const fetch=async()=>({ok:true,json:async()=>++calls===1?{id:'job'}:{id:'job',status:STATUS}});
SOURCE
refreshAds(5).then(s=>console.log(s.status)).catch(e=>{console.error(e.message);process.exitCode=1});
""".replace('STATUS', json.dumps(status)).replace('SOURCE', source)
        return subprocess.run(['node', '-e', script], capture_output=True, text=True)

    def test_busy_preserves_available_data_instead_of_throwing(self):
        result = self.run_refresh('ocupada')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ocupada')
        page = render_client_home([])
        self.assertIn("states.set(card,'busy')", page)
        self.assertIn('Coleta da loja em andamento · dados disponíveis', page)
        self.assertIn("state==='busy'", page)

    def test_success_still_completes(self):
        result = self.run_refresh('concluida')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'concluida')

    def test_real_failure_is_not_hidden(self):
        result = self.run_refresh('falhou')
        self.assertEqual(result.returncode, 1)
        self.assertIn('failed', result.stderr)
