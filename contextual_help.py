"""Small reusable help control, available on hover, keyboard focus and touch."""
from html import escape

def tip(label,text):
    return '<span class="kc-help"><button type="button" aria-label="'+escape(label+': '+text,quote=True)+'">?</button><span role="tooltip">'+escape(text)+'</span></span>'

STYLE='''<style>.kc-help{display:inline-block;position:relative;margin-left:7px;vertical-align:middle;font-size:12px;font-weight:400}.kc-help button{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;padding:0;border:1px solid #7892aa;border-radius:50%;font:inherit;background:transparent;color:inherit;cursor:pointer}.kc-help [role=tooltip]{display:none;position:absolute;z-index:30;top:27px;left:0;width:260px;max-width:65vw;padding:12px;border:1px solid #7892aa;border-radius:9px;background:#142940;color:#eff5ff!important;white-space:normal;line-height:1.5;box-shadow:0 5px 18px #0004}.kc-help:hover [role=tooltip],.kc-help:focus-within [role=tooltip]{display:block}.kc-help button:focus-visible{outline:2px solid #4a9ccc;outline-offset:3px}@layer keiper-appearance{html[data-theme=light] body .kc-help [role=tooltip]{background:#142940!important;color:#eff5ff!important}}@media(max-width:600px){.kc-help [role=tooltip]{position:fixed;top:auto;bottom:16px;left:16px;right:16px;width:auto;max-width:none}}</style>'''
