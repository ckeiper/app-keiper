"""Scoped presentation for the store costs page."""
STYLE = """<style>
body:has(.costs-theme),body:has(.costs-theme) .layout,body:has(.costs-theme) .layout>.conteudo{background:#081426;color:#eaf2ff}
body:has(.costs-theme) .conteudo .card,body:has(.costs-theme) .conteudo .stat{background:#11243a;border:1px solid #2d4864;color:#eaf2ff;border-radius:15px}
body:has(.costs-theme) .conteudo h2,body:has(.costs-theme) .conteudo .stat .num{color:#edf5ff}
body:has(.costs-theme) .conteudo .stat .lab,body:has(.costs-theme) .conteudo .sub,body:has(.costs-theme) .conteudo .muted{color:#bdd0e4}
body:has(.costs-theme) .conteudo input{background:#0d1d30;border:1px solid #3a5772;border-radius:8px;color:#f1f7ff;color-scheme:dark;max-width:100%;box-sizing:border-box;min-width:0}
body:has(.costs-theme) .conteudo table th{background:#1b344e;color:#d0dfef;border-color:#39536c}
body:has(.costs-theme) .conteudo table td{color:#d7e6f5;border-color:#30465c}
body:has(.costs-theme) .conteudo .link{color:#a7d9ff}
body:has(.costs-theme) .conteudo .aviso{background:#382e21;border-color:#80653c;color:#ffe0ae}
</style><span class='costs-theme' hidden></span>"""
