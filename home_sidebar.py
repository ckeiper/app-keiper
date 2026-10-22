"""Accessible, responsive navigation for the home directory."""


def render_home_sidebar(admin=False):
    security = "<footer class='ks-foot'><a href='/seguranca' title='Segurança'><span aria-hidden='true'>◇</span><span class='ks-label'>Segurança</span></a></footer>" if admin else ""
    overview = "<a href='/painel/analise' title='Visão geral'><span aria-hidden='true'>▦</span><span class='ks-label'>Visão geral</span></a>" if admin else ""
    crm = "<a href='/crm' title='CRM'><span aria-hidden='true'>◎</span><span class='ks-label'>CRM</span></a>" if admin else ""
    return """<style>
body:has(.ks-sidebar){--ks-width:224px;padding-left:var(--ks-width)}
body.ks-collapsed{--ks-width:68px}
.ks-sidebar{position:fixed;inset:0 auto 0 0;width:var(--ks-width);box-sizing:border-box;z-index:30;display:flex;flex-direction:column;padding:18px 12px;background:#0d192d;border-right:1px solid #273953;color:#e9f0ff;font-family:Inter,'Segoe UI',Arial,sans-serif}
.ks-toggle{display:flex;align-items:center;gap:12px;min-height:44px;width:100%;padding:10px;border:1px solid #365478;border-radius:10px;background:#1a2b45;color:#e9f0ff;cursor:pointer;font:inherit}
.ks-sidebar nav{display:grid;gap:8px;margin-top:28px}.ks-sidebar a{display:flex;align-items:center;gap:12px;min-height:44px;box-sizing:border-box;padding:10px;border-radius:10px;color:#b5c9e5;text-decoration:none;font-size:14px;white-space:nowrap}
.ks-sidebar a>span:first-child,.ks-toggle>span:first-child{width:20px;flex-shrink:0;text-align:center;font-size:20px}.ks-sidebar a:hover{background:#213957;color:#fff}.ks-sidebar a[aria-current=page]{background:#244a80;color:#fff}
.ks-sidebar a:focus-visible,.ks-toggle:focus-visible{outline:3px solid #92bcff;outline-offset:2px}.ks-foot{margin-top:auto;padding-top:18px;border-top:1px solid #273953}
.ks-collapsed .ks-label{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
body:has(.ks-sidebar) .kh-grid{grid-template-columns:repeat(auto-fill,minmax(min(290px,100%),1fr))}
@media(max-width:640px){body:has(.ks-sidebar){padding-left:0}.ks-sidebar{position:sticky;top:0;width:100%;padding:8px 12px;border-right:0;border-bottom:1px solid #273953}.ks-sidebar nav{margin-top:8px}.ks-foot{margin-top:8px;padding-top:8px}.ks-collapsed .ks-sidebar nav,.ks-collapsed .ks-foot{display:none}.ks-collapsed .ks-toggle .ks-label{position:static;width:auto;height:auto;margin:0;clip-path:none;overflow:visible}}
</style><aside class='ks-sidebar' aria-label='Menu lateral'>
<button class='ks-toggle' type='button' aria-expanded='true' aria-controls='ks-navigation' aria-label='Recolher menu' title='Recolher menu'><span aria-hidden='true'>☰</span><span class='ks-label'>Keiper Consultoria</span></button>
<div id='ks-navigation' style='display:flex;flex:1;flex-direction:column'>
<nav aria-label='Navegação principal'>""" + overview + """<a href='/painel' aria-current='page' title='Minhas lojas'><span aria-hidden='true'>⌂</span><span class='ks-label'>Minhas lojas</span></a>""" + crm + "</nav>" + security + """</div></aside>
<script>(function(){
const button=document.querySelector('.ks-toggle');
function setCollapsed(value){document.body.classList.toggle('ks-collapsed',value);button.setAttribute('aria-expanded',String(!value));button.setAttribute('aria-label',value?'Expandir menu':'Recolher menu');button.title=button.getAttribute('aria-label');}
setCollapsed(matchMedia('(max-width:640px)').matches);
button.addEventListener('click',function(){setCollapsed(!document.body.classList.contains('ks-collapsed'));});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&matchMedia('(max-width:640px)').matches){if(document.querySelector('.ks-sidebar').contains(document.activeElement))button.focus();setCollapsed(true);}});
})();</script>"""
