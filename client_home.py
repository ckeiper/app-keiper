"""Fast, database-light client directory for the landing page."""
from html import escape
from home_theme import NAVY_HOME_CSS


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
            "<span class='kh-store-copy'><strong class='kh-store-name'><span class='kh-trend' role='img' aria-label='Tendência de faturamento indisponível' title='Tendência de faturamento indisponível'></span><span class='kh-client-label'>" + name + "</span></strong>"
            "<span class='kh-status " + ("kh-active" if active else "kh-inactive") + "'>"
            "<span aria-hidden='true'>●</span> " + label + "</span></span>"
            "</a><button type='button' class='kh-more' aria-label='Opções de " + name + "' aria-expanded='false'>⋯</button>"
            "<div class='kh-menu' hidden><button type='button' data-act='rename'>Renomear</button>"
            "<a href='/excluir/" + str(cid) + "' class='kh-danger'>Excluir loja…</a></div>"
            "<div class='kh-alerts' aria-live='polite'></div></article>"
        )
    empty = ("<div class='kh-empty'>Nenhuma loja disponível. "
             + ("Conecte a primeira loja para começar." if admin else "Contate o administrador.")
             + "</div>") if not cards else ""
    count = str(len(cards)) + (" loja" if len(cards) == 1 else " lojas")
    return NAVY_HOME_CSS + """<style>
.kh-home{max-width:1240px;margin:4px auto 56px;padding:0 28px;color:#16243b;font-family:Inter,'Segoe UI',Arial,sans-serif}
.kh-head{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;flex-wrap:wrap;margin:0 0 28px;padding:8px 0 20px;border-bottom:1px solid #e4eaf3}
.kh-eyebrow{color:#5479bd;font-size:11px;font-weight:800;letter-spacing:2px;text-transform:uppercase}
.kh-home h2{font-size:clamp(30px,4vw,40px);line-height:1.15;letter-spacing:-1.35px;margin:9px 0 8px;font-weight:800;color:#172947}
.kh-ads-status{font-size:12px;color:#a4b6d0;margin:0 0 8px auto;line-height:1.5;text-align:right}.kh-alerts:empty{display:none}
.kh-count{font-size:12px;color:#657892;white-space:nowrap;font-weight:750;background:#eaf0f8;border:1px solid #dce5f1;padding:9px 12px;border-radius:25px}
.kh-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:17px;align-items:stretch}
.kh-store{position:relative;display:flex;flex-direction:column;align-items:stretch;min-width:0;min-height:104px;background:linear-gradient(145deg,#fff 0%,#fbfdff 100%);border:1px solid #dfe7f2;border-radius:17px;box-shadow:0 3px 7px #18335107,0 12px 29px #18335105;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease;overflow:visible}
.kh-store:before{content:'';position:absolute;left:0;top:22px;bottom:22px;width:3px;background:#4a83df;border-radius:0 4px 4px 0;opacity:.65;transition:opacity .2s}
.kh-store-main{display:flex;align-items:center;gap:14px;padding:20px 49px 20px 20px;flex:1;min-width:0;color:inherit;text-decoration:none}
.kh-store:hover,.kh-store:focus-within{transform:translateY(-3px);border-color:#8eafe4;box-shadow:0 14px 29px #15396514,0 4px 10px #15396508}
.kh-store:hover:before,.kh-store:focus-within:before{opacity:1}
.kh-store-main:focus-visible,.kh-more:focus-visible{outline:3px solid #4b87eb;outline-offset:2px}
.kh-store-icon{display:grid;place-items:center;border-radius:14px;background:linear-gradient(140deg,#e8f2ff,#d8e7fd);color:#366dbb;font-size:24px;font-weight:700;width:51px;height:51px;flex-shrink:0;box-shadow:inset 0 1px 0 #ffffffbd}
.kh-store-copy{display:flex;flex-direction:column;min-width:0;gap:8px;flex:1}
.kh-store-name{font-size:15px;line-height:1.35;font-weight:800;color:#1f304c;overflow-wrap:anywhere;display:flex;align-items:center;gap:7px;letter-spacing:-.3px}.kh-client-label{min-width:0;overflow-wrap:anywhere}
.kh-trend{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;flex-shrink:0;vertical-align:middle}.kh-trend svg{display:block;width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2.25;stroke-linecap:round;stroke-linejoin:round}.kh-trend.up{color:#15915c}.kh-trend.down{color:#df4853}.kh-trend.flat{color:#8292aa}
.kh-status{font-size:11px;color:#687b94;display:flex;gap:5px;align-items:center;font-weight:650;letter-spacing:.03em;text-transform:uppercase}
.kh-status span{display:none}.kh-active{color:#527090}.kh-inactive{color:#bc713c}
.kh-more{position:absolute;right:8px;top:12px;border:0;background:transparent;color:#6b7e99;font-size:25px;line-height:1;cursor:pointer;align-self:flex-start;margin:0;padding:4px 9px;border-radius:9px;transition:background .16s,color .16s}
.kh-more:hover,.kh-more[aria-expanded=true]{background:#e8effa;color:#24456f}
.kh-menu{position:absolute;right:9px;top:48px;z-index:10;background:#fff;border:1px solid #d9e4f2;border-radius:12px;box-shadow:0 18px 40px #12274430;padding:5px;min-width:180px}
.kh-menu[hidden]{display:none}.kh-menu button,.kh-menu a{width:100%;box-sizing:border-box;display:block;text-align:left;background:transparent;border:0;padding:11px;border-radius:8px;color:#253954;font:inherit;font-size:13px;font-weight:600;text-decoration:none;cursor:pointer}
.kh-menu button:hover,.kh-menu a:hover{background:#edf3fc}.kh-menu .kh-danger{color:#bd3642}
.kh-empty{padding:38px;background:#fff;border:1px dashed #d5e1f0;border-radius:16px;color:#72839b}
.kh-alerts{border-top:1px solid #e4eaf3;padding:11px 16px;font-size:12px;line-height:1.5;overflow-wrap:anywhere}.kh-alerts a{color:inherit;text-decoration:none;display:block}.kh-alerts a:hover{text-decoration:underline}.kh-alerts a:focus-visible{outline:3px solid #4b87eb;outline-offset:2px}.kh-alerts .critical{color:#b83240}.kh-alerts .warning{color:#966017}.kh-alerts .good{color:#14764e}.kh-alert-muted{color:#738197}.kh-alert-more{font-size:11px;margin-top:5px;color:#526b91!important}
body:has(.kh-home) .kh-alerts{border-color:#2d425e}body:has(.kh-home) .kh-alerts .critical{color:#ff98a5}body:has(.kh-home) .kh-alerts .warning{color:#f5c783}body:has(.kh-home) .kh-alerts .good{color:#72dfb5}body:has(.kh-home) .kh-alert-muted{color:#a4b6d0}body:has(.kh-home) .kh-alert-more{color:#aac8f6!important}.kh-alerts button{background:transparent;border:1px solid #526b91;border-radius:7px;padding:7px;text-align:left;font:inherit;cursor:pointer}
@media(max-width:640px){.kh-home{padding:0 12px}.kh-grid{grid-template-columns:1fr;gap:12px}.kh-head{align-items:flex-start}.kh-store{min-height:96px}.kh-store-main{padding:18px 47px 18px 17px}.kh-store-icon{width:45px;height:45px}.kh-home h2{font-size:31px}.kh-head{margin-bottom:18px;padding-bottom:16px}}
@media(prefers-reduced-motion:reduce){.kh-store,.kh-more{transition:none}.kh-store:hover{transform:none}}
</style><main class='kh-home'>
<section class='kh-head'><div><div class='kh-eyebrow'>Keiper · Workspace</div>
<h2>Suas lojas <span class='kh-count' id='kh-count'>""" + count + """</span></h2></div><p class='kh-ads-status' id='kh-ads-status' role='status'>Atualizando Ads…</p></section>
<section id='kh-grid' class='kh-grid' aria-label='Lojas conectadas'>""" + "".join(cards) + """</section>""" + empty + """</main>
<script>
(function(){
const cards=[...document.querySelectorAll('#kh-grid .kh-store')];
const grid=document.getElementById('kh-grid');
// Load with bounded concurrency so a portfolio does not flood the database.
let alertIndex=0,finished=0,failures=0,lastUpdated=0;
const adsStatus=document.getElementById('kh-ads-status');
function updateAdsStatus(){
 if(finished<cards.length){adsStatus.textContent='Atualizando Ads… '+finished+'/'+cards.length;return;}
 if(!cards.length){adsStatus.textContent='';return;}
 const time=lastUpdated?new Date(lastUpdated*1000).toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit'}):'';
 adsStatus.textContent=failures?(time?'Ads atualizados parcialmente às '+time:'Não foi possível atualizar os Ads'):'Ads atualizados às '+time;
}
updateAdsStatus();
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
async function refreshAds(id){
 const endpoint='/atualizacoes/'+encodeURIComponent(id)+'/ads?de='+today+'&ate='+today;
 const response=await fetch(endpoint,{method:'POST',headers:{Accept:'application/json'}});
 if(!response.ok)throw Error('refresh');const job=await response.json();
 const deadline=Date.now()+600000;
 while(Date.now()<deadline){await pause(1500);const r=await fetch(endpoint,{cache:'no-store',headers:{Accept:'application/json'}});if(!r.ok)throw Error('status');const state=await r.json();
 if(state.id!==job.id)throw Error('changed');if(state.status==='concluida')return state;
 if(!['aguardando','executando'].includes(state.status))throw Error('failed');}
 throw Error('timeout');
}
async function loadAlerts(){while(alertIndex<cards.length){
 const card=cards[alertIndex++],box=card.querySelector('.kh-alerts');
 const link=(text,url,cls)=>{const a=document.createElement('a');a.textContent=text;a.href=url;a.className=cls;box.appendChild(a);};
 try{const state=await refreshAds(card.dataset.id);const response=await fetch('/painel/alertas/'+encodeURIComponent(card.dataset.id),{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();box.replaceChildren();
 if(data.alerts.length){const first=data.alerts[0];link(first.label,data.url+'#alert-'+first.code,first.severity);if(data.alerts.length>1)link('+'+(data.alerts.length-1)+(data.alerts.length===2?' alerta':' alertas'),data.url,'kh-alert-more');}
 else{link(data.known?'Nenhum alerta nos dados disponíveis':'Campanhas ainda não sincronizadas',data.url,'kh-alert-muted');}
 lastUpdated=Math.max(lastUpdated,Number(state.fim_em)||0);
 }catch(e){failures++;box.replaceChildren();const retry=document.createElement('button');retry.type='button';retry.textContent='Falha ao atualizar Ads · tentar novamente';retry.className='kh-alert-muted';retry.addEventListener('click',()=>location.reload());box.appendChild(retry);}finally{finished++;updateAdsStatus();}
}}
Promise.all([loadAlerts(),loadAlerts()]);
// Cards are server-rendered alphabetically and never reordered by performance.
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
  try{const response=await fetch('/renomear/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({cliente:name.trim()})});const data=await response.json();if(!response.ok||!data.ok)throw Error('Falha ao renomear');card.querySelector('.kh-client-label').textContent=name.trim();}catch(err){alert('Não foi possível renomear esta loja.');}
 }
});
document.addEventListener('click',e=>{if(!e.target.closest('.kh-more,.kh-menu'))closeMenus();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenus();});
fetch('/painel/tendencias',{credentials:'same-origin'}).then(r=>{if(!r.ok)throw Error('indisponível');return r.json();}).then(d=>{
 for(const card of cards){const trend=d[String(card.dataset.id)];if(!trend)continue;
 const span=card.querySelector('.kh-trend');span.className='kh-trend '+trend;span.innerHTML=trend==='up'?'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 16 16 4M7 4h9v9"/></svg>':trend==='down'?'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4 4 12 12M7 16h9V7"/></svg>':'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h14m-5-5 5 5-5 5"/></svg>';
 const label=trend==='up'?'Faturamento em alta':trend==='down'?'Faturamento em queda':'Faturamento estável';
 span.title=label+' nos últimos 7 dias, comparados aos 7 anteriores';span.setAttribute('aria-label',span.title);
 }
}).catch(()=>{});
})();
</script>"""
