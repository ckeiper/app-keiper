"""Keiper dashboard visual refresh.

Pure CSS override: preserve all existing templates, endpoints and data logic.
"""
VISUAL_CSS = """
<style>
:root {
  --kp-ink:#17233c;
  --kp-subtle:#63728b;
  --kp-blue:#315cdd;
  --kp-blue-dark:#2547b7;
  --kp-bg:#f3f6fb;
  --kp-line:#e4eaf3;
  --kp-shadow:0 3px 16px rgba(25,46,90,.045),0 12px 34px rgba(25,46,90,.035);
}
html { scroll-behavior:smooth; }
body {
  background:var(--kp-bg);
  color:var(--kp-ink);
  font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
  line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.top {
  background:linear-gradient(112deg,#132443 0%,#1c3566 58%,#234b94 100%);
  padding:17px clamp(16px,3vw,42px);
  border-bottom:1px solid rgba(255,255,255,.12);
  box-shadow:0 4px 22px rgba(19,36,67,.12);
  gap:18px;
  min-height:82px;
}
.top h1 {font-size:19px;letter-spacing:-.35px;gap:10px;}
.top .brand {color:#c7d5ee;font-size:12px;margin-top:3px;opacity:1;}
.top a.btn {
  background:#fff;color:#213c73;border:1px solid rgba(255,255,255,.5);
  border-radius:10px;padding:10px 17px;
  box-shadow:0 3px 10px rgba(0,0,0,.08);
  transition:transform .16s ease,box-shadow .16s ease,background .16s ease;
}
.top a.btn:hover {transform:translateY(-1px);box-shadow:0 5px 16px rgba(0,0,0,.15);}
.top a.btn.sair {
  background:rgba(255,255,255,.10);color:#fff;
  border:1px solid rgba(255,255,255,.24);box-shadow:none;
}
.top a.btn.sair:hover {background:rgba(255,255,255,.20);}
.top .top-store {
  color:#e8efff;font-size:14px;font-weight:650;
  padding:7px 15px;border:1px solid rgba(255,255,255,.2);
  border-radius:999px;background:rgba(255,255,255,.08);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  max-width:min(36vw,420px);
}
.wrap {max-width:1530px;margin:28px auto;padding:0 clamp(14px,2.5vw,34px);}
.layout {gap:26px;}
.menu-lateral {
  width:235px;padding:16px 11px;
  border:1px solid var(--kp-line);
  border-radius:16px;box-shadow:var(--kp-shadow);
  top:20px;
}
.menu-lateral .voltar {
  padding:10px 12px 15px;margin-bottom:10px;
  border-bottom:1px solid var(--kp-line);
  font-size:12px;color:var(--kp-subtle);
}
.menu-lateral a.item {
  border-radius:10px;padding:11px 13px;
  font-size:13.5px;font-weight:600;color:#46546b;
  margin:2px 0;transition:background .16s ease,color .16s ease;
}
.menu-lateral a.item:hover {background:#eef3ff;color:#2547b7;}
.menu-lateral a.item.atual {
  background:linear-gradient(100deg,#315cdd,#4775ef);
  color:#fff;box-shadow:0 5px 14px rgba(49,92,221,.22);
}
.menu-lateral a.item.perigo {margin-top:10px;border-top:1px solid var(--kp-line);border-radius:0;padding-top:16px;}
.conteudo {padding-bottom:30px;}
.card,.stat {
  border:1px solid var(--kp-line);border-radius:16px;
  box-shadow:var(--kp-shadow);background:#fff;
}
.card {padding:clamp(17px,2vw,26px);margin-bottom:20px;}
.grid {gap:16px;}
.stat {
  border-left:0;padding:21px;position:relative;overflow:hidden;
  transition:transform .16s ease,box-shadow .16s ease;
}
.stat:before {
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#315cdd,#71a4ff);
}
.stat:hover {transform:translateY(-2px);box-shadow:0 12px 30px rgba(25,46,90,.09);}
.stat .num {font-size:clamp(23px,2.2vw,31px);letter-spacing:-.8px;color:#1d3566;font-variant-numeric:tabular-nums;}
.stat .lab {font-size:12px;letter-spacing:.1px;color:var(--kp-subtle);}
h2 {font-size:21px;letter-spacing:-.45px;color:var(--kp-ink);line-height:1.3;}
.sub {color:var(--kp-subtle);}
table {border-collapse:separate;border-spacing:0;font-size:13px;line-height:1.45;}
th {
  background:#f5f7fc;color:#53637c;
  font-size:11px;text-transform:uppercase;letter-spacing:.5px;
  padding:13px 15px;border-bottom:1px solid var(--kp-line);
}
td {padding:13px 15px;border-bottom:1px solid #edf1f7;color:#34445f;}
tr:hover td {background:#f7f9fe;}
tbody tr:last-child td {border-bottom:0;}
td:first-child {font-weight:500;}
table a {color:var(--kp-blue);}
a.link {color:var(--kp-blue);}
.btn-acoes,.btn-salvar,.btn-pequeno,.filtro-btn {
  background:var(--kp-blue);border-radius:9px;
  transition:background .16s ease,transform .16s ease;
}
.btn-acoes:hover,.btn-salvar:hover,.btn-pequeno:hover,.filtro-btn:hover {
  background:var(--kp-blue-dark);transform:translateY(-1px);
}
.btn-acoes.cinza {background:#edf1f8;color:#334563;}
.btn-acoes.cinza:hover {background:#dfe7f3;}
.filtro {
  text-decoration:none;color:#36517e;background:#fff;
  border:1px solid #d9e2f0;border-radius:9px;
  padding:8px 13px;font-weight:600;
  transition:background .16s ease,border-color .16s ease;
}
.filtro:hover {background:#eef3ff;border-color:#8ea9ed;}
.input,.input-inline {
  border:1px solid #d8e1ef;border-radius:10px;
  background:#fff;color:var(--kp-ink);
}
.input:focus,.input-inline:focus {
  outline:2px solid #aec5ff;outline-offset:1px;border-color:var(--kp-blue);
}
.muted {color:var(--kp-subtle);}
.aviso,.sucesso {border-radius:12px;}
a:focus-visible,button:focus-visible {
  outline:3px solid #8baafc;outline-offset:3px;
}
@media(max-width:1000px) {
  .wrap {margin-top:20px;}
  .layout {gap:17px;}
  .menu-lateral {width:195px;}
}
@media(max-width:820px) {
  .top {min-height:auto;padding:15px 17px;gap:12px;}
  .top h1 {font-size:17px;}
  .top .top-store {max-width:100%;order:3;flex-basis:100%;font-size:12px;}
  .wrap {padding:0 13px;margin:16px auto;}
  .layout {flex-direction:column;}
  .menu-lateral {
    width:100%;position:static;display:flex;gap:5px;
    overflow-x:auto;white-space:nowrap;padding:9px;
    scrollbar-width:thin;
  }
  .menu-lateral .voltar {
    display:inline-flex;align-items:center;
    padding:10px 12px;margin:0;border:0;
    border-right:1px solid var(--kp-line);
  }
  .menu-lateral a.item {
    display:inline-flex;align-items:center;flex-shrink:0;
    margin:0;padding:10px 12px;
  }
  .menu-lateral a.item.perigo {
    margin:0;padding:10px 12px;border:0;
  }
  .card {padding:16px;}
  .stat {padding:17px;}
  .grid {grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:11px;}
  th,td {padding:10px 11px;}
  h2 {font-size:19px;}
}
@media(max-width:440px) {
  .top a.btn {padding:8px 11px;font-size:12px;}
  .grid {grid-template-columns:repeat(2,minmax(0,1fr));}
  .stat .num {font-size:22px;overflow-wrap:anywhere;}
  .top .top-store {order:3;}
}
@media(prefers-reduced-motion:reduce) {
  *,*:before,*:after {scroll-behavior:auto!important;transition:none!important;}
}
@media print {
  .top,.menu-lateral {display:none!important;}
  .card,.stat {box-shadow:none;border-color:#ddd;}
  .wrap {max-width:100%;margin:0;}
}

/* Hybrid compact system-wide: shared pages and per-store navigation. */
:root {--kp-bg:#f5f7fb;--kp-ink:#172338;--kp-subtle:#64748b;--kp-line:#e7ecf3;--kp-shadow:0 1px 3px rgba(16,31,55,.035);}
body {background:#f5f7fb;color:#172338;}
.top {background:#15243a;min-height:64px;padding:12px clamp(16px,2vw,28px);box-shadow:none;}
.top h1 {font-size:17px;}
.wrap {max-width:1600px;margin:18px auto;padding:0 clamp(12px,1.6vw,24px);}
.layout {gap:0;background:#f5f7fb;border-radius:12px;overflow:visible;align-items:stretch;}
.layout>.menu-lateral {background:#111c2e;color:#d5deeb;border:0;border-radius:12px 0 0 12px;box-shadow:none;width:220px;top:12px;padding:13px 9px;align-self:flex-start;}
.layout>.menu-lateral .voltar {color:#cbd5e1;border-color:#314057;padding:9px 11px;font-size:12px;}
.layout>.menu-lateral a.item {color:#d5deeb;border-radius:7px;padding:9px 11px;font-size:12.5px;line-height:1.35;margin:2px 0;}
.layout>.menu-lateral a.item:hover {background:#253650;color:#fff;}
.layout>.menu-lateral a.item.atual {background:#315cdd;color:#fff;box-shadow:none;}
.layout>.menu-lateral a.item.perigo {color:#f4b4b4;border-color:#314057;}
.layout>.conteudo {background:#f5f7fb;padding:4px 0 22px 18px;min-width:0;}
.card,.stat {background:#fff;border:1px solid #e7ecf3;border-radius:10px;box-shadow:0 1px 3px rgba(16,31,55,.035);}
.card {padding:15px;margin-bottom:13px;}
.grid {gap:10px;}
.stat {padding:13px 14px;}
.stat:before {height:2px;background:#d9e5f8;}
.stat:hover {transform:none;box-shadow:0 1px 3px rgba(16,31,55,.035);}
.stat .num {font-size:22px;letter-spacing:-.5px;}
.stat .lab {font-size:11px;}
h2 {font-size:17px;letter-spacing:-.3px;}
table {font-size:12px;border-collapse:collapse;}
th {font-size:10.5px;padding:9px 10px;letter-spacing:.3px;background:#f8fafc;}
td {padding:9px 10px;}
@media(max-width:820px) {
  .layout {display:flex;flex-direction:column;gap:12px;}
  .layout>.menu-lateral {width:100%;border-radius:10px;position:static;display:flex;overflow-x:auto;white-space:nowrap;align-self:stretch;}
  .layout>.menu-lateral .voltar {border:0;border-right:1px solid #314057;margin:0;padding:9px 11px;}
  .layout>.menu-lateral a.item {flex-shrink:0;margin:0;padding:9px 11px;}
  .layout>.conteudo {padding:0 0 20px;}
  .wrap {margin:12px auto;}
  .card {padding:12px;}
  .stat {padding:12px;}
}
/* Refinamento de cards por loja */
body:has(.ks-store-sidebar) .conteudo .stat{padding:19px;border-radius:14px;border-color:#dfe7f3;box-shadow:0 5px 18px rgba(16,31,55,.045)}
body:has(.ks-store-sidebar) .conteudo .stat .num{font-size:clamp(23px,2.3vw,30px);font-weight:750;line-height:1.18;color:#182f57}
body:has(.ks-store-sidebar) .conteudo .stat .lab{font-size:12px;font-weight:600;color:#60718c}
body:has(.ks-store-sidebar) .conteudo .card{padding:clamp(16px,1.8vw,24px);border-radius:14px;border-color:#e1e8f2}
body:has(.ks-store-sidebar) .conteudo h2{font-size:clamp(18px,1.7vw,23px);font-weight:750;color:#192e50}
body:has(.ks-store-sidebar) .conteudo th{font-size:11px;background:#f2f6fc;color:#526783;padding:12px}
body:has(.ks-store-sidebar) .conteudo td{padding:12px;border-bottom-color:#e9eef6}
@media(max-width:640px){body:has(.ks-store-sidebar) .conteudo .stat,body:has(.ks-store-sidebar) .conteudo .card{padding:14px}body:has(.ks-store-sidebar) .conteudo th,body:has(.ks-store-sidebar) .conteudo td{padding:9px}}

</style>
"""
