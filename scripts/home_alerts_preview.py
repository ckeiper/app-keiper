"""Synthetic fixtures for landing-page refresh browser verification."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client_home import render_client_home

Path('visual-qa').mkdir(exist_ok=True)
Path('visual-qa/home-alerts.html').write_text(
    '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alertas Keiper</title>'
    + render_client_home([dict(id=1, cliente='Loja Exemplo', status='ativa'),
                          dict(id=2, cliente='Outra Loja', status='ativa')])+'</html>', encoding='utf-8')
