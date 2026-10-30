"""Progressive, local-only series controls for existing Chart.js store charts."""

CONTROLS = """<style>
.kp-chart-controls{margin:15px 0;display:flex;flex-wrap:wrap;gap:7px;align-items:center;font-family:Inter,'Segoe UI',sans-serif}.kp-chart-controls>span{width:100%;font-size:10px;color:#697d9b;margin-bottom:2px}.kp-chart-controls button{font:600 11px/1.4 Inter,'Segoe UI',sans-serif;border:1px solid #cfdaf0;background:#f5f8ff;color:#254267;border-radius:9px;min-height:38px;padding:9px 13px;cursor:pointer;display:inline-flex;align-items:center;gap:7px}.kp-chart-controls button[aria-pressed=false]{background:transparent;opacity:.65;border-style:dashed}.kp-chart-controls button:hover{border-color:#6d86cf}.kp-chart-controls button:focus-visible{outline:3px solid #6c91ed;outline-offset:2px}.kp-chart-controls i{width:7px;height:7px;border-radius:50%;background:var(--series,#7083b7)}.kp-chart-controls .kp-chart-reset{margin-left:auto;font-weight:400;background:transparent;border-color:transparent;color:#627698}
</style><script type='module'>
function enhanceCharts(){
if(!window.Chart||typeof window.Chart.getChart!=='function')return;
document.querySelectorAll('canvas').forEach(canvas=>{
if(canvas.dataset.kpPersonalized)return;
const chart=window.Chart.getChart(canvas);if(!chart||!chart.data.datasets.length)return;
canvas.dataset.kpPersonalized='true';
const controls=document.createElement('div');controls.className='kp-chart-controls';controls.setAttribute('role','group');controls.setAttribute('aria-label','Informações do gráfico');
const caption=document.createElement('span');caption.textContent='PERSONALIZAR GRÁFICO · clique nos cards para mostrar ou ocultar';controls.append(caption);
const defaults=chart.data.datasets.map((_,i)=>chart.isDatasetVisible(i));
const buttons=[];const key='keiper-chart:'+location.pathname+':'+canvas.id;
let saved;try{saved=JSON.parse(sessionStorage.getItem(key)||'null');}catch(e){}
function save(){try{sessionStorage.setItem(key,JSON.stringify(chart.data.datasets.map((_,i)=>chart.isDatasetVisible(i))));}catch(e){}}
function sync(){buttons.forEach((button,i)=>button.setAttribute('aria-pressed',String(chart.isDatasetVisible(i))));}
chart.data.datasets.forEach((dataset,index)=>{
if(Array.isArray(saved)&&saved.length===defaults.length&&typeof saved[index]==='boolean')chart.setDatasetVisibility(index,saved[index]);
const button=document.createElement('button');button.type='button';button.dataset.datasetIndex=String(index);
const swatch=document.createElement('i');swatch.setAttribute('aria-hidden','true');const color=typeof dataset.borderColor==='string'?dataset.borderColor:typeof dataset.backgroundColor==='string'?dataset.backgroundColor:'#7083b7';swatch.style.setProperty('--series',color);button.append(swatch,document.createTextNode(dataset.label||'Série '+(index+1)));
button.addEventListener('click',()=>{chart.setDatasetVisibility(index,!chart.isDatasetVisible(index));chart.update('none');sync();save();});buttons.push(button);controls.append(button);
});
const reset=document.createElement('button');reset.type='button';reset.className='kp-chart-reset';reset.textContent='Restaurar';reset.addEventListener('click',()=>{defaults.forEach((visible,i)=>chart.setDatasetVisibility(i,visible));chart.update('none');sync();save();});controls.append(reset);
const container=canvas.parentElement;container.parentElement.insertBefore(controls,container);sync();
// The existing Chart.js legend remains functional and keeps card state aligned.
controls.addEventListener('focusin',sync);canvas.addEventListener('click',()=>queueMicrotask(sync));
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
chart.stop();if(reduce){chart.options.animation=false;chart.update('none');}
else if('IntersectionObserver' in window){chart.reset();const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){chart.update();observer.disconnect();}},{threshold:.2});observer.observe(canvas);}
else chart.update('none');
});
}
enhanceCharts();window.addEventListener('load',enhanceCharts,{once:true});
// Existing pages create their charts synchronously or during DOMContentLoaded.
document.addEventListener('DOMContentLoaded',enhanceCharts,{once:true});
</script>"""
