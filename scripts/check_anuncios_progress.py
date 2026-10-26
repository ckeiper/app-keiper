"""Validate shipped progress evidence and history against its current baseline."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from anuncios_progress import read,summary
model=read();current=summary(model);last=model['historico'][-1]
if last['base']!=current['base'] or last['total']!=current['total'] or any(last['contagens'].get(state,0)!=count for state,count in current['counts'].items()):
    raise ValueError('Atualize a medição do histórico para corresponder às frentes atuais.')
if any(current['counts'].get(state,0)!=count for state,count in last['contagens'].items()):
    raise ValueError('Medição final divergente do estado atual.')
print('Registro íntegro:',current['total'],'frentes; contagens:',dict(current['counts']))
