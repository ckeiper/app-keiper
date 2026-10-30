"""Synthetic own-account consent UI rendered without database or SMTP calls."""
from catalog_preview import page,dest
from goal_notification_view import render
from test_goal_notifications import EMAIL
for mode in ['off','active','unconfigured','changed','cancelled','uncertain']:
    pref=None if mode in ('off','unconfigured') else dict(enabled=True,email=EMAIL)
    goal=dict(id=1,cancelled_at=1 if mode=='cancelled' else None)
    attempts=[dict(state='uncertain',attempted_at=1793278800)] if mode=='uncertain' else []
    html=render(7,'MLB1','stock',goal,'new@example.invalid' if mode=='changed' else EMAIL,pref,dict(rows=attempts,page=1,pages=1),'csrf',mode!='unconfigured')
    (dest/('goal-notifications-'+mode+'.html')).write_text(page('Avisos de metas',7,'Loja teste','anuncios',html))
