"""Shared collapsible navigation for the directory and every store page."""
from html import escape

STYLE = """<style>
body:has(.ks-sidebar){--ks-width:236px;padding-left:var(--ks-width)}body.ks-collapsed{--ks-width:72px}
.ks-sidebar{position:fixed;inset:0 auto 0 0;width:var(--ks-width);box-sizing:border-box;z-index:30;display:flex;flex-direction:column;padding:16px 12px;background:#0d192d;border-right:1px solid #273953;color:#e9f0ff;font-family:Inter,'Segoe UI',Arial,sans-serif;overflow-y:auto;overscroll-behavior:contain}
.ks-toggle{display:flex;align-items:center;gap:12px;min-height:44px;width:100%;padding:10px;border:1px solid #365478;border-radius:10px;background:#1a2b45;color:#e9f0ff;cursor:pointer;font:inherit;font-size:13px;text-align:left;flex-shrink:0}
.ks-store-name{font-size:11px;color:#92aaca;padding:15px 10px 3px;overflow-wrap:anywhere}.ks-sidebar nav{display:grid;gap:3px;margin-top:18px}.ks-sidebar a{display:flex;align-items:center;gap:12px;min-height:41px;box-sizing:border-box;padding:9px 10px;border-radius:9px;color:#b5c9e5;text-decoration:none;font-size:12px;line-height:1.35}
.ks-sidebar a>span:first-child,.ks-toggle>span:first-child{width:20px;flex-shrink:0;text-align:center;font-size:19px}.ks-sidebar svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;vertical-align:middle}.ks-sidebar a:hover{background:#213957;color:#fff;transform:translateX(2px)}.ks-sidebar a[aria-current=page]{background:#244a80;color:#fff;box-shadow:inset 3px 0 #7caaff}
.ks-sidebar a:focus-visible,.ks-toggle:focus-visible{outline:3px solid #92bcff;outline-offset:2px}.ks-foot{margin-top:auto;padding-top:14px;border-top:1px solid #273953}.ks-sidebar .ks-danger{color:#f6abb1}.ks-foot a{font-size:11px}
.ks-collapsed .ks-label,.ks-collapsed .ks-store-name{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
#ks-navigation{display:flex;flex:1;flex-direction:column;gap:20px}.ks-store-sidebar nav{margin-top:10px}
.ks-nav-group{border:0}.ks-nav-group summary{display:flex;align-items:center;gap:12px;padding:10px;border-radius:9px;cursor:pointer;font-size:12px;list-style:none;color:#b5c9e5}.ks-nav-group summary::-webkit-details-marker{display:none}.ks-nav-group summary:focus-visible{outline:3px solid #92bcff;outline-offset:2px}.ks-nav-group summary>span:first-child{width:20px;flex-shrink:0}.ks-nav-group summary:hover,.ks-nav-group[open]>summary{color:#fff;background:#162c48}.ks-nav-group[open]>summary{font-weight:650}.ks-nav-group summary:hover{background:#213957}.ks-nav-group summary svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.ks-nav-children a[aria-current=page]{background:#244a80;color:#fff;font-weight:650}.ks-sidebar a,.ks-nav-group summary{transition:background-color .16s ease,color .16s ease,transform .16s ease}.ks-nav-group summary:hover{transform:translateX(2px)}@media(prefers-reduced-motion:reduce){.ks-sidebar a,.ks-nav-group summary{transition:none}.ks-sidebar a:hover,.ks-nav-group summary:hover{transform:none}}.ks-chevron{margin-left:auto}.ks-nav-group[open] .ks-chevron{transform:rotate(180deg)}.ks-nav-children{margin:5px 0 5px 18px;padding-left:8px;border-left:1px solid #304764}.ks-nav-children a{font-size:11px}.ks-nav-children svg{width:15px;height:15px}.ks-collapsed .ks-chevron,.ks-collapsed .ks-nav-children{display:none}.ks-mobile-toggle{display:none}
body:has(.ks-sidebar) .kh-grid{grid-template-columns:repeat(auto-fill,minmax(min(290px,100%),1fr))}
body:has(.ks-store-sidebar) .layout{display:block}body:has(.ks-store-sidebar) .layout>.conteudo{padding:0 0 24px}body:has(.ks-store-sidebar) .wrap{max-width:1480px}body:has(.ks-store-sidebar) .top{flex-wrap:wrap;gap:12px}
@media(max-width:640px){body:has(.ks-sidebar){padding-left:0}.ks-sidebar{position:sticky;top:0;width:100%;max-height:85dvh;padding:8px 12px;border-right:0;border-bottom:1px solid #273953}.ks-sidebar nav{margin-top:8px}.ks-foot{margin-top:8px;padding-top:8px}.ks-collapsed #ks-navigation{display:none}.ks-collapsed .ks-toggle .ks-label{position:static;width:auto;height:auto;margin:0;clip-path:none;overflow:visible}.ks-store-name{padding-top:8px}.ks-store-sidebar nav{grid-template-columns:repeat(2,minmax(0,1fr))}.ks-sidebar a{font-size:11px}.ks-sidebar #ks-navigation{gap:8px}}
@media print{body:has(.ks-sidebar){padding-left:0}.ks-sidebar{display:none}}
@media(max-width:640px){.ks-store-sidebar{position:fixed;inset:0 auto 0 0;width:min(280px,82vw);height:100dvh;max-height:100dvh;transform:translateX(0);z-index:1102}.ks-collapsed .ks-store-sidebar{transform:translateX(-105%)}.ks-store-sidebar nav{grid-template-columns:1fr}.ks-mobile-toggle{display:block;margin:10px 12px;padding:9px 14px;border:1px solid #365478;border-radius:9px;background:#1a2b45;color:#e9f0ff;cursor:pointer;font:inherit;font-size:12px}body:has(.ks-store-sidebar):not(.ks-collapsed):before{content:'';position:fixed;inset:0;background:#07132380;z-index:1101}.ks-store-sidebar .ks-label{position:static;width:auto;height:auto;padding:0;margin:0;overflow:visible;clip-path:none;white-space:normal}}
</style>"""

SCRIPT = """<script>(function(){
const button=document.querySelector('.ks-toggle'),buttons=[button,...document.querySelectorAll('.ks-mobile-toggle')];
function setCollapsed(value){document.body.classList.toggle('ks-collapsed',value);document.querySelector('.ks-sidebar').inert=!!document.querySelector('.ks-mobile-toggle')&&matchMedia('(max-width:640px)').matches&&value;buttons.forEach(function(b){b.setAttribute('aria-expanded',String(!value));b.setAttribute('aria-label',value?'Expandir menu':'Recolher menu');b.title=b.getAttribute('aria-label');});}
const mobile=matchMedia('(max-width:640px)');setCollapsed(mobile.matches);
mobile.addEventListener('change',function(e){setCollapsed(e.matches);});
buttons.forEach(function(b){b.addEventListener('click',function(){setCollapsed(!document.body.classList.contains('ks-collapsed'));});});
document.querySelectorAll('.ks-nav-group').forEach(function(group){group.addEventListener('toggle',function(){if(group.open)document.querySelectorAll('.ks-nav-group').forEach(function(other){if(other!==group)other.open=false;});});group.querySelector('summary').addEventListener('click',function(){if(document.body.classList.contains('ks-collapsed')&&!matchMedia('(max-width:640px)').matches)setCollapsed(false);});});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&matchMedia('(max-width:640px)').matches){if(document.querySelector('.ks-sidebar').contains(document.activeElement))(document.querySelector('.ks-mobile-toggle')||button).focus();setCollapsed(true);}});
document.addEventListener('click',function(e){if(document.querySelector('.ks-mobile-toggle')&&mobile.matches&&!document.body.classList.contains('ks-collapsed')&&!e.target.closest('.ks-sidebar,.ks-mobile-toggle')){document.querySelector('.ks-mobile-toggle').focus();setCollapsed(true);}});
})();</script>"""


def shell(navigation, footer='', store_name=None):
    from theme_switcher import SETTINGS
    footer += SETTINGS
    kind=' ks-store-sidebar' if store_name is not None else ''
    store=("<div class='ks-store-name'>"+escape(str(store_name))+"</div>") if store_name is not None else ''
    mobile="<button class='ks-mobile-toggle' type='button' aria-expanded='true' aria-controls='ks-navigation' aria-label='Recolher menu'>☰ Menu da loja</button>" if store_name is not None else ''
    return STYLE+mobile+"<aside class='ks-sidebar"+kind+"' aria-label='Menu lateral'>"+"""
<button class='ks-toggle' type='button' aria-expanded='true' aria-controls='ks-navigation' aria-label='Recolher menu' title='Recolher menu'><span aria-hidden='true'>☰</span><span class='ks-label'>Keiper Consultoria</span></button>
<div id='ks-navigation'>"""+store+"<nav class='ks-store-nav' aria-label='Navegação principal'>"+navigation+"</nav>"+footer+"</div></aside>"+SCRIPT
