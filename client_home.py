"""Fast, database-light client directory for the landing page."""
from html import escape


def render_client_home(shops, admin=False):
    """Render only already authorized shops; no order, visit or Ads reads."""
    cards = []
    for shop in sorted(shops, key=lambda s: str(s.get("cliente") or "").casefold()):
        cid = int(shop["id"])
        name = escape(str(shop.get("cliente") or "Loja sem nome"))
        status = str(shop.get("status") or "").lower()
        active = status == "ativa"
        label = "Ativa" if active else (escape(status.capitalize()) or "Sem status")
        cards.append(
            "<article class='kh-store' data-id='" + str(cid) + "'>"
            "<a class='kh-store-main' href='/painel/" + str(cid) + "'>"
            "<span class='kh-store-icon' aria-hidden='true'><svg width='23' height='23' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><path d='M3 10h18l-1.3-5H4.3L3 10Z'/><path d='M5 10v9h14v-9M9 19v-6h6v6M3 10c0 2 3 2 4.5 0 1.5 2 3.5 2 4.5 0 1.5 2 3.5 2 4.5 0 1.5 2 4.5 2 4.5 0'/></svg></span>"
            "<span class='kh-store-copy'><strong class='kh-store-name'><span class='kh-trend' aria-label='Tendência indisponível' title='Comparando os últimos sete dias'></span><span class='kh-client-label'>" + name + "</span></strong>"
            "<span class='kh-status " + ("kh-active" if active else "kh-inactive") + "'>"
            "<span aria-hidden='true'>●</span> " + label + "</span></span>"
            "</a><button type='button' class='kh-more' aria-label='Opções de " + name + "' aria-expanded='false'>⋯</button>"
            "<div class='kh-menu' hidden><button type='button' data-act='rename'>Renomear</button>"
            "<a href='/excluir/" + str(cid) + "' class='kh-danger'>Excluir loja…</a></div>"
            "<div class='kh-card-bottom'><div class='kh-metric'>" 
            "<span class='kh-metric-label'>FATURAMENTO · ÚLTIMOS 7 DIAS</span>"
            "<span class='kh-metric-value' aria-live='polite'>Tendência indisponível</span></div>"
            "<span class='kh-card-go' aria-hidden='true'>Abrir painel <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='m9 18 6-6-6-6'/></svg></span>"
            "</div></article>"
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
.kh-home{max-width:1240px;margin:4px auto 56px;padding:0 28px;color:#16243b;font-family:Inter,'Segoe UI',Arial,sans-serif}
.kh-head{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;flex-wrap:wrap;margin:0 0 28px;padding:8px 0 20px;border-bottom:1px solid #e4eaf3}
.kh-eyebrow{color:#5479bd;font-size:11px;font-weight:800;letter-spacing:2px;text-transform:uppercase}
.kh-home h2{font-size:clamp(30px,4vw,40px);line-height:1.15;letter-spacing:-1.35px;margin:9px 0 8px;font-weight:800;color:#172947}
.kh-description{font-size:14px;color:#74839b;margin:0;line-height:1.5}
.kh-toolbar{display:flex;gap:16px;align-items:center;margin-bottom:22px;justify-content:space-between;flex-wrap:wrap}
.kh-search{padding:15px 18px 15px 44px;border:1px solid #dbe4f1;border-radius:13px;background:#fff;max-width:440px;width:100%;font-size:14px;outline-offset:3px;box-shadow:0 3px 10px #162b4a06;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' fill='none' stroke='%238297b4' stroke-width='1.7' viewBox='0 0 24 24'%3E%3Ccircle cx='10.8' cy='10.8' r='6.8'/%3E%3Cpath d='m16 16 5 5'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:15px center;transition:border-color .2s,box-shadow .2s}
.kh-search:focus{border-color:#477fe1;box-shadow:0 0 0 4px #477fe118;outline:none}
.kh-count{font-size:12px;color:#657892;white-space:nowrap;font-weight:750;background:#eaf0f8;border:1px solid #dce5f1;padding:9px 12px;border-radius:25px}
.kh-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:17px;align-items:stretch}
.kh-store{position:relative;display:flex;flex-direction:column;align-items:stretch;min-width:0;min-height:164px;background:linear-gradient(145deg,#fff 0%,#fbfdff 100%);border:1px solid #dfe7f2;border-radius:17px;box-shadow:0 3px 7px #18335107,0 12px 29px #18335105;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease;overflow:visible}
.kh-store:before{content:'';position:absolute;left:0;top:22px;bottom:22px;width:3px;background:#4a83df;border-radius:0 4px 4px 0;opacity:.65;transition:opacity .2s}
.kh-store-main{display:flex;align-items:center;gap:14px;padding:20px 9px 15px 20px;flex:1;min-width:0;color:inherit;text-decoration:none}
.kh-store:hover,.kh-store:focus-within{transform:translateY(-3px);border-color:#8eafe4;box-shadow:0 14px 29px #15396514,0 4px 10px #15396508}
.kh-store:hover:before,.kh-store:focus-within:before{opacity:1}
.kh-store-main:focus-visible,.kh-more:focus-visible{outline:3px solid #4b87eb;outline-offset:2px}
.kh-store-icon{display:grid;place-items:center;border-radius:14px;background:linear-gradient(140deg,#e8f2ff,#d8e7fd);color:#366dbb;font-size:24px;font-weight:700;width:51px;height:51px;flex-shrink:0;box-shadow:inset 0 1px 0 #ffffffbd}
.kh-store-copy{display:flex;flex-direction:column;min-width:0;gap:8px;flex:1}
.kh-store-name{font-size:15px;line-height:1.35;font-weight:800;color:#1f304c;overflow-wrap:anywhere;display:flex;align-items:center;gap:7px;letter-spacing:-.3px}.kh-client-label{min-width:0;overflow-wrap:anywhere}
.kh-trend{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;flex-shrink:0;vertical-align:middle}.kh-trend svg{display:block;width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2.25;stroke-linecap:round;stroke-linejoin:round}.kh-trend.up{color:#15915c}.kh-trend.down{color:#df4853}.kh-trend.flat{color:#8292aa}
.kh-status{font-size:11px;color:#687b94;display:flex;gap:5px;align-items:center;font-weight:650;letter-spacing:.03em;text-transform:uppercase}
.kh-status span{display:none}.kh-active{color:#527090}.kh-inactive{color:#bc713c}
.kh-more{border:0;background:transparent;color:#6b7e99;font-size:25px;line-height:1;cursor:pointer;align-self:flex-start;margin:12px 11px 0 0;padding:4px 9px;border-radius:9px;transition:background .16s,color .16s}
.kh-more:hover,.kh-more[aria-expanded=true]{background:#e8effa;color:#24456f}
.kh-menu{position:absolute;right:9px;top:48px;z-index:10;background:#fff;border:1px solid #d9e4f2;border-radius:12px;box-shadow:0 18px 40px #12274430;padding:5px;min-width:180px}
.kh-menu[hidden]{display:none}.kh-menu button,.kh-menu a{width:100%;box-sizing:border-box;display:block;text-align:left;background:transparent;border:0;padding:11px;border-radius:8px;color:#253954;font:inherit;font-size:13px;font-weight:600;text-decoration:none;cursor:pointer}
.kh-menu button:hover,.kh-menu a:hover{background:#edf3fc}.kh-menu .kh-danger{color:#bd3642}
.kh-card-bottom{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 18px 0 20px;padding:14px 0 18px;border-top:1px solid #e9eef5;min-height:64px}
.kh-metric{display:flex;flex-direction:column;gap:6px;min-width:0}.kh-metric-label{font-size:9px;line-height:1.2;letter-spacing:1px;font-weight:850;color:#8190a7}
.kh-metric-value{font-size:12px;color:#8390a4;font-weight:750;display:flex;align-items:center;gap:6px}
.kh-metric-value.up{color:#15895c}.kh-metric-value.down{color:#c44051}.kh-metric-value.flat{color:#76849b}
.kh-metric-value.down:before,.kh-metric-value.up:before{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;background:currentColor}
.kh-card-go{font-size:11px;white-space:nowrap;display:inline-flex;align-items:center;gap:4px;color:#516f9b;font-weight:750;opacity:.7}
.kh-store:hover .kh-card-go{opacity:1;color:#2358b0}
.kh-links{display:flex;gap:9px 22px;flex-wrap:wrap;border-top:1px solid #e2e9f2;margin-top:34px;padding:23px 0 0}
.kh-links a{color:#4e6d98;text-decoration:none;font-size:13px;font-weight:650}.kh-links a:hover{text-decoration:underline;color:#2859a7}
.kh-empty{padding:38px;background:#fff;border:1px dashed #d5e1f0;border-radius:16px;color:#72839b}
@media(max-width:640px){.kh-home{padding:0 12px}.kh-grid{grid-template-columns:1fr;gap:12px}.kh-head{align-items:flex-start}.kh-toolbar{gap:10px}.kh-search{max-width:none}.kh-store{min-height:148px}.kh-store-main{padding:18px 8px 10px 17px}.kh-card-bottom{margin:0 16px 0 17px;padding:12px 0 15px;min-height:56px}.kh-metric-label{font-size:9px}.kh-store-icon{width:45px;height:45px}.kh-home h2{font-size:31px}.kh-head{margin-bottom:18px;padding-bottom:16px}.kh-toolbar{margin-bottom:17px}}
@media(prefers-reduced-motion:reduce){.kh-store,.kh-search,.kh-more{transition:none}.kh-store:hover{transform:none}}
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
// Stable alphabetical order: do not reorder cards based on trends.\nconst key='keiper:client-card-order:v1';
try{const order=JSON.parse(localStorage.getItem(key)||'[]');order.forEach(id=>{const card=cards.find(c=>c.dataset.id===String(id));if(card)grid.appendChild(card);});}catch(e){}
function saveOrder(){try{localStorage.setItem(key,JSON.stringify([...grid.children].map(c=>c.dataset.id)));}catch(e){}}
function closeMenus(){document.querySelectorAll('.kh-menu').forEach(m=>m.hidden=true);document.querySelectorAll('.kh-more').forEach(b=>b.setAttribute('aria-expanded','false'));}
grid.addEventListener('click',async e=>{
 const trigger=e.target.closest('.kh-more');
 if(trigger){const menu=trigger.nextElementSibling,opening=menu.hidden;closeMenus();menu.hidden=!opening;trigger.setAttribute('aria-expanded',String(opening));return;}
 const btn=e.target.closest('[data-act]');if(!btn)return;
 const card=btn.closest('.kh-store'),id=card.dataset.id,act=btn.dataset.act;
 closeMenus();
 if(act==='rename'){
  const label=card.querySelector('.kh-store-name');
  const old=card.querySelector('.kh-client-label').textContent.trim();
  const name=prompt('Novo nome da loja:',old);
  if(name===null||!name.trim()||name.trim()===old)return;
  try{const response=await fetch('/renomear/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({cliente:name.trim()})});const data=await response.json();if(!response.ok||!data.ok)throw Error('Falha ao renomear');card.querySelector('.kh-client-label').textContent=name.trim();refresh();}catch(err){alert('Não foi possível renomear esta loja.');}
 }
});
document.addEventListener('click',e=>{if(!e.target.closest('.kh-more,.kh-menu'))closeMenus();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenus();});
fetch('/painel/tendencias',{credentials:'same-origin'}).then(r=>{if(!r.ok)throw Error('indisponível');return r.json();}).then(d=>{
 for(const card of cards){const trend=d[String(card.dataset.id)];if(!trend)continue;
 const span=card.querySelector('.kh-trend');span.className='kh-trend '+trend;span.innerHTML=trend==='up'?'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 16 16 4M7 4h9v9"/></svg>':trend==='down'?'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4 4 12 12M7 16h9V7"/></svg>':'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h14m-5-5 5 5-5 5"/></svg>';
 const label=trend==='up'?'Sinal de crescimento':trend==='down'?'Sinal de queda':'Sem mudança observada';
 span.title=label+' nos últimos 7 dias, comparados aos 7 anteriores';span.setAttribute('aria-label',label);
 const metric=card.querySelector('.kh-metric-value');metric.className='kh-metric-value '+trend;metric.textContent=label;
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
