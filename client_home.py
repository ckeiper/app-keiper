"""Fast, database-light client directory for the landing page."""
from html import escape


def render_client_home(shops, admin=False):
    """Render only already authorized shops; no order, visit or Ads reads."""
    cards = []
    for shop in shops:
        cid = int(shop["id"])
        name = escape(str(shop.get("cliente") or "Loja sem nome"))
        status = str(shop.get("status") or "").lower()
        active = status == "ativa"
        label = "Ativa" if active else (escape(status.capitalize()) or "Sem status")
        cards.append(
            "<article class='kh-store' data-id='" + str(cid) + "'>"
            "<a class='kh-store-main' href='/painel/" + str(cid) + "'>"
            "<span class='kh-store-icon' aria-hidden='true'>▣</span>"
            "<span class='kh-store-copy'><strong class='kh-store-name'><span class='kh-trend' aria-label='Tendência indisponível' title='Comparando os últimos sete dias'></span>" + name + "</strong>"
            "<span class='kh-status " + ("kh-active" if active else "kh-inactive") + "'>"
            "<span aria-hidden='true'>●</span> " + label + "</span></span>"
            "</a><button type='button' class='kh-more' aria-label='Opções de " + name + "' aria-expanded='false'>⋯</button>"
            "<div class='kh-menu' hidden><button type='button' data-act='rename'>Renomear</button>"
            "<button type='button' data-act='up'>Mover para cima</button>"
            "<button type='button' data-act='down'>Mover para baixo</button>"
            "<a href='/excluir/" + str(cid) + "' class='kh-danger'>Excluir loja…</a></div></article>"
        )
    actions = ""  # The global page header already contains Conectar loja.
    management = ("<nav class='kh-links' aria-label='Administração'>"
                  "<a href='/crm'>CRM e leads</a><a href='/usuarios'>Usuários</a>"
                  "<a href='/diagnostico'>Diagnóstico</a>"
                  "<a href='/painel/analise'>Relatórios consolidados</a></nav>"
                  if admin else "")
    empty = ("<div class='kh-empty'>Nenhuma loja disponível. "
             + ("Conecte a primeira loja para começar." if admin else "Contate o administrador.")
             + "</div>") if not cards else ""
    return """<style>
.kh-home{max-width:1180px;margin:12px auto 52px;padding:0 24px;color:#17243b}
.kh-head{display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:26px}
.kh-eyebrow{color:#6685bd;font-size:12px;font-weight:800;letter-spacing:1.7px;text-transform:uppercase}
.kh-home h2{font-size:clamp(26px,4vw,36px);margin:7px 0;color:#17243b}
.kh-description{font-size:14px;color:#69788e;margin:0}
.kh-action{background:#2563eb;border-radius:12px;color:white;text-decoration:none;padding:12px 17px;font-size:14px;font-weight:700}
.kh-toolbar{display:flex;gap:12px;align-items:center;margin-bottom:20px}
.kh-search{padding:15px 18px;border:1px solid #dfe6f0;border-radius:13px;background:#fff;max-width:520px;width:100%;font-size:15px;outline-offset:3px}
.kh-count{font-size:13px;color:#738098;white-space:nowrap}
.kh-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(245px,1fr));gap:15px}
.kh-store{position:relative;display:flex;align-items:center;color:inherit;background:white;border:1px solid #e2e9f2;border-radius:16px;box-shadow:0 4px 14px rgba(24,52,90,.035);transition:transform .15s,border-color .15s,box-shadow .15s;min-width:0}.kh-store-main{display:flex;align-items:center;gap:13px;padding:21px 14px;flex:1;min-width:0;color:inherit;text-decoration:none}
.kh-store:hover,.kh-store:focus-visible{transform:translateY(-2px);border-color:#6395eb;box-shadow:0 9px 25px rgba(32,76,155,.10)}
.kh-store-icon{display:grid;place-items:center;border-radius:12px;background:#edf4ff;color:#2563eb;font-size:25px;width:48px;height:48px;flex-shrink:0}
.kh-store-copy{display:flex;flex-direction:column;min-width:0;gap:6px;flex:1}
.kh-store-name{font-size:15px;overflow-wrap:anywhere;display:flex;align-items:center;gap:6px}.kh-trend{font-size:14px;line-height:1;min-width:12px}.kh-trend.up{color:#168657}.kh-trend.down{color:#d5424a}.kh-trend.flat{color:#8390a5}
.kh-more{border:0;background:transparent;color:#77849b;font-size:24px;cursor:pointer;align-self:flex-start;margin:9px 9px 0 0;padding:3px 9px;border-radius:8px}.kh-more:hover,.kh-more:focus-visible{background:#edf3fc;color:#1f3656}.kh-menu{position:absolute;right:8px;top:47px;z-index:10;background:#fff;border:1px solid #dbe5f1;border-radius:12px;box-shadow:0 12px 30px #12274424;padding:5px;min-width:165px}.kh-menu[hidden]{display:none}.kh-menu button,.kh-menu a{width:100%;box-sizing:border-box;display:block;text-align:left;background:transparent;border:0;padding:10px;border-radius:7px;color:#243854;font:inherit;font-size:13px;text-decoration:none;cursor:pointer}.kh-menu button:hover,.kh-menu a:hover{background:#edf3fc}.kh-menu .kh-danger{color:#b52c3b}
.kh-status{font-size:12px;color:#7b8696}
.kh-active{color:#17805a}
.kh-inactive{color:#c07824}
.kh-arrow{font-size:22px;color:#8da0b9}
.kh-links{display:flex;gap:8px 20px;flex-wrap:wrap;border-top:1px solid #e2e9f2;margin-top:28px;padding-top:22px}
.kh-links a{color:#5171a1;text-decoration:none;font-size:13px;font-weight:600}
.kh-links a:hover{text-decoration:underline}
.kh-empty{padding:35px;background:white;border:1px dashed #d6e1f0;border-radius:16px;color:#69788e}
@media(max-width:640px){.kh-home{padding:0 14px}.kh-grid{grid-template-columns:1fr}.kh-head{align-items:flex-start}.kh-toolbar{flex-wrap:wrap}}
</style><main class='kh-home'>
<section class='kh-head'><div><div class='kh-eyebrow'>Keiper · Workspace</div>
<h2>Suas lojas</h2><p class='kh-description'>Escolha um cliente para abrir seu painel.</p></div>""" + actions + """</section>
<div class='kh-toolbar'><input id='kh-search' class='kh-search' type='search'
placeholder='Buscar loja ou cliente...' aria-label='Buscar lojas' autocomplete='off'>
<span class='kh-count' id='kh-count'></span></div>
<section id='kh-grid' class='kh-grid' aria-label='Lojas conectadas'>""" + "".join(cards) + """</section>""" + empty + management + """</main>
<script>
(function(){
const input=document.getElementById('kh-search');
const cards=[...document.querySelectorAll('#kh-grid .kh-store')];
const count=document.getElementById('kh-count');
const grid=document.getElementById('kh-grid');
const key='keiper:client-card-order:v1';
try{const order=JSON.parse(localStorage.getItem(key)||'[]');order.forEach(id=>{const card=cards.find(c=>c.dataset.id===String(id));if(card)grid.appendChild(card);});}catch(e){}
function saveOrder(){try{localStorage.setItem(key,JSON.stringify([...grid.children].map(c=>c.dataset.id)));}catch(e){}}
function closeMenus(){document.querySelectorAll('.kh-menu').forEach(m=>m.hidden=true);document.querySelectorAll('.kh-more').forEach(b=>b.setAttribute('aria-expanded','false'));}
grid.addEventListener('click',async e=>{
 const trigger=e.target.closest('.kh-more');
 if(trigger){const menu=trigger.nextElementSibling,opening=menu.hidden;closeMenus();menu.hidden=!opening;trigger.setAttribute('aria-expanded',String(opening));return;}
 const btn=e.target.closest('[data-act]');if(!btn)return;
 const card=btn.closest('.kh-store'),id=card.dataset.id,act=btn.dataset.act;
 closeMenus();
 if(act==='up'&&card.previousElementSibling)grid.insertBefore(card,card.previousElementSibling);
 if(act==='down'&&card.nextElementSibling)grid.insertBefore(card.nextElementSibling,card);
 if(act==='up'||act==='down'){saveOrder();refresh();return;}
 if(act==='rename'){
  const label=card.querySelector('.kh-store-name');
  const old=label.textContent.trim();
  const name=prompt('Novo nome da loja:',old);
  if(name===null||!name.trim()||name.trim()===old)return;
  try{const response=await fetch('/renomear/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({cliente:name.trim()})});const data=await response.json();if(!response.ok||!data.ok)throw Error('Falha ao renomear');label.lastChild.textContent=name.trim();refresh();}catch(err){alert('Não foi possível renomear esta loja.');}
 }
});
document.addEventListener('click',e=>{if(!e.target.closest('.kh-more,.kh-menu'))closeMenus();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenus();});
fetch('/painel/tendencias',{credentials:'same-origin'}).then(r=>{if(!r.ok)throw Error('indisponível');return r.json();}).then(d=>{
 for(const card of cards){const trend=d[String(card.dataset.id)];if(!trend)continue;
 const span=card.querySelector('.kh-trend');span.className='kh-trend '+trend;span.textContent=trend==='up'?'▲':trend==='down'?'▼':'—';
 const label=trend==='up'?'Faturamento subiu':trend==='down'?'Faturamento caiu':'Faturamento estável';
 span.title=label+' nos últimos 7 dias, comparados aos 7 anteriores';span.setAttribute('aria-label',label);
 }
}).catch(()=>{});
function refresh(){
 const q=input.value.trim().toLocaleLowerCase('pt-BR');
 let visible=0;
 for(const card of cards){
  const show=card.querySelector('.kh-store-name').textContent.toLocaleLowerCase('pt-BR').includes(q);
  card.hidden=!show;card.style.display=show?'':'none';
  if(show)visible++;
 }
 count.textContent=visible+' '+(visible===1?'loja':'lojas');
}
input.addEventListener('input',refresh);refresh();
})();
</script>"""
