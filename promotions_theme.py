"""Scoped presentation for the store promotions overview."""
STYLE = """<style>
body:has(.promotions-theme),body:has(.promotions-theme) .layout,body:has(.promotions-theme) .layout>.conteudo{background:#081426;color:#eaf2ff}
body:has(.promotions-theme) .conteudo .card,body:has(.promotions-theme) .conteudo .stat,body:has(.promotions-theme) .conteudo .promo-item{background:#11243a;border:1px solid #2d4864;color:#eaf2ff;border-radius:15px}
body:has(.promotions-theme) .conteudo h2,body:has(.promotions-theme) .conteudo .stat .num,body:has(.promotions-theme) .conteudo .promo-item .titulo{color:#edf5ff}
body:has(.promotions-theme) .conteudo .stat .lab,body:has(.promotions-theme) .conteudo .sub,body:has(.promotions-theme) .conteudo .muted,body:has(.promotions-theme) .conteudo .promo-item .meta{color:#bdd0e4}
body:has(.promotions-theme) .conteudo input,body:has(.promotions-theme) .conteudo select{background:#0d1d30;border:1px solid #3a5772;border-radius:8px;color:#f1f7ff;max-width:100%;box-sizing:border-box;color-scheme:dark}
body:has(.promotions-theme) .conteudo table th{background:#1b344e;color:#d0dfef;border-color:#39536c}
body:has(.promotions-theme) .conteudo table td{color:#d7e6f5;border-color:#30465c}
body:has(.promotions-theme) .conteudo .promo-item{overflow-x:auto}
body:has(.promotions-theme) .conteudo .promo-item table{min-width:720px}
body:has(.promotions-theme) .conteudo .promo-scroll-hint{display:none;color:#bdd0e4;font-size:12px}
@media(max-width:760px){body:has(.promotions-theme) .conteudo .promo-scroll-hint{display:block}}
body:has(.promotions-theme) .conteudo .link{color:#a7d9ff}
body:has(.promotions-theme) .conteudo .aviso{background:#382e21;border-color:#80653c;color:#ffe0ae}
</style><span class='promotions-theme' hidden></span>"""
