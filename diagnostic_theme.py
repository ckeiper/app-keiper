"""Synchronization diagnostics use the directory navy palette."""
CSS = """<style>
.sync-diagnostic{max-width:1240px;margin:auto;min-width:0}
.sync-diagnostic .card{overflow-x:auto}
.sync-diagnostic .kh-health{max-width:none;margin:22px 0 28px}
html[data-theme=dark] body:has(.sync-diagnostic){background:radial-gradient(ellipse at 15% 0%,#142c50 0%,transparent 45%),#0b1426;color:#e9f0ff}
html[data-theme=dark] body:has(.sync-diagnostic) .top{background:#0d192d;border-color:#273953;box-shadow:none}
html[data-theme=dark] .sync-diagnostic :is(.card,.stat,.kh-health){background:#14233a;color:#e9f0ff;border-color:#2d425e;box-shadow:none}
html[data-theme=dark] .sync-diagnostic :is(h2,h3,.num,strong){color:#edf3ff}
html[data-theme=dark] .sync-diagnostic :is(.lab,.kh-health-head p,.kh-health-foot){color:#a4b7d2}
html[data-theme=dark] .sync-diagnostic :is(a,.kh-health-item small,.kh-health-eyebrow){color:#92bcff}
html[data-theme=dark] .sync-diagnostic .kh-health-item{background:#1a2b45;border-color:#624752;color:#edf3ff}
html[data-theme=dark] .sync-diagnostic .kh-health-item span{color:#ffa1ab}
html[data-theme=dark] .sync-diagnostic th{background:#1a2b45;color:#a8bfdf}
html[data-theme=dark] .sync-diagnostic td{border-color:#2d425e;color:#dfebff}
html[data-theme=dark] .sync-diagnostic tr:hover{background:#203858}
html[data-theme=light] .sync-diagnostic .kh-health{background:#fff;color:#172d47;border-color:#d4dfec}
</style>"""
