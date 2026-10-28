"""Browser-local appearance preference shared by both dashboard page shells."""

HEAD = """<script>(function(){var t='dark';try{if(localStorage.getItem('keiper-theme')==='light')t='light';}catch(e){}document.documentElement.dataset.theme=t;})();</script>
<style>
html[data-theme]{color-scheme:dark}
html[data-theme=light]{color-scheme:light;--kp-ink:#172d47;--kp-subtle:#52657c;--kp-bg:#f3f6fb;--kp-line:#d4dfec}
.kt-theme-toggle{display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:40px;padding:9px 13px;border:1px solid #526d8d;border-radius:10px;background:#18314b;color:#edf5ff;font:inherit;font-size:12px;font-weight:650;cursor:pointer;white-space:nowrap}
.kt-theme-toggle:focus-visible{outline:3px solid #479df1;outline-offset:3px}
@media(max-width:640px){.kt-theme-toggle{min-height:44px;padding:9px 11px}}
@media print{.kt-theme-toggle{display:none!important}}
/* Layered important declarations outrank the legacy unlayered scoped styles. */
@layer keiper-appearance {
html[data-theme=light] body{background:#f3f6fb!important;color:#172d47!important;color-scheme:light!important}
html[data-theme=light] body :where(.layout,.conteudo,.ap-progress,.kh-home,.mgmt-dashboard,.ka-ads,.k-camp,.kyra,.listing-diag,.freight-audit,.full-report){background:transparent!important;color:#172d47!important;--ink:#172d47;--muted:#52657c;--line:#d4dfec;--fa-bg:#fff;--fa-panel:#fff;--fa-line:#c5d5e6;--fa-text:#172d47;--fa-muted:#52657c;--fa-accent:#185bad;--ky-muted:#52657c;--ky-line:#c5d5e6}
html[data-theme=light] body :where(section,article,.card,.stat,.kh-store,.kh-menu,.kh-crm,.mgmt-preview-card,.mgmt-filter,.mgmt-period,.mgmt-chart,.mgmt-drawer,.ka-alert,.kc-campaign-row,.diag-action,.diag-next,.diag-summary,.diag-actions-empty,.diag-hint,.ky-panel,.ky-stat,.ky-finding,.ky-card,.kc-card,.full-summary,.promo-item,.ap-card,.ap-scope,.mgmt-shortcut,.mgmt-ads-strip,.top-store,.kh-count,.ky-campaign-card,.ky-campaign-stats>div,.ky-camp-metric,.fa-panel,.fa-guide,.fa-file,.fa-overview article,.catalog-toolbar,.catalog-filters,.catalog-table,.catalog-page,.catalog-shell,.catalog-dashboard,.listing-tasks,.item-timeline,.abc,.lc,.evidence-panel,.abc-card,.lt-cards>div,.evidence-source,.evidence-action,.evidence-next,.cross-reading,.evidence-drivers,.kc-stat,.kc-foot,.kh-health-item,.frete-metrica,.ka-alert-count,.fa-file-icon,.freight-audit .frete-metricas>div){background:#fff!important;color:#172d47!important;border-color:#d4dfec!important;box-shadow:0 3px 16px #233f6110!important}
html[data-theme=light] body :where(ul,ol,caption,nav,footer,div,span,b,strong,em,h1,h2,h3,h4,h5,p,small,label,summary,td,th,li,dt,dd,.num,.lab,.sub,.muted,.brand,.top-store,.kh-store-name,.kh-status,.kh-active,.kh-count,.kh-eyebrow,.mgmt-eyebrow,.mgmt-preview-title,.mgmt-preview-label,.mgmt-period-dates,.kc-sub,.kc-eyebrow,.diag-eyebrow,.diag-code,.ka-eyebrow,.ky-title,.ky-subtitle){color:inherit!important}
html[data-theme=light] body :where(.muted,.sub,.lab,.kh-status,.kh-active,.mgmt-period-dates,.kc-sub,.ka-budget-mini,.ka-budget-na){color:#52657c!important}
html[data-theme=light] body :where(.top,.ks-sidebar,.menu-lateral){background:#fff!important;color:#172d47!important;border-color:#d4dfec!important;box-shadow:none!important}
html[data-theme=light] body :where(.ks-store-name,.ks-sidebar a,.ks-nav-group summary,.menu-lateral a,.ks-label){color:#314e70!important}
html[data-theme=light] body :where(.ks-toggle,.ks-mobile-toggle,.kt-theme-toggle){background:#e9f1fb!important;color:#244b76!important;border-color:#b8cce3!important}
html[data-theme=light] body :where(.ks-sidebar a:hover,.ks-nav-group summary:hover,.ks-nav-group[open]>summary,.ks-sidebar a[aria-current=page],.menu-lateral .atual){background:#e3efff!important;color:#174c8c!important}
html[data-theme=light] body :where(.ks-foot,.ks-nav-children,.kh-head,.mgmt-tabs){border-color:#c5d5e6!important}
html[data-theme=light] body :where(a,.link,.kc-campaign-name,.mgmt-detail-trigger){color:#185bad!important}
html[data-theme=light] body :where(input:not([type=checkbox]):not([type=radio]),select,textarea,option){background:#fff!important;color:#172d47!important;border-color:#a6bbd2!important;color-scheme:light!important}
html[data-theme=light] body input::placeholder,html[data-theme=light] body textarea::placeholder{color:#5b7088!important;opacity:1}
html[data-theme=light] body :where(button:not(.kt-theme-toggle):not(.ks-toggle):not(.ks-mobile-toggle),.btn,.btn-acoes){background:#225fbe!important;color:#fff!important;border-color:#225fbe!important}
html[data-theme=light] body :where(button,.btn,.btn-acoes) :where(span,small,b,strong){color:inherit!important}
html[data-theme=light] body :where(th,thead){background:#eaf1fa!important;color:#314e70!important;border-color:#c5d5e6!important}
html[data-theme=light] body :where(td,tr,table){background:#fff!important;border-color:#d4dfec!important}
html[data-theme=light] body :where(tr:hover,.kc-campaign-row:hover,.kh-store:hover){background:#f0f6ff!important}
html[data-theme=light] body :where(.mgmt-header,.ka-hero,.kc-hero,.diag-hero,.ky-hero){background:#e6f0fd!important;color:#193a60!important;border-color:#b9cfe9!important}
html[data-theme=light] body :where(.aviso,.mgmt-notice,.alert,.warning){background:#fff4db!important;color:#704b06!important;border-color:#dabb76!important}
html[data-theme=light] body :where(.sales-up,.mgmt-variation-up,.kh-trend.up,.var.subiu,.positive,.success){color:#087447!important}
html[data-theme=light] body :where(.sales-down,.mgmt-variation-down,.kh-trend.down,.var.caiu,.negative,.ks-danger){color:#b22539!important}
html[data-theme=light] body :where(.sales-neutral,.mgmt-variation-neutral,.kh-trend.flat){color:#52657c!important}
html[data-theme=light] body :where(.ka-budget-track){background:#dce7f4!important}
html[data-theme=light] body :where(.mgmt-metric-icon,.kh-store-icon,.mgmt-tab-count,.mgmt-pill,.kc-badge){background:#e5effb!important;color:#24598e!important}
html[data-theme=light] body :where(.mgmt-chart-x,.mgmt-chart-y,.mgmt-chart-axis,.mgmt-chart-legend){color:#52657c!important}
html[data-theme=light] body svg text{fill:#52657c!important}
html[data-theme=light] body .mgmt-chart-plot{border-color:#bdcfe3!important}
html[data-theme=light] body :where(.fa-hero,.fa-shop,.fa-tag,.fa-export,.ky-core,.ky-chip,.ky-tag,.ky-category,.ky-rank){background:#e6f0fd!important;color:#24598e!important;border-color:#b9cfe9!important}
html[data-theme=light] body :where(.ky-purple,.ky-cyan,.ky-amber,.ky-overline,.ky-orbit-caption,.ky-evidence-label,.ky-stat-label,.ky-muted,.meta,.kc-loading,.mgmt-preview-action,.mgmt-product-placeholder){color:#52657c!important}
html[data-theme=light] body :where(.catalog-badge.catalog-green,.alerta.ok){background:#e4f6ee!important;color:#087447!important}
html[data-theme=light] body :where(.catalog-badge.catalog-red){background:#ffebe7!important;color:#a6293c!important}
html[data-theme=light] body :where(.catalog-badge.catalog-amber){background:#fff2db!important;color:#79530b!important}
html[data-theme=light] body :where(.catalog-badge.catalog-neutral){background:#edf0f7!important;color:#52657c!important}
html[data-theme=light] body :where(.filtro-btn,.ky-button){background:#225fbe!important;color:#fff!important}
html[data-theme=light] body .ka-budget-head b[style*="#dc646d"]{color:#b22539!important}
html[data-theme=light] body .ka-budget-head b[style*="#e2a646"]{color:#79530b!important}
html[data-theme=light] body .ka-budget-head b[style*="#2da99d"]{color:#087447!important}
}
</style>"""

SCRIPT = """<script>(function(){
var root=document.documentElement,key='keiper-theme';
function charts(){if(typeof Chart==='undefined')return;Object.values(Chart.instances).forEach(function(chart){
var light=root.dataset.theme==='light';
function change(object,property,value){if(!object)return;var saved=object.$keiperColors||(object.$keiperColors={});if(!(property in saved))saved[property]=object[property];object[property]=light?value:saved[property];}
Object.values(chart.options.scales||{}).forEach(function(axis){change(axis.ticks,'color','#52657c');change(axis.grid,'color','#dbe4ef');});
var legend=chart.options.plugins&&chart.options.plugins.legend;change(legend&&legend.labels,'color','#314e70');chart.update('none');});}
function sync(){var light=root.dataset.theme==='light';document.querySelectorAll('.kt-theme-toggle').forEach(function(button){button.textContent=light?'☾ Tema escuro':'☀ Tema claro';button.setAttribute('aria-label',light?'Ativar tema escuro':'Ativar tema claro');button.setAttribute('aria-pressed',String(light));});charts();}
function mount(){var button=document.createElement('button');button.type='button';button.className='kt-theme-toggle';button.addEventListener('click',function(){root.dataset.theme=root.dataset.theme==='light'?'dark':'light';try{localStorage.setItem(key,root.dataset.theme);}catch(e){}sync();});var top=document.querySelector('.top');if(top)top.appendChild(button);else{button.style.cssText='position:fixed;right:12px;top:12px;z-index:1100';document.body.appendChild(button);}sync();}
window.addEventListener('storage',function(e){if(e.key===key){root.dataset.theme=e.newValue==='light'?'light':'dark';sync();}});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
window.addEventListener('load',function(){if(root.dataset.theme==='light')charts();},{once:true});
})();</script>"""
