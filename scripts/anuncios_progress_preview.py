"""Preview the real chart and a labeled synthetic multi-release state."""
import sys,html,json
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import dest,env
from test_listing_details import main_function
from anuncios_progress import read,summary
from anuncios_progress_view import render
from anuncios_progress_routes import refresh_script,revision
page=main_function('pagina',env)
for name in ('current','history'):
    data=deepcopy(read())
    if name=='history':
        row=next(r for r in data['capacidades'] if r['estado']=='parcial');row.update(estado='concluida',falta='')
        model=summary(data)
        data['historico'].append(dict(base=model['base'],data='2026-10-26',resumo='Dados fictícios de evolução para teste',contagens=dict(model['counts']),total=model['total'],prs=[]))
    body=render(data,summary(data))+refresh_script(revision(data))
    if name=='history':(dest/'anuncios-progress-refresh.json').write_text(json.dumps(dict(revision='synthetic-history',html=render(data,summary(data)))),encoding='utf-8')
    if name=='history':body='<p>Dados fictícios para teste.</p>'+body
    (dest/('anuncios-progress-'+name+'.html')).write_text(page('Evolução de Anúncios',body),encoding='utf-8')
print('Progress chart previews rendered.')
